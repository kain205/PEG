"""Step 17 -- Build a frame folder in FastLabeler's *timeline* order for a display range.

FastLabeler Local v4.5 (video mode, ``frame_mode: timestamp_cfr``) indexes frames by
timestamp, not by decode order::

    index(frame) = floor((pts - start_pts) * time_base * fps + 0.5)

and timeline slot t shows the LAST decoded frame whose index <= t (duplicates: later one
wins; gaps: previous frame is held).  Camera streams drift (here 1 ms short every ~750
frames), so decode order n and timeline index t diverge (n - t grows to 98 by the end).

This script reads packet pts with ffprobe, computes t -> n, and materialises
``<out>/images/frame_%06d.jpg`` (local i = t - (lo - 1), i.e. display frame lo + i) as
NTFS hard links to an existing decode-order folder (``--decode_dir`` whose frame_000000
is decode index ``--decode_start``); decoded frames not present there are extracted with
cv2 (seek + verified against neighbouring existing jpgs).  Writes ``timeline_map.csv``.
"""
import argparse
import csv
import json
import math
import os
import subprocess
import sys

import cv2
import numpy as np


def packet_pts(video):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "packet=pts", "-of", "csv=p=0", video], capture_output=True, text=True, check=True)
    pts = [int(l.split(",")[0]) for l in out.stdout.splitlines() if l.strip()]
    tb = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                         "stream=time_base,start_pts,r_frame_rate", "-of", "json", video],
                        capture_output=True, text=True, check=True)
    st = json.loads(tb.stdout)["streams"][0]
    num, den = st["time_base"].split("/")
    fn, fd = st["r_frame_rate"].split("/")
    return np.array(pts, np.int64), int(st["start_pts"]), float(num) / float(den), float(fn) / float(fd)


def timeline_index(pts, origin, time_base, fps):
    return np.array([math.floor(float((p - origin) * time_base) * fps + .5) for p in pts], np.int64)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--lo", type=int, required=True, help="first display frame (1-based)")
    ap.add_argument("--hi", type=int, required=True, help="last display frame (1-based)")
    ap.add_argument("--decode_dir", required=True, help="images folder in decode order")
    ap.add_argument("--decode_start", type=int, required=True, help="decode index n of frame_000000 there")
    ap.add_argument("--out", required=True)
    ap.add_argument("--count", type=int, default=None, help="expected timeline length (app count)")
    args = ap.parse_args()

    pts, origin, tb, fps = packet_pts(args.video)
    assert np.all(np.diff(pts) > 0), "pts not monotonic: decode order != presentation order"
    idx = timeline_index(pts, origin, tb, fps)
    n_dec, n_slots = len(pts), int(idx.max()) + 1
    print(f"decoded={n_dec} timeline_slots={n_slots} fps={fps} time_base={tb}")
    if args.count is not None and args.count != n_slots:
        print(f"WARNING: app count {args.count} != slots {n_slots}")
    # slot t -> last decoded n with idx[n] <= t
    last_le = np.searchsorted(idx, np.arange(n_slots), side="right") - 1
    kind = np.full(n_slots, "exact", dtype=object)
    u, c = np.unique(idx, return_counts=True)
    dup_slots = set(u[c > 1].tolist())
    present = set(u.tolist())
    for t in range(n_slots):
        if t not in present:
            kind[t] = "hold"
        elif t in dup_slots:
            kind[t] = "dup"

    os.makedirs(os.path.join(args.out, "images"), exist_ok=True)
    rows, missing = [], {}
    for t in range(args.lo - 1, args.hi):
        n = int(last_le[t])
        local = t - (args.lo - 1)
        dst = os.path.join(args.out, "images", f"frame_{local:06d}.jpg")
        src_i = n - args.decode_start
        src = os.path.join(args.decode_dir, f"frame_{src_i:06d}.jpg") if src_i >= 0 else None
        rows.append((t + 1, t, n, int(pts[n]), kind[t], os.path.basename(dst)))
        if os.path.exists(dst):
            continue
        if src and os.path.exists(src):
            os.link(src, dst)
        else:
            missing.setdefault(n, []).append(dst)
    print(f"linked {len(rows) - sum(len(v) for v in missing.values())}, missing decoded frames: "
          f"{len(missing)} (n {min(missing) if missing else '-'}..{max(missing) if missing else '-'})")

    if missing:
        # ffmpeg with -copyts keeps absolute pts, so select by t = pts*time_base; seek a few
        # seconds earlier so the decoder has recovered (frames before the window are dropped).
        # Also pull 10 preceding frames that already exist in decode_dir to verify alignment.
        import shutil, tempfile
        n0, n1 = min(missing) - 10, max(missing)
        t1 = float(pts[n0] * tb) - 0.0005
        t2 = float(pts[n1] * tb) + 0.0005
        ss = max(0.0, float((pts[n0] - origin) * tb) - 3.0)
        tmp = tempfile.mkdtemp(prefix="tl_", dir=args.out)
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{ss:.6f}", "-copyts",
                        "-i", args.video, "-vf", f"select='between(t,{t1:.6f},{t2:.6f})'",
                        "-fps_mode", "passthrough", "-q:v", "2", "-start_number", str(n0),
                        os.path.join(tmp, "n_%06d.jpg")], check=True)
        got = sorted(os.listdir(tmp))
        assert len(got) == n1 - n0 + 1, f"expected {n1 - n0 + 1} frames, got {len(got)}"
        verified = 0
        for n in range(n0, n1 + 1):
            f = os.path.join(tmp, f"n_{n:06d}.jpg")
            src = os.path.join(args.decode_dir, f"frame_{n - args.decode_start:06d}.jpg")
            if os.path.exists(src):
                ref, cur = cv2.imread(src), cv2.imread(f)
                mad = float(np.abs(ref.astype(np.int16) - cur.astype(np.int16)).mean())
                assert mad < 3.0, f"pts extraction misaligned at n={n}: MAD {mad:.2f}"
                verified += 1
            if n in missing:
                shutil.move(f, missing[n][0])
                for dst in missing[n][1:]:
                    os.link(missing[n][0], dst)
                del missing[n]
        shutil.rmtree(tmp)
        print(f"extracted {n1 - n0 + 1 - verified} frames via ffmpeg pts-select "
              f"(alignment verified on {verified} existing frames); left: {len(missing)}")
        assert not missing

    with open(os.path.join(args.out, "timeline_map.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["display", "slot", "decode_n", "pts", "kind", "file"])
        w.writerows(rows)
    kinds = {k: sum(1 for r in rows if r[4] == k) for k in ("exact", "dup", "hold")}
    print(f"range display {args.lo}-{args.hi}: {len(rows)} slots, {kinds}; "
          f"n offset {rows[0][2] - rows[0][1]} .. {rows[-1][2] - rows[-1][1]}")
    n_files = len([f for f in os.listdir(os.path.join(args.out, "images")) if f.endswith(".jpg")])
    print(f"{n_files} jpgs in {os.path.join(args.out, 'images')}")


if __name__ == "__main__":
    main()
