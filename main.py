import feedparser
import re
import time
from datetime import datetime, timedelta

# ==========================================
# 1. 深度情报源配置 (含 YouTube & 顶级大神)
# ==========================================
RSS_SOURCES = {
    "🔍 Google & 核心算法": {
        "Google Search Central": "https://developers.google.com/search/blog/feed.xml",
        "Search Engine Land": "https://searchengineland.com/feed",
        "SEO Roundtable": "https://www.seroundtable.com/rss.xml",
    },
    "🧠 AI & 内容策略": {
        "OpenAI News": "https://openai.com/news/rss.xml",
        "Marie Haynes (AI SEO)": "https://www.mariehaynes.com/feed/",
        "Aleyda Solis": "https://www.aleydasolis.com/en/blog/feed/",
        "HubSpot Marketing": "https://blog.hubspot.com/marketing/rss.xml",
    },
    "🛠️ 实战技巧 & 工具": {
        "Backlinko (Brian Dean)": "https://backlinko.com/feed/",
        "Ahrefs Blog": "https://ahrefs.com/blog/feed/",
        "Onely (Tech SEO)": "https://onely.com/blog/feed/",
        "Detailed": "https://detailed.com/feed/",
    },
    "📺 视频与社交动态": {
        # YouTube 官方隐藏 RSS 接口
        "YouTube: Google Search Central": "https://www.youtube.com/feeds/videos.xml?channel_id=UCWf2ZlNsCGDS89VBF_awNvA", 
        "YouTube: Ahrefs": "https://www.youtube.com/feeds/videos.xml?channel_id=UCWquNQV8Y0_defMKnGKrGWQ",
        # Twitter 很难直接抓 RSS，这里保留位置，UI上做特殊处理
        "Zarazhang (Tech & AI)": "https://rss.feed43.com/zarazhang_placeholder.xml" 
    }
}

def clean_txt(raw):
    if not raw: return "暂无详细摘要，请点击阅读原文..."
    if isinstance(raw, list): raw = raw[0].get('value', '')
    text = re.sub('<.*?>', '', str(raw)).strip()
    return text[:120] + "..." if len(text) > 120 else text

def get_category_icon(cat_name):
    if "Google" in cat_name: return "🌍"
    if "AI" in cat_name: return "🤖"
    if "视频" in cat_name: return "📺"
    return "⚡"

def fetch_data():
    now = datetime.now()
    # 定义时间窗口：7天
    time_limit = now - timedelta(days=7)
    
    all_data = []
    
    # 1. 抓取数据
    for category, sources in RSS_SOURCES.items():
        for name, url in sources.items():
            try:
                # 模拟浏览器 User-Agent 防止被拦截
                feed = feedparser.parse(url, agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
                for entry in feed.entries:
                    dt = entry.get('published_parsed') or entry.get('updated_parsed')
                    if dt:
                        p_date = datetime(*dt[:6])
                        if p_date > time_limit:
                            # 识别 YouTube
                            is_video = "youtube" in url
                            uid = re.sub(r'\W+', '', entry.link)[-20:]
                            
                            all_data.append({
                                "id": uid,
                                "category": category,
                                "source": name,
                                "title": entry.title.strip(),
                                "link": entry.link,
                                "ts": int(p_date.timestamp()),
                                "date_str": p_date.strftime('%Y-%m-%d'),
                                "summary": clean_txt(entry.get('summary') or entry.get('description', '')),
                                "is_video": is_video
                            })
            except Exception as e:
                print(f"Error fetching {name}: {e}")
                continue

    # 按时间倒序
    all_data.sort(key=lambda x: x['ts'], reverse=True)

    # 2. 生成“智能摘要”逻辑 (模仿参考图的文本段落)
    # 简单的关键词聚合算法
    insights_html = ""
    keywords = {
        "Core Update": [], "AI": [], "Content": [], "Ads": [], "Video": []
    }
    
    for item in all_data[:15]: # 只分析最新的15条生成摘要
        title = item['title']
        link_html = f"<a href='{item['link']}' target='_blank'>{item['title']}</a>"
        
        if "Core" in title or "Google" in title or "Update" in title: keywords["Core Update"].append(link_html)
        elif "AI" in title or "GPT" in title or "Gemini" in title: keywords["AI"].append(link_html)
        elif "Content" in title or "SEO" in title: keywords["Content"].append(link_html)
        else: keywords["Content"].append(link_html) # 默认归类

    for key, links in keywords.items():
        if links:
            # 模仿参考图：标题蓝色，内容是一段话
            links_str = "。 ".join(links[:3]) + "..."
            insights_html += f"""
            <div class='insight-row'>
                <div class='insight-label'>{key} Trends:</div>
                <div class='insight-content'>{links_str} <span class='read-more'>[Read Insights]</span></div>
            </div>
            """

    # 3. 生成主页面 HTML (SaaS 风格)
    style = """
    <style>
        :root { --sidebar-w: 260px; --bg: #f4f6f8; --card-bg: #ffffff; --primary: #2563eb; --text: #1e293b; --text-light: #64748b; }
        body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); display: flex; height: 100vh; overflow: hidden; }
        
        /* Sidebar */
        .sidebar { width: var(--sidebar-w); background: #fff; border-right: 1px solid #e2e8f0; padding: 24px; display: flex; flex-direction: column; flex-shrink: 0; }
        .logo { font-size: 1.25rem; font-weight: 800; color: var(--primary); margin-bottom: 32px; display: flex; align-items: center; gap: 10px; }
        .nav-group { margin-bottom: 24px; }
        .nav-title { font-size: 0.75rem; font-weight: 700; color: #94a3b8; text-transform: uppercase; margin-bottom: 12px; letter-spacing: 0.05em; }
        .nav-item { display: flex; align-items: center; gap: 10px; padding: 10px 12px; color: var(--text-light); text-decoration: none; border-radius: 8px; font-size: 0.9rem; font-weight: 500; transition: 0.2s; margin-bottom: 4px; }
        .nav-item:hover, .nav-item.active { background: #eff6ff; color: var(--primary); }
        .social-links { margin-top: auto; border-top: 1px solid #e2e8f0; padding-top: 20px; }

        /* Main Area */
        .main { flex: 1; overflow-y: auto; padding: 32px 40px; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 32px; }
        .page-title { font-size: 1.5rem; font-weight: 700; }
        .filters { display: flex; gap: 8px; background: #e2e8f0; padding: 4px; border-radius: 8px; }
        .filter-btn { border: none; background: none; padding: 6px 16px; border-radius: 6px; font-size: 0.85rem; font-weight: 600; color: var(--text-light); cursor: pointer; }
        .filter-btn.active { background: #fff; color: var(--text); box-shadow: 0 1px 2px rgba(0,0,0,0.05); }

        /* Insights Box (参考图核心) */
        .insights-box { background: #fff; border-radius: 12px; padding: 24px; border: 1px solid #e2e8f0; margin-bottom: 40px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); }
        .box-header { font-size: 1.1rem; font-weight: 700; margin-bottom: 20px; color: var(--text); display: flex; align-items: center; gap: 8px; }
        .insight-row { margin-bottom: 16px; font-size: 0.95rem; line-height: 1.6; border-bottom: 1px dashed #f1f5f9; padding-bottom: 16px; }
        .insight-row:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
        .insight-label { color: var(--primary); font-weight: 700; margin-bottom: 4px; font-size: 0.85rem; text-transform: uppercase; }
        .insight-content a { color: var(--text); text-decoration: none; font-weight: 500; border-bottom: 1px solid #cbd5e1; transition: 0.2s; }
        .insight-content a:hover { color: var(--primary); border-color: var(--primary); }
        .read-more { font-size: 0.75rem; color: #94a3b8; margin-left: 8px; cursor: pointer; }

        /* Card Grid */
        .grid-title { font-size: 1rem; font-weight: 700; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 24px; }
        .card { background: #fff; border-radius: 12px; padding: 24px; border: 1px solid #e2e8f0; display: flex; flex-direction: column; transition: 0.2s; position: relative; }
        .card:hover { transform: translateY(-2px); border-color: var(--primary); box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05); }
        .card.is-read { opacity: 0.6; filter: grayscale(1); }
        .card-meta { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .source-tag { font-size: 0.7rem; font-weight: 700; color: var(--primary); background: #eff6ff; padding: 4px 8px; border-radius: 4px; text-transform: uppercase; }
        .date { font-size: 0.75rem; color: #94a3b8; }
        .card h3 { font-size: 1.1rem; font-weight: 600; margin: 0 0 12px 0; line-height: 1.4; color: var(--text); }
        .card p { font-size: 0.9rem; color: var(--text-light); line-height: 1.6; flex: 1; margin-bottom: 20px; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
        .card-footer { border-top: 1px solid #f1f5f9; padding-top: 16px; display: flex; justify-content: space-between; align-items: center; }
        
        /* Buttons */
        .action-btn { background: none; border: 1px solid #e2e8f0; padding: 6px 12px; border-radius: 6px; font-size: 0.8rem; cursor: pointer; color: var(--text-light); transition: 0.2s; }
        .action-btn:hover { border-color: var(--text-light); color: var(--text); }
        .btn-primary { background: var(--text); color: #fff; border: none; text-decoration: none; padding: 6px 12px; border-radius: 6px; font-size: 0.8rem; font-weight: 500; }
        .btn-primary:hover { background: #0f172a; }
        
        .video-badge { position: absolute; top: -8px; right: -8px; background: #ef4444; color: white; font-size: 0.7rem; padding: 2px 8px; border-radius: 10px; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    </style>
    """

    js = """
    <script>
        // 本地存储：标记已读和收藏
        let db = JSON.parse(localStorage.getItem('seo_dashboard_v5') || '{"read":[], "fav":[]}');

        function toggleRead(id, btn) {
            if (!db.read.includes(id)) {
                db.read.push(id);
                document.getElementById(id).classList.add('is-read');
                btn.innerText = '已读';
            }
            save();
        }

        function save() { localStorage.setItem('seo_dashboard_v5', JSON.stringify(db)); }

        // 页面加载时应用状态
        window.onload = () => {
            db.read.forEach(id => {
                const card = document.getElementById(id);
                if(card) {
                    card.classList.add('is-read');
                    const btn = card.querySelector('.btn-read');
                    if(btn) btn.innerText = '已读';
                }
            });
            
            // 简单的 Tab 切换逻辑
            document.querySelectorAll('.filter-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                    e.target.classList.add('active');
                    const days = parseInt(e.target.dataset.days);
                    const now = Math.floor(Date.now() / 1000);
                    
                    document.querySelectorAll('.card').forEach(card => {
                        const ts = parseInt(card.dataset.ts);
                        if ((now - ts) > (days * 86400)) {
                            card.style.display = 'none';
                        } else {
                            card.style.display = 'flex';
                        }
                    });
                });
            });
        };
    </script>
    """

    # 生成侧边栏链接
    nav_links = ""
    for cat in RSS_SOURCES.keys():
        icon = get_category_icon(cat)
        nav_links += f"<a href='#' class='nav-item'>{icon} {cat.split(' ')[1] if ' ' in cat else cat}</a>"

    # 生成卡片 HTML
    cards_html = ""
    for item in all_data:
        video_tag = "<div class='video-badge'>▶ VIDEO</div>" if item['is_video'] else ""
        cards_html += f"""
        <div class='card' id='{item['id']}' data-ts='{item['ts']}'>
            {video_tag}
            <div class='card-meta'>
                <span class='source-tag'>{item['source']}</span>
                <span class='date'>{item['date_str']}</span>
            </div>
            <h3>{item['title']}</h3>
            <p>{item['summary']}</p>
            <div class='card-footer'>
                <button class='action-btn btn-read' onclick="toggleRead('{item['id']}', this)">Mark Read</button>
                <a href='{item['link']}' target='_blank' class='btn-primary'>Read Full →</a>
            </div>
        </div>
        """

    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset='utf-8'><title>SEO Intelligence Dashboard</title>{style}</head>
    <body>
        <div class='sidebar'>
            <div class='logo'>🚀 SEO.Intel</div>
            <div class='nav-group'>
                <div class='nav-title'>Dashboards</div>
                <a href='#' class='nav-item active'>📊 Overview</a>
                <a href='#' class='nav-item'>⭐ Favorites</a>
            </div>
            <div class='nav-group'>
                <div class='nav-title'>Feeds</div>
                {nav_links}
            </div>
            <div class='social-links'>
                <div class='nav-title'>Social Pulse</div>
                <a href='https://x.com/zarazhangrui' target='_blank' class='nav-item'>𝕏 Zara Zhang</a>
                <a href='https://www.youtube.com/channel/UCWf2ZlNsCGDS89VBF_awNvA' target='_blank' class='nav-item'>📺 Google Search Central</a>
            </div>
        </div>

        <div class='main'>
            <div class='header'>
                <div class='page-title'>Intelligence Briefing</div>
                <div class='filters'>
                    <button class='filter-btn' data-days='3'>3 Days</button>
                    <button class='filter-btn active' data-days='7'>7 Days</button>
                    <button class='filter-btn' data-days='30'>30 Days</button>
                </div>
            </div>

            <div class='insights-box'>
                <div class='box-header'>⚡ Weekly SEO Insights Summary</div>
                {insights_html or "<div class='insight-row'>暂无足够数据生成摘要...</div>"}
            </div>

            <div class='grid-title'>
                <span>Latest Updates ({len(all_data)})</span>
                <span style='font-size:0.8rem; color:#94a3b8;'>Auto-synced just now</span>
            </div>
            <div class='grid'>
                {cards_html}
            </div>
        </div>
        {js}
    </body>
    </html>
    """

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(full_html)

if __name__ == "__main__":
    fetch_data()
