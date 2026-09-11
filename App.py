import webview
import threading
import re
import os
import urllib.request
import urllib.parse

# Default URL to load first
DEFAULT_URL = (
    "https://studio.tripo3d.ai/3d-model/anime-girl-with-dark-hair-in-a-black-and-pink-school-uniform-wielding-bc97148a-4c5b-4196-a3ed-57cea8530be6"
)

# 3D model file extensions to detect
MODEL_EXTENSIONS = [
    ".glb", ".gltf",
    ".fbx",
    ".obj",
    ".stl",
    ".ply",
    ".dae",       # Collada
    ".3ds",
    ".blend",
    ".usdz", ".usd",
    ".abc",       # Alembic
    ".x3d",
    ".wrl", ".vrml",
    ".off",
    ".iges", ".igs",
    ".step", ".stp",
]

# --- Primary pattern -------------------------------------------------------
# Matches any known 3D model extension followed by ?Key-Pair-Id= (Tripo3D CDN).
# Previously only matched .glb — now covers all extensions in MODEL_EXTENSIONS.
_primary_ext_pattern = "|".join(re.escape(e) for e in MODEL_EXTENSIONS)
TRIPO_MODEL_PATTERN = re.compile(
    rf"https?://[^\s\"'<>]+(?:{_primary_ext_pattern})\?Key-Pair-Id=[^\s\"'<>]+",
    re.IGNORECASE,
)

# --- Fallback pattern ------------------------------------------------------
# Broader match for any model extension with any query string / fragment,
# used when the primary Tripo3D-specific pattern finds nothing.
MODEL_URL_PATTERN = re.compile(
    rf"https?://[^\s\"'<>]+(?:{_primary_ext_pattern})(?:[?#][^\s\"'<>]*)?",
    re.IGNORECASE,
)

window = None  # set in main()

DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "Tripo3D")


def _filename_from_url(url: str) -> str:
    """Extract a clean filename from a signed URL (strip query string)."""
    path = urllib.parse.urlparse(url).path
    name = os.path.basename(path) or "model.glb"
    return urllib.parse.unquote(name)


def _download_worker(url: str, dest_path: str):
    """Runs in a background thread: streams the file to disk with progress."""
    try:
        print(f"[download] Starting: {url}")
        print(f"[download] Saving to: {dest_path}")

        def report_progress(block_num, block_size, total_size):
            if total_size > 0:
                downloaded = block_num * block_size
                pct = min(100, downloaded * 100 // total_size)
                print(f"\r[download] {pct}% ({downloaded}/{total_size} bytes)", end="")

        urllib.request.urlretrieve(url, dest_path, reporthook=report_progress)
        print(f"\n[download] Done → {dest_path}")

        if window is not None:
            safe_path = dest_path.replace("\\", "\\\\").replace("'", "\\'")
            window.evaluate_js(
                f"console.log('[Tripo3D Viewer] Download complete: {safe_path}');"
            )
    except Exception as e:
        print(f"\n[download] FAILED: {e}")
        if window is not None:
            safe_err = str(e).replace("\\", "\\\\").replace("'", "\\'")
            window.evaluate_js(
                f"console.error('[Tripo3D Viewer] Download failed: {safe_err}');"
            )


class Api:
    """Python API exposed to JavaScript running inside the webview."""

    def check_for_model_url(self, page_html: str) -> str | None:
        """
        Called from JS with the full page HTML / visible text.
        Tries the Tripo3D CDN pattern first, then falls back to the
        generic extension pattern.
        Returns the first matching URL, or None.
        """
        match = TRIPO_MODEL_PATTERN.search(page_html)
        if match:
            return match.group(0)

        match = MODEL_URL_PATTERN.search(page_html)
        return match.group(0) if match else None

    def redirect(self, url: str) -> None:
        """Navigate the window to *url* from Python."""
        if window is not None:
            window.load_url(url)
            print(f"[redirect] → {url}")

    def download_model(self, url: str) -> str:
        """
        Called from JS as soon as a model URL is detected.
        Auto-saves directly to DOWNLOAD_DIR — no file dialog shown.
        Download runs in a background thread so the UI stays responsive.
        Returns a status string.
        """
        if window is None:
            return "error: window not ready"

        os.makedirs(DOWNLOAD_DIR, exist_ok=True)

        suggested_name = _filename_from_url(url)
        dest_path = os.path.join(DOWNLOAD_DIR, suggested_name)

        # Avoid overwriting an existing file with the same name
        if os.path.exists(dest_path):
            base, ext = os.path.splitext(suggested_name)
            counter = 1
            while os.path.exists(dest_path):
                dest_path = os.path.join(DOWNLOAD_DIR, f"{base}_{counter}{ext}")
                counter += 1

        threading.Thread(
            target=_download_worker, args=(url, dest_path), daemon=True
        ).start()

        return f"downloading to {dest_path}"


# JavaScript injected into every Tripo3D page after it loads.
# Patches fetch/XHR and watches the Resource Timing API to catch the
# model URL the instant it is requested, then triggers auto-download
# via the Python side.
INJECTOR_JS = """
(function () {
    var EXT_LIST = [
        '\\.glb', '\\.gltf', '\\.fbx', '\\.obj', '\\.stl',
        '\\.ply', '\\.dae', '\\.3ds', '\\.blend',
        '\\.usdz', '\\.usd', '\\.abc', '\\.x3d',
        '\\.wrl', '\\.vrml', '\\.off', '\\.iges',
        '\\.igs', '\\.step', '\\.stp'
    ];
    // Primary: any model extension + ?Key-Pair-Id= (Tripo3D CDN)
    var PRIMARY_PATTERN = new RegExp(
        'https?://[^\\s"\\'<>]+(?:' + EXT_LIST.join('|') + ')\\\\?Key-Pair-Id=[^\\s"\\'<>]+',
        'i'
    );
    // Fallback: any model extension with any query / fragment
    var FALLBACK_PATTERN = new RegExp(
        'https?://[^\\s"\\'<>]+(?:' + EXT_LIST.join('|') + ')(?:[?#][^\\s"\\'<>]*)?',
        'i'
    );

    var _found = false;

    function isModelUrl(url) {
        if (!url) return null;
        var m = url.match(PRIMARY_PATTERN);
        if (m) return m[0];
        m = url.match(FALLBACK_PATTERN);
        return m ? m[0] : null;
    }

    function onModelUrlFound(url) {
        if (_found) return;
        _found = true;
        console.log('[Network Listener] Model URL detected:', url);
        window.pywebview.api.download_model(url);
    }

    // 1. Intercept fetch()
    var _origFetch = window.fetch;
    window.fetch = function (input, init) {
        var url = typeof input === 'string' ? input : (input && input.url);
        var match = isModelUrl(url);
        if (match) onModelUrlFound(match);
        return _origFetch.apply(this, arguments);
    };

    // 2. Intercept XMLHttpRequest
    var _origOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function (method, url) {
        var match = isModelUrl(url);
        if (match) onModelUrlFound(match);
        return _origOpen.apply(this, arguments);
    };

    // 3. Resource Timing API — catches loads not made via fetch/XHR
    var observer = new PerformanceObserver(function (list) {
        list.getEntries().forEach(function (entry) {
            var match = isModelUrl(entry.name);
            if (match) onModelUrlFound(match);
        });
    });
    observer.observe({ type: 'resource', buffered: true });

    console.log('[Network Listener] Watching fetch, XHR, and resource loads for model URLs...');
})();
"""


def on_loaded(window_ref):
    """Injected after every page load."""
    current_url = window_ref.get_current_url() or ""
    if "tripo3d.ai" in current_url:
        window_ref.evaluate_js(INJECTOR_JS)
        print(f"[scanner] Injected detector on: {current_url}")


def main():
    global window

    api = Api()

    window = webview.create_window(
        title="Tripo3D — 3D Model Viewer (auto-detect)",
        url=DEFAULT_URL,
        js_api=api,
        width=1280,
        height=800,
        resizable=True,
    )

    window.events.loaded += lambda: on_loaded(window)

    print("[Tripo3D Viewer] Starting …")
    print(f"[Tripo3D Viewer] Auto-saving downloads to: {DOWNLOAD_DIR}")
    print(f"[Tripo3D Viewer] Watching extensions: {', '.join(MODEL_EXTENSIONS)}")
    webview.start(debug=False)


if __name__ == "__main__":
    main()
