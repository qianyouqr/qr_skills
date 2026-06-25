"""
email_notifier.py -- 163 邮箱 SMTP 告警邮件发送

仅在有接口异常时调用。使用 Python stdlib smtplib，零外部依赖。
163 邮箱需开启 IMAP/SMTP 服务后获取授权码作为 smtp_password。

CLI: python email_notifier.py --test   (发送测试邮件验证 SMTP 配置)
"""
from __future__ import annotations

import io
import json
import logging
import smtplib
import ssl
import sys
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from pathlib import Path

logger = logging.getLogger(__name__)

SKILL_ROOT = Path(__file__).resolve().parent.parent

TZ_CN = timezone(timedelta(hours=8))


def _load_email_config() -> dict:
    base_path = SKILL_ROOT / "config" / "config.example.json"
    local_path = SKILL_ROOT / "config" / "config.local.json"

    with open(base_path, encoding="utf-8") as f:
        cfg = json.load(f)

    email_cfg = dict(cfg.get("email", {}))

    if local_path.exists():
        with open(local_path, encoding="utf-8") as f:
            local = json.load(f)
        email_cfg.update(local.get("email", {}))

    return email_cfg


def send_alert_email(
    email_cfg: dict,
    failed_endpoints: list[dict],
    report_summary: str = "",
) -> bool:
    smtp_server = email_cfg.get("smtp_server", "smtp.163.com")
    smtp_port = email_cfg.get("smtp_port", 465)
    use_ssl = email_cfg.get("use_ssl", True)
    sender = email_cfg.get("sender_email", "")
    password = email_cfg.get("smtp_password", "")
    recipients = email_cfg.get("recipient_emails", [])
    subject_prefix = email_cfg.get("subject_prefix", "[API健康检查]")

    if not sender or not password:
        logger.warning("邮箱配置不完整（sender_email 或 smtp_password 为空），跳过发送")
        return False
    if not recipients:
        logger.warning("recipient_emails 为空，跳过发送")
        return False

    now_str = datetime.now(TZ_CN).strftime("%Y-%m-%d %H:%M")
    fail_count = len(failed_endpoints)
    subject = f"{subject_prefix} {fail_count}个接口异常 - {now_str}"

    lines = [
        f"API 健康检查告警",
        f"检查时间: {now_str} (UTC+8)",
        f"异常接口数: {fail_count}",
        "",
        "=" * 50,
    ]
    for ep in failed_endpoints:
        lines.append(f"接口: {ep.get('name', '?')}")
        lines.append(f"  URL: {ep.get('url', '?')}")
        lines.append(f"  状态: {ep.get('status', '?')}")
        lines.append(f"  HTTP: {ep.get('http_code', 'N/A')}")
        lines.append(f"  耗时: {ep.get('response_time_ms', 'N/A')} ms")
        lines.append(f"  错误: {ep.get('error_message', 'N/A')}")
        snippet = ep.get("response_snippet", "")
        if snippet:
            lines.append(f"  响应片段: {snippet[:200]}")
        lines.append("-" * 50)

    if report_summary:
        lines.append("")
        lines.append("完整报告摘要:")
        lines.append(report_summary[:500])

    lines.append("")
    lines.append("--")
    lines.append("此邮件由 api-check skill 自动发送，请勿直接回复。")

    body = "\n".join(lines)

    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = ", ".join(recipients)

        context = ssl.create_default_context()

        if use_ssl:
            with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
                server.login(sender, password)
                server.sendmail(sender, recipients, msg.as_string())
        else:
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls(context=context)
                server.login(sender, password)
                server.sendmail(sender, recipients, msg.as_string())

        logger.info("告警邮件发送成功: recipients=%s", recipients)
        return True

    except Exception as exc:
        logger.error("邮件发送失败: %s", exc)
        return False


def _cli_test() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    email_cfg = _load_email_config()

    dummy_failures = [
        {
            "name": "fastQuery",
            "url": "https://www.quantbuddy.cn/skill/fastQuery",
            "status": "FAIL",
            "http_code": 500,
            "response_time_ms": None,
            "error_message": "[TEST] 这是一封测试邮件，非真实告警",
            "response_snippet": '{"error": "test"}',
        }
    ]

    ok = send_alert_email(email_cfg, dummy_failures, "这是一封测试邮件。")
    if ok:
        print("TEST EMAIL_SENT: true")
        sys.exit(0)
    else:
        print("TEST EMAIL_SENT: false (检查 config.local.json 中的邮箱配置)")
        sys.exit(1)


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    if "--test" in sys.argv:
        _cli_test()
    else:
        print("Usage: python email_notifier.py --test", file=sys.stderr)
        sys.exit(1)
