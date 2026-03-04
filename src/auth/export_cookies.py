from __future__ import annotations

from pathlib import Path
import json

try:
    from playwright.sync_api import sync_playwright
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "未安装 playwright，请先执行: uv sync --extra browser"
    ) from exc



def export_cookies(output: Path) -> None:
    with sync_playwright() as p:
        try:
            # 优先使用本机已安装的 Chrome，避免必须下载 Playwright Chromium。
            browser = p.chromium.launch(channel="chrome", headless=False)
        except Exception:
            browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        try:
            page.goto("https://xueqiu.com", wait_until="domcontentloaded", timeout=120000)
        except PlaywrightTimeoutError:
            # 网络抖动或站点反爬导致超时时，不中断流程，允许用户手动访问并登录。
            print("自动打开雪球首页超时，请在浏览器地址栏手动访问 https://xueqiu.com 并完成登录。")
        print("请在打开的浏览器中完成登录（确认进入登录后页面），然后按回车继续...")
        input()
        cookies = context.cookies()
        output.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
        browser.close()


if __name__ == "__main__":
    export_cookies(Path("cookies.json"))
    print("cookies 已导出到 cookies.json")
