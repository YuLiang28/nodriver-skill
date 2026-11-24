#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#   "nodriver>=0.50.99",
#   "beautifulsoup4>=4.12.0",
#   "markdownify>=0.13.1",
# ]
# ///
"""
Universal page fetcher and extractor powered by nodriver.

Renders dynamic JavaScript pages in Chromium and exports clean Markdown, raw HTML,
plain text, links JSON, or a full JSON bundle (with optional screenshots and persistent profiles).
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import pathlib
import re
import sys
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from markdownify import markdownify as md_convert
import nodriver as uc

GATE_PATTERNS = [
    re.compile(r"just a moment\.{0,3}", re.IGNORECASE),
    re.compile(r"attention required!?\s*\|\s*cloudflare", re.IGNORECASE),
    re.compile(r"verify you are human", re.IGNORECASE),
    re.compile(r"checking your browser before accessing", re.IGNORECASE),
    re.compile(r"access denied", re.IGNORECASE),
]


def detect_gate(title: str, body_text: str) -> str | None:
    sample = f"{title}\n{body_text[:1500]}"
    for pat in GATE_PATTERNS:
        if pat.search(sample) and len(body_text.strip()) < 4000:
            return pat.pattern
    return None


def html_to_clean_markdown(html: str, base_url: str) -> tuple[str, str, list[dict]]:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg", "template", "iframe"]):
        tag.decompose()

    links: list[dict] = []
    seen_hrefs: set[str] = set()
    for a in soup.find_all("a", href=True):
        raw_href = a["href"].strip()
        if not raw_href or raw_href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        abs_href = urljoin(base_url, raw_href)
        a["href"] = abs_href
        text = " ".join(a.get_text(" ", strip=True).split())
        if abs_href not in seen_hrefs:
            seen_hrefs.add(abs_href)
            links.append({"text": text, "href": abs_href})

    for img in soup.find_all("img", src=True):
        img["src"] = urljoin(base_url, img["src"].strip())

    plain_text = "\n".join(
        line.strip() for line in soup.get_text("\n").splitlines() if line.strip()
    )
    markdown = md_convert(str(soup), heading_style="ATX", bullets="-")
    markdown = re.sub(r"\n{3,}", "\n\n", markdown).strip()
    return markdown, plain_text, links


async def run_fetch(args: argparse.Namespace) -> int:
    connect_host, connect_port = None, None
    if args.connect:
        host_part, port_part = args.connect.rsplit(":", 1)
        connect_host, connect_port = host_part, int(port_part)

    profile_dir = str(pathlib.Path(args.profile_dir).resolve()) if args.profile_dir else None
    headless = not args.headed

    browser = await uc.start(
        headless=headless,
        user_data_dir=profile_dir,
        browser_executable_path=args.browser_path,
        lang=args.lang,
        host=connect_host,
        port=connect_port,
        expert=args.expert,
    )

    attached_external = bool(connect_host and connect_port)
    try:
        if args.cookies_file:
            cookie_path = pathlib.Path(args.cookies_file).resolve()
            if cookie_path.exists():
                await browser.cookies.load(file=cookie_path)

        if args.proxy:
            tab = await browser.create_context(
                url=args.url,
                new_window=not headless,
                proxy_server=args.proxy,
            )
        else:
            tab = await browser.get(args.url)

        await tab.select("body", timeout=args.timeout)

        if args.wait_selector:
            await tab.select(args.wait_selector, timeout=args.timeout)
        if args.wait_text:
            await tab.find(args.wait_text, best_match=True, timeout=args.timeout)
        if args.wait_seconds > 0:
            await tab.sleep(args.wait_seconds)

        for _ in range(args.scroll_steps):
            if await tab.scroll_bottom_reached():
                break
            await tab.scroll_down(args.scroll_amount)
            await tab.sleep(args.scroll_delay)

        title = await tab.evaluate("document.title", return_by_value=True) or ""
        final_url = tab.target.url or args.url

        if args.selector:
            elems = await tab.select_all(args.selector, timeout=args.timeout)
            if not elems:
                sys.stderr.write(f"[fetch_page] No elements matched selector: {args.selector}\n")
                return 2
            html_parts = [await el.get_html() for el in elems]
            raw_html = "\n\n".join(html_parts)
        else:
            raw_html = await tab.get_content()

        markdown, plain_text, links = html_to_clean_markdown(raw_html, final_url)
        gate_match = detect_gate(str(title), plain_text)

        if gate_match:
            sys.stderr.write(
                f"[GATE_DETECTED] Target page appears gated by an anti-bot or access challenge "
                f"(matched: {gate_match!r}).\n"
                f"To clear a Cloudflare checkbox challenge, call tab.verify_cf() in a custom "
                f"script (see SKILL.md). For anything else, run session_manager.py in headed "
                f"mode with --profile-dir so the user can complete verification manually.\n"
            )

        if args.screenshot:
            shot_path = pathlib.Path(args.screenshot).resolve()
            shot_path.parent.mkdir(parents=True, exist_ok=True)
            fmt = "png" if shot_path.suffix.lower() == ".png" else "jpeg"
            await tab.save_screenshot(filename=shot_path, format=fmt, full_page=args.full_page)
            sys.stderr.write(f"[fetch_page] Saved screenshot to {shot_path}\n")

        fetched_at = dt.datetime.now(dt.timezone.utc).isoformat()

        if args.format == "html":
            rendered_output = raw_html
        elif args.format == "text":
            rendered_output = plain_text
        elif args.format == "links":
            rendered_output = json.dumps(links, ensure_ascii=False, indent=2)
        elif args.format == "json":
            local_storage = {}
            try:
                local_storage = await tab.get_local_storage() or {}
            except Exception:
                pass
            payload = {
                "requested_url": args.url,
                "final_url": final_url,
                "title": title,
                "fetched_at": fetched_at,
                "gate_detected": bool(gate_match),
                "markdown": markdown,
                "links": links,
                "local_storage": local_storage,
            }
            rendered_output = json.dumps(payload, ensure_ascii=False, indent=2)
        else:
            if args.no_frontmatter:
                rendered_output = markdown
            else:
                safe_title = str(title).replace('"', '\\"')
                frontmatter = (
                    f"---\n"
                    f'title: "{safe_title}"\n'
                    f'source_url: "{final_url}"\n'
                    f'fetched_at: "{fetched_at}"\n'
                    f"---\n\n"
                )
                rendered_output = frontmatter + markdown + "\n"

        if args.output:
            out_path = pathlib.Path(args.output).resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(rendered_output, encoding="utf-8")
            sys.stderr.write(
                f"[fetch_page] Wrote {len(rendered_output)} chars ({args.format}) to {out_path}\n"
            )
        else:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
            sys.stdout.write(rendered_output)
            if not rendered_output.endswith("\n"):
                sys.stdout.write("\n")

        return 3 if gate_match else 0
    finally:
        if not attached_external:
            browser.stop()
            await asyncio.sleep(0.2)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Fetch and extract rendered web pages with nodriver.")
    p.add_argument("url", help="Target URL to open.")
    p.add_argument(
        "--format",
        choices=["markdown", "html", "text", "links", "json"],
        default="markdown",
        help="Output format (default: markdown).",
    )
    p.add_argument("-o", "--output", help="Output file path (UTF-8). Prints to stdout if omitted.")
    p.add_argument("--no-frontmatter", action="store_true", help="Omit YAML header in markdown output.")
    p.add_argument("--selector", help="Extract only elements matching this CSS selector.")
    p.add_argument("--wait-selector", help="Wait for this CSS selector before extracting.")
    p.add_argument("--wait-text", help="Wait for text to appear before extracting.")
    p.add_argument("--wait-seconds", type=float, default=1.0, help="Extra settle wait in seconds (default: 1.0).")
    p.add_argument("--timeout", type=float, default=15.0, help="Selector/navigation timeout in seconds.")
    p.add_argument("--scroll-steps", type=int, default=0, help="Number of downward scroll steps for lazy content.")
    p.add_argument("--scroll-amount", type=int, default=80, help="Scroll amount per step (default: 80).")
    p.add_argument("--scroll-delay", type=float, default=0.8, help="Delay in seconds between scroll steps.")
    p.add_argument("--headed", action="store_true", help="Launch visible browser window instead of headless.")
    p.add_argument("--profile-dir", help="Persistent user_data_dir path to reuse cookies/login state.")
    p.add_argument("--cookies-file", help="Load cookies from a CookieJar session file before navigating.")
    p.add_argument("--connect", help="Attach to existing browser debug host:port (e.g. 127.0.0.1:9222).")
    p.add_argument("--proxy", help="Optional proxy URL (supports http://user:pass@host:port via create_context).")
    p.add_argument("--browser-path", help="Explicit path to Chrome/Edge/Brave executable.")
    p.add_argument("--lang", default="en-US", help="Browser language (default: en-US).")
    p.add_argument("--expert", action="store_true", help="Enable nodriver expert mode (forces open shadow roots).")
    p.add_argument("--screenshot", help="Save a screenshot (.jpg or .png) before closing.")
    p.add_argument("--full-page", action="store_true", help="Capture full-page screenshot when --screenshot is set.")
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return uc.loop().run_until_complete(run_fetch(args))


if __name__ == "__main__":
    raise SystemExit(main())
