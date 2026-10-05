"""Shared helpers: unified record schema + JSONL writer + keyword prefilter."""
import hashlib, json, os, re, time

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")

# Recall-oriented prefilter: anything that might be a "trying to find a photo" story.
RETRIEVAL_RE = re.compile(
    r"\b(search|searched|searching|find|finding|found|locate|look(ing)? for|scroll(ed|ing)?|"
    r"can'?t find|cannot find|couldn'?t find|unable to find|remember|memor(y|ies)|old photo|old pic|"
    r"ask photos|screenshot|lost|missing|where is|dig(ging)? through|years ago|tagged|face group|"
    r"people & pets|people and pets|recognize|recognise|keyword|query|results?)\b",
    re.I,
)

def rid(source, key):
    return source + ":" + hashlib.md5(str(key).encode()).hexdigest()[:12]

def record(source, key, text, url="", date="", title="", rating=None, meta=None):
    return {
        "id": rid(source, key), "source": source, "url": url, "date": str(date)[:10],
        "title": (title or "").strip(), "text": (text or "").strip(),
        "rating": rating, "meta": meta or {},
    }

def write_jsonl(name, rows):
    os.makedirs(RAW_DIR, exist_ok=True)
    seen, out = set(), []
    for r in rows:
        if r["id"] in seen or len(r["text"]) + len(r["title"]) < 15:
            continue
        seen.add(r["id"]); out.append(r)
    path = os.path.join(RAW_DIR, f"{name}.jsonl")
    with open(path, "w") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[{name}] wrote {len(out)} rows -> {path}")
    return out

def get(session, url, tries=5, **kw):
    for i in range(tries):
        try:
            r = session.get(url, timeout=60, **kw)
            if r.status_code == 200:
                return r
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(3 * (i + 1)); continue
            return r
        except Exception:
            time.sleep(3 * (i + 1))
    return None
