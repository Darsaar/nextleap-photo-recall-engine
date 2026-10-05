"""Google Play reviews for Google Photos (several countries), newest first."""
import sys
from google_play_scraper import reviews, Sort
from common import record, write_jsonl

APP = "com.google.android.apps.photos"
TARGET = int(sys.argv[1]) if len(sys.argv) > 1 else 20000

rows = []
for country in ["in", "us", "gb"]:
    for sort in [Sort.NEWEST, Sort.MOST_RELEVANT]:
        token, got = None, 0
        while got < TARGET // 6:
            batch, token = reviews(APP, lang="en", country=country, sort=sort, count=200, continuation_token=token)
            if not batch:
                break
            got += len(batch)
            for b in batch:
                rows.append(record("play_store", b["reviewId"], b["content"], 
                    url=f"https://play.google.com/store/apps/details?id={APP}&reviewId={b['reviewId']}",
                    date=b["at"], rating=b["score"],
                    meta={"country": country, "thumbs_up": b.get("thumbsUpCount", 0), "app_version": b.get("appVersion")}))
            if token is None:
                break
        print(country, sort, got, flush=True)
write_jsonl("play_store", rows)
