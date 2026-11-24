# Tab Navigation, Smart Locators, IFrames, Shadow DOM & Media

Complete reference for `Tab` and `Element` operations in `nodriver` (`v0.50+`).

---

## 1. Navigation & Synchronization

```python
tab = await browser.get("https://example.com")

# History & reload
await tab.back()
await tab.forward()
await tab.reload(
    ignore_cache=True,
    script_to_evaluate_on_load="window.__PRELOAD_FLAG__ = true;",
)

# Wait primitives
await tab                       # Process pending CDP events on the tab
await tab.sleep(1.5)            # Non-blocking async sleep
await tab.wait_for(selector="main.loaded", timeout=15)
await tab.wait_for(text="Dashboard", timeout=15)
```

---

## 2. Smart Element Lookup (Text, CSS, XPath)

All high-level lookup methods (`find`, `find_all`, `select`, `select_all`, `xpath`) automatically retry until `timeout` seconds elapse, doubling as explicit wait conditions.

### Text Lookup (`find` / `find_all`)
Unlike naive XPath `contains()`, `best_match=True` scores candidates by closest matching text length (shortest match wins). Searching `"Accept all"` returns the actual `<button>` rather than an outer `<div>` or `<script>` block:

```python
# Single best match
accept_btn = await tab.find("Accept all", best_match=True, timeout=5)
if accept_btn:
    await accept_btn.click()

# All elements containing text
items = await tab.find_all("Read more", timeout=5)
```

### CSS Selectors (`select` / `select_all`)
```python
header = await tab.select("header h1", timeout=10)

# Include elements inside iframes with include_frames=True
cards = await tab.select_all("article.card", timeout=10, include_frames=True)

# Scoped sub-queries on an existing Element (immediate, non-waiting)
links_in_card = await cards[0].query_selector_all("a[href]")
title_el = await cards[0].query_selector("h2")
```

### XPath (`xpath`)
```python
rows = await tab.xpath("//table[@id='specs']//tr[td]", timeout=5.0)
```

---

## 3. Flat-Mode IFrames (`v0.50+`) & Shadow DOM

### Inspecting IFrames
In `nodriver >= 0.50`, flat-mode CDP connections expose `IFrame` targets directly:
```python
# Option A: Cross-frame CSS query
inputs = await tab.select_all("input[type='email']", include_frames=True)

# Option B: Enumerate inspectable IFrame objects directly
frames = await tab.get_frames()
for frame in frames:
    btn = await frame.select("button.submit", timeout=2)
    if btn:
        await btn.click()
```

### Shadow DOM Traversal
- For **open** shadow roots, inspect `elem.shadow_children` or `elem.shadow_roots`.
- For **closed** shadow roots, start the browser with `uc.start(expert=True)` (note: `expert=True` patches `attachShadow` to force open mode and disables site-isolation trials, which increases browser fingerprint detectability—use only when needed).

```python
host = await tab.select("custom-web-component")
await host.update()
for child in host.shadow_children:
    print(child.tag_name, child.text_all)
```

---

## 4. Reading Element Data & Mutating DOM

```python
el = await tab.select("article.post")

# Text & HTML
direct_text = el.text                # Immediate text node value
full_text = el.text_all              # Concatenated text of all descendants
outer_html = await el.get_html()     # Full HTML representation of the element
full_page_html = await tab.get_content()

# HTML attributes (dictionary-like access)
href = el.attrs.get("href")

# Run a JS arrow/function directly on the underlying DOM node
computed_color = await el.apply("(node) => getComputedStyle(node).color")
rect_info = await el.get_js_attributes()

# Mutate DOM values or remove noise (e.g. sticky banners before screenshots)
await el.set_text("Updated Heading")
banner = await tab.select(".cookie-banner", timeout=2)
if banner:
    await banner.remove_from_dom()
```

---

## 5. Mouse, Keyboard, Forms & File Uploads

### Clicking & Dragging
```python
btn = await tab.select("button#submit")
await btn.scroll_into_view()
await btn.click()                    # Standard DOM/CDP click
await btn.mouse_click(button="left") # Synthesized viewport mouse event at element center

# Drag-and-drop (Element-to-Element or relative pixel offset)
slider = await tab.select(".slider-handle")
await slider.mouse_drag((180, 0), relative=True, steps=15)

# Tab-level raw coordinate actions
await tab.mouse_move(400, 320, steps=12, flash=False)
await tab.mouse_click(400, 320, button="left")
await tab.mouse_drag((200, 200), (500, 350), steps=20)
```

### Text Input, Dropdowns & File Uploads
```python
email_input = await tab.select("input[name='email']")
await email_input.focus()
await email_input.clear_input()
await email_input.send_keys("buyer@example.com")

# Select an <option> element inside a <select>
opt = await tab.select("select#country option[value='US']")
await opt.select_option()

# Upload local files via <input type="file"> (pass absolute paths)
file_input = await tab.select("input[type='file']")
await file_input.send_file("D:/data/spec_sheet.pdf", "D:/data/photo.png")
```

---

## 6. Scrolling, Window Geometry, Screenshots & Video

### Scrolling & Infinite Feeds
```python
await tab.scroll_down(amount=80)     # Scroll down (percentage/step units)
await tab.scroll_up(amount=40)

# Scroll until bottom of infinite/lazy page (with safety cap)
for _ in range(20):
    if await tab.scroll_bottom_reached():
        break
    await tab.scroll_down(100)
    await tab.sleep(0.8)
```

### Window Sizing
```python
await tab.set_window_size(left=0, top=0, width=1440, height=900)
await tab.maximize()
await tab.minimize()
await tab.fullscreen()
```

### Screenshots, Element Recording & Visual Debugging
```python
# Full-page or viewport screenshot (format: "jpeg" or "png")
await tab.save_screenshot("full_page.png", format="png", full_page=True)
b64_img = await tab.save_screenshot(format="jpeg", as_base64=True)

# Cropped single-element screenshot
chart = await tab.select("#sales-chart")
await chart.save_screenshot("chart_2x.png", format="png", scale=2)

# Element video capture
await chart.record_video(filename="chart_demo.mp4", folder="./videos", duration=5)

# Visual debugging in headed mode
await chart.flash(duration=0.5)
await chart.highlight_overlay()
await tab.open_external_inspector()  # Opens DevTools frontend without dropping connection
```
