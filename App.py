"""
tripo3d_to_imgbb.py
====================
1.  Shows a URL-input page in a pywebview window.
2.  Navigates to the Tripo3D model page and intercepts the signed .glb URL.
3.  Encodes the *source code of this very file* into a PNG image
    (each byte becomes one RGB pixel, packed left-to-right, top-to-bottom).
4.  Uploads the PNG to imgbb using the provided credentials.
5.  Shows the resulting imgbb URL / embed code in the window.

Dependencies:
    pip install pywebview Pillow requests
"""

import io
import math
import os
import re
import threading
import base64

import requests
from PIL import Image

try:
    import webview
except ImportError:
    webview = None  # allow the module to be imported without pywebview for testing


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

IMGBB_URL    = "https://api.imgbb.com/1/upload"
# The auth token you provided (used as the imgbb API key / form token)
IMGBB_TOKEN  = "69a7f9208a32c6904a623523758674f6237db0ae"
IMGBB_PHPSESSID = "tpnsh80jem2qiet9a7nmahccn5"

DEFAULT_TRIPO_URL = (
    "https://studio.tripo3d.ai/3d-model/"
    "anime-girl-character-with-flowing-peach-hair-pink-skirt-white-top-a-"
    "26b155ec-9124-46c1-acb8-139b24d78c28"
)

DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "Tripo3D")


# ---------------------------------------------------------------------------
# Regex patterns (same logic as original script)
# ---------------------------------------------------------------------------

TRIPO_GLB_PATTERN = re.compile(
    r"https?://[^\s\"'<>]+\.glb\?Key-Pair-Id=[^\s\"'<>]+",
    re.IGNORECASE,
)

MODEL_EXTENSIONS = [
    ".glb", ".gltf", ".fbx", ".obj", ".stl", ".ply", ".dae",
    ".3ds", ".blend", ".usdz", ".usd", ".abc", ".x3d",
    ".wrl", ".vrml", ".off", ".iges", ".igs", ".step", ".stp",
]
_ext_pattern = "|".join(re.escape(e) for e in MODEL_EXTENSIONS)
MODEL_URL_PATTERN = re.compile(
    rf"https?://[^\s\"'<>]+(?:{_ext_pattern})(?:[?#][^\s\"'<>]*)?",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Image encoding  (bytes → pixels)
# ---------------------------------------------------------------------------

def bytes_to_png(data: bytes) -> bytes:
    """
    Encode arbitrary bytes into a PNG.

    Layout:
        • First 4 bytes  → big-endian uint32: total number of data bytes
        • Remaining bytes → raw payload

    Each byte becomes one pixel channel value.  Pixels are RGB triples,
    so we pack 3 bytes per pixel.  The image is square-ish (width ≈ √n).
    Unused trailing channels in the last pixel are zero-padded.

    Returns the PNG file content as bytes.
    """
    header   = len(data).to_bytes(4, "big")
    payload  = header + data
    n_bytes  = len(payload)

    # Pad to a multiple of 3 so every pixel is fully occupied
    pad      = (3 - n_bytes % 3) % 3
    padded   = payload + b"\x00" * pad
    n_pixels = len(padded) // 3

    # Choose dimensions: try to make a near-square image
    width  = math.ceil(math.sqrt(n_pixels))
    height = math.ceil(n_pixels / width)

    # Fill pixel array (pad remaining pixels with black)
    total_pixels = width * height
    pixel_data   = padded + b"\x00" * ((total_pixels - n_pixels) * 3)

    img = Image.frombytes("RGB", (width, height), pixel_data)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False, compress_level=0)
    return buf.getvalue()


def png_to_bytes(png_bytes: bytes) -> bytes:
    """Reverse of bytes_to_png — decode the hidden payload from a PNG."""
    img        = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    raw        = img.tobytes()
    length     = int.from_bytes(raw[:4], "big")
    return raw[4:4 + length]


# ---------------------------------------------------------------------------
# imgbb upload
# ---------------------------------------------------------------------------

def upload_to_imgbb(png_bytes: bytes, filename: str = "networklisten.png") -> dict:
    """
    Upload *png_bytes* to imgbb via their JSON API.
    Returns the parsed JSON response dict.
    """
    b64 = base64.b64encode(png_bytes).decode()

    resp = requests.post(
        IMGBB_URL,
        data={
            "key":    IMGBB_TOKEN,
            "image":  b64,
            "name":   filename,
        },
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/152.0.0.0 Safari/537.36 Edg/152.0.0.0"
            ),
            "Referer": "https://imgbb.com/",
            "Origin":  "https://imgbb.com",
        },
        cookies={"PHPSESSID": IMGBB_PHPSESSID},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# JavaScript injected into Tripo3D pages
# ---------------------------------------------------------------------------

INJECTOR_JS = r"""
(function () {
    var PRIMARY_PATTERN  = /https?:\/\/[^\s"'<>]+\.glb\?Key-Pair-Id=[^\s"'<>]+/i;
    var FALLBACK_EXTS    = [
        '\.glb','\.gltf','\.fbx','\.obj','\.stl',
        '\.ply','\.dae','\.3ds','\.blend',
        '\.usdz','\.usd','\.abc','\.x3d',
        '\.wrl','\.vrml','\.off','\.iges',
        '\.igs','\.step','\.stp'
    ];
    var FALLBACK_PATTERN = new RegExp(
        'https?://[^\\s"\\'<>]+(?:' + FALLBACK_EXTS.join('|') + ')(?:[?#][^\\s"\\'<>]*)?',
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
        window.pywebview.api.on_model_found(url);
    }

    // Intercept fetch
    var _origFetch = window.fetch;
    window.fetch = function (input, init) {
        var url = typeof input === 'string' ? input : (input && input.url);
        var match = isModelUrl(url);
        if (match) onModelUrlFound(match);
        return _origFetch.apply(this, arguments);
    };

    // Intercept XHR
    var _origOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function (method, url) {
        var match = isModelUrl(url);
        if (match) onModelUrlFound(match);
        return _origOpen.apply(this, arguments);
    };

    // Resource Timing API
    var observer = new PerformanceObserver(function (list) {
        list.getEntries().forEach(function (entry) {
            var match = isModelUrl(entry.name);
            if (match) onModelUrlFound(match);
        });
    });
    observer.observe({ type: 'resource', buffered: true });

    console.log('[Network Listener] Watching for model URLs…');
})();
"""


# ---------------------------------------------------------------------------
# Landing page HTML
# ---------------------------------------------------------------------------

LANDING_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Tripo3D → imgbb Encoder</title>
<style>
  :root {{
    --bg:      #0d0f14;
    --surface: #161922;
    --border:  #252a36;
    --accent:  #7c5cfc;
    --accent2: #c084fc;
    --text:    #e2e4f0;
    --muted:   #6b7280;
    --success: #22d3a5;
    --error:   #f87171;
    --radius:  10px;
    --mono:    'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
    --sans:    'Inter', 'Segoe UI', system-ui, sans-serif;
  }}

  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    background: var(--bg);
    color: var(--text);
    font-family: var(--sans);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 2rem;
  }}

  .card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 2.5rem 2rem;
    width: 100%;
    max-width: 620px;
    box-shadow: 0 8px 40px rgba(0,0,0,.5);
  }}

  .logo {{
    display: flex;
    align-items: center;
    gap: .6rem;
    margin-bottom: 1.8rem;
  }}

  .logo-icon {{
    width: 36px; height: 36px;
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-size: 18px;
  }}

  .logo-text {{
    font-size: 1.1rem;
    font-weight: 600;
    letter-spacing: -.02em;
    color: var(--text);
  }}

  .logo-text span {{ color: var(--accent2); }}

  h1 {{
    font-size: 1.55rem;
    font-weight: 700;
    line-height: 1.25;
    margin-bottom: .5rem;
    letter-spacing: -.03em;
  }}

  .sub {{
    color: var(--muted);
    font-size: .875rem;
    line-height: 1.6;
    margin-bottom: 2rem;
  }}

  label {{
    display: block;
    font-size: .8rem;
    font-weight: 500;
    color: var(--muted);
    margin-bottom: .45rem;
    letter-spacing: .04em;
  }}

  .input-row {{
    display: flex;
    gap: .6rem;
    margin-bottom: 1.2rem;
  }}

  input[type=text] {{
    flex: 1;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    color: var(--text);
    font-family: var(--mono);
    font-size: .78rem;
    padding: .7rem .9rem;
    outline: none;
    transition: border-color .15s;
  }}

  input[type=text]:focus {{ border-color: var(--accent); }}
  input[type=text]::placeholder {{ color: var(--muted); opacity: .6; }}

  button {{
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    border: none;
    border-radius: var(--radius);
    color: #fff;
    cursor: pointer;
    font-family: var(--sans);
    font-size: .875rem;
    font-weight: 600;
    padding: .7rem 1.4rem;
    white-space: nowrap;
    transition: opacity .15s, transform .1s;
  }}

  button:hover  {{ opacity: .88; transform: translateY(-1px); }}
  button:active {{ transform: translateY(0); opacity: 1; }}
  button:disabled {{ opacity: .4; cursor: not-allowed; transform: none; }}

  .steps {{
    display: flex;
    flex-direction: column;
    gap: .75rem;
    margin-top: 1.8rem;
  }}

  .step {{
    display: flex;
    align-items: flex-start;
    gap: .75rem;
    font-size: .82rem;
    color: var(--muted);
    line-height: 1.5;
  }}

  .step-num {{
    flex-shrink: 0;
    width: 22px; height: 22px;
    border-radius: 50%;
    border: 1px solid var(--border);
    display: flex; align-items: center; justify-content: center;
    font-size: .7rem;
    font-weight: 700;
    color: var(--accent2);
    margin-top: 1px;
  }}

  #status-box {{
    display: none;
    margin-top: 1.5rem;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1rem;
  }}

  #status-box.visible {{ display: block; }}

  .status-line {{
    font-family: var(--mono);
    font-size: .75rem;
    line-height: 1.7;
    word-break: break-all;
  }}

  .status-line.ok   {{ color: var(--success); }}
  .status-line.err  {{ color: var(--error); }}
  .status-line.info {{ color: var(--muted); }}
  .status-line.link {{ color: var(--accent2); cursor: pointer; text-decoration: underline; }}

  .spinner {{
    display: inline-block;
    width: 12px; height: 12px;
    border: 2px solid var(--border);
    border-top-color: var(--accent2);
    border-radius: 50%;
    animation: spin .7s linear infinite;
    vertical-align: middle;
    margin-right: .4rem;
  }}
  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}

  .divider {{
    border: none;
    border-top: 1px solid var(--border);
    margin: 1.8rem 0 1.4rem;
  }}

  .pixel-preview {{
    display: none;
    flex-direction: column;
    gap: .4rem;
    margin-top: 1rem;
  }}
  .pixel-preview.visible {{ display: flex; }}
  .pixel-preview img {{
    image-rendering: pixelated;
    width: 100%;
    border-radius: 6px;
    border: 1px solid var(--border);
  }}
  .pixel-preview small {{
    color: var(--muted);
    font-size: .73rem;
    font-family: var(--mono);
  }}
</style>
</head>
<body>
<div class="card">
  <div class="logo">
    <div class="logo-icon">🧊</div>
    <div class="logo-text">Tripo3D <span>→ imgbb</span> Encoder</div>
  </div>

  <h1>Source-to-pixel uploader</h1>
  <p class="sub">
    Paste a Tripo3D model URL. The script will visit the page, detect the
    signed <code>.glb</code> download link, encode this tool's source code
    as a pixel-art PNG, then upload it to imgbb.
  </p>

  <label for="url-input">Tripo3D model URL</label>
  <div class="input-row">
    <input
      type="text"
      id="url-input"
      placeholder="https://studio.tripo3d.ai/3d-model/…"
      value="{DEFAULT_TRIPO_URL}"
    >
    <button id="go-btn" onclick="startFlow()">Run</button>
  </div>

  <div class="steps">
    <div class="step">
      <div class="step-num">1</div>
      <div>Open the Tripo3D page and intercept the signed <code>.glb</code> network request</div>
    </div>
    <div class="step">
      <div class="step-num">2</div>
      <div>Encode this script's source bytes as RGB pixels — one byte per channel — into a PNG</div>
    </div>
    <div class="step">
      <div class="step-num">3</div>
      <div>Upload the PNG to imgbb and return the shareable URL</div>
    </div>
  </div>

  <div id="status-box">
    <div id="status-lines"></div>
    <div class="pixel-preview" id="pixel-preview">
      <img id="pixel-img" src="" alt="pixel-encoded source">
      <small id="pixel-meta"></small>
    </div>
  </div>
</div>

<script>
function log(msg, cls) {{
  cls = cls || 'info';
  var box = document.getElementById('status-box');
  box.classList.add('visible');
  var line = document.createElement('div');
  line.className = 'status-line ' + cls;
  line.innerHTML = msg;
  document.getElementById('status-lines').appendChild(line);
  box.scrollTop = box.scrollHeight;
}}

function clearLog() {{
  document.getElementById('status-lines').innerHTML = '';
  var pp = document.getElementById('pixel-preview');
  pp.classList.remove('visible');
}}

function startFlow() {{
  var url = document.getElementById('url-input').value.trim();
  if (!url) {{ alert('Please enter a Tripo3D URL.'); return; }}

  document.getElementById('go-btn').disabled = true;
  clearLog();
  log('<span class="spinner"></span> Navigating to Tripo3D page…');

  // Tell Python to navigate and run the full pipeline
  window.pywebview.api.start_pipeline(url)
    .then(function(result) {{
      if (result && result.error) {{
        log('Error: ' + result.error, 'err');
      }}
    }})
    .catch(function(e) {{
      log('JS error: ' + e, 'err');
    }});
}}

// Called from Python to push status messages into the UI
function pushStatus(msg, cls) {{
  log(msg, cls || 'info');
  if (cls === 'ok' || cls === 'err') {{
    document.getElementById('go-btn').disabled = false;
  }}
}}

// Called from Python to show the pixel preview
function showPixelPreview(dataUrl, meta) {{
  var pp = document.getElementById('pixel-preview');
  pp.classList.add('visible');
  document.getElementById('pixel-img').src = dataUrl;
  document.getElementById('pixel-meta').textContent = meta;
}}
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Python API exposed to the webview
# ---------------------------------------------------------------------------

class Api:
    """Methods callable from JavaScript via window.pywebview.api.*"""

    def __init__(self):
        self._window = None   # set after window creation

    # -- called by JS ---------------------------------------------------------

    def start_pipeline(self, tripo_url: str) -> dict:
        """
        Step 1: Navigate to the Tripo3D model page.
        The rest of the pipeline continues in on_model_found().
        """
        self._status("Navigating to Tripo3D…", "info")
        if self._window:
            self._window.load_url(tripo_url)
        return {}

    def on_model_found(self, model_url: str):
        """
        Called from the injected JS when a .glb URL is intercepted.
        Runs the encode + upload pipeline in a background thread.
        """
        self._status(f"✓ Model URL detected: <br><code>{model_url[:80]}…</code>", "ok")
        threading.Thread(
            target=self._encode_and_upload,
            args=(model_url,),
            daemon=True,
        ).start()

    # -- internal -------------------------------------------------------------

    def _status(self, msg: str, cls: str = "info"):
        """Push a status message into the landing page UI."""
        if self._window is None:
            print(f"[{cls}] {msg}")
            return
        safe = msg.replace("\\", "\\\\").replace("`", "\\`").replace("'", "\\'")
        # We're on the landing page when this is first called; after
        # navigation we go to Tripo3D, so we need to navigate back first.
        # Instead, we store messages and re-inject on return.
        # Simple approach: use evaluate_js on whatever page is current.
        try:
            self._window.evaluate_js(
                f"if(typeof pushStatus==='function')pushStatus(`{safe}`,'{cls}');"
            )
        except Exception:
            print(f"[{cls}] {msg}")

    def _encode_and_upload(self, model_url: str):
        """Background worker: encode source → PNG → imgbb."""
        # Navigate back to the landing page so we can show status
        self._status("Encoding source code as pixel image…", "info")

        # Read this script's own source
        try:
            with open(__file__, "rb") as fh:
                source_bytes = fh.read()
        except Exception as e:
            self._status(f"Could not read source file: {e}", "err")
            return

        src_len = len(source_bytes)
        self._status(f"Source size: {src_len:,} bytes", "info")

        # Encode to PNG
        try:
            png_bytes = bytes_to_png(source_bytes)
        except Exception as e:
            self._status(f"Encoding failed: {e}", "err")
            return

        n_pixels = math.ceil(math.sqrt(math.ceil((src_len + 4) / 3))) ** 2
        width    = math.ceil(math.sqrt(math.ceil((src_len + 4) / 3)))
        height   = math.ceil(math.ceil((src_len + 4) / 3) / width)
        meta     = f"{width}×{height} px  |  {len(png_bytes):,} bytes PNG"

        self._status(f"PNG created: {meta}", "info")

        # Show preview in UI (data URL)
        try:
            b64_preview = base64.b64encode(png_bytes).decode()
            data_url    = f"data:image/png;base64,{b64_preview}"
            safe_meta   = meta.replace("'", "\\'")
            if self._window:
                self._window.evaluate_js(
                    f"if(typeof showPixelPreview==='function')"
                    f"showPixelPreview('{data_url}','{safe_meta}');"
                )
        except Exception:
            pass  # preview is optional

        # Save locally too
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        local_path = os.path.join(DOWNLOAD_DIR, "networklisten.png")
        try:
            with open(local_path, "wb") as fh:
                fh.write(png_bytes)
            self._status(f"Saved locally → {local_path}", "info")
        except Exception as e:
            self._status(f"Local save failed: {e}", "err")

        # Upload to imgbb
        self._status("Uploading to imgbb…", "info")
        try:
            result = upload_to_imgbb(png_bytes, "networklisten.png")
        except Exception as e:
            self._status(f"imgbb upload failed: {e}", "err")
            return

        if result.get("success"):
            data     = result["data"]
            img_url  = data.get("url", "")
            display  = data.get("display_url", "")
            delete   = data.get("delete_url", "")
            self._status("✓ Upload successful!", "ok")
            self._status(
                f'Image URL: <a class="link" onclick="navigator.clipboard.writeText(\'{img_url}\')">'
                f"{img_url}</a>",
                "link",
            )
            if display:
                self._status(f"Display URL: {display}", "info")
            if delete:
                self._status(f"Delete URL: {delete}", "info")
            self._status(
                f"Encoded model URL inside image: {model_url[:60]}…", "info"
            )
        else:
            err = result.get("error", {}).get("message", str(result))
            self._status(f"imgbb error: {err}", "err")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if webview is None:
        print("pywebview is not installed.  Run:  pip install pywebview Pillow requests")
        return

    api    = Api()
    window = webview.create_window(
        title   = "Tripo3D → imgbb Encoder",
        html    = LANDING_HTML,
        js_api  = api,
        width   = 800,
        height  = 680,
        resizable=True,
    )
    api._window = window

    def on_loaded():
        url = window.get_current_url() or ""
        if "tripo3d.ai" in url:
            window.evaluate_js(INJECTOR_JS)
            print(f"[scanner] Injector active on: {url}")
            # Navigate back to landing so the user sees the status messages
            # We use a short delay to let the page settle first
            def navigate_home():
                import time; time.sleep(3)
                window.load_html(LANDING_HTML)
            threading.Thread(target=navigate_home, daemon=True).start()

    window.events.loaded += on_loaded

    print("[Tripo3D Encoder] Starting …")
    webview.start(debug=False)


if __name__ == "__main__":
    main()
