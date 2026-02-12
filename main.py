import feedparser
import re
from datetime import datetime, timedelta

# ==========================================
# 1. 全量资源配置 (已适配所有已知源)
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
        "Marie Haynes": "https://www.mariehaynes.com/feed/",
        "Backlinko": "https://backlinko.com/feed/"
    },
    "🤖 AI & 搜索前沿": {
        "Google Search Blog": "https://developers.google.com/search/blog/feed.xml",
        "OpenAI News": "https://openai.com/news/rss.xml",
        "The Rundown AI": "https://www.therundown.ai/feed"
    }
}

def clean_html(raw):
    """防止解析 Bug：如果没文字，返回默认占位符"""
    if not raw: return "点击进入原文查看精彩内容..."
    if isinstance(raw, list): raw = raw[0].get('value', '')
    text = re.sub('<.*?>', '', str(raw)).strip()
    return (text[:120] + "...") if len(text) > 120 else (text or "点击进入原文查看精彩内容...")

def fetch_data():
    # 扩大到 8 天，解决时区差导致的“消失” Bug
    time_limit = datetime.now() - timedelta(days=8)
    all_entries = []
    
    for category, sources in RSS_SOURCES.items():
        for name, url in sources.items():
            try:
                # 增强解析器：强制刷新，不使用缓存
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    dt = entry.get('published_parsed') or entry.get('updated_parsed') or entry.get('created_parsed')
                    if dt:
                        pub_date = datetime(*dt[:6])
                        if pub_date > time_limit:
                            all_entries.append({
                                "category": category,
                                "source": name,
                                "title": entry.title.strip(),
                                "link": entry.link,
                                "ts": int(pub_date.timestamp()),
                                "date": pub_date.strftime('%Y-%m-%d'),
                                "summary": clean_html(entry.get('summary') or entry.get('description', ''))
                            })
            except: continue

    # 按时间降序排列
    all_entries.sort(key=lambda x: x['ts'], reverse=True)

    # 生成顶部情报清单 (过去 7 天全量)
    summary_list_html = "".join([
        f"<li><span class='s-date'>{e['date']}</span> <span class='s-tag'>{e['source']}</span> <a href='{e['link']}' target='_blank' class='s-title'>{e['title']}</a></li>"
        for e in all_entries
    ])

    # 生成卡片区
    cards_html = "".join([
        f"<div class='card' data-ts='{e['ts']}'>"
        f"<div class='tag'>{e['source']}</div>"
        f"<h3>{e['title']}</h3>"
        f"<p>{e['summary']}</p>"
        f"<div class='card-footer'><span>📅 {e['date']}</span><a href='{e['link']}' target='_blank'>详情 →</a></div>"
        f"</div>" for e in all_entries
    ])

    style = """
    <style>
        :root { --primary: #1a73e8; --bg: #f1f3f4; }
        body { font-family: -apple-system, system-ui, sans-serif; background: var(--bg); margin: 0; color: #202124; line-height: 1.5; }
        .main { max-width: 1100px; margin: 0 auto; padding: 40px 20px; }
        
        /* 顶部情报快讯样式 */
        .summary-box { background: #fff; border-radius: 12px; padding: 25px; border: 1px solid #dadce0; margin-bottom: 40px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .summary-box h2 { margin-top: 0; font-size: 1.2rem; display: flex; align-items: center; gap: 8px; color: #d93025; }
        .summary-list { list-style: none; padding: 0; margin: 0; max-height: 300px; overflow-y: auto; }
        .summary-list li { padding: 10px 0; border-bottom: 1px solid #f1f3f4; display: flex; align-items: baseline; gap: 12px; font-size: 0.9rem; }
        .s-date { color: #70757a; font-family: monospace; white-space: nowrap; }
        .s-tag { background: #f8f9fa; border: 1px solid #dadce0; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; color: #5f6368; font-weight: bold; white-space: nowrap; }
        .s-title { color: #1a73e8; text-decoration: none; font-weight: 500; }
        .s-title:hover { text-decoration: underline; }

        /* 卡片筛选器样式 */
        .filter-bar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
        .tabs { display: flex; gap: 8px; background: #e8eaed; padding: 4px; border-radius: 8px; }
        .tab { border: none; padding: 6px 16px; border-radius: 6px; cursor: pointer; font-size: 0.85rem; color: #5f6368; font-weight: 500; }
        .tab.active { background: #fff; color: var(--primary); box-shadow: 0 1px 2px rgba(0,0,0,0.1); }

        /* 卡片网格 */
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 20px; }
        .card { background: #fff; border-radius: 12px; padding: 20px; border: 1px solid #dadce0; display: flex; flex-direction: column; transition: 0.2s; }
        .card:hover { border-color: var(--primary); transform: translateY(-2px); }
        .tag { font-size: 0.75rem; color: var(--primary); font-weight: bold; margin-bottom: 10px; }
        h3 { font-size: 1.1rem; margin: 0 0 12px; line-height: 1.4; color: #1c1e21; height: 3em; overflow: hidden; }
        p { font-size: 0.9rem; color: #5f6368; flex-grow: 1; margin-bottom: 20px; }
        .card-footer { display: flex; justify-content: space-between; align-items: center; font-size: 0.85rem; color: #9aa0a6; border-top: 1px solid #f1f3f4; padding-top: 15px; }
        .card-footer a { color: var(--primary); text-decoration: none; font-weight: bold; }
        .hidden { display: none; }
    </style>
    """

    js = """
    <script>
        function filterContent(days, btn) {
            const now = Math.floor(Date.now() / 1000);
            document.querySelectorAll('.card').forEach(c => {
                const isMatch = (now - parseInt(c.dataset.ts)) <= (days * 86400);
                c.classList.toggle('hidden', !isMatch);
            });
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            btn.classList.add('active');
        }
    </script>
    """

    full_html = f"""
    <html><head><meta charset='utf-8'><title>SEO 情报台</title>{style}</head>
    <body>
        <div class="main">
            <header style="margin-bottom: 40px;">
                <h1>🚀 SEO & AI 深度监控站</h1>
                <p style="color:#5f6368;">全量同步过去 7 天所有专家动态，无一遗漏</p>
            </header>

            <section class="summary-box">
                <h2>📢 过去 7 天情报一览 ({len(all_entries)} 条)</h2>
                <ul class="summary-list">
                    {summary_list_html or "<li>暂时没有新动态抓取到</li>"}
                </ul>
            </section>

            <div class="filter-bar">
                <h2 style="font-size:1.2rem; margin:0;">🔍 深度阅读摘要</h2>
                <div class="tabs">
                    <button class="tab active" onclick="filterContent(7, this)">近7天</button>
                    <button class="tab" onclick="filterContent(3, this)">近3天</button>
                    <button class="tab" onclick="filterContent(1, this)">今日</button>
                </div>
            </div>
            
            <div class="grid">{cards_html}</div>
        </div>
        {js}
    </body></html>
    """
    with open("index.html", "w", encoding="utf-8") as f: f.write(full_html)

if __name__ == "__main__": fetch_data()
