import feedparser
import re
from datetime import datetime, timedelta

# ==========================================
# 1. RESOURCE CONFIGURATION (Full Expert List)
# ==========================================
RSS_SOURCES = {
    "SEO EXPERTS & INFLUENCERS": {
        "SEO Roundtable (Barry Schwartz)": "https://www.seroundtable.com/rss.xml",
        "Lily Ray": "https://www.lilyray.ai/blog-feed.xml",
        "Aleyda Solis (Orainti)": "https://www.aleydasolis.com/en/blog/feed/",
        "Marie Haynes": "https://www.mariehaynes.com/feed/",
        "Backlinko (Brian Dean)": "https://backlinko.com/feed/",
        "Search Engine Land": "https://searchengineland.com/feed",
        "Kevin Indig": "https://www.kevin-indig.com/rss/",
        "Detailed (Glenn Allsopp)": "https://detailed.com/feed/",
        "Goralewicz (On-page SEO)": "https://onely.com/blog/feed/"
    },
    "AI & SEARCH INNOVATION": {
        "Google Search Blog": "https://developers.google.com/search/blog/feed.xml",
        "OpenAI News": "https://openai.com/news/rss.xml",
        "Anthropic News": "https://www.anthropic.com/index.xml",
        "The Rundown AI": "https://www.therundown.ai/feed"
    },
    "SEO TOOLS & INDUSTRY GIANTS": {
        "Semrush Blog": "https://www.semrush.com/blog/feed/",
        "Ahrefs Blog": "https://ahrefs.com/blog/feed/",
        "Moz Blog": "https://moz.com/posts/rss/blog",
        "Search Engine Journal": "https://www.searchenginejournal.com/feed/"
    }
}

def clean_html(raw):
    if not raw: return "Click to read full article..."
    if isinstance(raw, list): raw = raw[0].get('value', '')
    text = re.sub('<.*?>', '', str(raw)).strip()
    return (text[:150] + "...") if len(text) > 150 else (text or "Click to read full article...")

def fetch_data():
    limit_7d = datetime.now() - timedelta(days=7)
    limit_3d = datetime.now() - timedelta(days=3)
    category_data = {}

    for cat, sources in RSS_SOURCES.items():
        category_data[cat] = []
        for name, url in sources.items():
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    dt = entry.get('published_parsed') or entry.get('updated_parsed')
                    if dt:
                        p_date = datetime(*dt[:6])
                        if p_date > limit_7d:
                            category_data[cat].append({
                                "source": name,
                                "title": entry.title.strip(),
                                "link": entry.link,
                                "ts": int(p_date.timestamp()),
                                "date": p_date.strftime('%m-%d'),
                                "summary": clean_html(entry.get('summary') or entry.get('description', '')),
                                "is_3d": p_date > limit_3d
                            })
            except: continue
        category_data[cat].sort(key=lambda x: x['ts'], reverse=True)

    style = """
    <style>
        :root { --primary: #1a73e8; --bg: #f8f9fa; --text: #202124; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 40px 20px; }
        .container { max-width: 1100px; margin: 0 auto; }
        .section { margin-bottom: 60px; }
        h1 { text-align: center; color: var(--primary); font-size: 2.2rem; margin-bottom: 40px; }
        h2 { border-left: 6px solid var(--primary); padding-left: 15px; font-size: 1.5rem; margin-bottom: 25px; }
        
        /* SUMMARY BOX */
        .summary-box { background: #fff; border: 1px solid #dadce0; border-radius: 12px; padding: 25px; margin-bottom: 30px; }
        .summary-box h4 { margin: 0 0 15px 0; font-size: 1.1rem; color: #d93025; border-bottom: 1px solid #eee; padding-bottom: 10px; }
        .brief-list { list-style: none; padding: 0; margin: 0; }
        .brief-item { display: flex; align-items: baseline; gap: 15px; padding: 8px 0; border-bottom: 1px dashed #f1f3f4; font-size: 0.95rem; }
        .date-label { color: #70757a; font-family: monospace; font-size: 0.85rem; min-width: 45px; }
        .src-label { font-weight: bold; color: #5f6368; min-width: 110px; }
        .brief-link { color: var(--primary); text-decoration: none; font-weight: 500; }
        .brief-link:hover { text-decoration: underline; }
        .recent-tag { background: #e6f4ea; color: #137333; font-size: 0.7rem; padding: 2px 6px; border-radius: 4px; font-weight: bold; }

        /* GRID CARDS */
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 25px; }
        .card { background: #fff; border-radius: 12px; padding: 24px; border: 1px solid #dadce0; display: flex; flex-direction: column; transition: 0.2s; }
        .card:hover { border-color: var(--primary); transform: translateY(-3px); box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
        .card-src { color: var(--primary); font-size: 0.75rem; font-weight: bold; margin-bottom: 10px; text-transform: uppercase; }
        .card h3 { font-size: 1.1rem; margin: 0 0 12px 0; line-height: 1.4; height: 3em; overflow: hidden; }
        .card p { font-size: 0.9rem; color: #5f6368; line-height: 1.6; margin-bottom: 20px; flex-grow: 1; }
        .card-meta { font-size: 0.85rem; color: #9aa0a6; border-top: 1px solid #f1f3f4; padding-top: 15px; display: flex; justify-content: space-between; align-items: center; }
        .read-btn { color: var(--primary); text-decoration: none; font-weight: bold; }
    </style>
    """

    content_html = ""
    for cat, entries in category_data.items():
        if not entries: continue
        
        brief_rows = "".join([
            f"<li class='brief-item'>"
            f"<span class='date-label'>{e['date']}</span>"
            f"<span class='src-label'>[{e['source']}]</span>"
            f"<a href='{e['link']}' class='brief-link' target='_blank'>{e['title']}</a>"
            f"{'<span class='recent-tag'>NEW</span>' if e['is_3d'] else ''}</li>"
            for e in entries[:12]
        ])

        cards = "".join([
            f"<div class='card'>"
            f"<div class='card-src'>{e['source']}</div>"
            f"<h3>{e['title']}</h3>"
            f"<p>{e['summary']}</p>"
            f"<div class='card-meta'><span>{e['date']}</span><a href='{e['link']}' class='read-btn' target='_blank'>Full Story →</a></div>"
            f"</div>" for e in entries
        ])

        content_html += f"""
        <div class="section">
            <h2>{cat}</h2>
            <div class="summary-box">
                <h4>QUICK SCAN: Weekly Intelligence Report</h4>
                <ul class="brief-list">{brief_rows}</ul>
            </div>
            <div class="grid">{cards}</div>
        </div>
        """

    full_page = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head><meta charset="utf-8"><title>SEO Intelligence Dashboard</title>{style}</head>
    <body>
        <div class="container">
            <h1>SEO & SEARCH INTELLIGENCE</h1>
            {content_html}
        </div>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f: f.write(full_page)

if __name__ == "__main__": fetch_data()
