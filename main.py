import feedparser
from datetime import datetime, timedelta

# 1. 扩充源：加入 AI 资讯大厂动态
RSS_SOURCES = {
    "AI News & Tech": [
        "https://openai.com/news/rss.xml",
        "https://www.artificialintelligence-news.com/feed/",
        "https://www.unite.ai/feed/"
    ],
    "SEO Authority": [
        "https://www.semrush.com/blog/feed/",
        "https://searchengineland.com/feed",
        "https://www.searchenginejournal.com/feed/",
        "https://www.seroundtable.com/rss.xml",
        "https://developers.google.com/search/blog/feed.xml"
    ],
    "SEO Experts": [
        "https://www.aleydasolis.com/en/blog/feed/",
        "https://sparktoro.com/blog/feed/",
        "https://www.lilyray.ai/blog-feed.xml"
    ]
}

def fetch_data():
    three_days_ago = datetime.now() - timedelta(days=3)
    html_body = ""
    
    for category, urls in RSS_SOURCES.items():
        category_html = f"<div class='category-header'><h2>{category}</h2></div><div class='grid'>"
        has_content = False
        
        for url in urls:
            feed = feedparser.parse(url)
            source_name = feed.feed.get('title', '权威源')
            
            for entry in feed.entries:
                dt = entry.get('published_parsed') or entry.get('updated_parsed')
                if dt and datetime(*dt[:6]) > three_days_ago:
                    has_content = True
                    # 抓取摘要：优先取 summary，没有则取 description，截取前150字
                    raw_summary = entry.get('summary', entry.get('description', '点击查看详情...'))
                    clean_summary = raw_summary[:150] + "..." if len(raw_summary) > 150 else raw_summary
                    
                    category_html += f"""
                    <div class='card'>
                        <div class='source-tag'>{source_name}</div>
                        <h3>{entry.title}</h3>
                        <p class='summary'>{clean_summary}</p>
                        <div class='card-footer'>
                            <span class='date'>{datetime(*dt[:6]).strftime('%Y-%m-%d')}</span>
                            <a href='{entry.link}' target='_blank' class='btn'>阅读全文 →</a>
                        </div>
                    </div>
                    """
        category_html += "</div>"
        if has_content: html_body += category_html

    # 精美样式表
    style = """
    <style>
        body { font-family: -apple-system, sans-serif; background: #f0f2f5; color: #1c1e21; padding: 40px 20px; max-width: 1200px; margin: 0 auto; }
        h1 { text-align: center; color: #1a73e8; font-size: 2.5rem; margin-bottom: 10px; }
        .category-header { margin: 40px 0 20px; padding: 10px 20px; background: #fff; border-radius: 8px; border-left: 6px solid #1a73e8; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 25px; }
        .card { background: #fff; border-radius: 12px; padding: 20px; display: flex; flex-direction: column; box-shadow: 0 4px 12px rgba(0,0,0,0.08); transition: 0.3s; }
        .card:hover { transform: translateY(-5px); box-shadow: 0 8px 20px rgba(0,0,0,0.15); }
        .source-tag { font-size: 0.7rem; background: #e8f0fe; color: #1967d2; padding: 3px 8px; border-radius: 4px; font-weight: bold; align-self: flex-start; margin-bottom: 12px; }
        h3 { font-size: 1.1rem; margin: 0 0 12px; line-height: 1.4; color: #000; }
        .summary { font-size: 0.9rem; color: #606770; flex-grow: 1; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; margin-bottom: 15px; }
        .card-footer { display: flex; justify-content: space-between; align-items: center; pt: 15px; border-top: 1px solid #eee; }
        .date { font-size: 0.8rem; color: #8d949e; }
        .btn { background: #1a73e8; color: #fff; text-decoration: none; padding: 6px 15px; border-radius: 6px; font-size: 0.85rem; font-weight: 500; }
    </style>
    """
    
    full_html = f"<html><head><meta charset='utf-8'><title>SEO & AI 监控</title>{style}</head><body>"
    full_html += f"<h1>🚀 SEO & AI 深度快报</h1><p style='text-align:center;'>每 3 天自动更新一次（当前 UTC: {datetime.now().strftime('%Y-%m-%d %H:%M')}）</p>"
    full_html += (html_body if html_body else "<p style='text-align:center;'>最近三天很安静，暂无新动态。</p>") + "</body></html>"
    
    with open("index.html", "w", encoding="utf-8") as f: f.write(full_html)

if __name__ == "__main__": fetch_data()
