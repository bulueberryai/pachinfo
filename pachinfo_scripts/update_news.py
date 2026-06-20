"""
PACHINFO ニュース自動更新スクリプト
実行するたびに pachinko_news.html のニュースを最新に更新する
"""

import os
import re
import feedparser
import html
import requests
from bs4 import BeautifulSoup
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ---- YouTube チャンネル設定 -----------------------------------------------
ONE_MONTH_AGO = None  # main() で設定

def yt_rss(channel_id=None, user=None):
    if channel_id:
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    return f"https://www.youtube.com/feeds/videos.xml?user={user}"

YT_CHANNELS = [
    # ---- 実践系 ----
    {"name": "スロパチステーション",      "rss": yt_rss(channel_id="UC8yYqoMOYO_Q755YLJ-teoQ")},
    {"name": "寺井一択の爆裂最強限界突破TV","rss": yt_rss(channel_id="UCBhbCz5nY1Kctwe7diP6DPw")},
    # ---- メーカー公式 ----
    {"name": "京楽",       "rss": yt_rss(user="KYORAKUSANGYO")},
    {"name": "SANYO",      "rss": yt_rss(user="sanyoofficial")},
    {"name": "サミー",     "rss": yt_rss(user="SammyCorporation")},
    {"name": "SANKYO",     "rss": yt_rss(user="SANKYOFEVERTV")},
    {"name": "ニューギン", "rss": yt_rss(user="newginchannel")},
    {"name": "藤商事",     "rss": yt_rss(channel_id="UC5Gczn2J9pdfhj7hORCk0XA")},
    {"name": "平和",       "rss": yt_rss(channel_id="UCv5XfaorU_67je3AfovCEAQ")},
    {"name": "山佐",       "rss": yt_rss(channel_id="UCb-4ov2KFGo-Dgk0O86zeYA")},
    {"name": "フィールズ", "rss": yt_rss(channel_id="UCuTsB6V7NdKVIKjjNnzMN7Q")},
    {"name": "高尾",       "rss": yt_rss(channel_id="UCS1lRIO_OSL5n_7AOSuSlrw")},
    {"name": "大都技研",   "rss": yt_rss(user="DaitogikenTV")},
    {"name": "ベルコ",     "rss": yt_rss(channel_id="UC_VA5_0rcObV4t6cthUxVWg")},
    {"name": "マルホン",   "rss": yt_rss(channel_id="UCWP721-hcdv9SrdE_jJfPJg")},
]


def fetch_youtube_videos():
    """各チャンネルから直近1か月以内の最新動画を1本ずつ取得"""
    cutoff = datetime.now(JST) - timedelta(days=30)
    videos = []
    for ch in YT_CHANNELS:
        try:
            feed = feedparser.parse(ch["rss"])
            for entry in feed.entries[:5]:
                pub = entry.get("published_parsed") or entry.get("updated_parsed")
                if not pub:
                    continue
                dt = datetime(*pub[:6], tzinfo=timezone.utc).astimezone(JST)
                if dt < cutoff:
                    continue
                link = entry.get("link", "")
                m = re.search(r"v=([A-Za-z0-9_-]{11})", link)
                if not m:
                    continue
                video_id = m.group(1)
                videos.append({
                    "title": html.escape(entry.get("title", "")),
                    "channel": ch["name"],
                    "link": link,
                    "thumb": f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
                    "dt": dt,
                })
                break  # チャンネルごとに最新1本のみ
        except Exception as e:
            print(f"[WARN] YouTube {ch['name']} 取得失敗: {e}")
    videos.sort(key=lambda x: x["dt"], reverse=True)
    return videos


def build_sidebar_html(videos, updated):
    cards = ""
    for v in videos:
        date_str = v["dt"].strftime("%m.%d")
        cards += f"""
        <a href="{v['link']}" class="yt-card">
          <img src="{v['thumb']}" class="yt-thumb" loading="lazy" alt="">
          <div class="yt-info">
            <div class="yt-channel">{html.escape(v['channel'])}</div>
            <div class="yt-title">{v['title']}</div>
            <div class="yt-date">{date_str}</div>
          </div>
        </a>"""

    if not cards:
        cards = '<div style="font-size:11px; color:#2a4a6a; padding:8px 0;">直近1か月の動画なし</div>'

    return f"""<!-- SIDEBAR_START -->
      <div class="section-title">YOUTUBE</div>
      <div style="font-size:10px; color:#2a4a6a; margin-bottom:12px; font-family:'Orbitron',sans-serif;">UPDATED: {updated}</div>
      <div class="yt-list">
        {cards}
      </div>
<!-- SIDEBAR_END -->"""

if os.name == 'nt':
    HTML_FILE = Path(__file__).parent.parent / "claude" / "index.html"
else:
    HTML_FILE = Path(__file__).parent.parent / "index.html"

JST = timezone(timedelta(hours=9))

# ---- 収集対象RSSフィード ------------------------------------------------
# tag: "auto" はタイトルキーワードで自動判定、それ以外は固定
FEEDS = [
    {"url": "https://yugi-nippon.com/feed/",           "source": "遊技日本",               "tag": "auto"},
    {"url": "https://web-greenbelt.jp/feed/",          "source": "グリーンべると",          "tag": "auto"},
    {"url": "https://jenepi.jp/feed/",                 "source": "ジェネピ",               "tag": "store"},
    {"url": "https://chonborista.com/feed/",           "source": "ちょんぼりすた",          "tag": "auto"},
    {"url": "https://www.yugitsushin.jp/feed/",        "source": "遊技通信",               "tag": "auto"},
    {"url": "https://pachinko-curation.com/feed",      "source": "パチンコキュレーション",  "tag": "auto"},
    {"url": "https://rssblog.ameba.jp/2ndsales/rss20.xml", "source": "2ndsales",           "tag": "hot"},
    {"url": "https://p-johojima.jp/feed",                  "source": "パチンコ情報島",        "tag": "auto"},
]

# ---- キーワードによる自動タグ判定 ----------------------------------------
KEYWORD_RULES = [
    ("reg",   ["規制", "法令", "警察庁"]),
    ("new",   ["新台", "導入", "検定"]),
    ("mfg",   ["メーカー", "発表", "開発",
                "サミー", "三共", "ニューギン", "三洋", "山佐",
                "フィールズ", "藤商事", "京楽", "コナミ", "ユニバーサル"]),
]

def classify_tag(title: str, default_tag: str) -> str:
    if default_tag != "auto":
        return default_tag
    for tag, keywords in KEYWORD_RULES:
        if any(kw in title for kw in keywords):
            return tag
    return "hot"

TAG_LABELS = {
    "hot":   ("注目",   "tag-hot"),
    "new":   ("新台",   "tag-new"),
    "reg":   ("規制",   "tag-reg"),
    "mfg":   ("メーカー", "tag-mfg"),
    "store": ("店舗",   "tag-store"),
}

SOURCE_COLORS = {
    "hot":   "#f0a",
    "new":   "#0af",
    "reg":   "#fa0",
    "mfg":   "#a0f",
    "store": "#0cf",
}


def fetch_entries(max_per_feed=10):
    cutoff = datetime.now(JST) - timedelta(weeks=3)
    entries = []
    for feed_cfg in FEEDS:
        try:
            feed = feedparser.parse(feed_cfg["url"])
            for entry in feed.entries[:max_per_feed]:
                pub = entry.get("published_parsed") or entry.get("updated_parsed")
                if pub:
                    dt = datetime(*pub[:6], tzinfo=timezone.utc).astimezone(JST)
                else:
                    dt = datetime.now(JST)
                if dt < cutoff:
                    continue
                raw_title = entry.get("title", "（タイトルなし）")
                tag = classify_tag(raw_title, feed_cfg["tag"])
                entries.append({
                    "title": html.escape(raw_title),
                    "link": entry.get("link", "#"),
                    "source": feed_cfg["source"],
                    "tag": tag,
                    "dt": dt,
                })
        except Exception as e:
            print(f"[WARN] {feed_cfg['source']} の取得に失敗: {e}")
    entries.sort(key=lambda x: x["dt"], reverse=True)
    return entries


def make_tag_html(tag_key):
    label, css = TAG_LABELS.get(tag_key, ("INFO", "tag-hot"))
    return f'<span class="news-tag {css}">{label}</span>'


def make_source_html(source, tag_key):
    color = SOURCE_COLORS.get(tag_key, "#0af")
    return f'<div class="news-source" style="color:{color};">{html.escape(source)}</div>'


def make_featured_html(entry):
    color = SOURCE_COLORS.get(entry["tag"], "#0af")
    date_str = entry["dt"].strftime("%Y.%m.%d %H:%M")
    return f"""
    <a href="{entry['link']}" class="news-featured" data-tag="{entry['tag']}" style="border-left-color:{color};">
      {make_tag_html(entry['tag'])}
      {make_source_html(entry['source'], entry['tag'])}
      <div class="news-title">{entry['title']}</div>
      <div class="news-meta"><span>{date_str}</span></div>
    </a>"""


def make_card_html(entry):
    color = SOURCE_COLORS.get(entry["tag"], "#0af")
    return f"""
        <a href="{entry['link']}" class="news-card" data-tag="{entry['tag']}">
          <div style="display:flex; align-items:center; gap:8px; margin-bottom:6px;">
            {make_tag_html(entry['tag'])}
            <div class="news-source" style="color:{color}; margin-bottom:0;">{html.escape(entry['source'])}</div>
            <div style="margin-left:auto; font-size:10px; color:#4a6a8a; white-space:nowrap;">{entry['dt'].strftime('%m.%d %H:%M')}</div>
          </div>
          <div class="news-title">{entry['title']}</div>
        </a>"""


def build_news_html(entries):
    updated = datetime.now(JST).strftime("%Y.%m.%d %H:%M")
    cards_html = "\n".join(make_card_html(e) for e in entries)

    return f"""<!-- NEWS_START -->
      <div class="section-title">LATEST NEWS</div>
      <div style="font-size:10px; color:#2a4a6a; margin-bottom:12px; font-family:'Orbitron',sans-serif;">UPDATED: {updated}</div>
      <div class="news-list">
        {cards_html}
      </div>
<!-- NEWS_END -->"""


# ---- キーワード除外リスト ------------------------------------------------
STOP_WORDS = {
    "パチンコ", "パチスロ", "スロット", "まとめ", "情報", "解析", "記事",
    "スペック", "設定", "天井", "やめどき", "判別", "導入日", "スケジュール",
    "更新", "紹介", "について", "など", "ランキング", "一覧", "リスト",
    "初打ち", "評価", "感想", "報告", "速報", "詳細", "新台", "考察",
    "グランドオープン", "オープン", "リニューアル", "閉店",
}

def extract_keywords(entries, top_n=5):
    """記事タイトルからカタカナ・漢字トークンを抽出して頻度上位を返す"""
    counter = Counter()
    for e in entries:
        raw = html.unescape(e["title"])
        # カタカナ3文字以上 / 漢字2文字以上のまとまりを抽出
        tokens = re.findall(r'[ァ-ヶー]{3,}|[一-龯々]{2,}', raw)
        for t in tokens:
            if t not in STOP_WORDS:
                counter[t] += 1
    return counter.most_common(top_n)





def fetch_johojima_stats():
    LABEL_MAP = {
        "営業店舗数": "店舗数",
        "グループ数": "グループ数",
        "企業数":     "企業数",
        "パチンコ台数": "パチンコ台数",
        "スマパチ台数": "スマパチ台数",
        "スロット台数": "スロット台数",
        "スマスロ台数": "スマスロ台数",
    }
    try:
        res = requests.get("https://p-johojima.jp/", timeout=15,
                           headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(res.text, "html.parser")
        stats = {}
        for wrapper in soup.find_all("div", class_="widget-content-wrapper"):
            heading = wrapper.find("div", class_="widget-heading")
            numbers = wrapper.find("div", class_="widget-numbers")
            if not heading or not numbers:
                continue
            label_text = heading.get_text(strip=True)
            span = numbers.find("span")
            raw = span.get_text(strip=True) if span else numbers.get_text(strip=True)
            m = re.search(r"[\d,]+", raw)
            val_text = m.group(0).replace(",", "") if m else ""
            for key, stat_key in LABEL_MAP.items():
                if key in label_text and val_text.isdigit():
                    stats[stat_key] = f"{int(val_text):,}"
                    break
        return stats
    except Exception as e:
        print(f"[WARN] 情報島スクレイピング失敗: {e}")
        return {}


def build_stats_html(stats):
    if not stats:
        return "<!-- STATS_START --><!-- STATS_END -->"

    def val(key):
        v = stats.get(key, "-")
        return f"{int(v):,}" if v != "-" and v.isdigit() else v

    return (
        f'<!-- STATS_START -->'
        f'<span class="stats-group">'
        f'<span class="stats-group-label">STORE</span>'
        f'<span class="stats-item"><span class="stats-item-label">店舗</span><span class="stats-item-value">{val("店舗数")}</span></span>'
        f'<span class="stats-sep">|</span>'
        f'<span class="stats-item"><span class="stats-item-label">グループ</span><span class="stats-item-value">{val("グループ数")}</span></span>'
        f'<span class="stats-sep">|</span>'
        f'<span class="stats-item"><span class="stats-item-label">企業</span><span class="stats-item-value">{val("企業数")}</span></span>'
        f'</span>'
        f'<span class="stats-group">'
        f'<span class="stats-group-label">PACHIKO</span>'
        f'<span class="stats-item"><span class="stats-item-label">設置台数</span><span class="stats-item-value">{val("パチンコ台数")}</span></span>'
        f'<span class="stats-sep">|</span>'
        f'<span class="stats-item"><span class="stats-item-label">スマパチ</span><span class="stats-item-value">{val("スマパチ台数")}</span></span>'
        f'</span>'
        f'<span class="stats-group">'
        f'<span class="stats-group-label">PACHISLOT</span>'
        f'<span class="stats-item"><span class="stats-item-label">スロット</span><span class="stats-item-value">{val("スロット台数")}</span></span>'
        f'<span class="stats-sep">|</span>'
        f'<span class="stats-item"><span class="stats-item-label">スマスロ</span><span class="stats-item-value">{val("スマスロ台数")}</span></span>'
        f'</span>'
        f'<!-- STATS_END -->'
    )


def update_section(content, start_marker, end_marker, new_html):
    start = content.find(start_marker)
    end = content.find(end_marker) + len(end_marker)
    if start == -1 or end == -1:
        return None
    return content[:start] + new_html + content[end:]


def fetch_fullslottle_articles():
    import json
    cutoff = datetime.now(JST) - timedelta(weeks=1)
    articles = []
    try:
        feed = feedparser.parse("https://parlourfullslotl.com/feed")
        for entry in feed.entries:
            pub = entry.get("published_parsed") or entry.get("updated_parsed")
            if not pub:
                continue
            dt = datetime(*pub[:6], tzinfo=timezone.utc).astimezone(JST)
            if dt < cutoff:
                break
            articles.append({"t": entry.get("title", ""), "u": entry.get("link", "#")})
    except Exception as e:
        print(f"[WARN] フルスロットル記事取得失敗: {e}")
    return articles


def build_char_articles_js(articles):
    import json
    data = json.dumps(articles, ensure_ascii=False)
    return f'<!-- CHAR_ARTICLES_START --><script>var CHAR_ARTICLES={data};</script><!-- CHAR_ARTICLES_END -->'


def update_html(news_html, sidebar_html, stats_html, char_js):
    content = HTML_FILE.read_text(encoding="utf-8")
    for marker_s, marker_e, new in [
        ("<!-- NEWS_START -->",         "<!-- NEWS_END -->",         news_html),
        ("<!-- SIDEBAR_START -->",      "<!-- SIDEBAR_END -->",      sidebar_html),
        ("<!-- STATS_START -->",        "<!-- STATS_END -->",        stats_html),
        ("<!-- CHAR_ARTICLES_START -->","<!-- CHAR_ARTICLES_END -->", char_js),
    ]:
        content = update_section(content, marker_s, marker_e, new)
        if content is None:
            print(f"[ERROR] マーカーが見つかりません: {marker_s}")
            return False
    HTML_FILE.write_text(content, encoding="utf-8")
    return True


LOG_FILE = Path(r"C:\Users\Public\pachinfo_log.txt") if os.name == 'nt' else None

def log(msg):
    line = f"[{datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    if LOG_FILE:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def main():
    log(f"取得開始")
    updated = datetime.now(JST).strftime("%Y.%m.%d %H:%M")

    entries = fetch_entries()
    if not entries:
        log("WARN: ニュース記事が0件です")
        return
    log(f"ニュース {len(entries)} 件取得")
    news_html = build_news_html(entries)

    log("YouTube動画取得中...")
    videos = fetch_youtube_videos()
    log(f"YouTube {len(videos)} 件取得")
    sidebar_html = build_sidebar_html(videos, updated)

    log("情報島統計取得中...")
    stats = fetch_johojima_stats()
    stats_html = build_stats_html(stats)

    log("フルスロットル記事取得中...")
    char_articles = fetch_fullslottle_articles()
    log(f"フルスロットル {len(char_articles)} 件取得")
    char_js = build_char_articles_js(char_articles)

    if update_html(news_html, sidebar_html, stats_html, char_js):
        log(f"HTML更新完了: {HTML_FILE}")
        # PC環境のみデプロイ・スリープ処理
        if os.name == 'nt':
            import subprocess
            log("Netlifyへデプロイ中...")
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", r"C:\Users\Public\pachinfo_deploy.ps1"],
                capture_output=True
            )
            if result.returncode == 0:
                log("Netlifyデプロイ完了")
            else:
                log(f"ERROR: デプロイ失敗 (code={result.returncode})")
                log(result.stderr.decode(errors='replace'))
    else:
        log("ERROR: HTML更新に失敗しました（マーカーが見つからない可能性）")


if __name__ == "__main__":
    main()
    if os.name == 'nt':
        import subprocess
        subprocess.run(["powershell", "-Command", "Start-Sleep -Seconds 30; rundll32.exe powrprof.dll,SetSuspendState Sleep"], shell=False)
