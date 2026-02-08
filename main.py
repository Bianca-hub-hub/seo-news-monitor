import feedparser
import re
from datetime import datetime, timedelta

# ==========================================
# 1. 配置中心：包含所有你要求的大神和资讯源
# ==========================================
RSS_SOURCES = {
    "🔥 SEO 大神 & 专家动态": [
        "https://www.seroundtable.com/rss.xml",       # Barry Schwartz (聚合所有大神推文)
        "https://www.aleydasolis.com/en/blog/feed/",  # Aleyda Solis
        "https://www.lilyray.ai/blog-feed.xml",       # Lily Ray
        "https://www.mariehaynes.com/feed/",          # Marie Haynes
        "https://sparktoro.com/blog/feed/",           # Rand Fishkin
        "https://backlinko.com/feed",                  # Brian Dean
        "https://www.amsive.com/insights/seo/feed/"   # 包含多个专家的深度分析
    ],
    "🤖 AI 核心资讯": [
        "https://openai.com/news/rss.xml",
        "https://www.anthropic.com/index.xml",
        "https://www.artificialintelligence-news.com/feed/",
        "https://www.unite.ai/feed/"
    ],
    "🏢 官方与大厂动态": [
        "https://developers.google.com/search/blog/feed.xml", # Google Search Central
        "https://www.semrush.com/blog/feed/",                 # Semrush
        "https://ahrefs.com/blog/feed/",                       # Ahrefs
        "https://moz.com/posts/rss/blog"                       # Moz
    ]
}

# ==========================================
# 2. 核心抓取逻辑
# ==========================================
def clean_html(raw_html):
    """清除摘要中的 HTML 标签，保持界面整洁"""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext[:150] + "..." if len(cleantext) > 150 else cleantext

def fetch_data():
    three_days_ago = datetime.now() - timedelta(days=3)
    html_body = ""
    any_news_found = False
    
    for category, urls in RSS_SOURCES.items():
        category_html = f"<div class='category-header'><h2>{category}</h2></div><div class='grid'>"
        found_in_category = False
        
        for url in urls:
            try:
                feed = feedparser.parse(url)
                source_name = feed.feed.get('title', '权威源')
                
                for entry in feed.entries:
                    # 尝试解析发布日期
                    dt = entry.get('published_parsed') or entry.get('updated_parsed')
                    if dt:
                        pub_date = datetime(*dt[:6])
                        if pub_date > three_days_ago:
                            found_in_category = any_news_found = True
                            summary = clean_html(entry.get('summary', entry.get('description', '点击阅读全文了解详情')))
                            
                            category_html += f"""
                            <div class='card'>
                                <div class='source-tag'>{source_name}</div>
                                <h3>{entry.title}</h3>
                                <p class='summary'>{summary}</p>
                                <div class='card-footer'>
                                    <span class='date'>📅 {pub_date.strftime('%Y-%m-%d')}</span>
                                    <a href='{entry.link}' target='_blank' class='btn'>阅读全文 →</a>
                                </div>
                            </div>
                            """
            except Exception as e:
                print(f"Error fetching {url}: {e}")
        
        category_html += "</div>"
        if found_in_category:
            html_body += category_html

    # ==========================================
    # 3. 页面样式 (CSS)
    # ==========================================
    style = """
    <style>
        :root { --primary: #1a73e8; --bg: #f8f9fa; --text: #202124; }
        body { font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text); padding: 40px 20px; max-width: 1200px; margin: 0 auto; line-height: 1.5; }
        h1 { text-align: center; color: var(--primary); font-size: 2.8rem; margin-bottom: 10px; }
        .update-time { text-align: center; color: #70757a; margin-bottom: 40px; font-size: 0.9rem; }
        .category-header { margin: 40px 0 20px; padding: 10px 25px; background: #fff; border-radius: 12px; border-left: 8px solid var(--primary); box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 25px; }
        .card { background: #fff; border-radius: 16px; padding: 24px; display: flex; flex-direction: column; box-shadow: 0 4px 15px rgba(0,0,0,0.05); transition: all 0.3s ease; border: 1px solid #eee; }
        .card:hover { transform: translateY(-8px); box-shadow: 0 12px 24px rgba(0,0,0,0.12); }
        .source-tag { font-size: 0.75rem; background: #e8f0fe; color: var(--primary); padding: 4px 10px; border-radius: 6px; font-weight: 700; align-self: flex-start; margin-bottom: 15px; text-transform: uppercase; }
        h3 { font-size: 1.25rem; margin: 0 0 15px; line-height: 1.4; color: #1c1e21; }
        .summary { font-size: 0.95rem; color: #5f6368; flex-grow: 1; margin-bottom: 20px; display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; }
        .card-footer { display: flex; justify-content: space-between; align-items: center; padding-top: 15px; border-top: 1px solid #f1f3f4; }
        .date { font-size: 0.85rem; color: #70757a; font-weight: 500; }
        .btn { background: var(--primary); color: #fff; text-decoration: none; padding: 8px 18px; border-radius: 8px; font-size: 0.9rem; font-weight: 600; transition: background 0.2s; }
        .btn:hover { background: #1557b0; }
        @media (max-width: 600px) { .grid { grid-template-columns: 1fr; } h1 { font-size: 2rem; } }
    </style>
    """
    
    # 拼装最终网页
    full_html = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SEO & AI 专家情报站</title>
        {style}
    </head>
    <body>
        <h1>🚀 SEO & AI 专家情报站</h1>
        <p class="update-time">每 3 天自动同步专家动态 | 当前快报时间: {datetime.now().strftime('%Y-%m-%d %H:%M')} (UTC)</p>
        {"<p style='text-align:center; margin-top:100px; color:#999;'>最近 3 天大神们很低调，没有发布新内容。</p>" if not any_news_found else html_body}
        <footer style="text-align:center; margin-top:80px; color:#bdc3c7; font-size:0.8rem;">
            Powered by GitHub Actions & Python Scraper
        </footer>
    </body>
    </html>
    """
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(full_html)

if __name__ == "__main__":
    fetch_data()
