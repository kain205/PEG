"""Step 16 -- QA contact sheets for an auto-labelled frame range (no GT needed).

Reads the interpolated MOT gt (from step 15) + the frame jpgs and renders
  tracks   : one sheet per track: a row of crops along the track (first/last always) and
             4 full-frame thumbnails with every box; title = id, span, length, segments
  overview : one sheet per ``--block`` frames: 12 evenly spaced full frames, all boxes
  miss     : detections (step 14 --dets_out, conf >= --miss_conf) not covered by any box
             (IoU < 0.3) that persist >= --miss_len frames near one place -> one sheet each

Frame numbers everywhere are DISPLAY (1-based) numbers of the original video; the jpg
for frame F is ``images/frame_{F - start_display:06d}.jpg``.
"""
import argparse
import csv
import json
import os
import sys
from collections import defaultdict

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from glaremot.analysis.io import load_mot  # noqa: E402
from glaremot.analysis.render import _text, id_color  # noqa: E402

TILE_H = 260
FULL_W = 940
MAX_W = 1920


def frame_path(images, start, F):
    return os.path.join(images, f"frame_{F - start:06d}.jpg")


def draw_full(img, boxes, focus=None, scale=None):
    """boxes: [(id, x, y, w, h)]; returns resized copy with boxes + id labels."""
    H, W = img.shape[:2]
    s = scale or (FULL_W / float(W))
    out = cv2.resize(img, (int(W * s), int(H * s)))
    for tid, x, y, w, h in boxes:
        col = id_color(tid)
        th = 3 if focus is not None and tid == focus else 1
        p1, p2 = (int(x * s), int(y * s)), (int((x + w) * s), int((y + h) * s))
        cv2.rectangle(out, p1, p2, col, th)
        _text(out, str(tid), (p1[0], max(12, p1[1] - 4)), 0.45, col, 1)
    return out


def crop_tile(img, box, boxes, tid, pad=0.8, min_side=200):
    H, W = img.shape[:2]
    x, y, w, h = box
    cx, cy = x + w / 2, y + h / 2
    side = max(min_side, w * (1 + 2 * pad), h * (1 + 2 * pad))
    x1, y1 = int(max(0, cx - side / 2)), int(max(0, cy - side / 2))
    x2, y2 = int(min(W, cx + side / 2)), int(min(H, cy + side / 2))
    crop = img[y1:y2, x1:x2].copy()
    s = TILE_H / float(max(1, crop.shape[0]))
    crop = cv2.resize(crop, (max(1, int(crop.shape[1] * s)), TILE_H))
    for oid, ox, oy, ow, oh in boxes:
        col = id_color(oid)
        p1 = (int((ox - x1) * s), int((oy - y1) * s))
        p2 = (int((ox + ow - x1) * s), int((oy + oh - y1) * s))
        cv2.rectangle(crop, p1, p2, col, 2 if oid == tid else 1)
        if oid != tid:
            _text(crop, str(oid), (p1[0], max(12, p1[1] - 4)), 0.4, col, 1)
    return crop


def hstack_pad(tiles, gap=4):
    h = max(t.shape[0] for t in tiles)
    out = []
    for t in tiles:
        if t.shape[0] < h:
            t = cv2.copyMakeBorder(t, 0, h - t.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=(30, 30, 30))
        out.append(t)
        out.append(np.full((h, gap, 3), 30, np.uint8))
    return np.hstack(out[:-1])


def wrap_rows(tiles, max_w=MAX_W):
    rows, cur, w = [], [], 0
    for t in tiles:
        if cur and w + t.shape[1] > max_w:
            rows.append(hstack_pad(cur))
            cur, w = [], 0
        cur.append(t)
        w += t.shape[1] + 4
    if cur:
        rows.append(hstack_pad(cur))
    W = max(r.shape[1] for r in rows)
    rows = [cv2.copyMakeBorder(r, 0, 0, 0, W - r.shape[1], cv2.BORDER_CONSTANT, value=(30, 30, 30))
            for r in rows]
    return np.vstack(rows)


def title_bar(text, width):
    bar = np.full((28, width, 3), 20, np.uint8)
    _text(bar, text, (6, 20), 0.6, (255, 255, 255), 1)
    return bar


def pick(frames, n):
    if len(frames) <= n:
        return list(frames)
    idx = np.linspace(0, len(frames) - 1, n).round().astype(int)
    return [frames[i] for i in sorted(set(idx))]


def render_tracks(mot, images, start, out_dir, only=None, n_crops=16, segments=None):
    by_id = defaultdict(dict)
    for F, items in mot.items():
        for tid, x, y, w, h in items:
            by_id[tid][F] = (x, y, w, h)
    os.makedirs(out_dir, exist_ok=True)
    for tid in sorted(by_id):
        if only and tid not in only:
            continue
        frames = sorted(by_id[tid])
        crops = []
        for F in pick(frames, n_crops):
            img = cv2.imread(frame_path(images, start, F))
            if img is None:
                continue
            c = crop_tile(img, by_id[tid][F], mot[F], tid)
            _text(c, f"F{F}", (2, 16), 0.45, (255, 255, 255), 1)
            crops.append(c)
        fulls = []
        for F in pick(frames, 4):
            img = cv2.imread(frame_path(images, start, F))
            if img is None:
                continue
            f = draw_full(img, mot[F], focus=tid)
            _text(f, f"F{F}", (2, 16), 0.5, (255, 255, 255), 1)
            fulls.append(f)
        if not crops:
            continue
        body = wrap_rows(crops)
        full = wrap_rows(fulls) if fulls else None
        parts = [body] + ([full] if full is not None else [])
        W = max(p.shape[1] for p in parts)
        parts = [cv2.copyMakeBorder(p, 0, 0, 0, W - p.shape[1], cv2.BORDER_CONSTANT, value=(30, 30, 30))
                 for p in parts]
        seg = ""
        if segments and str(tid) in segments:
            seg = " segs=" + ",".join(f"{a}-{b}" for a, b in segments[str(tid)])
        sheet = np.vstack([title_bar(f"id {tid}  F{frames[0]}-F{frames[-1]}  n={len(frames)}{seg}", W)] + parts)
        cv2.imwrite(os.path.join(out_dir, f"track_{tid:03d}.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(f"tracks: {len(by_id)} -> {out_dir}")


def render_overview(mot, images, start, end, out_dir, block=500, n=12):
    os.makedirs(out_dir, exist_ok=True)
    for lo in range(start, end + 1, block):
        hi = min(end, lo + block - 1)
        tiles = []
        for F in pick(list(range(lo, hi + 1)), n):
            img = cv2.imread(frame_path(images, start, F))
            if img is None:
                continue
            t = draw_full(img, mot.get(F, []))
            ids = sorted({b[0] for b in mot.get(F, [])})
            _text(t, f"F{F} ids={ids}", (2, 16), 0.5, (255, 255, 255), 1)
            tiles.append(t)
        if not tiles:
            continue
        body = wrap_rows(tiles)
        sheet = np.vstack([title_bar(f"overview F{lo}-F{hi}", body.shape[1]), body])
        cv2.imwrite(os.path.join(out_dir, f"ov_{lo:06d}_{hi:06d}.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 80])
    print(f"overview -> {out_dir}")


def iou(a, b):
    ax1, ay1, ax2, ay2 = a[0], a[1], a[0] + a[2], a[1] + a[3]
    bx1, by1, bx2, by2 = b[0], b[1], b[0] + b[2], b[1] + b[3]
    iw, ih = max(0, min(ax2, bx2) - max(ax1, bx1)), max(0, min(ay2, by2) - max(ay1, by1))
    inter = iw * ih
    return inter / max(1e-6, a[2] * a[3] + b[2] * b[3] - inter)


def find_misses(mot, dets_csv, miss_conf, miss_len, lo, hi):
    """Chains of uncovered detections (IoU<0.3 with every box) linked frame to frame by
    IoU>=0.3; chains covering >= miss_len frames are reported."""
    per_frame = defaultdict(list)
    with open(dets_csv, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            F, c = int(r["frame"]), float(r["conf"])
            if c < miss_conf or not (lo <= F <= hi):
                continue
            b = (float(r["x"]), float(r["y"]), float(r["w"]), float(r["h"]))
            if all(iou(b, bb[1:]) < 0.3 for bb in mot.get(F, [])):
                per_frame[F].append((b, c))
    chains, active = [], []   # active: dict(frames, boxes, last)
    for F in sorted(per_frame):
        nxt = []
        used = set()
        for ch in active:
            if F - ch["last"] > 10:
                chains.append(ch)
                continue
            best, bi = 0.3, -1
            for i, (b, c) in enumerate(per_frame[F]):
                if i in used:
                    continue
                v = iou(ch["boxes"][-1], b)
                if v >= best:
                    best, bi = v, i
            if bi >= 0:
                b, c = per_frame[F][bi]
                used.add(bi)
                ch["frames"].append(F); ch["boxes"].append(b); ch["confs"].append(c); ch["last"] = F
            nxt.append(ch)
        for i, (b, c) in enumerate(per_frame[F]):
            if i not in used:
                nxt.append({"frames": [F], "boxes": [b], "confs": [c], "last": F})
        active = nxt
    chains += active
    out = [ch for ch in chains if ch["frames"][-1] - ch["frames"][0] + 1 >= miss_len and len(ch["frames"]) >= miss_len // 2]
    out.sort(key=lambda ch: -(ch["frames"][-1] - ch["frames"][0]))
    return out


def render_misses(mot, images, start, chains, out_dir, n=8):
    os.makedirs(out_dir, exist_ok=True)
    summary = []
    for k, ch in enumerate(chains):
        fr = ch["frames"]
        tiles = []
        for i in [int(v) for v in np.linspace(0, len(fr) - 1, min(n, len(fr))).round()]:
            F, b, c = fr[i], ch["boxes"][i], ch["confs"][i]
            img = cv2.imread(frame_path(images, start, F))
            if img is None:
                continue
            t = crop_tile(img, b, mot.get(F, []), -1, pad=1.0, min_side=260)
            _text(t, f"F{F} c={c:.2f}", (2, 16), 0.45, (0, 0, 255), 1)
            tiles.append(t)
        if not tiles:
            continue
        body = wrap_rows(tiles)
        mb = np.median(np.array(ch["boxes"]), axis=0)
        txt = (f"miss #{k:03d}  F{fr[0]}-F{fr[-1]} ({fr[-1] - fr[0] + 1} frames, {len(fr)} dets, "
               f"max conf {max(ch['confs']):.2f}) median box x={mb[0]:.0f} y={mb[1]:.0f} w={mb[2]:.0f} h={mb[3]:.0f}")
        sheet = np.vstack([title_bar(txt, body.shape[1]), body])
        cv2.imwrite(os.path.join(out_dir, f"miss_{k:03d}.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])
        summary.append({"k": k, "lo": fr[0], "hi": fr[-1], "n_dets": len(fr), "max_conf": max(ch["confs"]),
                        "median_xywh": [round(float(v), 1) for v in mb]})
    with open(os.path.join(out_dir, "misses.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
    print(f"misses: {len(summary)} -> {out_dir}")


def find_suspects(mot, lo, hi, W, H, chains, short_len=50, border=40, overlap_iou=0.45):
    """Review hints for a human: track births/deaths away from the image border (likely
    fragment or id switch), heavy overlaps between two tracks (possible swap), short tracks,
    and uncovered detections (misses)."""
    by_id = defaultdict(dict)
    for F, items in mot.items():
        for tid, x, y, w, h in items:
            by_id[tid][F] = (x, y, w, h)
    out = []

    def near_border(b):
        x, y, w, h = b
        return x < border or y < border or x + w > W - border or y + h > H - border

    for tid, fr in by_id.items():
        f0, f1 = min(fr), max(fr)
        if f1 - f0 + 1 < short_len:
            out.append({"frame": f0, "id": tid, "type": "short_track", "note": f"id {tid} only F{f0}-F{f1} ({f1 - f0 + 1} frames): FP or fragment?"})
        if f0 > lo and not near_border(fr[f0]):
            out.append({"frame": f0, "id": tid, "type": "birth_inside", "note": f"id {tid} starts at F{f0} away from the border: continuation of another id? (check previous ids there)"})
        if f1 < hi and not near_border(fr[f1]):
            out.append({"frame": f1, "id": tid, "type": "death_inside", "note": f"id {tid} ends at F{f1} away from the border: occlusion/lost? a new id may continue it"})
    # overlaps: report the first frame of each overlapping episode
    last = {}
    for F in sorted(mot):
        items = mot[F]
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a_, b_ = items[i], items[j]
                v = iou(a_[1:], b_[1:])
                if v >= overlap_iou:
                    key = (min(a_[0], b_[0]), max(a_[0], b_[0]))
                    if F - last.get(key, -10 ** 9) > 50:
                        out.append({"frame": F, "id": key[0], "type": "overlap", "note": f"ids {key[0]} & {key[1]} overlap IoU {v:.2f} from F{F}: possible swap / duplicate box"})
                    last[key] = F
    for k, ch in enumerate(chains):
        fr = ch["frames"]
        out.append({"frame": fr[0], "id": None, "type": "miss", "note": f"uncovered detections F{fr[0]}-F{fr[-1]} (max conf {max(ch['confs']):.2f}) near x={np.median([b[0] for b in ch['boxes']]):.0f} y={np.median([b[1] for b in ch['boxes']]):.0f}: unlabelled person? (sheet miss_{k:03d}.jpg)"})
    out.sort(key=lambda r: (r["frame"], str(r["id"])))
    return out


def write_suspects(sus, out_dir):
    with open(os.path.join(out_dir, "suspects.json"), "w", encoding="utf-8") as f:
        json.dump(sus, f, indent=1)
    by_type = defaultdict(int)
    for r in sus:
        by_type[r["type"]] += 1
    lines = ["# Review hints (display frame numbers, as shown in FastLabeler)", "",
             "Counts: " + ", ".join(f"{k}={v}" for k, v in sorted(by_type.items())), "",
             "| frame | id | type | note |", "|---|---|---|---|"]
    for r in sus:
        lines.append(f"| {r['frame']} | {r['id'] if r['id'] is not None else '-'} | {r['type']} | {r['note']} |")
    with open(os.path.join(out_dir, "suspects.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"suspects: {len(sus)} {dict(by_type)} -> {os.path.join(out_dir, 'suspects.md')}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mot", required=True, help="interpolated gt txt from step 15 (display frames)")
    ap.add_argument("--images", required=True)
    ap.add_argument("--start_display", type=int, required=True)
    ap.add_argument("--end_display", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", choices=["tracks", "overview", "miss", "suspects", "all"], default="all")
    ap.add_argument("--width", type=int, default=2688)
    ap.add_argument("--height", type=int, default=1520)
    ap.add_argument("--ids", default=None, help="comma list of track ids (tracks mode)")
    ap.add_argument("--report", default=None, help="step-15 report.json (segment info in titles)")
    ap.add_argument("--dets", default=None, help="step-14 --dets_out csv (miss mode)")
    ap.add_argument("--miss_conf", type=float, default=0.10)
    ap.add_argument("--miss_len", type=int, default=25)
    ap.add_argument("--block", type=int, default=500)
    args = ap.parse_args()

    mot = load_mot(args.mot)
    segments = None
    if args.report and os.path.exists(args.report):
        with open(args.report, encoding="utf-8") as f:
            segments = {k: v["segments"] for k, v in json.load(f)["tracks"].items()}
    if args.mode in ("tracks", "all"):
        only = {int(v) for v in args.ids.split(",")} if args.ids else None
        render_tracks(mot, args.images, args.start_display, os.path.join(args.out, "tracks"), only,
                      segments=segments)
    if args.mode in ("overview", "all"):
        render_overview(mot, args.images, args.start_display, args.end_display,
                        os.path.join(args.out, "overview"), args.block)
    chains = []
    if args.mode in ("miss", "suspects", "all") and args.dets:
        chains = find_misses(mot, args.dets, args.miss_conf, args.miss_len, args.start_display, args.end_display)
    if args.mode in ("miss", "all") and args.dets:
        render_misses(mot, args.images, args.start_display, chains, os.path.join(args.out, "miss"))
    if args.mode in ("suspects", "all"):
        os.makedirs(args.out, exist_ok=True)
        write_suspects(find_suspects(mot, args.start_display, args.end_display, args.width, args.height, chains), args.out)


if __name__ == "__main__":
    main()
