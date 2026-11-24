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
Environment checker and isolated .venv initializer for nodriver-skill.

Usage:
  # With uv (zero-config PEP 723 auto-provisioning):
  uv run scripts/setup_env.py --check-only

  # Without uv (creates <skill_dir>/.venv and installs requirements.txt):
  python scripts/setup_env.py

  # Install into current Python environment instead of .venv:
  python scripts/setup_env.py --system

  # Install nodriver in editable mode from a local source checkout:
  python scripts/setup_env.py --editable /path/to/nodriver
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import venv

SKILL_DIR = pathlib.Path(__file__).resolve().parent.parent
VENV_DIR = SKILL_DIR / ".venv"
REQ_FILE = SKILL_DIR / "requirements.txt"


def get_venv_python(venv_dir: pathlib.Path) -> pathlib.Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def probe_python_env(python_exe: str) -> dict:
    probe_code = (
        "import json, sys\n"
        "info = {'python_executable': sys.executable, 'python_version': sys.version.split()[0]}\n"
        "try:\n"
        "    import nodriver\n"
        "    from nodriver.core.config import find_chrome_executable\n"
        "    info['nodriver_installed'] = True\n"
        "    info['nodriver_version'] = getattr(nodriver, '__version__', 'unknown')\n"
        "    try:\n"
        "        exe = find_chrome_executable()\n"
        "        info['browser_executable'] = str(exe) if exe else None\n"
        "    except Exception as e:\n"
        "        info['browser_executable'] = None\n"
        "        info['browser_Lookup_error'] = str(e)\n"
        "except Exception as e:\n"
        "    info['nodriver_installed'] = False\n"
        "    info['import_error'] = str(e)\n"
        "try:\n"
        "    import bs4, markdownify\n"
        "    info['parsers_installed'] = True\n"
        "except Exception:\n"
        "    info['parsers_installed'] = False\n"
        "print(json.dumps(info))\n"
    )
    proc = subprocess.run(
        [python_exe, "-c", probe_code],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return {
            "python_executable": python_exe,
            "nodriver_installed": False,
            "error": proc.stderr.strip() or proc.stdout.strip(),
        }
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:
        return {
            "python_executable": python_exe,
            "nodriver_installed": False,
            "raw_output": proc.stdout.strip(),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize or verify nodriver-skill environment.")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check current Python (or existing .venv) without installing packages.",
    )
    parser.add_argument(
        "--system",
        action="store_true",
        help="Install dependencies into the active Python interpreter instead of <skill_dir>/.venv.",
    )
    parser.add_argument(
        "--editable",
        type=str,
        default=None,
        help="Optional path to a local nodriver git checkout for pip install -e.",
    )
    args = parser.parse_args()

    uv_path = shutil.which("uv")

    if args.check_only:
        target_py = sys.executable
        venv_py = get_venv_python(VENV_DIR)
        current_probe = probe_python_env(target_py)
        if not current_probe.get("nodriver_installed") and venv_py.exists():
            current_probe = probe_python_env(str(venv_py))
        current_probe["uv_available"] = bool(uv_path)
        current_probe["ready"] = bool(
            current_probe.get("nodriver_installed") and current_probe.get("browser_executable")
        )
        print(json.dumps(current_probe, indent=2))
        return 0 if current_probe["ready"] else 1

    if args.system:
        target_py = pathlib.Path(sys.executable)
    else:
        venv_py = get_venv_python(VENV_DIR)
        if not venv_py.exists():
            sys.stderr.write(f"[setup_env] Creating isolated virtual environment at {VENV_DIR} ...\n")
            builder = venv.EnvBuilder(with_pip=True)
            builder.create(VENV_DIR)
        target_py = venv_py

    pip_cmd = [str(target_py), "-m", "pip", "install", "--upgrade"]
    if args.editable:
        local_repo = pathlib.Path(args.editable).resolve()
        if not local_repo.exists():
            sys.stderr.write(f"[setup_env] Editable path does not exist: {local_repo}\n")
            return 2
        pip_cmd.extend(["-e", str(local_repo), "beautifulsoup4>=4.12.0", "markdownify>=0.13.1"])
    else:
        pip_cmd.extend(["-r", str(REQ_FILE)])

    sys.stderr.write(f"[setup_env] Installing dependencies via: {' '.join(pip_cmd)}\n")
    install_proc = subprocess.run(pip_cmd, check=False)
    if install_proc.returncode != 0:
        sys.stderr.write("[setup_env] Dependency installation failed.\n")
        return install_proc.returncode

    report = probe_python_env(str(target_py))
    report["uv_available"] = bool(uv_path)
    report["ready"] = bool(report.get("nodriver_installed") and report.get("browser_executable"))
    if not report.get("browser_executable"):
        report["hint"] = (
            "No Chromium-based browser (Chrome, Edge, Brave, Chromium) was auto-detected. "
            "Install Chrome/Edge or pass --browser-path explicitly."
        )
    print(json.dumps(report, indent=2))
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
