"""App Store reviews for Google Photos via Apple's public customer-reviews RSS (XML feed; JSON feed is flaky).
Max 10 pages x 50 reviews per country per sort order."""
import requests, xml.etree.ElementTree as ET
from common import record, write_jsonl, get

APP_ID = "962194608"
NS = {"a": "http://www.w3.org/2005/Atom", "im": "http://itunes.apple.com/rss"}
s = requests.Session(); s.headers["User-Agent"] = "Mozilla/5.0"
rows = []
for cc in ["us", "in", "gb", "ca", "au", "sg", "ie", "nz", "ph", "za"]:
    for sort in ["mostrecent", "mosthelpful"]:
        for page in range(1, 11):
            r = get(s, f"https://itunes.apple.com/{cc}/rss/customerreviews/page={page}/id={APP_ID}/sortby={sort}/xml")
            if not r: break
            try: root = ET.fromstring(r.content)
            except ET.ParseError: break
            entries = [e for e in root.findall("a:entry", NS) if e.find("im:rating", NS) is not None]
            if not entries: break
            for e in entries:
                content = next((c.text for c in e.findall("a:content", NS) if c.get("type") == "text"), "")
                rows.append(record("app_store", e.findtext("a:id", "", NS), content,
                    url=f"https://apps.apple.com/{cc}/app/id{APP_ID}?see-all=reviews",
                    date=e.findtext("a:updated", "", NS), title=e.findtext("a:title", "", NS),
                    rating=int(e.findtext("im:rating", "0", NS)), meta={"country": cc}))
        print(cc, sort, len(rows), flush=True)
write_jsonl("app_store", rows)
