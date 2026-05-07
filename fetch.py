#!/usr/bin/env python3
"""
ExtraterrestrEAL — Content Pipeline
Fetches from NewsAPI + YouTube, summarizes with Claude, outputs JSON for each tab.
"""

import os, json, re, time, hashlib, requests
from datetime import datetime, timezone
from anthropic import Anthropic

# ── CONFIG ──────────────────────────────────────────────────────────────────

NEWS_API_KEY      = os.environ["NEWS_API_KEY"]
YOUTUBE_API_KEY   = os.environ["YOUTUBE_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

client = Anthropic(api_key=ANTHROPIC_API_KEY)

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

MAX_NEWS     = 30
MAX_VIDEOS   = 24
MAX_PODCASTS = 20
MAX_DOCS     = 20

# ── NEWS QUERIES ─────────────────────────────────────────────────────────────

NEWS_QUERIES = [
    "UFO UAP disclosure",
    "alien extraterrestrial government",
    "UAP Congress whistleblower",
    "Pentagon UFO non-human intelligence",
    "AARO UAP report",
    "UFO sighting military pilots",
    "David Grusch testimony UAP",
    "UAP legislation NDAA disclosure",
    "non-human intelligence craft recovered",
    "SETI extraterrestrial signal anomaly",
]

DOC_QUERIES = [
    "FOIA UFO declassified documents release",
    "CIA declassified alien files government",
    "Pentagon UAP AARO official report",
    "government UFO cover-up documents released",
    "UAP whistleblower congressional testimony documents",
    "declassified military UFO encounter report",
]

# ── YOUTUBE SEARCH TERMS ─────────────────────────────────────────────────────

VIDEO_SEARCHES = [
    "Weaponized George Knapp Jeremy Corbell UAP",
    "Ross Coulthart Need to Know UFO disclosure",
    "Jesse Michels American Alchemy UAP interview",
    "Richard Dolan UFO history analysis",
    "Steven Greer disclosure project UFO",
    "UAP Gerb documentary investigation",
    "NewsNation UAP coverage 2025",
    "Cristina Gomez Paradigm Shifts UAP",
    "David Grusch UFO interview testimony",
    "Lue Elizondo UAP Pentagon interview",
]

PODCAST_SEARCHES = [
    "Need to Know podcast Coulthart Zabel UAP",
    "That UFO Podcast Andy McGrillen interview",
    "Somewhere in the Skies Ryan Sprague UFO",
    "Fade to Black Jimmy Church UFO radio",
    "High Strange podcast UAP investigation",
    "Disclosure Team Vinnie Adams UFO interview",
    "UAP alien podcast interview 2025",
]

# ── HELPERS ──────────────────────────────────────────────────────────────────

def uid(text):
    return hashlib.md5(text.encode()).hexdigest()[:8]

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def clean(text, length=220):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:length] + ('…' if len(text) > length else '')

# ── CLAUDE SUMMARIZE ──────────────────────────────────────────────────────────

def claude_summarize(title, raw_desc, content_type="news"):
    try:
        prompt = f"""You are the editor of ExtraterrestrEAL — a serious, credible aggregator covering UFOs, UAPs, extraterrestrial life, and government disclosure. Editorial stance: UFOs are real, aliens are real, governments have suppressed this for decades. This is not a conspiracy site — it is a disclosure site.

Rewrite this {content_type} description in 1-2 punchy, declarative sentences. Tone: serious, urgent, credible — like a classified intelligence briefing, not tabloid. No fluff. No "in this video" or "this article discusses". No first-person. Just the facts and why they matter to the disclosure movement.

Title: {title}
Original: {raw_desc}

Return ONLY the rewritten description. Nothing else."""

        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        return resp.content[0].text.strip()
    except Exception as e:
        print(f"  Claude error: {e}")
        return clean(raw_desc)

# ── NEWSAPI ───────────────────────────────────────────────────────────────────

def fetch_news_query(query, page_size=4):
    try:
        r = requests.get("https://newsapi.org/v2/everything", params={
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": page_size,
            "apiKey": NEWS_API_KEY,
        }, timeout=15)
        return r.json().get("articles", [])
    except Exception as e:
        print(f"  NewsAPI error ({query}): {e}")
        return []

def fetch_all_news(queries, page_size=4):
    seen = set()
    articles = []
    for q in queries:
        for a in fetch_news_query(q, page_size):
            url = a.get("url", "")
            if not url or url in seen:
                continue
            if "[Removed]" in (a.get("title", "") + a.get("description", "")):
                continue
            seen.add(url)
            articles.append(a)
        time.sleep(0.3)
    return articles

def process_articles(raw_articles, content_type="news", max_items=30):
    results = []
    for a in raw_articles[:max_items]:
        title    = (a.get("title") or "").strip()
        raw_desc = a.get("description") or a.get("content") or ""
        if not title:
            continue
        desc = claude_summarize(title, raw_desc, content_type)
        results.append({
            "id":          uid(a.get("url", "")),
            "type":        content_type,
            "title":       title,
            "description": desc,
            "url":         a.get("url", ""),
            "image":       a.get("urlToImage") or "",
            "source":      a.get("source", {}).get("name", ""),
            "publishedAt": a.get("publishedAt", ""),
        })
        time.sleep(0.15)
    return results

# ── YOUTUBE ───────────────────────────────────────────────────────────────────

def fetch_youtube(search_terms, max_per_term=3, content_type="video"):
    seen = set()
    items = []
    for term in search_terms:
        try:
            r = requests.get("https://www.googleapis.com/youtube/v3/search", params={
                "part":       "snippet",
                "q":          term,
                "type":       "video",
                "order":      "date",
                "maxResults": max_per_term,
                "key":        YOUTUBE_API_KEY,
            }, timeout=15)
            data = r.json()

            if "error" in data:
                print(f"  YouTube API error ({term}): {data['error'].get('message','unknown')}")
                time.sleep(1)
                continue

            for v in data.get("items", []):
                vid = v.get("id", {}).get("videoId", "")
                if not vid or vid in seen:
                    continue
                seen.add(vid)

                sn    = v.get("snippet", {})
                title = sn.get("title", "").strip()
                if not title:
                    continue

                raw_desc = sn.get("description", "")
                desc     = claude_summarize(title, raw_desc, content_type)

                # best available thumbnail
                thumbs = sn.get("thumbnails", {})
                thumb  = (
                    thumbs.get("high") or
                    thumbs.get("medium") or
                    thumbs.get("default") or {}
                ).get("url", "")

                items.append({
                    "id":          uid(vid),
                    "type":        content_type,
                    "title":       title,
                    "description": desc,
                    "url":         f"https://www.youtube.com/watch?v={vid}",
                    "image":       thumb,
                    "source":      sn.get("channelTitle", ""),
                    "publishedAt": sn.get("publishedAt", ""),
                })
                time.sleep(0.15)

        except Exception as e:
            print(f"  YouTube fetch error ({term}): {e}")

        time.sleep(0.4)

    return items

# ── SAVE ─────────────────────────────────────────────────────────────────────

def save(filename, items):
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
    print(f"  ✓ Saved {len(items)} items → {path}")

# ── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print(f"\n[{now_iso()}] 🛸 ExtraterrestrEAL pipeline starting...\n")

    # NEWS
    print("→ Fetching news articles...")
    raw_news  = fetch_all_news(NEWS_QUERIES, page_size=4)
    news_items = process_articles(raw_news, "news", MAX_NEWS)
    save("news.json", news_items)

    # VIDEOS
    print("\n→ Fetching YouTube videos...")
    video_items = fetch_youtube(VIDEO_SEARCHES, max_per_term=3, content_type="video")
    save("videos.json", video_items[:MAX_VIDEOS])

    # PODCASTS
    print("\n→ Fetching podcast content...")
    podcast_items = fetch_youtube(PODCAST_SEARCHES, max_per_term=3, content_type="podcast")
    save("podcasts.json", podcast_items[:MAX_PODCASTS])

    # DECLASSIFIED DOCS
    print("\n→ Fetching declassified/FOIA content...")
    raw_docs  = fetch_all_news(DOC_QUERIES, page_size=5)
    doc_items = process_articles(raw_docs, "doc", MAX_DOCS)
    save("docs.json", doc_items)

    print(f"\n[{now_iso()}] ✅ Pipeline complete.\n")

if __name__ == "__main__":
    main()
