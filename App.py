
import io
import math
import os
import re
import sys
import threading

from PIL import Image

try:
    import webview
except ImportError:
    webview = None


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_TRIPO_URL = (
    "https://studio.tripo3d.ai/3d-model/"
    "anime-girl-character-with-flowing-peach-hair-pink-skirt-white-top-a-"
    "26b155ec-9124-46c1-acb8-139b24d78c28"
)

# Save next to the exe (when frozen) or next to this .py file
def _exe_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

OUTPUT_DIR = _exe_dir()


# ---------------------------------------------------------------------------
# Regex patterns
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
    Pack raw bytes into a lossless PNG.

    Format:
        [4 bytes big-endian length] [data bytes] [zero padding to fill last pixel]

    3 bytes per pixel (RGB).  Image is as square as possible.
    """
    header  = len(data).to_bytes(4, "big")
    payload = header + data
    n       = len(payload)
    pad     = (3 - n % 3) % 3
    padded  = payload + b"\x00" * pad
    n_px    = len(padded) // 3

    width  = math.ceil(math.sqrt(n_px))
    height = math.ceil(n_px / width)
    total  = width * height

    pixel_data = padded + b"\x00" * ((total - n_px) * 3)

    img = Image.frombytes("RGB", (width, height), pixel_data)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False, compress_level=0)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# JavaScript injected into Tripo3D pages
# ---------------------------------------------------------------------------

INJECTOR_JS = r"""
(function () {
    var PRIMARY  = /https?:\/\/[^\s"'<>]+\.glb\?Key-Pair-Id=[^\s"'<>]+/i;
    var FALLBACK_EXTS = [
        '\.glb','\.gltf','\.fbx','\.obj','\.stl',
        '\.ply','\.dae','\.3ds','\.blend',
        '\.usdz','\.usd','\.abc','\.x3d',
        '\.wrl','\.vrml','\.off','\.iges','\.igs','\.step','\.stp'
    ];
    var FALLBACK = new RegExp(
        'https?://[^\\s"\\'<>]+(?:' + FALLBACK_EXTS.join('|') + ')(?:[?#][^\\s"\\'<>]*)?', 'i'
    );

    var _done = false;

    function check(url) {
        if (!url) return null;
        var m = url.match(PRIMARY) || url.match(FALLBACK);
        return m ? m[0] : null;
    }

    function found(url) {
        if (_done) return;
        _done = true;
        console.log('[Tripo3D Encoder] Model URL:', url);
        window.pywebview.api.on_model_found(url);
    }

    var _fetch = window.fetch;
    window.fetch = function (input, init) {
        var u = typeof input === 'string' ? input : (input && input.url);
        var m = check(u); if (m) found(m);
        return _fetch.apply(this, arguments);
    };

    var _open = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function (method, url) {
        var m = check(url); if (m) found(m);
        return _open.apply(this, arguments);
    };

    new PerformanceObserver(function (list) {
        list.getEntries().forEach(function (e) {
            var m = check(e.name); if (m) found(m);
        });
    }).observe({ type: 'resource', buffered: true });

    console.log('[Tripo3D Encoder] Watching network…');
})();
"""


# ---------------------------------------------------------------------------
# Landing page HTML
# ---------------------------------------------------------------------------

LANDING_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Tripo3D Encoder</title>
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
    --mono: 'JetBrains Mono','Fira Code',monospace;
    --sans: 'Inter','Segoe UI',system-ui,sans-serif;
  }}
  *,*::before,*::after {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{
    background:var(--bg); color:var(--text);
    font-family:var(--sans);
    min-height:100vh; display:flex;
    align-items:center; justify-content:center; padding:2rem;
  }}
  .card {{
    background:var(--surface); border:1px solid var(--border);
    border-radius:12px; padding:2.5rem 2rem;
    width:100%; max-width:600px;
    box-shadow:0 8px 40px rgba(0,0,0,.5);
  }}
  .logo {{ display:flex; align-items:center; gap:.6rem; margin-bottom:1.8rem; }}
  .logo-icon {{
    width:36px; height:36px;
    background:linear-gradient(135deg,var(--accent),var(--accent2));
    border-radius:8px; display:flex; align-items:center;
    justify-content:center; font-size:18px;
  }}
  .logo-text {{ font-size:1rem; font-weight:600; }}
  .logo-text span {{ color:var(--accent2); }}
  h1 {{ font-size:1.5rem; font-weight:700; letter-spacing:-.03em; margin-bottom:.4rem; }}
  .sub {{ color:var(--muted); font-size:.85rem; line-height:1.6; margin-bottom:1.8rem; }}
  label {{ display:block; font-size:.75rem; font-weight:500; color:var(--muted);
           margin-bottom:.4rem; letter-spacing:.04em; }}
  .row {{ display:flex; gap:.6rem; margin-bottom:1.2rem; }}
  input[type=text] {{
    flex:1; background:var(--bg); border:1px solid var(--border);
    border-radius:8px; color:var(--text); font-family:var(--mono);
    font-size:.75rem; padding:.65rem .9rem; outline:none;
    transition:border-color .15s;
  }}
  input[type=text]:focus {{ border-color:var(--accent); }}
  input::placeholder {{ color:var(--muted); opacity:.6; }}
  button {{
    background:linear-gradient(135deg,var(--accent),var(--accent2));
    border:none; border-radius:8px; color:#fff; cursor:pointer;
    font-size:.875rem; font-weight:600; padding:.65rem 1.3rem;
    white-space:nowrap; transition:opacity .15s,transform .1s;
  }}
  button:hover {{ opacity:.88; transform:translateY(-1px); }}
  button:active {{ transform:translateY(0); }}
  button:disabled {{ opacity:.4; cursor:not-allowed; transform:none; }}
  #log {{
    display:none; margin-top:1.4rem; background:var(--bg);
    border:1px solid var(--border); border-radius:8px;
    padding:.9rem; max-height:220px; overflow-y:auto;
  }}
  #log.on {{ display:block; }}
  .line {{ font-family:var(--mono); font-size:.73rem; line-height:1.8; word-break:break-all; }}
  .line.info {{ color:var(--muted); }}
  .line.ok   {{ color:var(--success); }}
  .line.err  {{ color:var(--error); }}
  .spin {{
    display:inline-block; width:11px; height:11px;
    border:2px solid var(--border); border-top-color:var(--accent2);
    border-radius:50%; animation:spin .7s linear infinite;
    vertical-align:middle; margin-right:.35rem;
  }}
  @keyframes spin {{ to {{ transform:rotate(360deg); }} }}
  #preview {{ display:none; margin-top:1rem; }}
  #preview.on {{ display:block; }}
  #preview img {{
    image-rendering:pixelated; width:100%;
    border-radius:6px; border:1px solid var(--border);
  }}
  #preview small {{ display:block; color:var(--muted); font-size:.7rem;
                    font-family:var(--mono); margin-top:.3rem; }}
</style>
</head>
<body>
<div class="card">
  <div class="logo">
    <div class="logo-icon">🧊</div>
    <div class="logo-text">Tripo3D <span>Encoder</span></div>
  </div>
  <h1>Source → pixel image</h1>
  <p class="sub">
    Paste a Tripo3D model URL. The app visits the page, intercepts the
    signed <code>.glb</code> link, then encodes this script's source
    bytes as an RGB pixel PNG and saves it next to the exe.
  </p>
  <label for="u">Tripo3D model URL</label>
  <div class="row">
    <input type="text" id="u"
      placeholder="https://studio.tripo3d.ai/3d-model/…"
      value="{DEFAULT_TRIPO_URL}">
    <button id="btn" onclick="go()">Run</button>
  </div>
  <div id="log"></div>
  <div id="preview"><img id="pimg" src="" alt="pixel preview"><small id="pmeta"></small></div>
</div>
<script>
function log(msg, cls) {{
  var box = document.getElementById('log');
  box.classList.add('on');
  var d = document.createElement('div');
  d.className = 'line ' + (cls||'info');
  d.innerHTML = msg;
  box.appendChild(d);
  box.scrollTop = box.scrollHeight;
}}
function clearLog() {{
  document.getElementById('log').innerHTML = '';
  document.getElementById('preview').classList.remove('on');
}}
function go() {{
  var url = document.getElementById('u').value.trim();
  if (!url) {{ alert('Please enter a URL.'); return; }}
  document.getElementById('btn').disabled = true;
  clearLog();
  log('<span class="spin"></span>Navigating to Tripo3D…');
  window.pywebview.api.start_pipeline(url).catch(function(e) {{
    log('Error: ' + e, 'err');
  }});
}}
function pushStatus(msg, cls) {{
  log(msg, cls);
  if (cls === 'ok' || cls === 'err')
    document.getElementById('btn').disabled = false;
}}
function showPreview(dataUrl, meta) {{
  var p = document.getElementById('preview');
  p.classList.add('on');
  document.getElementById('pimg').src = dataUrl;
  document.getElementById('pmeta').textContent = meta;
}}
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Python API
# ---------------------------------------------------------------------------

class Api:
    def __init__(self):
        self._win = None

    def start_pipeline(self, tripo_url: str) -> dict:
        self._push("Navigating to Tripo3D…")
        if self._win:
            self._win.load_url(tripo_url)
        return {}

    def on_model_found(self, model_url: str):
        self._push(f"✓ Model URL intercepted", "ok")
        threading.Thread(target=self._encode, args=(model_url,), daemon=True).start()

    # -------------------------------------------------------------------------

    def _push(self, msg: str, cls: str = "info"):
        if self._win is None:
            print(f"[{cls}] {msg}")
            return
        safe = msg.replace("\\", "\\\\").replace("`", "\\`").replace("'", "\\'")
        try:
            self._win.evaluate_js(
                f"if(typeof pushStatus==='function')pushStatus(`{safe}`,'{cls}');"
            )
        except Exception:
            print(f"[{cls}] {msg}")

    def _encode(self, model_url: str):
        # ---- read source ----
        src_path = getattr(sys, "_MEIPASS", None)
        # For a frozen exe the .py isn't on disk; we stored it at build time.
        # For a plain .py run we just read __file__.
        script_path = os.path.abspath(__file__)
        try:
            with open(script_path, "rb") as fh:
                source_bytes = fh.read()
        except Exception as e:
            self._push(f"Could not read source: {e}", "err")
            return

        self._push(f"Source: {len(source_bytes):,} bytes")

        # ---- encode ----
        try:
            png_bytes = bytes_to_png(source_bytes)
        except Exception as e:
            self._push(f"Encode failed: {e}", "err")
            return

        n   = len(source_bytes)
        w   = math.ceil(math.sqrt(math.ceil((n + 4) / 3)))
        h   = math.ceil(math.ceil((n + 4) / 3) / w)
        meta = f"{w}×{h} px  |  {len(png_bytes):,} bytes"
        self._push(f"PNG: {meta}")

        # ---- preview ----
        try:
            import base64
            b64 = base64.b64encode(png_bytes).decode()
            safe_meta = meta.replace("'", "\\'")
            if self._win:
                self._win.evaluate_js(
                    f"if(typeof showPreview==='function')"
                    f"showPreview('data:image/png;base64,{b64}','{safe_meta}');"
                )
        except Exception:
            pass

        # ---- save next to exe / script ----
        out_path = os.path.join(OUTPUT_DIR, "networklisten.png")
        try:
            with open(out_path, "wb") as fh:
                fh.write(png_bytes)
            self._push(f"✓ Saved → {out_path}", "ok")
        except Exception as e:
            self._push(f"Save failed: {e}", "err")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if webview is None:
        print("Install pywebview:  pip install pywebview Pillow")
        return

    api = Api()
    win = webview.create_window(
        title    = "Tripo3D Encoder",
        html     = LANDING_HTML,
        js_api   = api,
        width    = 780,
        height   = 620,
        resizable= True,
    )
    api._win = win

    def on_loaded():
        url = win.get_current_url() or ""
        if "tripo3d.ai" in url:
            win.evaluate_js(INJECTOR_JS)
            print(f"[encoder] Injector active: {url}")

            def back_home():
                import time; time.sleep(4)
                win.load_html(LANDING_HTML)
            threading.Thread(target=back_home, daemon=True).start()

    win.events.loaded += on_loaded
    print(f"[Tripo3D Encoder] Output dir: {OUTPUT_DIR}")
    webview.start(debug=False)


if __name__ == "__main__":
    main()
