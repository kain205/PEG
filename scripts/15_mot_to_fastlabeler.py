"""Step 15 -- MOT txt (display frames) -> FastLabeler Local v4.5 labels project + MOT gt.

Pipeline
  1. load MOT rows (frame = display/1-based number of the ORIGINAL video)
  2. stable id remap raw -> final (first appearance order, from ``--first_id``), persisted
     in ``<out_dir>/idmap.json`` so edits keep referring to the same final ids
  3. apply ``--edits`` (JSON list, see EDIT OPS) on final ids
  4. drop tracks shorter than ``--min_len`` observed frames (listed in the report)
  5. cut each track at gaps > ``--gap_interp`` frames; EVERY piece gets its own final id
     (lost track => new id, numbered from --first_id by first appearance); sparsify
     keyframes greedily (keep one when linear interpolation would deviate > ``--eps`` px);
     write an ``outside`` keyframe right after each piece
  6. write ``labels_project.json`` (FastLabeler schema, keyframe keys 0-based = F-1),
     ``gt_<lo>_<hi>.txt`` (our emulation of the app's interpolation, frames 1-based,
     9 cols) and ``report.json``

EDIT OPS (edits.json = [ {...}, ... ], applied in order, ids are FINAL ids)
  {"op":"delete","id":23}
  {"op":"merge","into":21,"from":27}             # boxes of 27 added to 21 (21 wins on conflicts)
  {"op":"split","id":21,"at":40123,"new_id":40} # frames >= at move to new_id
  {"op":"trim","id":21,"lo":35068,"hi":40000}   # keep only frames in [lo,hi]
  {"op":"cut","id":21,"lo":36000,"hi":36100}    # remove frames in [lo,hi] (creates a gap)
  {"op":"box","id":21,"frame":36000,"xywh":[100,200,40,90]}   # set/add a box
  {"op":"occluded","id":21,"lo":36000,"hi":36100}             # flag frames occluded (vis=0)
  {"op":"shift","id":21,"lo":36000,"hi":36100,"dx":0,"dy":0,"dw":0,"dh":0}

``--template`` = a project.json the app itself saved for this video (gives video_source,
images, classes); with ``--inject`` the output project is that file with our tracks.
"""
import argparse
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_mot(path):
    tracks = defaultdict(dict)   # id -> {F: [x,y,w,h]}
    with open(path, encoding="utf-8") as f:
        for ln in f:
            p = ln.strip().split(",")
            if len(p) < 6:
                continue
            F, tid = int(float(p[0])), int(float(p[1]))
            tracks[tid][F] = [float(v) for v in p[2:6]]
    return tracks


def remap_ids(tracks, idmap_path, first_id):
    idmap = {}
    if os.path.exists(idmap_path):
        with open(idmap_path, encoding="utf-8") as f:
            idmap = {int(k): int(v) for k, v in json.load(f).items()}
    nxt = max(idmap.values(), default=first_id - 1) + 1
    for raw in sorted(tracks, key=lambda t: (min(tracks[t]), t)):
        if raw not in idmap:
            idmap[raw] = nxt
            nxt += 1
    with open(idmap_path, "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in sorted(idmap.items())}, f, indent=1)
    return {idmap[r]: dict(fr) for r, fr in tracks.items()}, idmap


def apply_edits(tracks, occl, edits):
    for e in edits:
        op = e["op"]
        if op == "delete":
            tracks.pop(e["id"], None)
        elif op == "merge":
            src = tracks.pop(e["from"], {})
            dst = tracks.setdefault(e["into"], {})
            for F, b in src.items():
                dst.setdefault(F, b)
        elif op == "split":
            src = tracks[e["id"]]
            new = {F: b for F, b in src.items() if F >= e["at"]}
            for F in new:
                del src[F]
            tracks[e["new_id"]] = new
        elif op == "trim":
            src = tracks[e["id"]]
            for F in [F for F in src if F < e["lo"] or F > e["hi"]]:
                del src[F]
        elif op == "cut":
            src = tracks[e["id"]]
            for F in [F for F in src if e["lo"] <= F <= e["hi"]]:
                del src[F]
        elif op == "box":
            tracks.setdefault(e["id"], {})[e["frame"]] = [float(v) for v in e["xywh"]]
        elif op == "occluded":
            for F in range(e["lo"], e["hi"] + 1):
                occl[(e["id"], F)] = True
        elif op == "shift":
            src = tracks[e["id"]]
            for F, b in src.items():
                if e["lo"] <= F <= e["hi"]:
                    b[0] += e.get("dx", 0); b[1] += e.get("dy", 0)
                    b[2] += e.get("dw", 0); b[3] += e.get("dh", 0)
        else:
            raise ValueError(f"unknown edit op {op}")
    for tid in [t for t, fr in tracks.items() if not fr]:
        del tracks[tid]
    return tracks


def lerp(a, b, r):
    return [a[i] + (b[i] - a[i]) * r for i in range(4)]


def sparsify(frames, boxes, eps):
    """frames sorted; keep indices so that linear interpolation between kept frames is
    within eps px (max abs over x,y,w,h) of every observed box. Returns kept indices."""
    n = len(frames)
    if n <= 2:
        return list(range(n))
    keep = [0]
    a = 0
    while a < n - 1:
        j = a + 1
        last_ok = j
        while j < n:
            ok = True
            fa, fb = frames[a], frames[j]
            for k in range(a + 1, j):
                r = (frames[k] - fa) / float(fb - fa)
                ib = lerp(boxes[a], boxes[j], r)
                if max(abs(ib[i] - boxes[k][i]) for i in range(4)) > eps:
                    ok = False
                    break
            if not ok:
                break
            last_ok = j
            j += 1
        keep.append(last_ok)
        a = last_ok
    return keep


def build(tracks, occl, lo, hi, min_len, gap_interp, eps, W, H, n_images, first_id):
    """-> (fl_tracks {id: keyframes{key0: dict}}, gt_rows, report).
    A track is cut wherever it is unobserved for more than ``gap_interp`` frames; every
    piece becomes its OWN id (lost track => new id). Pieces are numbered from ``first_id``
    in order of first appearance."""
    pieces = []   # (first_frame, src_id, {F: box})
    rep = {"dropped_short": [], "tracks": {}, "pieces_from": {}}
    for tid in sorted(tracks):
        fr = {F: b for F, b in tracks[tid].items() if lo <= F <= hi}
        if not fr:
            continue
        frames = sorted(fr)
        cur = [frames[0]]
        segs = []
        for F in frames[1:]:
            if F - cur[-1] > gap_interp:
                segs.append(cur)
                cur = [F]
            else:
                cur.append(F)
        segs.append(cur)
        for seg in segs:
            if len(seg) < min_len:
                rep["dropped_short"].append({"src_id": tid, "n": len(seg), "lo": seg[0], "hi": seg[-1]})
                continue
            pieces.append((seg[0], tid, {F: fr[F] for F in seg}))
    pieces.sort(key=lambda p: (p[0], p[1]))
    fl, gt = {}, []
    for k, (f0, src, fr) in enumerate(pieces):
        tid = first_id + k
        seg = sorted(fr)
        boxes = [fr[F] for F in seg]
        keep = sparsify(seg, boxes, eps)
        kfs = {}
        for i in keep:
            F = seg[i]
            x, y, w, h = boxes[i]
            kfs[str(F - 1)] = {"x": round(x, 2), "y": round(y, 2), "w": round(w, 2),
                               "h": round(h, 2), "outside": False,
                               "occluded": bool(occl.get((src, F), False)), "source": "manual"}
        Fe = seg[-1] + 1
        x, y, w, h = boxes[-1]
        if Fe - 1 < n_images:   # no marker needed when the track runs to the video end
            kfs[str(Fe - 1)] = {"x": round(x, 2), "y": round(y, 2), "w": round(w, 2),
                                "h": round(h, 2), "outside": True, "occluded": False,
                                "source": "manual"}
        kept = [seg[i] for i in keep]
        for a_, b_ in zip(kept, kept[1:]):
            for F in range(a_, b_):
                r = (F - a_) / float(b_ - a_)
                gt.append((F, tid, lerp(fr[a_], fr[b_], r), occl.get((src, F), False)))
        gt.append((kept[-1], tid, fr[kept[-1]], occl.get((src, kept[-1]), False)))
        fl[str(tid)] = {"id": str(tid), "label": "person", "manual_carry": True, "keyframes": kfs}
        rep["tracks"][tid] = {"first": seg[0], "last": seg[-1], "observed": len(seg),
                              "segments": [[seg[0], seg[-1]]], "keyframes": len(kfs),
                              "box_keyframes": len(keep), "src_id": src}
        rep["pieces_from"].setdefault(str(src), []).append(tid)
    rows = []
    for F, tid, (x, y, w, h), occ in sorted(gt, key=lambda r: (r[0], r[1])):
        x1, y1 = max(0.0, x), max(0.0, y)
        x2, y2 = min(float(W), x + w), min(float(H), y + h)
        vis = 0 if occ else 1
        rows.append(f"{F},{tid},{x1:.2f},{y1:.2f},{max(1.0, x2 - x1):.2f},{max(1.0, y2 - y1):.2f},1,1,{vis}")
    return fl, rows, rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mot", required=True)
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--lo", type=int, required=True, help="first display frame of our range")
    ap.add_argument("--hi", type=int, required=True, help="last display frame of our range")
    ap.add_argument("--first_id", type=int, default=20)
    ap.add_argument("--edits", default=None)
    ap.add_argument("--min_len", type=int, default=10)
    ap.add_argument("--gap_interp", type=int, default=25)
    ap.add_argument("--eps", type=float, default=2.0)
    ap.add_argument("--n_images", type=int, default=73353)
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--template", default=None, help="project.json saved by the app for this video")
    ap.add_argument("--inject", default=None, help="write template + our tracks to this path")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    raw = load_mot(args.mot)
    tracks, idmap = remap_ids(raw, os.path.join(args.out_dir, "idmap.json"), args.first_id)
    occl = {}
    edits = []
    if args.edits and os.path.exists(args.edits):
        with open(args.edits, encoding="utf-8") as f:
            edits = json.load(f)
        tracks = apply_edits(tracks, occl, edits)
    W, H, n_images, classes = args.width, args.height, args.n_images, ["person"]
    tpl = None
    if args.template:
        with open(args.template, encoding="utf-8") as f:
            tpl = json.load(f)
        vs = tpl.get("video_source", {})
        if vs.get("size"):
            W, H = int(vs["size"][0]), int(vs["size"][1])
        n_images = len(tpl.get("images", [])) or n_images
        classes = tpl.get("classes") or classes
    fl, rows, rep = build(tracks, occl, args.lo, args.hi, args.min_len, args.gap_interp, args.eps, W, H, n_images, args.first_id)

    # sanity
    for tid, t in fl.items():
        keys = [int(k) for k in t["keyframes"]]
        assert all(0 <= k < n_images for k in keys), (tid, min(keys), max(keys))
    seen = set()
    for r in rows:
        F, tid = r.split(",")[:2]
        assert (F, tid) not in seen, ("duplicate", F, tid)
        seen.add((F, tid))

    project = {
        "version": 2, "project_type": "video",
        "images": [f"frame_{i:06d}.jpg" for i in range(n_images)],
        "classes": classes, "tracks": fl,
        "frame_id_overrides": {}, "id_override_ranges": [], "deleted_boxes": {},
        "annotation_source": "manual",
    }
    pj = os.path.join(args.out_dir, "labels_project.json")
    with open(pj, "w", encoding="utf-8") as f:
        json.dump(project, f)
    if tpl is not None and args.inject:
        out = dict(tpl)
        out["tracks"] = fl
        out["classes"] = classes
        out["frame_id_overrides"], out["id_override_ranges"], out["deleted_boxes"] = {}, [], {}
        tmp = args.inject + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(out, f)
        os.replace(tmp, args.inject)
    gt = os.path.join(args.out_dir, f"gt_{args.lo}_{args.hi}.txt")
    with open(gt, "w", encoding="utf-8") as f:
        f.write("\n".join(rows) + ("\n" if rows else ""))
    rep.update({"n_tracks": len(fl), "n_keyframes": sum(len(t["keyframes"]) for t in fl.values()),
                "n_gt_rows": len(rows), "ids": sorted(int(t) for t in fl), "edits": len(edits),
                "params": {"lo": args.lo, "hi": args.hi, "min_len": args.min_len,
                           "gap_interp": args.gap_interp, "eps": args.eps, "W": W, "H": H,
                           "n_images": n_images}})
    with open(os.path.join(args.out_dir, "report.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=1)
    print(f"tracks={rep['n_tracks']} keyframes={rep['n_keyframes']} gt_rows={rep['n_gt_rows']} "
          f"dropped_short={len(rep['dropped_short'])} ids={rep['ids'][:5]}..{rep['ids'][-1:] if rep['ids'] else ''}")
    print(f"-> {pj}\n-> {gt}")


if __name__ == "__main__":
    main()
