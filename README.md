# Photo Recall Engine — AI discovery engine

Deliverable 1 of the NextLeap graduation case: **why can't people retrieve a photo they only half remember?**
It reads public feedback about Google Photos, extracts a structured retrieval story from each post with an LLM,
and ranks the retrieval problems so the survey and interviews can test the right ones.

Not a sentiment pass: nothing here asks whether a review is positive. Every post is broken down into
*what the person remembered, what they had forgotten, what they typed, where the search broke, and what they did instead*,
so different retrieval problems can be compared against each other.

## Pipeline

```
scrapers/                      pipeline/clean.py        pipeline/tag.py          pipeline/analyze.py      app/build.py
Play Store   ─┐
App Store     │   raw JSONL    normalise, dedupe,       LLM structured           score opportunities,     one static
Reddit        ├──────────────▶ language filter,  ──────▶ extraction per post ───▶ build cue gaps and ────▶ index.html
Help forum    │                retrieval prefilter      (Gemini or Claude)       the failure matrix
YouTube       │
HN / Stack Ex ┘
```

| Stage | Script | Output |
|---|---|---|
| 1. Collect | `scrapers/*.py` | `data/raw/<source>.jsonl` |
| 2. Clean + prefilter | `pipeline/clean.py` | `data/clean/corpus.jsonl`, `candidates.jsonl`, `funnel_stage2.json` |
| 3. Tag with an LLM | `pipeline/tag.py` | `data/tagged/tagged.jsonl` (resumable) |
| 4. Score + compare | `pipeline/analyze.py` | `data/engine.json`, `data/evidence.json` |
| 5. Build the app | `app/build.py` | `app/dist/index.html` |

## Sources and how each is reached

| Source | Method | Note |
|---|---|---|
| Google Play reviews | `google-play-scraper`, several countries and sort orders | highest volume, lowest story rate |
| App Store reviews | Apple's public customer-reviews RSS (XML), 10 pages per country per sort | small but useful |
| Reddit | Arctic Shift archive API (`arctic-shift.photon-reddit.com`) | reddit.com is blocked from the build environment |
| Google Photos Help Community | `support.google.com/photos/threads`, Searching / Face groups / Organization categories plus keyword filters; thread bodies decoded from the page's data blob | richest retrieval stories |
| YouTube comments | YouTube Data API v3 (`YOUTUBE_API_KEY`) | scraping is blocked from this environment |
| Hacker News, Stack Exchange | Algolia HN API, Stack Exchange API | adds power users and web/desktop context |

## What the LLM extracts per post

`relevance` (retrieval story / search feedback / off-goal / noise) · `content_type` · `cues_remembered` ·
`cues_forgotten` · `query_typed` (verbatim) · `failure_stage` · `workaround` · `outcome` · `severity` ·
`user_need` · `quote` · `segment_signal`. Schema and prompt: `pipeline/tag.py`.

`failure_stage` is the spine of the analysis and maps onto the case's metric decomposition:

| Stage | Meaning |
|---|---|
| `cannot_express` | can't turn the memory into a query |
| `misunderstood` | search misreads the words |
| `buried` | right photo lost among results or in the timeline |
| `cannot_refine` | no way to combine or narrow cues |
| `index_gap` | photo isn't searchable (faces, text, place not indexed) |
| `feature_regression` | search changed or got worse |
| `not_in_library` | photo is genuinely gone |

## Opportunity score

`√mentions × (0.5 + severity) × (0.5 + source spread) × addressability`

Every input is shown on the card, so a reader can disagree with the weighting. `addressability` is a judgement
about whether better retrieval could fix the cause at all: 1.0 for query and ranking problems, 0.2 for photos
that were never backed up.

## Run it

```bash
pip install -r requirements.txt
cd scrapers && python play_store.py && python app_store.py && python reddit.py && python help_forum.py
python forums.py && YOUTUBE_API_KEY=… python youtube.py          # YouTube optional
cd ../pipeline && python clean.py
GEMINI_API_KEY=…  python tag.py --limit 50     # checkpoint: eyeball 50 tagged posts first
GEMINI_API_KEY=…  python tag.py                # then the rest; re-running skips what's done
python analyze.py && cd ../app && python build.py
```

`ANTHROPIC_API_KEY` works in place of `GEMINI_API_KEY`. Keys are read from the environment and never stored in the repo.

## Honesty notes

- The corpus is self-selected: people who quietly give up on a search rarely post about it. The survey and
  interviews exist to cover that gap, and the app says so on the findings page.
- Counts describe this corpus, not all Google Photos users.
- No experiment results are claimed, and no metric is shown that wasn't computed from the data in `data/`.
