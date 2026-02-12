import feedparser
import re
from datetime import datetime, timedelta

# ==========================================
# 1. ENHANCED SOURCE CONFIGURATION
# ==========================================
RSS_SOURCES = {
    "ELITE EXPERTS": {
        "SEO Roundtable": "https://www.seroundtable.com/rss.xml",
        "Aleyda Solis": "https://www.aleydasolis.com/en/blog/feed/",
        "Marie Haynes": "https://www.mariehaynes.com/feed/",
        "Backlinko": "https://backlinko.com/feed/",
        "Onely": "https://onely.com/blog/feed/",
        "HubSpot": "https://blog.hubspot.com/marketing/rss.xml"
    },
    "OFFICIAL BLOGS": {
        "Google Search Central": "https://developers.google.com/search/blog/feed.xml",
        "Search Engine Land": "https://searchengineland.com/feed",
        "Ahrefs": "https://ahrefs.com/blog/feed/",
        "Semrush": "https://www.semrush.com/blog/feed/"
    }
}

def clean_txt(raw):
    if not raw: return "No summary available."
    if isinstance(raw, list): raw = raw[0].get('value', '')
    return re.sub('<.*?>', '', str(raw)).strip()[:140] + "..."

def fetch_data():
    now = datetime.now()
    periods = {"Today": 1, "3D": 3, "7D": 7}
    all_data = []
    
    for cat, sources in RSS_SOURCES.items():
        for name, url in sources.items():
            try:
                feed = feedparser.parse(url, agent='Mozilla/5.0 SEO-Dash/1.0')
                for entry in feed.entries:
                    dt = entry.get('published_parsed') or entry.get('updated_parsed')
                    if dt:
                        p_date = datetime(*dt[:6])
                        if p_date > (now - timedelta(days=8)):
                            uid = re.sub(r'\W+', '', entry.link)[-20:]
                            all_data.append({
                                "id": uid, "cat": cat, "src": name,
                                "title": entry.title.strip().replace("'", ""),
                                "link": entry.link, "ts": int(p_date.timestamp()),
                                "date": p_date.strftime('%b %d'),
                                "sum": clean_txt(entry.get('summary') or entry.get('description', ''))
                            })
            except: continue

    all_data.sort(key=lambda x: x['ts'], reverse=True)

    style = """
    <style>
        :root { --sidebar-w: 240px; --primary: #1a73e8; --bg: #f8f9fa; --border: #dadce0; }
        body { font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); margin: 0; display: flex; height: 100vh; overflow: hidden; }
        
        /* SIDEBAR */
        .sidebar { width: var(--sidebar-w); background: #fff; border-right: 1px solid var(--border); padding: 20px; display: flex; flex-direction: column; }
        .logo { font-weight: bold; font-size: 1.4rem; margin-bottom: 30px; display: flex; align-items: center; gap: 10px; color: var(--primary); }
        .nav-item { padding: 10px; color: #5f6368; text-decoration: none; border-radius: 8px; margin-bottom: 5px; font-size: 0.9rem; transition: 0.2s; }
        .nav-item:hover, .nav-item.active { background: #e8f0fe; color: var(--primary); font-weight: 500; }
        .social-link { font-size: 0.8rem; margin-top: 15px; color: #9aa0a6; text-decoration: none; display: block; padding-left: 10px; }

        /* MAIN CONTENT */
        .main { flex: 1; overflow-y: auto; padding: 0 40px 40px; }
        .top-bar { position: sticky; top: 0; background: var(--bg); padding: 20px 0; z-index: 10; display: flex; justify-content: space-between; align-items: center; }
        .filter-group { display: flex; gap: 8px; background: #eee; padding: 4px; border-radius: 10px; }
        .f-btn { border: none; padding: 6px 16px; border-radius: 8px; cursor: pointer; font-size: 0.85rem; font-weight: 500; background: none; color: #5f6368; }
        .f-btn.active { background: #fff; color: var(--primary); box-shadow: 0 2px 4px rgba(0,0,0,0.1); }

        /* CONSOLIDATED SUMMARY */
        .intel-box { background: #fff; border: 1px solid var(--border); border-radius: 12px; padding: 25px; margin-bottom: 30px; }
        .intel-box h2 { font-size: 1.1rem; margin-top: 0; color: #202124; }
        .period-block { margin-bottom: 20px; font-size: 0.95rem; line-height: 1.6; }
        .period-label { font-weight: bold; color: var(--accent); display: block; margin-bottom: 8px; font-size: 0.8rem; text-transform: uppercase; }
        .period-block a { color: var(--primary); text-decoration: none; margin-right: 15px; display: inline-block; }
        .period-block a:hover { text-decoration: underline; }

        /* CARDS */
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 20px; }
        .card { background: #fff; border: 1px solid var(--border); border-radius: 12px; padding: 20px; transition: 0.2s; position: relative; }
        .card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.08); transform: translateY(-2px); }
        .card.is-read { opacity: 0.5; filter: grayscale(0.8); }
        .card-src { font-size: 0.7rem; font-weight: bold; color: var(--primary); margin-bottom: 10px; }
        .card h3 { font-size: 1rem; margin: 0 0 10px 0; line-height: 1.4; color: #202124; }
        .card-actions { display: flex; gap: 10px; margin-top: 15px; border-top: 1px solid #f1f3f4; padding-top: 15px; }
        .act-btn { cursor: pointer; border: none; background: none; color: #70757a; font-size: 0.8rem; font-weight: 500; }
        .act-btn:hover { color: var(--primary); }
    </style>
    """

    report_html = ""
    for label, days in periods.items():
        period_entries = [e for e in all_data if datetime.fromtimestamp(e['ts']) > (now - timedelta(days=days))]
        if period_entries:
            links = "".join([f"<a href='{e['link']}' target='_blank'>• {e['title']} ({e['src']})</a>" for e in period_entries[:8]])
            report_html += f"<div class='period-block'><span class='period-label'>{label} Insights</span>{links}</div>"

    cards_html = "".join([f"""
        <div class='card' id='{e['id']}' data-ts='{e['ts']}'>
            <div class='card-src'>{e['src']}</div>
            <h3>{e['title']}</h3>
            <p style='font-size:0.85rem; color:#5f6368; height: 3.6em; overflow: hidden;'>{e['sum']}</p>
            <div class='card-actions'>
                <button class='act-btn' onclick="markRead('{e['id']}')">✓ Mark Read</button>
                <button class='act-btn' onclick="toggleFav('{e['id']}')">★ Favorite</button>
                <a href='{e['link']}' target='_blank' class='act-btn' style='margin-left:auto; text-decoration:none;'>Full Story →</a>
            </div>
        </div>
    """ for e in all_data])

    js = """
    <script>
        let db = JSON.parse(localStorage.getItem('seo_v4') || '{"read":[], "fav":[]}');
        function markRead(id) { db.read.push(id); save(); }
        function toggleFav(id) { db.fav.includes(id) ? db.fav=db.fav.filter(x=>x!==id) : db.fav.push(id); save(); }
        function save() { localStorage.setItem('seo_v4', JSON.stringify(db)); location.reload(); }
        function filterT(d, b) {
            const now = Math.floor(Date.now()/1000);
            document.querySelectorAll('.card').forEach(c => {
                c.style.display = (now - c.dataset.ts) < (d*86400) ? 'block' : 'none';
            });
            document.querySelectorAll('.f-btn').forEach(btn => btn.classList.remove('active'));
            b.classList.add('active');
        }
        window.onload = () => {
            db.read.forEach(id => document.getElementById(id)?.classList.add('is-read'));
            db.fav.forEach(id => {
                const el = document.getElementById(id);
                if(el) el.style.borderColor = '#fbbc04';
            });
        }
    </script>
    """

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(f"<html><head><meta charset='utf-8'>{style}</head><body>")
        f.write(f"<div class='sidebar'><div class='logo'>🚀 SEO Intel</div>")
        f.write(f"<a href='#' class='nav-item active'>Google SEO</a><a href='#' class='nav-item'>AI News</a>")
        f.write(f"<div style='margin-top:auto;'><span class='social-link'>SOCIAL CHANNELS</span>")
        f.write(f"<a href='https://x.com/zarazhangrui' target='_blank' class='social-link'>𝕏 Zara Zhang</a>")
        f.write(f"<a href='https://www.youtube.com/channel/UCx7J37QuXsGL7QG6SMIpqKg' target='_blank' class='social-link'>📺 YouTube SEO</a></div></div>")
        f.write(f"<div class='main'><div class='top-bar'><h2>Insights Summary</h2>")
        f.write(f"<div class='filter-group'><button class='f-btn' onclick='filterT(1,this)'>3D</button><button class='f-btn active' onclick='filterT(7,this)'>7D</button></div></div>")
        f.write(f"<div class='intel-box'>{report_html}</div><div class='grid'>{cards_html}</div></div>{js}</body></html>")

if __name__ == "__main__": fetch_data()
