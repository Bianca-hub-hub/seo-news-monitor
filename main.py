import os
import re
import html
import hashlib
from datetime import datetime, timedelta

import feedparser

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

# ==========================================
# 1) 监控分类与信源
# ==========================================
CATEGORY_ORDER = [
    "SEO 动态",
    "GEO 趋势",
    "AI 搜索",
    "国内资讯",
    "X 社交动态",
]

CATEGORY_ICON = {
    "SEO 动态": "🔍",
    "GEO 趋势": "🌐",
    "AI 搜索": "🤖",
    "国内资讯": "🇨🇳",
    "X 社交动态": "𝕏",
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
        "Search Engine Journal (AI Search)": "https://www.searchenginejournal.com/category/artificial-intelligence/feed/",
        "Perplexity Blog": "https://www.perplexity.ai/hub/blog/rss.xml",
        "Aleyda Solis": "https://www.aleydasolis.com/en/blog/feed/",
        "Onely (Tech SEO)": "https://onely.com/blog/feed/",
    },
    "AI 搜索": {
        "OpenAI News": "https://openai.com/news/rss.xml",
        "Google Blog (AI)": "https://blog.google/technology/ai/rss/",
        "Microsoft Bing Blog": "https://blogs.bing.com/search/rss.xml",
    },
    "国内资讯": {
        # 注：微信公众号通常无官方 RSS，优先通过可公开订阅源接入
        "36Kr AI": "https://36kr.com/feed",
        "机器之心": "https://www.jiqizhixin.com/rss",
        "InfoQ AI": "https://xie.infoq.cn/rss/ai",
        # 公众号示例：建议后续替换为自建抓取接口或 RSSHub 私有部署
        "独立站与SEO艺术(订阅源占位)": "https://rsshub.app/wechat/placeholder_dulizhan_seo",
        "从0到AI(订阅源占位)": "https://rsshub.app/wechat/placeholder_from0toai",
    },
    "X 社交动态": {
        # 使用 RSS 订阅桥接（可替换为你自建的更稳定镜像）
        "Aleyda Solis (X)": "https://rsshub.app/twitter/user/Aleyda",
        "Lily Ray (X)": "https://rsshub.app/twitter/user/lilyraynyc",
        "Zara Zhang (X)": "https://rsshub.app/twitter/user/zarazhangrui",
    },
}


def normalize_text(raw):
    if not raw:
        return ""
    if isinstance(raw, list):
        raw = raw[0].get("value", "")
    text = re.sub("<.*?>", "", str(raw))
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fallback_cn_summary(item, target_len=120):
    base = normalize_text(item.get("raw_summary", "")) or item["title"]
    source = item["source"]
    prefix = f"来自{source}："
    body_limit = max(60, target_len - len(prefix))
    body = base[:body_limit]
    tail = "。点击卡片可查看原文。" if not body.endswith(("。", "！", "？")) else "点击卡片可查看原文。"
    summary = f"{prefix}{body}{tail}"
    if len(summary) < 100:
        summary += "该信息已纳入本期监测清单，用于跟踪SEO、GEO与AI搜索相关变化。"
    return summary[:150]


def build_ai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or OpenAI is None:
        return None
    base_url = os.getenv("OPENAI_BASE_URL", "").strip() or None
    return OpenAI(api_key=api_key, base_url=base_url)


def generate_ai_summary(client, item):
    if client is None:
        return fallback_cn_summary(item)

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    raw = normalize_text(item.get("raw_summary", ""))[:1200]
    prompt = (
        "你是SEO与AI搜索行业编辑。请将以下资讯压缩成中文摘要，"
        "控制在100-150字，要求信息密度高、语义清晰、无营销话术。"
        "输出纯文本，不要使用项目符号。\n\n"
        f"来源：{item['source']}\n"
        f"分类：{item['category']}\n"
        f"标题：{item['title']}\n"
        f"正文片段：{raw or '无正文片段'}\n"
    )
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是严谨的中文科技编辑。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        text = (resp.choices[0].message.content or "").strip()
        text = re.sub(r"\s+", "", text)
        if len(text) < 95 or len(text) > 170:
            return fallback_cn_summary(item)
        return text[:150]
    except Exception:
        return fallback_cn_summary(item)


def parse_entry_date(entry, now):
    dt = entry.get("published_parsed") or entry.get("updated_parsed")
    if dt:
        return datetime(*dt[:6])
    return now


def parse_feed_items(category, source, url, time_limit):
    results = []
    status = {
        "category": category,
        "source": source,
        "url": url,
        "ok": False,
        "count": 0,
        "error": "",
    }
    try:
        feed = feedparser.parse(url, agent="Mozilla/5.0 (Macintosh; Intel Mac OS X)")
        if getattr(feed, "bozo", False) and getattr(feed, "bozo_exception", None):
            status["error"] = str(feed.bozo_exception)[:120]
        now = datetime.now()
        for entry in feed.entries:
            p_date = parse_entry_date(entry, now)
            if p_date < time_limit:
                continue
            link = (entry.get("link") or "").strip()
            title = (entry.get("title") or "Untitled").strip()
            if not link:
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
                    "ts": int(p_date.timestamp()),
                    "date_str": p_date.strftime("%Y-%m-%d"),
                    "raw_summary": entry.get("summary") or entry.get("description", ""),
                    "is_video": "youtube" in url.lower(),
                }
            )
        status["count"] = len(results)
        status["ok"] = len(results) > 0 and not status["error"]
    except Exception as e:
        status["error"] = str(e)[:120]
        print(f"[WARN] fetch failed: {source} -> {e}")
    return results, status


def inject_x_fallback_cards(all_data, time_limit):
    has_x = any(i["category"] == "X 社交动态" for i in all_data)
    if has_x:
        return
    now = datetime.now()
    if now < time_limit:
        return
    fallback_profiles = {
        "Aleyda Solis (X)": "https://x.com/Aleyda",
        "Lily Ray (X)": "https://x.com/lilyraynyc",
        "Zara Zhang (X)": "https://x.com/zarazhangrui",
    }
    for source, link in fallback_profiles.items():
        uid = hashlib.md5(f"x-fallback-{source}".encode("utf-8")).hexdigest()[:16]
        all_data.append(
            {
                "id": uid,
                "category": "X 社交动态",
                "source": source,
                "title": f"{source} 最新动态入口",
                "link": link,
                "ts": int(now.timestamp()),
                "date_str": now.strftime("%Y-%m-%d"),
                "raw_summary": "当前未拉取到可用RSS条目，已提供个人主页作为动态入口。",
                "summary": "当前未拉取到可用RSS条目，已提供该专家的X主页入口，便于你直接查看最新观点与实时讨论。",
                "is_video": False,
            }
        )


def build_weekly_insights(items):
    by_cat = {cat: [] for cat in CATEGORY_ORDER}
    for item in items[:40]:
        by_cat[item["category"]].append(item)

    blocks = []
    for cat in CATEGORY_ORDER:
        if not by_cat[cat]:
            continue
        picks = by_cat[cat][:3]
        links = "；".join(
            [f"<a href='{p['link']}' target='_blank'>{html.escape(p['title'])}</a>" for p in picks]
        )
        blocks.append(
            f"""
            <div class='insight-row'>
                <div class='insight-label'>{CATEGORY_ICON.get(cat, "⚡")} {cat}</div>
                <div class='insight-content'>本期重点：{links}</div>
            </div>
            """
        )
    return "".join(blocks)


def build_card_html(item):
    video_tag = "<div class='video-badge'>▶ VIDEO</div>" if item["is_video"] else ""
    return f"""
    <article class='card card-item' id='{item['id']}' data-ts='{item['ts']}'>
        {video_tag}
        <div class='card-meta'>
            <span class='source-tag'>{html.escape(item['source'])}</span>
            <span class='date'>{item['date_str']}</span>
        </div>
        <h3>{html.escape(item['title'])}</h3>
        <p>{html.escape(item['summary'])}</p>
        <div class='card-footer'>
            <button class='action-btn btn-read' onclick="toggleRead('{item['id']}', this)">Mark Read</button>
            <a href='{item['link']}' target='_blank' class='btn-primary'>Read Full →</a>
        </div>
    </article>
    """


def build_health_table(source_health):
    rows = []
    for item in source_health:
        badge = "✅ 正常" if item["ok"] else "⚠️ 异常"
        count = item["count"]
        err = html.escape(item["error"] or "-")
        rows.append(
            f"""
            <tr>
                <td>{html.escape(item['category'])}</td>
                <td>{html.escape(item['source'])}</td>
                <td>{badge}</td>
                <td>{count}</td>
                <td class='error-cell'>{err}</td>
            </tr>
            """
        )
    return "".join(rows)


def render_dashboard(all_data, source_health):
    style = """
    <style>
        :root { --sidebar-w: 280px; --bg: #f4f6f8; --card-bg: #ffffff; --primary: #2563eb; --text: #1e293b; --text-light: #64748b; }
        body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); display: flex; height: 100vh; overflow: hidden; }
        .sidebar { width: var(--sidebar-w); background: #fff; border-right: 1px solid #e2e8f0; padding: 24px; display: flex; flex-direction: column; flex-shrink: 0; }
        .logo { font-size: 1.25rem; font-weight: 800; color: var(--primary); margin-bottom: 24px; }
        .nav-group { margin-bottom: 20px; }
        .nav-title { font-size: 0.75rem; font-weight: 700; color: #94a3b8; text-transform: uppercase; margin-bottom: 10px; }
        .nav-item { display: block; padding: 10px 12px; color: var(--text-light); text-decoration: none; border-radius: 8px; font-size: 0.92rem; margin-bottom: 4px; }
        .nav-item:hover { background: #eff6ff; color: var(--primary); }
        .main { flex: 1; overflow-y: auto; padding: 28px 36px; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 28px; }
        .page-title { font-size: 1.5rem; font-weight: 700; }
        .filters { display: flex; gap: 8px; background: #e2e8f0; padding: 4px; border-radius: 8px; }
        .filter-btn { border: none; background: none; padding: 6px 14px; border-radius: 6px; font-size: 0.85rem; font-weight: 600; color: var(--text-light); cursor: pointer; }
        .filter-btn.active { background: #fff; color: var(--text); }
        .insights-box { background: #fff; border-radius: 12px; padding: 20px; border: 1px solid #e2e8f0; margin-bottom: 30px; }
        .box-header { font-size: 1.05rem; font-weight: 700; margin-bottom: 16px; }
        .insight-row { margin-bottom: 12px; font-size: 0.92rem; line-height: 1.6; border-bottom: 1px dashed #f1f5f9; padding-bottom: 12px; }
        .insight-row:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
        .insight-label { color: var(--primary); font-weight: 700; margin-bottom: 4px; }
        .insight-content a { color: var(--text); text-decoration: none; border-bottom: 1px solid #cbd5e1; }
        .insight-content a:hover { color: var(--primary); border-color: var(--primary); }
        .category-section { margin-bottom: 28px; }
        .section-title { font-size: 1rem; font-weight: 700; margin-bottom: 14px; display: flex; justify-content: space-between; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 18px; }
        .card { background: #fff; border-radius: 12px; padding: 18px; border: 1px solid #e2e8f0; display: flex; flex-direction: column; position: relative; }
        .card:hover { border-color: var(--primary); box-shadow: 0 8px 16px rgba(0,0,0,0.06); }
        .card.is-read { opacity: 0.62; filter: grayscale(1); }
        .card-meta { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        .source-tag { font-size: 0.7rem; font-weight: 700; color: var(--primary); background: #eff6ff; padding: 3px 8px; border-radius: 4px; text-transform: uppercase; }
        .date { font-size: 0.75rem; color: #94a3b8; }
        .card h3 { font-size: 1.03rem; margin: 0 0 10px 0; line-height: 1.4; }
        .card p { font-size: 0.9rem; color: var(--text-light); line-height: 1.65; margin: 0 0 14px 0; flex: 1; display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; }
        .card-footer { border-top: 1px solid #f1f5f9; padding-top: 12px; display: flex; justify-content: space-between; align-items: center; }
        .action-btn { background: none; border: 1px solid #e2e8f0; padding: 6px 10px; border-radius: 6px; font-size: 0.8rem; color: var(--text-light); cursor: pointer; }
        .btn-primary { background: var(--text); color: #fff; text-decoration: none; padding: 6px 10px; border-radius: 6px; font-size: 0.8rem; }
        .video-badge { position: absolute; top: -8px; right: -8px; background: #ef4444; color: #fff; font-size: 0.68rem; padding: 2px 8px; border-radius: 10px; font-weight: 700; }
        .health-box { background: #fff; border-radius: 12px; padding: 20px; border: 1px solid #e2e8f0; margin-bottom: 30px; }
        .health-table { width: 100%; border-collapse: collapse; font-size: 0.86rem; }
        .health-table th, .health-table td { border-bottom: 1px solid #f1f5f9; padding: 8px 6px; text-align: left; vertical-align: top; }
        .health-table th { color: #64748b; font-weight: 700; }
        .error-cell { max-width: 420px; color: #ef4444; word-break: break-all; }
    </style>
    """

    js = """
    <script>
        let db = JSON.parse(localStorage.getItem('seo_dashboard_v6') || '{"read":[]}');
        function save() { localStorage.setItem('seo_dashboard_v6', JSON.stringify(db)); }
        function toggleRead(id, btn) {
            if (!db.read.includes(id)) {
                db.read.push(id);
                const card = document.getElementById(id);
                if (card) card.classList.add('is-read');
                btn.innerText = '已读';
                save();
            }
        }
        function applyDaysFilter(days) {
            const now = Math.floor(Date.now() / 1000);
            document.querySelectorAll('.card-item').forEach(card => {
                const ts = parseInt(card.dataset.ts);
                const visible = (now - ts) <= (days * 86400);
                card.style.display = visible ? 'flex' : 'none';
            });
        }
        window.onload = () => {
            db.read.forEach(id => {
                const card = document.getElementById(id);
                if (card) {
                    card.classList.add('is-read');
                    const btn = card.querySelector('.btn-read');
                    if (btn) btn.innerText = '已读';
                }
            });
            document.querySelectorAll('.filter-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                    e.target.classList.add('active');
                    applyDaysFilter(parseInt(e.target.dataset.days));
                });
            });
            applyDaysFilter(7);
        };
    </script>
    """

    nav_links = "".join(
        [f"<a href='#{cat}' class='nav-item'>{CATEGORY_ICON.get(cat, '⚡')} {cat}</a>" for cat in CATEGORY_ORDER]
    )

    insights_html = build_weekly_insights(all_data)
    health_html = build_health_table(source_health)

    groups = {cat: [] for cat in CATEGORY_ORDER}
    for item in all_data:
        groups[item["category"]].append(item)

    sections = []
    for cat in CATEGORY_ORDER:
        cards = "".join(build_card_html(item) for item in groups[cat][:40])
        sections.append(
            f"""
            <section class='category-section' id='{cat}'>
                <div class='section-title'>
                    <span>{CATEGORY_ICON.get(cat, "⚡")} {cat}</span>
                    <span style='font-size:0.78rem; color:#94a3b8;'>{len(groups[cat])} 条</span>
                </div>
                <div class='grid'>{cards or "<div style='color:#94a3b8;'>暂无更新</div>"}</div>
            </section>
            """
        )
    sections_html = "".join(sections)

    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset='utf-8'>
        <meta name='viewport' content='width=device-width, initial-scale=1'>
        <title>SEO + GEO Intelligence Dashboard</title>
        {style}
    </head>
    <body>
        <aside class='sidebar'>
            <div class='logo'>🚀 SEO Intelligence Monitor</div>
            <div class='nav-group'>
                <div class='nav-title'>分类导航</div>
                {nav_links}
            </div>
            <div class='nav-group'>
                <div class='nav-title'>社交入口</div>
                <a href='https://x.com/Aleyda' target='_blank' class='nav-item'>𝕏 Aleyda Solis</a>
                <a href='https://x.com/lilyraynyc' target='_blank' class='nav-item'>𝕏 Lily Ray</a>
                <a href='https://x.com/zarazhangrui' target='_blank' class='nav-item'>𝕏 Zara Zhang</a>
            </div>
        </aside>
        <main class='main'>
            <div class='header'>
                <div class='page-title'>SEO / GEO / AI Search 情报看板</div>
                <div class='filters'>
                    <button class='filter-btn' data-days='3'>3 Days</button>
                    <button class='filter-btn active' data-days='7'>7 Days</button>
                    <button class='filter-btn' data-days='30'>30 Days</button>
                </div>
            </div>
            <section class='insights-box'>
                <div class='box-header'>⚡ 本周重点摘要</div>
                {insights_html or "<div class='insight-row'>暂无足够数据生成摘要...</div>"}
            </section>
            <section class='health-box'>
                <div class='box-header'>🩺 信源健康状态</div>
                <table class='health-table'>
                    <thead>
                        <tr>
                            <th>分类</th>
                            <th>信源</th>
                            <th>状态</th>
                            <th>近7天条目</th>
                            <th>错误信息</th>
                        </tr>
                    </thead>
                    <tbody>
                        {health_html}
                    </tbody>
                </table>
            </section>
            {sections_html}
        </main>
        {js}
    </body>
    </html>
    """

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(full_html)


def fetch_data():
    now = datetime.now()
    time_limit = now - timedelta(days=7)
    all_data = []
    source_health = []

    for category, sources in RSS_SOURCES.items():
        for source, url in sources.items():
            items, status = parse_feed_items(category, source, url, time_limit)
            all_data.extend(items)
            source_health.append(status)

    # 去重（同链接只保留最新）
    unique_by_link = {}
    for item in sorted(all_data, key=lambda x: x["ts"], reverse=True):
        if item["link"] not in unique_by_link:
            unique_by_link[item["link"]] = item
    all_data = list(unique_by_link.values())

    inject_x_fallback_cards(all_data, time_limit)

    ai_client = build_ai_client()
    for item in all_data:
        if not item.get("summary"):
            item["summary"] = generate_ai_summary(ai_client, item)

    all_data.sort(key=lambda x: x["ts"], reverse=True)
    render_dashboard(all_data, source_health)
    print(f"[OK] Generated index.html with {len(all_data)} items")


if __name__ == "__main__":
    fetch_data()
