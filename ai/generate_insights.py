"""
generate_insights.py — GenAI narrative layer (optional, LLM-powered).

Turns the model metrics + headline numbers into a plain-language executive
narrative. If an Anthropic API key is available it uses Claude to write the
narrative; otherwise it falls back to the deterministic insights already
produced by ml/build_ai.py — so the pipeline always yields output.

    pip install anthropic          # only needed for the LLM path
    setx ANTHROPIC_API_KEY "sk-..."   (Windows)  / export on *nix
    python ai/generate_insights.py

Writes ai/ai_narrative.md. This demonstrates LLM/GenAI integration (RAG-style:
the model's own metrics are the retrieved context) with a safe offline fallback.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
METRICS = os.path.join(ROOT, "ml", "model_metrics.json")
OUT = os.path.join(HERE, "ai_narrative.md")

CONTEXT = {}
if os.path.exists(METRICS):
    with open(METRICS, encoding="utf-8") as f:
        CONTEXT["model_metrics"] = json.load(f)

PROMPT = (
    "You are a senior data analyst writing the executive summary of a dashboard.\n"
    "Using ONLY the JSON metrics below, write 4-5 tight bullet points and a one-line "
    "recommendation. Be concrete, cite the numbers, and avoid hype.\n\n"
    f"METRICS:\n{json.dumps(CONTEXT, indent=2)}\n"
)


def with_claude():
    import anthropic  # noqa
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        messages=[{"role": "user", "content": PROMPT}],
    )
    return msg.content[0].text


def fallback():
    ai_js = os.path.join(ROOT, "dashboard", "ai.js")
    if os.path.exists(ai_js):
        raw = open(ai_js, encoding="utf-8").read()
        raw = raw[raw.index("{"): raw.rindex("}") + 1]
        data = json.loads(raw)
        lines = [f"- {i['text']}" for i in data.get("insights", [])]
        rec = data.get("recommendation", "")
        return "\n".join(lines) + (f"\n\n**Recommended action:** {rec}" if rec else "")
    return "- (run ml/build_ai.py first to generate model metrics)"


def main():
    used_llm = False
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            body = with_claude()
            used_llm = True
        except Exception as e:
            print(f"LLM path failed ({e}); using deterministic fallback.")
            body = fallback()
    else:
        print("No ANTHROPIC_API_KEY set — using deterministic insight engine (offline).")
        body = fallback()

    header = ("# AI-generated executive narrative\n\n"
              f"_Source: {'Claude (claude-haiku-4-5)' if used_llm else 'deterministic insight engine'} "
              "over the model metrics in `ml/model_metrics.json`._\n\n")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(header + body + "\n")
    print(f"wrote {os.path.relpath(OUT, ROOT)} ({'LLM' if used_llm else 'offline'})")


if __name__ == "__main__":
    main()
