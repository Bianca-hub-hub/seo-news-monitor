# seo-news-monitor

一个给自己看的 SEO / GEO / AI Search 情报站。项目会定期抓取 RSS 信源，生成静态 `index.html`，适合部署到 GitHub Pages。

## 本地运行

```bash
pip install -r requirements.txt
python main.py
python -m http.server 4173
```

打开 `http://127.0.0.1:4173/` 预览。

## 自动更新

仓库已配置 GitHub Actions：

- 每天 UTC 00:00 自动运行一次，对应北京时间 08:00。
- 也可以在 GitHub 的 `Actions -> Update SEO/GEO News -> Run workflow` 手动运行。
- 脚本会重新生成 `index.html` 并自动提交到 `main` 分支。

## 可选 AI 摘要

如果不配置 OpenAI，项目会使用本地规则生成中文摘要，不会影响抓取。

如果想启用 AI 摘要，在 GitHub 仓库的 `Settings -> Secrets and variables -> Actions` 添加：

- `OPENAI_API_KEY`
- `OPENAI_MODEL`，可选，默认 `gpt-4o-mini`
- `OPENAI_BASE_URL`，可选

AI 摘要失败时会自动降级成本地摘要，不会再丢掉文章。

## 添加信源

在 `main.py` 的 `RSS_SOURCES` 中添加 RSS 地址：

```python
"SEO 动态": {
    "Example Blog": "https://example.com/feed.xml",
}
```

如果是 X / Twitter、微信公众号、Perplexity 这类没有稳定公开 RSS 的来源，建议先放到 `EXPERT_PROFILES` 做入口，后续再接入自建 RSSHub 或专门 API。
