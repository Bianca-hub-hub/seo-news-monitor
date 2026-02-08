import feedparser
import re
from datetime import datetime, timedelta

# ==========================================
# 1. 资源配置中心 (包含你要求的所有大神、AI与官方源)
# ==========================================
RSS_SOURCES = {
    "🔥 SEO 大神 & 专家": {
        "SEO Roundtable": "https://www.seroundtable.com/rss.xml",
        "Aleyda Solis": "https://www.aleydasolis.com/en/blog/feed/",
        "Lily Ray": "https://www.lilyray.ai/blog-feed.xml",
        "Marie Haynes": "https://www.mariehaynes.com/feed/",
        "Rand Fishkin (SparkToro)": "https://sparktoro.com/blog/feed/",
        "Brian Dean (Backlinko)": "https://backlinko.com/feed",
        "Cyrus Shepard": "https://www.amsive.com/insights/seo/feed/"
    },
    "🤖 AI 核心前沿": {
        "OpenAI News": "https://openai.com/news/rss.xml",
        "Anthropic News": "https://www.anthropic.com/index.xml",
        "AI News": "https://www.artificialintelligence-news.com/feed/",
        "Unite.AI": "https://www.unite.ai/feed/"
    },
    "🏢 官方与工具大厂": {
        "Google Search Blog": "https://developers.google.com/search/blog/feed.xml",
        "Semrush Blog": "https://www.semrush.com/blog/feed/",
        "Ahrefs Blog": "https://ahrefs.com/blog/feed/",
        "Moz Blog": "https://moz.com/posts/rss/blog"
    }
}

# ==========================================
# 2. 辅助功能
# ==========================================
def clean_html(raw_html):
    """清理HTML并截取摘要"""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext[:160] + "..." if len(cleantext) > 160 else cleantext

def fetch_data():
    # 时间跨度改为 7 天
    time_limit = datetime.now() - timedelta(days=7)
    html_content = ""
    sidebar_links = ""
    any_news_found = False
    
    for category, sources in RSS_SOURCES.items():
        sidebar_links += f"<div class='nav-group'><h3>{category}</h3>"
        category_id = category.replace(" ", "-")
        category_html = f"<div id='{category_id}' class='category-section'><div class='category-header'><h2>{category}</h2></div><div class='grid'>"
        found_in_category = False
        
        for name, url in sources.items():
            # 侧边栏链接：即便没更新也可以点击跳转原站
            sidebar_links += f"<a href='{url.replace('feed/', '').replace('rss.xml', '')}' target='_blank' class='nav-item'>🔗 {name}</a>"
            
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    dt = entry.get('published_parsed') or entry.get('updated_parsed')
                    if dt and datetime(*dt[:6]) > time_limit:
                        found_in_category = any_news_found = True
                        summary = clean_html(entry.get('summary', entry.get('description', '查看正文获取更多细节...')))
                        
                        category_html += f"""
                        <div class='card'>
                            <div class='source-tag'>{name}</div>
                            <h3>{entry.title}</h3>
                            <p class='summary'>{summary}</p>
                            <div class='card-footer'>
                                <span class='date'>📅 {datetime(*dt[:6]).strftime('%m-%d')}</span>
                                <a href='{entry.link}' target='_blank' class='btn'>阅读全文 →</a>
                            </div>
                        </div>
                        """
            except: continue
        
        sidebar_links += "</div>"
        category_html += "</div></div>"
        if found_in_category:
            html_content += category_html

    # ==========================================
    # 3. 页面样式 (左右布局设计)
    # ==========================================
    style = """
    <style>
        :root { --primary: #1a73e8; --bg: #f4f7f6; --sidebar-bg: #ffffff; }
        body { font-family: 'Inter', system-ui, sans-serif; background: var(--bg); margin: 0; display: flex; color: #202124; }
        
        /* 侧边栏样式 */
        .sidebar { width: 280px; background: var(--sidebar-bg); height: 100vh; position: fixed; border-right: 1px solid #e0e0e0; padding: 20px; overflow-y: auto; }
        .sidebar h2 { color: var(--primary); font-size: 1.2rem; margin-bottom: 25px; border-bottom: 2px solid var(--primary); padding-bottom: 10px; }
        .nav-group { margin-bottom: 25px; }
        .nav-group h3 { font-size: 0.85rem; color: #70757a; text-transform: uppercase; margin-bottom: 12px; letter-spacing: 1px; }
        .nav-item { display: block; padding: 8px 12px; color: #444; text-decoration: none; font-size: 0.9rem; border-radius: 6px; margin-bottom: 4px; transition: 0.2s; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .nav-item:hover { background: #e8f0fe; color: var(--primary); }

        /* 主内容区样式 */
        .main-content { margin-left: 320px; flex: 1; padding: 40px; }
        .top-header { text-align: center; margin-bottom: 50px; }
        .top-header h1 { font-size: 2.2rem; color: var(--primary); margin-bottom: 10px; }
        .category-header { margin: 40px 0 20px; border-left: 6px solid var(--primary); padding-left: 15px; background: #fff; padding: 10px 15px; border-radius: 4px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }
        .card { background: #fff; border-radius: 12px; padding: 20px; box-shadow: 0 4px 10px rgba(0,0,0,0.06); display: flex; flex-direction: column; transition: 0.3s; border: 1px solid #efefef; }
        .card:hover { transform: translateY(-5px); box-shadow: 0 8px 20px rgba(0,0,0,0.1); }
        .source-tag { font-size: 0.7rem; font-weight: bold; color: var(--primary); background: #e8f0fe; padding: 3px 8px; border-radius: 4px; align-self: flex-start; margin-bottom: 12px; }
        h3 { font-size: 1.05rem; margin: 0 0 12px; line-height: 1.4; color: #1c1e21; }
        .summary { font-size: 0.88rem; color: #5f6368; flex-grow: 1; margin-bottom: 15px; display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; }
        .card-footer { display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #f1f3f4; padding-top: 12px; }
        .date { font-size: 0.8rem; color: #9aa0a6; }
        .btn { background: var(--primary); color: white; text-decoration: none; padding: 6px 14px; border-radius: 6px; font-size: 0.85rem; font-weight: 500; }
        
        @media (max-width: 900px) { .sidebar { display: none; } .main-content { margin-left: 0; } }
    </style>
    """

    full_html = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head><meta charset="utf-8"><title>SEO & AI 专家监控台</title>{style}</head>
    <body>
        <div class="sidebar">
            <h2>🔍 资源监控目录</h2>
            {sidebar_links}
            <p style="margin-top:40px; font-size:0.7rem; color:#bdc3c7;">点击上方名称可直达官网</p>
        </div>
        <div class="main-content">
            <div class="top-header">
                <h1>🚀 SEO & AI 专家情报站</h1>
                <p>滚动追踪过去 7 天专家动态 | UTC: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
            </div>
            {html_content if any_news_found else "<div style='text-align:center; padding:100px; color:#999;'>最近 7 天暂无新发文，请通过左侧目录直接访问官网。</div>"}
        </div>
    </body>
    </html>
    """
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(full_html)

if __name__ == "__main__":
    fetch_data()
