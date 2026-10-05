"""Reddit via the Arctic Shift archive API (reddit.com itself is blocked from our environment).
1) Every r/googlephotos post since START, paged chronologically, kept if it passes the retrieval prefilter.
2) Keyword comment search in r/googlephotos and adjacent subs.
"""
import time, requests, datetime as dt
from common import record, write_jsonl, get, RETRIEVAL_RE

A = "https://arctic-shift.photon-reddit.com/api"
START = "2023-01-01"
s = requests.Session(); s.headers["User-Agent"] = "nl-discovery-engine/0.1 (research)"
rows = []

def ts(x): return dt.datetime.utcfromtimestamp(int(x)).strftime("%Y-%m-%d")

# 1. posts in r/googlephotos
after, n, misses = START, 0, 0
while True:
    r = get(s, f"{A}/posts/search?subreddit=googlephotos&limit=100&sort=asc&after={after}")
    try: data = (r.json().get("data") if r else None) or []
    except Exception: data = []
    if not data:
        misses += 1
        if misses > 4:
            after_ts = (after if isinstance(after, int) else int(dt.datetime.fromisoformat(after).timestamp())) + 7 * 86400
            if after_ts > time.time(): break
            after, misses = after_ts, 0
        time.sleep(5); continue
    misses = 0
    for p in data:
        n += 1
        txt = (p.get("selftext") or "").replace("[removed]", "").replace("[deleted]", "")
        if RETRIEVAL_RE.search(p.get("title", "") + " " + txt):
            rows.append(record("reddit", p["id"], txt, url="https://www.reddit.com" + p.get("permalink", ""),
                date=ts(p["created_utc"]), title=p.get("title", ""),
                meta={"subreddit": p.get("subreddit"), "score": p.get("score"), "num_comments": p.get("num_comments"), "kind": "post"}))
    after = int(data[-1]["created_utc"]) + 1
    if n % 1000 < 100: print("posts scanned", n, "kept", len(rows), ts(after), flush=True)
    time.sleep(0.4)
print("posts done", n, len(rows), flush=True)

# 2. keyword comment search
SUBS = ["googlephotos", "GooglePixel", "Android", "google", "DataHoarder", "techsupport", "pixel_phones", "samsung", "iphone", "ios"]
QUERIES = ["can't find photo", "find old photo", "search photos", "photos search", "ask photos", "find a picture",
           "couldn't find", "search for a photo", "screenshot search", "remember the photo", "scrolling through photos"]
for sub in SUBS:
    for q in QUERIES:
        before = None
        for _ in range(3):
            url = f"{A}/comments/search?subreddit={sub}&body={requests.utils.quote(q)}&limit=100&after={START}"
            if before: url += f"&before={before}"
            r = get(s, url)
            try: data = (r.json().get("data") if r else None) or []
            except Exception: data = []
            for c in data:
                body = c.get("body") or ""
                if sub != "googlephotos" and "photo" not in body.lower(): continue
                rows.append(record("reddit", c["id"], body,
                    url=f"https://www.reddit.com/r/{c.get('subreddit')}/comments/{(c.get('link_id') or '')[3:]}/_/{c['id']}/",
                    date=ts(c["created_utc"]), meta={"subreddit": c.get("subreddit"), "score": c.get("score"), "kind": "comment", "query": q}))
            if len(data) < 100: break
            before = int(data[-1]["created_utc"])
            time.sleep(0.5)
        time.sleep(0.5)
    print("comments", sub, len(rows), flush=True)
write_jsonl("reddit", rows)
