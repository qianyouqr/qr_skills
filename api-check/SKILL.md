---
name: api-check
description: >
  检查 quant-buddy 后端 8 个核心 API 接口的健康状态（fastQuery、searchFunctions、
  searchSimilarCases、confirmDataMulti、stockProfile、version/check、indicatorCheck、runMultiFormulaBatchStream），
  生成结构化健康报告通过飞书智能体交付；若有接口异常，通过 163 邮箱发送告警邮件，
  并可选通过阿里云语音服务拨打电话告警。
  本 skill 挂载在 api-check 专用 agent 上，支持手动 @ 触发和可选 cron 定时触发；主 agent 请勿加载。
  API 端点：https://www.quantbuddy.cn/skill（与 quant-buddy-skill 共用后端）。
  触发词：API健康检查、接口检查、健康检测、API巡检、api check、health check、endpoint check、接口状态。
metadata:
  only_for_agent: "api-check"
  supports_cron: true
---

# api-check — API 健康巡检 Skill

本 skill 定期对 quant-buddy 后端 8 个核心接口发送探测请求，
判断接口是否正常返回数据，生成健康报告 + 飞书卡片摘要。
异常时自动通过 163 邮箱发送告警邮件，并可选拨打电话告警。

> **本 skill 只应由 api-check 专用 agent 加载。用户在群里 @ 要求"立刻检查一下 / 跑一次巡检"时，直接在当前会话按下面 phase 执行，不要调用 cron tool。只有用户明确要求"触发/查看/修改 cron 定时任务"时，才使用 OpenClaw cron。**

> **每次触发都必须完整重新执行 Phase 0+1+2+3，生成新的 run_id 和新的 report 文件。禁止复用本 session 任何先前的 run_id 或检查结果。**

> ⚠️ **飞书渲染防重复（必须遵守）**：
> 1. **执行期间调用工具时不要输出伴随文本**。即 assistant message 中只放 toolCall，不放 text。所有用户可见文本只写在最终回复中。
> 2. **thinking 中禁止写附件关键词和路径** — 详见下方"投递规则"节，那里有完整的禁止清单。这是导致飞书重复的已知根因。

---

## 检查的接口（8 个）

| # | 接口 | 方法 | 路径 | 测试载荷 | 判定方式 | 说明 |
|---|------|------|------|----------|----------|------|
| 1 | fastQuery | POST | /fastQuery | `{"assets":["贵州茅台"],"query_type":"snapshot","fields":["收盘价"]}` | HTTP 2xx | 核心数据通道 |
| 2 | searchFunctions | POST | /searchFunctions | `{"query":"回测","top_k":1}` | HTTP 2xx | 函数检索 |
| 3 | searchSimilarCases | POST | /searchSimilarCases | `{"query":"收盘价排名"}` | HTTP 2xx | 案例模板 |
| 4 | confirmDataMulti | POST | /confirmDataMulti | `{"data_desc":"收盘价"}` | HTTP 2xx | 数据确认 |
| 5 | stockProfile | POST | /stockProfile | `{"asset":"贵州茅台","task_id":"health-check-probe"}` | HTTP 2xx | 个股画像 |
| 6 | version/check | GET | /skill/version/check | 无body | HTTP 2xx | 控制面 |
| 7 | indicatorCheck | GET | /indicatorCheck?is_trading_day=… | 无body | HTTP 2xx **且** `code=0` | 指标数据刷新监控 |
| 8 | runMultiFormulaBatchStream | POST | /runMultiFormulaBatchStream | `{"formulas":["估值分析_比亚迪_PE=...","估值分析_比亚迪_PB=..."]}` | HTTP 2xx | 批量公式流式计算 |

测试载荷均为只读、最小化请求，不产生副作用。
对于流式端点 (stream=true)，仅读取首个数据块确认连接正常，不等待完整响应。
indicatorCheck 与其他接口不同：它不仅检查接口是否存活，还通过响应体 `code` 字段判断数据库中的指标数据是否已刷新到位。

---

## 健康判断逻辑

对每个接口的 HTTP 响应：

| 条件 | 判定 |
|------|------|
| HTTP 2xx（且无 `expect_code` 配置） | **PASS** |
| HTTP 2xx 但配置了 `expect_code`，响应体 `code` 不匹配 | **FAIL**（报告服务端返回的 `message`） |
| HTTP 非 2xx / 网络超时 / 连接异常 | **FAIL** |

> 当前只有 `indicatorCheck` 配置了 `expect_code: 0`，其余接口仅检查 HTTP 状态码。

---

## 路径约定

**`{SKILL_ROOT}`** = 本 SKILL.md 所在目录，即包含 `scripts/`、`config/`、`state/`、`output/` 的那个目录。

当前部署：
```
{SKILL_ROOT} = <workspace>/skills/api-check/
```

**所有命令、文件路径均以 `{SKILL_ROOT}` 为根**。每次执行前，先用 `read` 工具确认 `{SKILL_ROOT}/config/config.local.json` 的 `api_key` 已填写。

---

## 前置检查（每次运行开始必做）

1. 读取 `{SKILL_ROOT}/config/config.local.json`，确认 `api_key` 非空且非占位符。
2. 探活：
   ```bash
   cd {SKILL_ROOT} && python scripts/api_client.py --probe
   ```
   - 返回 `{"ok": true, ...}` → 继续。
   - exit 2（api_key 缺失）→ **立即停止**并输出告警：
     ```
     api-check: api_key 未配置，请在 {SKILL_ROOT}/config/config.local.json 中填写。
     ```

---

## Phase 0 — 判断今天是否为 A 股交易日

在执行探测之前，Agent 必须先判断今天是否为 A 股交易日，结果用于 `indicatorCheck` 端点。

**判断规则（按顺序）：**
1. 周六、周日 → **非交易日**
2. 属于中国法定节假日（春节、国庆、元旦、清明、劳动节、端午、中秋等）的调休/放假日 → **非交易日**
3. 其余工作日 → **交易日**

Agent 根据当前日期自行判断，将结果记为 `IS_TRADING_DAY`（`true` 或 `false`），传入 Phase 1 命令。

---

## Phase 1 — check：探测所有端点

```bash
cd {SKILL_ROOT} && python scripts/run_check.py --phase check --is-trading-day <IS_TRADING_DAY>
```

> `<IS_TRADING_DAY>` 替换为 Phase 0 得到的 `true` 或 `false`。该参数会作为 `is_trading_day` query param 传递给 `indicatorCheck` 端点。

- 逐个请求 8 个端点，记录状态/耗时/响应片段。
- 成功后 stdout 输出 `run_id=<ID>  endpoints=8  passed=N  failed=M`，记住 run_id。
- 产物：`{SKILL_ROOT}/state/runs/<runId>/check_results.json`

> 遇到 exit code 2（api_key 缺失），停止后续步骤，直接输出告警。

> **exec 跟进规则（防止 context 膨胀导致 LLM idle timeout）**
> 1. 若 exec 返回 `"Command still running"`，调用一次 `process poll`（`timeout: 120000`）等待完成。
> 2. 当 poll 返回结果中出现 `exitCode`（0 或非 0）时，命令已结束——**直接使用 `details.aggregated` 作为 stdout 内容**，不要再调 `process log`。

---

## Phase 2 — report：生成健康报告

```bash
cd {SKILL_ROOT} && python scripts/run_check.py --phase report
```

本 phase 完成两件事：

### 1. 生成 markdown 健康报告

写入 `{SKILL_ROOT}/output/reports/YYYY-MM-DD_HHMM_health.md`：
概览统计 + 各端点状态表格 + 失败/待判断详情。

### 2. 输出摘要到 stdout

stdout = 概览 + 状态列表 + 末尾两行：
- `REPORT_FILE: <绝对路径>`
- `HAS_FAILURES: true/false`

---

## Phase 3 — alert（Agent 条件触发）

Agent 读取 Phase 2 stdout 后判断：

- **如果 `HAS_FAILURES: true`**：
  1. Agent 格式化飞书回复，包含异常端点详情。
  2. Agent 执行告警：
     ```bash
     cd {SKILL_ROOT} && python scripts/run_check.py --phase alert
     ```
  3. stdout 返回：
     - `EMAIL_SENT: true/false  recipients: [...]`
     - `VOICE_CALL: true/false  number: 178xxxxxxxx`（仅当 voice_call.enabled=true）
  4. 若 `EMAIL_SENT: false`（邮箱未配置），在回复中提示用户配置邮箱。
  5. 若 `VOICE_CALL: false`（语音未配置/SDK未安装），在回复中提示用户配置。

- **如果全部正常（`HAS_FAILURES: false`）**：
  1. Agent 回复简短健康摘要，无需告警。

---

## 投递规则（飞书）

- Phase 2 stdout 末尾为 `REPORT_FILE: <绝对路径>`，**不是 `MEDIA:`**。
- Agent **最终回复** = 格式化摘要正文 + 最后一行 `MEDIA: <REPORT_FILE的绝对路径>`。
- **`MEDIA:` 必须只出现一次，并且只出现在最终 text 回复的最后一行。**
- 最终 text 中不要出现 `REPORT_FILE:`；只把 Phase 2 的 `REPORT_FILE:` 前缀替换成唯一的 `MEDIA:`。
- **同一 session 内若有第二次触发，必须重新完整跑 Phase 1+2+3。**
- 不要使用 Feishu `message` / `send` 工具发送摘要正文。
- Feishu 投递层会把 assistant message 中的 `thinking` block 也纳入附件扫描。**生成最终回复时，thinking / 推理 / 草稿中绝对禁止出现以下内容**：
  - 字面字符串 `MEDIA:`（即使在反引号或引号内也不行）
  - 完整的 report 文件路径（如 `/root/...` 或 `C:\Users\...`）
  - 字面字符串 `REPORT_FILE:`
  - 如需核对报告路径，最多写"使用 Phase 2 的报告路径作为附件"，**不要写出实际路径**。
  - 违反此规则会导致飞书卡片内容重复 + 附件发两份。

---

## 语音告警配置

使用阿里云语音服务（Dyvmsapi）在接口故障时拨打电话告警。

### 前置条件

1. 安装 SDK：`pip install alibabacloud-dyvmsapi20170525`
2. 阿里云控制台开通「语音服务」
3. 创建 TTS 模板（如："API监控告警，${fail_count}个接口异常：${endpoints}"），获取 TtsCode
4. 配置显示号码（CalledShowNumber）
5. 将 access_key_id、access_key_secret、tts_code 填入 `config/config.local.json` 的 `voice_call` 节

### 启用

在 `config/config.example.json` 或 `config.local.json` 中设置 `voice_call.enabled: true`。

### 降级行为

- SDK 未安装：跳过语音告警，不影响邮件告警和报告
- 配置不完整：打印 `VOICE_CALL: false`，Agent 提示用户配置

---

## 错误处理

| 情况 | 处理方式 |
| --- | --- |
| api_key 缺失（exit 2） | 立即停止，输出告警，不更新 state |
| 脚本异常（exit 1） | 停止，记录到 stderr，不更新 state |
| check_results.json 不存在 | report/alert phase 报 FileNotFoundError（exit 1），请先执行 check phase |
| 所有端点正常 | 正常生成报告，回复"全部正常"，不发邮件不打电话 |
| 邮箱配置不完整 | alert phase 打印 `EMAIL_SENT: false`，Agent 在回复中提示用户配置 |
| 语音配置不完整或 SDK 未安装 | alert phase 打印 `VOICE_CALL: false`，Agent 在回复中提示用户配置 |

---

## 调试命令

```bash
cd {SKILL_ROOT}

# 健康探活
python scripts/api_client.py --probe

# dry-run（不写文件、不发邮件、不打电话）
python scripts/run_check.py --phase check --dry-run
python scripts/run_check.py --phase report --dry-run
python scripts/run_check.py --phase alert --dry-run

# 用已有 run 重跑 report
python scripts/run_check.py --phase report --run-id <ID>

# 测试邮件发送
python scripts/email_notifier.py --test

# 测试语音电话（需先配置 voice_call）
python scripts/voice_notifier.py --test
```

---

## 文件速查

所有路径以 `{SKILL_ROOT}` 为根：

| 文件 | 说明 |
| --- | --- |
| `config/config.local.json` | api_key + 邮箱授权码（**不 git 追踪**，需手动填写） |
| `config/config.example.json` | 完整配置（端点列表、邮箱服务器、超时等） |
| `state/last_run.json` | 上次运行的 run_id |
| `state/runs/<runId>/check_results.json` | 检查结果原始数据（check phase 产物） |
| `output/reports/*_health.md` | 健康报告（report phase 产物，由最终回复末尾唯一的 `MEDIA:` 行投递） |
| `scripts/api_client.py` | HTTP 客户端（含 `--probe`） |
| `scripts/email_notifier.py` | 163 SMTP 邮件发送（含 `--test`） |
| `scripts/voice_notifier.py` | 阿里云语音电话告警（含 `--test`），需 `pip install alibabacloud-dyvmsapi20170525` |
| `scripts/run_check.py` | 三 Phase 编排器 |
