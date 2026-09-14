#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日 arXiv 论文雷达。

抓取 config.json 指定分类的最新投稿，按关键词加权打分，
生成中文 Markdown 日报到 digests/YYYY-MM-DD.md，并刷新 README 索引。

三个刻意的设计：
  1) 只用 Python 标准库 —— GitHub Actions 上零安装，不会因依赖挂掉；
  2) 主源用 arXiv 的 RSS（rss.arxiv.org），拿不到再退回 arXiv API —— API 会限流；
  3) 无论结果如何都写文件 —— 抓取失败也留痕，不会静默断更。
"""

import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TZ_CN = timezone(timedelta(hours=8))
UA = "daily-arxiv-digest/1.0 (github actions daily digest; contact: repo owner)"
RSS_URL = "https://rss.arxiv.org/rss/%s"
API_URL = "http://export.arxiv.org/api/query?"
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "rss": "http://purl.org/rss/1.0/",
    "arxiv": "http://arxiv.org/schemas/atom",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def log(msg):
    print("[digest] %s" % msg, flush=True)


def tag_of(el):
    return el.tag.split("}")[-1]


def load_config():
    with open(ROOT / "config.json", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg.pop("_comment", None)
    cfg.setdefault("categories", ["cs.IR"])
    cfg.setdefault("min_score", 3)
    cfg.setdefault("max_items", 40)
    cfg.setdefault("high_score", 10)
    cfg.setdefault("window_days", 3)
    cfg.setdefault("announce_types", ["new", "cross"])
    cfg.setdefault("keywords", {})
    return cfg


def http_get(url, retries=3, timeout=45):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception as exc:  # noqa: BLE001
            last = exc
            if i < retries - 1:
                wait = 4 * (i + 1)
                log("请求失败(%d/%d) %s → %s，%ds 后重试" % (i + 1, retries, url, exc, wait))
                time.sleep(wait)
    raise RuntimeError("请求最终失败 %s: %s" % (url, last))


def clean_abstract(text):
    text = re.sub(r"^\s*arXiv:\S+\s*Announce Type:\s*\w+\s*", "", text)
    text = re.sub(r"^\s*Abstract:\s*", "", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def norm_id(url_or_id):
    m = re.search(r"(\d{4}\.\d{4,5})", url_or_id or "")
    return m.group(1) if m else (url_or_id or "").strip()


def from_rss(xml_text, category):
    """解析 rss.arxiv.org 的一个分类订阅，返回论文列表。"""
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    if channel is None:
        return []
    out = []
    for it in channel.findall("item"):
        fields = {tag_of(c): c for c in it}
        aid = norm_id(fields["link"].text if "link" in fields else "")
        if not aid:
            continue
        cats = [c.text.strip() for c in it.findall("category") if c.text]
        announce = ""
        for key, el in fields.items():
            if key == "announce_type":
                announce = (el.text or "").strip()
        pub = None
        if "pubDate" in fields:
            try:
                pub = parsedate_to_datetime(fields["pubDate"].text)
            except Exception:  # noqa: BLE001
                pub = None
        creators = fields.get("creator")
        authors = [a.strip() for a in (creators.text or "").split(",") if a.strip()] if creators is not None else []
        out.append(
            {
                "id": aid,
                "url": "https://arxiv.org/abs/%s" % aid,
                "pdf": "https://arxiv.org/pdf/%s" % aid,
                "title": re.sub(r"\s+", " ", (fields["title"].text or "")).strip(),
                "abstract": clean_abstract(fields["description"].text or "") if "description" in fields else "",
                "published": pub.astimezone(TZ_CN).strftime("%Y-%m-%d %H:%M") if pub else "",
                "published_dt": pub,
                "authors": authors,
                "categories": cats or [category],
                "announce": announce,
                "comment": "",
                "source": "rss/%s" % category,
            }
        )
    return out


def from_api(xml_text, category):
    """兜底源：解析 arXiv Atom API。"""
    root = ET.fromstring(xml_text)
    out = []
    for e in root.findall("atom:entry", NS):
        def txt(rel):
            node = e.find("atom:%s" % rel, NS)
            return (node.text or "").strip() if node is not None else ""

        aid = norm_id(txt("id"))
        if not aid:
            continue
        authors = [
            (a.find("atom:name", NS).text or "").strip()
            for a in e.findall("atom:author", NS)
            if a.find("atom:name", NS) is not None
        ]
        cats = [c.get("term") for c in e.findall("atom:category", NS) if c.get("term")]
        cm = e.find("arxiv:comment", NS)
        pub = None
        if txt("published"):
            try:
                pub = datetime.strptime(txt("published"), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            except Exception:  # noqa: BLE001
                pub = None
        out.append(
            {
                "id": aid,
                "url": "https://arxiv.org/abs/%s" % aid,
                "pdf": "https://arxiv.org/pdf/%s" % aid,
                "title": re.sub(r"\s+", " ", txt("title")),
                "abstract": clean_abstract(txt("summary")),
                "published": pub.astimezone(TZ_CN).strftime("%Y-%m-%d %H:%M") if pub else "",
                "published_dt": pub,
                "authors": authors,
                "categories": cats or [category],
                "announce": "new",
                "comment": (cm.text or "").strip() if cm is not None else "",
                "source": "api/%s" % category,
            }
        )
    return out


def collect(cfg):
    """按分类收集，RSS 优先，任一分类失败则对该分类退回 API。"""
    seen, papers, srcs, errors = {}, [], set(), []
    cutoff = datetime.now(timezone.utc) - timedelta(days=cfg["window_days"])
    for cat in cfg["categories"]:
        got = []
        try:
            got = from_rss(http_get(RSS_URL % cat), cat)
            log("RSS %s → %d 篇" % (cat, len(got)))
        except Exception as exc:  # noqa: BLE001
            log("RSS %s 失败(%s)，改用 API" % (cat, exc))
            try:
                q = urllib.parse.urlencode(
                    {
                        "search_query": "cat:%s" % cat,
                        "start": 0,
                        "max_results": 100,
                        "sortBy": "submittedDate",
                        "sortOrder": "descending",
                    }
                )
                got = from_api(http_get(API_URL + q), cat)
                log("API %s → %d 篇" % (cat, len(got)))
            except Exception as exc2:  # noqa: BLE001
                errors.append("%s: %s" % (cat, exc2))
                log("分类 %s 两条源都失败: %s" % (cat, exc2))
        for p in got:
            if p["announce"] and p["announce"] not in cfg["announce_types"]:
                continue
            if p["published_dt"] and p["published_dt"] < cutoff:
                continue
            if p["id"] in seen:
                # 同一篇被多个分类收录，合并分类信息
                exist = seen[p["id"]]
                for c in p["categories"]:
                    if c not in exist["categories"]:
                        exist["categories"].append(c)
                continue
            seen[p["id"]] = p
            papers.append(p)
            srcs.add(p["source"])
    return papers, sorted(srcs), errors


def score_paper(paper, keywords):
    """关键词加权打分：标题命中双倍权重，摘要命中单倍。`*` 表示 40 字符内任意内容。"""
    title = paper["title"].lower()
    text = (paper["title"] + " " + paper["abstract"]).lower()
    total, hits = 0, []
    for kw, weight in keywords.items():
        pattern = re.escape(kw.lower()).replace(r"\*", r".{0,40}")
        try:
            if re.search(pattern, text):
                w = int(weight) * (2 if re.search(pattern, title) else 1)
                total += w
                hits.append("%s +%d" % (kw, w))
        except re.error:
            continue
    paper["score"] = total
    paper["hits"] = hits
    return paper


def short_authors(names, limit=3):
    if not names:
        return "—"
    if len(names) <= limit:
        return ", ".join(names)
    return "%s 等 %d 人" % (names[0], len(names))


def one_liner(abstract, limit=280):
    text = (abstract or "").strip()
    if not text:
        return "（无摘要）"
    line = " ".join(re.split(r"(?<=[.!?])\s+", text)[:2])
    return line[:limit] + ("…" if len(line) > limit else "")


def esc(s):
    return (s or "").replace("|", "\\|").replace("[", "\\[").replace("]", "\\]")


def build_markdown(today_cn, cfg, papers, stats):
    L = []
    L.append("# arXiv 论文雷达 · %s" % today_cn)
    L.append("")
    L.append(
        "> 分类：`%s` ｜ 抓到 %d 篇 ｜ 命中 %d 篇（阈值 %d 分）｜ 源：%s"
        % (
            "`, `".join(cfg["categories"]),
            stats["fetched"],
            len(papers),
            cfg["min_score"],
            ", ".join(stats["sources"]) or "无",
        )
    )
    L.append("")

    if stats["errors"]:
        L.append("> ⚠️ 部分分类抓取失败：%s" % "；".join(stats["errors"]))
        L.append("")

    if not papers:
        L.append("## 今天没有命中关键词的论文")
        L.append("")
        L.append("可能是 arXiv 今天没公告新论文（周末/节假日），也可能是关键词太窄。")
        L.append("调整方式：改 `config.json` 里的 `keywords` 或把 `min_score` 调低。")
        L.append("")
        return "\n".join(L)

    hot = [p for p in papers if p["score"] >= cfg["high_score"]]
    if hot:
        L.append("## 🔥 优先看（%d 篇）" % len(hot))
        L.append("")
        for p in hot:
            L.append("- **[%s](%s)** ｜ %d 分 ｜ `%s`" % (p["title"], p["url"], p["score"], ", ".join(p["categories"][:3])))
            L.append("  - %s" % one_liner(p["abstract"], 320))
            if p["comment"]:
                L.append("  - 备注：%s" % p["comment"][:160])
            L.append("  - [PDF](%s)" % p["pdf"])
        L.append("")

    L.append("## 全部命中（按分数降序）")
    L.append("")
    L.append("| 分 | 标题 | 分类 | 作者 | 命中关键词 | PDF |")
    L.append("| ---: | --- | --- | --- | --- | --- |")
    for p in papers:
        L.append(
            "| %d | [%s](%s) | %s | %s | %s | [📄](%s) |"
            % (
                p["score"],
                esc(p["title"]),
                p["url"],
                ", ".join(p["categories"][:3]),
                esc(short_authors(p["authors"])),
                esc(" / ".join(p["hits"][:4])),
                p["pdf"],
            )
        )
    L.append("")
    L.append("## 当天分类分布")
    L.append("")
    for cat, n in stats["by_cat"].items():
        L.append("- `%s`：%d 篇" % (cat, n))
    L.append("")
    L.append("---")
    L.append("")
    L.append("### 使用方法")
    L.append("")
    L.append("1. 先扫 🔥 区标题，感兴趣的直接点 PDF。")
    L.append("2. 值得留的丢进 Zotero，并在下面「我的批注」里写一句为什么留。")
    L.append("3. 每周扫一遍本周日报，攒开题/综述的文献池。")
    L.append("")
    L.append("### 我的批注")
    L.append("")
    L.append("<!-- 写你今天看了哪几篇、有什么想法。不用删这行注释。 -->")
    L.append("")
    return "\n".join(L)


def update_readme(today_cn, total, hit):
    readme = ROOT / "README.md"
    if not readme.exists():
        return
    text = readme.read_text(encoding="utf-8")
    start, end = "<!-- DIGEST:START -->", "<!-- DIGEST:END -->"
    if start not in text or end not in text:
        log("README 缺少 DIGEST:START/END 标记，跳过索引更新")
        return
    head, rest = text.split(start, 1)
    body, tail = rest.split(end, 1)
    rows = [
        r.strip()
        for r in body.splitlines()
        if r.strip().startswith("| [") and not r.strip().startswith("| 日期")
    ]
    row = "| [%s](digests/%s.md) | %d | %d |" % (today_cn, today_cn, total, hit)
    rows = [r for r in rows if today_cn not in r]
    rows.insert(0, row)
    rows = rows[:365]
    new_body = "\n\n| 日期 | 当日抓到 | 命中 |\n| --- | ---: | ---: |\n" + "\n".join(rows) + "\n\n"
    readme.write_text(head + start + new_body + end + tail, encoding="utf-8")
    log("README 索引已更新（%d 条）" % len(rows))


def main():
    cfg = load_config()
    today_cn = datetime.now(TZ_CN).strftime("%Y-%m-%d")
    out_dir = ROOT / "digests"
    out_dir.mkdir(exist_ok=True)

    papers, sources, errors = [], [], []
    try:
        papers, sources, errors = collect(cfg)
    except Exception as exc:  # noqa: BLE001
        errors.append("整体失败: %s" % exc)
        log("抓取整体失败: %s" % exc)

    by_cat = {}
    for p in papers:
        for c in p["categories"]:
            if c in cfg["categories"]:
                by_cat[c] = by_cat.get(c, 0) + 1
                break

    scored = [score_paper(p, cfg["keywords"]) for p in papers]
    picked = sorted(
        [p for p in scored if p["score"] >= cfg["min_score"]],
        key=lambda p: (p["score"], p["published"]),
        reverse=True,
    )[: cfg["max_items"]]

    stats = {
        "fetched": len(papers),
        "sources": sources,
        "errors": errors,
        "by_cat": dict(sorted(by_cat.items())),
    }
    md = build_markdown(today_cn, cfg, picked, stats)
    path = out_dir / ("%s.md" % today_cn)
    path.write_text(md, encoding="utf-8")
    log("已写出 %s（抓到 %d，命中 %d）" % (path.relative_to(ROOT), len(papers), len(picked)))
    update_readme(today_cn, len(papers), len(picked))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        log("未捕获异常: %s" % exc)
        sys.exit(1)
