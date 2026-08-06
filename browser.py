"""
Simple Desktop Browser
-----------------------
A real browser-like desktop app built with PyQt5 + QtWebEngine.

Features:
- Multiple tabs (open/close/switch)
- Address bar (type a URL or search term and press Enter)
- Back / Forward / Reload / Home buttons
- Tab titles & icons update automatically
- New tab button (+)

Run:
    pip install PyQt5 PyQtWebEngine
    python browser.py

Build a Windows .exe (must be run ON WINDOWS):
    pip install pyinstaller
    pyinstaller --noconfirm --onefile --windowed --name Browser browser.py
    (the .exe will appear in the "dist" folder)
"""

import sys
from PyQt5.QtCore import QUrl, Qt
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QToolBar, QLineEdit,
    QAction, QWidget, QVBoxLayout, QStyle, QTabBar
)
from PyQt5.QtWebEngineWidgets import QWebEngineView

HOME_URL = "https://www.google.com"


class BrowserTab(QWebEngineView):
    def __init__(self, url=HOME_URL):
        super().__init__()
        self.load(QUrl(url))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("My Browser")
        self.resize(1200, 800)

        # --- Tabs ---
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.current_tab_changed)
        self.setCentralWidget(self.tabs)

        # --- Toolbar ---
        toolbar = QToolBar("Navigation")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        style = self.style()

        back_btn = QAction(style.standardIcon(QStyle.SP_ArrowBack), "Back", self)
        back_btn.triggered.connect(lambda: self.current_browser().back())
        toolbar.addAction(back_btn)

        forward_btn = QAction(style.standardIcon(QStyle.SP_ArrowForward), "Forward", self)
        forward_btn.triggered.connect(lambda: self.current_browser().forward())
        toolbar.addAction(forward_btn)

        reload_btn = QAction(style.standardIcon(QStyle.SP_BrowserReload), "Reload", self)
        reload_btn.triggered.connect(lambda: self.current_browser().reload())
        toolbar.addAction(reload_btn)

        home_btn = QAction(style.standardIcon(QStyle.SP_DirHomeIcon), "Home", self)
        home_btn.triggered.connect(self.navigate_home)
        toolbar.addAction(home_btn)

        # --- Address bar ---
        self.address_bar = QLineEdit()
        self.address_bar.returnPressed.connect(self.navigate_to_url)
        toolbar.addWidget(self.address_bar)

        new_tab_btn = QAction("+", self)
        new_tab_btn.triggered.connect(lambda: self.add_new_tab())
        toolbar.addAction(new_tab_btn)

        self.add_new_tab(HOME_URL, "New Tab")

    # ---------- Tab management ----------
    def add_new_tab(self, url=HOME_URL, label="New Tab"):
        browser = BrowserTab(url)
        index = self.tabs.addTab(browser, label)
        self.tabs.setCurrentIndex(index)

        browser.urlChanged.connect(lambda qurl, b=browser: self.update_url_bar(qurl, b))
        browser.titleChanged.connect(lambda title, b=browser: self.update_tab_title(title, b))
        browser.iconChanged.connect(lambda icon, b=browser: self.update_tab_icon(icon, b))
        return browser

    def close_tab(self, index):
        if self.tabs.count() < 2:
            self.close()
            return
        self.tabs.removeTab(index)

    def current_browser(self):
        return self.tabs.currentWidget()

    def current_tab_changed(self, index):
        browser = self.current_browser()
        if browser:
            self.address_bar.setText(browser.url().toString())

    # ---------- Navigation ----------
    def navigate_home(self):
        self.current_browser().setUrl(QUrl(HOME_URL))

    def navigate_to_url(self):
        text = self.address_bar.text().strip()
        if not text:
            return
        if "." in text and " " not in text:
            if not text.startswith("http://") and not text.startswith("https://"):
                text = "https://" + text
            url = QUrl(text)
        else:
            # treat as a search query
            url = QUrl("https://www.google.com/search?q=" + text.replace(" ", "+"))
        self.current_browser().setUrl(url)

    # ---------- UI updates ----------
    def update_url_bar(self, qurl, browser=None):
        if browser != self.current_browser():
            return
        self.address_bar.setText(qurl.toString())
        self.address_bar.setCursorPosition(0)

    def update_tab_title(self, title, browser):
        index = self.tabs.indexOf(browser)
        if index != -1:
            short = title if len(title) < 20 else title[:17] + "..."
            self.tabs.setTabText(index, short or "New Tab")

    def update_tab_icon(self, icon, browser):
        index = self.tabs.indexOf(browser)
        if index != -1:
            self.tabs.setTabIcon(index, icon)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("My Browser")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
