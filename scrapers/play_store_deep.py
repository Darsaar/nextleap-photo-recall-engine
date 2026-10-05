"""Deeper Play Store pull: newest-first pagination for one locale until N reviews (the default run caps each sort at ~5k)."""
import sys
from google_play_scraper import reviews, Sort
from common import record, write_jsonl
APP = "com.google.android.apps.photos"; N = int(sys.argv[1]) if len(sys.argv) > 1 else 60000
rows, token = [], None
while len(rows) < N:
    batch, token = reviews(APP, lang="en", country="us", sort=Sort.NEWEST, count=200, continuation_token=token)
    if not batch: break
    for b in batch:
        rows.append(record("play_store", b["reviewId"], b["content"],
            url=f"https://play.google.com/store/apps/details?id={APP}&reviewId={b['reviewId']}", date=b["at"], rating=b["score"],
            meta={"country": "us", "thumbs_up": b.get("thumbsUpCount", 0), "app_version": b.get("appVersion")}))
    if len(rows) % 5000 < 200: print(len(rows), rows[-1]["date"], flush=True)
    if token is None: break
write_jsonl("play_store_deep", rows)
