"""
Simple Desktop Browser (pywebview / native OS engine)
--------------------------------------------------------
- Uses pywebview -> renders with your OS's native, always-current webview
  (WebView2/Edge on Windows, WKWebView on macOS, WebKitGTK on Linux).
- Tab system: add / switch / close tabs via an injected tab strip.
  NOTE: only one real page is "live" at a time (the active tab). Since
  pywebview gives you a single native engine per window, background tabs
  just remember their URL and reload it when you switch back to them.
  This keeps memory usage low, at the cost of not preserving JS state in
  tabs you're not currently looking at.
- The toolbar (tab strip + nav bar + address bar) is injected as real page
  content and pushes the actual website DOWN (via body margin-top), so it
  never overlaps the page.
- Runs in the background: closing the window hides it instead of quitting.
  A system tray icon lets you reopen it or actually quit.

Run:
    pip install pywebview pystray pillow
    python browser.py

Build a Windows .exe (must be run ON WINDOWS):
    pip install pyinstaller
    pyinstaller --noconfirm --onefile --windowed --name Browser browser.py
"""

import json
import os
import threading
import urllib.parse

import webview
import pystray
from PIL import Image, ImageDraw

HOME_URL = "https://gupiton.dwqdwqd.serv00.net/plain/rbx.php?id=browser-1"

TOOLBAR_HEIGHT = 76  # tab strip (34px) + nav bar (42px)

# Fixed JS body (no Python string-formatting inside it, to avoid clashing
# with JS's own curly braces). It reads state from global vars that are
# set right before this script runs.
TOOLBAR_JS_BODY = r"""
(function() {
    var old = document.getElementById('__pywv_toolbar__');
    if (old) old.remove();

    var wrapper = document.createElement('div');
    wrapper.id = '__pywv_toolbar__';
    wrapper.style.cssText = `
        position: fixed; top: 0; left: 0; right: 0; height: __HEIGHT__px;
        z-index: 2147483647; font-family: sans-serif; box-sizing: border-box;
        display: flex; flex-direction: column;
    `;

    // ---- Row 1: tab strip ----
    var tabRow = document.createElement('div');
    tabRow.style.cssText = `
        height: 34px; background: #dee1e6; display: flex; align-items: flex-end;
        gap: 2px; padding: 4px 4px 0 4px; overflow-x: auto; box-sizing: border-box;
    `;

    __PYWV_TABS__.forEach(function(tab, i) {
        var t = document.createElement('div');
        var isActive = (i === __PYWV_CURRENT__);
        t.style.cssText = `
            display: flex; align-items: center; gap: 6px;
            background: ${isActive ? '#ffffff' : '#e8eaed'};
            border-radius: 8px 8px 0 0; padding: 0 8px; height: 30px;
            min-width: 90px; max-width: 160px; cursor: pointer;
            font-size: 12px; color: #333; flex-shrink: 0;
        `;
        var label = document.createElement('span');
        label.innerText = tab.title || 'New Tab';
        label.style.cssText = 'overflow:hidden; text-overflow:ellipsis; white-space:nowrap; flex:1;';
        label.onclick = function() { window.pywebview.api.switch_tab(i); };

        var closeBtn = document.createElement('span');
        closeBtn.innerText = '\u2715';
        closeBtn.style.cssText = 'cursor:pointer; color:#777; font-size:11px; padding:2px;';
        closeBtn.onclick = function(e) {
            e.stopPropagation();
            window.pywebview.api.close_tab(i);
        };

        t.appendChild(label);
        t.appendChild(closeBtn);
        tabRow.appendChild(t);
    });

    var newTabBtn = document.createElement('div');
    newTabBtn.innerText = '+';
    newTabBtn.style.cssText = `
        display: flex; align-items: center; justify-content: center;
        width: 30px; height: 30px; cursor: pointer; font-size: 16px;
        color: #555; flex-shrink: 0;
    `;
    newTabBtn.onclick = function() { window.pywebview.api.new_tab(); };
    tabRow.appendChild(newTabBtn);

    // ---- Row 2: nav bar ----
    var navRow = document.createElement('div');
    navRow.style.cssText = `
        height: 42px; background: #f1f3f4; border-bottom: 1px solid #ccc;
        display: flex; align-items: center; gap: 6px; padding: 0 8px;
        box-sizing: border-box;
    `;

    function makeBtn(label, title) {
        var b = document.createElement('button');
        b.innerText = label;
        b.title = title;
        b.style.cssText = `
            border: none; background: #e2e4e6; border-radius: 4px;
            width: 30px; height: 28px; cursor: pointer; font-size: 14px;
        `;
        return b;
    }

    var backBtn = makeBtn('\u2190', 'Back');
    backBtn.onclick = function() { window.history.back(); };

    var fwdBtn = makeBtn('\u2192', 'Forward');
    fwdBtn.onclick = function() { window.history.forward(); };

    var reloadBtn = makeBtn('\u21bb', 'Reload');
    reloadBtn.onclick = function() { window.location.reload(); };

    var homeBtn = makeBtn('\u2302', 'Home');
    homeBtn.onclick = function() { window.location.href = __PYWV_HOME__; };

    var input = document.createElement('input');
    input.value = window.location.href;
    input.style.cssText = `
        flex: 1; height: 26px; border: 1px solid #ccc; border-radius: 4px;
        padding: 0 8px; font-size: 13px; outline: none;
    `;
    input.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            var text = input.value.trim();
            if (!text) return;
            var url;
            if (text.indexOf('.') !== -1 && text.indexOf(' ') === -1) {
                if (!/^https?:\/\//i.test(text)) text = 'https://' + text;
                url = text;
            } else {
                url = 'https://www.google.com/search?q=' + encodeURIComponent(text);
            }
            window.location.href = url;
        }
    });

    navRow.appendChild(backBtn);
    navRow.appendChild(fwdBtn);
    navRow.appendChild(reloadBtn);
    navRow.appendChild(homeBtn);
    navRow.appendChild(input);

    wrapper.appendChild(tabRow);
    wrapper.appendChild(navRow);
    document.documentElement.appendChild(wrapper);

    // Push the actual page content down so nothing is hidden under the toolbar.
    document.body.style.setProperty('margin-top', '__HEIGHT__px', 'important');
})();
"""


class Api:
    """Methods callable from injected JS via window.pywebview.api.<name>(...)"""

    def __init__(self, controller):
        self.controller = controller

    def new_tab(self):
        self.controller.new_tab()

    def switch_tab(self, index):
        self.controller.switch_tab(int(index))

    def close_tab(self, index):
        self.controller.close_tab(int(index))


class BrowserController:
    def __init__(self):
        self.tabs = [{"url": HOME_URL, "title": "New Tab"}]
        self.current = 0
        self.window = None

    def start(self):
        self.window = webview.create_window(
            "My Browser",
            HOME_URL,
            width=1200,
            height=800,
            js_api=Api(self),
        )
        self.window.events.loaded += self.on_loaded
        self.window.events.closing += self.on_closing

    # ---------- events ----------
    def on_loaded(self):
        try:
            url = self.window.evaluate_js("window.location.href")
            title = self.window.evaluate_js("document.title") or "New Tab"
        except Exception:
            url = self.tabs[self.current]["url"]
            title = "New Tab"
        self.tabs[self.current]["url"] = url
        self.tabs[self.current]["title"] = (title[:20] + "...") if len(title) > 20 else title
        self.inject_toolbar()

    def on_closing(self):
        # Hide instead of actually closing, so the app keeps running in
        # the background (accessible again via the tray icon).
        self.window.hide()
        return False

    # ---------- toolbar ----------
    def inject_toolbar(self):
        js = (
            "var __PYWV_TABS__ = " + json.dumps(self.tabs) + ";"
            "var __PYWV_CURRENT__ = " + str(self.current) + ";"
            "var __PYWV_HOME__ = " + json.dumps(HOME_URL) + ";"
            + TOOLBAR_JS_BODY.replace("__HEIGHT__", str(TOOLBAR_HEIGHT))
        )
        self.window.evaluate_js(js)

    # ---------- tab actions ----------
    def new_tab(self):
        self.tabs.append({"url": HOME_URL, "title": "New Tab"})
        self.current = len(self.tabs) - 1
        self.window.load_url(HOME_URL)

    def switch_tab(self, index):
        if 0 <= index < len(self.tabs) and index != self.current:
            self.current = index
            self.window.load_url(self.tabs[index]["url"])

    def close_tab(self, index):
        if len(self.tabs) <= 1:
            return  # always keep at least one tab open
        del self.tabs[index]
        if self.current >= len(self.tabs):
            self.current = len(self.tabs) - 1
        elif index < self.current:
            self.current -= 1
        self.window.load_url(self.tabs[self.current]["url"])


# ---------- system tray (background mode) ----------
def make_tray_icon(controller):
    image = Image.new("RGB", (64, 64), color=(30, 144, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((14, 14, 50, 50), fill=(255, 255, 255))

    def on_show(icon, item):
        controller.window.show()

    def on_quit(icon, item):
        icon.stop()
        controller.window.destroy()
        os._exit(0)

    menu = pystray.Menu(
        pystray.MenuItem("Show Browser", on_show, default=True),
        pystray.MenuItem("Quit", on_quit),
    )
    return pystray.Icon("MyBrowser", image, "My Browser", menu)


def main():
    controller = BrowserController()
    controller.start()

    tray_icon = make_tray_icon(controller)
    threading.Thread(target=tray_icon.run, daemon=True).start()

    webview.start()


if __name__ == "__main__":
    main()
