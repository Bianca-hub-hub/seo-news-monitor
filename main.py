import feedparser
import re
from datetime import datetime, timedelta

# ==========================================
# 1. RESOURCE CONFIGURATION
# ==========================================
RSS_SOURCES = {
    "SEO EXPERTS & INFLUENCERS": {
        "SEO Roundtable": "https://www.seroundtable.com/rss.xml",
        "Lily Ray": "https://www.lilyray.ai/blog-feed.xml",
        "Aleyda Solis": "https://www.aleydasolis.com/en/blog/feed/",
        "Marie Haynes": "https://www.mariehaynes.com/feed/",
        "Backlinko": "https://backlinko.com/feed/",
        "Search Engine Land": "https://searchengineland.com/feed",
        "Kevin Indig": "https://www.kevin-indig.com/rss/",
        "Detailed": "https://detailed.com/feed/"
    },
    "AI & SEARCH INNOVATION": {
        "Google Search Blog": "https://developers.google.com/search/blog/feed.xml",
        "OpenAI News": "https://openai.com/news/rss.xml",
        "Anthropic News": "https://www.anthropic.com/index.xml",
        "The Rundown AI": "https://www.therundown.ai/feed"
    },
    "SEO TOOLS & GIANTS": {
        "Semrush Blog": "https://www.semrush.com/blog/feed/",
        "Ahrefs Blog": "https://ahrefs.com/blog/feed/",
        "Moz Blog": "https://moz.com/posts/rss/blog",
        "Search Engine Journal": "https://www.searchenginejournal.com/feed/"
    }
}

def clean_html(raw):
    if not raw: return "No summary available."
    if isinstance(raw, list): raw = raw[0].get('value', '')
    text = re.sub('<.*?>', '', str(raw)).strip()
    return (text[:150] + "...") if len(text) > 150 else text

def fetch_data():
    limit_7d = datetime.now() - timedelta(days=7)
    limit_3d = datetime.now() - timedelta(days=3)
    all_entries = []

    for cat, sources in RSS_SOURCES.items():
        for name, url in sources.items():
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    dt = entry.get('published_parsed') or entry.get('updated_parsed')
                    if dt:
                        p_date = datetime(*dt[:6])
                        if p_date > limit_7d:
                            # Generate a unique ID based on the link
                            uid = re.sub(r'\W+', '', entry.link)[-20:]
                            all_entries.append({
                                "id": uid,
                                "category": cat,
                                "source": name,
                                "title": entry.title.replace("'", "\\'"),
                                "link": entry.link,
                                "ts": int(p_date.timestamp()),
                                "date": p_date.strftime('%m-%d'),
                                "summary": clean_html(entry.get('summary') or entry.get('description', '')).replace("'", "\\'"),
                                "is_3d": p_date > limit_3d
                            })
            except: continue
    
    all_entries.sort(key=lambda x: x['ts'], reverse=True)

    style = """
    <style>
        :root { --primary: #1a73e8; --bg: #f8f9fa; --text: #202124; --fav: #fbbc04; }
        body { font-family: -apple-system, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .nav-header { position: sticky; top: 0; background: #fff; z-index: 100; padding: 15px; border-bottom: 1px solid #ddd; display: flex; justify-content: space-between; align-items: center; border-radius: 0 0 12px 12px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
        
        .section-title { border-left: 6px solid var(--primary); padding-left: 15px; margin: 40px 0 20px; font-size: 1.4rem; }
        
        /* SUMMARY LIST */
        .summary-box { background: #fff; border: 1px solid #dadce0; border-radius: 12px; padding: 20px; margin-bottom: 20px; }
        .brief-item { display: flex; gap: 15px; padding: 8px 0; border-bottom: 1px dashed #eee; font-size: 0.9rem; }
        
        /* CARDS */
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 20px; }
        .card { background: #fff; border-radius: 12px; padding: 20px; border: 1px solid #dadce0; position: relative; transition: 0.3s; }
        .card.is-read { opacity: 0.5; order: 999; filter: grayscale(1); }
        .card.is-fav { border: 2px solid var(--fav); }
        
        .card-actions { position: absolute; top: 15px; right: 15px; display: flex; gap: 10px; }
        .action-btn { cursor: pointer; border: 1px solid #ddd; background: #fff; padding: 5px 8px; border-radius: 6px; font-size: 0.8rem; }
        .action-btn:hover { background: #f1f3f4; }
        .btn-read.active { background: #34a853; color: white; }
        .btn-fav.active { background: var(--fav); color: white; }

        .tag { font-size: 0.7rem; font-weight: bold; color: var(--primary); background: #e8f0fe; padding: 3px 8px; border-radius: 4px; margin-bottom: 10px; display: inline-block; }
        h3 { font-size: 1.1rem; margin: 10px 0; line-height: 1.4; padding-right: 60px; }
        .meta { font-size: 0.8rem; color: #70757a; margin-top: 15px; display: flex; justify-content: space-between; }
        
        #favorites-section { background: #fffef0; padding: 20px; border-radius: 12px; border: 2px dashed var(--fav); margin-bottom: 40px; display: none; }
        .hidden { display: none !important; }
    </style>
    """

    js = """
    <script>
        let storage = JSON.parse(localStorage.getItem('seo_dashboard') || '{"read":[], "fav":[]}');

        function updateUI() {
            document.querySelectorAll('.card').forEach(card => {
                const id = card.id;
                if (storage.read.includes(id)) card.classList.add('is-read');
                if (storage.fav.includes(id)) {
                    card.classList.add('is-fav');
                    card.querySelector('.btn-fav').classList.add('active');
                }
            });
            renderFavs();
        }

        function toggleRead(id) {
            if (storage.read.includes(id)) storage.read = storage.read.filter(i => i !== id);
            else storage.read.push(id);
            save();
        }

        function toggleFav(id) {
            if (storage.fav.includes(id)) storage.fav = storage.fav.filter(i => i !== id);
            else storage.fav.push(id);
            save();
        }

        function save() {
            localStorage.setItem('seo_dashboard', JSON.stringify(storage));
            location.reload();
        }

        function renderFavs() {
            const favBox = document.getElementById('favorites-section');
            if (storage.fav.length > 0) {
                favBox.style.display = 'block';
                const grid = favBox.querySelector('.grid');
                grid.innerHTML = '';
                storage.fav.forEach(id => {
                    const original = document.getElementById(id);
                    if (original) {
                        const clone = original.cloneNode(true);
                        clone.classList.remove('is-read');
                        grid.appendChild(clone);
                    }
                });
            }
        }

        window.onload = updateUI;
    </script>
    """

    content_html = ""
    # Grouping by category
    cats = list(dict.fromkeys([e['category'] for e in all_entries]))
    
    for cat in cats:
        cat_entries = [e for e in all_entries if e['category'] == cat]
        
        briefs = "".join([f"<div class='brief-item'><span>{e['date']}</span><b>[{e['source']}]</b><a href='{e['link']}' target='_blank'>{e['title']}</a></div>" for e in cat_entries[:10]])
        
        cards = "".join([f"""
            <div class='card' id='{e['id']}' data-ts='{e['ts']}'>
                <div class='card-actions'>
                    <button class='action-btn btn-fav' onclick="toggleFav('{e['id']}')">★</button>
                    <button class='action-btn btn-read' onclick="toggleRead('{e['id']}')">READ</button>
                </div>
                <div class='tag'>{e['source']}</div>
                <h3>{e['title']}</h3>
                <p style='font-size:0.9rem; color:#555;'>{e['summary']}</p>
                <div class='meta'>
                    <span>{e['date']}</span>
                    <a href='{e['link']}' target='_blank' style='color:var(--primary); text-decoration:none; font-weight:bold;'>Full Text →</a>
                </div>
            </div>
        """ for e in cat_entries])

        content_html += f"<h2 class='section-title'>{cat}</h2><div class='summary-box'><h4>Quick Summary</h4>{briefs}</div><div class='grid'>{cards}</div>"

    full_page = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head><meta charset="utf-8"><title>SEO Intelligence</title>{style}</head>
    <body>
        <div class="container">
            <div class="nav-header">
                <h1>SEO INTELLIGENCE</h1>
                <div><button onclick="localStorage.clear(); location.reload();" class="action-btn">Reset All</button></div>
            </div>
            
            <div id="favorites-section">
                <h2 class="section-title" style="border-color:var(--fav)">★ FAVORITES</h2>
                <div class="grid"></div>
            </div>

            {content_html}
        </div>
        {js}
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f: f.write(full_page)

if __name__ == "__main__": fetch_data()
