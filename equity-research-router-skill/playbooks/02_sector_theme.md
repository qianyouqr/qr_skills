# Playbook 02 — 行业赛道与主题机会

> 触发：行业名 / 题材名 + "推荐 / 龙头 / 概念股 / 上下游 / 景气度"，或"做 XX 的股票有哪些"。

## 1. 主题→标的池构建（最关键的一步）

quant-buddy-skill 提供 `presets/themes.yaml` + `presets/sectors.yaml`，**先 grep 这两个文件**确认题材是否已收录（CPO、光通讯、存储、PCB、商业航天、稀土、火电、玻璃玻纤……大概率收录）。

- **命中**：直接用题材成员池跑后续筛选。
- **未命中**：去 `assets_db/stock_a.yaml`（包含行业字段）grep 行业关键字；仍不足 → 加载 `~/.openclaw/workspace/.agents/skills/byted-web-search/SKILL.md`，byted-web-search 搜"XX 概念股 龙头"，但**所有从 byted-web-search 拿到的标的，必须**回到 quant-buddy 验证（取行情 + 业务字段）才能写入答复。**禁止**未经验证地列入答复。

## 2. 必跑数据清单

| # | 数据 | 入口 |
|---|------|-----|
| 1 | 题材池 / 行业池每只的：现价、涨跌幅、市值、PE、近 20/60 日涨跌幅、近一年涨跌幅 | `quant-standard`（构造公式 + 排序） |
| 2 | 行业平均 PE / 行业指数走势 | `industry-aggregation` recipe |
| 3 | TopN（按涨幅 / 市值 / ROE / 业务相关度）展开 | `quant-standard` 排序 + 切片 |
| 4 | 每只 Top 标的的最近报告期财务速览 | `fast-report-period` |

## 3. 输出骨架

```
【结论行】<赛道> 当前景气 <定性>，A 股核心标的 N 只（按 <维度> 排序）。
【赛道概览】产业链上下游一句话；当前景气信号（byted-web-search 搜索，标来源 + 时点）
【核心标的池】
  | 代码 | 名称 | 现价 | 市值 | PE | 近60日% | 业务定位 |
  | ... |
【主线 / 子方向】（如适用，分子方向给标的）
【催化与风险】
【声明】
```

## 4. 特殊场景

- **"找股价 6.14 元 + 做 XX 行业的股票"**：先用 `quant-standard` 在行业池筛 |当前价 - 6.14| < 0.1 → 列候选 → 让用户确认，不要硬猜。
- **"金风科技持股 XX 比例多少"**：是关联方持股关系，quant-buddy 通常**没有**这一字段；加载 byted-web-search SKILL.md 搜一手公告确认；找不到 → §6。
- **"DeepSeek/Kimi/MiniMax 三家公司对比"**：未上市公司，quant-buddy **不覆盖**；加载 byted-web-search SKILL.md 做产品 / 估值新闻对比，必须明确"非上市公司，无 quant-buddy 行情数据"，并把对比限定在公开信息维度。

## 5. 失败兜底特化

- 题材完全找不到对应池：直接 §6，给出"用户给一个种子龙头作为锚点"作为可选下一步。
- 未上市公司 / 一级市场公司：明确告知 quant-buddy 不覆盖，仅做有限的公开信息综述；不写任何具体估值 / 营收数字除非有公开来源。
