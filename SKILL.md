---
name: nodriver
description: >-
  Automate Chromium browsers asynchronously, extract JavaScript-rendered web pages to Markdown/HTML/JSON,
  manage persistent browser profiles and cookies, interact with complex DOM/IFrame/Shadow-DOM elements,
  capture screenshots/videos, and inspect or intercept network traffic via Chrome DevTools Protocol (CDP)
  using Python's nodriver library (no Selenium or WebDriver binaries required). Clears Cloudflare
  "Verify you are human" checkbox challenges with verify_cf(). Use this skill whenever the user wants to
  use nodriver, scrape dynamic SPAs, reuse authenticated browser sessions, capture XHR/Fetch API responses,
  or build custom async browser automation workflows.
license: MIT
homepage: https://github.com/YuLiang28/nodriver-skill
tags:
  - nodriver
  - browser-automation
  - web-scraping
  - chrome-devtools-protocol
  - cdp
  - chromium
  - python
  - agent-skills
---

# Nodriver Browser Automation & Web Extraction Skill

`nodriver` communicates directly with local Chromium-based browsers (Chrome, Edge, Brave, Chromium) over asynchronous Chrome DevTools Protocol (CDP) WebSockets—without `chromedriver` binaries or Selenium.

Resolve all relative paths below (`./scripts/...`, `./references/...`) against the directory containing this `SKILL.md` (`<skill_dir>`).

---

## Step 0: Environment & Dependency Initialization

`npx skills` copies skill files without running install hooks. Choose one of the two execution paths below before running any workflow:

### Path A — Zero-Config via `uv` (Preferred)
Every script in `./scripts/` includes PEP 723 inline dependency metadata. If `uv` is installed (`uv --version`), run scripts directly—`uv` will automatically create and cache an isolated environment on first run:
```bash
uv run <skill_dir>/scripts/setup_env.py --check-only
uv run <skill_dir>/scripts/fetch_page.py "https://example.com" -o page.md
```
To run a custom one-off Python script with `uv`:
```bash
uv run --with "nodriver>=0.50.99" python my_automation.py
```

### Path B — Isolated `.venv` Fallback (When `uv` Is Unavailable)
Initialize a dedicated virtual environment inside `<skill_dir>/.venv` and verify that a Chromium browser exists on the host:
```bash
python <skill_dir>/scripts/setup_env.py
```
`setup_env.py` outputs a JSON report containing `python_executable` and `browser_executable`. Use that `python_executable` (`<skill_dir>/.venv/Scripts/python.exe` on Windows, `<skill_dir>/.venv/bin/python` on macOS/Linux) for all subsequent commands.

---

## Layer 1: Ready-to-Use CLI Workflows (`./scripts/`)

Use the bundled CLI tools for common tasks without writing boilerplate code:

### 1. Extract Rendered Web Pages (`fetch_page.py`)
Fetches a URL in a real Chromium browser, optionally waits for selectors/text, scrolls lazy-loaded content, and exports clean Markdown, raw HTML, plain text, extracted links, `localStorage`, or screenshots.

```bash
# Save rendered page as clean Markdown (headless by default)
uv run <skill_dir>/scripts/fetch_page.py "https://example.com" --format markdown -o output/page.md

# Headed mode + persistent profile + wait for selector + lazy-load scroll + screenshot
uv run <skill_dir>/scripts/fetch_page.py "https://example.com/feed" \
  --headed \
  --profile-dir ./profiles/default \
  --wait-selector "article" \
  --scroll-steps 5 \
  --screenshot output/feed.jpg \
  -o output/feed.md
```
Key flags:
- `--format {markdown,html,text,links,json}` (default: `markdown`; `json` bundles metadata, markdown, links, and `localStorage`)
- `--selector <css>`: Extract only a specific container (e.g., `main`, `article`, `.post-content`)
- `--wait-selector <css>` / `--wait-text <str>` / `--wait-seconds <float>`
- `--headed`: Run with a visible browser window (recommended when debugging or reusing interactive profiles)
- `--profile-dir <dir>`: Persist cookies, IndexedDB, and session state across runs
- `--cookies-file <file>`: Load cookies saved via `CookieJar.save()` before navigating
- `--connect <host:port>`: Attach to an already running Chrome debugging session instead of launching a new browser

### 2. Manage Persistent Sessions & Human-in-the-Loop Login (`session_manager.py`)
Opens a visible browser backed by a persistent `--profile-dir` so a human user can log in or complete interactive gates, or exports/clears cookies.

```bash
# Launch headed browser with persistent profile and wait for user confirmation (or --duration seconds)
uv run <skill_dir>/scripts/session_manager.py open \
  --url "https://example.com/login" \
  --profile-dir ./profiles/site_a \
  --export-cookies ./profiles/site_a.cookies.dat

# Inspect cookies stored in a profile or session file
uv run <skill_dir>/scripts/session_manager.py inspect --profile-dir ./profiles/site_a
```

### 3. Capture XHR/Fetch API Responses via CDP (`network_capture.py`)
Listens to `cdp.network.RequestWillBeSent` and `cdp.network.ResponseReceived`, retrieves matching response bodies (JSON/text/base64), and writes structured `.jsonl` logs.

```bash
# Capture all API JSON responses matching "api/" or "graphql" while scrolling
uv run <skill_dir>/scripts/network_capture.py "https://example.com/app" \
  --url-filter "api|graphql" \
  --mime-filter "json" \
  --scroll-steps 4 \
  -o output/api_calls.jsonl
```

---

## Layer 2: Writing Custom `nodriver` Scripts (Full Library Capabilities)

When a task requires multi-step UI workflows (form filling, pagination loops, multi-tab orchestration, IFrame traversal, file uploads, drag-and-drop, request modification, or custom CDP commands), write a Python script using `nodriver` directly.

### Standard Async Boilerplate & Clean Shutdown
Always stop the browser inside a `try ... finally` block and allow a brief event-loop drain (`await asyncio.sleep(0.2)`) so Chromium child processes and Windows pipes exit cleanly:

```python
import asyncio
import nodriver as uc

async def main():
    browser = await uc.start(
        headless=False,
        user_data_dir="./profiles/custom",  # Omit for a fresh auto-cleaned temp profile
    )
    try:
        tab = await browser.get("https://example.com")
        await tab.select("body", timeout=15)  # Smart wait for DOM readiness

        # Smart shortest-match text lookup (e.g., finds actual button, not outer wrapper)
        btn = await tab.find("Learn more", best_match=True, timeout=5)
        if btn:
            await btn.click()

        html = await tab.get_content()
        print(f"Captured {len(html)} bytes from {tab.target.url}")
    finally:
        browser.stop()
        await asyncio.sleep(0.2)

if __name__ == "__main__":
    uc.loop().run_until_complete(main())
```

### Cloudflare Challenges: `tab.verify_cf()`
When `browser.get()` lands on a Cloudflare challenge page, click the checkbox with nodriver's built-in helper instead of stopping:

```python
tab = await browser.get("https://example.com")   # may land on a Cloudflare challenge page
await tab.select("body", timeout=15)

if "Just a moment" in await tab.get_content():    # challenge page: click the checkbox
    await tab.sleep(3)                            # give the challenge a moment to render
    await tab.verify_cf()                         # clicks "Verify you are human"
    await tab.sleep(5)                            # give Cloudflare time to let the page through
```

- Needs `opencv-python`, which nodriver does not install by itself: `uv run --with "nodriver>=0.50.99" --with "opencv-python" python my_automation.py`
- Does not work with `expert=True`
- Matches only the English checkbox at 100% zoom / display scale. For other languages, pass your own image: `verify_cf(template_image="checkbox.png")`
- Always clicks somewhere, even when no checkbox is visible, so call it only on a challenge page. It returns `None`: check the page afterwards

### Capability Reference Manuals (Read On Demand)
Load ONLY the reference file needed for your specific task:

1. **[Browser, Config, Profiles, Proxies & Extensions](./references/browser-and-config.md)**
   - `Config` & `uc.start()` parameters (`headless`, `user_data_dir`, `browser_executable_path`, `browser_args`, `sandbox`, `lang`, `expert`)
   - Connecting to an existing Chrome debug port (`host` + `port`) or migrating from `undetected_chromedriver`
   - Loading unpacked/CRX extensions (`config.add_extension()`)
   - Multi-tab / multi-window control (`new_tab`, `new_window`, `browser.tabs`, `tile_windows()`, `grant_all_permissions()`)
   - Isolated incognito contexts & authenticated HTTP/SOCKS5 proxies (`browser.create_context(proxy_server="http://user:pass@host:port")` powered by `ProxyForwarder`)
   - Cookie persistence (`browser.cookies.get_all()`, `set_all()`, `save()`, `load()`, `clear()`)

2. **[Tab Navigation, Smart Selectors, IFrames, Shadow DOM & Interactions](./references/tab-and-dom.md)**
   - Smart text search (`tab.find(best_match=True)`, `tab.find_all()`) vs CSS (`tab.select()`, `tab.select_all(include_frames=True)`) vs XPath (`tab.xpath()`)
   - v0.50+ flat-mode IFrame inspection (`await tab.get_frames()`, querying inside frames) and Shadow DOM traversal (`elem.shadow_children`, `expert=True`)
   - Element interactions: `click()`, `mouse_click()`, `mouse_move()`, `mouse_drag()`, `send_keys()`, `clear_input()`, `send_file()` (file upload), `select_option()`, `set_value()`, `apply("(el) => ...")`
   - Viewport & media: `scroll_down()`, `scroll_into_view()`, `set_window_size()`, tab/element `save_screenshot(full_page=True)`, element `record_video()`, visual debugging (`flash()`, `highlight_overlay()`)
   - Cloudflare challenge checkbox: `tab.verify_cf()` and `tab.template_location()` (preconditions and pitfalls)

3. **[Raw Chrome DevTools Protocol (CDP), Network Interception & Storage](./references/cdp-and-network.md)**
   - Calling any `nodriver.cdp.*` domain (`await tab.send(cdp.<domain>.<command>())` and `tab.feed_cdp()`)
   - Event listeners (`tab.add_handler(EventClass, callback)`)
   - Intercepting, blocking, or modifying HTTP requests/headers (`cdp.fetch.enable()`, `cdp.fetch.RequestPaused`)
   - Capturing XHR/Fetch/WebSocket payloads (`cdp.network.get_response_body()`)
   - JavaScript evaluation (`tab.evaluate()`, `tab.js_dumps()`), `localStorage` read/write, and controlled file downloads (`set_download_path()`, `download_file()`)

---

## Safety & Human-in-the-Loop Rules

1. **Clear Cloudflare checkbox challenges with `verify_cf()`**: When a tab lands on a Cloudflare challenge page (title/text such as `Just a moment...` or `Verify you are human`), call `await tab.verify_cf()` to click the checkbox instead of stopping (see "Cloudflare Challenges" in Layer 2).
2. **Pause on anything `verify_cf()` cannot clear**: Other CAPTCHAs (image puzzles, hCaptcha/reCAPTCHA), login walls, and pages that are still gated after `verify_cf()`: stop immediately and report it to the user. Offer to launch `session_manager.py open --profile-dir <dir> --url <url>` in headed mode so the user can complete verification or login manually in the visible browser window, then reuse `--profile-dir <dir>` for subsequent authorized access.
3. **Respect target servers**: Avoid aggressive concurrency; prefer sequential navigation with reasonable waits and clean `browser.stop()` teardown so orphan Chromium processes do not accumulate.
