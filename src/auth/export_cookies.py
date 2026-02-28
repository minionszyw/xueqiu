from __future__ import annotations

from pathlib import Path
import json

try:
    from playwright.sync_api import sync_playwright
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "未安装 playwright，请先执行: uv sync --extra browser"
    ) from exc



def export_cookies(output: Path) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://xueqiu.com", wait_until="domcontentloaded")
        print("请在打开的浏览器中完成登录，然后按回车继续...")
        input()
        cookies = context.cookies()
        output.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
        browser.close()


if __name__ == "__main__":
    export_cookies(Path("cookies.json"))
    print("cookies 已导出到 cookies.json")
