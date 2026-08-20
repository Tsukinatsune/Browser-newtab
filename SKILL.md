---
name: artoriasphere-extension
description: >
  Use this skill for ANY request involving the Artoriasphere new-tab Chrome extension.
  Triggers include: creating or designing a widget, building a custom search bar, writing
  custom CSS/HTML/JS for the page, explaining settings, generating widget code snippets,
  or asking how to customize the page. Claude MUST follow this skill to produce working,
  copy-paste-ready outputs for every task.
---

# Artoriasphere Extension — Developer & User Skill

## What This Extension Is

Artoriasphere is a Chrome new-tab extension with a full settings panel. The page loads
`newtab.html` + `newtab.js`. All user customisation is saved to `localStorage` and applied
at load time. The extension has **seven settings panels** and three advanced injection
points (Custom Code). Claude must know all of them to help the user.

---

## MANDATORY OUTPUT RULES

Claude must **always** do ALL THREE of these things in every response:

1. **Create a widget** — produce working, copy-paste-ready code for the Widget panel
2. **Produce custom page code** — provide CSS/HTML/JS for the Custom Code panel
3. **Write a tutorial** — explain every relevant settings panel step the user needs

Never give partial output. A response with only code and no tutorial is incomplete.
A response with only instructions and no code is incomplete.

---

## Settings Panel Map

### 1. Search Engines (`Settings → Search engines`)
- Three built-in groups: **General**, **Trusted research sources**, **Thai research sources**
- Add a **custom engine**: Name + URL ending before the query string (e.g. `https://example.com/search?q=`)
- Click a chip to toggle it on/off; multiple engines open searches in parallel tabs
- Edit any engine name/URL with the pen icon; remove custom ones with ✕
- Smart search shortcut: type `EngineName[query]` to force one engine
- Custom regex rules: pattern + target URL with `{q}` placeholder

### 2. Search Box (`Settings → Search box`)
- **Placeholder text** — change the hint text inside the box
- **Width** — slider 320 px → 800 px (CSS var `--sb-width`)
- **Corner roundness** — slider 0 → 999; 999 = pill shape (CSS var `--sb-radius`)
- **Colors** — four pickers: Background, Border, Text, Button (CSS vars `--sb-bg`, `--sb-border`, `--sb-text`, `--sb-btn-bg`; button text auto-contrasts)
- **Show engine row** toggle — hides/shows the engine name row below the search bar
- **Reset search box** — restores all defaults

### 3. Background (`Settings → Background`)
- Paste any image or video URL and click Apply
- Videos: `.mp4 .webm .ogg .ogv .mov .m4v` are detected automatically
- **Fit**: Cover (crop-fill) or Contain (letterbox)
- **Overlay opacity** — semi-transparent warm overlay (`rgba(238,233,225,opacity)`) from 0–100%
- **Clear background** — removes the media

### 4. Font (`Settings → Font`)
- Dropdown with built-in Google Fonts: Iowan Old Style (default), Playfair Display,
  Cormorant Garamond, Fraunces, Libre Baskerville, Inter, Space Grotesk, JetBrains Mono
- **Custom font URL** — paste a `.ttf .otf .woff .woff2` URL; the extension injects
  a `@font-face` and sets `--user-font`
- Font preview updates live

### 5. Widgets (`Settings → Widgets`)

Two modes:

#### From URL (iframe embed)
- Name + embed URL → creates a draggable, resizable iframe window floating on the page
- Widgets appear on `#widgetLayer` (position: fixed, z-index layer above the page)
- Each widget window has: drag handle (move icon), resize handle (bottom-right corner),
  optional console panel, pin toggle (locks position, hides handle)

#### Custom Code Widget (HTML/CSS/JS)
- Name + HTML textarea + CSS textarea + JS textarea
- HTML and CSS are wrapped into an `srcdoc` iframe: `<html><head><style>{css}</style></head><body>{html}</body></html>`
- JS is run through the built-in **Selenelion interpreter** (safe sandbox with full Web API
  access: `document`, `window`, `fetch`, `localStorage`, `setTimeout`, Canvas, WebSocket, etc.)
- Console output (log/warn/error) appears in the in-widget console panel (▸ log button)
- Widgets are persisted in `localStorage` keys: `customWidgets`, `activeWidgets`,
  `widgetPositions`, `widgetLocked`, `widgetMinimized`, `widgetSizes`

**Available JS APIs inside widget code** (Selenelion-injected):
`window`, `document`, `navigator`, `location`, `localStorage`, `sessionStorage`,
`fetch`, `fetchJSON`, `setTimeout`, `setInterval`, `clearTimeout`, `clearInterval`,
`requestAnimationFrame`, `WebSocket`, `XMLHttpRequest`, `Blob`, `File`, `FileReader`,
`URL`, `URLSearchParams`, `FormData`, `TextEncoder`, `TextDecoder`, `crypto`, `uuidv4`,
`sha256`, `Math`, `JSON`, `Object`, `Array`, `String`, `Number`, `Date`, `RegExp`,
`Map`, `Set`, `Promise`, `Proxy`, `Reflect`, `Intl`, `Worker`, `BroadcastChannel`,
`AudioContext`, `Canvas`/`OffscreenCanvas`, `performance`, `MutationObserver`,
`IntersectionObserver`, `ResizeObserver`, `SpeechRecognition`, `speechSynthesis`,
`LanguageDetector`, `Translator`, `Summarizer`, `ai`, `alert`, `confirm`, `prompt`,
`getComputedStyle`, `matchMedia`, utility helpers: `sleep(ms)`, `range(s,e,step)`,
`clone(v)`, `debounce(fn,d)`, `throttle(fn,d)`, `chunk(arr,n)`, `unique(arr)`,
`flatten(arr,d)`, `groupBy(arr,fn)`, `zip(...arrs)`, `sum(arr)`, `mean(arr)`,
`min(arr)`, `max(arr)`, `base64Encode(s)`, `base64Decode(s)`, `randomHex(bytes)`,
`uuidv4()`, `sha256(msg)` (async), `sha1(msg)` (async), `sha512(msg)` (async)

### 6. Smart Search (`Settings → Smart search`)
- **Auto-open URLs** toggle — if the query looks like a URL, open it directly
- **engine[term] shortcut** toggle — `Google[weather Bangkok]` opens that engine
- **Custom regex rules** — Name + Regex pattern + Target URL with `{q}` placeholder
  Example: pattern `^r/(.+)`, URL `https://reddit.com/r/{q}` → `r/webdev` → Reddit

### 7. Custom Code (`Settings → Custom code`)

Three tabs — **CSS**, **HTML**, **JavaScript**. Click **Apply & save**.

#### CSS tab
- Applies globally via `<style id="userCustomCssStyle">` injected into `<head>`
- Can restyle ANY element: `.search-ring`, `.frame`, `.top-bar`, `body`, etc.
- Avoid re-declaring `border-radius`/`background` on `.search-ring` if you already set
  them in Search Box settings (they will conflict)

#### HTML tab
- Injected into `<div id="userCustomHtml">` — a transparent div in the DOM
- Use CSS to position it: `#userCustomHtml { position:fixed; top:80px; left:20px; }`
- Can contain any valid HTML: clocks, links, widgets, SVG, etc.

#### JavaScript tab
- Runs via **Selenelion interpreter** with FULL DOM access (unsandboxed on the newtab page)
- `document.querySelector(...)` works directly
- Use to: animate elements, add event listeners, fetch data, manipulate the search bar
- Runs every time the page loads (after CSS and HTML are applied)

---

## DOM Elements Claude Can Target

```
body                        — page root
#bgLayer                    — background image/video container
#bgOverlay                  — warm overlay div (rgba fill)
#widgetLayer                — all floating widget windows live here
#userCustomHtml             — Custom Code HTML injection point
.top-bar                    — top strip containing the brand/settings button
.corner-brand               — settings button (logo + text)
.frame                      — centers the search form
#searchForm                 — the <form> element
.search-ring                — the pill/box containing input + button
#q                          — search <input>
.go                         — search submit <button>
.meta-row                   — row showing engine name + "opens in new tab"
#selectedSummary            — engine name text inside meta-row
.modal-backdrop             — settings modal overlay
.modal                      — settings modal box
```

CSS variables set by the extension:
```css
--sb-width          /* search box max-width */
--sb-radius         /* border-radius of search ring */
--sb-bg             /* search ring background */
--sb-border         /* search ring border color */
--sb-text           /* input text color */
--sb-btn-bg         /* go button background */
--sb-btn-text       /* go button text color (auto-calculated) */
--user-font         /* font-family applied to :root */
```

---

## Claude's Required Output Format

For every request, structure the response as follows:

### Section 1: Widget Code
Always produce a complete widget for the **Widgets → Custom code** panel.
Give three clearly labeled blocks:

```
=== HTML ===
(paste into HTML textarea)

=== CSS ===
(paste into CSS textarea)

=== JavaScript ===
(paste into JS textarea)
```

### Section 2: Custom Code (Full Page)
Always produce code for the **Custom Code** panel:

```
=== CSS Tab ===
(global CSS to paste)

=== HTML Tab ===
(HTML to inject into #userCustomHtml)

=== JavaScript Tab ===
(JS to paste and run)
```

### Section 3: Step-by-Step Tutorial
Always write a complete numbered tutorial covering every click the user must make.
Cover all settings panels that are relevant to the task.

---

## Widget Design Principles

- Widgets float over the page as resizable, draggable windows
- Default sizes are small (260×200 to 300×220 px) — design for compactness
- Widget JS runs in the widget iframe's document context (`document`, `window` = iframe)
- Use `fetch` or `fetchJSON` for API calls (CORS must allow it from extension origin)
- Use `localStorage` for persisting widget state across loads
- Prefer inline styles or scoped classes to avoid conflicts with parent page CSS
- The widget srcdoc iframe is isolated from the parent page's CSS — define all styles inside
- Use `setInterval` for live-updating widgets (clocks, countdowns, feeds)
- Use `speechSynthesis` for text-to-speech widgets
- Use `AudioContext` for sound/music widgets
- Use `canvas` + `requestAnimationFrame` for visual/game widgets

---

## Custom Search Bar Examples

The search bar is `.search-ring > #q + .go`. To fully replace its appearance:

```css
/* Example: neon green terminal style */
.search-ring {
  background: #0a0a0a;
  border: 2px solid #00ff88;
  border-radius: 4px;
  box-shadow: 0 0 20px rgba(0,255,136,0.3);
}
#q {
  color: #00ff88;
  font-family: 'JetBrains Mono', monospace;
  caret-color: #00ff88;
}
#q::placeholder { color: #005533; }
.go {
  background: #00ff88;
  color: #0a0a0a;
  border-radius: 2px;
}
```

To reposition the search bar to a corner or sidebar, target `.frame`:
```css
.frame {
  position: fixed;
  bottom: 40px;
  left: 40px;
  top: auto;
  transform: none;
}
```

---

## Common Widget Templates

### Live Clock Widget
```html
<div id="clock"></div>
```
```css
#clock {
  font-size: 3rem;
  font-weight: bold;
  text-align: center;
  color: white;
  text-shadow: 0 2px 10px rgba(0,0,0,0.5);
  padding: 20px;
  font-family: 'JetBrains Mono', monospace;
}
```
```js
function tick() {
  document.getElementById('clock').textContent = new Date().toLocaleTimeString();
}
tick();
setInterval(tick, 1000);
```

### Weather Widget (fetches open-meteo, no API key needed)
```html
<div id="weather">Loading…</div>
```
```css
#weather { padding: 12px; color: white; font-family: sans-serif; font-size: 0.9rem; }
```
```js
// Change lat/lon to your location
const lat = 13.7, lon = 100.5;
fetchJSON(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current_weather=true`)
  .then(d => {
    const w = d.current_weather;
    document.getElementById('weather').textContent = `${w.temperature}°C  wind ${w.windspeed} km/h`;
  })
  .catch(() => { document.getElementById('weather').textContent = 'Unable to load'; });
```

### Quick-link Bookmarks Widget
```html
<div id="links"></div>
```
```css
#links { display: flex; flex-wrap: wrap; gap: 6px; padding: 8px; }
#links a { background: rgba(255,255,255,0.15); color: white; text-decoration: none;
  padding: 4px 10px; border-radius: 6px; font-size: 0.8rem; font-family: sans-serif; }
#links a:hover { background: rgba(255,255,255,0.3); }
```
```js
const links = [
  { label: 'Gmail', url: 'https://mail.google.com' },
  { label: 'GitHub', url: 'https://github.com' },
  { label: 'Notion', url: 'https://notion.so' },
];
const container = document.getElementById('links');
links.forEach(l => {
  const a = document.createElement('a');
  a.href = l.url;
  a.target = '_blank';
  a.textContent = l.label;
  container.appendChild(a);
});
```

### Countdown Timer Widget
```html
<div id="countdown"></div>
<div id="cd-label" style="text-align:center;color:rgba(255,255,255,0.6);font-size:0.7rem;font-family:sans-serif;">until target date</div>
```
```css
#countdown { font-size: 2rem; font-weight: bold; text-align: center; color: white;
  font-family: 'JetBrains Mono', monospace; padding: 16px; }
```
```js
const target = new Date('2025-12-31T00:00:00');
function update() {
  const diff = target - new Date();
  if (diff < 0) { document.getElementById('countdown').textContent = '🎉'; return; }
  const d = Math.floor(diff / 86400000);
  const h = Math.floor((diff % 86400000) / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  const s = Math.floor((diff % 60000) / 1000);
  document.getElementById('countdown').textContent = `${d}d ${h}h ${m}m ${s}s`;
}
update();
setInterval(update, 1000);
```

---

## Tutorial Template (Always Include)

When explaining how to use the output, always cover:

1. Open the new tab page and click the **Artoriasphere logo** (top-left corner) to open Settings
2. For **Widgets**: click **Widgets** in the menu → choose **Custom code (HTML/CSS/JS)** tab
3. Give the widget a name, paste HTML / CSS / JS into the three textareas, click **Add custom widget**
4. The widget appears as a floating window — drag by the move icon (⊕), resize from the bottom-right corner
5. To pin it in place: open Widgets settings → click the 📌 thumbtack icon on the widget chip
6. For **Custom Code**: click **Custom code** in the menu → paste into CSS / HTML / JS tabs → click **Apply & save**
7. For **Search box**: click **Search box** → adjust sliders and color pickers live; click **Reset search box** to undo
8. For **Background**: click **Background** → paste image or video URL → click **Apply** → adjust overlay opacity
9. For **Font**: click **Font** → choose from the dropdown or paste a font file URL → click **Apply**
10. For **Search engines**: click **Search engines** → click chips to select/deselect; click **+Add** for custom engines
11. For **Smart search**: click **Smart search** → toggle URL detection and engine shortcuts; add regex rules
12. To reset everything: open Settings → scroll to the bottom → click **Reset everything to default**
