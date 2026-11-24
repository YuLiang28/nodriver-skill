# Chrome DevTools Protocol (CDP), Network Interception & Storage

`nodriver` ships strongly typed Python bindings for the entire Chrome DevTools Protocol under `nodriver.cdp` (`cdp.network`, `cdp.fetch`, `cdp.page`, `cdp.runtime`, `cdp.dom`, `cdp.storage`, `cdp.emulation`, `cdp.security`, etc.).

---

## 1. Sending Raw CDP Commands (`send` vs `feed_cdp`)

- `await tab.send(cdp.<domain>.<command>(...))`: Awaits and returns the typed CDP response.
- `tab.feed_cdp(cdp.<domain>.<command>(...))`: Fires a CDP generator asynchronously from inside synchronous/event callbacks without deadlocking the connection read loop.

```python
from nodriver import cdp

# Override User-Agent or timezone via CDP Emulation
await tab.send(
    cdp.emulation.set_timezone_override(timezone_id="America/New_York")
)
await tab.send(
    cdp.emulation.set_device_metrics_override(
        width=390, height=844, device_scale_factor=3, mobile=True
    )
)
```

---

## 2. Subscribing to CDP Events & Capturing API Responses

Register callbacks with `tab.add_handler(EventType, handler)`. Callbacks may accept `(event)` or `(event, tab)`.

```python
import base64
from nodriver import cdp, ProtocolException

captured_json = []

async def on_response(ev: cdp.network.ResponseReceived, tab):
    if "api/" not in ev.response.url:
        return
    try:
        body, is_b64 = await tab.send(cdp.network.get_response_body(ev.request_id))
        if is_b64:
            body = base64.b64decode(body).decode("utf-8", errors="replace")
        captured_json.append({
            "url": ev.response.url,
            "status": ev.response.status,
            "mime": ev.response.mime_type,
            "body": body,
        })
    except (ProtocolException, TypeError):
        # Preflight/redirect requests may have no response body
        pass

await tab.send(cdp.network.enable())
tab.add_handler(cdp.network.ResponseReceived, on_response)
await tab.get("https://example.com/app")
await tab.sleep(3)
```

---

## 3. Intercepting, Modifying, Blocking, or Mocking Requests (`cdp.fetch`)

Use `cdp.fetch` when you need to block heavy media/analytics, inject custom HTTP headers, or mock backend responses. Inside `RequestPaused`, use `tab.feed_cdp(...)` so request continuation never blocks the WebSocket reader:

```python
from nodriver import cdp

async def on_request_paused(ev: cdp.fetch.RequestPaused, tab):
    url = ev.request.url

    # Block unnecessary images/fonts to speed up scraping
    if any(url.endswith(ext) for ext in (".png", ".jpg", ".woff2", ".mp4")):
        tab.feed_cdp(
            cdp.fetch.fail_request(
                request_id=ev.request_id,
                error_reason=cdp.network.ErrorReason.BLOCKED_BY_CLIENT,
            )
        )
        return

    # Inject a custom header and continue
    headers = [cdp.fetch.HeaderEntry(name=k, value=v) for k, v in ev.request.headers.items()]
    headers.append(cdp.fetch.HeaderEntry(name="X-Custom-Trace", value="nodriver-skill"))
    tab.feed_cdp(cdp.fetch.continue_request(request_id=ev.request_id, headers=headers))

tab.add_handler(cdp.fetch.RequestPaused, on_request_paused)
await tab.send(cdp.fetch.enable())
await tab.get("https://httpbin.org/headers")
```

---

## 4. JavaScript Execution & State Extraction

```python
# Evaluate arbitrary JS expressions or async Promises
title = await tab.evaluate("document.title", return_by_value=True)
api_data = await tab.evaluate(
    "fetch('/api/status').then(r => r.json())",
    await_promise=True,
    return_by_value=True,
)

# Serialize complex global JS objects (e.g., Next.js / Nuxt hydration state)
next_data = await tab.js_dumps("__NEXT_DATA__")
```

---

## 5. `localStorage`, Resource Discovery & Downloads

### `localStorage` Read & Write
```python
storage = await tab.get_local_storage()          # Returns dict
await tab.set_local_storage({"locale": "en-US"}) # Sets key-value pairs
```

### Extracting Page Links & Frame Resources
```python
# All <a href="..."> URLs (resolved to absolute URLs by default)
urls = await tab.get_all_urls(absolute=True)

# All Elements with src/href attributes (<img>, <script>, <link>, <video>, <a>)
linked_elements = await tab.get_all_linked_sources()

# Frame resource inspection via CDP Page domain
resource_urls = await tab.get_frame_resource_urls()
matches = await tab.search_frame_resources("graphql")
```

### Controlled File Downloads & Self-Signed Certificates
```python
# Direct browser download directory
await tab.set_download_path("D:/downloads")

# Download a specific asset URL through the browser context
await tab.download_file("https://example.com/manual.pdf", filename="D:/downloads/manual.pdf")

# Proceed past local/staging self-signed TLS warning interstitials
await tab.bypass_insecure_connection_warning()
```
