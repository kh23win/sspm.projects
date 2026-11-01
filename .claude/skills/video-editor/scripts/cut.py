#!/usr/bin/env python3
"""Render the keep-ranges of an EDL into one clip (frame accurate, high quality).

Usage: cut.py source.mp4 edl.json out.mp4 [--crf 16]
"""
import argparse, json, subprocess

ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("edl"); ap.add_argument("out")
ap.add_argument("--crf", default="16")
ap.add_argument("--fade", type=float, default=0.012, help="audio micro-fade at each cut (s)")
a = ap.parse_args()

keep = json.load(open(a.edl))["keep"]
f = a.fade
parts, labels = [], ""
for i, (s, e) in enumerate(keep):
    d = e - s
    parts.append(f"[0:v]trim=start={s}:end={e},setpts=PTS-STARTPTS[v{i}]")
    parts.append(f"[0:a]atrim=start={s}:end={e},asetpts=PTS-STARTPTS,"
                 f"afade=t=in:d={f},afade=t=out:st={max(0, d - f):.3f}:d={f}[a{i}]")
    labels += f"[v{i}][a{i}]"
parts.append(f"{labels}concat=n={len(keep)}:v=1:a=1[v][a]")

cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", a.src,
       "-filter_complex", ";".join(parts), "-map", "[v]", "-map", "[a]",
       "-c:v", "libx264", "-preset", "slow", "-crf", a.crf, "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-movflags", "+faststart", a.out]
subprocess.run(cmd, check=True)
print(f"Wrote {a.out} ({len(keep)} segments, {sum(e - s for s, e in keep):.2f}s)")
