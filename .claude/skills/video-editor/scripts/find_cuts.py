#!/usr/bin/env python3
"""Find retakes and long pauses in a Whisper word-timestamp JSON.

Usage: find_cuts.py audio.json [--max-pause 0.5] [--pad 0.08] [--out edl.json]

Writes an edit decision list: {"keep": [[start, end], ...], "removed": [...]}
and prints a numbered transcript with retake flags for human/agent review.
"""
import argparse, json, re

REDO_PHRASES = [
    r"let'?s redo( that| this)?", r"redo that", r"let me (start|try) (that )?(over|again)",
    r"start (that )?over", r"take two", r"one more time", r"scratch that", r"let me redo",
    r"from the top", r"try that again", r"cut that", r"sorry,? let me",
]
REDO_RE = re.compile(r"\b(" + "|".join(REDO_PHRASES) + r")\b", re.I)


def norm(w):
    return re.sub(r"[^a-z0-9']", "", w.lower())


def load_words(path):
    data = json.load(open(path))
    segs = []
    for s in data.get("segments", []):
        words = [
            {"w": w["word"].strip(), "s": float(w["start"]), "e": float(w["end"])}
            for w in s.get("words", []) if w["word"].strip()
        ]
        if words:
            segs.append({"text": s["text"].strip(), "words": words})
    return segs, data


def split_sentences(segs, gap=0.9):
    """Re-split into sentence-ish units on punctuation or long gaps."""
    units, cur = [], []
    allw = [w for s in segs for w in s["words"]]
    for i, w in enumerate(allw):
        cur.append(w)
        nxt = allw[i + 1] if i + 1 < len(allw) else None
        end_punct = w["w"][-1:] in ".?!"
        long_gap = nxt is not None and nxt["s"] - w["e"] > gap
        if nxt is None or end_punct or long_gap:
            units.append(cur)
            cur = []
    return units


def text(u):
    return " ".join(w["w"] for w in u)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json")
    ap.add_argument("--max-pause", type=float, default=0.5)
    ap.add_argument("--pad", type=float, default=0.08, help="seconds kept before/after speech at a cut")
    ap.add_argument("--out", default="edl.json")
    a = ap.parse_args()

    segs, data = load_words(a.json)
    units = split_sentences(segs)
    drop = set()
    reasons = {}

    for i, u in enumerate(units):
        t = text(u)
        # explicit "let's redo that" etc.: drop this unit, and the previous one (the bad take)
        if REDO_RE.search(t):
            drop.add(i); reasons[i] = "redo cue"
            if i > 0 and (i - 1) not in drop:
                drop.add(i - 1); reasons[i - 1] = "take before redo cue"
        # restarted sentence: same first 3 words as a later unit nearby -> earlier is a false start
        k = [norm(w["w"]) for w in u[:3]]
        for j in range(i + 1, min(i + 4, len(units))):
            kj = [norm(w["w"]) for w in units[j][:3]]
            if len(k) >= 2 and k[:min(3, len(k))] == kj[:min(3, len(k))]:
                drop.add(i); reasons[i] = f"restarted later (#{j})"
                break
        # very short fragment ending without punctuation immediately before a new start
        if len(u) <= 3 and u[-1]["w"][-1:] not in ".?!" and i + 1 < len(units) and i not in drop:
            reasons.setdefault(i, "possible false start (check)")

    print("=== Transcript (X = will be cut, ? = check) ===")
    for i, u in enumerate(units):
        mark = "X" if i in drop else ("?" if i in reasons else " ")
        r = f"   <- {reasons[i]}" if i in reasons else ""
        print(f"[{mark}] #{i:<3} {u[0]['s']:7.2f}-{u[-1]['e']:7.2f}  {text(u)}{r}")

    # Build keep ranges from kept words, cutting any gap > max_pause
    kept = [w for i, u in enumerate(units) if i not in drop for w in u]
    keep = []  # [start, end_of_last_word]
    for w in kept:
        if keep and w["s"] - keep[-1][1] <= a.max_pause:
            keep[-1][1] = w["e"]          # short pause: keep it as natural rhythm
        else:
            keep.append([w["s"], w["e"]])  # pause > max_pause (or a removed retake): cut
    keep = [[round(max(0.0, s - a.pad), 3), round(e + a.pad, 3)] for s, e in keep]
    # merge overlaps from padding
    merged = []
    for s, e in keep:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])

    total_in = units[-1][-1]["e"] if units else 0
    total_out = sum(e - s for s, e in merged)
    json.dump({"keep": merged,
               "removed_units": [{"id": i, "text": text(units[i]), "reason": reasons.get(i)} for i in sorted(drop)]},
              open(a.out, "w"), indent=1)
    print(f"\nKept {len(merged)} ranges; speech span {total_in:.1f}s -> {total_out:.1f}s. "
          f"Dropped {len(drop)} retake units. Wrote {a.out}")


if __name__ == "__main__":
    main()
