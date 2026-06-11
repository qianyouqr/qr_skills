---
name: equity-research-router-skill
slug: equity-research-router-skill
version: 1.0.0
description: |
  把"用户对 A 股 / 港股 / 美股 / ETF / 基金 / 可转债 / 行业主题 / 大盘事件 / 资金面 / 量化选股"这一大类研究问题，
  路由到一条**结构化、可执行、不胡说**的研究路径。
  覆盖 8 大类（个股深度、对比组合、行业主题、宏观事件、
  港美股、ETF/基金/转债、资金面/选股、研究工具与配置），每类都给出：
    1) 触发关键词
    2) 必须先调用的 quant-buddy-skill 数据节点（绝不允许凭空写数）
    3) 解读 / 报告骨架
    4) 触发"受控失败答复"的判定与模板
  关键铁律：
    - 任何**数据**（行情、估值、财务、资金流、持仓、PE 分位、区间收益、K 线）→ 必须走 quant-buddy-skill；
    - 任何**消息 / 事件 / 政策 / 财报解读 / 股东背景**等定性信息 → 走 byted-web-search 搜索 + agent 推理；⚠️ 禁止使用 `web_fetch` 直连境外域名（服务器在中国大陆，Google / Yahoo / Reuters 均不可达）；
    - 当 quant-buddy-skill + byted-web-search + agent 推理仍**无法满足问题任一关键数据需求**时，
      必须输出"受控失败答复"（见 §6），禁止编造数据、禁止避重就轻。
runtime: prompt-only
primaryDataSkill: quant-buddy-skill
metadata:
  category: equity-research-routing
  tags: [equity, A-stock, HK-stock, US-stock, ETF, fund, sector, macro, quant, fail-safe]
---

# 研究问题路由 Skill（equity-research-router）

> **唯一入口**：先读完本文件 §1 ~ §6，再按 §3 路由到对应 playbook 文件 `playbooks/0X_*.md`，最后执行。
> **本 skill 不直接生成数据**——所有数值都从 `quant-buddy-skill` 取；本 skill 只负责**路由 + 框架 + 失败兜底**。
> **输出合同前置**：进入任何研究 / 分析 / 选股 / 对比 / 复盘 / 策略类 playbook 后，必须先锁定 §7 输出合同和对应 playbook 输出骨架，再取数和组织答案。
> **先搭骨架，再填数据**：最终答案不得先写自由文本草稿。必须先按 playbook 骨架创建章节、表格、分节线、计算维度容器，再把工具返回值填入对应槽位。
> **最终输出必须过 §7 格式门禁**：任何 playbook、群聊简洁化目标、工具结果摘要都不得覆盖 §7。发送前自检只是保险；若仍不满足 §7，必须先重写，再发送。

---

## §1. 顶层硬规则（违反必须立即停止任务）

1. **数据来源唯一性**：股价、涨跌幅、成交量、换手率、PE/PB/PS/股息率/分位、资金流、北向、主力 / 大单 / 散户、营收 / 净利润 / ROE / 现金流、近 N 日序列、区间收益、K 线、行业排名等任何**数字**——**只能**通过 `quant-buddy-skill` 获取（参考其 `场景路由` 表选 fast-snapshot / fast-window / fast-report-period / period-return-compare / quant-standard 等子流程）。
2. **禁止编造数据**：若 `quant-buddy-skill` 调用失败或返回 `字段不存在 / N/A / 报错`，**禁止**用"大致 / 约 / 历史经验告诉我们 / 通常情况下"等话术绕过；改走 §6 受控失败答复。
3. **禁止用 K 线把已知不存在的事实合理化**：不能因为图形看起来涨就臆测出基本面利好，也不能因为基本面好就编造未发生的成交量。
4. **第一句话必须是数据结论**：禁止以"好的""收到""让我先来调用…""我将分以下几步…"开头。第一句话必须直接给出**最关键的一个或两个数据**或**最关键的一个判断**。
5. **资产代码归一化**：先在 `quant-buddy-skill/presets/assets_db/*.yaml` 里 grep 名字 → 拿到正式 ticker（如"闪迪 → SNDK.O"、"腾讯 → 00700.HK"、"002594 → 002594.SZ"）。
   - **A / H 股同名默认规则**：用户只给中文公司名（未附港股代码 / ".HK" / "港股"字样），且该公司同时有 A 股和 H 股 → **默认取 A 股**，直接分析，不询问。例外：用户明确说"港股 / H股 / .HK / 香港市场"才切到 H 股。
   - **其他真实歧义**（同名但业务完全不同的两家 A 股公司、用户给的代码在多市场均有匹配且业务不同）→ 先问一句再继续。
6. **任务含糊先反问，禁止猜测开干**——但以下均**不属于含糊，直接走综合版**（基本面 + 估值 + 技术面 + 资金面），无需问用户：
   - "详细分析 / 深度分析 / 全面分析 / 分析一下 / 看看 + 代码/名称"
   - **单独输入股票名称 / 股票代码**（不附加任何修饰词，如用户只发"平治信息"或"300571"）→ **直接路由到 playbook 03，调用 stockProfile**

   只有以下情况才反问：
   - 资产市场有真实歧义（同名两家 A 股公司、或用户未指明 A/H 且第 5 条默认规则无法覆盖）；
   - "持仓占比"未指明是 ETF 前十大持仓 还是 公募持有该股；
   - "对比"未给出对比标的或对比维度；
   - "近期"窗口对结果影响极大且上下文无法推断（如事件研究起始日）。

   其他所有情况一律按合理默认值直接执行，**不允许用"您想看哪个维度 / 您想看哪个市场"把问题踢回给用户**。
7. **失败必须显式说**：见 §6。任何路径走不通都不能以"过程日志 / 自我安慰 / 改写题目"收尾。
8. **最终格式门禁必须执行**：除 §3 中 00 工具配置类外，所有研究 / 分析 / 选股 / 对比 / 复盘 / 策略类回答，必须先按 §7 和 playbook 骨架填槽生成；发送前再按 §7 自检。主路径是"先搭骨架再填数据"，不是先写纯文字再重写；若异常生成不满足 §7，才重写。
9. **03/04 路由唯一取数工具**：凡路由到 playbook `03_single_stock_deep_dive` 或 `04_multi_asset_compare` 的问题，**唯一数据入口是 `stockProfile`**（`stockProfile` 不返回的字段直接在骨架中跳过，重要缺失走 §6）。**严禁**在 03/04 路由中调用 `fast_query`（任何 workflow 变体）、`fast-snapshot`、`fast-window`、`fast-report-period`、`period-return-compare`、`quant-standard` 等工具作为补位——无论用户是否主动要求。
10. **画图类请求强制早期拦截（优先级高于所有 §3 路由及规则 9）**：用户意图含"画 / 图 / 折线图 / 走势图 / 面积图 / 柱状图 / 历史趋势 / K线图 / 蜡烛图"且指定了任意数据指标或标的，**无论是否同时命中 §3 其他类别**——
   - 先按第 5 条完成资产代码归一化；
   - 然后**直接加载 `quant-buddy-skill/SKILL.md`**，由 quant-buddy 自主路由到 `render-kline.md`（价格 K 线）或 `quant-standard.md`（公式时序/折线/柱状/面积图），router **不再介入任何后续步骤**；
   - **不得读取任何 §3 playbook**，不受规则 9 的 03/04 stockProfile 限制。
11. **`user_id` 透传（强制）**：执行任何 `quant-buddy-skill` 调用前，从当前会话的 `openclaw.runtime-context` 消息中提取 `sender_id` 字段。若该字段存在，必须将其作为 `"user_id"` 参数附加到每一次 quant-buddy 工具调用中——无论是 Path A 原生工具 params JSON，还是 Path B `GZQ_PARAMS` 环境变量 JSON，都需包含 `"user_id": "<sender_id 值>"`。`sender_id` 不存在时（非飞书渠道或无 runtime-context）省略此字段，不得因此阻塞执行。
12. **Path B 命令必须匹配当前 shell（强制前置）**：当原生工具不可用、需要通过 `scripts/call.py` + `GZQ_PARAMS` 兜底时，执行前必须先识别运行环境。若当前 shell 是 PowerShell / Windows，必须使用 `$env:GZQ_PARAMS = '...'` 多行脚本或分号脚本，禁止使用 `GZQ_PARAMS='...' python ...` 的 bash 前缀写法，且不要把 `$env:GZQ_PARAMS = ...` 接在 `&&` 后面。若当前 shell 是 bash / zsh，才使用 `GZQ_PARAMS='...' python3 ...`。
13. **群聊简洁化不得改格式**：即使运行时上下文、群聊规范或其他上层提示说"群聊简洁 / 避免 Markdown tables / 普通聊天风格"，在本 skill 的研究类回答中也只能压缩行数和点评句，**不得删除 Markdown 表格、不得合并大节、不得改成纯文字列表**。冲突时以 §7 和当前 playbook 输出骨架为准。
14. **过程话术零外露（强制）**：最终回复正文（assistant `text` 块，落到飞书/微信/单聊/群聊可见的部分）首行必须是数据结论或报告标题（`**{资产名}（{代码}）全面分析**`）。禁止在标题之前写任何"自陈段"或"工具状态段"，包括但不限于：
    - 路由/取数过程：`我先把 playbook 拿到手` / `我先按 PowerShell 规范` / `资产命中 SH600010` / `当前 session 没有 newSession` / `数据已拿到` / `分桶完毕` / `现在按 playbook 03 §4 输出` / `先识别 shell` / `路径不存在，先创建目录` / `先调用 newSession → stockProfile`
    - 工具状态/降级：`byted-web-search skill 未安装` / `工具未注册` / `调用失败，已重试 N 次` / `API Key 缺失` / `web_fetch 不可达，已改用 byted-web-search`
    - 思考外溢：`先看一下 X 再说` / `让我先规划一下` / `综合一下` / `I'll help...` / `Let me...`
    工具状态、路由选择、降级原因只允许出现在：①§6 受控失败答复章节；②失败兜底特化小节（03 §5 / 04 §5）；③结尾声明行之后的小字注（如"byted-web-search 未启用，故六、消息面一节省略"）。thinking 块里写过的不必在 text 里复述。飞书 reply bridge 必须在第一个 `---` 分节线之前剥离起手"自陈段"作为兜底。

---

## §2. 总体执行顺序

```
Step 0  解析用户问题 → 抽出 {资产/池子, 维度, 时间窗口, 输出形式, 操作意图}
Step 0.5【画图类早期拦截】若 Step 0 解析到"画/图/折线/走势/K线/面积/柱状"且有数据目标
        → 跳过 Step 1～4，直接：§1 第 5 条归一化 → 加载 quant-buddy-skill/SKILL.md
        → 由 quant-buddy 接管全部执行，本 skill 退出（见 §1 规则 10）
Step 1  按 §3 路由表选 1 个主 playbook（必要时 + 1 个附加 playbook）
Step 1.5【输出合同锁定】若主 playbook 属于研究 / 分析 / 选股 / 对比 / 复盘 / 策略类
        → 在取数前先确定最终答案必须使用该 playbook 的 Markdown 表格骨架
        → 在内部先建立"章节 + 表格 + 计算维度容器 + 结尾声明"的填槽计划
        → 明确禁止群聊简洁化覆盖表格、中文大节、计算维度独立章节和结尾声明
Step 2  读取该 playbook，按其"数据清单"逐项调 quant-buddy-skill
        ├─ 单股综合 / ≤10 标对比（03/04 路由）→ stockProfile（唯一；禁止任何其他工具补位）
        ├─ 行情/估值快照（非 03/04 路由）→ fast-snapshot
        ├─ 近 N 日/窗口（非 03/04 路由）→ fast-window / quick-window
        ├─ 最近报告期财务（非 03/04 路由）→ fast-report-period
        ├─ 区间收益对比（非 03/04 路由）→ period-return-compare
        ├─ K 线 → render-kline
        ├─ 选股/因子/回测/上传/下载 → quant-standard
        └─ 行业聚合排名 → quant-standard + recipes/industry-aggregation
Step 3  非数据信息（公告 / 财报点评 / 政策 / 舆情 / 同业地位）→ 加载 `~/.openclaw/workspace/.agents/skills/byted-web-search/SKILL.md`，调用 byted-web-search 搜索 + agent 推理；⚠️ 禁止使用 `web_fetch` 直连境外域名（服务器在中国大陆，Google / Yahoo / Reuters 均不可达）
Step 4  只允许按 Step 1.5 已锁定的"输出骨架"填槽生成答复，不得自由发挥成列表/摘要；不得弱化 §7 通用输出门禁
Step 5  数据自检：是否有任何关键数据缺失且未明示？若有 → §6 受控失败答复
Step 6  格式自检：最终回答是否满足 §7？正常情况下 Step 1.5/Step 4 已保证满足；若异常不满足 → 先重写为 §7 格式，再发送
```

---

## §3. 分类路由表

| # | 类别 | 触发关键词（命中即可） | playbook |
|---|------|-------------------------|----------|
| **0V** | **图表 / 可视化（最高优先级拦截）** | **画 / 图 / 折线图 / 走势图 / 面积图 / 柱状图 / 历史趋势 / K线图 / 蜡烛图** + 任意指标或标的；或"[标的]+[指标]走势图"等 | → **不读 playbook**；完成资产代码归一化后直接加载 `quant-buddy-skill/SKILL.md`（由 quant-buddy 内部区分 `render-kline` vs `quant-standard`+`renderChart`） |
| 03 | **个股深度分析与操作策略** | **单只股票名称 / 代码（单独输入即触发，无需附加关键词）**；或附带："深度分析 / 走势 / 基本面 / 操作建议 / 持有 / 低吸 / 建仓 / 卖出 / 业绩拐点 / 业务变化 / 财报点评 / 拐点" | [playbooks/03_single_stock_deep_dive.md](playbooks/03_single_stock_deep_dive.md) |
| 04 | **多标的对比 / 组合配置** | 多个代码 / 名称（≥2）+ "对比 / 比较 / 帮我分析这几只 / 对标 / 推荐 N 只 / 组合 / 仓位 / 调仓 / 买入时机" | [playbooks/04_multi_asset_compare.md](playbooks/04_multi_asset_compare.md) |
| 02 | **行业赛道 / 主题机会** | 行业名 / 题材名 + "推荐 / 龙头 / 概念股 / 重点股票 / 上下游 / 景气度 / 分析这个赛道" 或 "找做 XX 的股票"、"哪些标的属于 XX" | [playbooks/02_sector_theme.md](playbooks/02_sector_theme.md) |
| 01 | **宏观市场 / 事件影响** | 大盘 / 上证 / 沪深 300 / 纳指 / 恒科 / 复盘 / 全天 / 盘前 / 融资余额 / 油价 / 黄金白银 / 美伊 / 关税 / 加息 / 政策 / 厄尔尼诺 / 消费税 | [playbooks/01_macro_event.md](playbooks/01_macro_event.md) |
| 07 | **港股 / 美股 / 海外标的** | 港股代码（4–5 位 / .HK）、美股代码（.O/.N/.A 或英文 ticker）、Tesla/Intel/NVDA/TSM/ARM/MU/AMD/腾讯 700.HK 等 | [playbooks/07_hk_us_overseas.md](playbooks/07_hk_us_overseas.md) |
| 06 | **基金 / ETF / 可转债 / 指数产品** | 6 位基金代码（0/1/5 开头 ETF）、"联接 / LOF / 场内 / 场外 / PE 分位 / 持仓占比 / 转债 / 指数增强 / 调仓换基" | [playbooks/06_fund_etf_bond.md](playbooks/06_fund_etf_bond.md) |
| 05 | **资金面 / 量化选股 / 交易策略** | 主力 / 散户 / 机构 / 大单 / 资金流 / 换手率 / 涨停 / 拉板 / FVG / SMC / 通达信公式 / 选股 / 今日看涨 / 涨停概率 | [playbooks/05_capital_flow_quant.md](playbooks/05_capital_flow_quant.md) |
| 00 | **研究工具 / 数据获取 / 配置** | "怎么接入 / 如何接入 / API / 飞书 / 微信 / Clawbot / skill 下载 / 模板 / 提示词 / 表格显示 / 长会话 / 模型 ID" | [playbooks/00_meta_tooling.md](playbooks/00_meta_tooling.md) |

**0V 最高优先级**：0V 命中时立即拦截，不参与多类命中合并，不受规则 9 的 03/04 stockProfile 限制。

**多类命中时（0V 未命中）**：以**用户最终诉求**为主类（多为 03 个股深度 / 04 多标的对比 / 02 行业），其他作为附加 playbook 提供数据维度。

**含糊命中时**：见 §1 第 6 条，先反问。

---

## §4. 数据需求 → quant-buddy-skill 子流程对照表

| 用户想要 | 走 quant-buddy-skill 的哪个 leaf |
|---------|--------------------------------|
| **单股综合 / ≤10 标对比（03/04 路由）** — 估值 / 财务 / 资金 / 走势 / 波动率一次性 | `stockProfile`（**唯一**；此路由下禁止调用下表其余任何 leaf） |
| 最新价 / 涨跌幅 / 换手率 / PE / PB / 市值 / 当日成交额（**非** 03/04 路由） | `fast-snapshot.md` |
| 近 5 / 10 / 20 日价格序列、窗口高低、波动率、涨跌幅序列（**非** 03/04 路由） | `fast-window.md` / `quick-window.md` |
| 最近一期营收 / 净利润 / 归母 / ROE / 资产负债率 / 现金流（**非** 03/04 路由） | `fast-report-period.md` / `quick-report-period.md` |
| 从某日到某日累计涨跌幅、多资产区间对比、同期相对收益（**非** 03/04 路由） | `period-return-compare.md` |
| K 线图 / 蜡烛图 / 均线图 | `render-kline.md` |
| 多条件筛选股池（PE<X、ROE>Y、市值范围、行业、概念）、TopN 排名 | `quant-standard.md` |
| 因子构建、回测、净值、IC、上传 CSV、下载 CSV | `quant-standard.md` + 对应 `recipes/*` |
| 行业 / 板块聚合排名（行业平均涨幅、板块成交额） | `quant-standard.md` + `recipes/industry-aggregation.md` |
| 历次事件后 N 日表现 / 阈值区间统计 | `event-study.md` / `regime-segmentation.md` |
| 历史 PE / PB **分位数** | `quant-standard.md`（构造 percentile 公式） |
| 任意指标历史时序走势图 / 折线图 / 面积图 / 柱状图（PE走势 / PB趋势 / ROE历史 / 净值曲线 / 营收趋势 / 自定义公式图…） | **不经 §3 playbook**；直接加载 `quant-buddy-skill/SKILL.md`，由 quant-buddy 路由到 `quant-standard.md`+`renderChart`（或 `render-kline.md` 若为价格 K 线） |

> **不要为了"显得专业"重复多次调用**。Fast Path 能解决就停在 Fast Path。
> **不要在 quant-buddy-skill 之外另起 Python / shell 取数**——除非问题超出 quant-buddy 能力范围，并已记入 §6 失败原因。

---

## §5. quant-buddy-skill 能力边界（agent 必须知道）

**它能给的**（高置信）：
- A 股 5500+ 只、港股 2860+ 只、美股 1040+ 只的行情 / 估值 / K 线 / 区间收益；
- A 股完整三大表财务字段；港 / 美股财务以 `fast_query(report)` 实际返回为准；
- 指数 503 条、期货 257 条、常用 ETF / 基金行情；
- 选股、因子、回测、行业聚合、事件研究、阈值区间统计。

**它不直接给的**（必须 agent 联网或受控失败）：
- 公司未公开消息 / 微信群传闻 / 内部交流纪要；
- 行业最新政策原文、专家访谈、卖方研报观点；
- 公司主要客户、竞争格局、产品认证进度等定性叙述（除非已有结构化字段）；
- 单笔大单逐笔明细（只有日级 / 分钟级聚合资金流）；
- 龙虎榜营业部明细（agent 视实际 fast_query 返回判定，没有就走 §6）；
- 公司股东 / 高管背景人脉（联网搜索）；
- "明日预测 / 涨停概率 / 短期高点"——**任何对未来价格的点估计**都不是数据，是判断；可给概率框架但**必须明确标注为定性推断**，不得伪装成 quant-buddy 数据。

### stockProfile 字段速查（仅适用于 03/04 路由）

**已覆盖（可直接引用）**

| 维度 | base_id | 主要 variants |
|------|---------|--------------|
| 资产走势 | `close_price` | `ret:20` / `ret:60` / `ret:120` / `ret:250`（倍数，×100 得百分比） |
| 估值 | `pe_ttm` / `pb_ratio` / `ps_ttm` / `dividend_yield` | `pctrank:1Y` / `pctrank:3Y` / `pctrank:5Y`（0~1，1=历史最高） |
| 财务分析 | `fa_revenue_growth` / `fa_non_recurring_profit_growth` / `fa_gross_margin` / `fa_net_margin` / `fa_operating_margin` / `fa_roe_analysis` / `fa_roic_analysis` / `fa_operating_cash_flow` / `fa_capex_cash_flow` / `fa_capex_cash_flow_ratio` / `fa_contract_liability` / `fa_wip` | `quarter_yoy` / `quarter_qoq` / `ttm_level` / `ttm_yoy` / `ttm_qoq` / `annual_level` / `annual_yoy` |
| 资金流向 | `turnover_ratio` / `turnover_ma` / `short_selling_ratio` / `fund_holding_ratio` | `trend60` / `pctrank:3Y` / `param:5/10/20/60/120/250` |
| 波动率 | `annualized_volatility` / `stddev` | `pctrank:1Y` / `pctrank:3Y` / `pctrank:5Y` |
| 宏观胜率背景 | 按接口实际返回 | — |
| 动态补充维度 | `dimensions` 下任意未在上方列出的维度名和指标名 | 不预设字段；逐维度读取 `indicators.*.name/latest_value/latest_date/description/unit/variants`，并在最终回答中完整覆盖 |

**不返回（在 03/04 路由中禁止写入骨架；用户硬问走 §6）**：MA5 / MA10 / MA20 / MA60 绝对价位、KDJ / MACD / 布林带、主力 / 超大单 / 大单 / 散户净流入明细、龙虎榜营业部、当日 OHLC 明细、近 5 日价格序列、区间最高 / 最低价具体值、精确支撑 / 压力价位。

---

## §6. 受控失败答复协议（最重要的兜底）

**触发条件**（任一即触发）：
1. quant-buddy-skill 关键调用连续失败（同类报错 ≥ 2 次或熔断），且无替代字段；
2. 用户问的关键数据/字段在 quant-buddy 能力外，联网也找不到一手来源；
3. 用户的关键资产无法消歧（grep 资产库返回多条且用户已澄清仍冲突）；
4. 问题本质是"预测未来具体点位 / 涨停概率 / 几月几号买入"且没有量化模型支撑；
5. 用户配置缺失（API Key / 环境）经一次引导仍未提供；
6. 问题路由至 03/04，但用户明确要求 stockProfile 不覆盖的字段（MA 绝对价位、KDJ / MACD / 布林带、主力净流入四档、龙虎榜、当日 OHLC 等）且拒绝接受替代方案。

**失败答复模板**（**必须**全包含以下 5 段，不得删减）：

```
【未能完成的部分】
- 你的原始问题（一句复述）：______
- 卡在哪一步：______（工具名 + 错误摘要 / 字段名 + 缺失原因）
- 为什么这一步绕不过去：______（一句话，例如"该字段 quant-buddy 不提供，且联网无一手数据源"）

【已经拿到的部分】（如果有）
- 已经成功取到的数据 / 已确认的事实，简洁列出，明确标注数据时点。

【替代可做的事】（给用户的下一步选项）
- 选项 A：换一个可执行的相近问题（举例，例如把"明日涨停概率"换成"近 N 日涨停频次 + 当前位置"）；
- 选项 B：用户提供更多输入（指定窗口 / 指定标的 / 提供 API Key）；
- 选项 C：等待时点（例如盘后再跑、财报披露后再跑）。

【风险提示】
本回答未对缺失部分做任何编造或推断。以上内容不构成投资建议。
```

**禁止行为**（任何一条出现都属违规，需重写）：
- 用"大致 / 约 / 应该 / 通常 / 历史经验" 替代真实数据；
- 把"找不到"包装成"目前看不出明显异常"；
- 自创"主力净流入约 X 亿"等具体数字；
- 把 K 线形态当作未来价格的确定性结论。

---

## §7. 输出生成合同与格式门禁（所有 playbook 共享）

本节是**生成前合同 + 发送前硬门禁**，优先级高于所有 playbook 的局部骨架、群聊简洁化目标、过程摘要和工具结果摘要。

**生成前必须先做（不是失败后补救）**：
- 在读取工具结果前，先选择对应 playbook 的输出骨架，并把最终答案限定为“填槽式生成”；
- 在写任何结论句前，先保留中文编号大节、`---` 分节线、Markdown 表格表头和结尾声明的位置；
- 使用 `stockProfile` 时，取数后先枚举 `data.dimensions` 的全部非空维度，建立 `常规模板维度` 与 `计算维度` 的映射，再开始写正文；
- 计算维度必须先建独立容器：单股为 `## 四、计算维度`，多标的为 `## 五、计算维度横向对比`；然后按返回维度逐个生成小标题和指标表；
- 群聊简洁化只能减少点评句和表格行数，不能改变已锁定的章节、表格、计算维度容器和结尾声明；
- 禁止先写纯文字摘要、项目符号列表或聊天式回答，再依赖“发送前重写”修正。
- 6. **首行之前禁止出现任何自陈 / 工具状态 / 路由结论文字**。如"数据已拿到 / byted-web-search skill 未安装 / 现在按 playbook §4 输出 / 先识别 shell / 分桶完毕 / 资产命中 SH600010"等全部禁止；首行直接是 `**{资产名}（{代码}）全面分析**` 或对比标题。违反此条的输出必须整段重写。

除 §3 中 00 工具配置类外，每个研究 / 分析 / 选股 / 对比 / 复盘 / 策略类回答，最终发送文本必须**同时**包含：

1. **首行标题**：`**{股票名/标的}（{代码}）全面分析**` + 时间 / 数据来源行；
2. **`---` 分节线**：每个大节之间必须有分隔线；
3. **大节编号**：中文数字 `## 一、二、三、四、`；
4. **行内加粗指标**：`**最新价**：X元 | **PE(TTM)**：X倍` 格式，用 `|` 分隔同行指标；
5. **表格强制**：行情估值、财务、资金、计算维度、波动率、多资产对比等结构化数据必须用 Markdown 表格（必须出现 `|---` 表头分隔行），禁止用纯文字列表、项目符号或冒号列表替代；
6. **emoji 信号色**：🟢 看多/利好/流入，🔴 看空/利空/流出，🟡 中性/观察，⚫ 数据缺失；
7. **结尾声明行**：`> 数据截至 YYYY-MM-DD；不构成投资建议。`

**发送前必须逐项自检（保险，不是主要生成方式）**：
- 如果最终答案没有 `## 一、` 这类中文编号大节 → 必须重写；
- 如果任一结构化大节没有 Markdown 表格（没有 `|---` 分隔行）而是纯文字列表 / 项目符号 / 冒号列表 → 必须重写；
- 如果没有 `---` 分节线 → 必须重写；
- 如果没有 emoji 信号色 → 必须重写；
- 如果使用 `stockProfile`，但没有先枚举 `data.dimensions` 的全部非空维度并在最终回答中覆盖所有未展示维度 / 未展示指标 → 必须重写；
- 如果存在任意未被常规模板展示的 `stockProfile` 维度，却没有独立的 `## 四、计算维度`（或多标的 `## 五、计算维度横向对比`）章节和表格 → 必须重写；
- 如果单股 `## 四、计算维度` 把多个计算维度混在一张大表中，而不是按 `### {维度名}得分：{score} {信号}` 分组展示 → 必须重写；
- 如果单股每个计算维度小标题没有体现该维度综合分/最终得分和 emoji 信号 → 必须重写；
- 如果把计算维度合并进“波动率与风险 / 波动率与趋势结构 / 资产趋势 / 技术面”等其他标题 → 必须重写；
- 如果最终回答以英文过程话术或中文过程话术开头（如 `I'll help...`、`我先来...`、`根据工具...`）而不是数据结论 → 必须重写；
- 如果没有 `> 数据截至 YYYY-MM-DD；不构成投资建议。` → 必须重写；
- 不得用"群聊里简洁一点 / 口语一点 / 可读一点"作为省略上述格式的理由。可以简洁，但必须保留 §7 的结构。

> playbook 文件只负责给出每类**专属的**数据清单与骨架细化；若 playbook 骨架与本节不一致，以本节为准。

---

## §8. 文件结构

```
equity-research-router-skill/
├── SKILL.md                    ← 本文件（入口 + 顶层规则）
└── playbooks/
    ├── 00_meta_tooling.md           研究工具与数据获取
    ├── 01_macro_event.md            宏观市场与事件影响
    ├── 02_sector_theme.md           行业赛道与主题机会
    ├── 03_single_stock_deep_dive.md 个股深度分析与操作策略
    ├── 04_multi_asset_compare.md    多标的对比与组合配置
    ├── 05_capital_flow_quant.md     资金面交易策略与量化选股
    ├── 06_fund_etf_bond.md          基金 ETF 可转债与指数产品
    └── 07_hk_us_overseas.md         港美股与海外标的
```
