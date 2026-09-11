import webview
import threading
import re

# Default URL to load first
DEFAULT_URL = (
    "https://studio.tripo3d.ai/3d-model/"
    "anime-girl-with-dark-hair-in-a-black-and-pink-school-uniform-"
    "wielding-bc97148a-4c5b-4196-a3ed-57cea8530be6"
)

# 3D model file extensions to detect (used as a fallback pattern)
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
# Tripo3D's signed download links always look like:
#   ...meshopt.glb?Key-Pair-Id=...&Policy=...&Signature=...
# This is a static, predictable structure, so we match on it directly
# instead of relying on a generic extension scan.
TRIPO_GLB_PATTERN = re.compile(
    r"https?://[^\s\"'<>]+\.glb\?Key-Pair-Id=[^\s\"'<>]+",
    re.IGNORECASE,
)

# --- Fallback pattern --------------------------------------------------
# Broader match against any known 3D model extension, used only if the
# primary Tripo3D-specific pattern doesn't find anything (e.g. Tripo3D
# changes their CDN param order, or the page serves a different format).
_ext_pattern = "|".join(re.escape(e) for e in MODEL_EXTENSIONS)
MODEL_URL_PATTERN = re.compile(
    rf"https?://[^\s\"'<>]+(?:{_ext_pattern})(?:[?#][^\s\"'<>]*)?",
    re.IGNORECASE,
)

window = None  # will be set in main()


class Api:
    """Python API exposed to JavaScript running inside the webview."""

    def check_for_model_url(self, page_html: str) -> str | None:
        """
        Called from JS with the full page HTML / visible text.
        Tries the static Tripo3D .glb?Key-Pair-Id= pattern first, then
        falls back to the generic extension pattern.
        Returns the first matching URL, or None.
        """
        match = TRIPO_GLB_PATTERN.search(page_html)
        if match:
            return match.group(0)

        match = MODEL_URL_PATTERN.search(page_html)
        return match.group(0) if match else None

    def redirect(self, url: str) -> None:
        """Navigate the window to *url* from Python (runs on the main thread)."""
        if window is not None:
            window.load_url(url)
            print(f"[redirect] → {url}")


# JavaScript injected into every page after it loads.
# It scans the DOM for model-file URLs and calls Python as soon as one is found.
INJECTOR_JS = """
(function () {
    var _redirected = false;

    function extractModelUrl() {
        if (_redirected) return;

        // Gather all text content that might hold a URL
        var sources = [
            document.documentElement.innerHTML,
            window.location.href,
        ];

        // Also collect href/src from anchor and media elements
        document.querySelectorAll('a[href], source[src], video[src]').forEach(function (el) {
            sources.push(el.href || el.src || '');
        });

        var combined = sources.join(' ');

        // Primary: Tripo3D's static signed .glb link structure
        var primaryPattern = /https?:\\/\\/[^\\s"'<>]+\\.glb\\?Key-Pair-Id=[^\\s"'<>]+/i;

        var match = combined.match(primaryPattern);

        if (!match) {
            // Fallback: generic extension scan
            var exts = [
                '\\.glb', '\\.gltf', '\\.fbx', '\\.obj', '\\.stl',
                '\\.ply', '\\.dae', '\\.3ds', '\\.blend',
                '\\.usdz', '\\.usd', '\\.abc', '\\.x3d',
                '\\.wrl', '\\.vrml', '\\.off', '\\.iges',
                '\\.igs', '\\.step', '\\.stp'
            ];
            var fallbackPattern = new RegExp(
                'https?://[^\\s\\"\\'<>]+(?:' + exts.join('|') + ')(?:[?#][^\\s\\"\\'<>]*)?',
                'i'
            );
            match = combined.match(fallbackPattern);
        }

        if (match) {
            _redirected = true;
            console.log('[Tripo3D Detector] Found model URL:', match[0]);
            window.pywebview.api.redirect(match[0]);
        }
    }

    // Run immediately
    extractModelUrl();

    // Also run after a short delay (for JS-rendered content)
    setTimeout(extractModelUrl, 1500);
    setTimeout(extractModelUrl, 3500);

    // Watch for dynamic DOM mutations (e.g. lazy-loaded download buttons)
    var observer = new MutationObserver(function () {
        extractModelUrl();
    });
    observer.observe(document.body || document.documentElement, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['href', 'src', 'data-url', 'data-src'],
    });
})();
"""


def on_loaded(window_ref):
    """Injected after every page load."""
    # Only scan Tripo3D pages (skip if we already landed on a model file)
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

    # Hook page-load event
    window.events.loaded += lambda: on_loaded(window)

    print("[Tripo3D Viewer] Starting …")
    print(f"[Tripo3D Viewer] Watching for: .glb?Key-Pair-Id= (primary), "
          f"{', '.join(MODEL_EXTENSIONS)} (fallback)")
    webview.start(debug=True)


if __name__ == "__main__":
    main()
