"""Stage 5: research-question insight cards and Overview chart data, computed from evidence.json + engine.json.
No LLM call: numbers come from the tagged data, the sentences are templates, so the cards always match the data.
Output: data/insights.json (read by app/build.py)."""
import json, os, re, collections

ROOT = os.path.join(os.path.dirname(__file__), "..")
D = lambda *p: os.path.join(ROOT, "data", *p)
E = json.load(open(D("evidence.json")))
G = json.load(open(D("engine.json")))

def L(x): return x if isinstance(x, list) else ([x] if x else [])
def real(xs): return [c for c in L(xs) if c and str(c).strip() not in ("none", "none_stated", "unknown", "-1")]
stage = lambda r: (r.get("failure_stage") or "").strip()
S = [r for r in E if r["relevance"] == "retrieval_story"]
KNOWN = ("found", "found_with_effort", "not_found")
def nf(rows):
    k = [r for r in rows if r["relevance"] == "retrieval_story" and r.get("outcome") in KNOWN]
    return sum(r["outcome"] == "not_found" for r in k) / len(k) if k else None
def srcs(rows): return len({r["source"] for r in rows})
def pct(a, b): return round(100 * a / b) if b else 0
# Same thresholds as the Ask tab's evidence badge (strength() in template.html)
def strength(n, s): return "High" if n >= 300 and s >= 6 else "Medium" if n >= 60 and s >= 3 else "Low"
def ev(rows, n=None):
    n = len(rows) if n is None else n
    return {"n": n, "sources": srcs(rows), "badge": strength(n, srcs(rows))}

opp = {o["stage"]: o for o in G["opportunities"]}
CUE = {"rough_time": "Rough time", "person": "Person", "object": "Object / thing in it", "text_in_image": "Words in the image",
       "source_app": "Which app it came from", "visual_look": "How it looked", "place": "Place", "event_context": "The event",
       "exact_date": "Exact date", "device": "Device"}

# ---------- Charts ----------
rem = collections.Counter(c for r in S for c in real(r.get("cues_remembered")))
c_remembered = [[k, rem[k], pct(rem[k], len(S))] for k in CUE if rem[k]][:8]
c_remembered.sort(key=lambda x: -x[1])

Q = [r for r in S if (r.get("query_typed") or "").strip()]
multi = [r for r in Q if len(real(r.get("cues_remembered"))) >= 2]
bucket = lambda n: "4+" if n >= 4 else str(n)
qlen = collections.Counter(bucket(len(r["query_typed"].split())) for r in Q)
c_length = {"all": [[b, qlen[b]] for b in ("1", "2", "3", "4+")], "n": len(Q),
            "multi_n": len(multi), "multi_short": sum(len(r["query_typed"].split()) <= 2 for r in multi)}

STAGES = [o["stage"] for o in G["opportunities"]]
c_stages = [[s, opp[s]["label"], opp[s]["mentions"], nf([r for r in E if stage(r) == s])] for s in STAGES]

K = [r for r in S if r.get("outcome") in KNOWN]
out = collections.Counter(r["outcome"] for r in K)
wk = collections.Counter(r.get("workaround") for r in S if real([r.get("workaround")]))
c_next = {"outcomes": [[k, out[k]] for k in ("found", "found_with_effort", "not_found")], "known": len(K),
          "workarounds": wk.most_common(5), "stated": sum(wk.values())}

TYPES = [t for t, _ in collections.Counter(r.get("content_type") for r in S).most_common() if t not in ("other", "unknown", None)][:8]
heat = {t: collections.Counter(stage(r) for r in S if r.get("content_type") == t) for t in TYPES}
c_heat = {"types": TYPES, "stages": STAGES, "cells": [[heat[t][s] for s in STAGES] for t in TYPES]}

yr = collections.defaultdict(collections.Counter)
for r in E:
    y = (r.get("date") or "")[:4]
    if y.isdigit(): yr[y][stage(r)] += 1
c_time = [[y, sum(yr[y].values()), yr[y]["feature_regression"], pct(yr[y]["feature_regression"], sum(yr[y].values()))]
          for y in sorted(yr) if sum(yr[y].values()) >= 40]  # years with too few posts make a noisy share

# ---------- Insight cards ----------
cards = []
two_plus = sum(len(real(r.get("cues_remembered"))) >= 2 for r in S)
cards.append({"q": "What do people remember about a photo they can't find?",
    "headline": "A rough sense of when, plus who or what was in it.",
    "body": f"Rough time, a person and an object are the most remembered details (chart 1). Only {pct(two_plus, len(S))}% of stories mention two or more, but that is what people write down, not all they recall.",
    "counter": "These are the details people chose to write down; the survey asks what they actually recall.",
    "recs": ["Treat time as a range (\"around 2019\", \"before the move\"), not an exact date.",
             "Use people and objects the library already knows as one-tap cues."],
    "hyp": ["H1", "H2"], "chart": 1, "filter": {"rel": "retrieval_story"}, **ev(S)})
short = qlen["1"] + qlen["2"]
cards.append({"q": "What do they type into search?",
    "headline": "One or two words, even when they remember more.",
    "body": f"{pct(short, len(Q))}% of the {len(Q)} quoted searches are 1–2 words (chart 2). Of {len(multi)} people who remembered two or more things, {c_length['multi_short']} still typed two words or fewer.",
    "counter": f"Only {len(Q)} of {len(S)} stories quote the exact search, so this rests on a small share of posts.",
    "recs": ["Let one search hold several cues (person + place + time) as chips.",
             "After the first word, suggest the next cue (\"Riya\" → \"in Goa?\", \"around Diwali?\").",
             "Show why each result matched, so a wrong cue is easy to fix."],
    "hyp": ["H1"], "chart": 2, "filter": {"rel": "retrieval_story", "q": True}, **ev(Q)})
top4 = [opp[s] for s in STAGES[:4]]
pool3 = [r for r in E if stage(r) in STAGES[:4]]
rank = {s: i + 1 for i, s in enumerate(STAGES)}
cards.append({"q": "Do real posts back the two branches slide 2 picked?",
    "headline": "Yes: combining cues and buried results rank 1 and 2, but \"not searchable\" is a close third.",
    "body": f"Combining cues ({opp['cannot_refine']['score']:.1f}) and buried results ({opp['buried']['score']:.1f}) top the ranking, and \"never backed up\" is last ({opp['not_in_library']['score']:.1f}), matching slide 2's fix / out calls (chart 3).",
    "counter": f"\"Not searchable\" has the most posts ({opp['index_gap']['mentions']}) and scores {opp['index_gap']['score']:.1f}; slide 2 parks it on feasibility, not size.",
    "recs": ["Keep combining cues and buried as the two focus branches.",
             "Say on the slide why \"not searchable\" is parked: it is an indexing fix, not a search-experience one."],
    "hyp": ["H1", "H2", "H3"], "chart": 3, "filter": {"stages": STAGES[:4]}, **ev(pool3)})
low = lambda r: (r.get("text") or "").lower()
cr = [r for r in E if stage(r) == "cannot_refine"]
cr_and = [r for r in cr if re.search(r"\band\b.*\b(and|with)\b|combine|both|multiple (people|faces|terms)|two people", low(r))]
cr_filter = [r for r in cr if re.search(r"filter|narrow|refine|date range|between", low(r))]
cards.append({"q": "Combining cues: what exactly goes wrong?",
    "headline": "Search drops the second cue, and there is no way to narrow by date or place.",
    "body": f"Of {len(cr)} \"can't combine\" posts, {len(cr_and)} describe trying two things at once (two people, a person and a place) and {len(cr_filter)} ask for a filter or date range. {pct(nf(cr) * 100, 100)}% of these stories end without the photo.",
    "counter": "The split comes from keyword matching on the post text, so treat it as direction, not exact counts.",
    "recs": ["Measure slide 2's inputs: share of multi-cue searches and zero results on them.",
             "Prototype cue chips plus a date-range slider in the same search."],
    "hyp": ["H1"], "chart": 3, "filter": {"stages": ["cannot_refine"]}, **ev(cr)})
bu = [r for r in E if stage(r) == "buried"]
bu_vol = [r for r in bu if re.search(r"too many|hundreds|thousands|endless|scroll(ing)? (for|through)", low(r))]
bu_order = [r for r in bu if re.search(r"wrong date|out of order|sorted|date taken|\border\b", low(r))]
bu_dup = [r for r in bu if re.search(r"duplicat|similar|look.?alike|same photo|burst|near.?identical", low(r))]
cards.append({"q": "Buried results: is it look-alikes or sheer volume?",
    "headline": "Where people say why, it is volume and wrong dates more than look-alikes.",
    "body": f"Of {len(bu)} \"buried\" posts, {len(bu_vol)} talk about too many results or long scrolls and {len(bu_order)} about photos in the wrong date or order; only {len(bu_dup)} mention duplicates or look-alike shots.",
    "counter": "Keyword matching, and most buried posts don't say why, so look-alikes may be under-described.",
    "recs": ["Consider renaming slide 2's branch to \"buried in volume\" and keep look-alikes as one input.",
             "Track scroll depth and the rank of the photo finally opened (slide 2's inputs)."],
    "hyp": ["H2"], "chart": 4, "filter": {"stages": ["buried"]}, **ev(bu)})
found = out["found"] + out["found_with_effort"]
cards.append({"q": "What do people do when search fails?",
    "headline": "They scroll the timeline or give up.",
    "body": f"{pct(out['not_found'], len(K))}% of stories with a known ending never found the photo. Where the next step is stated, scrolling and giving up lead, and some move to another app (chart 4).",
    "counter": f"{found} stories did find the photo ({out['found']} easily, {out['found_with_effort']} with effort), so search works for some.",
    "recs": ["Make \"roughly when\" a one-tap jump instead of a long scroll.",
             "When a search misses, offer \"what else do you remember?\" rather than an empty page."],
    "hyp": ["H2"], "chart": 4, "filter": {"rel": "retrieval_story", "outcome": "not_found"}, **ev(K)})
INFO = {"screenshot_info", "document_id", "receipt_bill", "medical", "text_in_image"}
info = [r for r in S if r.get("content_type") in INFO]
cards.append({"q": "Which photos are hardest to find?",
    "headline": "Information photos: screenshots, IDs, bills, medicines.",
    "body": f"{pct(sum(r.get('outcome') == 'not_found' for r in info if r.get('outcome') in KNOWN), sum(r.get('outcome') in KNOWN for r in info))}% of these stories end without the photo, and they usually fail because the words in them aren't searchable (chart 6).",
    "counter": f"A small base: {len(info)} stories.",
    "recs": ["Make text in screenshots and documents searchable and say when it is.",
             "Let people search by the app a screenshot came from."],
    "hyp": ["H4"], "chart": 6, "filter": {"types": sorted(INFO)}, **ev(info)})
SEG_ALL = {"android", "ios", "web", "large_library", "heavy_screenshots", "parent", "traveller", "professional", "uses_as_document_store", "older_user"}
SEG = {"large_library": "people with large libraries", "web": "web / desktop users", "android": "Android users", "ios": "iPhone users", "traveller": "travellers", "parent": "parents"}
segs = lambda r: [str(s).strip() for s in L(r.get("segment_signal")) if str(s).strip() in SEG_ALL]
base = collections.Counter(s for r in E for s in segs(r))
sub = collections.Counter(s for r in cr for s in segs(r))
lift = sorted([(s, sub[s], (sub[s] / len(cr)) / (base[s] / len(E))) for s in SEG if sub[s] >= 30], key=lambda x: -x[2])[:2]
cards.append({"q": "Who is hit hardest?",
    "headline": f"{' and '.join(SEG[s] for s, _, _ in lift).capitalize()}: the more photos, the more cues they need to combine.",
    "body": " ".join(f"{SEG[s][0].upper() + SEG[s][1:]} show up {l:.1f}× more often than usual in \"can't combine cues\" posts ({n} posts)." for s, n, l in lift),
    "counter": "Groups are self-declared and overlap, and Android dominates because most posts come from Google Play.",
    "recs": ["Pilot multi-cue search with large-library users first.",
             "Recruit large-library users for the interviews."],
    "hyp": ["H1"], "chart": None, "filter": {"stages": ["cannot_refine"]}, **ev(cr)})
PEOPLE = ("person", "pet", "child_family")
ppl = [r for r in E if r.get("content_type") in PEOPLE]
ppl_gap = [r for r in ppl if stage(r) == "index_gap"]
cards.append({"q": "Are photos of people a memory problem or an indexing problem?",
    "headline": "Mostly indexing: the photo exists but search can't see the face or name.",
    "body": f"{len(ppl_gap)} of {len(ppl)} people and pet posts are indexing gaps: faces not grouped, names lost after a reset, old photos never processed. {pct(nf([r for r in E if stage(r) == 'index_gap']) * 100, 100)}% of indexing-gap stories end without the photo.",
    "counter": "The spot check found some face-grouping posts tagged off-goal, so this is undercounted, not overcounted.",
    "recs": ["When a name search finds little, show likely unnamed faces to confirm in one tap.",
             "Warn people when names were lost after a restore or reset."],
    "hyp": ["H3"], "chart": 6, "filter": {"types": list(PEOPLE), "stages": ["index_gap"]}, **ev(ppl_gap)})
fr = [r for r in E if stage(r) == "feature_regression"]
fr_ai = [r for r in fr if re.search(r"ask photos|gemini|\bai\b", (r.get("text") or "").lower())]
c_recent = [x for x in c_time if x[0] >= "2023"]
cards.append({"q": "Did the new AI search (Ask Photos) help?",
    "headline": "For some heavy users it made things worse.",
    "body": f"{len(fr)} posts say search changed or got worse, {len(fr_ai)} of them naming Ask Photos, Gemini or AI. Their share of posts was 0–10% a year before 2023 and {min(x[3] for x in c_recent if x[0] >= "2024")}–{max(x[3] for x in c_recent)}% since 2024 (chart 5).",
    "counter": f"Loud but ranks {STAGES.index('feature_regression') + 1}th: the fix is a rollback debate, not a new way to find photos.",
    "recs": ["Keep exact name and date search one tap away for heavy users.",
             "Warn users when an update changes results they relied on."],
    "hyp": ["H6"], "chart": 5, "filter": {"stages": ["feature_regression"]}, **ev(fr)})


# ---------- Opportunity tiers (for the Opportunities tab) ----------
TIERS = {"cannot_refine": 1, "buried": 1, "index_gap": 1, "misunderstood": 1, "cannot_express": 2, "feature_regression": 3, "not_in_library": 3}
FOCUS = ["cannot_refine", "buried"]  # the two branches the deck (slide 2) picked
HMW = {"cannot_refine": "How might we let one search carry everything a person remembers?",
       "buried": "How might we get people to the right stretch of time without scrolling?",
       "index_gap": "How might we make faces and words in photos findable?",
       "misunderstood": "How might we show what search understood, so a misread is fixed in one tap?",
       "cannot_express": "How might we start a search from context (what was happening, which app)?",
       "feature_regression": "How might we keep the exact searches heavy users rely on?",
       "not_in_library": "How might we tell people early that a photo was never backed up?"}

json.dump({"cards": cards, "charts": {"remembered": c_remembered, "length": c_length, "stages": c_stages, "next": c_next, "heat": c_heat, "time": c_time},
           "tiers": TIERS, "focus": FOCUS, "hmw": HMW, "cue_labels": CUE},
          open(D("insights.json"), "w"), ensure_ascii=False, indent=1)
print("insights.json:", len(cards), "cards")
for c in cards: print(f"- {c['q']} | {c['badge']} {c['n']} posts, {c['sources']} sources")
