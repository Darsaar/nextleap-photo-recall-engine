"""Google Photos Help Community (support.google.com/photos/threads).
Thread lists come from the 'Searching' / 'Face groups' / 'Organization' categories plus keyword filters;
each thread page embeds the question and replies in a script blob, which we decode."""
import re, html, time, requests
from concurrent.futures import ThreadPoolExecutor
from common import record, write_jsonl, get, RETRIEVAL_RE

BASE = "https://support.google.com/photos"
s = requests.Session(); s.headers.update({"User-Agent": "Mozilla/5.0", "Accept-Language": "en"})

FILTERS = ["(category:photos_searching)", "(category:photos_facegroups)", "(category:photos_organization)"] + [
    f'(query:"{q}")' for q in ["can't find", "cannot find", "find a photo", "find old photos", "search not working",
    "search results", "search for", "ask photos", "looking for a photo", "find picture", "search by date",
    "search screenshots", "search text", "remember", "find photos of", "missing from search", "find a picture"]]

threads = {}
for f in FILTERS:
    r = get(s, f"{BASE}/threads?hl=en&max_results=1000&thread_filter={requests.utils.quote(f, safe='():')}")
    if not r: continue
    for tid, slug in re.findall(r'/photos/thread/(\d+)/([^"?]+)', r.text):
        threads.setdefault(tid, {"slug": slug, "filters": set()})["filters"].add(f)
    print(f, len(threads), flush=True)

def dec(x):
    x = re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), x)
    x = x.replace('\\\\u0026', '&').replace('\\u0026', '&')
    x = re.sub(r"\\+u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), x)
    return html.unescape(re.sub(r"<[^>]+>", " ", x)).replace('\\"', '"').replace("\\n", " ")

def fetch(item):
    tid, info = item
    r = get(s, f"{BASE}/thread/{tid}?hl=en", tries=2)
    if not r: return None
    t = r.text
    m = re.search(r"\[\[" + tid + r",\\x22\d+\\x22,\d+,\d+\](.{0,200000})", t, re.S)
    if not m: return None
    blob = m.group(1)
    strs = [dec(x) for x in re.findall(r"\\x22((?:[^\\]|\\(?!x22))*?)\\x22", blob)]
    strs = [re.sub(r"\s+", " ", x.replace("\\", " ")).strip() for x in strs]
    strs = [x for x in strs if x]
    if len(strs) < 2: return None
    title, body = strs[0], strs[1]
    prose = [x for x in strs[2:] if len(x) > 40 and " " in x and not x.startswith("http")]
    replies = []
    for x in prose:
        if x not in replies and x != body: replies.append(x)
        if len(replies) >= 6: break
    date = ""
    md = re.search(r"\[" + tid + r",\\x22(\d{10})", t)
    return record("help_forum", tid, body, url=f"{BASE}/thread/{tid}?hl=en", title=title,
                  meta={"filters": sorted(info["filters"]), "replies": [x[:800] for x in replies]})

# Keep every 'Searching' thread; for other filters keep threads whose title slug looks retrieval-related.
SLUG_RE = re.compile(r"find|search|look|lost|missing|remember|old|where|locate|ask-photos|face|people|screenshot|date|location|text|scroll", re.I)
picked = {t: i for t, i in threads.items() if "(category:photos_searching)" in i["filters"] or SLUG_RE.search(i["slug"])}
# Resume: keep rows already fetched, only fetch the rest (Google throttles bursts).
import json, os
_prev = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "help_forum.jsonl")
kept = [json.loads(l) for l in open(_prev)] if os.path.exists(_prev) else []
have = {r["meta"].get("tid") or r["url"].split("/thread/")[1].split("?")[0] for r in kept}
picked = {t: i for t, i in picked.items() if t not in have}
print("threads to fetch", len(picked), "of", len(threads), flush=True)
rows = list(kept)
with ThreadPoolExecutor(4) as ex:
    for n, r in enumerate(ex.map(fetch, picked.items())):
        if r: rows.append(r)
        if n % 200 == 0: print("fetched", n, len(rows), flush=True)
print("fetched", len(rows), "of", len(picked))
write_jsonl("help_forum", rows)
