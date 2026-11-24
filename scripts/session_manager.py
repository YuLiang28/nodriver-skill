#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#   "nodriver>=0.50.99",
# ]
# ///
"""
Persistent browser profile and CookieJar session manager for Human-in-the-Loop workflows.

Subcommands:
  open     Launch a headed browser with --profile-dir so the user can manually log in
           or complete verification, then close the window (or let --duration expire)
           to persist session state and optionally export cookies.
  inspect  List cookie metadata (domains, names, expiry) stored in --profile-dir.
  clear    Clear all cookies inside --profile-dir.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys
import time

import nodriver as uc


async def cmd_open(args: argparse.Namespace) -> int:
    profile_dir = pathlib.Path(args.profile_dir).resolve()
    profile_dir.mkdir(parents=True, exist_ok=True)

    browser = await uc.start(
        headless=False,
        user_data_dir=str(profile_dir),
        browser_executable_path=args.browser_path,
    )
    try:
        if args.import_cookies:
            cfile = pathlib.Path(args.import_cookies).resolve()
            if cfile.exists():
                await browser.cookies.load(file=cfile)
                sys.stderr.write(f"[session_manager] Imported cookies from {cfile}\n")

        tab = await browser.get(args.url)
        await tab.bring_to_front()

        sys.stderr.write(
            f"[session_manager] Opened headed browser using profile: {profile_dir}\n"
            f"  URL: {args.url}\n"
            f"  Complete your login or manual verification in the browser window.\n"
            f"  Close the browser window when finished (or wait up to {args.duration}s).\n"
        )

        deadline = time.monotonic() + args.duration
        last_cookies_export = None
        while time.monotonic() < deadline:
            if browser.stopped:
                break
            proc = getattr(browser, "_process", None)
            if proc is not None and proc.returncode is not None:
                break
            if args.export_cookies:
                try:
                    out_cookie = pathlib.Path(args.export_cookies).resolve()
                    out_cookie.parent.mkdir(parents=True, exist_ok=True)
                    await browser.cookies.save(file=out_cookie)
                    last_cookies_export = str(out_cookie)
                except Exception:
                    pass
            await asyncio.sleep(1.5)

        summary = {
            "status": "completed",
            "profile_dir": str(profile_dir),
            "exported_cookies": last_cookies_export,
        }
        print(json.dumps(summary, indent=2))
        return 0
    finally:
        try:
            browser.stop()
        except Exception:
            pass
        await asyncio.sleep(0.2)


async def cmd_inspect(args: argparse.Namespace) -> int:
    profile_dir = pathlib.Path(args.profile_dir).resolve()
    if not profile_dir.exists():
        sys.stderr.write(f"[session_manager] Profile directory not found: {profile_dir}\n")
        return 1

    browser = await uc.start(
        headless=True,
        user_data_dir=str(profile_dir),
        browser_executable_path=args.browser_path,
    )
    try:
        await browser.get("about:blank")
        cookies = await browser.cookies.get_all(requests_cookie_format=False)
        items = []
        for c in cookies:
            entry = {
                "domain": getattr(c, "domain", ""),
                "name": getattr(c, "name", ""),
                "path": getattr(c, "path", "/"),
                "secure": bool(getattr(c, "secure", False)),
                "httpOnly": bool(getattr(c, "http_only", False)),
                "expires": getattr(c, "expires", None),
            }
            if args.show_values:
                entry["value"] = getattr(c, "value", "")
            items.append(entry)

        result = {
            "profile_dir": str(profile_dir),
            "cookie_count": len(items),
            "domains": sorted({i["domain"] for i in items if i["domain"]}),
            "cookies": items,
        }
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    finally:
        browser.stop()
        await asyncio.sleep(0.2)


async def cmd_clear(args: argparse.Namespace) -> int:
    profile_dir = pathlib.Path(args.profile_dir).resolve()
    if not profile_dir.exists():
        sys.stderr.write(f"[session_manager] Profile directory not found: {profile_dir}\n")
        return 1

    browser = await uc.start(
        headless=True,
        user_data_dir=str(profile_dir),
        browser_executable_path=args.browser_path,
    )
    try:
        await browser.get("about:blank")
        await browser.cookies.clear()
        print(json.dumps({"status": "cleared", "profile_dir": str(profile_dir)}, indent=2))
        return 0
    finally:
        browser.stop()
        await asyncio.sleep(0.2)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Manage persistent nodriver profiles and cookies.")
    sub = p.add_subparsers(dest="command", required=True)

    p_open = sub.add_parser("open", help="Open headed persistent profile for manual login/session setup.")
    p_open.add_argument("--url", default="https://example.com", help="Initial URL to open.")
    p_open.add_argument("--profile-dir", required=True, help="Directory to store persistent browser profile.")
    p_open.add_argument("--duration", type=int, default=300, help="Max seconds to keep window open (default: 300).")
    p_open.add_argument("--import-cookies", help="Optional CookieJar file to import on launch.")
    p_open.add_argument("--export-cookies", help="Optional CookieJar file path to continuously save cookies.")
    p_open.add_argument("--browser-path", help="Explicit path to Chrome/Edge/Brave executable.")

    p_ins = sub.add_parser("inspect", help="Inspect cookies stored in a persistent profile.")
    p_ins.add_argument("--profile-dir", required=True, help="Persistent browser profile directory.")
    p_ins.add_argument("--show-values", action="store_true", help="Include raw cookie values in output.")
    p_ins.add_argument("--browser-path", help="Explicit path to Chrome/Edge/Brave executable.")

    p_clr = sub.add_parser("clear", help="Clear all cookies in a persistent profile.")
    p_clr.add_argument("--profile-dir", required=True, help="Persistent browser profile directory.")
    p_clr.add_argument("--browser-path", help="Explicit path to Chrome/Edge/Brave executable.")

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    dispatch = {
        "open": cmd_open,
        "inspect": cmd_inspect,
        "clear": cmd_clear,
    }
    return uc.loop().run_until_complete(dispatch[args.command](args))


if __name__ == "__main__":
    raise SystemExit(main())
