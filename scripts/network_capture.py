#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#   "nodriver>=0.50.99",
# ]
# ///
"""
CDP network traffic & XHR/Fetch response body sniffer powered by nodriver.

Captures HTTP requests and response bodies matching URL / MIME filters while loading
and optionally scrolling a page, outputting structured JSON Lines (.jsonl).
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import pathlib
import re
import sys

import nodriver as uc
from nodriver import ProtocolException, cdp


async def run_capture(args: argparse.Namespace) -> int:
    url_regex = re.compile(args.url_filter, re.IGNORECASE) if args.url_filter else None
    mime_sub = args.mime_filter.lower() if args.mime_filter else None

    connect_host, connect_port = None, None
    if args.connect:
        h, p = args.connect.rsplit(":", 1)
        connect_host, connect_port = h, int(p)

    profile_dir = str(pathlib.Path(args.profile_dir).resolve()) if args.profile_dir else None
    headless = not args.headed

    browser = await uc.start(
        headless=headless,
        user_data_dir=profile_dir,
        browser_executable_path=args.browser_path,
        host=connect_host,
        port=connect_port,
    )
    attached_external = bool(connect_host and connect_port)

    requests_meta: dict[str, dict] = {}
    pending_responses: list[tuple[str, cdp.network.Response]] = []

    def on_request(ev: cdp.network.RequestWillBeSent):
        req_id = str(ev.request_id)
        requests_meta[req_id] = {
            "method": ev.request.method,
            "request_headers": dict(ev.request.headers) if ev.request.headers else {},
            "post_data": getattr(ev.request, "post_data", None),
            "resource_type": str(ev.type_) if ev.type_ else None,
        }

    def on_response(ev: cdp.network.ResponseReceived):
        resp = ev.response
        if url_regex and not url_regex.search(resp.url):
            return
        if mime_sub and mime_sub not in (resp.mime_type or "").lower():
            return
        pending_responses.append((ev.request_id, resp))

    try:
        tab = browser.main_tab
        await tab.send(cdp.network.enable())
        tab.add_handler(cdp.network.RequestWillBeSent, on_request)
        tab.add_handler(cdp.network.ResponseReceived, on_response)

        tab = await browser.get(args.url)
        await tab.select("body", timeout=args.timeout)
        await tab.sleep(args.wait_seconds)

        for _ in range(args.scroll_steps):
            if await tab.scroll_bottom_reached():
                break
            await tab.scroll_down(80)
            await tab.sleep(args.scroll_delay)

        records: list[dict] = []
        for req_id, resp in pending_responses[: args.max_items]:
            meta = requests_meta.get(str(req_id), {})
            record: dict = {
                "url": resp.url,
                "method": meta.get("method", "GET"),
                "status": resp.status,
                "mime_type": resp.mime_type,
                "resource_type": meta.get("resource_type"),
            }
            if meta.get("post_data"):
                record["post_data"] = meta["post_data"]

            if not args.metadata_only:
                try:
                    body, is_b64 = await tab.send(cdp.network.get_response_body(req_id))
                    if is_b64:
                        raw_bytes = base64.b64decode(body)
                        if "json" in (resp.mime_type or "").lower() or "text" in (resp.mime_type or "").lower():
                            text_body = raw_bytes.decode("utf-8", errors="replace")
                            record["body"] = text_body[: args.max_body_chars]
                        else:
                            record["body_base64_len"] = len(body)
                    else:
                        if "json" in (resp.mime_type or "").lower():
                            try:
                                record["json"] = json.loads(body)
                            except Exception:
                                record["body"] = body[: args.max_body_chars]
                        else:
                            record["body"] = body[: args.max_body_chars]
                except (ProtocolException, TypeError):
                    record["body_unavailable"] = True

            records.append(record)

        lines = "\n".join(json.dumps(r, ensure_ascii=False) for r in records)
        if lines:
            lines += "\n"

        if args.output:
            out_path = pathlib.Path(args.output).resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(lines, encoding="utf-8")
            sys.stderr.write(f"[network_capture] Saved {len(records)} captured responses to {out_path}\n")
        else:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
            sys.stdout.write(lines)

        return 0
    finally:
        if not attached_external:
            browser.stop()
            await asyncio.sleep(0.2)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Capture network requests and response bodies via nodriver CDP.")
    p.add_argument("url", help="Target URL to navigate and monitor.")
    p.add_argument("--url-filter", help="Regex pattern to filter captured response URLs (e.g. 'api|graphql').")
    p.add_argument("--mime-filter", help="Substring filter on response MIME type (e.g. 'json').")
    p.add_argument("--metadata-only", action="store_true", help="Skip fetching response bodies.")
    p.add_argument("--max-items", type=int, default=100, help="Max responses to export (default: 100).")
    p.add_argument("--max-body-chars", type=int, default=50000, help="Max text chars per response body.")
    p.add_argument("--wait-seconds", type=float, default=2.5, help="Initial settle wait in seconds (default: 2.5).")
    p.add_argument("--timeout", type=float, default=15.0, help="Navigation timeout in seconds.")
    p.add_argument("--scroll-steps", type=int, default=0, help="Downward scroll steps to trigger lazy API calls.")
    p.add_argument("--scroll-delay", type=float, default=1.0, help="Delay between scroll steps.")
    p.add_argument("--headed", action="store_true", help="Run in visible browser window instead of headless.")
    p.add_argument("--profile-dir", help="Persistent user_data_dir path.")
    p.add_argument("--connect", help="Attach to existing browser debug host:port.")
    p.add_argument("--browser-path", help="Explicit path to Chrome/Edge/Brave executable.")
    p.add_argument("-o", "--output", help="Output .jsonl file path. Writes to stdout if omitted.")
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return uc.loop().run_until_complete(run_capture(args))


if __name__ == "__main__":
    raise SystemExit(main())
