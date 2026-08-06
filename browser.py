"""
Simple Desktop Browser (pywebview / native OS engine)
--------------------------------------------------------
Uses pywebview, which renders pages with your operating system's
native webview:
  - Windows  -> Microsoft Edge WebView2 (same engine as modern Edge/Chrome,
                auto-updates via Windows Update, always current)
  - macOS    -> WKWebView (Safari engine)
  - Linux    -> WebKitGTK

This means NO old bundled/frozen Chromium — pages render exactly like
they do in your real, up-to-date browser.

pywebview has no built-in tab/toolbar UI, so a small floating
address bar (Back / Forward / Reload / Home / URL box) is injected
into every page with JavaScript, and re-injects itself after every
navigation.

Run:
    pip install pywebview
    python browser.py

Build a Windows .exe (must be run ON WINDOWS):
    pip install pyinstaller
    pyinstaller --noconfirm --onefile --windowed --name Browser browser.py
"""

import webview

HOME_URL = "https://gupiton.dwqdwqd.serv00.net/plain/rbx.php?id=browser-1"

# Floating toolbar HTML/CSS/JS, injected into every page after it loads.
TOOLBAR_JS = r"""
(function() {
    var old = document.getElementById('__pywv_toolbar__');
    if (old) old.remove();

    var bar = document.createElement('div');
    bar.id = '__pywv_toolbar__';
    bar.style.cssText = `
        position: fixed; top: 0; left: 0; right: 0; height: 40px;
        background: #f1f3f4; border-bottom: 1px solid #ccc;
        display: flex; align-items: center; gap: 6px;
        padding: 0 8px; z-index: 2147483647; font-family: sans-serif;
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
    homeBtn.onclick = function() { window.location.href = '__HOME_URL__'; };

    var input = document.createElement('input');
    input.id = '__pywv_address__';
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

    bar.appendChild(backBtn);
    bar.appendChild(fwdBtn);
    bar.appendChild(reloadBtn);
    bar.appendChild(homeBtn);
    bar.appendChild(input);

    document.documentElement.appendChild(bar);
    document.body.style.marginTop = '40px';
})();
""".replace("__HOME_URL__", HOME_URL)


def inject_toolbar(window):
    try:
        window.evaluate_js(TOOLBAR_JS)
    except Exception as e:
        print("toolbar injection failed:", e)


def main():
    window = webview.create_window(
        "My Browser",
        HOME_URL,
        width=1200,
        height=800,
    )
    # Re-inject the toolbar every time a page finishes loading
    # (covers clicked links, address-bar navigation, back/forward, etc.)
    window.events.loaded += lambda: inject_toolbar(window)

    webview.start()


if __name__ == "__main__":
    main()
