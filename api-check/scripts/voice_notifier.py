"""
voice_notifier.py -- 阿里云语音电话告警

接口异常时拨打电话通知。使用阿里云 V2.0 SDK (alibabacloud-dyvmsapi20170525)。
需在阿里云控制台开通语音服务、创建 TTS 模板、配置显示号码。

CLI: python voice_notifier.py --test   (拨打测试电话验证配置)
"""
from __future__ import annotations

import io
import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

SKILL_ROOT = Path(__file__).resolve().parent.parent

try:
    from alibabacloud_dyvmsapi20170525.client import Client as DyvmsClient
    from alibabacloud_dyvmsapi20170525 import models as dyvmsapi_models
    from alibabacloud_tea_openapi import models as open_api_models
    HAS_VOICE_SDK = True
except ImportError:
    HAS_VOICE_SDK = False


def _load_voice_config() -> dict:
    base_path = SKILL_ROOT / "config" / "config.example.json"
    local_path = SKILL_ROOT / "config" / "config.local.json"

    with open(base_path, encoding="utf-8") as f:
        cfg = json.load(f)

    voice_cfg = dict(cfg.get("voice_call", {}))

    if local_path.exists():
        with open(local_path, encoding="utf-8") as f:
            local = json.load(f)
        voice_cfg.update(local.get("voice_call", {}))

    return voice_cfg


def send_voice_alert(
    voice_cfg: dict,
    failed_endpoints: list[dict],
    summary: str = "",
) -> bool:
    if not voice_cfg.get("enabled", False):
        logger.info("语音告警未启用 (enabled=false)")
        return False

    if not HAS_VOICE_SDK:
        logger.warning("alibabacloud-dyvmsapi20170525 未安装，跳过语音告警。"
                        "请执行: pip install alibabacloud-dyvmsapi20170525")
        return False

    ak_id = voice_cfg.get("access_key_id", "")
    ak_secret = voice_cfg.get("access_key_secret", "")
    if not ak_id or not ak_secret:
        logger.warning("access_key_id 或 access_key_secret 为空，跳过语音告警")
        return False

    tts_code = voice_cfg.get("tts_code", "")
    if not tts_code:
        logger.warning("tts_code 为空，跳过语音告警")
        return False

    called_number = voice_cfg.get("called_number", "")
    if not called_number:
        logger.warning("called_number 为空，跳过语音告警")
        return False

    called_show_number = voice_cfg.get("called_show_number", "")
    endpoint = voice_cfg.get("endpoint", "dyvmsapi.aliyuncs.com")

    ep_names = ", ".join(ep.get("name", "?") for ep in failed_endpoints[:3])
    tts_param = json.dumps({
        "fail_count": str(len(failed_endpoints)),
        "endpoints": ep_names,
    }, ensure_ascii=False)

    try:
        config = open_api_models.Config(
            access_key_id=ak_id,
            access_key_secret=ak_secret,
        )
        config.endpoint = endpoint
        client = DyvmsClient(config)

        request = dyvmsapi_models.SingleCallByTtsRequest(
            called_number=called_number,
            called_show_number=called_show_number,
            tts_code=tts_code,
            tts_param=tts_param,
        )

        response = client.single_call_by_tts(request)
        body = response.body
        code = getattr(body, "code", None)

        if code == "OK":
            logger.info("语音告警拨打成功: number=%s call_id=%s",
                        called_number, getattr(body, "call_id", "?"))
            return True
        else:
            logger.error("语音告警拨打失败: code=%s message=%s",
                         code, getattr(body, "message", "?"))
            return False

    except Exception as exc:
        logger.error("语音告警异常: %s", exc)
        return False


def _cli_test() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    voice_cfg = _load_voice_config()

    if not voice_cfg.get("enabled", False):
        voice_cfg["enabled"] = True
        print("[TEST] 临时启用 enabled=true 用于测试")

    dummy_failures = [
        {
            "name": "fastQuery",
            "url": "https://www.quantbuddy.cn/skill/fastQuery",
            "status": "FAIL",
            "http_code": 500,
            "response_time_ms": None,
            "error_message": "[TEST] 测试电话，非真实告警",
        }
    ]

    ok = send_voice_alert(voice_cfg, dummy_failures, "测试语音告警")
    if ok:
        print("TEST VOICE_CALL: true")
        sys.exit(0)
    else:
        print("TEST VOICE_CALL: false (检查 config.local.json 中的 voice_call 配置)")
        sys.exit(1)


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    if "--test" in sys.argv:
        _cli_test()
    else:
        print("Usage: python voice_notifier.py --test", file=sys.stderr)
        sys.exit(1)
