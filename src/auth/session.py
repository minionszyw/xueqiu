from __future__ import annotations

from pathlib import Path
import json

import httpx


def load_cookie_header(cookie_file: Path) -> str:
    if not cookie_file.exists():
        raise FileNotFoundError(f"Cookie 文件不存在: {cookie_file}")

    raw = json.loads(cookie_file.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "cookies" in raw:
        raw = raw["cookies"]

    if not isinstance(raw, list):
        raise ValueError("Cookie 文件格式错误，期望数组或包含 cookies 字段")

    pairs: list[str] = []
    for item in raw:
        name = item.get("name")
        value = item.get("value")
        if name and value is not None:
            pairs.append(f"{name}={value}")

    if not pairs:
        raise ValueError("Cookie 文件中未找到有效 cookie")
    return "; ".join(pairs)


def build_headers(cookie_header: str, user_agent: str) -> dict[str, str]:
    return {
        "User-Agent": user_agent,
        "Accept": "application/json, text/plain, */*",
        "Cookie": cookie_header,
        "Referer": "https://xueqiu.com/",
    }


def validate_auth(base_url: str, headers: dict[str, str], timeout_sec: int) -> None:
    url = f"{base_url}/home"
    with httpx.Client(timeout=timeout_sec, follow_redirects=True, headers=headers) as client:
        resp = client.get(url)

    if resp.status_code != 200:
        raise RuntimeError(f"登录态校验失败，状态码: {resp.status_code}")

    text = resp.text.lower()
    if "login" in text and "xueqiu" in text:
        raise RuntimeError("登录态疑似失效，页面包含登录提示")
