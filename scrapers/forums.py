"""Other public forums: Hacker News (Algolia API) and Stack Exchange (webapps, android, apple)."""
import requests, html, re, datetime as dt
from common import record, write_jsonl, get

s = requests.Session(); s.headers["User-Agent"] = "nl-discovery-engine/0.1"
rows = []
def clean(x): return html.unescape(re.sub(r"<[^>]+>", " ", x or "")).strip()
for q in ["google photos search", "google photos find photo", "google photos ask photos", "photo search memory", "find old photo phone"]:
    for tag in ["comment", "story"]:
        r = get(s, f"https://hn.algolia.com/api/v1/search?query={requests.utils.quote(q)}&tags={tag}&hitsPerPage=200")
        for h in (r.json().get("hits", []) if r else []):
            txt = clean(h.get("comment_text") or h.get("story_text") or "")
            if "photo" not in (txt + (h.get("title") or "")).lower(): continue
            rows.append(record("hacker_news", h["objectID"], txt, url=f"https://news.ycombinator.com/item?id={h['objectID']}",
                date=(h.get("created_at") or "")[:10], title=h.get("title") or h.get("story_title") or "", meta={"query": q}))
print("hn", len(rows), flush=True)
for site in ["webapps", "android", "apple", "superuser"]:
    for q in ["google photos search", "google photos find", "find photo google photos"]:
        r = get(s, "https://api.stackexchange.com/2.3/search/advanced", params={"q": q, "site": site, "pagesize": 100, "filter": "withbody", "order": "desc", "sort": "relevance"})
        for it in (r.json().get("items", []) if r else []):
            rows.append(record("stack_exchange", f"{site}-{it['question_id']}", clean(it.get("body")), url=it["link"],
                date=dt.datetime.utcfromtimestamp(it["creation_date"]).strftime("%Y-%m-%d"), title=html.unescape(it["title"]),
                meta={"site": site, "score": it.get("score")}))
print("all", len(rows))
write_jsonl("forums", rows)
