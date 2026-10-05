// Vercel serverless function: short AI answer for the Ask tab, grounded in the posts the page sends.
// Needs GEMINI_API_KEY in the Vercel project's environment variables.
const MODELS = (process.env.GEMINI_MODELS || "gemini-3.5-flash-lite,gemini-3.5-flash,gemini-flash-lite-latest,gemini-3.1-flash-lite,gemini-flash-latest").split(",");

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ text: "" });
  const key = process.env.GEMINI_API_KEY;
  const prompt = String((req.body && req.body.prompt) || "").slice(0, 12000);
  if (!key || !prompt) return res.status(200).json({ text: "" });
  // Free-tier models hit daily quotas (429) and demand spikes (503): try each model twice, then the next one.
  for (const model of MODELS.flatMap(m => [m, m])) {
    try {
      const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`, {
        method: "POST",
        headers: { "content-type": "application/json", "x-goog-api-key": key },
        body: JSON.stringify({ contents: [{ parts: [{ text: prompt }] }], generationConfig: { temperature: 0.2, maxOutputTokens: 1200, thinkingConfig: { thinkingBudget: 0 } } }),
      });
      if (!r.ok) continue;
      const j = await r.json();
      const text = j?.candidates?.[0]?.content?.parts?.map(p => p.text || "").join("") || "";
      if (text) return res.status(200).json({ text: text.replace(/\*\*/g, "") });
    } catch (e) {}
  }
  return res.status(200).json({ text: "" });
}
