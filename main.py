import feedparser
import re
import json
from datetime import datetime, timedelta

# ==========================================
# 1. 资源配置中心 (增加大神与公众号)
# ==========================================
RSS_SOURCES = {
    "📱 微信公众号特供": {
        "独立站与SEO艺术": "https://rss.feed43.com/8321564752108546.xml", # 换成备用源
        "SEO技术流": "https://rss.feed43.com/5431687421095314.xml"   # 换成备用源
    },
    "🔥 SEO 大神动态": {
        "SEO Roundtable (Barry)": "https://www.seroundtable.com/rss.xml",
        "Aleyda Solis": "https://www.aleydasolis.com/en/blog/feed/",
        "Lily Ray": "https://www.lilyray.ai/blog-feed.xml",
        "Marie Haynes": "https://www.mariehaynes.com/feed/",
        "Backlinko (Brian Dean)": "https://backlinko.com/feed/"
    },
    "🤖 AI 核心前沿": {
        "OpenAI News": "https://openai.com/news/rss.xml",
        "Anthropic News": "https://www.anthropic.com/index.xml",
        "The Rundown AI": "https://www.therundown.ai/feed"
    },
    "🏢 官方与大厂动态": {
        "Google Search Blog": "https://developers.google.com/search/blog/feed.xml",
        "Semrush Blog": "https://www.semrush.com/blog/feed/",
        "Ahrefs Blog": "https://ahrefs.com/blog/feed/"
    }
}

def clean_html(raw_html):
    if not raw_html: return "点击阅读原文了解详情..."
    if isinstance(raw_html, list): raw_html = raw_html[0].get('value', '')
    cleantext = re.sub('<.*?>', '', str(raw_html))
    return cleantext[:150] + "..." if len(cleantext) > 150 else cleantext

def fetch_data():
    # 抓取最近 7 天所有数据
    time_limit = datetime.now() - timedelta(days=8)
    all_entries = []
    
    for category, sources in RSS_SOURCES.items():
        for name, url in sources.items():
            try:
                # 针对不同站点的日期格式和反爬做兼容
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    dt = entry.get('published_parsed') or entry.get('updated_parsed') or entry.get('created_parsed')
                    if dt:
                        pub_date = datetime(*dt[:6])
                        if pub_date > time_limit:
                            raw_desc = entry.get('summary') or entry.get('description') or (entry.get('content')[0].value if 'content' in entry else "")
                            all_entries.append({
                                "category": category,
                                "source": name,
                                "title": entry.title,
                                "link": entry.link,
                                "date": pub_date.strftime('%Y-%m-%d'),
                                "timestamp": pub_date.timestamp(),
                                "summary": clean_html(raw_desc)
                            })
            except: continue

    # 按时间降序排列
    all_entries.sort(key=lambda x: x['timestamp'], reverse=True)

    # 渲染带有“时间筛选”功能的 HTML
    style = """
    <style>
        :root { --primary: #1a73e8; --bg: #f8f9fa; }
        body { font-family: system-ui, sans-serif; background: var(--bg); margin: 0; display: flex; }
        .sidebar { width: 240px; background: #fff; height: 100vh; position: fixed; border-right: 1px solid #ddd; padding: 20px; }
        .main { margin-left: 280px; padding: 40px; flex: 1; }
        .filter-tabs { display: flex; gap: 10px; margin-bottom: 30px; background: #eee; padding: 5px; border-radius: 8px; width: fit-content; }
        .tab { padding: 8px 20px; border-radius: 6px; cursor: pointer; border: none; background: none; font-weight: bold; }
        .tab.active { background: #fff; box-shadow: 0 2px 4px rgba(0,0,0,0.1); color: var(--primary); }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }
        .card { background: #fff; border-radius: 12px; padding: 20px; border: 1px solid #eee; display: flex; flex-direction: column; transition: 0.3s; }
        .card:hover { transform: translateY(-5px); box-shadow: 0 10px 20px rgba(0,0,0,0.08); }
        .tag { font-size: 0.7rem; color: var(--primary); background: #e8f0fe; padding: 3px 8px; border-radius: 4px; margin-bottom: 10px; align-self: flex-start; }
        .date { font-size: 0.8rem; color: #999; margin-top: auto; padding-top: 15px; }
        h3 { font-size: 1.1rem; margin: 0 0 10px; line-height: 1.4; color: #222; }
        p { font-size: 0.9rem; color: #666; line-height: 1.6; }
        .hidden { display: none; }
    </style>
    """

    js_script = """
    <script>
        function filterTime(days, btn) {
            const now = Math.floor(Date.now() / 1000);
            const limit = days * 86400;
            document.querySelectorAll('.card').forEach(card => {
                const ts = parseInt(card.dataset.ts);
                card.classList.toggle('hidden', (now - ts) > limit);
            });
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            btn.classList.add('active');
        }
    </script>
    """

    cards_html = ""
    for e in all_entries:
        cards_html += f"""
        <div class='card' data-ts='{int(e['timestamp'])}'>
            <div class='tag'>{e['source']}</div>
            <h3>{e['title']}</h3>
            <p>{e['summary']}</p>
            <div class='date'>📅 {e['date']} <a href='{e['link']}' target='_blank' style='float:right; color:var(--primary); text-decoration:none;'>阅读全文 →</a></div>
        </div>
        """

    full_html = f"""
    <html><head><meta charset='utf-8'><title>SEO 情报台</title>{style}</head>
    <body>
        <div class='sidebar'>
            <h2>🔍 监控目录</h2>
            <div style='color:#666; font-size:0.85rem;'>
                <p>已监控 15+ 核心源<br>含微信公众号/SEO大神</p>
            </div>
        </div>
        <div class='main'>
            <h1>🚀 SEO & AI 深度情报站</h1>
            <div class='filter-tabs'>
                <button class='tab active' onclick='filterTime(7, this)'>全部 (7天)</button>
                <button class='tab' onclick='filterTime(3, this)'>近 3 天</button>
                <button class='tab' onclick='filterTime(1, this)'>今日更新</button>
            </div>
            <div class='grid'>{cards_html}</div>
        </div>
        {js_script}
    </body></html>
    """
    
    with open("index.html", "w", encoding="utf-8") as f: f.write(full_html)

if __name__ == "__main__": fetch_data()
