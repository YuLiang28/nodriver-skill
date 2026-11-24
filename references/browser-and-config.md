# Browser Lifecycle, Configuration, Contexts, Proxies & Cookies

Complete reference for `nodriver.start()`, `Config`, `Browser`, `CookieJar`, and `ProxyForwarder` (`nodriver >= 0.50`).

---

## 1. Launching & Configuring a Browser (`start` & `Config`)

### Quick Start vs Explicit `Config`
```python
import asyncio
import nodriver as uc

async def main():
    # Option 1: Keyword arguments directly on uc.start()
    browser = await uc.start(
        headless=False,
        user_data_dir="./profiles/my_profile",  # Persists profile; omit for auto-cleaned temp dir
        browser_executable_path=None,           # Auto-detects Chrome / Edge / Brave / Chromium
        browser_args=["--window-size=1440,900"],
        sandbox=True,                           # Auto-disabled when running as root on Linux
        lang="en-US",
        expert=False,                           # True opens closed shadow-roots & disables site isolation
    )
    try:
        tab = await browser.get("https://example.com")
    finally:
        browser.stop()
        await asyncio.sleep(0.2)
```

### Using the `Config` Object & Gotchas
```python
config = uc.Config(
    user_data_dir="./profiles/work",
    headless=False,
    lang="en-US",
    expert=False,
)
# Add extra Chromium CLI flags via add_argument:
config.add_argument("--mute-audio")
config.add_argument("--disable-notifications")

# IMPORTANT GOTCHA:
# Do NOT pass "headless", "data-dir", "no-sandbox", or "lang" to config.add_argument()!
# nodriver raises ValueError for those flags; always set them as attributes on Config:
# config.headless = True
# config.sandbox = False

browser = await uc.start(config=config)
```

### Detecting Installed Browsers
```python
from nodriver.core.config import find_chrome_executable

default_exe = find_chrome_executable()              # Path to primary Chromium browser
all_candidates = find_chrome_executable(return_all=True)  # List of all detected browsers
```

---

## 2. Connecting to an Existing Browser Session

If a user already has Chrome/Edge running with `--remote-debugging-port=9222`, pass both `host` and `port`. When both are set, `nodriver` attaches over WebSocket without spawning a new browser process:

```python
browser = await uc.start(host="127.0.0.1", port=9222)
tab = browser.main_tab
print(tab.target.url)
# Note: Avoid calling browser.stop() if you want to leave the user's external browser open!
```

### Migrating a Running `undetected_chromedriver` Instance
```python
from nodriver.core.util import create_from_undetected_chromedriver

nd_browser = await create_from_undetected_chromedriver(uc_driver)
```

---

## 3. Loading Browser Extensions

`Config.add_extension()` accepts either an unpacked extension directory (containing `manifest.json`) or a packed `.crx` / `.zip` archive:

```python
config = uc.Config(headless=False)  # Extensions generally require headed mode or --headless=new
config.add_extension("./extensions/my-unpacked-ext")
config.add_extension("./extensions/ublock.crx")

browser = await uc.start(config=config)
```

---

## 4. Multi-Tab, Multi-Window & Permissions Management

```python
# Primary tab
tab1 = await browser.get("https://example.com")

# Open in a new tab or a separate window
tab2 = await browser.get("https://example.org", new_tab=True)
tab3 = await browser.get("https://iana.org", new_window=True)

# Inspect all active page tabs
for t in browser.tabs:
    print(t.target.title, t.target.url)

# Focus / bring tab to front
await tab2.activate()
await tab2.bring_to_front()

# Automatically tile multiple browser windows across the monitor grid (uses mss)
await browser.tile_windows(max_columns=2)

# Grant browser permissions (clipboard, geolocation, notifications, media, storageAccess, etc.)
await browser.grant_all_permissions()

# Close a single tab
await tab3.close()
```

---

## 5. Isolated Contexts & Authenticated Proxies (`create_context`)

`browser.create_context()` creates an isolated incognito-style `BrowserContext` within the same browser process. When `proxy_server` includes credentials (`http://user:pass@host:port` or `socks5://user:pass@host:port`), `nodriver` automatically spins up a local `ProxyForwarder` so Chromium never prompts for proxy auth:

```python
tab_isolated = await browser.create_context(
    url="https://httpbin.org/ip",
    new_window=True,
    dispose_on_detach=True,
    proxy_server="http://username:password@proxy.example.com:8080",
    proxy_bypass_list=["localhost", "127.0.0.1"],
)
content = await tab_isolated.get_content()
```

---

## 6. Cookie Management (`browser.cookies`)

`browser.cookies` returns a `CookieJar` controller backed by CDP `storage` commands:

```python
# Save all cookies (or filter by URL/domain regex pattern) to a file
await browser.cookies.save(file="session.cookies.dat", pattern=".*")

# Load cookies into a fresh browser session
await browser.cookies.load(file="session.cookies.dat", pattern=".*")

# Retrieve cookies as CDP Cookie objects
cdp_cookies = await browser.cookies.get_all(requests_cookie_format=False)

# Retrieve cookies as Python http.cookiejar / requests-compatible Cookie objects
req_cookies = await browser.cookies.get_all(requests_cookie_format=True)

# Set custom CDP CookieParam objects
from nodriver import cdp
await browser.cookies.set_all([
    cdp.network.CookieParam(
        name="theme",
        value="dark",
        domain=".example.com",
        path="/",
        secure=True,
    )
])

# Clear all browser cookies
await browser.cookies.clear()
```
