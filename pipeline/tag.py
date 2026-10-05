"""Stage 3: LLM structured extraction. Each candidate post gets the fields below.
Works with Gemini (GEMINI_API_KEY) or Claude (ANTHROPIC_API_KEY). Resumable: already-tagged ids are skipped.
Usage: python tag.py [--limit N] [--batch 8] [--workers 4]"""
import argparse, json, os, re, sys, time, requests
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.join(os.path.dirname(__file__), "..")
IN, OUT = os.path.join(ROOT, "data/clean/candidates.jsonl"), os.path.join(ROOT, "data/tagged/tagged.jsonl")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

SCHEMA_DOC = """
For EACH post return one JSON object with exactly these keys:
- id: copy the post id
- relevance: "retrieval_story" (the writer, or someone they describe, tried to find/retrieve a specific existing photo/video/screenshot),
             "search_feedback" (opinion or request about search/finding features without a specific retrieval attempt),
             "off_goal" (storage, backup, pricing, editing, crashes, deletion/recovery of lost data not about finding), or "noise"
- content_type: one of trip_place, event_occasion, person, pet, child_family, screenshot_info, document_id, receipt_bill, medical,
                product_shopping, food, text_in_image, video, old_scanned, other, unknown
- cues_remembered: list from [rough_time, exact_date, place, person, object, text_in_image, event_context, life_context
                   (what was happening in their life), visual_look (colour/scene), source_app (WhatsApp/screenshot/camera), why_taken, device, none]
- cues_forgotten: list from [date, place, album_folder, what_to_type, who_sent, which_account_device, filename, none_stated]
- query_typed: the exact search words the user says they typed, quoted verbatim, else ""
- failure_stage: one of
    cannot_express   (user cannot turn the memory into a query the app accepts)
    misunderstood    (search returns wrong things / ignores words / no results for something that exists)
    buried           (right photo is somewhere in too many results or the timeline; endless scrolling)
    cannot_refine    (no way to combine or narrow cues: date+place, person+object, exclude, sort)
    index_gap        (photo not searchable: faces not grouped, text/OCR not indexed, location missing, metadata wrong)
    feature_regression (search/Ask Photos changed or got worse, feature removed)
    not_in_library   (photo truly missing/not backed up/deleted)
    none             (no failure / not applicable)
- workaround: one of scroll_timeline, map_or_places, people_tab, albums_folders, date_jump, other_app (WhatsApp/Drive/Gallery),
              ask_someone, third_party_tool, gave_up, none_stated
- outcome: found, found_with_effort, not_found, unknown
- severity: 1-3 (3 = emotionally important or urgent, e.g. medical, ID, deceased relative, legal)
- user_need: one short sentence in plain words, what the user wanted the product to do
- quote: the single most telling sentence from the post, verbatim (<= 35 words)
- segment_signal: list from [large_library, heavy_screenshots, uses_as_document_store, parent, traveller, professional, older_user, android, ios, web]
Return ONLY a JSON array, one object per post, same order. No commentary.
"""
PROMPT = ("You are a UX researcher analysing public feedback about Google Photos to understand how people retrieve "
          "vaguely remembered photos. Be literal: only tag what the text supports." + SCHEMA_DOC)

def call_llm(text):
    if os.getenv("GEMINI_API_KEY"):
        # Try models in order; free-tier models hit 503 (demand) or 429 (quota) and the next one usually answers.
        models = os.getenv("GEMINI_MODELS", "gemini-3.5-flash-lite,gemini-flash-lite-latest,gemini-3.1-flash-lite,gemini-flash-latest").split(",")
        last = None
        for model in models:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]}, timeout=180,
                json={"contents": [{"parts": [{"text": text}]}], "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}})
            if r.status_code in (429, 500, 503):
                last = f"{model} {r.status_code}"; continue
            r.raise_for_status(); return r.json()["candidates"][0]["content"]["parts"][0]["text"], model
        raise RuntimeError("all models busy: " + str(last))
    if os.getenv("ANTHROPIC_API_KEY"):
        model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
        r = requests.post("https://api.anthropic.com/v1/messages", timeout=180,
            headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"},
            json={"model": model, "max_tokens": 8000, "temperature": 0, "messages": [{"role": "user", "content": text}]})
        r.raise_for_status(); return r.json()["content"][0]["text"], model
    sys.exit("Set GEMINI_API_KEY or ANTHROPIC_API_KEY")

def tag_batch(batch):
    posts = "\n\n".join(f"### id: {p['id']} | source: {p['source']}\n{p['full_text'][:2500]}" for p in batch)
    for attempt in range(4):
        try:
            raw, model = call_llm(PROMPT + "\n\nPOSTS:\n" + posts)
            arr = json.loads(re.search(r"\[.*\]", raw, re.S).group(0))
            byid = {a.get("id"): a for a in arr}
            return [dict(byid[p["id"]], _model=model) for p in batch if p["id"] in byid]
        except Exception as e:
            msg = str(e).split("?")[0]  # never log URLs with query strings
            print("retry", attempt, type(e).__name__, msg[:200], flush=True); time.sleep(5 * (attempt + 1))
    return []

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--batch", type=int, default=8); ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    done = {json.loads(l)["id"] for l in open(OUT)} if os.path.exists(OUT) else set()
    todo = [json.loads(l) for l in open(IN)]; todo = [p for p in todo if p["id"] not in done]
    # Richest sources and longest posts first, so a partial run still covers the best evidence.
    rank = {"help_forum": 0, "reddit": 1, "stack_exchange": 2, "hacker_news": 3, "youtube": 4, "app_store": 5, "play_store": 6}
    todo.sort(key=lambda p: (rank.get(p["source"], 9), -p["words"]))
    if a.limit: todo = todo[:a.limit]
    batches = [todo[i:i + a.batch] for i in range(0, len(todo), a.batch)]
    print(f"{len(done)} already tagged, {len(todo)} to tag in {len(batches)} batches", flush=True)
    with open(OUT, "a") as f, ThreadPoolExecutor(a.workers) as ex:
        for i, res in enumerate(ex.map(tag_batch, batches)):
            for t in res: f.write(json.dumps(t, ensure_ascii=False) + "\n")
            f.flush()
            if i % 10 == 0: print("batch", i, "/", len(batches), flush=True)
