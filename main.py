import feedparser
import re
from datetime import datetime, timedelta

# ==========================================
# 1. 资源全量库 (补全所有大神源，去掉公众号)
# ==========================================
RSS_SOURCES = {
    "🔥 SEO 大神 & 专家动态": {
        "SEO Roundtable (Barry Schwartz)": "https://www.seroundtable.com/rss.xml",
        "Lily Ray": "https://www.lilyray.ai/blog-feed.xml",
        "Aleyda Solis (Orainti)": "https://www.aleydasolis.com/en/blog/feed/",
        "Marie Haynes": "https://www.mariehaynes.com/feed/",
        "Backlinko (Brian Dean)": "https://backlinko.com/feed/",
        "Search Engine Land": "https://searchengineland.com/feed",
        "Kevin Indig": "https://www.kevin-indig.com/rss/"
    },
    "🤖 AI & 搜索前沿": {
        "Google Search Blog": "https://developers.google.com/search/blog/feed.xml",
        "OpenAI News": "https://openai.com/news/rss.xml",
        "Anthropic News": "https://www.anthropic.com/index.xml",
        "The Rundown AI": "https://www.therundown.ai/feed"
    },
    "🏢 官方与工具大厂": {
        "Semrush Blog": "https://www.semrush.com/blog/feed/",
        "Ahrefs Blog": "https://ahrefs.com/blog/feed/",
        "Moz Blog": "https://moz.com/posts/rss/blog"
    }
}

def clean_html(raw):
    if not raw: return "点击阅读原文查看..."
    if isinstance(raw, list): raw = raw[0].get('value', '')
    text = re.sub('<.*?>', '', str(raw)).strip()
    return text[:140] + "..." if len(text) > 140 else (text or "点击阅读原文查看...")

def fetch_data():
    # 抓取 7 天内数据，解决时区漏抓问题
    time_limit_7d = datetime.now() - timedelta(days=7)
    time_limit_3d = datetime.now() - timedelta(days=3)
    
    category_data = {}

    for category, sources in RSS_SOURCES.items():
        category_data[category] = []
        for name, url in sources.items():
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    dt = entry.get('published_parsed') or entry.get('updated_parsed') or entry.get('created_parsed')
                    if dt:
                        pub_date = datetime(*dt[:6])
                        if pub_date > time_limit_7d:
                            category_data[category].append({
                                "source": name,
                                "title": entry.title.strip(),
                                "link": entry.link,
                                "ts": int(pub_date.timestamp()),
                                "date": pub_date.strftime('%m-%d'),
                                "summary": clean_html(entry.get('summary') or entry.get('description', '')),
                                "is_recent_3d": pub_date > time_limit_3d
                            })
            except: continue
        # 按时间排序
        category_data[category].sort(key=lambda x: x['ts'], reverse=True)

    # UI 样式
    style = """
    <style>
        :root { --primary: #1a73e8; --bg: #f8f9fa; }
        body { font-family: -apple-system, system-ui, sans-serif; background: var(--bg); margin: 0; padding: 40px 20px; color: #202124; }
        .container { max-width: 1000px; margin: 0 auto; }
        .section { margin-bottom: 60px; }
        h1 { color: var(--primary); text-align: center; margin-bottom: 40px; }
        h2 { border-left: 5px solid var(--primary); padding-left: 15px; margin-bottom: 20px; }
        
        /* 概括简报样式 */
        .summary-brief { background: #fff; border: 1px solid #dadce0; border-radius: 8px; padding: 20px; margin-bottom: 25px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
        .summary-brief h4 { margin: 0 0 15px 0; color: #d93025; font-size: 1rem; border-bottom: 1px solid #eee; padding-bottom: 8px; }
        .brief-list { list-style: none; padding: 0; margin: 0; }
        .brief-item { font-size: 0.9rem; padding: 6px 0; display: flex; align-items: baseline; gap: 10px; border-bottom: 1px dashed #f1f3f4; }
        .brief-item .date { color: #70757a; font-family: monospace; font-size: 0.8rem; }
        .brief-item .src { font-weight: bold; color: #5f6368; min-width: 80px; }
        .brief-item a { color: var(--primary); text-decoration: none; }
        .brief-item a:hover { text-decoration: underline; }

        /* 卡片网格 */
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }
        .card { background: #fff; border-radius: 12px; padding: 20px; border: 1px solid #dadce0; transition: 0.2s; display: flex; flex-direction: column; }
        .card:hover { border-color: var(--primary); transform: translateY(-2px); }
        .card-src { font-size: 0.75rem; color: var(--primary); font-weight: bold; margin-bottom: 8px; }
        .card h3 { font-size: 1rem; margin: 0 0 10px 0; line-height: 1.4; height: 2.8em; overflow: hidden; }
        .card p { font-size: 0.85rem; color: #5f6368; flex-grow: 1; margin-bottom: 15px; }
        .card-meta { font-size: 0.8rem; color: #9aa0a6; border-top: 1px solid #f1f3f4; padding-top: 12px; display: flex; justify-content: space-between; }
    </style>
    """

    main_html = ""
    for cat, entries in category_data.items():
        if not entries: continue
        
        # 1. 生成该分类的概括简报
        brief_items = "".join([
            f"<li class='brief-item'><span class='date'>{e['date']}</span><span class='src'>[{e['source']}]</span><a href='{e['link']}' target='_blank'>{e['title']}</a></li>"
            for e in entries[:10] # 简报展示最近10条
        ])
        
        # 2. 生成深度阅读卡片
        cards = "".join([
            f"<div class='card'><div class='card-src'>{e['source']}</div><h3>{e['title']}</h3><p>{e['summary']}</p><div class='card-meta'><span>📅 {e['date']}</span><a href='{e['link']}' target='_blank' style='color:var(--primary);text-decoration:none;font-weight:bold;'>详情 →</a></div></div>"
            for e in entries
        ])

        main_html += f"""
        <div class="section">
            <h2>{cat}</h2>
            <div class="summary-brief">
                <h4>📋 本周/三日更新概括 (快速扫描)</h4>
                <ul class="brief-list">{brief_items}</ul>
            </div>
            <div class="grid">{cards}</div>
        </div>
        """

    full_html = f"""
    <html><head><meta charset='utf-8'><title>SEO大神情报站</title>{style}</head>
    <body>
        <div class="container">
            <h1>🚀 SEO & AI 深度监控 (专家站版)</h1>
            {main_html}
        </div>
    </body></html>
    """
    with open("index.html", "w", encoding="utf-8") as f: f.write(full_html)

if __name__ == "__main__": fetch_data()
