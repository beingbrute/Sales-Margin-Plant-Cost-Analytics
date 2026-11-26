"""
Tags each sales field note with one theme using a local language model (Ollama), then checks the result.

    python src/tag_field_notes.py                    # tag every note (needs Ollama running with qwen3:4b)
    python src/tag_field_notes.py --retry            # ask again only for notes left Unclassified
    python src/tag_field_notes.py --score            # after you have filled in the hand-check sheet

Steps:
  1. Each distinct note text is sent once to the model with a fixed list of themes, temperature 0.
     Identical texts reuse the same answer.
  2. The model sometimes copies the theme's description too ("Competitor pricing: competitors' prices ...").
     Only the part before the first colon is compared with the list. Anything that still is not a theme
     name is recorded as "Unclassified", never guessed. Every raw answer is kept in
     data/derived/field_note_answers_raw.csv so the matching can be checked.
  3. Writes data/derived/field_note_themes_llm.csv (loaded into the database by src/load_data.py)
     and data/derived/field_notes_hand_check.csv: 40 notes for a person to mark Y (correct) or N.
  4. --score reports the model's accuracy from the hand-check, and against the generator's answer key
     (data/answer_key/field_note_themes.csv), with the themes it confuses most.
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "derived"
KEY = ROOT / "data" / "answer_key" / "field_note_themes.csv"
THEMES = ["Competitor pricing", "Delivery delays", "Discount pressure", "Product quality",
          "Demand and season", "Display and visibility", "Payment terms"]
PROMPT = """You classify notes written by sales staff after visiting a distributor or retailer of fans, wires,
water heaters and voltage stabilisers. Choose the ONE theme that best describes the main point of the note.

Themes:
- Competitor pricing: competitors' prices, schemes or models taking sales
- Delivery delays: late, short or pending deliveries, stock not available
- Discount pressure: requests for more discount or better schemes
- Product quality: faulty units, returns, complaints, service calls
- Demand and season: how strong demand is and why
- Display and visibility: display stands, shelf space, visibility in store
- Payment terms: credit days, delayed payments

Note: "{note}"

Reply with JSON only: {{"theme": "<one theme name from the list>"}} /no_think"""


def match_theme(answer):
    """Theme name from the model's answer, or Unclassified. Text after the first colon is ignored."""
    name = str(answer).split(":")[0].strip().strip('."').lower()
    match = [t for t in THEMES if t.lower() == name]
    return match[0] if match else "Unclassified"


def ask(model, note, url, timeout=180):
    """Returns (theme, raw answer)."""
    body = json.dumps({"model": model, "prompt": PROMPT.format(note=note.replace('"', "'")), "stream": False,
                       "format": "json", "think": False, "keep_alive": "30m",
                       "options": {"temperature": 0, "seed": 1, "num_predict": 128}}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        text = json.loads(r.read())["response"]
    text = text.split("</think>")[-1]                     # keep only what follows any reasoning text
    text = re.sub(r"<think>.*", "", text, flags=re.S).strip()
    try:
        answer = json.loads(text).get("theme", "")
    except (json.JSONDecodeError, AttributeError):
        answer = text
    return match_theme(answer), str(answer)


def tag(model, url, retry=False):
    notes = pd.read_csv(RAW / "field_notes.csv")
    texts = notes.note.drop_duplicates().tolist()
    raw_file = OUT / "field_note_answers_raw.csv"
    answers, raw = {}, {}
    if retry:
        done = pd.read_csv(OUT / "field_note_themes_llm.csv").merge(notes[["note_id", "note"]], on="note_id")
        answers = dict(zip(done.note, done.theme))
        if raw_file.exists():
            r = pd.read_csv(raw_file)
            raw = dict(zip(r.note, r.raw_answer))
        for t, th in answers.items():                 # notes matched on the first run: answer was the theme name
            raw.setdefault(t, th)
        texts = [t for t in texts if answers.get(t, "Unclassified") == "Unclassified"]
        print(f"Retrying {len(texts):,} distinct texts that were Unclassified. Model: {model}")
    else:
        print(f"{len(notes):,} notes, {len(texts):,} distinct texts. Model: {model}")
    print("Loading the model (the first answer can take a few minutes) ...")
    t0 = time.time()
    try:
        ask(model, texts[0], url, timeout=600)       # warm-up: loads the model into memory
    except urllib.error.URLError as e:
        sys.exit(f"Cannot reach Ollama at {url} ({e.reason}). Start Ollama and check `ollama list`.")
    except TimeoutError:
        sys.exit("Ollama did not answer within 10 minutes. Check the model runs: ollama run qwen3:4b \"hello /no_think\"")
    print(f"  model ready in {time.time() - t0:,.0f} s")
    start = time.time()
    for i, t in enumerate(texts, start=1):
        for attempt in (1, 2):                       # one retry if a single note times out
            try:
                answers[t], raw[t] = ask(model, t, url)
                break
            except TimeoutError:
                if attempt == 2:
                    answers[t], raw[t] = "Unclassified", "(timed out)"
            except urllib.error.URLError as e:
                sys.exit(f"Cannot reach Ollama at {url} ({e.reason}). Start Ollama and check `ollama list`.")
        if i == 5:
            per = (time.time() - start) / 5
            print(f"  about {per:.1f} s per note -> roughly {per * len(texts) / 60:.0f} minutes for all {len(texts)}")
        if i % 50 == 0 or i == len(texts):
            print(f"  {i:>4}/{len(texts)}  {time.time() - start:,.0f} s")
    notes["theme"] = notes.note.map(answers)
    notes["model"] = model
    OUT.mkdir(parents=True, exist_ok=True)
    notes[["note_id", "theme", "model"]].to_csv(OUT / "field_note_themes_llm.csv", index=False)
    pd.DataFrame({"note": list(raw), "raw_answer": list(raw.values()),
                  "theme": [answers.get(t, "Unclassified") for t in raw]}).to_csv(raw_file, index=False)
    check_file = OUT / "field_notes_hand_check.csv"
    if check_file.exists() and pd.read_csv(check_file, encoding="utf-8-sig").correct_Y_or_N.notna().any():
        print(f"Kept your marked hand-check sheet {check_file} (delete it to get a fresh one)")
    else:
        sample = notes.sample(40, random_state=7)[["note_id", "region", "note", "theme"]]
        sample["correct_Y_or_N"] = ""
        sample.to_csv(check_file, index=False, encoding="utf-8-sig")
    print(notes.theme.value_counts().to_string())
    print(f"Took {(time.time() - start) / 60:.1f} minutes")
    print(f"Saved {OUT / 'field_note_themes_llm.csv'}, {raw_file} and the hand-check sheet {check_file}")


def score():
    tagged = pd.read_csv(OUT / "field_note_themes_llm.csv")
    check = pd.read_csv(OUT / "field_notes_hand_check.csv", encoding="utf-8-sig")
    marked = check.correct_Y_or_N.astype(str).str.strip().str.upper().isin(["Y", "N"])
    if marked.sum() == 0:
        sys.exit("No rows marked yet: open data/derived/field_notes_hand_check.csv and put Y or N in correct_Y_or_N.")
    hand = (check.loc[marked, "correct_Y_or_N"].str.strip().str.upper() == "Y").mean()
    print(f"Hand-check: {marked.sum()} notes marked, {hand:.1%} judged correct")
    truth = pd.read_csv(KEY).merge(tagged, on="note_id")
    acc = (truth.theme_true == truth.theme).mean()
    print(f"Against the answer key: {acc:.1%} of {len(truth):,} notes correct")
    wrong = truth[truth.theme_true != truth.theme]
    if len(wrong):
        print("Most common confusions (true theme -> model's theme):")
        print(wrong.groupby(["theme_true", "theme"]).size().sort_values(ascending=False).head(6).to_string())
    by_theme = (truth.theme_true == truth.theme).groupby(truth.theme_true).mean()
    print("Accuracy by true theme:\n" + by_theme.map("{:.1%}".format).to_string())


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="qwen3:4b")
    p.add_argument("--url", default="http://localhost:11434/api/generate")
    p.add_argument("--score", action="store_true")
    p.add_argument("--retry", action="store_true", help="ask again only for notes left Unclassified")
    a = p.parse_args()
    score() if a.score else tag(a.model, a.url, retry=a.retry)
