from __future__ import annotations

from typing import Any

import httpx
import time


class XueqiuClient:
    def __init__(
        self,
        base_url: str,
        headers: dict[str, str],
        timeout_sec: int,
        retry_times: int,
        backoff_base_sec: float,
    ):
        self.base_url = base_url
        self.client = httpx.Client(base_url=base_url, headers=headers, timeout=timeout_sec)
        self.retry_times = retry_times
        self.backoff_base_sec = backoff_base_sec

    def close(self) -> None:
        self.client.close()

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(1, self.retry_times + 1):
            try:
                resp = self.client.get(path, params=params)
                if resp.status_code >= 500 or resp.status_code == 429:
                    raise RuntimeError(f"接口临时不可用: {resp.status_code}")
                if resp.status_code != 200:
                    raise RuntimeError(f"接口请求失败: {resp.status_code}, body={resp.text[:200]}")
                data = resp.json()
                if not isinstance(data, dict):
                    raise RuntimeError("接口返回非对象 JSON")
                return data
            except Exception as exc:
                last_exc = exc
                if attempt >= self.retry_times:
                    break
                sleep_sec = self.backoff_base_sec * (2 ** (attempt - 1))
                time.sleep(min(8.0, sleep_sec))
        assert last_exc is not None
        raise last_exc
