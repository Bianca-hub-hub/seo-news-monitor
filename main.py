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
    "专家动态",
]

CATEGORY_META = {
    "SEO 动态": {"icon": "🔎", "slug": "seo", "accent": "#2563eb", "label": "SEO"},
    "GEO 趋势": {"icon": "🌐", "slug": "geo", "accent": "#0891b2", "label": "GEO"},
    "AI 搜索": {"icon": "🤖", "slug": "ai-search", "accent": "#7c3aed", "label": "AI"},
    "专家动态": {"icon": "𝕏", "slug": "experts", "accent": "#111827", "label": "X"},
}

RSS_SOURCES = {
    "SEO 动态": {
        "Google Search Central": "https://developers.google.com/search/blog/rss.xml",
        "Search Engine Land": "https://searchengineland.com/feed",
        "SEO Roundtable": "https://www.seroundtable.com/rss.xml",
        "Ahrefs Blog": "https://ahrefs.com/blog/feed/",
        "Backlinko": "https://backlinko.com/feed/",
        "Moz Blog": "https://moz.com/blog/feed",
    },
    "GEO 趋势": {
        "Search Engine Journal": "https://www.searchenginejournal.com/feed/",
        "Aleyda Solis Blog": "https://www.aleydasolis.com/en/blog/feed/",
        "Onely Tech SEO": "https://www.onely.com/blog/feed/",
        "Perplexity Blog": "https://blog.perplexity.ai/rss",
    },
    "AI 搜索": {
        "OpenAI News": "https://openai.com/news/rss.xml",
        "Google AI Blog": "https://blog.google/technology/ai/rss/",
        "Anthropic News": "https://www.anthropic.com/news/rss.xml",
        "The Verge AI": "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml",
    },
}

EXPERT_PROFILES = [
    {
        "name": "Aleyda Solis",
        "title": "Aleyda Solis on X — International SEO & AI Search",
        "url": "https://x.com/Aleyda",
        "note": "International SEO consultant. Best for technical SEO, internationalization, and AI Search discussions.",
    },
    {
        "name": "Lily Ray",
        "title": "Lily Ray on X — Google Updates & E-E-A-T",
        "url": "https://x.com/lilyraynyc",
        "note": "Tracks Google algorithm updates, content quality, E-E-A-T, and search visibility changes.",
    },
    {
        "name": "Zara Zhang",
        "title": "Zara Zhang on X — AI Products & Global Tech",
        "url": "https://x.com/zarazhangrui",
        "note": "AI products, global tech trends, and cross-market AI strategy perspectives.",
    },
]

WINDOW_DAYS = int(os.environ.get("WINDOW_DAYS", "14"))
MAX_ITEMS_PER_SOURCE = int(os.environ.get("MAX_ITEMS_PER_SOURCE", "12"))
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "20"))
USER_AGENT = (
    "Mozilla/5.0 (compatible; SEO-News-Monitor/3.0; "
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


def fallback_summary(item, target_len=120):
    base = normalize_text(item.get("raw_summary", "")) or item["title"]
    source = item["source"]
    prefix = f"From {source}: "
    body_limit = max(42, target_len - len(prefix) - 10)
    body = base[:body_limit].rstrip("., ")
    return f"{prefix}{body}."


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
    prompt = (
        "You are an SEO intelligence editor. Summarize the following news item "
        "from the perspective of SEO growth, content strategy, search traffic, "
        "and AI Search/GEO impact. Write 1-2 sentences in English, high information "
        "density, actionable, no marketing fluff.\n\n"
        f"Source: {item['source']}\n"
        f"Category: {item['category']}\n"
        f"Title: {item['title']}\n"
        f"Excerpt: {raw or 'No excerpt available'}"
    )
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a concise, precise SEO strategy editor."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        text = normalize_text(resp.choices[0].message.content or "")
        if 20 <= len(text) <= 300:
            return text[:280]
    except Exception as exc:
        print(f"[WARN] AI summary failed: {item['title'][:70]} -> {exc}")
    return fallback_summary(item)


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

        for entry in feed.entries[: MAX_ITEMS_PER_SOURCE * 3]:
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
                    "is_video": "youtube" in link.lower()
                    or "video" in normalize_text(entry.get("tags", "")).lower(),
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
            status["error"] = bozo_error or f"No items in last {WINDOW_DAYS} days"

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
        "ok": ("Normal", "status-ok"),
        "warning": ("Warning", "status-warning"),
        "empty": ("No new items", "status-empty"),
        "error": ("Error", "status-error"),
    }
    return labels.get(state, ("Unknown", "status-error"))


def item_card(item):
    meta = CATEGORY_META[item["category"]]
    video_badge = "<span class='badge-video'>VIDEO</span>" if item["is_video"] else ""
    title_escaped = html.escape(item["title"])
    link_escaped = html.escape(item["link"])
    source_escaped = html.escape(item["source"])
    summary_escaped = html.escape(item["summary"])

    return f"""
<article class="news-card" id="{item['id']}" data-ts="{item['ts']}" data-category="{html.escape(item['category'])}">
  <div class="card-header">
    <span class="source-tag" style="--accent:{meta['accent']}">{source_escaped}</span>
    <span class="card-date">{item['date_str']}</span>
  </div>
  <h3 class="card-title"><a href="{link_escaped}" target="_blank" rel="noopener noreferrer">{title_escaped}</a></h3>
  <p class="card-summary">{summary_escaped}</p>
  <div class="card-footer">
    <button class="btn-read" type="button" onclick="toggleRead('{item['id']}', this)">Mark read</button>
    <a class="btn-open" href="{link_escaped}" target="_blank" rel="noopener noreferrer">Read →{video_badge}</a>
  </div>
</article>
"""


def category_section(category, items):
    meta = CATEGORY_META[category]
    cards = "".join(item_card(item) for item in items[:60])
    empty = "<div class='empty-state'>No new content fetched for this window.</div>"
    count = len(items)
    return f"""
<section class="cat-section" id="{meta['slug']}">
  <div class="cat-header">
    <div class="cat-label">
      <span class="cat-icon" style="background:{meta['accent']}">{meta['icon']}</span>
      <div>
        <div class="cat-kicker">{meta['label']}</div>
        <h2 class="cat-title">{category}</h2>
      </div>
    </div>
    <span class="cat-count">{count} items</span>
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
        meta = CATEGORY_META[category]
        links_html = ""
        for item in picks:
            links_html += f'<a href="{html.escape(item["link"])}" target="_blank" rel="noopener noreferrer">{html.escape(item["title"])}</a>'
        rows.append(f"""
<div class="insight-row">
  <div class="insight-dot" style="background:{meta['accent']}"></div>
  <div class="insight-body">
    <div class="insight-cat">{meta['icon']} {category}</div>
    <div class="insight-links">{links_html}</div>
  </div>
</div>""")
    return "".join(rows)


def health_rows(source_health):
    rows = []
    for item in source_health:
        label, klass = status_label(item["state"])
        error_display = html.escape(item["error"] or "—")
        rows.append(f"""
<tr>
  <td class="td-cat">{html.escape(item['category'])}</td>
  <td><a href="{html.escape(item['url'])}" target="_blank" rel="noopener noreferrer" class="source-link">{html.escape(item['source'])}</a></td>
  <td><span class="badge {klass}">{label}</span></td>
  <td class="td-count">{item['count']}</td>
  <td class="td-error">{error_display}</td>
</tr>""")
    return "".join(rows)


def render_dashboard(all_data, source_health):
    grouped = {category: [] for category in CATEGORY_ORDER}
    for item in all_data:
        if item["category"] in grouped:
            grouped[item["category"]].append(item)

    total = len(all_data)
    active_sources = sum(1 for s in source_health if s["state"] in {"ok", "warning"})
    error_sources = sum(1 for s in source_health if s["state"] in {"error", "empty"})
    latest_date = max((item["date_str"] for item in all_data if item["category"] != "专家动态"), default="—")
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    nav_links = ""
    for cat in CATEGORY_ORDER:
        meta = CATEGORY_META[cat]
        nav_links += f'<a class="nav-link" href="#{meta["slug"]}"><span class="nav-icon">{meta["icon"]}</span><span class="nav-text">{cat}</span><span class="nav-badge">{len(grouped[cat])}</span></a>'

    sections = "".join(category_section(category, grouped[category]) for category in CATEGORY_ORDER)

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SEO Intelligence Monitor</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@700;800&family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root {{
  --bg: #0d0f14;
  --surface: #151820;
  --surface2: #1c2030;
  --border: #252a38;
  --border2: #2e3548;
  --text: #e2e6f0;
  --muted: #6b7591;
  --dim: #3d4561;
  --blue: #4f8ef7;
  --cyan: #22d3ee;
  --purple: #a78bfa;
  --green: #34d399;
  --amber: #fbbf24;
  --red: #f87171;
  --white: #ffffff;
  --font-display: 'Syne', sans-serif;
  --font-body: 'DM Sans', sans-serif;
  --font-mono: 'DM Mono', monospace;
  --radius: 10px;
  --radius-sm: 6px;
}}

*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
html {{ scroll-behavior: smooth; }}
body {{
  background: var(--bg);
  color: var(--text);
  font-family: var(--font-body);
  line-height: 1.6;
  min-height: 100vh;
}}
a {{ color: inherit; text-decoration: none; }}

/* ── Layout ─────────────────────────────────────── */
.layout {{
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  min-height: 100vh;
}}

/* ── Sidebar ─────────────────────────────────────── */
.sidebar {{
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
  background: var(--surface);
  border-right: 1px solid var(--border);
  padding: 28px 16px;
  display: flex;
  flex-direction: column;
  gap: 0;
}}

.brand {{
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 4px 24px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 20px;
}}
.brand-logo {{
  width: 36px; height: 36px;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--blue), var(--purple));
  display: grid;
  place-items: center;
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 800;
  color: #fff;
  flex-shrink: 0;
}}
.brand-name {{ font-family: var(--font-display); font-size: 15px; font-weight: 800; line-height: 1.2; }}
.brand-sub {{ font-size: 11px; color: var(--muted); margin-top: 2px; font-family: var(--font-mono); }}

.sidebar-section {{ margin-bottom: 28px; }}
.sidebar-label {{
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: var(--dim);
  text-transform: uppercase;
  font-family: var(--font-mono);
  padding: 0 8px;
  margin-bottom: 8px;
}}
.nav-link {{
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 8px;
  border-radius: var(--radius-sm);
  color: var(--muted);
  font-size: 13.5px;
  font-weight: 500;
  transition: all 0.15s;
}}
.nav-link:hover {{ background: var(--surface2); color: var(--text); }}
.nav-icon {{ width: 18px; text-align: center; font-size: 14px; flex-shrink: 0; }}
.nav-text {{ flex: 1; }}
.nav-badge {{
  font-size: 11px;
  font-family: var(--font-mono);
  color: var(--dim);
  background: var(--surface2);
  border-radius: 99px;
  padding: 1px 7px;
}}

.expert-link {{
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 8px;
  border-radius: var(--radius-sm);
  color: var(--muted);
  font-size: 13px;
  transition: all 0.15s;
}}
.expert-link:hover {{ background: var(--surface2); color: var(--text); }}
.expert-x {{ font-size: 13px; width: 18px; text-align: center; opacity: 0.5; }}

/* ── Main ─────────────────────────────────────── */
.main {{
  padding: 36px 40px 60px;
  min-width: 0;
}}

/* ── Top bar ─────────────────────────────────────── */
.topbar {{
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 32px;
  flex-wrap: wrap;
}}
.page-eyebrow {{
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.1em;
  color: var(--blue);
  text-transform: uppercase;
  margin-bottom: 8px;
}}
.page-title {{
  font-family: var(--font-display);
  font-size: 32px;
  font-weight: 800;
  line-height: 1.15;
  color: var(--white);
}}
.page-sub {{
  color: var(--muted);
  font-size: 14px;
  margin-top: 8px;
  max-width: 520px;
}}

.toolbar {{
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  flex-shrink: 0;
}}
.search-input {{
  background: var(--surface);
  border: 1px solid var(--border2);
  border-radius: var(--radius-sm);
  color: var(--text);
  font-family: var(--font-body);
  font-size: 13px;
  padding: 9px 12px;
  width: 220px;
  outline: none;
  transition: border-color 0.15s;
}}
.search-input::placeholder {{ color: var(--muted); }}
.search-input:focus {{ border-color: var(--blue); }}

.day-tabs {{
  display: flex;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 3px;
  gap: 2px;
}}
.day-tab {{
  border: 0;
  background: transparent;
  color: var(--muted);
  border-radius: 4px;
  padding: 7px 12px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  font-family: var(--font-body);
}}
.day-tab.active {{
  background: var(--blue);
  color: #fff;
}}

/* ── Stats ─────────────────────────────────────── */
.stats-row {{
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 28px;
}}
.stat-card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px 18px;
  position: relative;
  overflow: hidden;
}}
.stat-card::before {{
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 2px;
  background: var(--accent-line, var(--blue));
}}
.stat-label {{ font-size: 12px; color: var(--muted); font-family: var(--font-mono); text-transform: uppercase; letter-spacing: 0.05em; }}
.stat-value {{ font-family: var(--font-display); font-size: 28px; font-weight: 800; color: var(--white); margin-top: 6px; }}
.stat-value.sm {{ font-size: 18px; margin-top: 9px; }}

/* ── Panel grid ─────────────────────────────────────── */
.panel-row {{
  display: grid;
  grid-template-columns: 1fr 420px;
  gap: 16px;
  margin-bottom: 32px;
  align-items: start;
}}
.panel {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px 22px;
}}
.panel-title {{
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 800;
  color: var(--white);
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}}
.panel-title-icon {{
  width: 24px; height: 24px;
  border-radius: 6px;
  background: var(--surface2);
  display: grid;
  place-items: center;
  font-size: 12px;
}}

/* Insight rows */
.insight-row {{
  display: flex;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid var(--border);
}}
.insight-row:last-child {{ border-bottom: none; padding-bottom: 0; }}
.insight-row:first-child {{ padding-top: 0; }}
.insight-dot {{
  width: 8px; height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 7px;
}}
.insight-cat {{
  font-size: 11px;
  font-family: var(--font-mono);
  color: var(--muted);
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}}
.insight-links {{
  display: flex;
  flex-direction: column;
  gap: 5px;
}}
.insight-links a {{
  font-size: 13px;
  color: var(--text);
  line-height: 1.45;
  transition: color 0.12s;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}}
.insight-links a:hover {{ color: var(--blue); }}

/* Health table */
.health-scroll {{ overflow-x: auto; }}
.health-table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
}}
.health-table th {{
  text-align: left;
  padding: 6px 8px;
  color: var(--dim);
  font-family: var(--font-mono);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}}
.health-table td {{
  padding: 8px 8px;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
}}
.health-table tr:last-child td {{ border-bottom: none; }}
.source-link {{ color: var(--muted); }}
.source-link:hover {{ color: var(--blue); }}
.td-cat {{ color: var(--muted); white-space: nowrap; }}
.td-count {{ font-family: var(--font-mono); color: var(--muted); text-align: right; }}
.td-error {{
  max-width: 200px;
  color: var(--dim);
  font-family: var(--font-mono);
  font-size: 11px;
  word-break: break-all;
}}

.badge {{
  display: inline-flex;
  border-radius: 99px;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 700;
  font-family: var(--font-mono);
  white-space: nowrap;
}}
.status-ok {{ color: var(--green); background: rgba(52, 211, 153, 0.1); }}
.status-warning {{ color: var(--amber); background: rgba(251, 191, 36, 0.1); }}
.status-empty {{ color: var(--muted); background: var(--surface2); }}
.status-error {{ color: var(--red); background: rgba(248, 113, 113, 0.1); }}

/* ── Category sections ─────────────────────────── */
.cat-section {{ margin-bottom: 40px; scroll-margin-top: 20px; }}
.cat-header {{
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}}
.cat-label {{ display: flex; align-items: center; gap: 12px; }}
.cat-icon {{
  width: 38px; height: 38px;
  border-radius: 9px;
  display: grid;
  place-items: center;
  font-size: 18px;
  flex-shrink: 0;
}}
.cat-kicker {{
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-bottom: 2px;
}}
.cat-title {{
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 800;
  color: var(--white);
}}
.cat-count {{
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--muted);
  padding-bottom: 4px;
}}

/* ── News grid ─────────────────────────────────────── */
.news-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}}

.news-card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: border-color 0.15s, transform 0.15s;
  position: relative;
}}
.news-card:hover {{
  border-color: var(--border2);
  transform: translateY(-2px);
}}
.news-card.is-read {{
  opacity: 0.4;
}}

.card-header {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}}
.source-tag {{
  font-size: 11px;
  font-weight: 700;
  font-family: var(--font-mono);
  color: var(--accent, var(--blue));
  background: color-mix(in srgb, var(--accent, var(--blue)) 12%, transparent);
  border-radius: 4px;
  padding: 2px 7px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 60%;
}}
.card-date {{
  font-size: 11px;
  color: var(--dim);
  font-family: var(--font-mono);
  white-space: nowrap;
}}

.card-title {{
  font-size: 15px;
  font-weight: 600;
  line-height: 1.4;
  flex: 1;
}}
.card-title a {{ color: var(--text); }}
.card-title a:hover {{ color: var(--blue); }}

.card-summary {{
  font-size: 13px;
  color: var(--muted);
  line-height: 1.65;
  flex: 1;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}}

.card-footer {{
  display: flex;
  align-items: center;
  gap: 8px;
  border-top: 1px solid var(--border);
  padding-top: 10px;
  margin-top: auto;
}}
.btn-read {{
  border: 1px solid var(--border2);
  background: transparent;
  color: var(--dim);
  border-radius: var(--radius-sm);
  padding: 5px 10px;
  font-size: 12px;
  cursor: pointer;
  font-family: var(--font-body);
  transition: all 0.12s;
}}
.btn-read:hover {{ border-color: var(--muted); color: var(--muted); }}
.btn-open {{
  margin-left: auto;
  background: var(--surface2);
  border: 1px solid var(--border2);
  color: var(--text);
  border-radius: var(--radius-sm);
  padding: 5px 10px;
  font-size: 12px;
  font-weight: 600;
  transition: all 0.12s;
}}
.btn-open:hover {{ background: var(--blue); border-color: var(--blue); color: #fff; }}
.badge-video {{
  background: rgba(248, 113, 113, 0.15);
  color: var(--red);
  font-size: 10px;
  font-weight: 700;
  border-radius: 4px;
  padding: 2px 5px;
  font-family: var(--font-mono);
}}

.empty-state {{
  border: 1px dashed var(--border2);
  border-radius: var(--radius);
  padding: 24px;
  color: var(--dim);
  font-size: 14px;
  text-align: center;
  grid-column: 1 / -1;
}}

.footer-note {{
  color: var(--dim);
  font-size: 12px;
  font-family: var(--font-mono);
  margin-top: 32px;
  padding-top: 20px;
  border-top: 1px solid var(--border);
}}

/* ── Responsive ─────────────────────────────────────── */
@media (max-width: 1100px) {{
  .panel-row {{ grid-template-columns: 1fr; }}
}}
@media (max-width: 900px) {{
  .layout {{ grid-template-columns: 1fr; }}
  .sidebar {{ position: static; height: auto; overflow: visible; flex-direction: row; flex-wrap: wrap; padding: 16px; gap: 12px; }}
  .brand {{ border-bottom: none; padding-bottom: 0; margin-bottom: 0; }}
  .sidebar-section {{ margin-bottom: 0; }}
  .sidebar-label {{ display: none; }}
  nav.sidebar-section {{ display: flex; gap: 4px; }}
  .main {{ padding: 20px 16px 40px; }}
  .stats-row {{ grid-template-columns: repeat(2, 1fr); }}
}}
@media (max-width: 560px) {{
  .page-title {{ font-size: 24px; }}
  .stats-row {{ grid-template-columns: 1fr 1fr; }}
  .toolbar {{ width: 100%; }}
  .search-input {{ width: 100%; }}
}}
</style>
</head>
<body>
<div class="layout">

<aside class="sidebar">
  <div class="brand">
    <div class="brand-logo">SEO</div>
    <div>
      <div class="brand-name">SEO Monitor</div>
      <div class="brand-sub">Auto-fetch · Daily</div>
    </div>
  </div>

  <div class="sidebar-section">
    <div class="sidebar-label">Categories</div>
    <nav>{nav_links}</nav>
  </div>

  <div class="sidebar-section">
    <div class="sidebar-label">Expert Feeds</div>
    <nav>
      <a class="expert-link" href="https://x.com/Aleyda" target="_blank" rel="noopener noreferrer"><span class="expert-x">𝕏</span> Aleyda Solis</a>
      <a class="expert-link" href="https://x.com/lilyraynyc" target="_blank" rel="noopener noreferrer"><span class="expert-x">𝕏</span> Lily Ray</a>
      <a class="expert-link" href="https://x.com/zarazhangrui" target="_blank" rel="noopener noreferrer"><span class="expert-x">𝕏</span> Zara Zhang</a>
    </nav>
  </div>
</aside>

<main class="main">

  <div class="topbar">
    <div>
      <div class="page-eyebrow">SEO / GEO / AI Search Intelligence</div>
      <h1 class="page-title">Search Monitor</h1>
      <p class="page-sub">Your personal feed for SEO, AI Search &amp; GEO updates — auto-fetched daily.</p>
    </div>
    <div class="toolbar">
      <input id="searchInput" class="search-input" type="search" placeholder="Search titles, sources…">
      <div class="day-tabs" aria-label="Time filter">
        <button class="day-tab" type="button" data-days="3">3d</button>
        <button class="day-tab active" type="button" data-days="7">7d</button>
        <button class="day-tab" type="button" data-days="{WINDOW_DAYS}">{WINDOW_DAYS}d</button>
      </div>
    </div>
  </div>

  <div class="stats-row">
    <div class="stat-card" style="--accent-line: var(--blue)">
      <div class="stat-label">Total Items</div>
      <div class="stat-value">{total}</div>
    </div>
    <div class="stat-card" style="--accent-line: var(--green)">
      <div class="stat-label">Active Sources</div>
      <div class="stat-value">{active_sources}</div>
    </div>
    <div class="stat-card" style="--accent-line: var(--red)">
      <div class="stat-label">Needs Attention</div>
      <div class="stat-value">{error_sources}</div>
    </div>
    <div class="stat-card" style="--accent-line: var(--purple)">
      <div class="stat-label">Latest Item</div>
      <div class="stat-value sm">{latest_date}</div>
    </div>
  </div>

  <div class="panel-row">
    <div class="panel">
      <div class="panel-title"><span class="panel-title-icon">⚡</span> This Week's Highlights</div>
      {insight_rows(all_data) or "<div class='empty-state'>No highlights available yet.</div>"}
    </div>
    <div class="panel">
      <div class="panel-title"><span class="panel-title-icon">🩺</span> Source Health</div>
      <div class="health-scroll">
        <table class="health-table">
          <thead><tr><th>Category</th><th>Source</th><th>Status</th><th style="text-align:right">Items</th><th>Note</th></tr></thead>
          <tbody>{health_rows(source_health)}</tbody>
        </table>
      </div>
    </div>
  </div>

  {sections}

  <div class="footer-note">Generated: {generated_at} · Window: last {WINDOW_DAYS} days · Auto-updated via GitHub Actions</div>

</main>
</div>

<script>
const STORE_KEY = "seo_monitor_v3";
const state = (() => {{
  try {{ return JSON.parse(localStorage.getItem(STORE_KEY) || '{{"read":[]}}'); }}
  catch {{ return {{ read: [] }}; }}
}})();

const cards = Array.from(document.querySelectorAll(".news-card"));
const tabs = Array.from(document.querySelectorAll(".day-tab"));
const searchInput = document.getElementById("searchInput");
let activeDays = 7;

function save() {{
  try {{ localStorage.setItem(STORE_KEY, JSON.stringify(state)); }} catch(_) {{}}
}}

function toggleRead(id, btn) {{
  if (!state.read.includes(id)) state.read.push(id);
  const card = document.getElementById(id);
  if (card) card.classList.add("is-read");
  btn.textContent = "Read ✓";
  save();
}}

function applyFilters() {{
  const now = Math.floor(Date.now() / 1000);
  const query = (searchInput.value || "").trim().toLowerCase();
  cards.forEach(card => {{
    const inWindow = (now - Number(card.dataset.ts)) <= activeDays * 86400;
    const matches = !query || card.textContent.toLowerCase().includes(query);
    card.style.display = (inWindow && matches) ? "flex" : "none";
  }});
}}

// Restore read state
state.read.forEach(id => {{
  const card = document.getElementById(id);
  if (!card) return;
  card.classList.add("is-read");
  const btn = card.querySelector(".btn-read");
  if (btn) btn.textContent = "Read ✓";
}});

tabs.forEach(tab => {{
  tab.addEventListener("click", () => {{
    tabs.forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    activeDays = Number(tab.dataset.days);
    applyFilters();
  }});
}});

searchInput.addEventListener("input", applyFilters);
applyFilters();
</script>
</body>
</html>
"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(full_html)


def fetch_data():
    all_data, source_health = collect_data()
    render_dashboard(all_data, source_health)
    print(f"[OK] Generated index.html with {len(all_data)} items")


if __name__ == "__main__":
    fetch_data()
