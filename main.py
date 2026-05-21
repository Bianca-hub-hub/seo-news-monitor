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
    "SEO 动态": {"icon": "🔎", "slug": "seo",       "accent": "#2563eb", "light": "#eff6ff", "label": "SEO"},
    "GEO 趋势": {"icon": "🌐", "slug": "geo",       "accent": "#0891b2", "light": "#ecfeff", "label": "GEO"},
    "AI 搜索":  {"icon": "🤖", "slug": "ai-search", "accent": "#7c3aed", "light": "#f5f3ff", "label": "AI"},
    "专家动态": {"icon": "★",  "slug": "experts",   "accent": "#374151", "light": "#f9fafb", "label": "Expert"},
}

RSS_SOURCES = {
    "SEO 动态": {
        # feedburner 代理的官方 Google Search Central feed
        "Google Search Central": "https://feeds.feedburner.com/blogspot/amDG",
        "Search Engine Land":    "https://searchengineland.com/feed",
        "SEO Roundtable":        "https://www.seroundtable.com/rss.xml",
        "Ahrefs Blog":           "https://ahrefs.com/blog/feed/",
        "Backlinko":             "https://backlinko.com/feed/",
        "Moz Blog":              "https://moz.com/blog/feed",
        "Semrush Blog":          "https://www.semrush.com/blog/feed/",
    },
    "GEO 趋势": {
        "Search Engine Journal": "https://www.searchenginejournal.com/feed/",
        "Aleyda Solis Blog":     "https://www.aleydasolis.com/en/blog/feed/",
        "Onely Tech SEO":        "https://www.onely.com/blog/feed/",
        # Perplexity 无公开 RSS，替换为 Wired AI
        "Wired AI":              "https://www.wired.com/feed/tag/ai/latest/rss",
        # BrightEdge 无公开 RSS，替换为 Search Engine Watch
        "Search Engine Watch":   "https://www.searchenginewatch.com/feed/",
    },
    "AI 搜索": {
        "OpenAI News":           "https://openai.com/news/rss.xml",
        "Google AI Blog":        "https://blog.google/technology/ai/rss/",
        # Anthropic 无官方 RSS，使用社区维护的抓取 feed
        "Anthropic News":        "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml",
        # The Verge AI 正确 URL
        "The Verge AI":          "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
        "MIT Technology Review": "https://www.technologyreview.com/feed/",
    },
}

EXPERT_PROFILES = [
    {"name": "Aleyda Solis",   "role": "International SEO",        "url": "https://x.com/Aleyda",       "note": "International SEO consultant — technical SEO, crawling, AI Search impact."},
    {"name": "Lily Ray",       "role": "E-E-A-T & Algo Updates",   "url": "https://x.com/lilyraynyc",   "note": "Tracks Google algorithm updates, content quality, E-E-A-T and visibility."},
    {"name": "Barry Schwartz", "role": "SEO News & Google Daily",  "url": "https://x.com/rustybrick",   "note": "Founder of SEO Roundtable, covers Google updates daily in real time."},
    {"name": "John Mueller",   "role": "Google Search Advocate",   "url": "https://x.com/JohnMu",       "note": "Google Search Advocate — direct source on how Google Search works."},
    {"name": "Marie Haynes",   "role": "Google Penalties & EAT",  "url": "https://x.com/Marie_Haynes", "note": "Expert on Google penalties, quality issues, and E-E-A-T signals."},
    {"name": "Glenn Gabe",     "role": "Algorithm Analysis",       "url": "https://x.com/glenngabe",    "note": "Deep-dives into Google algorithm updates and their traffic impact."},
    {"name": "Rand Fishkin",   "role": "SEO & Audience Strategy",  "url": "https://x.com/randfish",     "note": "Founder of Moz & SparkToro. Broad takes on SEO, content and audience research."},
    {"name": "Kevin Indig",    "role": "Growth & GEO",             "url": "https://x.com/Kevin_Indig",  "note": "Growth strategy, GEO and organic search at scale for tech companies."},
    {"name": "Brodie Clark",   "role": "Google Features & SERP",   "url": "https://x.com/brodieseo",    "note": "Documents Google SERP feature changes with screenshots and analysis."},
    {"name": "Cyrus Shepard",  "role": "On-page & Internal Links", "url": "https://x.com/CyrusShepard", "note": "On-page SEO, internal linking structure, and technical content strategy."},
    {"name": "Wil Reynolds",   "role": "Search & AI Strategy",     "url": "https://x.com/wilreynolds",  "note": "CEO of Seer Interactive, covers AI's evolving role in search strategy."},
    {"name": "Zara Zhang",     "role": "AI Products & Global",     "url": "https://x.com/zarazhangrui", "note": "AI products, global tech trends, and cross-market AI strategy perspectives."},
]

WINDOW_DAYS = int(os.environ.get("WINDOW_DAYS", "14"))
MAX_ITEMS_PER_SOURCE = int(os.environ.get("MAX_ITEMS_PER_SOURCE", "12"))
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "20"))
USER_AGENT = "Mozilla/5.0 (compatible; SEO-News-Monitor/4.0; +https://github.com/Bianca-hub-hub/seo-news-monitor)"


# ── Utilities ────────────────────────────────────────────────────────────────

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
    return f"From {item['source']}: {base[:110].rstrip('., ')}."


def build_ai_client():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or OpenAI is None:
        return None
    base_url = os.environ.get("OPENAI_BASE_URL")
    return OpenAI(api_key=api_key, **({"base_url": base_url.strip()} if base_url else {}))


def generate_ai_summary(client, item):
    if client is None:
        return fallback_summary(item)
    model = os.environ.get("OPENAI_MODEL", "claude-sonnet-4-6")
    raw = normalize_text(item.get("raw_summary", ""))[:1200]
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a concise SEO strategy editor."},
                {"role": "user", "content": (
                    "Summarize this news item from the angle of SEO, GEO, and AI Search impact. "
                    "1-2 sentences, high info density, no fluff.\n\n"
                    f"Source: {item['source']}\nTitle: {item['title']}\nExcerpt: {raw or 'N/A'}"
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


def generate_weekly_digest(client, category, items):
    """
    Returns a dict:
      {
        "paragraphs": [{"text": str, "refs": [{"title":str,"link":str,"source":str}]}],
        "date_range": str,
        "count": int,
      }
    Each paragraph is an analysis chunk followed by its source references.
    """
    if not items:
        return {}

    date_range = f"{min(i['date_str'] for i in items)} ~ {max(i['date_str'] for i in items)}"
    result_base = {"date_range": date_range, "count": len(items)}

    # Build input for AI: include title + summary + link index
    lines = []
    ref_map = {}  # index -> item
    for idx, i in enumerate(items[:15], 1):
        raw = normalize_text(i.get("raw_summary", "") or i.get("summary", ""))[:400]
        lines.append(f"[{idx}] 来源:{i['source']} | 标题:{i['title']} | 摘要:{raw}")
        ref_map[idx] = i

    digest_input = "\n".join(lines)
    model = os.environ.get("OPENAI_MODEL", "claude-sonnet-4-6")

    prompt = (
        f"你是资深SEO/AI搜索行业分析师。以下是「{category}」板块本周（{date_range}）的文章（编号[1]-[{len(ref_map)}]）：\n\n"
        f"{digest_input}\n\n"
        "请写一篇中文本周综述，格式要求：\n"
        "- 分2-4个段落，每段聚焦一个主题/趋势\n"
        "- 每段结尾用 [引用编号] 标注来源，如：...值得关注。[1][3]\n"
        "- 语言专业简洁，有分析视角，指出对SEO从业者的实际影响\n"
        "- 总字数200-400字\n"
        "- 只输出正文段落，不要标题，不要bullet points\n"
        "- 段落之间用空行分隔"
    )

    ai_text = ""
    if client is not None:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "你是专业的SEO/AI搜索行业分析师，写作风格简洁专业。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.35,
                max_tokens=800,
            )
            ai_text = normalize_text(resp.choices[0].message.content or "")
            print(f"[OK] Digest generated for {category}: {len(ai_text)} chars")
        except Exception as exc:
            print(f"[WARN] Weekly digest API failed for {category}: {type(exc).__name__}: {exc}")

    if not ai_text or len(ai_text) < 50:
        # Structured fallback: group items by source and write a basic digest
        by_source = {}
        for i in items[:12]:
            by_source.setdefault(i["source"], []).append(i)
        paras = []
        for src, src_items in list(by_source.items())[:4]:
            chunk_titles = "、".join("《" + x["title"][:40] + "》" for x in src_items[:2])
            paras.append({
                "text": f"{src} 本周发布了关于 {chunk_titles} 等内容。",
                "refs": [{"title": x["title"], "link": x["link"], "source": x["source"]} for x in src_items[:3]],
            })
        result_base["paragraphs"] = paras
        result_base["ai_generated"] = False
        return result_base

    # Parse AI text: split on blank lines into paragraphs, extract [N] refs
    import re as _re
    raw_paras = [p.strip() for p in _re.split(r"\n\s*\n", ai_text) if p.strip()]
    paragraphs = []
    for para in raw_paras:
        ref_indices = [int(m) for m in _re.findall(r"\[(\d+)\]", para)]
        clean_text = _re.sub(r"\[\d+\]", "", para).strip()
        refs = []
        seen_links = set()
        for idx in ref_indices:
            item = ref_map.get(idx)
            if item and item["link"] not in seen_links:
                refs.append({"title": item["title"], "link": item["link"], "source": item["source"]})
                seen_links.add(item["link"])
        paragraphs.append({"text": clean_text, "refs": refs})

    result_base["paragraphs"] = paragraphs
    result_base["ai_generated"] = True
    return result_base


def parse_entry_date(entry, fallback):
    dt = entry.get("published_parsed") or entry.get("updated_parsed")
    if dt:
        try:
            return datetime(*dt[:6])
        except Exception:
            pass
    return fallback


def fetch_feed(url):
    r = requests.get(url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, */*"}, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    enc = r.encoding or r.apparent_encoding or "utf-8"
    text = strip_invalid_xml_chars(r.content.decode(enc, errors="replace"))
    return feedparser.parse(text), r.headers.get("content-type", "")


def parse_feed_items(category, source, url, time_limit):
    results = []
    status = {"category": category, "source": source, "url": url, "state": "error", "count": 0, "error": ""}
    now = datetime.now()
    try:
        feed, _ = fetch_feed(url)
        bozo_err = compact_error(getattr(feed, "bozo_exception", None)) if getattr(feed, "bozo", False) else ""
        for entry in feed.entries[:MAX_ITEMS_PER_SOURCE * 3]:
            pub = parse_entry_date(entry, now)
            if pub < time_limit:
                continue
            link = (entry.get("link") or "").strip()
            title = normalize_text(entry.get("title") or "Untitled")
            if not link or not title:
                continue
            uid = hashlib.md5(f"{category}|{source}|{link}".encode()).hexdigest()[:16]
            results.append({
                "id": uid, "category": category, "source": source, "title": title, "link": link,
                "ts": int(pub.timestamp()), "date_str": pub.strftime("%Y-%m-%d"),
                "raw_summary": entry.get("summary") or entry.get("description", ""),
                "is_video": "youtube" in link.lower(),
            })
            if len(results) >= MAX_ITEMS_PER_SOURCE:
                break
        status["count"] = len(results)
        if results and bozo_err:
            status["state"], status["error"] = "warning", bozo_err
        elif results:
            status["state"] = "ok"
        else:
            status["state"] = "empty"
            status["error"] = bozo_err or f"No items in last {WINDOW_DAYS} days"
    except Exception as exc:
        status["error"] = compact_error(exc)
        print(f"[WARN] fetch failed: {source} -> {exc}")
    return results, status


def inject_expert_cards(all_data):
    now = datetime.now()
    for p in EXPERT_PROFILES:
        uid = hashlib.md5(f"expert-{p['url']}".encode()).hexdigest()[:16]
        all_data.append({
            "id": uid, "category": "专家动态", "source": p["name"],
            "title": f"{p['name']} — {p['role']}", "link": p["url"],
            "ts": int(now.timestamp()), "date_str": now.strftime("%Y-%m-%d"),
            "raw_summary": p["note"], "summary": p["note"],
            "is_video": False, "role": p["role"],
        })


def collect_data():
    time_limit = datetime.now() - timedelta(days=WINDOW_DAYS)
    all_data, source_health = [], []
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
    inject_expert_cards(all_data)
    all_data.sort(key=lambda x: x["ts"], reverse=True)
    # Generate per-category weekly digests
    weekly_digests = {}
    for cat in CATEGORY_ORDER:
        if cat == "专家动态":
            continue
        cat_items = [i for i in all_data if i["category"] == cat]
        print(f"[INFO] Generating weekly digest for {cat} ({len(cat_items)} items)...")
        weekly_digests[cat] = generate_weekly_digest(client, cat, cat_items)
    return all_data, source_health, weekly_digests


# ── HTML helpers ─────────────────────────────────────────────────────────────

def status_badge(state):
    return {
        "ok":      ('<span class="badge-ok">Normal</span>'),
        "warning": ('<span class="badge-warn">Warning</span>'),
        "empty":   ('<span class="badge-empty">No items</span>'),
        "error":   ('<span class="badge-error">Error</span>'),
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
        '<button class="btn-mark" onclick="toggleRead(\'' + item["id"] + '\',this)">Mark read</button>'
        '<a class="btn-open" href="' + e(item["link"]) + '" target="_blank" rel="noopener noreferrer">Read &rarr;' + video + '</a>'
        '</div>'
        '</article>'
    )


def expert_card(item):
    e = html.escape
    return (
        '<a class="expert-card" href="' + e(item["link"]) + '" target="_blank" rel="noopener noreferrer">'
        '<div class="expert-x">X</div>'
        '<div class="expert-info">'
        '<div class="expert-name">' + e(item["source"]) + '</div>'
        '<div class="expert-role">' + e(item.get("role", "")) + '</div>'
        '<div class="expert-note">' + e(item["summary"]) + '</div>'
        '</div>'
        '</a>'
    )


def page_section(category, items, digest=""):
    meta = CATEGORY_META[category]
    e = html.escape
    if category == "专家动态":
        inner = "".join(expert_card(i) for i in items)
        grid_cls = "expert-grid"
        digest_html = ""
    else:
        inner = "".join(item_card(i) for i in items[:60])
        grid_cls = "news-grid"
        if digest:
            date_range = ""
            if items:
                dates = [i["date_str"] for i in items]
                date_range = f"{min(dates)} ~ {max(dates)}"
            digest_html = (
                '<div class="digest-box" style="--ac:' + meta["accent"] + ';--lc:' + meta["light"] + '">'
                '<div class="digest-label">📋 本周综述 <span class="digest-date">' + date_range + '</span></div>'
                '<div class="digest-body">' + e(digest) + '</div>'
                '</div>'
            )
        else:
            digest_html = ""
    if not inner:
        inner = "<div class='empty'>No content fetched for this window.</div>"
    return (
        '<section class="page-section" id="page-' + meta["slug"] + '" style="display:none">'
        '<div class="section-head">'
        '<span class="section-icon" style="background:' + meta["accent"] + '">' + meta["icon"] + '</span>'
        '<div>'
        '<div class="section-kicker" style="color:' + meta["accent"] + '">' + meta["label"] + '</div>'
        '<h2 class="section-title">' + e(category) + '</h2>'
        '</div>'
        '<span class="section-count">' + str(len(items)) + ' items</span>'
        '</div>'
        + digest_html +
        '<div class="' + grid_cls + '">' + inner + '</div>'
        '</section>'
    )


def insight_rows(items):
    out = []
    for cat in CATEGORY_ORDER:
        if cat == "专家动态":
            continue
        picks = [i for i in items if i["category"] == cat][:3]
        if not picks:
            continue
        meta = CATEGORY_META[cat]
        e = html.escape
        links = "".join(
            '<a href="' + e(i["link"]) + '" target="_blank" rel="noopener noreferrer">' + e(i["title"]) + '</a>'
            for i in picks
        )
        out.append(
            '<div class="insight-row">'
            '<span class="ins-dot" style="background:' + meta["accent"] + '"></span>'
            '<div>'
            '<div class="ins-cat" style="color:' + meta["accent"] + '">' + meta["icon"] + ' ' + cat + '</div>'
            '<div class="ins-links">' + links + '</div>'
            '</div>'
            '</div>'
        )
    return "".join(out) or "<div class='empty'>No highlights yet.</div>"


def health_rows(source_health):
    """Only show sources that have fetched items (ok/warning) — hide empty/error/no-update ones."""
    out = []
    e = html.escape
    for s in source_health:
        if s["state"] not in ("ok", "warning"):
            continue  # only show sources that actually got content
        out.append(
            '<tr>'
            '<td class="td-muted">' + e(s["category"]) + '</td>'
            '<td><a href="' + e(s["url"]) + '" target="_blank" class="src-link">' + e(s["source"]) + '</a></td>'
            '<td>' + status_badge(s["state"]) + '</td>'
            '<td class="td-num">' + str(s["count"]) + '</td>'
            '<td class="td-err">' + e(s["error"] or "—") + '</td>'
            '</tr>'
        )
    if not out:
        return '<tr><td colspan="5" style="color:var(--dim);padding:12px 8px;font-size:12px">No sources fetched content in this window.</td></tr>'
    return "".join(out)


# ── Main render ───────────────────────────────────────────────────────────────

def render_dashboard(all_data, source_health, weekly_digests):
    grouped = {cat: [] for cat in CATEGORY_ORDER}
    for item in all_data:
        if item["category"] in grouped:
            grouped[item["category"]].append(item)

    total = len([i for i in all_data if i["category"] != "专家动态"])
    active = sum(1 for s in source_health if s["state"] in {"ok", "warning"})
    errors = sum(1 for s in source_health if s["state"] in {"error", "empty"})
    latest = max((i["date_str"] for i in all_data if i["category"] != "专家动态"), default="—")
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    nav_tabs_html = ""
    for cat in CATEGORY_ORDER:
        meta = CATEGORY_META[cat]
        cnt = len(grouped[cat])
        nav_tabs_html += (
            '<button class="nav-tab" data-target="page-' + meta["slug"] + '" '
            'onclick="showPage(\'' + meta["slug"] + '\')">'
            + meta["icon"] + ' ' + cat +
            ' <span class="nav-cnt">' + str(cnt) + '</span>'
            '</button>'
        )

    expert_sidebar_html = ""
    for ex in EXPERT_PROFILES:
        expert_sidebar_html += (
            '<a class="expert-sl" href="' + html.escape(ex["url"]) + '" target="_blank" rel="noopener noreferrer">'
            '<span class="xi">X</span>' + html.escape(ex["name"]) +
            '</a>'
        )

    sections_html = "".join(page_section(cat, grouped[cat], weekly_digests.get(cat, "")) for cat in CATEGORY_ORDER)

    page = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SEO Intelligence Monitor</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#f4f6fb;--surface:#fff;--surface2:#f0f3f9;
  --border:#e2e8f4;--border2:#c8d3e8;
  --text:#0f172a;--muted:#64748b;--dim:#94a3b8;
  --blue:#2563eb;--green:#059669;--red:#dc2626;--purple:#7c3aed;
  --sw:228px;--r:12px;--rs:8px;
  --font:'Plus Jakarta Sans',sans-serif;--mono:'JetBrains Mono',monospace;
  --shadow:0 1px 3px rgba(15,23,42,.05),0 4px 14px rgba(15,23,42,.04);
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{font-family:var(--font);background:var(--bg);color:var(--text);min-height:100vh}
a{color:inherit;text-decoration:none}

.shell{display:grid;grid-template-columns:var(--sw) 1fr;min-height:100vh}

/* Sidebar */
.sidebar{
  position:sticky;top:0;height:100vh;overflow-y:auto;
  background:var(--surface);border-right:1px solid var(--border);
  padding:18px 10px;display:flex;flex-direction:column;gap:2px;
}
.brand{display:flex;align-items:center;gap:10px;padding:4px 8px 18px;border-bottom:1px solid var(--border);margin-bottom:8px}
.brand-mark{
  width:34px;height:34px;border-radius:9px;
  background:linear-gradient(135deg,#2563eb,#7c3aed);
  color:#fff;font-weight:800;font-size:11px;letter-spacing:-.3px;
  display:grid;place-items:center;flex-shrink:0;
}
.brand-name{font-size:13px;font-weight:700}
.brand-sub{font-size:10px;color:var(--muted);margin-top:1px;font-family:var(--mono)}
.slabel{font-size:10px;font-weight:700;letter-spacing:.1em;color:var(--dim);text-transform:uppercase;padding:14px 8px 4px;font-family:var(--mono)}
.home-btn{
  width:100%;text-align:left;border:none;
  background:var(--blue);color:#fff;
  display:flex;align-items:center;gap:8px;
  padding:10px 12px;border-radius:var(--rs);
  font-family:var(--font);font-size:13px;font-weight:700;
  cursor:pointer;transition:all .15s;margin-bottom:4px;
}
.home-btn:hover{background:#1d4ed8}
.home-btn.off{background:transparent;color:var(--muted);font-weight:500}
.home-btn.off:hover{background:var(--surface2);color:var(--text)}
.nav-tab{
  width:100%;text-align:left;border:none;background:transparent;
  display:flex;align-items:center;gap:8px;
  padding:9px 10px;border-radius:var(--rs);
  font-family:var(--font);font-size:13px;font-weight:500;color:var(--muted);
  cursor:pointer;transition:all .15s;
}
.nav-tab:hover{background:var(--surface2);color:var(--text)}
.nav-tab.active{background:#eff6ff;color:var(--blue);font-weight:700}
.nav-cnt{margin-left:auto;font-size:11px;font-family:var(--mono);background:var(--surface2);color:var(--dim);border-radius:99px;padding:1px 7px}
.nav-tab.active .nav-cnt{background:#dbeafe;color:var(--blue)}
.expert-sl{
  display:flex;align-items:center;gap:8px;
  padding:7px 10px;border-radius:var(--rs);
  font-size:12.5px;color:var(--muted);transition:all .15s;
}
.expert-sl:hover{background:var(--surface2);color:var(--text)}
.xi{font-size:11px;opacity:.45;width:16px;text-align:center}

/* Main */
.main{padding:32px 38px 60px;min-width:0}

/* Home */
.eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.1em;color:var(--blue);text-transform:uppercase;margin-bottom:8px}
.page-title{font-size:28px;font-weight:800;line-height:1.2;margin-bottom:6px}
.page-sub{color:var(--muted);font-size:14px;margin-bottom:28px}

.toolbar{display:flex;gap:10px;align-items:center;margin-bottom:22px;flex-wrap:wrap}
.search-box{
  flex:1;min-width:180px;border:1px solid var(--border2);border-radius:var(--rs);
  background:var(--surface);color:var(--text);font-family:var(--font);font-size:13px;
  padding:9px 12px;outline:none;transition:border-color .15s;
}
.search-box:focus{border-color:var(--blue)}
.search-box::placeholder{color:var(--dim)}
.day-tabs{display:flex;background:var(--surface2);border-radius:var(--rs);padding:3px;gap:2px}
.day-tab{
  border:none;background:transparent;color:var(--muted);
  border-radius:6px;padding:6px 12px;font-size:13px;font-weight:600;
  cursor:pointer;font-family:var(--font);transition:all .15s;
}
.day-tab.active{background:var(--surface);color:var(--text);box-shadow:0 1px 3px rgba(0,0,0,.08)}

/* Stats */
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:22px}
.stat{
  background:var(--surface);border:1px solid var(--border);border-radius:var(--r);
  padding:16px 18px;position:relative;overflow:hidden;box-shadow:var(--shadow);
}
.stat::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--ac,var(--blue))}
.stat-label{font-size:11px;color:var(--muted);font-family:var(--mono);text-transform:uppercase;letter-spacing:.06em}
.stat-val{font-size:26px;font-weight:800;margin-top:4px;color:var(--ac,var(--blue))}
.stat-val.sm{font-size:16px;margin-top:9px;font-weight:700}

/* Home panels */
.home-panels{display:grid;grid-template-columns:1fr 370px;gap:16px;align-items:start}
.panel{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:20px 22px;box-shadow:var(--shadow)}
.panel-title{font-size:15px;font-weight:700;margin-bottom:16px;display:flex;align-items:center;gap:8px;color:var(--text)}
.pticon{width:26px;height:26px;border-radius:7px;background:var(--surface2);display:grid;place-items:center;font-size:14px}

/* Insight */
.insight-row{display:flex;gap:12px;padding:12px 0;border-bottom:1px solid var(--border)}
.insight-row:last-child{border-bottom:none;padding-bottom:0}
.insight-row:first-child{padding-top:0}
.ins-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0;margin-top:8px}
.ins-cat{font-size:11px;font-family:var(--mono);text-transform:uppercase;letter-spacing:.08em;margin-bottom:5px;font-weight:700}
.ins-links{display:flex;flex-direction:column;gap:5px}
.ins-links a{font-size:13px;color:var(--text);line-height:1.4;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.ins-links a:hover{color:var(--blue)}

/* Health table */
.health-wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:12px}
th{text-align:left;padding:5px 8px;color:var(--dim);font-family:var(--mono);font-size:10px;text-transform:uppercase;letter-spacing:.07em;border-bottom:1px solid var(--border);white-space:nowrap}
td{padding:7px 8px;border-bottom:1px solid var(--border);vertical-align:top}
tr:last-child td{border-bottom:none}
.td-muted{color:var(--muted);white-space:nowrap;font-size:11px}
.td-num{font-family:var(--mono);color:var(--muted);text-align:right;padding-right:4px}
.td-err{max-width:170px;color:var(--dim);font-family:var(--mono);font-size:10px;word-break:break-all}
.src-link{color:var(--muted)}.src-link:hover{color:var(--blue)}
.badge-ok{display:inline-flex;border-radius:99px;padding:2px 7px;font-size:10px;font-weight:700;font-family:var(--mono);color:#065f46;background:#dcfce7}
.badge-warn{display:inline-flex;border-radius:99px;padding:2px 7px;font-size:10px;font-weight:700;font-family:var(--mono);color:#92400e;background:#fef3c7}
.badge-empty{display:inline-flex;border-radius:99px;padding:2px 7px;font-size:10px;font-weight:700;font-family:var(--mono);color:var(--muted);background:var(--surface2)}
.badge-error{display:inline-flex;border-radius:99px;padding:2px 7px;font-size:10px;font-weight:700;font-family:var(--mono);color:#991b1b;background:#fee2e2}

/* Page sections */
.page-section{animation:fi .2s ease}
@keyframes fi{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:none}}
.section-head{display:flex;align-items:center;gap:14px;margin-bottom:20px}
.section-icon{width:40px;height:40px;border-radius:10px;display:grid;place-items:center;font-size:20px;flex-shrink:0;color:#fff}
.section-kicker{font-size:11px;font-family:var(--mono);text-transform:uppercase;letter-spacing:.1em;font-weight:700;margin-bottom:2px}
.section-title{font-size:22px;font-weight:800}
.section-count{margin-left:auto;font-size:12px;color:var(--muted);font-family:var(--mono)}

/* Cards */
.news-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.card{
  background:var(--surface);border:1px solid var(--border);border-radius:var(--r);
  padding:16px;display:flex;flex-direction:column;gap:10px;
  box-shadow:var(--shadow);transition:border-color .15s,transform .15s;
}
.card:hover{border-color:var(--border2);transform:translateY(-2px)}
.card.is-read{opacity:.42}
.card-top{display:flex;align-items:center;justify-content:space-between;gap:8px}
.source-pill{
  font-size:11px;font-weight:700;font-family:var(--mono);
  color:var(--ac);background:var(--lc);
  border-radius:5px;padding:2px 8px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:60%;
}
.card-date{font-size:11px;color:var(--dim);font-family:var(--mono);white-space:nowrap}
.card h3{font-size:14.5px;font-weight:600;line-height:1.42;flex:1}
.card h3 a:hover{color:var(--blue)}
.card p{font-size:13px;color:var(--muted);line-height:1.65;flex:1;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.card-foot{display:flex;align-items:center;gap:8px;border-top:1px solid var(--border);padding-top:10px;margin-top:auto}
.btn-mark{border:1px solid var(--border2);background:#fff;color:var(--dim);border-radius:6px;padding:5px 10px;font-size:12px;cursor:pointer;font-family:var(--font);transition:all .12s}
.btn-mark:hover{border-color:var(--muted);color:var(--muted)}
.btn-open{margin-left:auto;background:var(--text);color:#fff;border-radius:6px;padding:5px 11px;font-size:12px;font-weight:600;transition:all .12s}
.btn-open:hover{background:var(--blue)}
.tag-video{background:#fee2e2;color:#991b1b;font-size:10px;font-weight:700;border-radius:4px;padding:1px 5px;font-family:var(--mono)}

/* Expert cards */
.expert-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:14px}
.expert-card{
  background:var(--surface);border:1px solid var(--border);border-radius:var(--r);
  padding:16px;display:flex;gap:14px;align-items:flex-start;
  box-shadow:var(--shadow);transition:border-color .15s,transform .15s;
}
.expert-card:hover{border-color:var(--blue);transform:translateY(-2px)}
.expert-x{
  width:36px;height:36px;border-radius:9px;background:#0f172a;color:#fff;
  display:grid;place-items:center;font-size:13px;font-weight:800;flex-shrink:0;
  letter-spacing:-.5px;
}
.expert-info{}
.expert-name{font-size:14px;font-weight:700;margin-bottom:2px}
.expert-role{font-size:11px;color:var(--blue);font-family:var(--mono);font-weight:600;margin-bottom:6px}
.expert-note{font-size:12.5px;color:var(--muted);line-height:1.55}

.empty{border:1px dashed var(--border2);border-radius:var(--r);padding:24px;color:var(--dim);text-align:center;grid-column:1/-1;font-size:14px}
.footer{color:var(--dim);font-size:11px;font-family:var(--mono);margin-top:32px;padding-top:18px;border-top:1px solid var(--border)}
.digest-box{
  background:var(--lc,#eff6ff);border:1.5px solid var(--ac,#2563eb);border-radius:var(--r);
  padding:20px 24px;margin-bottom:24px;
}
.digest-header{display:flex;align-items:baseline;justify-content:space-between;gap:12px;margin-bottom:14px;flex-wrap:wrap}
.digest-label{
  font-size:13px;font-weight:700;font-family:var(--mono);
  color:var(--ac,#2563eb);display:flex;align-items:center;gap:8px;
}
.digest-ai-badge{
  font-size:10px;font-weight:700;font-family:var(--mono);
  background:var(--ac,#2563eb);color:#fff;
  border-radius:4px;padding:2px 6px;letter-spacing:.04em;
}
.digest-ai-fallback{background:var(--muted)}
.digest-meta{font-size:11px;color:var(--muted);font-family:var(--mono)}
.digest-body{font-size:14px;line-height:1.9;color:var(--text)}
.digest-para{margin-bottom:10px}
.digest-para:last-child{margin-bottom:0}
.digest-refs{
  display:flex;flex-wrap:wrap;gap:6px;
  margin-bottom:14px;margin-top:6px;padding-left:2px;
}
.digest-ref-link{
  display:inline-flex;align-items:center;gap:5px;
  background:color-mix(in srgb,var(--ac,#2563eb) 8%,#fff);
  border:1px solid color-mix(in srgb,var(--ac,#2563eb) 20%,transparent);
  border-radius:6px;padding:4px 10px;
  font-size:12px;color:var(--text);line-height:1.3;
  transition:all .12s;max-width:320px;
}
.digest-ref-link:hover{background:color-mix(in srgb,var(--ac,#2563eb) 15%,#fff);color:var(--ac,#2563eb)}
.ref-source{
  font-size:10px;font-weight:700;font-family:var(--mono);
  color:var(--ac,#2563eb);white-space:nowrap;flex-shrink:0;
}

@media(max-width:1000px){.home-panels{grid-template-columns:1fr}}
@media(max-width:900px){
  .shell{grid-template-columns:1fr}
  .sidebar{position:static;height:auto;flex-direction:row;flex-wrap:wrap;padding:12px}
  .brand{border-bottom:none;padding-bottom:0;margin-bottom:0}
  .main{padding:20px 16px 40px}
  .stats{grid-template-columns:1fr 1fr}
}
@media(max-width:560px){.news-grid,.expert-grid{grid-template-columns:1fr}.page-title{font-size:22px}}
</style>
</head>
<body>
<div class="shell">
<aside class="sidebar">
  <div class="brand">
    <div class="brand-mark">SEO</div>
    <div><div class="brand-name">SEO Monitor</div><div class="brand-sub">Auto-fetch &middot; Daily</div></div>
  </div>
  <button class="home-btn" id="home-btn" onclick="showPage('home')">&#127968;&nbsp; Home / Overview</button>
  <div class="slabel">Categories</div>
  NAV_TABS_PLACEHOLDER
  <div class="slabel">Expert Feeds</div>
  EXPERT_SIDEBAR_PLACEHOLDER
</aside>
<main class="main">
  <div id="page-home">
    <div class="eyebrow">SEO / GEO / AI Search Intelligence</div>
    <h1 class="page-title">Search Monitor</h1>
    <p class="page-sub">Your personal feed for SEO, AI Search &amp; GEO updates &mdash; auto-fetched daily.</p>
    <div class="toolbar">
      <input id="searchInput" class="search-box" type="search" placeholder="Search across all articles&hellip;">
      <div class="day-tabs">
        <button class="day-tab" data-days="3">3d</button>
        <button class="day-tab active" data-days="7">7d</button>
        <button class="day-tab" data-days="WINDOW_DAYS_PLACEHOLDER">WINDOW_DAYS_PLACEHOLDERd</button>
      </div>
    </div>
    <div class="stats">
      <div class="stat" style="--ac:#2563eb"><div class="stat-label">Total Articles</div><div class="stat-val">TOTAL_PLACEHOLDER</div></div>
      <div class="stat" style="--ac:#059669"><div class="stat-label">Active Sources</div><div class="stat-val">ACTIVE_PLACEHOLDER</div></div>
      <div class="stat" style="--ac:#dc2626"><div class="stat-label">Need Attention</div><div class="stat-val">ERRORS_PLACEHOLDER</div></div>
      <div class="stat" style="--ac:#7c3aed"><div class="stat-label">Latest Item</div><div class="stat-val sm">LATEST_PLACEHOLDER</div></div>
    </div>
    <div class="panel" style="margin-bottom:16px">
      <div class="panel-title"><span class="pticon">&#129322;</span> Source Health &mdash; Active &amp; Issues Only</div>
      <div class="health-wrap">
        <table>
          <thead><tr><th>Category</th><th>Source</th><th>Status</th><th>Items</th><th>Note</th></tr></thead>
          <tbody>HEALTH_PLACEHOLDER</tbody>
        </table>
      </div>
    </div>
    <div class="panel">
      <div class="panel-title"><span class="pticon">&#9889;</span> This Week's Highlights</div>
      INSIGHTS_PLACEHOLDER
    </div>
  </div>
  SECTIONS_PLACEHOLDER
  <div class="footer">Generated: GENERATED_AT_PLACEHOLDER &middot; Window: last WINDOW_DAYS_PLACEHOLDER days &middot; Auto-updated via GitHub Actions</div>
</main>
</div>
<script>
const STORE="seo_v4";
let state;try{state=JSON.parse(localStorage.getItem(STORE)||'{"read":[]}');}catch(_){state={read:[]};}
const allCards=Array.from(document.querySelectorAll(".card"));
const dayTabs=Array.from(document.querySelectorAll(".day-tab"));
const searchBox=document.getElementById("searchInput");
let activeDays=7,currentPage="home";
function save(){try{localStorage.setItem(STORE,JSON.stringify(state));}catch(_){}}
function toggleRead(id,btn){
  if(!state.read.includes(id))state.read.push(id);
  const c=document.getElementById(id);if(c)c.classList.add("is-read");
  btn.textContent="Read \u2713";save();
}
function showPage(slug){
  document.getElementById("page-home").style.display="none";
  document.querySelectorAll(".page-section").forEach(s=>s.style.display="none");
  const hb=document.getElementById("home-btn");
  document.querySelectorAll(".nav-tab").forEach(t=>t.classList.remove("active"));
  if(slug==="home"){
    document.getElementById("page-home").style.display="block";
    hb.className="home-btn";currentPage="home";
  }else{
    const sec=document.getElementById("page-"+slug);if(sec)sec.style.display="block";
    hb.className="home-btn off";
    const tab=document.querySelector('.nav-tab[data-target="page-'+slug+'"]');
    if(tab)tab.classList.add("active");currentPage=slug;
  }
}
function applyFilters(){
  if(currentPage!=="home")return;
  const now=Math.floor(Date.now()/1000);
  const q=(searchBox.value||"").trim().toLowerCase();
  allCards.forEach(c=>{
    const ok=(now-Number(c.dataset.ts))<=activeDays*86400&&(!q||c.textContent.toLowerCase().includes(q));
    c.style.display=ok?"flex":"none";
  });
}
state.read.forEach(id=>{
  const c=document.getElementById(id);if(!c)return;
  c.classList.add("is-read");const b=c.querySelector(".btn-mark");if(b)b.textContent="Read \u2713";
});
dayTabs.forEach(t=>t.addEventListener("click",()=>{
  dayTabs.forEach(x=>x.classList.remove("active"));t.classList.add("active");
  activeDays=Number(t.dataset.days);applyFilters();
}));
if(searchBox)searchBox.addEventListener("input",applyFilters);
showPage("home");applyFilters();
</script>
</body></html>"""

    page = page.replace("NAV_TABS_PLACEHOLDER", nav_tabs_html)
    page = page.replace("EXPERT_SIDEBAR_PLACEHOLDER", expert_sidebar_html)
    page = page.replace("SECTIONS_PLACEHOLDER", sections_html)
    page = page.replace("INSIGHTS_PLACEHOLDER", insight_rows(all_data))
    page = page.replace("HEALTH_PLACEHOLDER", health_rows(source_health))
    page = page.replace("TOTAL_PLACEHOLDER", str(total))
    page = page.replace("ACTIVE_PLACEHOLDER", str(active))
    page = page.replace("ERRORS_PLACEHOLDER", str(errors))
    page = page.replace("LATEST_PLACEHOLDER", latest)
    page = page.replace("GENERATED_AT_PLACEHOLDER", generated_at)
    page = page.replace("WINDOW_DAYS_PLACEHOLDER", str(WINDOW_DAYS))

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(page)


def fetch_data():
    all_data, source_health, weekly_digests = collect_data()
    render_dashboard(all_data, source_health, weekly_digests)
    print(f"[OK] Generated index.html with {len(all_data)} items")


if __name__ == "__main__":
    fetch_data()
