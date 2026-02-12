import feedparser
import re
from datetime import datetime, timedelta

# ==========================================
# 1. 资源配置中心 (包含你要求的微信、大神、大厂)
# ==========================================
RSS_SOURCES = {
    "📱 微信公众号特供": {
        "独立站与SEO艺术": "https://rsshub.app/wechat/mp/msghistory/gh_87469796856a",
        "SEO技术流": "https://rsshub.app/wechat/mp/msghistory/gh_a146430932c0"
    },
    "🔥 SEO 大神动态": {
        "SEO Roundtable (大神搬运)": "https://www.seroundtable.com/rss.xml",
        "Aleyda Solis": "https://www.aleydasolis.com/en/blog/feed/",
        "Lily Ray": "https://www.lilyray.ai/blog-feed.xml",
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
    if not raw_html: return "点击阅读全文了解详情..."
    if isinstance(raw_html, list): raw_html = raw_html[0].get('value', '')
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', str(raw_html))
    return cleantext[:150] + "..." if len(cleantext) > 150 else cleantext

def fetch_data():
    # 跨度改为 7 天，确保内容足够丰富
    time_limit = datetime.now() - timedelta(days=7)
    html_content = ""
    sidebar_links = ""
    any_news_found = False
    
    for category, sources in RSS_SOURCES.items():
        sidebar_links += f"<div class='nav-group'><h3>{category}</h3>"
        category_inner_html = ""
        
        for name, url in sources.items():
            # 生成侧边栏快捷链接
            site_link = url.replace('rss.xml', '').replace('feed/', '')
            sidebar_links += f"<a href='{site_link}' target='_blank' class='nav-item'>🔗 {name}</a>"
            
            try:
                # 微信公众号抓取需要设置 User-Agent 防止被封
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    # 尝试解析多个可能的日期字段
                    dt = entry.get('published_parsed') or entry.get('updated_parsed') or entry.get('created_parsed')
                    if dt and datetime(*dt[:6]) > time_limit:
                        any_news_found = True
                        # 深度挖掘内容摘要
                        raw_desc = entry.get('summary') or entry.get('description') or (entry.get('content')[0].value if 'content' in entry else "")
                        summary = clean_html(raw_desc)
                        
                        category_inner_html += f"""
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
        if category_inner_html:
            html_content += f"<div class='category-section'><h2>{category}</h2><div class='grid'>{category_inner_html}</div></div>"

    # ==========================================
    # 2. UI 极致简化布局 (CSS)
    # ==========================================
    style = """
    <style>
        :root { --primary: #1a73e8; --bg: #f8f9fa; --sidebar: #ffffff; }
        body { font-family: -apple-system, system-ui, sans-serif; background: var(--bg); margin: 0; display: flex; color: #202124; }
        
        /* 侧边栏样式 */
        .sidebar { width: 260px; background: var(--sidebar); height: 100vh; position: fixed; border-right: 1px solid #dadce0; padding: 25px 15px; overflow-y: auto; }
        .sidebar h2 { font-size: 1.1rem; color: var(--primary); margin-bottom: 25px; border-bottom: 2px solid var(--primary); padding-bottom: 10px; }
        .nav-group h3 { font-size: 0.75rem; color: #70757a; text-transform: uppercase; margin: 20px 0 10px; padding-left: 5px; }
        .nav-item { display: block; padding: 8px 10px; color: #444; text-decoration: none; font-size: 0.85rem; border-radius: 6px; margin-bottom: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .nav-item:hover { background: #e8f0fe; color: var(--primary); }

        /* 主内容区样式 */
        .main-content { margin-left: 290px; flex: 1; padding: 40px; }
        h1 { font-size: 2rem; color: var(--primary); }
        h2 { border-left: 6px solid var(--primary); padding-left: 15px; margin: 40px 0 20px; font-size: 1.4rem; background: #fff; padding: 10px 15px; border-radius: 4px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 20px; }
        .card { background: #fff; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); display: flex; flex-direction: column; border: 1px solid #eee; transition: 0.3s; }
        .card:hover { transform: translateY(-5px); box-shadow: 0 8px 20px rgba(0,0,0,0.1); }
        .source-tag { font-size: 0.7rem; font-weight: bold; color: var(--primary); background: #e8f0fe; padding: 3px 8px; border-radius: 4px; align-self: flex-start; margin-bottom: 12px; }
        h3 { font-size: 1.05rem; margin: 0 0 12px; line-height: 1.4; color: #1c1e21; height: 3em; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
        .summary { font-size: 0.9rem; color: #5f6368; flex-grow: 1; margin-bottom: 20px; line-height: 1.5; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; }
        .card-footer { display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #f1f3f4; padding-top: 15px; }
        .date { font-size: 0.8rem; color: #9aa0a6; }
        .btn { background: var(--primary); color: white; text-decoration: none; padding: 8px 16px; border-radius: 6px; font-size: 0.8rem; font-weight: bold; }
        
        @media (max-width: 800px) { .sidebar { display: none; } .main-content { margin-left: 0; } }
    </style>
    """

    full_html = f"<html><head><meta charset='utf-8'><title>SEO/AI 情报站</title>{style}</head><body>"
    full_html += f"<div class='sidebar'><h2>🔍 资源目录</h2>{sidebar_links}</div>"
    full_html += f"<div class='main-content'><h1>🚀 SEO & AI 专家情报站</h1><p>已整合公众号、SEO大神及AI前沿动态</p>"
    full_html += (html_content if any_news_found else "<div style='text-align:center; padding:100px; color:#999;'>最近 7 天暂无新文章，请点击左侧目录直达。</div>")
    full_html += "</div></body></html>"
    
    with open("index.html", "w", encoding="utf-8") as f: f.write(full_html)

if __name__ == "__main__": fetch_data()
