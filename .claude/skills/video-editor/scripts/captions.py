#!/usr/bin/env python3
"""Make brand-styled, word-highlighted ASS captions from a Whisper word-timestamp JSON.

Usage: captions.py words.json out.ass [--width 1080 --height 1920] [--words 3]
       [--font Montserrat] [--main 0B1F3A] [--accent FF6B4A] [--upper]
Burn in: ffmpeg -i in.mp4 -vf "ass=out.ass:fontsdir=<skill>/brand/fonts" ...
"""
import argparse, json


def ass_color(hexrgb, alpha="00"):
    h = hexrgb.lstrip("#")
    return f"&H{alpha}{h[4:6]}{h[2:4]}{h[0:2]}".upper()


def ts(t):
    t = max(0, t)
    h, m = int(t // 3600), int(t % 3600 // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


ap = argparse.ArgumentParser()
ap.add_argument("json"); ap.add_argument("out")
ap.add_argument("--width", type=int, default=1080)
ap.add_argument("--height", type=int, default=1920)
ap.add_argument("--words", type=int, default=3, help="max words per caption")
ap.add_argument("--font", default="Montserrat ExtraBold")
ap.add_argument("--main", default="0B1F3A", help="outline/shadow color (brand color 1)")
ap.add_argument("--accent", default="FF6B4A", help="active-word color (brand color 2)")
ap.add_argument("--text", default="FFFFFF")
ap.add_argument("--no-upper", action="store_true")
a = ap.parse_args()

W, H = a.width, a.height
vertical = H > W
size = round(W * (0.085 if vertical else 0.048))
margin_v = round(H * (0.38 if vertical else 0.08))
outline = max(3, round(size * 0.09))
shadow = max(2, round(size * 0.06))

words = []
for s in json.load(open(a.json)).get("segments", []):
    for w in s.get("words", []):
        if w["word"].strip():
            words.append({"w": w["word"].strip(), "s": float(w["start"]), "e": float(w["end"])})

# group into short chunks; break on punctuation, long gaps, or max words
chunks, cur = [], []
for i, w in enumerate(words):
    cur.append(w)
    nxt = words[i + 1] if i + 1 < len(words) else None
    if (len(cur) >= a.words or w["w"][-1:] in ".?!," or nxt is None or nxt["s"] - w["e"] > 0.6):
        chunks.append(cur); cur = []

head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{a.font},{size},{ass_color(a.text)},{ass_color(a.accent)},{ass_color(a.main)},{ass_color(a.main, '60')},0,0,0,0,100,100,1,0,1,{outline},{shadow},2,{round(W*0.08)},{round(W*0.08)},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

lines = []
for ci, c in enumerate(chunks):
    start = c[0]["s"]
    end = c[-1]["e"] + 0.15
    if ci + 1 < len(chunks):
        end = min(end, chunks[ci + 1][0]["s"])
    for wi, w in enumerate(c):
        ws = w["s"] if wi else start
        we = c[wi + 1]["s"] if wi + 1 < len(c) else end
        if we <= ws:
            continue
        parts = []
        for k, x in enumerate(c):
            t = x["w"] if a.no_upper else x["w"].upper()
            t = t.replace("{", "(").replace("}", ")")
            if k == wi:
                parts.append(f"{{\\c{ass_color(a.accent)}\\fscx106\\fscy106}}{t}{{\\c{ass_color(a.text)}\\fscx100\\fscy100}}")
            else:
                parts.append(t)
        pop = "{\\fad(60,0)}" if wi == 0 else ""
        lines.append(f"Dialogue: 0,{ts(ws)},{ts(we)},Cap,,0,0,0,,{pop}{' '.join(parts)}")

open(a.out, "w").write(head + "\n".join(lines) + "\n")
print(f"Wrote {a.out}: {len(chunks)} captions, {len(words)} words, font {a.font} {size}px")
