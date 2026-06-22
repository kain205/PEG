"""Build per-sequence box tracks for the forecaster from the MOT ground truth.

Source priority per sequence:
  1. the synthetic-occlusion GT (q-sequences: extended ``gt.txt`` whose
     visibility column already carries ``vis_geom``), else
  2. the original clean tracking GT (clean trajectories, m = 1).

Per (track, frame) we store the normalized axis-aligned box
``(cx, cy, w, h)`` from the amodal MOT box, plus the reliability

    m = vis_geom * m_glare

where ``m_glare`` per (track, frame) is reconstructed from the synthetic-glare
schedule (`glare_m.py`) — so the forecaster sees realistic low-m stretches
exactly when a person is burnt or occluded.

Only small text files are read (no images — HDD-light). Output: one pickle per
sequence in ``<cache_dir>/tracks/<seq>.pkl``.

Run:  python scripts/08_build_tracks.py
"""
import argparse
import json
import os
import pickle

from ..config import cache_dir, data_path, load_config


def _read_meta_wh(seq_dir):
    """Frame size from the occlusion schedule (q-seqs) or DONE.json (all seqs)."""
    p = os.path.join(seq_dir, "meta", "occlusion_schedule.json")
    if os.path.exists(p):
        d = json.load(open(p, encoding="utf-8"))
        if d.get("W") and d.get("H"):
            return float(d["W"]), float(d["H"])
    done = os.path.join(seq_dir, "meta", "DONE.json")
    if os.path.exists(done):
        d = json.load(open(done, encoding="utf-8"))
        w = d.get("label_image_width"); h = d.get("label_image_height")
        if w and h:
            return float(w), float(h)
    return None, None


def read_extended_gt(gt_path):
    """MOT rows -> {id: {'t': [frame0..], 'xywh': [(x,y,w,h)..], 'm': [vis..]}}.
    Columns: frame,id,x,y,w,h,flag,class,visibility ; frame is 1-indexed."""
    tracks = {}
    for ln in open(gt_path, encoding="utf-8"):
        p = ln.strip().split(",")
        if len(p) < 9:
            continue
        f = int(float(p[0])) - 1
        tid = int(float(p[1]))
        x, y, w, h = (float(v) for v in p[2:6])
        m = float(p[8])
        tr = tracks.setdefault(tid, {"t": [], "xywh": [], "m": []})
        tr["t"].append(f); tr["xywh"].append((x, y, w, h)); tr["m"].append(m)
    return tracks


def process_sequence(seq_dir, glare_m=None):
    name = os.path.basename(seq_dir)
    gt_path = os.path.join(seq_dir, "mot", "gt", "gt.txt")
    if not os.path.exists(gt_path):
        return None
    W, H = _read_meta_wh(seq_dir)
    if W is None:
        return None
    glare_m = glare_m or {}
    raw = read_extended_gt(gt_path)
    tracks = {}
    n_glared = 0
    for tid, tr in raw.items():
        boxes, ms = [], []
        for (x, y, w, h), f, m_occ in zip(tr["xywh"], tr["t"], tr["m"]):
            boxes.append(((x + w / 2.0) / W, (y + h / 2.0) / H, w / W, h / H))
            mg = glare_m.get((tid, f), 1.0)
            if mg < 1.0:
                n_glared += 1
            ms.append(float(m_occ) * mg)                # m = vis_geom * m_glare
        tracks[tid] = {"t": tr["t"], "box": boxes, "m": ms}
    return {"seq": name, "W": W, "H": H, "n_glared_rows": n_glared,
            "n_frames": (max(max(tr["t"]) for tr in tracks.values()) + 1) if tracks else 0,
            "tracks": tracks}


def build_all(cfg=None, limit=0):
    cfg = cfg or load_config()
    trk_root = data_path(cfg, "tracking")
    out_dir = cache_dir(cfg, "tracks")

    seqs = sorted(s for s in os.listdir(trk_root)
                  if os.path.isdir(os.path.join(trk_root, s)))
    if limit:
        seqs = seqs[:limit]

    manifest = []
    n_occ = n_clean = 0
    for i, name in enumerate(seqs):
        src = os.path.join(trk_root, name)
        if not os.path.exists(os.path.join(src, "mot", "gt", "gt.txt")):
            print(f"[{i + 1}/{len(seqs)}] {name}: skipped (no gt)")
            continue
        data = process_sequence(src, glare_m={})
        if data is None:
            print(f"[{i + 1}/{len(seqs)}] {name}: skipped (no meta)")
            continue
        with open(os.path.join(out_dir, f"{name}.pkl"), "wb") as f:
            pickle.dump(data, f)
        n_clean += 1
        lens = [len(t["t"]) for t in data["tracks"].values()]
        manifest.append({"seq": name, "src": "clean",
                         "n_tracks": len(data["tracks"]),
                         "max_len": max(lens) if lens else 0,
                         "n_glared_rows": data["n_glared_rows"]})
    json.dump(manifest, open(os.path.join(out_dir, "manifest.json"), "w"), indent=2)
    print(f"\nWrote {len(manifest)} sequences to {out_dir} "
          f"({n_occ} occlusion+glare, {n_clean} clean)")
    return out_dir


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    build_all(load_config(args.config), limit=args.limit)


if __name__ == "__main__":
    main()
