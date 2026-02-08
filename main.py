import feedparser
import time
from datetime import datetime, timedelta

# 你指定的权威 SEO 资源列表
RSS_SOURCES = {
    "Google Search Blog": "https://developers.google.com/search/blog/feed.xml",
    "Semrush Blog": "https://www.semrush.com/blog/feed/",
    "Search Engine Land": "https://searchengineland.com/feed",
    "Search Engine Journal": "https://www.searchenginejournal.com/feed/",
    "SEO Roundtable": "https://www.seroundtable.com/rss.xml",
    "Ahrefs Blog": "https://ahrefs.com/blog/feed/",
    "Moz Blog": "https://moz.com/posts/rss/blog",
    "Aleyda Solis (SMM)": "https://www.aleydasolis.com/en/blog/feed/"
}

def fetch_and_generate():
    three_days_ago = datetime.now() - timedelta(days=3)
    content = f"""
    <html><head><meta charset='utf-8'><title>SEO News Monitor</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; line-height: 1.6; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #333; }}
        h1 {{ border-bottom: 2px solid #1a73e8; padding-bottom: 10px; color: #1a73e8; }}
        .source-group {{ margin-top: 30px; }}
        .item {{ margin-bottom: 15px; padding: 10px; border-left: 4px solid #eee; }}
        .item:hover {{ border-left-color: #1a73e8; background: #f9f9f9; }}
        a {{ text-decoration: none; color: #1a73e8; font-weight: bold; }}
        .date {{ font-size: 0.85em; color: #666; }}
    </style></head><body>
    <h1>SEO 行业动态推送 (过去3天)</h1>
    <p>更新时间 (UTC): {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
    """

    any_news = False
    for name, url in RSS_SOURCES.items():
        feed = feedparser.parse(url)
        source_html = f"<div class='source-group'><h2>{name}</h2>"
        found_in_source = False
        
        for entry in feed.entries:
            # 尝试解析发布时间
            dt = entry.get('published_parsed') or entry.get('updated_parsed')
            if dt:
                pub_date = datetime(*dt[:6])
                if pub_date > three_days_ago:
                    found_in_source = any_news = True
                    source_html += f"""
                    <div class='item'>
                        <a href='{entry.link}' target='_blank'>{entry.title}</a><br>
                        <span class='date'>发布日期: {pub_date.strftime('%Y-%m-%d')}</span>
                    </div>
                    """
        source_html += "</div>"
        if found_in_source:
            content += source_html

    if not any_news:
        content += "<p>最近 3 天没有发现新的算法更新或文章。</p>"
    
    content += "</body></html>"
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    fetch_and_generate()
