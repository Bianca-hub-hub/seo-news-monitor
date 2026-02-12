import feedparser
import re
from datetime import datetime, timedelta

# ==========================================
# 1. CORE EXPERT SOURCES (Prioritized)
# ==========================================
RSS_SOURCES = {
    "ELITE EXPERTS": {
        "Barry Schwartz (SER)": "https://www.seroundtable.com/rss.xml",
        "Lily Ray": "https://www.lilyray.ai/blog-feed.xml",
        "Aleyda Solis": "https://www.aleydasolis.com/en/blog/feed/",
        "Marie Haynes": "https://www.mariehaynes.com/feed/",
        "Brian Dean (Backlinko)": "https://backlinko.com/feed/",
        "Glenn Allsopp (Detailed)": "https://detailed.com/feed/",
        "Kevin Indig": "https://www.kevin-indig.com/rss/",
        "Onely (Technical SEO)": "https://onely.com/blog/feed/"
    },
    "SEARCH & AI GIANTS": {
        "Google Search Central": "https://developers.google.com/search/blog/feed.xml",
        "Search Engine Land": "https://searchengineland.com/feed",
        "Search Engine Journal": "https://www.searchenginejournal.com/feed/",
        "Ahrefs": "https://ahrefs.com/blog/feed/",
        "Semrush": "https://www.semrush.com/blog/feed/",
        "OpenAI": "https://openai.com/news/rss.xml",
        "The Rundown AI": "https://www.therundown.ai/feed"
    }
}

def clean_txt(raw):
    if not raw: return ""
    if isinstance(raw, list): raw = raw[0].get('value', '')
    return re.sub('<.*?>', '', str(raw)).strip()[:140] + "..."

def fetch_data():
    now = datetime.now()
    periods = {
        "Today": now - timedelta(days=1),
        "Last 3 Days": now - timedelta(days=3),
        "Last 7 Days": now - timedelta(days=7)
    }
    
    all_data = []
    
    for cat, sources in RSS_SOURCES.items():
        for name, url in sources.items():
            try:
                # Use a specific user agent to prevent being blocked by Expert Blogs
                feed = feedparser.parse(url, agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) SEO-Dashboard/1.0')
                for entry in feed.entries:
                    dt = entry.get('published_parsed') or entry.get('updated_parsed')
                    if dt:
                        p_date = datetime(*dt[:6])
                        if p_date > (now - timedelta(days=8)):
                            uid = re.sub(r'\W+', '', entry.link)[-20:]
                            all_data.append({
                                "id": uid,
                                "cat": cat,
                                "src": name,
                                "title": entry.title.strip(),
                                "link": entry.link,
                                "ts": int(p_date.timestamp()),
                                "date": p_date.strftime('%b %d'),
                                "sum": clean_txt(entry.get('summary') or entry.get('description', ''))
                            })
            except: continue

    all_data.sort(key=lambda x: x['ts'], reverse=True)

    # UI GENERATION
    style = """
    <style>
        :root { --primary: #1a73e8; --bg: #f8f9fa; --accent: #d93025; }
        body { font-family: -apple-system, sans-serif; background: var(--bg); margin: 0; padding: 20px; line-height: 1.5; color: #202124; }
        .container { max-width: 1200px; margin: 0 auto; }
        .intel-report { background: #fff; border: 2px solid #dadce0; border-radius: 12px; padding: 30px; margin-bottom: 40px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
        .intel-group { margin-bottom: 25px; padding-bottom: 20px; border-bottom: 1px solid #eee; }
        .intel-group:last-child { border: none; }
        .intel-group h3 { color: var(--accent); margin-top: 0; font-size: 1.1rem; text-transform: uppercase; }
        .consolidated-text { font-size: 1rem; color: #3c4043; }
        .consolidated-text a { color: var(--primary); text-decoration: none; font-weight: 500; }
        .consolidated-text a:hover { text-decoration: underline; background: #e8f0fe; }
        .src-tag { font-size: 0.75rem; background: #f1f3f4; padding: 2px 6px; border-radius: 4px; margin-right: 4px; font-weight: bold; color: #5f6368; }
        
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 25px; }
        .card { background: #fff; border-radius: 12px; border: 1px solid #dadce0; padding: 24px; position: relative; transition: 0.2s; }
        .card:hover { border-color: var(--primary); box-shadow: 0 8px 16px rgba(0,0,0,0.1); }
        .card.is-read { opacity: 0.4; order: 999; }
        .actions { position: absolute; top: 15px; right: 15px; }
        .btn { border: 1px solid #dadce0; background: #fff; cursor: pointer; padding: 5px 10px; border-radius: 6px; font-size: 0.75rem; }
        .btn-fav.active { background: #fbbc04; border-color: #fbbc04; color: #fff; }
    </style>
    """

    # Build Consolidated Summaries
    report_html = ""
    for label, delta_time in periods.items():
        period_entries = [e for e in all_data if datetime.fromtimestamp(e['ts']) > delta_time]
        if period_entries:
            links = " • ".join([f"<span class='src-tag'>{e['src']}</span> <a href='{e['link']}' target='_blank'>{e['title']}</a>" for e in period_entries])
            report_html += f"<div class='intel-group'><h3>{label} Update</h3><div class='consolidated-text'>{links}</div></div>"

    # Build Cards
    cards_html = "".join([f"""
        <div class='card' id='{e['id']}' data-ts='{e['ts']}'>
            <div class='actions'>
                <button class='btn btn-fav' onclick="toggleFav('{e['id']}')">★</button>
                <button class='btn' onclick="toggleRead('{e['id']}')">Mark Read</button>
            </div>
            <div style='color:var(--primary); font-size:0.7rem; font-weight:bold; margin-bottom:10px;'>{e['src']}</div>
            <h3 style='margin:0 0 10px 0; font-size:1.1rem; line-height:1.4;'>{e['title']}</h3>
            <p style='font-size:0.9rem; color:#5f6368;'>{e['sum']}</p>
            <div style='font-size:0.8rem; color:#9aa0a6; border-top:1px solid #f1f3f4; padding-top:10px;'>{e['date']}</div>
        </div>
    """ for e in all_data])

    js = """
    <script>
        let db = JSON.parse(localStorage.getItem('seo_v3') || '{"read":[], "fav":[]}');
        function toggleRead(id) {
            db.read.includes(id) ? db.read = db.read.filter(x=>x!==id) : db.read.push(id);
            save();
        }
        function toggleFav(id) {
            db.fav.includes(id) ? db.fav = db.fav.filter(x=>x!==id) : db.fav.push(id);
            save();
        }
        function save() { localStorage.setItem('seo_v3', JSON.stringify(db)); location.reload(); }
        window.onload = () => {
            db.read.forEach(id => document.getElementById(id)?.classList.add('is-read'));
            db.fav.forEach(id => document.getElementById(id)?.querySelector('.btn-fav').classList.add('active'));
        }
    </script>
    """

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(f"<html><head><meta charset='utf-8'><title>SEO Intel</title>{style}</head><body>")
        f.write(f"<div class='container'><h1>SEO CONSOLIDATED INTELLIGENCE</h1>")
        f.write(f"<div class='intel-report'>{report_html or 'No updates found in the selected period.'}</div>")
        f.write(f"<div class='grid'>{cards_html}</div></div>{js}</body></html>")

if __name__ == "__main__": fetch_data()
