import hashlib
import html
import os
import re
from datetime import datetime, timedelta

import feedparser
import requests

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


CATEGORY_ORDER = [
    "SEO 动态",
    "GEO 趋势",
    "AI 搜索",
    "国内资讯",
    "专家动态",
]

CATEGORY_META = {
    "SEO 动态": {"icon": "🔎", "slug": "seo", "accent": "#2563eb"},
    "GEO 趋势": {"icon": "🌐", "slug": "geo", "accent": "#0891b2"},
    "AI 搜索": {"icon": "🤖", "slug": "ai-search", "accent": "#7c3aed"},
    "国内资讯": {"icon": "CN", "slug": "china", "accent": "#dc2626"},
    "专家动态": {"icon": "𝕏", "slug": "experts", "accent": "#111827"},
}

RSS_SOURCES = {
    "SEO 动态": {
        "Google Search Central": "https://developers.google.com/search/blog/feed.xml",
        "Search Engine Land": "https://searchengineland.com/feed",
        "SEO Roundtable": "https://www.seroundtable.com/rss.xml",
        "Ahrefs Blog": "https://ahrefs.com/blog/feed/",
        "Backlinko": "https://backlinko.com/feed/",
    },
    "GEO 趋势": {
        "Search Engine Journal": "https://www.searchenginejournal.com/feed/",
        "Aleyda Solis Blog": "https://www.aleydasolis.com/en/blog/feed/",
        "Onely Tech SEO": "https://www.onely.com/blog/feed/",
    },
    "AI 搜索": {
        "OpenAI News": "https://openai.com/news/rss.xml",
        "Google AI Blog": "https://blog.google/technology/ai/rss/",
        "Microsoft Bing Blog": "https://blogs.bing.com/search/feed",
    },
    "国内资讯": {
        "36Kr": "https://36kr.com/feed",
        "机器之心": "https://www.jiqizhixin.com/rss",
        "InfoQ AI": "https://xie.infoq.cn/rss/ai",
    },
}

EXPERT_PROFILES = [
    {
        "name": "Aleyda Solis",
        "title": "Aleyda Solis 最新观点入口",
        "url": "https://x.com/Aleyda",
        "note": "国际 SEO 顾问，适合跟踪技术 SEO、国际化 SEO 与 AI Search 相关讨论。",
    },
    {
        "name": "Lily Ray",
        "title": "Lily Ray 最新观点入口",
        "url": "https://x.com/lilyraynyc",
        "note": "关注 Google 更新、内容质量、E-E-A-T 与搜索可见性变化。",
    },
    {
        "name": "Zara Zhang",
        "title": "Zara Zhang 最新观点入口",
        "url": "https://x.com/zarazhangrui",
        "note": "适合关注 AI 产品、全球科技趋势与中文语境下的 AI 讨论。",
    },
]

WINDOW_DAYS = int(os.environ.get("WINDOW_DAYS", "14"))
MAX_ITEMS_PER_SOURCE = int(os.environ.get("MAX_ITEMS_PER_SOURCE", "12"))
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "20"))
USER_AGENT = (
    "Mozilla/5.0 (compatible; SEO-News-Monitor/2.0; "
    "+https://github.com/Bianca-hub-hub/seo-news-monitor)"
)


def normalize_text(raw):
    if not raw:
        return ""
    if isinstance(raw, list):
        raw = raw[0].get("value", "")
    text = re.sub(r"<[^>]+>", " ", str(raw))
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def strip_invalid_xml_chars(text):
    return re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", text)


def compact_error(error):
    if not error:
        return ""
    text = re.sub(r"\s+", " ", str(error)).strip()
    return text[:160]


def fallback_cn_summary(item, target_len=120):
    base = normalize_text(item.get("raw_summary", "")) or item["title"]
    source = item["source"]
    prefix = f"来自 {source}："
    body_limit = max(42, target_len - len(prefix) - 18)
    body = base[:body_limit].rstrip("，,；;。 ")
    if not body:
        body = item["title"]
    summary = f"{prefix}{body}。"
    if len(summary) < 72:
        summary += "可作为本期 SEO、GEO 或 AI 搜索变化的观察线索。"
    return summary[:150]


def build_ai_client():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or OpenAI is None:
        return None
    base_url = os.environ.get("OPENAI_BASE_URL")
    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url.strip())
    return OpenAI(api_key=api_key)


def generate_ai_summary(client, item):
    if client is None:
        return fallback_cn_summary(item)

    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    raw = normalize_text(item.get("raw_summary", ""))[:1200]
    prompt = (
        "你是中文 SEO 情报编辑。请从 SEO 增长、内容策略、搜索流量获取、"
        "AI Search/GEO 影响的视角，总结下面这条资讯。"
        "输出 80-140 字中文摘要，信息密度高、可执行，不要列表，不要营销话术。\n\n"
        f"来源：{item['source']}\n"
        f"分类：{item['category']}\n"
        f"标题：{item['title']}\n"
        f"正文片段：{raw or '无正文片段'}"
    )
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是严谨、克制、实用的中文 SEO 策略编辑。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        text = normalize_text(resp.choices[0].message.content or "")
        if 40 <= len(text) <= 180:
            return text[:160]
    except Exception as exc:
        print(f"[WARN] AI summary failed: {item['title'][:70]} -> {exc}")
    return fallback_cn_summary(item)


def parse_entry_date(entry, fallback):
    dt = entry.get("published_parsed") or entry.get("updated_parsed")
    if dt:
        try:
            return datetime(*dt[:6])
        except Exception:
            return fallback
    return fallback


def fetch_feed(url):
    response = requests.get(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    encoding = response.encoding or response.apparent_encoding or "utf-8"
    text = response.content.decode(encoding, errors="replace")
    text = strip_invalid_xml_chars(text)
    feed = feedparser.parse(text)
    return feed, content_type


def parse_feed_items(category, source, url, time_limit):
    results = []
    status = {
        "category": category,
        "source": source,
        "url": url,
        "state": "error",
        "count": 0,
        "error": "",
    }
    now = datetime.now()
    try:
        feed, content_type = fetch_feed(url)
        bozo_error = ""
        if getattr(feed, "bozo", False) and getattr(feed, "bozo_exception", None):
            bozo_error = compact_error(feed.bozo_exception)

        for entry in feed.entries[:MAX_ITEMS_PER_SOURCE * 3]:
            published_at = parse_entry_date(entry, now)
            if published_at < time_limit:
                continue
            link = (entry.get("link") or "").strip()
            title = normalize_text(entry.get("title") or "Untitled")
            if not link or not title:
                continue
            uid_seed = f"{category}|{source}|{link}"
            uid = hashlib.md5(uid_seed.encode("utf-8")).hexdigest()[:16]
            results.append(
                {
                    "id": uid,
                    "category": category,
                    "source": source,
                    "title": title,
                    "link": link,
                    "ts": int(published_at.timestamp()),
                    "date_str": published_at.strftime("%Y-%m-%d"),
                    "raw_summary": entry.get("summary") or entry.get("description", ""),
                    "is_video": "youtube" in link.lower() or "video" in normalize_text(entry.get("tags", "")).lower(),
                }
            )
            if len(results) >= MAX_ITEMS_PER_SOURCE:
                break

        status["count"] = len(results)
        if results and bozo_error:
            status["state"] = "warning"
            status["error"] = bozo_error
        elif results:
            status["state"] = "ok"
        else:
            status["state"] = "empty"
            status["error"] = bozo_error or f"未发现近 {WINDOW_DAYS} 天内的条目；content-type: {content_type or 'unknown'}"
    except Exception as exc:
        status["error"] = compact_error(exc)
        print(f"[WARN] fetch failed: {source} -> {exc}")
    return results, status


def inject_expert_cards(all_data):
    now = datetime.now()
    for profile in EXPERT_PROFILES:
        uid = hashlib.md5(f"expert-{profile['url']}".encode("utf-8")).hexdigest()[:16]
        all_data.append(
            {
                "id": uid,
                "category": "专家动态",
                "source": profile["name"],
                "title": profile["title"],
                "link": profile["url"],
                "ts": int(now.timestamp()),
                "date_str": now.strftime("%Y-%m-%d"),
                "raw_summary": profile["note"],
                "summary": profile["note"],
                "is_video": False,
            }
        )


def collect_data():
    time_limit = datetime.now() - timedelta(days=WINDOW_DAYS)
    all_data = []
    source_health = []

    for category, sources in RSS_SOURCES.items():
        for source, url in sources.items():
            items, status = parse_feed_items(category, source, url, time_limit)
            all_data.extend(items)
            source_health.append(status)

    unique_by_link = {}
    for item in sorted(all_data, key=lambda x: x["ts"], reverse=True):
        if item["link"] not in unique_by_link:
            unique_by_link[item["link"]] = item
    all_data = list(unique_by_link.values())

    client = build_ai_client()
    final_items = []
    for item in all_data:
        item["summary"] = item.get("summary") or generate_ai_summary(client, item)
        final_items.append(item)

    inject_expert_cards(final_items)
    final_items.sort(key=lambda x: x["ts"], reverse=True)
    return final_items, source_health


def status_label(state):
    labels = {
        "ok": ("正常", "status-ok"),
        "warning": ("有警告", "status-warning"),
        "empty": ("无新内容", "status-empty"),
        "error": ("异常", "status-error"),
    }
    return labels.get(state, ("未知", "status-error"))


def item_card(item):
    meta = CATEGORY_META[item["category"]]
    video = "<span class='badge danger'>VIDEO</span>" if item["is_video"] else ""
    return f"""
    <article class="news-card card-item" id="{item['id']}" data-ts="{item['ts']}" data-category="{html.escape(item['category'])}">
        <div class="card-top">
            <span class="source-pill" style="--accent:{meta['accent']}">{html.escape(item['source'])}</span>
            <span class="date">{item['date_str']}</span>
        </div>
        <h3><a href="{html.escape(item['link'])}" target="_blank" rel="noopener noreferrer">{html.escape(item['title'])}</a></h3>
        <p>{html.escape(item['summary'])}</p>
        <div class="card-actions">
            <button class="ghost-btn btn-read" type="button" onclick="toggleRead('{item['id']}', this)">标记已读</button>
            <a class="read-link" href="{html.escape(item['link'])}" target="_blank" rel="noopener noreferrer">阅读全文</a>
            {video}
        </div>
    </article>
    """


def category_section(category, items):
    meta = CATEGORY_META[category]
    cards = "".join(item_card(item) for item in items[:60])
    empty = "<div class='empty-state'>这段时间没有抓到新内容。</div>"
    return f"""
    <section class="category-section" id="{meta['slug']}">
        <div class="section-heading">
            <div>
                <span class="section-kicker" style="color:{meta['accent']}">{meta['icon']} {category}</span>
                <h2>{category}</h2>
            </div>
            <span class="count">{len(items)} 条</span>
        </div>
        <div class="news-grid">{cards or empty}</div>
    </section>
    """


def insight_rows(items):
    rows = []
    for category in CATEGORY_ORDER:
        picks = [item for item in items if item["category"] == category][:3]
        if not picks:
            continue
        links = "".join(
            f"<a href='{html.escape(item['link'])}' target='_blank' rel='noopener noreferrer'>{html.escape(item['title'])}</a>"
            for item in picks
        )
        meta = CATEGORY_META[category]
        rows.append(
            f"""
            <div class="insight-row">
                <div class="insight-icon" style="background:{meta['accent']}">{meta['icon']}</div>
                <div>
                    <div class="insight-title">{category}</div>
                    <div class="insight-links">{links}</div>
                </div>
            </div>
            """
        )
    return "".join(rows)


def health_rows(source_health):
    rows = []
    for item in source_health:
        label, klass = status_label(item["state"])
        rows.append(
            f"""
            <tr>
                <td>{html.escape(item['category'])}</td>
                <td><a href="{html.escape(item['url'])}" target="_blank" rel="noopener noreferrer">{html.escape(item['source'])}</a></td>
                <td><span class="status {klass}">{label}</span></td>
                <td>{item['count']}</td>
                <td class="error-cell">{html.escape(item['error'] or "-")}</td>
            </tr>
            """
        )
    return "".join(rows)


def render_dashboard(all_data, source_health):
    grouped = {category: [] for category in CATEGORY_ORDER}
    for item in all_data:
        grouped[item["category"]].append(item)

    total = len(all_data)
    active_sources = sum(1 for source in source_health if source["state"] in {"ok", "warning"})
    warning_sources = sum(1 for source in source_health if source["state"] in {"warning", "error"})
    latest_date = max((item["date_str"] for item in all_data), default="-")
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    nav_links = "".join(
        f"<a href='#{CATEGORY_META[cat]['slug']}'>{CATEGORY_META[cat]['icon']}<span>{cat}</span><strong>{len(grouped[cat])}</strong></a>"
        for cat in CATEGORY_ORDER
    )
    sections = "".join(category_section(category, grouped[category]) for category in CATEGORY_ORDER)

    full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SEO / GEO / AI Search 情报站</title>
    <style>
        :root {{
            --bg: #f6f7f9;
            --panel: #ffffff;
            --text: #172033;
            --muted: #667085;
            --line: #e4e7ec;
            --ink: #111827;
            --blue: #2563eb;
            --green: #059669;
            --orange: #d97706;
            --red: #dc2626;
            --shadow: 0 10px 28px rgba(15, 23, 42, 0.07);
        }}
        * {{ box-sizing: border-box; }}
        html {{ scroll-behavior: smooth; }}
        body {{
            margin: 0;
            background: var(--bg);
            color: var(--text);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Microsoft YaHei", Arial, sans-serif;
            letter-spacing: 0;
        }}
        a {{ color: inherit; }}
        .layout {{ display: grid; grid-template-columns: 260px minmax(0, 1fr); min-height: 100vh; }}
        .sidebar {{
            position: sticky;
            top: 0;
            height: 100vh;
            background: #fff;
            border-right: 1px solid var(--line);
            padding: 24px 18px;
        }}
        .brand {{ display: flex; gap: 10px; align-items: center; margin-bottom: 28px; }}
        .brand-mark {{ width: 34px; height: 34px; border-radius: 8px; background: var(--ink); color: #fff; display: grid; place-items: center; font-weight: 800; }}
        .brand-title {{ font-weight: 800; line-height: 1.2; }}
        .brand-subtitle {{ color: var(--muted); font-size: 12px; margin-top: 3px; }}
        .nav-label {{ color: #98a2b3; font-size: 12px; font-weight: 700; margin: 24px 8px 10px; }}
        .nav a {{
            display: grid;
            grid-template-columns: 26px 1fr auto;
            align-items: center;
            gap: 8px;
            padding: 10px 8px;
            border-radius: 8px;
            color: #475467;
            text-decoration: none;
            font-size: 14px;
        }}
        .nav a:hover {{ background: #f2f4f7; color: var(--ink); }}
        .nav strong {{ color: #98a2b3; font-size: 12px; }}
        .main {{ padding: 30px 36px 48px; min-width: 0; }}
        .hero {{
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            gap: 22px;
            align-items: end;
            margin-bottom: 22px;
        }}
        .eyebrow {{ color: var(--blue); font-size: 13px; font-weight: 800; margin-bottom: 8px; }}
        h1 {{ margin: 0; font-size: 30px; line-height: 1.15; }}
        .intro {{ margin: 10px 0 0; color: var(--muted); line-height: 1.7; max-width: 760px; }}
        .toolbar {{ display: flex; gap: 10px; align-items: center; justify-content: flex-end; flex-wrap: wrap; }}
        .search {{
            width: 260px;
            border: 1px solid var(--line);
            border-radius: 8px;
            background: #fff;
            padding: 10px 12px;
            font-size: 14px;
        }}
        .segmented {{ display: flex; gap: 4px; background: #e9edf3; padding: 4px; border-radius: 8px; }}
        .filter-btn {{
            border: 0;
            border-radius: 6px;
            padding: 8px 12px;
            background: transparent;
            color: #475467;
            cursor: pointer;
            font-weight: 700;
        }}
        .filter-btn.active {{ background: #fff; color: var(--ink); box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08); }}
        .stats {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin-bottom: 20px; }}
        .stat {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; }}
        .stat-label {{ color: var(--muted); font-size: 13px; }}
        .stat-value {{ font-size: 26px; font-weight: 800; margin-top: 6px; }}
        .panel-grid {{ display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(360px, 0.65fr); gap: 18px; align-items: start; margin-bottom: 28px; }}
        .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 18px; box-shadow: var(--shadow); }}
        .panel h2 {{ margin: 0 0 14px; font-size: 18px; }}
        .insight-row {{ display: grid; grid-template-columns: 36px 1fr; gap: 12px; padding: 12px 0; border-top: 1px solid #f0f2f5; }}
        .insight-row:first-of-type {{ border-top: 0; padding-top: 0; }}
        .insight-icon {{ width: 36px; height: 36px; border-radius: 8px; color: #fff; display: grid; place-items: center; font-size: 13px; font-weight: 800; }}
        .insight-title {{ font-weight: 800; margin-bottom: 5px; }}
        .insight-links {{ display: flex; flex-wrap: wrap; gap: 8px; }}
        .insight-links a {{ color: #344054; text-decoration: none; border-bottom: 1px solid #cfd6e1; line-height: 1.5; }}
        .insight-links a:hover {{ color: var(--blue); border-color: var(--blue); }}
        .health-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
        .health-table th, .health-table td {{ padding: 8px 6px; border-top: 1px solid #f0f2f5; text-align: left; vertical-align: top; }}
        .health-table th {{ color: var(--muted); font-size: 12px; }}
        .status {{ display: inline-flex; border-radius: 999px; padding: 3px 8px; font-size: 12px; font-weight: 800; white-space: nowrap; }}
        .status-ok {{ color: #067647; background: #ecfdf3; }}
        .status-warning {{ color: #b54708; background: #fffaeb; }}
        .status-empty {{ color: #475467; background: #f2f4f7; }}
        .status-error {{ color: #b42318; background: #fef3f2; }}
        .error-cell {{ max-width: 240px; color: #667085; word-break: break-word; }}
        .category-section {{ margin-top: 30px; scroll-margin-top: 18px; }}
        .section-heading {{ display: flex; justify-content: space-between; align-items: end; gap: 16px; margin-bottom: 14px; }}
        .section-kicker {{ font-size: 13px; font-weight: 900; }}
        .section-heading h2 {{ margin: 3px 0 0; font-size: 22px; }}
        .count {{ color: var(--muted); font-size: 13px; font-weight: 700; }}
        .news-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 14px; }}
        .news-card {{ background: #fff; border: 1px solid var(--line); border-radius: 8px; padding: 16px; min-height: 238px; display: flex; flex-direction: column; }}
        .news-card:hover {{ border-color: #b8c2d3; box-shadow: 0 8px 22px rgba(15, 23, 42, 0.08); }}
        .news-card.is-read {{ opacity: 0.56; }}
        .card-top {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 12px; }}
        .source-pill {{ color: var(--accent); background: color-mix(in srgb, var(--accent) 10%, white); border: 1px solid color-mix(in srgb, var(--accent) 18%, white); border-radius: 999px; padding: 4px 9px; font-size: 12px; font-weight: 800; max-width: 70%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
        .date {{ color: #98a2b3; font-size: 12px; white-space: nowrap; }}
        .news-card h3 {{ margin: 0 0 10px; font-size: 17px; line-height: 1.45; }}
        .news-card h3 a {{ text-decoration: none; }}
        .news-card h3 a:hover {{ color: var(--blue); }}
        .news-card p {{ margin: 0; color: #475467; line-height: 1.7; font-size: 14px; flex: 1; }}
        .card-actions {{ display: flex; align-items: center; gap: 10px; border-top: 1px solid #f0f2f5; padding-top: 12px; margin-top: 14px; }}
        .ghost-btn {{ border: 1px solid var(--line); background: #fff; color: #475467; border-radius: 6px; padding: 7px 10px; cursor: pointer; }}
        .read-link {{ margin-left: auto; background: var(--ink); color: #fff; text-decoration: none; border-radius: 6px; padding: 7px 10px; font-weight: 700; font-size: 13px; }}
        .badge.danger {{ color: #b42318; background: #fef3f2; border-radius: 999px; padding: 4px 8px; font-size: 11px; font-weight: 800; }}
        .empty-state {{ border: 1px dashed #cfd6e1; border-radius: 8px; padding: 18px; color: var(--muted); background: #fff; }}
        .footer-note {{ color: var(--muted); font-size: 12px; margin-top: 30px; }}
        @media (max-width: 980px) {{
            .layout {{ grid-template-columns: 1fr; }}
            .sidebar {{ position: static; height: auto; }}
            .nav {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }}
            .main {{ padding: 22px 16px 36px; }}
            .hero, .panel-grid {{ grid-template-columns: 1fr; }}
            .toolbar {{ justify-content: flex-start; }}
            .stats {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
            .search {{ width: 100%; }}
        }}
        @media (max-width: 560px) {{
            h1 {{ font-size: 25px; }}
            .stats, .news-grid, .nav {{ grid-template-columns: 1fr; }}
            .segmented {{ width: 100%; }}
            .filter-btn {{ flex: 1; }}
        }}
    </style>
</head>
<body>
    <div class="layout">
        <aside class="sidebar">
            <div class="brand">
                <div class="brand-mark">SEO</div>
                <div>
                    <div class="brand-title">SEO News Monitor</div>
                    <div class="brand-subtitle">自动抓取 · 情报筛选 · 信源体检</div>
                </div>
            </div>
            <div class="nav-label">分类导航</div>
            <nav class="nav">{nav_links}</nav>
            <div class="nav-label">专家入口</div>
            <nav class="nav">
                <a href="https://x.com/Aleyda" target="_blank" rel="noopener noreferrer"><span>𝕏</span><span>Aleyda Solis</span><strong></strong></a>
                <a href="https://x.com/lilyraynyc" target="_blank" rel="noopener noreferrer"><span>𝕏</span><span>Lily Ray</span><strong></strong></a>
                <a href="https://x.com/zarazhangrui" target="_blank" rel="noopener noreferrer"><span>𝕏</span><span>Zara Zhang</span><strong></strong></a>
            </nav>
        </aside>
        <main class="main">
            <header class="hero">
                <div>
                    <div class="eyebrow">SEO / GEO / AI SEARCH INTELLIGENCE</div>
                    <h1>每天给自己看的搜索情报站</h1>
                    <p class="intro">聚合你关心的海外 SEO、AI Search、GEO 与中文科技资讯。抓取失败会被记录，但不会再吞掉已经抓到的文章。</p>
                </div>
                <div class="toolbar">
                    <input id="searchInput" class="search" type="search" placeholder="搜索标题、来源或摘要">
                    <div class="segmented" aria-label="时间筛选">
                        <button class="filter-btn" type="button" data-days="3">3天</button>
                        <button class="filter-btn active" type="button" data-days="7">7天</button>
                        <button class="filter-btn" type="button" data-days="{WINDOW_DAYS}">{WINDOW_DAYS}天</button>
                    </div>
                </div>
            </header>
            <section class="stats">
                <div class="stat"><div class="stat-label">当前条目</div><div class="stat-value">{total}</div></div>
                <div class="stat"><div class="stat-label">可用信源</div><div class="stat-value">{active_sources}</div></div>
                <div class="stat"><div class="stat-label">需关注信源</div><div class="stat-value">{warning_sources}</div></div>
                <div class="stat"><div class="stat-label">最近更新</div><div class="stat-value" style="font-size:18px">{latest_date}</div></div>
            </section>
            <section class="panel-grid">
                <div class="panel">
                    <h2>本期重点</h2>
                    {insight_rows(all_data) or "<div class='empty-state'>暂时没有可展示的重点内容。</div>"}
                </div>
                <div class="panel">
                    <h2>信源健康</h2>
                    <table class="health-table">
                        <thead><tr><th>分类</th><th>信源</th><th>状态</th><th>条目</th><th>说明</th></tr></thead>
                        <tbody>{health_rows(source_health)}</tbody>
                    </table>
                </div>
            </section>
            {sections}
            <div class="footer-note">生成时间：{generated_at}，窗口：近 {WINDOW_DAYS} 天。可在 GitHub Actions 手动运行或按计划自动更新。</div>
        </main>
    </div>
    <script>
        const storeKey = "seo_news_monitor_v2";
        const state = JSON.parse(localStorage.getItem(storeKey) || '{{"read":[]}}');
        const cards = Array.from(document.querySelectorAll(".card-item"));
        const buttons = Array.from(document.querySelectorAll(".filter-btn"));
        const searchInput = document.getElementById("searchInput");
        let activeDays = 7;

        function save() {{
            localStorage.setItem(storeKey, JSON.stringify(state));
        }}

        function toggleRead(id, btn) {{
            if (!state.read.includes(id)) state.read.push(id);
            const card = document.getElementById(id);
            if (card) card.classList.add("is-read");
            btn.innerText = "已读";
            save();
        }}

        function applyFilters() {{
            const now = Math.floor(Date.now() / 1000);
            const query = (searchInput.value || "").trim().toLowerCase();
            cards.forEach(card => {{
                const inWindow = (now - Number(card.dataset.ts)) <= activeDays * 86400;
                const matches = !query || card.innerText.toLowerCase().includes(query);
                card.style.display = inWindow && matches ? "flex" : "none";
            }});
        }}

        state.read.forEach(id => {{
            const card = document.getElementById(id);
            if (!card) return;
            card.classList.add("is-read");
            const btn = card.querySelector(".btn-read");
            if (btn) btn.innerText = "已读";
        }});

        buttons.forEach(btn => {{
            btn.addEventListener("click", () => {{
                buttons.forEach(item => item.classList.remove("active"));
                btn.classList.add("active");
                activeDays = Number(btn.dataset.days);
                applyFilters();
            }});
        }});
        searchInput.addEventListener("input", applyFilters);
        applyFilters();
    </script>
</body>
</html>
"""

    with open("index.html", "w", encoding="utf-8") as file:
        file.write(full_html)


def fetch_data():
    all_data, source_health = collect_data()
    render_dashboard(all_data, source_health)
    print(f"[OK] Generated index.html with {len(all_data)} items")


if __name__ == "__main__":
    fetch_data()
