# nodriver-skill

An universal **Agent Skill** wrapping Python's [`nodriver`](https://github.com/ultrafunkamsterdam/nodriver) (`v0.50+`) for asynchronous Chromium browser automation, dynamic SPA web extraction, persistent session management, DOM/IFrame/Shadow-DOM interaction, and raw Chrome DevTools Protocol (CDP) network inspection—without Selenium or `chromedriver` binaries.

基于 Python [`nodriver`](https://github.com/ultrafunkamsterdam/nodriver)（`v0.50+`）封装的通用 **AI Agent Skill**。无需 `chromedriver` 或 Selenium，直接通过异步 Chrome DevTools Protocol (CDP) 操控本地 Chrome / Edge / Brave，支持动态网页抓取转 Markdown、持久化登录会话、复杂 DOM / IFrame / Shadow DOM 交互以及原生 CDP 网络流量监听与请求拦截。

---

## Installation / 安装方式

Install via [`npx skills`](https://github.com/vercel-labs/skills) into your current project or globally:

通过 `npx skills` 一键安装到当前项目（`.agents/skills/nodriver`）或全局环境：

```bash
# Project-level installation / 安装到当前项目
npx skills add YuLiang28/nodriver-skill

# Global installation / 全局安装（本机所有项目通用）
npx skills add YuLiang28/nodriver-skill --global
```

---

## Dependency Initialization / 依赖初始化机制

`npx skills` only copies skill files and does not run post-install hooks. This skill provides a **dual-path zero-pollution setup**:

`npx skills` 仅拉取文件而不自动执行脚本，本仓库设计了**双通道零污染依赖初始化机制**：

1. **Path A — `uv run` Zero-Config (Recommended / 推荐首选)**
   All CLI scripts in `scripts/` declare [PEP 723](https://peps.python.org/pep-0723/) inline dependencies. If [`uv`](https://docs.astral.sh/uv/) is installed, running any script automatically provisions and caches an isolated environment on first execution:
   所有 `scripts/*.py` 均内置 PEP 723 依赖声明。只要本机安装了 `uv`，首次执行脚本时会自动创建隔离缓存环境并安装 `nodriver>=0.50.99`：
   ```bash
   uv run scripts/setup_env.py --check-only
   uv run scripts/fetch_page.py "https://example.com" -o page.md
   ```

2. **Path B — Isolated `.venv` Fallback (无 `uv` 环境自动兜底)**
   If `uv` is not installed, run `setup_env.py` once to verify local Chrome/Edge/Brave availability and build `<skill_dir>/.venv`:
   若未安装 `uv`，执行一次 `setup_env.py` 即可自动检测本机浏览器并在 Skill 目录内构建独立的 `.venv` 虚拟环境：
   ```bash
   python scripts/setup_env.py
   ```

---

## Capability Matrix / 能力全景

| Layer / 层级 | Component / 模块 | Capabilities Covered / 覆盖能力 |
| :--- | :--- | :--- |
| **CLI Tools**<br>即用命令行工具 | `scripts/setup_env.py` | Browser executable detection (Chrome/Edge/Brave/Chromium), `.venv` provisioning, JSON readiness check.<br>浏览器路径自动探测、独立 `.venv` 构建、JSON 状态自检。 |
| | `scripts/fetch_page.py` | Render JS SPAs -> Markdown / HTML / Plain Text / Links / JSON + `localStorage` + Full-page Screenshot + Gate Detection.<br>动态渲染提取 Markdown/HTML/链接/截图，支持等待选择器、懒加载滚动与持久化 Profile。 |
| | `scripts/session_manager.py` | Human-in-the-Loop headed profile session (`user_data_dir`) for manual login, `CookieJar` export/import/inspect.<br>人机协同有头持久化会话管理、人工登录固化、Cookie 导出与查看。 |
| | `scripts/network_capture.py` | CDP `RequestWillBeSent` & `ResponseReceived` sniffer saving XHR/Fetch JSON/text payloads to `.jsonl`.<br>原生 CDP 接口抓包，自动过滤并落盘后台 XHR/Fetch 响应体。 |
| **References**<br>全量原生能力手册 | `references/browser-and-config.md` | `Config`, `start()`, remote debug port attach (`host:port`), extensions (`add_extension`), `expert` mode, `create_context` + authenticated `ProxyForwarder`, `CookieJar`, multi-window `tile_windows()`. |
| | `references/tab-and-dom.md` | `find(best_match=True)`, `select_all(include_frames=True)`, `xpath()`, v0.50+ flat-mode `get_frames()`, Shadow DOM, mouse/keyboard/drag, `send_file()` upload, `save_screenshot()`, `record_video()`. |
| | `references/cdp-and-network.md` | Direct `nodriver.cdp.*` commands, `add_handler()`, `cdp.fetch.RequestPaused` request interception/modification, `evaluate()` / `js_dumps()`, `localStorage`, controlled downloads. |

---

## Repository Structure / 目录结构

```text
nodriver-skill/
├── SKILL.md                        # Agent instructions & progressive disclosure router
├── README.md                       # Bilingual documentation (EN / ZH)
├── LICENSE                         # MIT License
├── requirements.txt                # Standard pip dependencies
├── scripts/
│   ├── setup_env.py                # Browser check & .venv initializer
│   ├── fetch_page.py               # Universal page renderer & Markdown/HTML/JSON exporter
│   ├── session_manager.py          # Persistent profile & CookieJar manager
│   └── network_capture.py          # CDP XHR/Fetch traffic & response body sniffer
└── references/
    ├── browser-and-config.md       # Browser lifecycle, Config, Contexts, Proxies, Cookies
    ├── tab-and-dom.md              # Locators, IFrames, Shadow DOM, Mouse/Keyboard, Media
    └── cdp-and-network.md          # Raw CDP domains, Event Bus, Request Interception, Storage
```

---

## Compliance & Responsible Use / 合规使用说明

This skill is designed for legitimate browser automation, testing, and authorized web content extraction. Automated CAPTCHA solving or anti-bot challenge bypassing is intentionally excluded; when interacting with sites requiring login or human verification, use `session_manager.py` in headed mode with a persistent `--profile-dir` to complete authentication manually.

本 Skill 面向合法的浏览器自动化测试与授权数据采集设计，不包含自动破解或绕过验证码/反爬质询的逻辑；访问需要登录或真人验证的站点时，请使用 `session_manager.py` 打开有头持久化 Profile 手动完成认证后复用会话。

## License

MIT License (Note: Upstream [`nodriver`](https://github.com/ultrafunkamsterdam/nodriver) is licensed under AGPL-3.0 and installed separately via PyPI).
