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


CATEGORY_ORDER = ["SEO 动态", "GEO 趋势", "AI 搜索", "专家动态"]

CATEGORY_META = {
    "SEO 动态": {"icon": "🔎", "slug": "seo", "accent": "#2563eb", "light": "#eff6ff", "label": "SEO"},
    "GEO 趋势": {"icon": "🌐", "slug": "geo", "accent": "#0891b2", "light": "#ecfeff", "label": "GEO"},
    "AI 搜索": {"icon": "🤖", "slug": "ai-search", "accent": "#7c3aed", "light": "#f5f3ff", "label": "AI"},
    "专家动态": {"icon": "★", "slug": "experts", "accent": "#374151", "light": "#f9fafb", "label": "Expert"},
}

RSS_SOURCES = {
    "SEO 动态": {
        "Google Search Central": "https://feeds.feedburner.com/blogspot/amDG",
        "Search Engine Land": "https://searchengineland.com/feed",
        "SEO Roundtable": "https://www.seroundtable.com/rss.xml",
        "Ahrefs Blog": "https://ahrefs.com/blog/feed/",
        "Backlinko": "https://backlinko.com/feed/",
        "Moz Blog": "https://moz.com/blog/feed",
        "Semrush Blog": "https://www.semrush.com/blog/feed/",
    },
    "GEO 趋势": {
        "Search Engine Journal": "https://www.searchenginejournal.com/feed/",
        "Aleyda Solis Blog": "https://www.aleydasolis.com/en/blog/feed/",
        "Onely Tech SEO": "https://www.onely.com/blog/feed/",
        "Wired AI": "https://www.wired.com/feed/tag/ai/latest/rss",
        "Search Engine Watch": "https://www.searchenginewatch.com/feed/",
    },
    "AI 搜索": {
        "OpenAI News": "https://openai.com/news/rss.xml",
        "Google AI Blog": "https://blog.google/technology/ai/rss/",
        "Anthropic News": "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml",
        "The Verge AI": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
        "MIT Technology Review": "https://www.technologyreview.com/feed/",
    },
}

EXPERT_PROFILES = [
    {"name": "Aleyda Solis", "role": "International SEO", "url": "https://x.com/Aleyda", "note": "International SEO consultant — technical SEO, crawling, AI Search impact."},
    {"name": "Lily Ray", "role": "E-E-A-T & Algo Updates", "url": "https://x.com/lilyraynyc", "note": "Tracks Google algorithm updates, content quality, E-E-A-T and visibility."},
    {"name": "Barry Schwartz", "role": "SEO News & Google Daily", "url": "https://x.com/rustybrick", "note": "Founder of SEO Roundtable, covers Google updates daily in real time."},
    {"name": "John Mueller", "role": "Google Search Advocate", "url": "https://x.com/JohnMu", "note": "Google Search Advocate — direct source on how Google Search works."},
    {"name": "Marie Haynes", "role": "Google Penalties & EAT", "url": "https://x.com/Marie_Haynes", "note": "Expert on Google penalties, quality issues, and E-E-A-T signals."},
    {"name": "Glenn Gabe", "role": "Algorithm Analysis", "url": "https://x.com/glenngabe", "note": "Deep-dives into Google algorithm updates and their traffic impact."},
    {"name": "Rand Fishkin", "role": "SEO & Audience Strategy", "url": "https://x.com/randfish", "note": "Founder of Moz & SparkToro. Broad takes on SEO, content and audience research."},
    {"name": "Kevin Indig", "role": "Growth & GEO", "url": "https://x.com/Kevin_Indig", "note": "Growth strategy, GEO and organic search at scale for tech companies."},
    {"name": "Brodie Clark", "role": "Google Features & SERP", "url": "https://x.com/brodieseo", "note": "Documents Google SERP feature changes with screenshots and analysis."},
    {"name": "Cyrus Shepard", "role": "On-page & Internal Links", "url": "https://x.com/CyrusShepard", "note": "On-page SEO, internal linking structure, and technical content strategy."},
    {"name": "Wil Reynolds", "role": "Search & AI Strategy", "url": "https://x.com/wilreynolds", "note": "CEO of Seer Interactive, covers AI's evolving role in search strategy."},
    {"name": "Zara Zhang", "role": "AI Products & Global", "url": "https://x.com/zarazhangrui", "note": "AI products, global tech trends, and cross-market AI strategy perspectives."},
]

WINDOW_DAYS = int(os.environ.get("WINDOW_DAYS", "14"))
MAX_ITEMS_PER_SOURCE = int(os.environ.get("MAX_ITEMS_PER_SOURCE", "12"))
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "20"))
USER_AGENT = "Mozilla/5.0 (compatible; SEO-News-Monitor/4.1; +https://github.com/Bianca-hub-hub/seo-news-monitor)"


def normalize_text(raw):
    if not raw:
        return ""
    if isinstance(raw, list):
        raw = raw[0].get("value", "")
    text = re.sub(r"<[^>]+>", " ", str(raw))
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def strip_invalid_xml_chars(text):
    return re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", text)


def compact_error(error):
    if not error:
        return ""
    return re.sub(r"\s+", " ", str(error)).strip()[:160]


def fallback_summary(item):
    base = normalize_text(item.get("raw_summary", "")) or item["title"]
    return f"From {item['source']}: {base[:120].rstrip('., ')}."


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
        return fallback_summary(item)

    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    raw = normalize_text(item.get("raw_summary", ""))[:1200]

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a concise SEO strategy editor."},
                {"role": "user", "content": (
                    "Summarize this news item from the angle of SEO, GEO, and AI Search impact. "
                    "1-2 sentences, high info density, no fluff.\n\n"
                    f"Source: {item['source']}\n"
                    f"Category: {item['category']}\n"
                    f"Title: {item['title']}\n"
                    f"Excerpt: {raw or 'N/A'}"
                )},
            ],
            temperature=0.2,
        )
        text = normalize_text(resp.choices[0].message.content or "")
        if 20 <= len(text) <= 300:
            return text[:280]
    except Exception as exc:
        print(f"[WARN] AI summary failed: {item['title'][:60]} -> {exc}")

    return fallback_summary(item)


def article_link(item):
    title_short = item["title"][:58] + ("…" if len(item["title"]) > 58 else "")
    return (
        '<a class="inline-ref" href="' + html.escape(item["link"]) + '" '
        'target="_blank" rel="noopener noreferrer" '
        'title="' + html.escape(item["title"]) + '">'
        '<span class="inline-ref-source">' + html.escape(item["source"]) + '</span>'
        + html.escape(title_short) +
        '</a>'
    )


def digest_date_range(items):
    if not items:
        return ""
    return f"{min(i['date_str'] for i in items)} ~ {max(i['date_str'] for i in items)}"


def fallback_digest(category, items):
    if not items:
        return {}

    top = items[:6]
    date_range = digest_date_range(items)

    lead = top[0]
    second = top[1] if len(top) > 1 else top[0]
    third = top[2] if len(top) > 2 else top[0]

    paragraphs = [
        {
            "html": (
                f"本周 {category} 领域最值得关注的是搜索体验继续向 AI 摘要、答案整合和多来源引用转移。"
                f"{article_link(lead)} 是一个值得优先阅读的信号，它说明搜索入口正在从传统蓝链列表，"
                "转向更强调语义理解、内容可信度和品牌可见性的复合型结果页。"
            )
        },
        {
            "html": (
                f"与此同时，内容策略的重点也在变化。{article_link(second)} 提醒我们，"
                "单纯围绕关键词扩写内容已经不够，网站需要把核心页面改造成更容易被搜索系统理解和引用的内容资产，"
                "包括清晰的问题结构、事实依据、作者可信度、内部链接和主题覆盖。"
            )
        },
        {
            "html": (
                f"从运营角度看，{article_link(third)} 可以作为本周复盘入口。"
                "接下来更值得关注的不是单篇文章能否排名，而是品牌、专家观点和高质量页面能否持续出现在 AI Search、"
                "精选摘要和搜索结果的关键位置。"
            )
        },
    ]

    return {
        "paragraphs": paragraphs,
        "date_range": date_range,
        "count": len(items),
        "ai_generated": False,
    }


def generate_weekly_digest(client, category, items):
    """
    Returns:
      {
        "paragraphs": [{"html": "..."}],
        "date_range": "...",
        "count": int,
        "ai_generated": bool
      }
    """
    if not items:
        return {}

    items = sorted(items, key=lambda x: x["ts"], reverse=True)
    date_range = digest_date_range(items)

    ref_map = {}
    source_lines = []

    for idx, item in enumerate(items[:18], 1):
        raw = normalize_text(item.get("summary") or item.get("raw_summary", ""))[:320]
        source_lines.append(
            f"[{idx}] 分类：{item['category']}｜来源：{item['source']}｜日期：{item['date_str']}｜"
            f"标题：{item['title']}｜摘要：{raw}"
        )
        ref_map[idx] = item

    if client is None:
        return fallback_digest(category, items)

    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    prompt = (
        f"你是资深 SEO / GEO / AI Search 行业分析师。\n"
        f"以下是「{category}」在 {date_range} 的资讯列表，共 {len(items)} 篇，下面最多列出 18 篇：\n\n"
        + "\n".join(source_lines)
        + "\n\n请写一篇中文本周综述，要求：\n"
        "1. 3 个自然段，总字数 300-500 字。\n"
        "2. 像行业分析，不要逐条罗列标题。\n"
        "3. 第一段讲本周最重要趋势，第二段讲对 SEO / 内容 / GEO 的影响，第三段讲网站运营接下来应该关注什么。\n"
        "4. 正文自然引用 2-4 篇文章，引用格式只能用 [REF:编号]，例如 [REF:2]。\n"
        "5. 不要编造来源里没有的信息。\n"
        "6. 只输出正文，不要标题。"
    )

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是专业、克制、有洞察力的中文 SEO / AI 搜索情报编辑。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.35,
            max_tokens=1200,
        )
        ai_text = (resp.choices[0].message.content or "").strip()
        if len(normalize_text(ai_text)) < 120:
            return fallback_digest(category, items)

        def replace_ref(match):
            idx = int(match.group(1))
            item = ref_map.get(idx)
            return article_link(item) if item else ""

        paragraphs = []
        for para in re.split(r"\n\s*\n|\n", ai_text):
            para = para.strip()
            if not para:
                continue
            safe = html.escape(para)
            safe = re.sub(r"\[REF:(\d+)\]", replace_ref, safe)
            paragraphs.append({"html": safe})

        if paragraphs:
            return {
                "paragraphs": paragraphs,
                "date_range": date_range,
                "count": len(items),
                "ai_generated": True,
            }

    except Exception as exc:
        print(f"[WARN] Digest API failed for {category}: {type(exc).__name__}: {exc}")

    return fallback_digest(category, items)


def parse_entry_date(entry, fallback):
    dt = entry.get("published_parsed") or entry.get("updated_parsed")
    if dt:
        try:
            return datetime(*dt[:6])
        except Exception:
            pass
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
    encoding = response.encoding or response.apparent_encoding or "utf-8"
    text = response.content.decode(encoding, errors="replace")
    text = strip_invalid_xml_chars(text)
    return feedparser.parse(text), response.headers.get("content-type", "")


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
        bozo_error = compact_error(getattr(feed, "bozo_exception", None)) if getattr(feed, "bozo", False) else ""

        for entry in feed.entries[:MAX_ITEMS_PER_SOURCE * 3]:
            published_at = parse_entry_date(entry, now)
            if published_at < time_limit:
                continue

            link = (entry.get("link") or "").strip()
            title = normalize_text(entry.get("title") or "Untitled")
            if not link or not title:
                continue

            uid = hashlib.md5(f"{category}|{source}|{link}".encode("utf-8")).hexdigest()[:16]

            results.append({
                "id": uid,
                "category": category,
                "source": source,
                "title": title,
                "link": link,
                "ts": int(published_at.timestamp()),
                "date_str": published_at.strftime("%Y-%m-%d"),
                "raw_summary": entry.get("summary") or entry.get("description", ""),
                "is_video": "youtube" in link.lower() or "video" in normalize_text(entry.get("tags", "")).lower(),
            })

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
            status["error"] = bozo_error or f"No items in last {WINDOW_DAYS} days; content-type: {content_type or 'unknown'}"

    except Exception as exc:
        status["error"] = compact_error(exc)
        print(f"[WARN] fetch failed: {source} -> {exc}")

    return results, status


def inject_expert_cards(all_data):
    now = datetime.now()

    for profile in EXPERT_PROFILES:
        uid = hashlib.md5(f"expert-{profile['url']}".encode("utf-8")).hexdigest()[:16]
        all_data.append({
            "id": uid,
            "category": "专家动态",
            "source": profile["name"],
            "title": f"{profile['name']} — {profile['role']}",
            "link": profile["url"],
            "ts": int(now.timestamp()),
            "date_str": now.strftime("%Y-%m-%d"),
            "raw_summary": profile["note"],
            "summary": profile["note"],
            "is_video": False,
            "role": profile["role"],
        })


def collect_data():
    time_limit = datetime.now() - timedelta(days=WINDOW_DAYS)
    all_data = []
    source_health = []

    for category, sources in RSS_SOURCES.items():
        for source, url in sources.items():
            items, status = parse_feed_items(category, source, url, time_limit)
            all_data.extend(items)
            source_health.append(status)

    seen = {}
    for item in sorted(all_data, key=lambda x: x["ts"], reverse=True):
        if item["link"] not in seen:
            seen[item["link"]] = item

    all_data = list(seen.values())

    client = build_ai_client()

    for item in all_data:
        item["summary"] = item.get("summary") or generate_ai_summary(client, item)

    news_items = sorted(all_data, key=lambda x: x["ts"], reverse=True)

    print(f"[INFO] Generating homepage weekly digest ({len(news_items)} items)...")
    home_digest = generate_weekly_digest(client, "SEO / GEO / AI 搜索", news_items)

    weekly_digests = {}
    for category in CATEGORY_ORDER:
        if category == "专家动态":
            continue
        cat_items = [item for item in news_items if item["category"] == category]
        print(f"[INFO] Generating weekly digest for {category} ({len(cat_items)} items)...")
        weekly_digests[category] = generate_weekly_digest(client, category, cat_items)

    inject_expert_cards(all_data)
    all_data.sort(key=lambda x: x["ts"], reverse=True)

    return all_data, source_health, weekly_digests, home_digest


def status_badge(state):
    return {
        "ok": '<span class="badge-ok">Normal</span>',
        "warning": '<span class="badge-warn">Warning</span>',
        "empty": '<span class="badge-empty">No items</span>',
        "error": '<span class="badge-error">Error</span>',
    }.get(state, '<span class="badge-error">Unknown</span>')


def item_card(item):
    meta = CATEGORY_META[item["category"]]
    video = "<span class='tag-video'>VIDEO</span>" if item["is_video"] else ""
    e = html.escape

    return (
        '<article class="card" id="' + item["id"] + '" data-ts="' + str(item["ts"]) + '">'
        '<div class="card-top">'
        '<span class="source-pill" style="--ac:' + meta["accent"] + ';--lc:' + meta["light"] + '">' + e(item["source"]) + '</span>'
        '<span class="card-date">' + item["date_str"] + '</span>'
        '</div>'
        '<h3><a href="' + e(item["link"]) + '" target="_blank" rel="noopener noreferrer">' + e(item["title"]) + '</a></h3>'
        '<p>' + e(item["summary"]) + '</p>'
        '<div class="card-foot">'
        '<button class="btn-mark" onclick="markRead(\'' + item["id"] + '\')">Mark read</button>'
        '<a class="btn-open" href="' + e(item["link"]) + '" target="_blank" rel="noopener noreferrer">Read → ' + video + '</a>'
        '</div>'
        '</article>'
    )


def expert_card(item):
    e = html.escape
    return (
        '<a class="expert-card" href="' + e(item["link"]) + '" target="_blank" rel="noopener noreferrer">'
        '<div class="expert-x">X</div>'
        '<div>'
        '<div class="expert-name">' + e(item["source"]) + '</div>'
        '<div class="expert-role">' + e(item.get("role", "")) + '</div>'
        '<div class="expert-note">' + e(item["summary"]) + '</div>'
        '</div>'
        '</a>'
    )


def digest_html(digest, accent="#2563eb", light="#eff6ff"):
    if not digest or not digest.get("paragraphs"):
        return ""

    badge = '<span class="digest-ai-badge">AI 综述</span>' if digest.get("ai_generated") else '<span class="digest-ai-badge digest-ai-fallback">自动整理</span>'
    paras = "".join('<p class="digest-para">' + p["html"] + '</p>' for p in digest["paragraphs"])

    return (
        '<div class="digest-box" style="--ac:' + accent + ';--lc:' + light + '">'
        '<div class="digest-header">'
        '<div class="digest-label">📋 本周综述 ' + badge + '</div>'
        '<div class="digest-meta">' + html.escape(digest.get("date_range", "")) + ' · 共 ' + str(digest.get("count", 0)) + ' 篇</div>'
        '</div>'
        '<div class="digest-body">' + paras + '</div>'
        '</div>'
    )


def page_section(category, items, digest=None):
    meta = CATEGORY_META[category]
    e = html.escape

    if category == "专家动态":
        inner = "".join(expert_card(item) for item in items)
        grid_class = "expert-grid"
        top_digest = ""
    else:
        inner = "".join(item_card(item) for item in items[:60])
        grid_class = "news-grid"
        top_digest = digest_html(digest, meta["accent"], meta["light"])

    if not inner:
        inner = "<div class='empty'>No content fetched for this window.</div>"

    return (
        '<section class="page-section" id="' + meta["slug"] + '">'
        '<div class="section-head">'
        '<span class="section-icon" style="background:' + meta["accent"] + '">' + meta["icon"] + '</span>'
        '<div>'
        '<div class="section-kicker" style="color:' + meta["accent"] + '">' + meta["label"] + '</div>'
        '<h2 class="section-title">' + e(category) + '</h2>'
        '</div>'
        '<span class="section-count">' + str(len(items)) + ' items</span>'
        '</div>'
        + top_digest +
        '<div class="' + grid_class + '">' + inner + '</div>'
        '</section>'
    )


def insight_rows(items):
    out = []

    for category in CATEGORY_ORDER:
        if category == "专家动态":
            continue

        picks = [item for item in items if item["category"] == category][:3]
        if not picks:
            continue

        meta = CATEGORY_META[category]
        links = "".join(
            '<a href="' + html.escape(item["link"]) + '" target="_blank" rel="noopener noreferrer">' + html.escape(item["title"]) + '</a>'
            for item in picks
        )

        out.append(
            '<div class="insight-row">'
            '<span class="ins-dot" style="background:' + meta["accent"] + '"></span>'
            '<div>'
            '<div class="ins-cat" style="color:' + meta["accent"] + '">' + meta["icon"] + ' ' + category + '</div>'
            '<div class="ins-links">' + links + '</div>'
            '</div>'
            '</div>'
        )

    return "".join(out) or "<div class='empty'>No highlights yet.</div>"


def health_rows(source_health):
    out = []

    for source in source_health:
        if source["state"] not in ("ok", "warning"):
            continue

        out.append(
            '<tr>'
            '<td class="td-muted">' + html.escape(source["category"]) + '</td>'
            '<td><a href="' + html.escape(source["url"]) + '" target="_blank" class="src-link">' + html.escape(source["source"]) + '</a></td>'
            '<td>' + status_badge(source["state"]) + '</td>'
            '<td class="td-num">' + str(source["count"]) + '</td>'
            '<td class="td-err">' + html.escape(source["error"] or "—") + '</td>'
            '</tr>'
        )

    if not out:
        return '<tr><td colspan="5" class="td-muted">No sources fetched content in this window.</td></tr>'

    return "".join(out)


def render_dashboard(all_data, source_health, weekly_digests, home_digest):
    grouped = {category: [] for category in CATEGORY_ORDER}

    for item in all_data:
        if item["category"] in grouped:
            grouped[item["category"]].append(item)

    news_items = [item for item in all_data if item["category"] != "专家动态"]
    total = len(news_items)
    active = sum(1 for s in source_health if s["state"] in {"ok", "warning"})
    errors = sum(1 for s in source_health if s["state"] in {"error", "empty"})
    latest = max((item["date_str"] for item in news_items), default="—")
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    nav = "".join(
        '<a href="#' + CATEGORY_META[cat]["slug"] + '">' + CATEGORY_META[cat]["icon"] + '<span>' + cat + '</span><strong>' + str(len(grouped[cat])) + '</strong></a>'
        for cat in CATEGORY_ORDER
    )

    sections = "".join(page_section(cat, grouped[cat], weekly_digests.get(cat)) for cat in CATEGORY_ORDER)

    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SEO Intelligence Monitor</title>
<style>
:root {{
  --bg:#f4f6fb;--surface:#fff;--surface2:#f0f3f9;--border:#e2e8f4;--border2:#c8d3e8;
  --text:#0f172a;--muted:#64748b;--dim:#94a3b8;--blue:#2563eb;--green:#059669;--red:#dc2626;
  --shadow:0 1px 3px rgba(15,23,42,.05),0 4px 14px rgba(15,23,42,.04);
}}
*{{box-sizing:border-box;margin:0;padding:0}}
html{{scroll-behavior:smooth}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",Arial,sans-serif;background:var(--bg);color:var(--text)}}
a{{color:inherit;text-decoration:none}}
.shell{{display:grid;grid-template-columns:240px 1fr;min-height:100vh}}
.sidebar{{position:sticky;top:0;height:100vh;background:#fff;border-right:1px solid var(--border);padding:20px 14px;overflow:auto}}
.brand{{display:flex;gap:10px;align-items:center;margin-bottom:22px}}
.brand-mark{{width:36px;height:36px;border-radius:9px;background:linear-gradient(135deg,#2563eb,#7c3aed);color:#fff;display:grid;place-items:center;font-weight:800}}
.brand-name{{font-weight:800;font-size:14px}}
.brand-sub{{color:var(--muted);font-size:11px;margin-top:2px}}
.nav-label{{font-size:11px;color:var(--dim);font-weight:800;text-transform:uppercase;margin:20px 8px 8px}}
.nav a{{display:grid;grid-template-columns:24px 1fr auto;gap:8px;align-items:center;padding:10px 8px;border-radius:8px;color:var(--muted);font-size:13px}}
.nav a:hover{{background:var(--surface2);color:var(--text)}}
.nav strong{{font-size:11px;color:var(--dim)}}
.main{{padding:32px 38px 60px;min-width:0}}
.eyebrow{{font-size:12px;color:var(--blue);font-weight:800;letter-spacing:.08em;text-transform:uppercase;margin-bottom:8px}}
h1{{font-size:30px;margin-bottom:8px}}
.page-sub{{color:var(--muted);font-size:14px;margin-bottom:24px;line-height:1.7}}
.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
.stat{{background:#fff;border:1px solid var(--border);border-radius:10px;padding:16px;box-shadow:var(--shadow)}}
.stat-label{{font-size:12px;color:var(--muted);font-weight:700}}
.stat-val{{font-size:26px;font-weight:800;margin-top:5px;color:var(--ac)}}
.stat-val.sm{{font-size:17px;margin-top:10px}}
.panel{{background:#fff;border:1px solid var(--border);border-radius:10px;padding:20px;box-shadow:var(--shadow);margin-bottom:18px}}
.panel-title{{font-weight:800;margin-bottom:14px}}
.digest-box{{background:var(--lc);border:1.5px solid var(--ac);border-radius:10px;padding:20px 22px;margin-bottom:22px;box-shadow:var(--shadow)}}
.digest-header{{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:14px;flex-wrap:wrap}}
.digest-label{{font-weight:900;color:var(--ac);display:flex;gap:8px;align-items:center}}
.digest-ai-badge{{font-size:11px;background:var(--ac);color:#fff;border-radius:5px;padding:3px 7px}}
.digest-ai-fallback{{background:var(--muted)}}
.digest-meta{{font-size:12px;color:var(--muted)}}
.digest-body{{font-size:15px;line-height:1.9;color:#243044}}
.digest-para{{margin-bottom:12px}}
.digest-para:last-child{{margin-bottom:0}}
.inline-ref{{display:inline-flex;align-items:center;gap:5px;background:#fff;border:1px solid rgba(37,99,235,.22);border-radius:6px;padding:2px 8px;margin:0 2px;color:var(--text);font-size:13px;vertical-align:middle;max-width:360px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.inline-ref:hover{{color:var(--ac);border-color:var(--ac)}}
.inline-ref-source{{font-size:10px;font-weight:800;color:var(--ac);background:rgba(37,99,235,.09);border-radius:4px;padding:1px 4px;flex-shrink:0}}
.insight-row{{display:flex;gap:12px;padding:12px 0;border-bottom:1px solid var(--border)}}
.insight-row:last-child{{border-bottom:0}}
.ins-dot{{width:8px;height:8px;border-radius:50%;margin-top:7px;flex-shrink:0}}
.ins-cat{{font-size:12px;font-weight:900;margin-bottom:6px}}
.ins-links{{display:flex;flex-direction:column;gap:6px}}
.ins-links a{{font-size:13px;line-height:1.45}}
.ins-links a:hover{{color:var(--blue)}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th,td{{padding:8px;border-bottom:1px solid var(--border);text-align:left;vertical-align:top}}
th{{color:var(--dim);font-size:11px;text-transform:uppercase}}
.td-muted{{color:var(--muted)}}
.td-num{{text-align:right;color:var(--muted)}}
.td-err{{color:var(--dim);max-width:220px;word-break:break-word}}
.badge-ok,.badge-warn,.badge-empty,.badge-error{{display:inline-flex;border-radius:99px;padding:2px 7px;font-size:11px;font-weight:800}}
.badge-ok{{color:#065f46;background:#dcfce7}}
.badge-warn{{color:#92400e;background:#fef3c7}}
.badge-empty{{color:var(--muted);background:var(--surface2)}}
.badge-error{{color:#991b1b;background:#fee2e2}}
.page-section{{margin-top:34px;scroll-margin-top:20px}}
.section-head{{display:flex;align-items:center;gap:14px;margin-bottom:18px}}
.section-icon{{width:40px;height:40px;border-radius:10px;display:grid;place-items:center;color:#fff;font-size:20px}}
.section-kicker{{font-size:11px;text-transform:uppercase;letter-spacing:.08em;font-weight:900}}
.section-title{{font-size:22px;font-weight:900}}
.section-count{{margin-left:auto;color:var(--muted);font-size:13px}}
.news-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}}
.card{{background:#fff;border:1px solid var(--border);border-radius:10px;padding:16px;display:flex;flex-direction:column;gap:10px;box-shadow:var(--shadow)}}
.card:hover{{border-color:var(--border2)}}
.card.is-read{{opacity:.45}}
.card-top{{display:flex;justify-content:space-between;gap:8px}}
.source-pill{{font-size:11px;font-weight:800;color:var(--ac);background:var(--lc);border-radius:5px;padding:3px 8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:65%}}
.card-date{{font-size:11px;color:var(--dim);white-space:nowrap}}
.card h3{{font-size:15px;line-height:1.45}}
.card h3 a:hover{{color:var(--blue)}}
.card p{{font-size:13px;color:var(--muted);line-height:1.65;flex:1}}
.card-foot{{display:flex;align-items:center;gap:8px;border-top:1px solid var(--border);padding-top:10px}}
.btn-mark{{border:1px solid var(--border2);background:#fff;color:var(--muted);border-radius:6px;padding:6px 10px;cursor:pointer}}
.btn-open{{margin-left:auto;background:var(--text);color:#fff;border-radius:6px;padding:6px 11px;font-size:12px;font-weight:700}}
.tag-video{{background:#fee2e2;color:#991b1b;font-size:10px;border-radius:4px;padding:1px 5px}}
.expert-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:14px}}
.expert-card{{background:#fff;border:1px solid var(--border);border-radius:10px;padding:16px;display:flex;gap:14px;box-shadow:var(--shadow)}}
.expert-card:hover{{border-color:var(--blue)}}
.expert-x{{width:36px;height:36px;border-radius:9px;background:#0f172a;color:#fff;display:grid;place-items:center;font-weight:900;flex-shrink:0}}
.expert-name{{font-weight:800;margin-bottom:3px}}
.expert-role{{color:var(--blue);font-size:12px;font-weight:700;margin-bottom:6px}}
.expert-note{{font-size:13px;color:var(--muted);line-height:1.55}}
.empty{{border:1px dashed var(--border2);border-radius:10px;padding:24px;color:var(--dim);text-align:center;grid-column:1/-1}}
.footer{{color:var(--dim);font-size:12px;margin-top:36px;padding-top:18px;border-top:1px solid var(--border)}}
@media(max-width:900px){{.shell{{grid-template-columns:1fr}}.sidebar{{position:static;height:auto}}.main{{padding:22px 16px 40px}}.stats{{grid-template-columns:repeat(2,1fr)}}}}
@media(max-width:560px){{.stats,.news-grid,.expert-grid{{grid-template-columns:1fr}}h1{{font-size:24px}}}}
</style>
</head>
<body>
<div class="shell">
<aside class="sidebar">
  <div class="brand">
    <div class="brand-mark">SEO</div>
    <div>
      <div class="brand-name">SEO Monitor</div>
      <div class="brand-sub">Auto-fetch · Daily</div>
    </div>
  </div>
  <div class="nav-label">Categories</div>
  <nav class="nav">{nav}</nav>
</aside>

<main class="main">
  <div class="eyebrow">SEO / GEO / AI Search Intelligence</div>
  <h1>Search Monitor</h1>
  <p class="page-sub">Your personal feed for SEO, AI Search & GEO updates. Auto-fetched daily and summarized into a weekly intelligence brief.</p>

  <section class="stats">
    <div class="stat" style="--ac:#2563eb"><div class="stat-label">Total Articles</div><div class="stat-val">{total}</div></div>
    <div class="stat" style="--ac:#059669"><div class="stat-label">Active Sources</div><div class="stat-val">{active}</div></div>
    <div class="stat" style="--ac:#dc2626"><div class="stat-label">Need Attention</div><div class="stat-val">{errors}</div></div>
    <div class="stat" style="--ac:#7c3aed"><div class="stat-label">Latest Item</div><div class="stat-val sm">{latest}</div></div>
  </section>

  {digest_html(home_digest, "#2563eb", "#eff6ff")}

  <section class="panel">
    <div class="panel-title">Source Health — Active Sources Only</div>
    <table>
      <thead><tr><th>Category</th><th>Source</th><th>Status</th><th>Items</th><th>Note</th></tr></thead>
      <tbody>{health_rows(source_health)}</tbody>
    </table>
  </section>

  <section class="panel">
    <div class="panel-title">This Week's Highlights</div>
    {insight_rows(news_items)}
  </section>

  {sections}

  <div class="footer">Generated: {generated_at} · Window: last {WINDOW_DAYS} days · Auto-updated via GitHub Actions</div>
</main>
</div>

<script>
const STORE = "seo_monitor_read_v1";
let state;
try {{
  state = JSON.parse(localStorage.getItem(STORE) || '{{"read":[]}}');
}} catch (_) {{
  state = {{"read":[]}};
}}

function save() {{
  localStorage.setItem(STORE, JSON.stringify(state));
}}

function markRead(id) {{
  if (!state.read.includes(id)) state.read.push(id);
  const card = document.getElementById(id);
  if (card) card.classList.add("is-read");
  save();
}}

state.read.forEach(id => {{
  const card = document.getElementById(id);
  if (card) card.classList.add("is-read");
}});
</script>
</body>
</html>
"""

    with open("index.html", "w", encoding="utf-8") as file:
        file.write(page)


def fetch_data():
    all_data, source_health, weekly_digests, home_digest = collect_data()
    render_dashboard(all_data, source_health, weekly_digests, home_digest)
    print(f"[OK] Generated index.html with {len(all_data)} items")


if __name__ == "__main__":
    fetch_data()
