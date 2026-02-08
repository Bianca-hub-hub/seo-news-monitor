import feedparser
import re
from datetime import datetime, timedelta

# ==========================================
# 1. 资源配置中心 (已补全所有核心 SEO 大神)
# ==========================================
RSS_SOURCES = {
    "🔥 SEO 大神 & 专家": {
        "SEO Roundtable (Barry)": "https://www.seroundtable.com/rss.xml",
        "Aleyda Solis": "https://www.aleydasolis.com/en/blog/feed/",
        "Lily Ray": "https://www.lilyray.ai/blog-feed.xml",
        "Marie Haynes": "https://www.mariehaynes.com/feed/",
        "SparkToro (Rand Fishkin)": "https://sparktoro.com/blog/feed/",
        "Backlinko (Brian Dean)": "https://backlinko.com/feed/",
        "Cyrus Shepard": "https://www.amsive.com/insights/seo/feed/"
    },
    "🤖 AI 核心资讯": {
        "OpenAI News": "https://openai.com/news/rss.xml",
        "Anthropic News": "https://www.anthropic.com/index.xml",
        "AI News (Global)": "https://www.artificialintelligence-news.com/feed/",
        "Unite.AI": "https://www.unite.ai/feed/"
    },
    "🏢 官方与工具大厂": {
        "Google Search Blog": "https://developers.google.com/search/blog/feed.xml",
        "Semrush Blog": "https://www.semrush.com/blog/feed/",
        "Ahrefs Blog": "https://ahrefs.com/blog/feed/",
        "Moz Blog": "https://moz.com/posts/rss/blog"
    }
}

def clean_html(raw_html):
    if not raw_html: return "点击阅读全文查看详情..."
    if isinstance(raw_html, list): raw_html = raw_html[0].get('value', '')
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', str(raw_html))
    return cleantext[:150] + "..." if len(cleantext) > 150 else cleantext

def fetch_data():
    # 扩大至 8 天跨度，抵消时区偏差
    time_limit = datetime.now() - timedelta(days=8)
    html_content = ""
    sidebar_links = ""
    any_news_found = False
    
    for category, sources in RSS_SOURCES.items():
        sidebar_links += f"<div class='nav-group'><h3>{category}</h3>"
        category_inner_html = ""
        
        for name, url in sources.items():
            site_link = url.replace('rss.xml', '').replace('feed/', '').replace('feed', '')
            sidebar_links += f"<a href='{site_link}' target='_blank' class='nav-item'>🔗 {name}</a>"
            
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    # 多标签日期识别
                    dt = entry.get('published_parsed') or entry.get('updated_parsed') or entry.get('created_parsed')
                    
                    if dt and datetime(*dt[:6]) > time_limit:
                        any_news_found = True
                        # 多字段内容探测
                        raw_desc = entry.get('summary') or entry.get('description') or (entry.get('content')[0].value if 'content' in entry else "")
                        summary = clean_html(raw_desc)
                        
                        category_inner_html += f"""
                        <div class='card'>
                            <div class='source-tag'>{name}</div>
                            <h3>{entry.title}</h3>
                            <p class='summary'>{summary}</p>
                            <div class='card-footer'>
                                <span class='date'>📅 {datetime(*dt[:6]).strftime('%Y-%m-%d')}</span>
                                <a href='{entry.link}' target='_blank' class='btn'>阅读全文 →</a>
                            </div>
                        </div>
                        """
            except: continue
        
        sidebar_links += "</div>"
        if category_inner_html:
            html_content += f"<div class='category-section'><div class='category-header'><h2>{category}</h2></div><div class='grid'>{category_inner_html}</div></div>"

    # CSS 样式增强 (包含侧边栏)
    style = """
    <style>
        :root { --primary: #1a73e8; --bg: #f8f9fa; }
        body { font-family: system-ui, -apple-system, sans-serif; background: var(--bg); margin: 0; display: flex; color: #202124; }
        .sidebar { width: 260px; background: #fff; height: 100vh; position: fixed; border-right: 1px solid #dadce0; padding: 25px 15px; overflow-y: auto; }
        .sidebar h2 { font-size: 1.1rem; color: var(--primary); margin-bottom: 20px; border-bottom: 2px solid var(--primary); padding-bottom: 10px; }
        .nav-group { margin-bottom: 25px; }
        .nav-group h3 { font-size: 0.75rem; color: #70757a; text-transform: uppercase; margin-bottom: 10px; }
        .nav-item { display: block; padding: 8px 10px; color: #444; text-decoration: none; font-size: 0.85rem; border-radius: 6px; margin-bottom: 4px; }
        .nav-item:hover { background: #e8f0fe; color: var(--primary); }
        .main-content { margin-left: 290px; flex: 1; padding: 40px; }
        .category-header { margin: 30px 0 20px; border-left: 6px solid var(--primary); padding: 10px 15px; background: #fff; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 20px; }
        .card { background: #fff; border-radius: 12px; padding: 24px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); display: flex; flex-direction: column; transition: 0.3s; border: 1px solid #eee; }
        .card:hover { transform: translateY(-5px); box-shadow: 0 8px 20px rgba(0,0,0,0.12); }
        .source-tag { font-size: 0.72rem; font-weight: bold; color: var(--primary); background: #e8f0fe; padding: 3px 8px; border-radius: 4px; align-self: flex-start; margin-bottom: 12px; }
        h3 { font-size: 1.1rem; margin: 0 0 12px; line-height: 1.4; color: #1c1e21; height: 3em; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
        .summary { font-size: 0.9rem; color: #5f6368; flex-grow: 1; margin-bottom: 20px; display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; }
        .card-footer { display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #f1f3f4; padding-top: 15px; }
        .date { font-size: 0.8rem; color: #9aa0a6; }
        .btn { background: var(--primary); color: white; text-decoration: none; padding: 8px 16px; border-radius: 6px; font-size: 0.85rem; font-weight: 500; }
        @media (max-width: 800px) { .sidebar { display: none; } .main-content { margin-left: 0; } }
    </style>
    """

    full_html = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head><meta charset="utf-8"><title>SEO/AI 情报监控站</title>{style}</head>
    <body>
        <div class="sidebar"><h2>🔍 资源目录</h2>{sidebar_links}</div>
        <div class="main-content">
            <div style="text-align:center; margin-bottom:40px;">
                <h1>🚀 SEO & AI 专家情报站</h1>
                <p>自动汇总过去 7 天动态 | 更新时间 (UTC): {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
            </div>
            {html_content if any_news_found else "<div style='text-align:center; padding-top:100px; color:#999;'>最近 7 天暂无新发文，请通过左侧目录访问官网。</div>"}
        </div>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f: f.write(full_html)

if __name__ == "__main__": fetch_data()
