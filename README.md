# 📡 Daily arXiv Digest · 每日 arXiv 论文雷达

> 每天早上自动抓一遍 arXiv，按我关心的关键词（多模态推荐 / LLM 推荐 / 跨模态融合）排序，
> 生成一份中文日报提交回本仓库。全部跑在 GitHub Actions 上，零成本、不用开机。

[![Daily arXiv Digest](https://github.com/OWNER/REPO/actions/workflows/daily.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/daily.yml)

## 这是什么

一个「每天真的产出一点东西」的自动化工作流，而不是空提交刷绿格子。

- **抓取**：`arXiv API`，分类见 [`config.json`](config.json)
- **打分**：关键词加权（标题命中双倍），阈值过滤
- **产出**：`digests/YYYY-MM-DD.md` 中文日报 + 本文下方的索引表
- **提交**：每天北京时间 06:17 由 GitHub Actions 自动 commit & push

## 日报索引

<!-- DIGEST:START -->

| 日期 | 当日抓到 | 命中 |
| --- | ---: | ---: |
| [2026-09-14](digests/2026-09-14.md) | 300 | 14 |

<!-- DIGEST:END -->

（首次运行后这里会自动长出列表。）

## 怎么用

### 1. 想让雷达更懂你：改 `config.json`

```json
{
  "categories": ["cs.IR", "cs.CL", "cs.CV", "cs.MM", "cs.LG"],
  "window_days": 2,
  "min_score": 3,
  "keywords": { "multimodal recommendation": 6, "semantic id": 4 }
}
```

`keywords` 的 value 是权重，标题里命中会再翻倍。觉得某类论文太多/太少，就调 `min_score`
（调高 = 更挑），或直接调关键词权重。关键词支持 `*` 通配，例如 `"large language model*recommend"`。

### 2. 想立刻跑一遍：Actions → Daily arXiv Digest → Run workflow

### 3. 手动补跑历史：本地执行

```bash
python scripts/daily_digest.py     # 只依赖 Python 标准库
```

## 目录结构

```
├── .github/workflows/daily.yml   # 定时任务：生成 + 提交
├── config.json                   # 抓什么分类、认哪些关键词
├── scripts/daily_digest.py       # 纯标准库实现，零依赖
├── digests/                      # 每日日报（自动生成）
└── SETUP.md                      # 部署与排错说明
```

## 相关

- [`TideDra/zotero-arxiv-daily`](https://github.com/TideDra/zotero-arxiv-daily) — 同一思路，但按 Zotero 库做向量推荐、只发邮件
- [`gautamkrishnar/blog-post-workflow`](https://github.com/gautamkrishnar/blog-post-workflow) — RSS/博客自动更新 README
- [`anmol098/waka-readme-stats`](https://github.com/anmol098/waka-readme-stats) — WakaTime 真实编码时长统计
