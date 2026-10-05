"""Stage 2: normalise, dedupe, drop non-English / too-short rows, then split into evidence buckets
with a recall-oriented prefilter (the LLM makes the final relevance call in stage 3)."""
import glob, json, os, re, hashlib, collections

ROOT = os.path.join(os.path.dirname(__file__), "..")
RAW, OUT = os.path.join(ROOT, "data/raw"), os.path.join(ROOT, "data/clean")
os.makedirs(OUT, exist_ok=True)

# Signals that a post is about finding / searching for a photo (candidate retrieval story).
FIND = re.compile(r"(can'?t|cannot|couldn'?t|unable to|hard to|impossible to|never) (find|locate|search)|"
    r"\b(search(ed|ing|es)?|find(ing)?|look(ing)? for|scroll(ed|ing)? (through|back|for)|dig(ging)? (through|for)|ask photos|"
    r"remember(ed)?|forgot|years ago|old (photo|pic|picture|screenshot)s?|where (is|did) (my|the|that) (photo|pic|picture))\b", re.I)
PHOTO = re.compile(r"\b(photo|pic|picture|image|screenshot|video|memory|memories|selfie|album)s?\b", re.I)
# Loud but off-goal themes in Photos feedback.
OFFGOAL = re.compile(r"\b(storage|backup|back up|backing up|subscription|google one|pay|price|ads?|crash(es|ed)?|slow|lag|"
    r"upload(ing)?|sync(ing)?|deleted|trash|recover|restore|takeout|space|gb|tb|edit(or|ing)?|collage|movie)\b", re.I)

def english(t):
    letters = re.findall(r"[A-Za-z]", t)
    return len(letters) >= 0.6 * max(1, len(re.sub(r"\s", "", t)))

rows, seen = [], set()
funnel = collections.defaultdict(lambda: collections.Counter())
for path in sorted(glob.glob(os.path.join(RAW, "*.jsonl"))):
    for line in open(path):
        r = json.loads(line); src = r["source"]; funnel[src]["raw"] += 1
        full = (r["title"] + ". " + r["text"]).strip(". ")
        key = hashlib.md5(re.sub(r"\W+", "", full.lower())[:300].encode()).hexdigest()
        if key in seen: funnel[src]["dup"] += 1; continue
        seen.add(key)
        if len(full.split()) < 6 or not english(full): funnel[src]["short_or_non_english"] += 1; continue
        funnel[src]["clean"] += 1
        find, photo, off = bool(FIND.search(full)), bool(PHOTO.search(full)), bool(OFFGOAL.search(full))
        searching_cat = "(category:photos_searching)" in (r.get("meta") or {}).get("filters", [])
        if (find and (photo or src in ("help_forum", "reddit"))) or searching_cat:
            bucket = "candidate"
        elif off:
            bucket = "off_goal"
        else:
            bucket = "other"
        funnel[src][bucket] += 1
        r["full_text"], r["bucket"], r["words"] = full, bucket, len(full.split())
        rows.append(r)

with open(os.path.join(OUT, "corpus.jsonl"), "w") as f:
    for r in rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")
with open(os.path.join(OUT, "candidates.jsonl"), "w") as f:
    for r in rows:
        if r["bucket"] == "candidate": f.write(json.dumps(r, ensure_ascii=False) + "\n")
json.dump({k: dict(v) for k, v in funnel.items()}, open(os.path.join(OUT, "funnel_stage2.json"), "w"), indent=1)
for k, v in funnel.items(): print(k, dict(v))
print("candidates", sum(1 for r in rows if r["bucket"] == "candidate"))
