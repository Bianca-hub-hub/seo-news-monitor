import feedparser
import re
from datetime import datetime, timedelta

# ==========================================
# 1. 精选资源库 (大神视角：质量优先于数量)
# ==========================================
RSS_SOURCES = {
    "📱 公众号精选": {
        "独立站与SEO艺术": "https://rss.feed43.com/8321564752108546.xml",
        "SEO技术流": "https://rss.feed43.com/5431687421095314.xml"
    },
    "🔥 SEO 大神动态": {
        "SEO Roundtable (Barry)": "https://www.seroundtable.com/rss.xml",
        "Lily Ray": "https://www.lilyray.ai/blog-feed.xml",
        "Aleyda Solis": "https://www.aleydasolis.com/en/blog/feed/",
        "Backlinko": "https://backlinko.com/feed/"
    },
    "🤖 AI & 搜索前沿": {
        "Google Search Blog": "https://developers.google.com/search/blog/feed.xml",
        "OpenAI News": "https://openai.com/news/rss.xml",
        "The Rundown AI": "https://www.therundown.ai/feed"
    }
}

def clean_html(raw_html):
    """提取核心摘要，拒绝噪音"""
    if not raw_html: return "点击阅读原文..."
    if isinstance(raw_html, list): raw_html = raw_html[0].get('value', '')
    text = re.sub('<.*?>', '', str(raw_html))
    return text[:140] + "..." if len(text) > 140 else text

def fetch_data():
    time_limit = datetime.now() - timedelta(days=8)
    all_entries = []
    
    for category, sources in RSS_SOURCES.items():
        for name, url in sources.items():
            try:
                # 增强抓取逻辑，应对不同日期格式
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    dt = entry.get('published_parsed') or entry.get('updated_parsed') or entry.get('created_parsed')
                    if dt:
                        pub_date = datetime(*dt[:6])
                        if pub_date > time_limit:
                            all_entries.append({
                                "category": category,
                                "source": name,
                                "title": entry.title,
                                "link": entry.link,
                                "date": pub_date.strftime('%m-%d'),
                                "timestamp": pub_date.timestamp(),
                                "summary": clean_html(entry.get('summary') or entry.get('description', ''))
                            })
            except: continue

    # 按最新时间排序
    all_entries.sort(key=lambda x: x['timestamp'], reverse=True)

    # ==========================================
    # 2. 现代 Dashboard UI (带时间切换)
    # ==========================================
    style = """
    <style>
        :root { --primary: #1a73e8; --bg: #f8f9fa; }
        body { font-family: -apple-system, system-ui, sans-serif; background: var(--bg); margin: 0; display: flex; color: #202124; }
        .sidebar { width: 250px; background: #fff; height: 100vh; position: fixed; border-right: 1px solid #dadce0; padding: 30px 20px; }
        .main { margin-left: 290px; padding: 40px; flex: 1; max-width: 1200px; }
        .tabs { display: flex; gap: 8px; margin-bottom: 30px; background: #e8eaed; padding: 4px; border-radius: 8px; width: fit-content; }
        .tab { padding: 8px 20px; border: none; border-radius: 6px; cursor: pointer; font-weight: 500; color: #5f6368; background: none; }
        .tab.active { background: #fff; color: var(--primary); box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 24px; }
        .card { background: #fff; border-radius: 12px; padding: 24px; border: 1px solid #dadce0; display: flex; flex-direction: column; transition: 0.2s; }
        .card:hover { border-color: var(--primary); transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
        .source-tag { font-size: 0.75rem; color: var(--primary); background: #e8f0fe; padding: 4px 10px; border-radius: 4px; align-self: flex-start; margin-bottom: 15px; font-weight: bold; }
        h3 { font-size: 1.15rem; margin: 0 0 12px; line-height: 1.4; color: #1c1e21; }
        p { font-size: 0.9rem; color: #5f6368; line-height: 1.6; margin-bottom: 20px; flex-grow: 1; }
        .card-footer { display: flex; justify-content: space-between; align-items: center; color: #9aa0a6; font-size: 0.85rem; }
        .hidden { display: none; }
    </style>
    """

    js = """
    <script>
        function filterNews(days, btn) {
            const now = Math.floor(Date.now() / 1000);
            document.querySelectorAll('.card').forEach(c => {
                const diff = now - parseInt(c.dataset.ts);
                c.classList.toggle('hidden', diff > (days * 86400));
            });
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            btn.classList.add('active');
        }
    </script>
    """

    cards = "".join([f"""
        <div class='card' data-ts='{int(e['timestamp'])}'>
            <div class='source-tag'>{e['source']}</div>
            <h3>{e['title']}</h3>
            <p>{e['summary']}</p>
            <div class='card-footer'>
                <span>📅 {e['date']}</span>
                <a href='{e['link']}' target='_blank' style='color:var(--primary); text-decoration:none;'>Read More →</a>
            </div>
        </div>
    """ for e in all_entries])

    full_html = f"""
    <html><head><meta charset='utf-8'><title>SEO Dashboard</title>{style}</head>
    <body>
        <div class='sidebar'>
            <h2>🔍 资源目录</h2>
            <p style='font-size:0.85rem; color:#666;'>按分类和频率聚合的最优情报源</p>
        </div>
        <div class='main'>
            <h1>🚀 SEO & AI 深度监控</h1>
            <div class='tabs'>
                <button class='tab active' onclick='filterNews(7, this)'>近 7 天</button>
                <button class='tab' onclick='filterNews(3, this)'>近 3 天</button>
                <button class='tab' onclick='filterNews(1, this)'>今日</button>
            </div>
            <div class='grid'>{cards}</div>
        </div>
        {js}
    </body></html>
    """
    with open("index.html", "w", encoding="utf-8") as f: f.write(full_html)

if __name__ == "__main__": fetch_data()
