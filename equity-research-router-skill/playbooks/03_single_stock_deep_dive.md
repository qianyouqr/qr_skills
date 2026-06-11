# Playbook 03 — 个股深度分析与操作策略

> 触发：单只 A 股 / 港股 / 美股，要求"分析 / 走势 / 基本面 / 操作建议 / 持有 / 低吸 / 业绩拐点 / 今日走势"等。
> **唯一数据入口：`stockProfile`**（1 次调用）。本 playbook 全程不调用 `fast_query` / `fast-snapshot` / `fast-window` / `fast-report-period` / `period-return-compare` / `quant-standard` 等任何其他工具。

---

## 1. 资产识别（先做，必须）

1. 用户给的可能是**代码、中文名、英文名、口语化名称**（例："腾讯 700.HK"、"002594"、"闪迪"、"鸿腾精密"、"豪威集团"）。
2. 在 `quant-buddy-skill/presets/assets_db/{stock_a|stock_hk|stock_us}.yaml` 里 **grep**，拿到正式 ticker。
3. **歧义必须澄清**：同名两家 A 股公司、或港美股代码不确定时，先问一句再继续。

## 1b. 分析深度默认规则（优先于反问）

| 用户说的 | 默认行为 | 是否反问 |
|---------|---------|--------|
| 详细分析 / 深度分析 / 全面分析 / 综合分析 / 分析一下 / 看看 / 怎么样 / 只给代码 | 综合版（§4 完整骨架） | ❌ 不问 |
| 走势 / 技术面 / 近期走势 / 今天 / 今日走势 | 综合版（stockProfile 取走势+估值+资金，联网取当日新闻） | ❌ 不问 |
| 基本面 / 财报 / 业务 / 业绩 | 综合版（侧重 §4 二、财务分析节） | ❌ 不问 |
| 操作建议 / 低吸 / 建仓 / 持有吗 / 适合买吗 | 综合版 + §4 六、综合观察与定性建议 | ❌ 不问 |
| 只给中文名且 A/H 均有（如"民生银行"） | **默认 A 股**，综合版 | ❌ 不问 |

> **综合版 = 1 次 `stockProfile` + 联网消息面**；禁止追加任何 fast_query 调用。

---

## 2. 唯一数据调用

### 2.0 输出合同锁定（必须先于取数）

在调用 `newSession` / `stockProfile` 之前，先锁定本轮最终答案版式：

1. **必须使用 §4 的 Markdown 表格骨架**：行情与估值、财务分析、资金 / 交易特征、计算维度、波动率与风险都必须是表格或表格 + 简短结论。
2. **必须保留独立章节**：`## 四、计算维度` 与 `## 五、波动率与风险` 分开输出；不得合并成“波动率与趋势结构 / 技术面与波动率 / 资产趋势与计算维度”。
3. **必须先建立填槽骨架**：在写正文前，先固定 `标题 → 时间/来源 → 一～七大节 → 每节表格表头 → 结尾声明`；后续只允许把 `stockProfile` 和联网结果填入槽位，不允许临时改写成聊天摘要或项目符号。
4. **必须先计划计算维度分组**：取到 `stockProfile` 后，先枚举 `data.dimensions` 全部非空维度，把常规模板未覆盖的维度逐个分组；每个维度单独输出小标题、综合分/最终得分、信号和指标表。
5. **群聊只压缩点评，不压缩结构**：飞书群聊可以减少解释句，但不能删除表格、不能改成项目符号、不能删 `---` 分节线。
6. **禁止过程话术外露**：首句必须直接是报告标题 `**{资产名}（{代码}）全面分析**` 与关键数据。禁止在标题前写"我先把 X 拿到手 / 我先按 PowerShell 规范 / 资产命中 SH600010 / 数据已拿到 / 分桶完毕 / 现在按 playbook 03 §4 输出 / byted-web-search skill 未安装 / 先识别 shell / 路径不存在"等。完整黑名单见 `SKILL.md` §1 规则 14。
7. **群聊默认走计算维度简洁模式（Top3 + 总结）**，单聊或显式"详细/完整/全部"走详细模式（见 §3.5）。

**一次写对的生成顺序（强制）**：
1. 先把 §4 输出骨架作为最终答案模板，不写自由文本草稿。
2. 调用 `stockProfile` 后，先做维度分桶：`资产走势 / 估值 / 财务分析 / 资金流向 / 波动率` 进入固定章节，其余非空维度进入 `## 四、计算维度`。
3. 为 `## 四、计算维度` 先生成所有维度小标题：`### {维度名}得分：{score} {信号}`，再在每个小标题下生成该维度自己的指标表。
4. 最后才写每节 1 句点评和综合观察；点评不得改变骨架、不得合并章节。
5. 若工具未返回某槽位，填 `⚫` 或跳过该行；不得因为缺字段把整节改成纯文字说明。

> ⚠️ **调用前必读——3 条强制规则**
> 1. **严禁**通过 `agents_list` 查找"quant-buddy agent"——quant-buddy 工具不是 sub-agent，`agents_list` 走不通。
> 2. **严禁**根据 memory 中历史失败记录预判"quant-buddy 不可用"——每次新会话必须**实际尝试**调用，不得凭历史记忆跳过。
> 3. 优先尝试原生工具；**若当前 session 的工具列表中没有 `newSession`**，立即切到下方 exec 兜底路径——两条路都走不通才输出 §5。

---

### 路径 A：原生工具（若 `newSession` 在工具列表中）

**Step A1：调用 `newSession`**
```json
{ "user_query": "<用户原始问题>" }
```
**Step A2：调用 `stockProfile`**
```json
{ "asset": "<正式代码，如 300571.SZ>", "user_query": "<用户原始问题>" }
```

---

### 路径 B：exec 兜底（`newSession` 不在工具列表时，必须走此路径）

> quant-buddy 工具未注册为本会话原生函数时，按此路径调用 `scripts/call.py`。
> **先识别当前 shell**：Windows / PowerShell 环境禁止使用 `GZQ_PARAMS='...' python ...` 这种 bash 前缀写法；PowerShell 会把 `GZQ_PARAMS=...` 当成命令名执行并报 `not recognized`。PowerShell 必须用 `$env:GZQ_PARAMS = '...'`，且不要把该赋值语句接在 `&&` 后面；用多行脚本或分号分隔。

**Step B1：新建 session**

PowerShell（Windows，当前 OpenClaw 常见环境）：
```powershell
$skillRoot = Join-Path $HOME ".openclaw\workspace\skills\quant-buddy-skill"
if (-not (Test-Path $skillRoot)) { $skillRoot = Join-Path $HOME ".agents\skills\quant-buddy-skill" }
Set-Location $skillRoot
$env:GZQ_PARAMS = '{"user_query": "<用户原始问题>", "user_id": "<sender_id，若存在>"}'
python scripts/call.py newSession 2>&1
```

bash / zsh（Linux/macOS）：
```bash
cd /root/.openclaw/workspace/skills/quant-buddy-skill && GZQ_PARAMS='{"user_query": "<用户原始问题>", "user_id": "<sender_id，若存在>"}' python3 scripts/call.py newSession 2>&1
```

**Step B2：调用 stockProfile**（将 B1 返回的 `task_id` 透传给 B2 不需要，stockProfile 会自动读 session）

PowerShell（Windows，当前 OpenClaw 常见环境）：
```powershell
$skillRoot = Join-Path $HOME ".openclaw\workspace\skills\quant-buddy-skill"
if (-not (Test-Path $skillRoot)) { $skillRoot = Join-Path $HOME ".agents\skills\quant-buddy-skill" }
Set-Location $skillRoot
$env:GZQ_PARAMS = '{"asset": "<正式代码，如 SZ300571>", "user_query": "<用户原始问题>", "user_id": "<sender_id，若存在>"}'
python scripts/call.py stockProfile 2>&1
```

bash / zsh（Linux/macOS）：
```bash
cd /root/.openclaw/workspace/skills/quant-buddy-skill && GZQ_PARAMS='{"asset": "<正式代码，如 SZ300571>", "user_query": "<用户原始问题>", "user_id": "<sender_id，若存在>"}' python3 scripts/call.py stockProfile 2>&1
```

> 若 B1/B2 报 `401` / `api_key 为空`：立即停止，告知用户 quant-buddy API Key 配置失效，需重新配置。

---

| 返回情况 | 处理 |
|---------|------|
| `code:0` 且 `indicators_count > 0` | 进入 §4 输出骨架 |
| `ASSET_NOT_FOUND` / `ASSET_REQUIRED` | §5 失败兜底，不降级跑其他工具 |
| `code:0` 且 `indicators_count = 0` | §5 失败兜底，不降级跑其他工具 |
| 某单个维度为空 | 跳过该大节（加 ⚫ 标注），继续输出其他维度 |
| `api_key 为空` / `code:1` / 401 | 立即停止，提示用户配置 quant-buddy API Key |
| 路径 A + 路径 B 均失败 | §5 失败兜底，说明具体错误 |

**不存在任何补位调用**：本 playbook 不调用 fast_query 或任何其他 quant-buddy workflow。

**联网消息面**（在 stockProfile 调用完成后，用 byted-web-search 检索）：

> ⚠️ **工具强制**：必须加载 `~/.openclaw/workspace/.agents/skills/byted-web-search/SKILL.md`，调用 byted-web-search 执行以下搜索。**禁止**直接使用 `web_fetch` 拉取任何 URL——服务器在中国大陆，Google / Yahoo Finance / Reuters 等境外域名必然失败；上一次任务的 web_fetch 失败不代表 byted-web-search 也会失败，**每次新任务必须重新调用 byted-web-search**，不得因上轮失败直接跳过消息面。

搜索内容（通过 exec 工具执行，`{baseDir}` 为加载 skill 后解析的实际路径）：

- 财报 / 业绩快报 + 重大公告（重组 / 解禁 / 回购 / 增减持）合并一次：
  ```bash
  cd {baseDir} && python3 scripts/web_search.py "{股票名} 财报 业绩 公告" --time-range OneMonth
  ```
- 当日走势相关新闻（仅当用户问今日走势时追加）：
  ```bash
  cd {baseDir} && python3 scripts/web_search.py "{股票名} 最新消息" --time-range OneWeek
  ```

每条引用必须标注来源 + 时点；byted-web-search 返回无实质内容的条目不写，不杜撰。

---

## 3. 字段路径速查

> 取数时直接按以下路径读 `stockProfile` 返回的 `dimensions` 对象。`latest_date` / `unit` 可能在维度层级而非指标层级，先查维度，再查指标自身，取最具体的。

| 大节 | 指标名 | 路径 |
|------|--------|------|
| 最新价 | close_price | `dimensions.资产走势.indicators.close_price.latest_value`（支持日内分钟级刷新） |
| 近 N 日累计涨跌幅 | ret:N | `dimensions.资产走势.indicators.close_price.variants.ret:20/60/120/250.value`（倍数，×100=百分比） |
| PE(TTM) | pe_ttm | `dimensions.估值.indicators.pe_ttm.latest_value` |
| PE 分位 | pctrank | `dimensions.估值.indicators.pe_ttm.variants.pctrank:1Y/3Y/5Y.value`（0~1） |
| PB | pb_ratio | `dimensions.估值.indicators.pb_ratio.latest_value` |
| PS(TTM) | ps_ttm | `dimensions.估值.indicators.ps_ttm.latest_value` |
| 股息率 | dividend_yield | `dimensions.估值.indicators.dividend_yield.latest_value` |
| 收入增速 | fa_revenue_growth | `dimensions.财务分析.indicators.fa_revenue_growth.latest_value` + variants |
| 扣非增速 | fa_non_recurring_profit_growth | `dimensions.财务分析.indicators.fa_non_recurring_profit_growth.latest_value` + variants |
| 毛利率(单季) | fa_gross_margin | `dimensions.财务分析.indicators.fa_gross_margin.latest_value` + variants |
| 净利率(单季) | fa_net_margin | `dimensions.财务分析.indicators.fa_net_margin.latest_value` + variants |
| 营业利润率(单季) | fa_operating_margin | `dimensions.财务分析.indicators.fa_operating_margin.latest_value` + variants |
| ROE(单季) | fa_roe_analysis | `dimensions.财务分析.indicators.fa_roe_analysis.latest_value` + variants |
| ROIC(TTM) | fa_roic_analysis | `dimensions.财务分析.indicators.fa_roic_analysis.latest_value` + variants |
| 经营现金流(单季) | fa_operating_cash_flow | `dimensions.财务分析.indicators.fa_operating_cash_flow.latest_value` + variants |
| 资本开支收入比(TTM) | fa_capex_cash_flow_ratio | `dimensions.财务分析.indicators.fa_capex_cash_flow_ratio.latest_value` + variants |
| 合同负债 | fa_contract_liability | `dimensions.财务分析.indicators.fa_contract_liability` + `previous_value/previous_date` + variants |
| 在建工程 | fa_wip | `dimensions.财务分析.indicators.fa_wip` + `previous_value/previous_date` + variants |
| 成交额占比 | turnover_ratio | `dimensions.资金流向.indicators.turnover_ratio.latest_value` + `variants.trend60.value` + `variants.pctrank:3Y.value` |
| 换手均线 | turnover_ma | `dimensions.资金流向.indicators.turnover_ma.variants.param:5/10/20/60/120/250.value` |
| 做空比例 | short_selling_ratio | `dimensions.资金流向.indicators.short_selling_ratio.latest_value` + `variants.trend60/pctrank:3Y` |
| 基金持仓比例 | fund_holding_ratio | `dimensions.资金流向.indicators.fund_holding_ratio.latest_value` + `variants.trend60/pctrank:3Y` |
| 年化波动率 | annualized_volatility | `dimensions.波动率.indicators.annualized_volatility.latest_value` + variants |
| 标准差 | stddev | `dimensions.波动率.indicators.stddev.latest_value` + variants |

**variant 变体规则**：
- `quarter_yoy` = 单季同比；`quarter_qoq` = 单季环比
- `ttm_level` = TTM 绝对值；`ttm_yoy` = TTM 同比
- `annual_level` = 年度值；`annual_yoy` = 年度同比
- `pctrank:1Y/3Y/5Y` = 1/3/5 年分位（0~1，1=历史最高，0=历史最低）
- `trend60` = 60 日趋势（正=上升，负=下降，近 0=横盘）
- `ret:N` = 近 N 交易日累计涨跌幅（倍数，0.82 → 82%）

**动态维度覆盖规则（强制）**：
- 读完 `stockProfile` 后，先列出 `data.dimensions` 下所有 `indicators` 非空的维度名，形成 `returned_dimensions`。
- 常规模板只负责优先展示：`资产走势` / `估值` / `财务分析` / `资金流向` / `波动率`。
- 对 `returned_dimensions` 中未被常规模板覆盖的维度，以及常规模板维度中未被表格展示的额外指标，必须写入“计算维度”章节。
- “计算维度”章节必须按维度分组输出，禁止把多个维度混在一张大表里。每个返回维度都必须有自己的小标题和自己的指标表。
- 每个维度小标题格式固定为：`### {维度名}得分：{score} {🟢/🟡/🔴/⚫}`。`score` 从该维度内表示综合分/最终得分的指标读取，优先匹配：指标名含 `{维度名}` 且 description 含 `最终得分`；其次匹配指标名含 `综合分` / `最终得分`；都没有则写 `暂无综合分 ⚫`。
- 维度小标题信号口径：`score >= 0.70` 用 🟢，`0.40 <= score < 0.70` 用 🟡，`score < 0.40` 用 🔴，缺失用 ⚫。单个指标也按同一口径给信号；若 description 明确是“不过热/健康/低风险”等 1=好、0=差的指标，也按数值高低给信号。
- 每个维度自己的指标表必须逐指标展示，不得只写“还有其他维度”。每行至少包含：指标、最新值、说明/口径、信号。综合分/最终得分已放在小标题时，可不在表格中重复。
- 若指标很多，允许每个维度表只压缩说明/variants，但不能遗漏维度；确因群聊长度需要压缩时，也必须保留每个维度小标题、综合分、信号和核心指标名。
- 只要有任意未被常规模板覆盖的维度，“计算维度”必须是独立章节，标题必须写成 `## 四、计算维度`，不得写成“波动率与趋势结构 / 技术面与波动率 / 资产趋势与计算维度”等合并标题。
- `## 四、计算维度` 下必须按 `{维度小标题 + Markdown 指标表}` 重复输出，不允许改成项目符号列表，也不允许只输出一张跨维度大表。

### 3.5 计算维度展示模式（详细 / 简洁）

为防止 stockProfile 后续接入 60+ 计算维度时单股报告爆长，定义两种展示模式：

- **详细模式（默认；单聊 / 用户显式说"详细/完整/全部"）**：所有非空维度全部按 §3 规则分组展开。
- **简洁模式（默认；飞书群聊 / Discord / WhatsApp 等多人群聊）**：LLM 在所有非空维度中按规则选 Top 3，顶部加 1 段 ≤120 字的总结。

**简洁模式选维规则**（强制）：
1. 优先按综合分升序（最差信号先出现，给读者风险预警）；score 缺失（`null`/`⚫`）排在有 score 之后。
2. score 相同时，按该维度 `indicators.*.description` 关键词命中数（`信号/风险/质量/趋势/估值/资金/盈利/成长/动量/反转/形态/风控`）降序。
3. 当非空维度数 ≤ 3 时，两模式等价（仍按详细模式展开）。
4. 用户显式"详细/完整/全部/展开维度"→ 立即切回详细模式。

**简洁模式 LLM 任务**：

```
输入：stockProfile 返回的全部非空计算维度，每个维度含
  - name: 维度名
  - score: 综合分（0-1，缺失为 null）
  - indicators: [{ name, description, latest_value }]

任务：
  1. 选 3 个维度（最差 score 优先），按 score 升序输出。
  2. 用 ≤120 字写 1 段总结，包含：
     - 信号分布（X 个 🟢 / Y 个 🟡 / Z 个 🔴）
     - 共性结论（多维度共有的趋势或分歧）
     - 1 个最大风险点（点名具体维度 + 指标）
  3. 每个选中维度只保留 5 个指标，按 description 关键词命中数（信号/风险/质量/趋势/估值/资金/盈利/成长）降序。
  4. 输出格式：3 个 `### {维度名}得分：{score} {🟢/🟡/🔴/⚫}` 小标题 + 各 5 行表 + 1 段总结。
```

**简洁模式输出模板**（替换 §4 中"## 四、计算维度"节的 Markdown 骨架）：

```markdown
## 四、计算维度（简洁模式 · Top3）

> **信号分布**：{N_dim} 个非空维度中 {X}🟢 / {Y}🟡 / {Z}🔴。
> **共性结论**：{≤40 字总结共性趋势或分歧}。
> **最大风险**：{点名具体维度 + 指标 + 1 句风险描述，≤40 字}。

### {维度1名}得分：{score} {信号}

| 指标 | 最新值 | 说明/口径 | 信号 |
|------|--------|-----------|------|
| {indicator1} | {value} | {description} | {信号} |
| {indicator2} | … | … | … |
| {indicator3} | … | … | … |
| {indicator4} | … | … | … |
| {indicator5} | … | … | … |

### {维度2名}得分：{score} {信号}

| 指标 | 最新值 | 说明/口径 | 信号 |
|------|--------|-----------|------|
…（同上 5 行）

### {维度3名}得分：{score} {信号}

| 指标 | 最新值 | 说明/口径 | 信号 |
|------|--------|-----------|------|
…（同上 5 行）
```

未选中的维度在"## 七、综合观察"中以 1 句合并形式提及："另有 {K} 个维度（{维度名列表}）未在 §四 展开，详见详细模式 / 链接到原 JSON"。不强制用户回看。

---

## 4. 输出骨架

> **§7 格式门禁全部保留：中文大节 + `---` + Markdown 表格 + emoji 信号色 + 结尾声明行。**
> **接口未返回的维度整节跳过，标题后加 `⚫ 本轮接口未返回该维度`，不编造数字。**
> **先建骨架再填槽**：下方 markdown 骨架就是最终答案模板；不得先输出自由文本摘要，再在发送前尝试补表格。
> **禁止压缩成列表**：下方所有带 `|` 的表格必须保留 Markdown 表格形态；不得改写为 `指标：数值` 的纯文本列表。
> **禁止合并章节**：`## 四、计算维度` 和 `## 五、波动率与风险` 必须分开；不得输出“波动率与趋势结构”这类合并标题。

````markdown
**{股票名}（{代码}）全面分析**

时间：截至 {data.computed_at 日期} | 数据来源：QB

---

## 一、行情与估值

**最新价**：{close_price}元 | **近20日**：{ret:20×100}% | **近60日**：{ret:60×100}% | **近120日**：{ret:120×100}% | **近250日**：{ret:250×100}%

| 指标 | 最新值 | 1Y 分位 | 3Y 分位 | 5Y 分位 | 信号 |
|------|--------|---------|---------|---------|------|
| PE(TTM) | {pe_ttm}倍 | {pctrank:1Y×100}% | {pctrank:3Y×100}% | {pctrank:5Y×100}% | 🔴/🟡/🟢 |
| PB | {pb_ratio}倍 | {pctrank:1Y×100}% | {pctrank:3Y×100}% | {pctrank:5Y×100}% | 🔴/🟡/🟢 |
| PS(TTM) | {ps_ttm}倍 | {pctrank:1Y×100}% | {pctrank:3Y×100}% | {pctrank:5Y×100}% | 🔴/🟡/🟢 |
| 股息率 | {dividend_yield}% | {pctrank:1Y×100}% | {pctrank:3Y×100}% | {pctrank:5Y×100}% | 🔴/🟡/🟢 |

> 分位接近 100% = 估值历史最高区间 🔴；接近 0% = 历史最低区间 🟢；40%~60% = 中性 🟡。

---

## 二、财务分析

> 最近报告期：{dimensions.财务分析.latest_date}

| 指标 | 单季最新 | 单季YoY | 单季QoQ | TTM | TTM YoY | 年度 | 年度YoY | 信号 |
|------|---------|---------|---------|-----|---------|------|---------|------|
| 收入增速 | {fa_revenue_growth.latest_value}% | {quarter_yoy}% | {quarter_qoq}% | {ttm_level}% | {ttm_yoy}% | {annual_level}% | {annual_yoy}% | 🔴/🟡/🟢 |
| 扣非增速 | {fa_non_recurring_profit_growth.latest_value}% | {quarter_yoy}% | {quarter_qoq}% | {ttm_level}% | {ttm_yoy}% | {annual_level}% | {annual_yoy}% | 🔴/🟡/🟢 |
| 毛利率 | {fa_gross_margin.latest_value}% | {quarter_yoy}% | {quarter_qoq}% | {ttm_level}% | {ttm_yoy}% | {annual_level}% | {annual_yoy}% | 🔴/🟡/🟢 |
| 净利率 | {fa_net_margin.latest_value}% | {quarter_yoy}% | {quarter_qoq}% | {ttm_level}% | {ttm_yoy}% | {annual_level}% | {annual_yoy}% | 🔴/🟡/🟢 |
| 营业利润率 | {fa_operating_margin.latest_value}% | {quarter_yoy}% | {quarter_qoq}% | {ttm_level}% | {ttm_yoy}% | {annual_level}% | {annual_yoy}% | 🔴/🟡/🟢 |
| ROE | {fa_roe_analysis.latest_value}% | {quarter_yoy}% | {quarter_qoq}% | {ttm_level}% | {ttm_yoy}% | {annual_level}% | {annual_yoy}% | 🔴/🟡/🟢 |
| ROIC(TTM) | — | — | — | {fa_roic_analysis.latest_value}% | {ttm_yoy}% | {annual_level}% | {annual_yoy}% | 🔴/🟡/🟢 |
| 经营现金流 | {fa_operating_cash_flow.latest_value} | {quarter_yoy}% | {quarter_qoq}% | {ttm_level} | {ttm_yoy}% | {annual_level} | {annual_yoy}% | 🔴/🟡/🟢 |
| 资本开支/收入(TTM) | — | — | — | {fa_capex_cash_flow_ratio.latest_value}% | {ttm_yoy}% | {annual_level}% | {annual_yoy}% | 🔴/🟡/🟢 |

**资产负债结构**（如有返回）

| 指标 | 最新值 | 上一期值（{previous_date}） | 年度YoY |
|------|--------|--------------------------|---------|
| 合同负债 | {fa_contract_liability.latest_value} | {previous_value} | {annual_yoy}% |
| 在建工程 | {fa_wip.latest_value} | {previous_value} | {annual_yoy}% |

{1–2 句财务定性点评，基于上表趋势，不得超出已取数据范围，标注来源：联网 / 公告}

---

## 三、资金 / 交易特征

| 指标 | 最新值 | 5日均线 | 60日趋势 | 3Y分位 | 信号 |
|------|--------|--------|---------|--------|------|
| 成交额占比 | {turnover_ratio}% | {param:5} | {trend60>0?上升🟢:trend60<0?下降🔴:横盘🟡} | {pctrank:3Y×100}% | 🔴/🟡/🟢 |
| 做空比例 | {short_selling_ratio}% | — | {trend60} | {pctrank:3Y×100}% | 🔴/🟡/🟢 |
| 基金持仓比例 | {fund_holding_ratio}% | — | {trend60} | {pctrank:3Y×100}% | 🔴/🟡/🟢 |

**换手均线多周期对比（turnover_ma）**

| 5日 | 10日 | 20日 | 60日 | 120日 | 250日 |
|-----|------|------|------|-------|-------|
| {param:5} | {param:10} | {param:20} | {param:60} | {param:120} | {param:250} |

{1 句资金特征结论：活跃度趋势 / 机构态度 / 卖空意愿}

---

## 四、计算维度

> 对 `stockProfile` 返回但未在“一、二、三、五”中展示的所有维度和指标，必须放入本节；没有额外计算维度时写“本轮无额外计算维度”。不要预设维度名。
> 必须按维度分组输出：每个维度一个 `### {维度名}得分：{score} {信号}` 小标题，小标题下放该维度自己的指标表。禁止把所有维度做成一张大表。
> **展示模式**：群聊（飞书群 / Discord / WhatsApp）默认走**简洁模式（Top3）**——按 §3.5 规则选 Top3 维度 + 总结段；单聊或用户显式"详细/完整/全部"走**详细模式**——所有非空维度全部展开。
> **首行之前禁止任何自陈 / 工具状态 / 路由结论文字**（见 SKILL.md §1 规则 14 + §7 合同项 6）。

**详细模式骨架**：

### {dimension_name}得分：{score} {🟢/🟡/🔴/⚫}

| 指标 | 最新值 | 说明/口径 | 信号 |
|------|--------|-----------|------|
| {indicator.name 或 indicator_key} | {latest_value}{unit} | {description 或 —} | 🟢/🟡/🔴/⚫ |

（其余非空维度重复此小标题 + 指标表）

**简洁模式骨架**（按 §3.5 选 Top3，模板全文见 §3.5）：

> **信号分布**：… **共性结论**：… **最大风险**：…

### {dim1}得分：{score} {信号}

| 指标 | 最新值 | 说明/口径 | 信号 |
|------|--------|-----------|------|
（5 行）

### {dim2}得分：{score} {信号}

| 指标 | 最新值 | 说明/口径 | 信号 |
|------|--------|-----------|------|
（5 行）

### {dim3}得分：{score} {信号}

| 指标 | 最新值 | 说明/口径 | 信号 |
|------|--------|-----------|------|
（5 行）

未选中维度合并在 §七 综合观察 提 1 句。

{1 句计算维度结论：只总结本节返回的事实，不写目标价或预测明日涨跌}

---

## 五、波动率与风险

| 指标 | 最新值 | 1Y分位 | 3Y分位 | 5Y分位 | 信号 |
|------|--------|--------|--------|--------|------|
| 年化波动率 | {annualized_volatility}% | {pctrank:1Y×100}% | {pctrank:3Y×100}% | {pctrank:5Y×100}% | 🔴/🟡/🟢 |
| 标准差 | {stddev} | {pctrank:1Y×100}% | {pctrank:3Y×100}% | {pctrank:5Y×100}% | 🔴/🟡/🟢 |

> 波动率分位接近 100% = 当前波动处历史高位，持仓风险偏大 🔴。

---

## 六、消息面（近 30 日）

| 时间 | 事件 | 影响 |
|------|------|------|
| {YYYY-MM-DD} | {来源+事件摘要} | 🟢/🔴/🟡 |

{找不到一手来源的条目不写，不杜撰}

---

## 七、综合观察

**估值定性**：{基于 PE/PB/PS 三档分位的一句话，例："当前 PE(TTM) 3Y 分位 100%，估值处极度高位。"}

**财务趋势**：{基于收入增速 / 扣非增速 / 毛利率 / ROE 趋势的一句话，例："收入单季 YoY +42%，扣非增速 +67%，成长性突出；毛利率连续两季微降。"}

**资金特征**：{基于 turnover_ratio trend60 + 基金持仓 + 做空比例的一句话，例："成交额占比 60 日呈上升趋势，基金持仓归零，呈散户主导型交易结构。"}

**计算维度**：{基于“计算维度”表的一句话；若本轮无额外计算维度则写“本轮 stockProfile 未返回额外计算维度”。}

**风险因子**：{基于波动率分位 + 经营现金流 + 资本开支比的一句话}

| 持仓情况 | 定性建议 |
|---------|---------|
| 空仓 | {基于估值分位 + 财务趋势的定性描述，不给具体价位} |
| 已持有 | {基于波动率分位 + 财务趋势的定性描述，不给具体价位} |
| 高位浮盈 | {基于估值高位 + 波动率的定性描述，不给具体价位} |

**一句话总结**：{最核心的定性判断，必须有 stockProfile 数据支撑，禁止给明日涨跌预测}

---

> 数据截至 {computed_at 日期}（财务截至 {dimensions.财务分析.latest_date}）；不构成投资建议。
````

**Emoji 信号色约定**：
- 🟢 = 看多 / 改善 / 低分位 / 趋势向上 / 利好
- 🔴 = 看空 / 恶化 / 高分位 / 趋势向下 / 利空
- 🟡 = 中性 / 观察 / 等待确认
- ⚫ = 数据缺失 / 维度未返回

---

## 5. 失败兜底特化

- **`ASSET_NOT_FOUND` / `ASSET_REQUIRED`**：§6，明确说"该标的未在 quant-buddy 资产库中收录"，给出"用户提供更准确的代码/市场后缀"作为下一步。**不得降级跑任何其他工具试一遍**。
- **`indicators_count = 0`**：§6，说明"该资产暂无预计算指标数据"。不得改用其他工具或模型常识补写。
- **某单个维度整块不返回**（如港 / 美股财务维度为空）：在骨架里**跳过该大节**，标题行后加 `⚫ 本轮接口未返回该维度指标`，继续输出其余维度，不视为整体失败。
- **用户明确要求 stockProfile 不覆盖的字段**（MA5/10/20/60 绝对价位、KDJ / MACD / 布林带、主力 / 超大单 / 大单净流入明细、龙虎榜营业部、当日 OHLC 分时、近 5 日价格序列）：§6，原因写"本路由唯一工具为 stockProfile，不返回该字段，且本路由不调用 fast_query 补位"。
- **用户问"明日 / 下周 / 涨停概率 / 精确支撑压力位 / 目标价"**：§6；不得伪装成 stockProfile 数据，不得用波动率编造具体价位。
