import feedparser
import re
from datetime import datetime, timedelta

# ==========================================
# 1. 混合源配置 (博客 + YouTube + X/Twitter)
# ==========================================
RSS_SOURCES = {
    # --- 核心博客 ---
    "Google & SEO": [
        ("Google Search Central", "https://developers.google.com/search/blog/feed.xml"),
        ("SEO Roundtable", "https://www.seroundtable.com/rss.xml"),
        ("Search Engine Land", "https://searchengineland.com/feed"),
    ],
    "AI & Tech": [
        ("OpenAI News", "https://openai.com/news/rss.xml"),
        ("Marie Haynes", "https://www.mariehaynes.com/feed/"),
        ("Aleyda Solis", "https://www.aleydasolis.com/en/blog/feed/"),
    ],
    # --- 视频源 (YouTube 官方 RSS) ---
    "YouTube Channel": [
        ("Google Search Central", "https://www.youtube.com/feeds/videos.xml?channel_id=UCWf2ZlNsCGDS89VBF_awNvA"),
        ("Ahrefs TV", "https://www.youtube.com/feeds/videos.xml?channel_id=UCWquNQV8Y0_defMKnGKrGWQ"),
        ("Matt Diggity", "https://www.youtube.com/feeds/videos.xml?channel_id=UCO3S7_yYn0rZ4Tz6e-yqA2A"), # 增加大神
    ],
    # --- 社交媒体 (使用 Nitter 镜像抓取 X) ---
    "Social (X/Twitter)": [
        # 注意：如果 nitter.poast.org 失效，可更换为 nitter.net 或 rss.app 生成的源
        ("Zara Zhang (X)", "https://nitter.poast.org/zarazhangrui/rss"),
        ("Google Search Liason (X)", "https://nitter.poast.org/searchliaison/rss"),
    ]
}

def clean_txt(raw):
    if not raw: return "点击查看详情..."
    if isinstance(raw, list): raw = raw[0].get('value', '')
    text = re.sub('<.*?>', '', str(raw)).strip()
    return text[:100] + "..." if len(text) > 100 else text

# 专门提取 YouTube 封面图
def get_youtube_thumb(entry):
    # 尝试从 media_thumbnail 提取，如果失败则用视频ID拼接
    if 'media_thumbnail' in entry and len(entry.media_thumbnail) > 0:
        return entry.media_thumbnail[0]['url']
    if 'yt_videoid' in entry:
        return f"https://i.ytimg.com/vi/{entry.yt_videoid}/mqdefault.jpg"
    return ""

def fetch_data():
    now = datetime.now()
    time_limit = now - timedelta(days=14) 
    all_data = []
    
    for category, sources in RSS_SOURCES.items():
        for name, url in sources:
            try:
                # 针对不同源做一些伪装
                feed = feedparser.parse(url, agent='Mozilla/5.0 (compatible; SEO-Dashboard/1.0)')
                
                for entry in feed.entries:
                    dt = entry.get('published_parsed') or entry.get('updated_parsed')
                    if dt:
                        p_date = datetime(*dt[:6])
                        if p_date > time_limit:
                            # 核心字段提取
                            uid = re.sub(r'\W+', '', entry.link)[-20:]
                            title = entry.title.strip()
                            link = entry.link
                            summary = clean_txt(entry.get('summary') or entry.get('description', ''))
                            
                            # 类型判断
                            card_type = "blog"
                            image_url = ""
                            
                            if "youtube.com" in url:
                                card_type = "video"
                                image_url = get_youtube_thumb(entry)
                                # YouTube 摘要通常在 media_group 描述里
                                if 'media_group' in entry:
                                    summary = clean_txt(entry.media_group[0]['media_description']['content'])
                            
                            elif "nitter" in url or "twitter" in url:
                                card_type = "tweet"
                                title = f"@{name.split()[0]}: {title[:50]}..." # 推文标题处理
                                summary = clean_txt(entry.get('description', ''))

                            all_data.append({
                                "id": uid,
                                "cat": category,
                                "src": name,
                                "type": card_type, # blog, video, tweet
                                "title": title,
                                "link": link,
                                "img": image_url,
                                "ts": int(p_date.timestamp()),
                                "date": p_date.strftime('%m-%d'),
                                "sum": summary
                            })
            except Exception as e:
                print(f"Error fetching {name}: {e}")
                continue

    all_data.sort(key=lambda x: x['ts'], reverse=True)

    # 生成 HTML (保留了你喜欢的 CSS order 沉底功能)
    style = """
    <style>
        :root { --bg: #f3f4f6; --card-bg: #fff; --primary: #2563eb; --text: #1f2937; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; display: flex; gap: 30px; }
        
        /* 左侧边栏 */
        .sidebar { width: 220px; flex-shrink: 0; position: sticky; top: 20px; height: fit-content; }
        .logo { font-size: 1.5rem; font-weight: 800; margin-bottom: 30px; color: var(--primary); display: flex; align-items: center; gap: 10px; }
        .nav-item { padding: 10px; margin-bottom: 5px; cursor: pointer; border-radius: 8px; font-weight: 500; color: #4b5563; }
        .nav-item.active, .nav-item:hover { background: #dbeafe; color: var(--primary); }
        .nav-header { font-size: 0.75rem; text-transform: uppercase; color: #9ca3af; margin: 20px 0 10px; font-weight: 700; }

        /* 主区域 */
        .main-content { flex: 1; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }

        /* 卡片通用样式 */
        .card { background: var(--card-bg); border-radius: 12px; overflow: hidden; border: 1px solid #e5e7eb; transition: 0.2s; display: flex; flex-direction: column; position: relative; }
        .card:hover { transform: translateY(-3px); box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); border-color: var(--primary); }
        
        /* 交互状态样式 */
        .card.is-read { opacity: 0.6; filter: grayscale(1); order: 9999; background: #f9fafb; }
        .card.is-fav { border: 2px solid #fbbf24; order: -9999; } /* 收藏置顶 */
        .fav-btn { position: absolute; top: 10px; right: 10px; z-index: 10; font-size: 1.2rem; cursor: pointer; background: rgba(255,255,255,0.8); border-radius: 50%; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; border: none; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .fav-btn.active { color: #d97706; background: #fffbeb; }

        /* 内容布局 */
        .card-body { padding: 16px; display: flex; flex-direction: column; flex: 1; }
        .meta { font-size: 0.75rem; color: #6b7280; margin-bottom: 8px; display: flex; align-items: center; gap: 6px; }
        .src-badge { padding: 2px 6px; border-radius: 4px; background: #eff6ff; color: var(--primary); font-weight: 600; }
        h3 { font-size: 1rem; margin: 0 0 8px 0; line-height: 1.4; color: #111827; }
        h3 a { text-decoration: none; color: inherit; }
        h3 a:hover { color: var(--primary); }
        p { font-size: 0.85rem; color: #4b5563; line-height: 1.5; margin: 0; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }

        /* YouTube 特有样式 */
        .video-thumb { width: 100%; height: 160px; object-fit: cover; background: #000; }
        .play-icon { position: absolute; top: 70px; left: 50%; transform: translate(-50%, -50%); color: white; font-size: 2rem; opacity: 0.9; text-shadow: 0 2px 4px rgba(0,0,0,0.5); pointer-events: none; }
        
        /* Twitter 特有样式 */
        .tweet-card { border-left: 4px solid #1da1f2; }
        .tweet-icon { color: #1da1f2; font-size: 0.8rem; }

        .hidden { display: none !important; }
    </style>
    """

    js = """
    <script>
        let db = JSON.parse(localStorage.getItem('seo_v7') || '{"read":[], "fav":[]}');

        function toggleRead(id) {
            if(!db.read.includes(id)) {
                db.read.push(id);
                document.getElementById(id).classList.add('is-read');
                save();
            }
        }
        
        function toggleFav(id, btn) {
            event.stopPropagation(); // 防止触发阅读
            if(db.fav.includes(id)) {
                db.fav = db.fav.filter(x => x !== id);
                btn.classList.remove('active');
                btn.innerHTML = '☆';
            } else {
                db.fav.push(id);
                btn.classList.add('active');
                btn.innerHTML = '★';
            }
            // 更新样式
            const card = document.getElementById(id);
            db.fav.includes(id) ? card.classList.add('is-fav') : card.classList.remove('is-fav');
            save();
        }

        function save() { localStorage.setItem('seo_v7', JSON.stringify(db)); }
        
        function filter(type) {
            document.querySelectorAll('.card').forEach(c => {
                c.classList.remove('hidden');
                if(type === 'fav' && !c.classList.contains('is-fav')) c.classList.add('hidden');
                if(type === 'video' && !c.classList.contains('type-video')) c.classList.add('hidden');
            });
            // 菜单高亮逻辑略
        }

        window.onload = () => {
            db.read.forEach(id => document.getElementById(id)?.classList.add('is-read'));
            db.fav.forEach(id => {
                const c = document.getElementById(id);
                if(c) {
                    c.classList.add('is-fav');
                    c.querySelector('.fav-btn').classList.add('active');
                    c.querySelector('.fav-btn').innerHTML = '★';
                }
            });
        }
    </script>
    """

    # 生成卡片 HTML
    cards_html = ""
    for item in all_data:
        # 1. 视频卡片结构
        if item['type'] == 'video':
            media_html = f"""
                <div style="position:relative;">
                    <img src="{item['img']}" class="video-thumb" loading="lazy">
                    <div class="play-icon">▶</div>
                </div>
            """
            extra_class = "type-video"
            icon = "📺"
        # 2. 推文卡片结构
        elif item['type'] == 'tweet':
            media_html = ""
            extra_class = "tweet-card"
            icon = "𝕏"
        # 3. 博客卡片结构
        else:
            media_html = ""
            extra_class = ""
            icon = "📄"

        cards_html += f"""
        <div class='card {extra_class}' id='{item['id']}'>
            <button class='fav-btn' onclick="toggleFav('{item['id']}', this)">☆</button>
            <a href='{item['link']}' target='_blank' onclick="toggleRead('{item['id']}')" style="text-decoration:none; color:inherit;">
                {media_html}
                <div class='card-body'>
                    <div class='meta'>
                        <span class='src-badge'>{icon} {item['src']}</span>
                        <span>{item['date']}</span>
                    </div>
                    <h3>{item['title']}</h3>
                    <p>{item['sum']}</p>
                </div>
            </a>
        </div>
        """

    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset='utf-8'><title>SEO Integrated Dashboard</title>{style}</head>
    <body>
        <div class="container">
            <div class="sidebar">
                <div class="logo">🚀 SEO.Intel</div>
                
                <div class="nav-header">Dashboard</div>
                <div class="nav-item active" onclick="filter('all')">📊 全部动态</div>
                <div class="nav-item" onclick="filter('fav')">⭐️ 我的收藏</div>
                
                <div class="nav-header">Filter by Type</div>
                <div class="nav-item" onclick="filter('video')">📺 仅看视频</div>
                
                <div class="nav-header">Quick Links</div>
                <div class="nav-item" style="cursor:default; color:#999;">Updating: {now.strftime('%H:%M')}</div>
            </div>
            
            <div class="main-content">
                <div class="grid">
                    {cards_html}
                </div>
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
