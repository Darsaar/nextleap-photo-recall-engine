"""YouTube comments via the YouTube Data API v3 (needs YOUTUBE_API_KEY; plain scraping is blocked from the build environment)."""
import os, requests, sys
from common import record, write_jsonl, get

KEY = os.getenv("YOUTUBE_API_KEY") or sys.exit("Set YOUTUBE_API_KEY")
QUERIES = ["google photos search tips", "google photos ask photos", "find old photos google photos", "google photos search not working",
           "google photos hidden features", "ask photos gemini", "how to find a photo in google photos", "google photos tips and tricks",
           "google photos vs apple photos search", "google photos search people pets", "google photos search text screenshots",
           "google photos organize memories"]
s = requests.Session(); rows = []; vids = {}
for q in QUERIES:
    r = get(s, "https://www.googleapis.com/youtube/v3/search", params={"key": KEY, "part": "snippet", "q": q,
            "type": "video", "maxResults": 25, "relevanceLanguage": "en"})
    for it in (r.json().get("items", []) if r else []):
        vids[it["id"]["videoId"]] = it["snippet"]["title"]
print("videos", len(vids), flush=True)
for vid, title in vids.items():
    page = None
    for _ in range(8):
        p = {"key": KEY, "part": "snippet", "videoId": vid, "maxResults": 100, "order": "relevance", "textFormat": "plainText"}
        if page: p["pageToken"] = page
        r = get(s, "https://www.googleapis.com/youtube/v3/commentThreads", params=p)
        if not r or r.status_code != 200: break
        j = r.json()
        for it in j.get("items", []):
            sn = it["snippet"]["topLevelComment"]["snippet"]
            rows.append(record("youtube", it["id"], sn["textDisplay"],
                url=f"https://www.youtube.com/watch?v={vid}&lc={it['id']}", date=sn.get("publishedAt", "")[:10],
                meta={"video_id": vid, "video_title": title, "likes": sn.get("likeCount"), "replies": it["snippet"].get("totalReplyCount")}))
        page = j.get("nextPageToken")
        if not page: break
    print(vid, len(rows), flush=True)
write_jsonl("youtube", rows)
