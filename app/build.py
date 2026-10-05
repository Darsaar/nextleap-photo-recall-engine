"""Inline engine.json, evidence.json, story.json and meta into template.html -> dist/index.html (one static file)."""
import json, os
H = os.path.dirname(__file__); D = os.path.join(H, "..", "data")
t = open(os.path.join(H, "template.html")).read()
j = lambda p: json.dumps(json.load(open(p)), ensure_ascii=False).replace("</", "<\\/")
t = (t.replace("/*__ENGINE__*/null", j(os.path.join(D, "engine.json")))
      .replace("/*__EVIDENCE__*/[]", j(os.path.join(D, "evidence.json")))
      .replace("/*__STORY__*/{}", j(os.path.join(H, "story.json")))
      .replace("/*__META__*/{}", j(os.path.join(H, "meta.json"))))
os.makedirs(os.path.join(H, "dist"), exist_ok=True)
open(os.path.join(H, "dist", "index.html"), "w").write(t)
print("dist/index.html", round(len(t) / 1e6, 2), "MB")
