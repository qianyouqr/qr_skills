"""
api_client.py -- quant-buddy API 健康检查 HTTP 客户端

对配置中的每个端点发送探测请求，记录状态/耗时/响应片段。
判定规则：
  HTTP 2xx            -> PASS
  HTTP 非2xx / 网络异常 -> FAIL

提供 --probe CLI 入口做最简单的版本检查验活。
"""
from __future__ import annotations

import io
import json
import logging
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SKILL_ROOT = Path(__file__).resolve().parent.parent

_NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

SNIPPET_MAX = 500


class ApiKeyMissingError(RuntimeError):
    """api_key 未配置"""


class CheckError(RuntimeError):
    """检查过程中的其他错误"""


def load_config() -> dict:
    base_path = SKILL_ROOT / "config" / "config.example.json"
    local_path = SKILL_ROOT / "config" / "config.local.json"

    with open(base_path, encoding="utf-8") as f:
        cfg: dict = json.load(f)

    if local_path.exists():
        with open(local_path, encoding="utf-8") as f:
            local: dict = json.load(f)
        deep_keys = ("email", "voice_call")
        for sub_key in deep_keys:
            if sub_key in local and sub_key in cfg:
                cfg[sub_key].update(local[sub_key])
        local_copy = {k: v for k, v in local.items() if k not in deep_keys}
        cfg.update(local_copy)
    else:
        logger.warning("config.local.json not found -- api_key will be missing")

    return cfg


class HealthCheckClient:

    def __init__(
        self,
        base_url: str,
        api_key: str,
        skill_version: str = "4.21.1",
        skill_channel: str = "",
        timeout: int = 30,
    ) -> None:
        if not api_key:
            raise ApiKeyMissingError(
                "api_key 未配置，请在 config/config.local.json 中填写"
            )
        self._base = base_url.rstrip("/")
        self._api_key = api_key
        self._version = skill_version
        self._channel = skill_channel
        self._timeout = timeout

    def _build_headers(self, method: str) -> dict[str, str]:
        headers: dict[str, str] = {
            "Authorization": f"Bearer {self._api_key}",
            "x-skill-version": self._version,
        }
        if self._channel:
            headers["x-skill-channel"] = self._channel
        if method == "POST":
            headers["Content-Type"] = "application/json; charset=utf-8"
        return headers

    def check_endpoint(self, ep: dict[str, Any]) -> dict[str, Any]:
        name = ep["name"]
        method = ep.get("method", "POST").upper()
        path = ep["path"]
        payload = ep.get("payload")

        url = f"{self._base}{path}"
        headers = self._build_headers(method)
        if ep.get("stream", False):
            headers["Accept"] = "text/event-stream"

        result: dict[str, Any] = {
            "name": name,
            "url": url,
            "method": method,
            "status": "FAIL",
            "http_code": None,
            "response_time_ms": None,
            "response_snippet": None,
            "error_message": None,
        }

        data = None
        if method == "POST" and payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        timeout = ep.get("timeout", self._timeout)
        is_stream = ep.get("stream", False)

        t0 = time.monotonic()
        try:
            with _NO_PROXY_OPENER.open(req, timeout=timeout) as resp:
                elapsed_ms = round((time.monotonic() - t0) * 1000)
                if is_stream:
                    chunk = resp.read(4096)
                    body = chunk.decode("utf-8", errors="replace")
                else:
                    body = resp.read().decode("utf-8")
                result["http_code"] = resp.status
                result["response_time_ms"] = elapsed_ms
                result["response_snippet"] = body[:SNIPPET_MAX]
                result["status"] = "PASS"

                expect_code = ep.get("expect_code")
                if expect_code is not None:
                    try:
                        body_json = json.loads(body)
                        actual_code = body_json.get("code")
                        if actual_code != expect_code:
                            result["status"] = "FAIL"
                            result["error_message"] = body_json.get(
                                "message", f"code={actual_code}, expected {expect_code}"
                            )
                    except (json.JSONDecodeError, KeyError):
                        result["status"] = "FAIL"
                        result["error_message"] = "无法解析响应体 JSON"

        except urllib.error.HTTPError as exc:
            elapsed_ms = round((time.monotonic() - t0) * 1000)
            result["http_code"] = exc.code
            result["response_time_ms"] = elapsed_ms
            result["error_message"] = f"HTTP {exc.code}: {exc.reason}"
            try:
                result["response_snippet"] = exc.read().decode("utf-8")[:SNIPPET_MAX]
            except Exception:
                pass

        except urllib.error.URLError as exc:
            elapsed_ms = round((time.monotonic() - t0) * 1000)
            result["response_time_ms"] = elapsed_ms
            result["error_message"] = f"URLError: {exc.reason}"

        except TimeoutError:
            elapsed_ms = round((time.monotonic() - t0) * 1000)
            result["response_time_ms"] = elapsed_ms
            result["error_message"] = f"Timeout after {self._timeout}s"

        except Exception as exc:
            elapsed_ms = round((time.monotonic() - t0) * 1000)
            result["response_time_ms"] = elapsed_ms
            result["error_message"] = f"{type(exc).__name__}: {exc}"

        return result

    def check_all(self, endpoints: list[dict]) -> list[dict]:
        results = []
        for ep in endpoints:
            try:
                r = self.check_endpoint(ep)
            except Exception as exc:
                r = {
                    "name": ep.get("name", "unknown"),
                    "url": f"{self._base}{ep.get('path', '')}",
                    "method": ep.get("method", "?"),
                    "status": "FAIL",
                    "http_code": None,
                    "response_time_ms": None,
                    "response_snippet": None,
                    "error_message": f"Unexpected: {type(exc).__name__}: {exc}",
                }
            results.append(r)
        return results

    def probe(self) -> dict:
        ep = {
            "name": "probe",
            "method": "GET",
            "path": "/skill/version/check",
            "payload": None,
        }
        r = self.check_endpoint(ep)
        return {"ok": r["status"] == "PASS", "detail": r}


def _cli_probe() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    cfg = load_config()
    api_key = cfg.get("api_key", "")
    base_url = cfg.get("base_url", "")
    client = HealthCheckClient(
        base_url=base_url,
        api_key=api_key,
        skill_version=cfg.get("skill_version", "4.21.1"),
        skill_channel=cfg.get("skill_channel", ""),
        timeout=cfg.get("check", {}).get("timeout_sec", 30),
    )
    try:
        result = client.probe()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["ok"] else 1)
    except ApiKeyMissingError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    if "--probe" in sys.argv:
        _cli_probe()
    else:
        print("Usage: python api_client.py --probe", file=sys.stderr)
        sys.exit(1)
