"""
run_check.py -- API 健康检查三 Phase 编排器

Usage:
  python run_check.py --phase check  [--dry-run]
  python run_check.py --phase report [--run-id ID] [--no-state] [--dry-run]
  python run_check.py --phase alert  [--run-id ID] [--dry-run]

Phase 说明:
  check  : 探测所有配置端点，记录结果
  report : 读取检查结果，生成 markdown 报告
  alert  : 对失败端点发送邮件告警
"""
from __future__ import annotations

import argparse
import io
import json
import logging
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from api_client import load_config, ApiKeyMissingError, HealthCheckClient
from email_notifier import send_alert_email
from voice_notifier import send_voice_alert

logger = logging.getLogger(__name__)

SKILL_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = SKILL_ROOT / "state"
RUNS_DIR = STATE_DIR / "runs"
OUTPUT_DIR = SKILL_ROOT / "output" / "reports"
LAST_RUN_FILE = STATE_DIR / "last_run.json"

TZ_CN = timezone(timedelta(hours=8))


def _load_state() -> dict:
    if LAST_RUN_FILE.exists():
        with open(LAST_RUN_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"last_run_id": None}


def _save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(LAST_RUN_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _resolve_run_id(args) -> str:
    if args.run_id:
        return args.run_id
    state = _load_state()
    rid = state.get("last_run_id")
    if not rid:
        print("[ERROR] 没有找到上次运行记录，请先执行 --phase check 或用 --run-id 指定", file=sys.stderr)
        sys.exit(1)
    return rid


def _load_results(run_id: str) -> dict:
    result_path = RUNS_DIR / run_id / "check_results.json"
    if not result_path.exists():
        print(f"[ERROR] {result_path} 不存在，请先执行 --phase check", file=sys.stderr)
        sys.exit(1)
    with open(result_path, encoding="utf-8") as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════════
# Phase 1 -- check
# ═══════════════════════════════════════════════════════════════════

def phase_check(args) -> None:
    cfg = load_config()
    run_id = uuid.uuid4().hex[:8]
    now = datetime.now(TZ_CN)

    endpoints = cfg.get("check", {}).get("endpoints", [])
    if not endpoints:
        print("[ERROR] config 中未配置 check.endpoints", file=sys.stderr)
        sys.exit(1)

    client = HealthCheckClient(
        base_url=cfg.get("base_url", ""),
        api_key=cfg.get("api_key", ""),
        skill_version=cfg.get("skill_version", "4.21.1"),
        skill_channel=cfg.get("skill_channel", ""),
        timeout=cfg.get("check", {}).get("timeout_sec", 30),
    )

    results = client.check_all(endpoints)

    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")

    data = {
        "run_id": run_id,
        "checked_at": now.isoformat(),
        "endpoints_total": len(results),
        "passed": passed,
        "failed": failed,
        "results": results,
    }

    if not args.dry_run:
        run_dir = RUNS_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        with open(run_dir / "check_results.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        state = _load_state()
        state["last_run_id"] = run_id
        _save_state(state)

    print(f"run_id={run_id}  endpoints={len(results)}  passed={passed}  failed={failed}")


# ═══════════════════════════════════════════════════════════════════
# Phase 2 -- report
# ═══════════════════════════════════════════════════════════════════

def phase_report(args) -> None:
    run_id = _resolve_run_id(args)
    data = _load_results(run_id)

    results = data["results"]
    total = data["endpoints_total"]
    passed = data["passed"]
    failed = data["failed"]
    checked_at = data["checked_at"]

    has_failures = failed > 0

    md_lines = []
    md_lines.append("# API 健康检查报告")
    md_lines.append(f"> 检查时间: {checked_at} | 检查接口: {total} | 通过: {passed} | 失败: {failed}")
    md_lines.append("")
    md_lines.append("| 接口 | 状态 | 耗时(ms) | HTTP | 备注 |")
    md_lines.append("|------|------|----------|------|------|")

    for r in results:
        time_str = str(r["response_time_ms"]) if r["response_time_ms"] is not None else "-"
        http_str = str(r["http_code"]) if r["http_code"] is not None else "-"
        note = r.get("error_message") or ""
        md_lines.append(f"| {r['name']} | {r['status']} | {time_str} | {http_str} | {note} |")

    fail_list = [r for r in results if r["status"] == "FAIL"]

    if fail_list:
        md_lines.append("")
        md_lines.append("## 失败详情")
        for r in fail_list:
            md_lines.append(f"### {r['name']}")
            md_lines.append(f"- URL: {r['url']}")
            md_lines.append(f"- HTTP状态: {r.get('http_code', 'N/A')}")
            md_lines.append(f"- 耗时: {r.get('response_time_ms', 'N/A')} ms")
            md_lines.append(f"- 错误: {r.get('error_message', 'N/A')}")
            snippet = r.get("response_snippet", "")
            if snippet:
                md_lines.append(f"- 响应片段: ```{snippet[:300]}```")
            md_lines.append("")

    md_content = "\n".join(md_lines)

    # 写文件
    now = datetime.now(TZ_CN)
    filename = now.strftime("%Y-%m-%d_%H%M") + "_health.md"

    if not args.dry_run:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        report_path = OUTPUT_DIR / filename
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(md_content)
    else:
        report_path = OUTPUT_DIR / filename

    # stdout 输出（给 Agent 解析）
    announce_lines = []
    if has_failures:
        announce_lines.append(f"API 健康检查: {failed}/{total} 个接口异常")
    else:
        announce_lines.append(f"API 健康检查: 全部 {total} 个接口正常")

    announce_lines.append("")
    announce_lines.append(f"检查时间: {checked_at}")
    announce_lines.append(f"通过: {passed} | 失败: {failed}")
    announce_lines.append("")

    for r in results:
        icon = {"PASS": "[OK]", "FAIL": "[FAIL]"}[r["status"]]
        time_str = f"{r['response_time_ms']}ms" if r["response_time_ms"] is not None else "-"
        announce_lines.append(f"  {icon} {r['name']}  {time_str}  {r.get('error_message', '')}")

    if fail_list:
        announce_lines.append("")
        announce_lines.append("失败端点:")
        for r in fail_list:
            announce_lines.append(f"  - {r['name']}: {r.get('error_message', 'unknown')}")

    announce_lines.append("")
    announce_lines.append(f"REPORT_FILE: {report_path.resolve()}")
    announce_lines.append(f"HAS_FAILURES: {'true' if has_failures else 'false'}")

    print("\n".join(announce_lines))


# ═══════════════════════════════════════════════════════════════════
# Phase 3 -- alert
# ═══════════════════════════════════════════════════════════════════

def phase_alert(args) -> None:
    run_id = _resolve_run_id(args)
    data = _load_results(run_id)
    cfg = load_config()

    fail_list = [r for r in data["results"] if r["status"] == "FAIL"]

    if not fail_list:
        print("No failures, skip alerts.")
        return

    summary = f"检查时间: {data['checked_at']}, 失败: {len(fail_list)}/{data['endpoints_total']}"

    # 邮件告警
    email_cfg = cfg.get("email", {})
    if args.dry_run:
        print(f"[DRY-RUN] Would send email for {len(fail_list)} failed endpoints")
        email_ok = False
    else:
        email_ok = send_alert_email(email_cfg, fail_list, summary)
    recipients = email_cfg.get("recipient_emails", [])
    print(f"EMAIL_SENT: {'true' if email_ok else 'false'}  recipients: {recipients}")

    # 语音电话告警
    voice_cfg = cfg.get("voice_call", {})
    if voice_cfg.get("enabled", False):
        if args.dry_run:
            print(f"[DRY-RUN] Would make voice call to {voice_cfg.get('called_number')}")
            voice_ok = False
        else:
            voice_ok = send_voice_alert(voice_cfg, fail_list, summary)
        print(f"VOICE_CALL: {'true' if voice_ok else 'false'}  number: {voice_cfg.get('called_number', 'N/A')}")


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════

def _main() -> None:
    parser = argparse.ArgumentParser(description="API 健康检查编排器")
    parser.add_argument("--phase", required=True, choices=["check", "report", "alert"])
    parser.add_argument("--run-id", default=None, help="指定 run_id（report/alert phase）")
    parser.add_argument("--dry-run", action="store_true", help="不写文件、不发邮件")
    parser.add_argument("--no-state", action="store_true", help="不更新 last_run.json")
    args = parser.parse_args()

    try:
        if args.phase == "check":
            phase_check(args)
        elif args.phase == "report":
            phase_report(args)
        elif args.phase == "alert":
            phase_alert(args)
    except ApiKeyMissingError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(2)
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"[ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    _main()
