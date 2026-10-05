"""Stage 4: turn tagged posts into the engine's findings.
Outputs data/engine.json, which the web app reads: funnel, source yield, cue gaps,
failure-stage x content-type matrix, scored opportunity areas (with quotes), query examples, hypotheses inputs."""
import json, os, collections, math, re

ROOT = os.path.join(os.path.dirname(__file__), "..")
D = lambda *p: os.path.join(ROOT, "data", *p)
corpus = {json.loads(l)["id"]: json.loads(l) for l in open(D("clean/corpus.jsonl"))}
tags = {}
for l in open(D("tagged/tagged.jsonl")):
    t = json.loads(l)
    if t.get("id") in corpus: tags[t["id"]] = t
funnel2 = json.load(open(D("clean/funnel_stage2.json")))

STAGES = ["cannot_express", "misunderstood", "buried", "cannot_refine", "index_gap", "feature_regression", "not_in_library"]
STAGE_LABEL = {"cannot_express": "Can't put the memory into words", "misunderstood": "Search misreads the query",
    "buried": "Right photo buried in results / timeline", "cannot_refine": "Can't combine or narrow cues",
    "index_gap": "Photo isn't searchable (faces, text, place not indexed)", "feature_regression": "Search changed or got worse",
    "not_in_library": "Photo actually missing"}
ADDRESSABLE = {"cannot_express": 1.0, "misunderstood": 0.9, "buried": 1.0, "cannot_refine": 1.0, "index_gap": 0.8,
               "feature_regression": 0.6, "not_in_library": 0.2}  # could a retrieval-UX change fix it (vs. backup/infra)?

def L(x): return x if isinstance(x, list) else ([x] if x else [])
rows = []
for i, t in tags.items():
    c = corpus[i]
    rows.append({**t, "source": c["source"], "url": c["url"], "date": c["date"], "words": c["words"],
                 "rating": c.get("rating"), "title": c.get("title", ""), "text": c["full_text"][:700]})
stories = [r for r in rows if r.get("relevance") == "retrieval_story"]
feedback = [r for r in rows if r.get("relevance") == "search_feedback"]
evidence = stories + feedback

# Funnel + source yield
sources = sorted(funnel2)
src = {}
for s in sources:
    f = funnel2[s]; tagged = [r for r in rows if r["source"] == s]
    st = [r for r in stories if r["source"] == s]
    src[s] = {"raw": f.get("raw", 0), "clean": f.get("clean", 0), "candidates": f.get("candidate", 0), "tagged": len(tagged),
              "stories": len(st), "feedback": sum(r["source"] == s for r in feedback),
              "density": round(len(st) / max(1, len(tagged)), 3),
              "median_words": sorted([r["words"] for r in st])[len(st)//2] if st else 0}
funnel = {"raw": sum(v["raw"] for v in src.values()), "clean": sum(v["clean"] for v in src.values()),
          "candidates": sum(v["candidates"] for v in src.values()), "tagged": len(rows),
          "stories": len(stories), "feedback": len(feedback),
          "off_goal": sum(r.get("relevance") == "off_goal" for r in rows), "noise": sum(r.get("relevance") == "noise" for r in rows)}

cnt = lambda key, pool: collections.Counter(v for r in pool for v in L(r.get(key)) if v and v not in ("none", "none_stated", "unknown"))
remembered, forgotten = cnt("cues_remembered", stories), cnt("cues_forgotten", stories)
typed_cues = collections.Counter()  # which remembered cues made it into the typed query
for r in stories:
    q = (r.get("query_typed") or "").strip()
    if q:
        for cue in L(r.get("cues_remembered")): typed_cues[cue] += 1

matrix = collections.defaultdict(collections.Counter)
for r in stories:
    matrix[r.get("content_type", "unknown")][r.get("failure_stage", "none")] += 1

def quote(r): return {"q": r.get("quote") or r["text"][:240], "source": r["source"], "url": r["url"], "date": r["date"],
                      "type": r.get("content_type"), "stage": r.get("failure_stage"), "need": r.get("user_need", "")}

# Opportunity areas = failure stages, scored with visible inputs
opps = []
N = max(1, len(evidence))
for st in STAGES:
    pool = [r for r in evidence if r.get("failure_stage") == st]
    if not pool: continue
    prevalence = len(pool) / N
    sev = sum(int(r.get("severity") or 1) for r in pool) / len(pool) / 3
    srcs = len({r["source"] for r in pool}); diversity = srcs / max(1, len(sources))
    notfound = sum(r.get("outcome") == "not_found" for r in pool) / len(pool)
    score = math.sqrt(len(pool)) * (0.5 + sev) * (0.5 + diversity) * ADDRESSABLE[st]
    # Evidence order: real stories first, then ones that quote a search or name a cue, then mid-length posts (most readable)
    def qrank(r):
        q = r.get("quote") or ""
        return (r.get("relevance") != "retrieval_story", not (r.get("query_typed") or "").strip(),
                not [c for c in L(r.get("cues_remembered")) if c not in ("none",)], abs(len(q.split()) - 25))
    best = sorted(pool, key=qrank)
    opps.append({"stage": st, "label": STAGE_LABEL[st], "mentions": len(pool), "prevalence": round(prevalence, 3),
                 "severity": round(sev, 2), "sources": srcs, "not_found_rate": round(notfound, 2),
                 "addressable": ADDRESSABLE[st], "score": round(score, 2),
                 "content_types": cnt("content_type", pool).most_common(5), "workarounds": cnt("workaround", pool).most_common(5),
                 "quotes": [quote(r) for r in best[:8]]})
opps.sort(key=lambda o: -o["score"])

queries = [{"query": r["query_typed"], "remembered": L(r.get("cues_remembered")), "stage": r.get("failure_stage"),
            "type": r.get("content_type"), "source": r["source"], "url": r["url"]}
           for r in stories if (r.get("query_typed") or "").strip()]

# Memory richness vs query richness: how many cues people hold vs how many words they type
def real(cs): return [c for c in L(cs) if c and c not in ("none", "none_stated")]
multi = [r for r in stories if len(real(r.get("cues_remembered"))) >= 2]
qlens = [len(q["query"].split()) for q in [{"query": r["query_typed"]} for r in stories if (r.get("query_typed") or "").strip()]]
richness = {"stories_with_2plus_cues": len(multi), "share_2plus_cues": round(len(multi) / max(1, len(stories)), 3),
            "avg_cues_remembered": round(sum(len(real(r.get("cues_remembered"))) for r in stories) / max(1, len(stories)), 2),
            "queries_quoted": len(qlens), "query_median_words": sorted(qlens)[len(qlens)//2] if qlens else 0,
            "queries_1_2_words": sum(1 for n in qlens if n <= 2), "share_queries_1_2_words": round(sum(1 for n in qlens if n <= 2) / max(1, len(qlens)), 3)}
by_source_stage = {s: dict(collections.Counter(r.get("failure_stage") for r in evidence if r["source"] == s)) for s in sources}
out = {"funnel": funnel, "richness": richness, "by_source_stage": by_source_stage, "sources": src, "remembered": remembered.most_common(), "forgotten": forgotten.most_common(),
       "typed_cues": typed_cues.most_common(), "content_types": cnt("content_type", stories).most_common(),
       "stages": cnt("failure_stage", evidence).most_common(), "workarounds": cnt("workaround", stories).most_common(),
       "outcomes": cnt("outcome", stories).most_common(), "segments": cnt("segment_signal", stories).most_common(),
       "matrix": {k: dict(v) for k, v in matrix.items()}, "opportunities": opps, "queries": queries,
       "stage_labels": STAGE_LABEL, "models": collections.Counter(r.get("_model") for r in rows).most_common()}
json.dump(out, open(D("engine.json"), "w"), ensure_ascii=False, indent=1)
# Evidence table for the explorer + chat retrieval
with open(D("evidence.json"), "w") as f:
    json.dump([{k: r.get(k) for k in ["id", "source", "url", "date", "relevance", "content_type", "cues_remembered", "cues_forgotten",
               "query_typed", "failure_stage", "workaround", "outcome", "severity", "user_need", "quote", "segment_signal", "text"]}
               for r in evidence], f, ensure_ascii=False)
print(json.dumps(funnel), "\n", [(o["label"], o["mentions"], o["score"]) for o in opps])
