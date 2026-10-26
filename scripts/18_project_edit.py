"""Step 18 -- read / edit a FastLabeler Local v4.5 video project.json the way the app does.

Subcommands
  tomot   project.json -> MOT txt (display frames, output ids after id_override_ranges /
          frame_id_overrides, deleted boxes skipped). Re-implements server.frame_box:
          exact keyframe (None if outside) · before first keyframe None · after last keyframe
          carried only when manual_carry and last not outside · between a,b: a outside -> None,
          b outside -> copy a, else linear interpolation.
  edit    apply an edits JSON list to project.json (in place, keeps a .bak), ops:
          {"op":"delete_track","id":24}
          {"op":"end","id":24,"frame":40100}            # like the app's T at display frame
          {"op":"relink","id":28,"to":26,"frame":40004} # like the app's J (id_override_ranges)
          {"op":"hide","id":24,"frame":40100}           # like the app's X (deleted_boxes)
          {"op":"add_track","id":145,"boxes":{"40100":[x,y,w,h],...}} # display frame keys; ends with outside
          {"op":"set_box","id":20,"frame":40100,"xywh":[x,y,w,h]}     # add/replace a keyframe
          {"op":"trim_start","id":24,"frame":40100}     # drop keyframes before display frame
          {"op":"extend","id":50,"boxes":{"45617":[x,y,w,h],...}} # add keyframes to a track, re-end after
          {"op":"unhide_all"}                           # clear the app's Hide/Show (V) flags
          {"op":"clear_range","id":52,"lo":45837,"hi":45852}  # drop keyframes in a display-frame range
          {"op":"split","id":288,"frame":56194,"new_id":300,"box":[x,y,w,h]}  # id hop: keyframes >= frame -> new track
          {"op":"merge","id":215,"from":231}               # track 231 continues 215 (same person after occlusion)
          {"op":"shift","id":20,"lo":40000,"hi":40100,"dx":0,"dy":0,"dw":0,"dh":0}
  renumber  bake overrides, renumber output ids from --first_id, re-sparsify keyframes (--eps)
  rekey     renumber from --first_id AND re-pick keyframes of the auto tracks (smooth + Douglas-
            Peucker, --eps px); tracks in --keep (hand-edited) are copied verbatim
  REFUSES to write while the app (FastLabelerLocal*.exe) is running.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys


def app_running():
    out = subprocess.run(["tasklist"], capture_output=True, text=True).stdout.lower()
    return "fastlabelerlocal" in out


def frame_box(track, f):
    """Box dict or None for 0-based frame f (server.frame_box semantics)."""
    kfs = track.get("keyframes") or {}
    if not kfs:
        return None
    keys = sorted(int(k) for k in kfs)
    sk = str(f)
    if sk in kfs:
        kf = kfs[sk]
        return None if kf.get("outside") else kf
    if f < keys[0]:
        return None
    if f > keys[-1]:
        last = kfs[str(keys[-1])]
        return last if track.get("manual_carry") and not last.get("outside") else None
    import bisect
    i = bisect.bisect_right(keys, f)
    a, b = kfs[str(keys[i - 1])], kfs[str(keys[i])]
    if a.get("outside"):
        return None
    if b.get("outside"):
        return a
    r = (f - keys[i - 1]) / float(keys[i] - keys[i - 1])
    return {k: a[k] + (b[k] - a[k]) * r for k in ("x", "y", "w", "h")} | \
        {"occluded": (a if r < 0.5 else b).get("occluded", False)}


def output_id(project, tid, f):
    fo = (project.get("frame_id_overrides") or {}).get(str(f), {})
    if str(tid) in fo:
        return int(fo[str(tid)])
    out = int(tid)
    for rule in project.get("id_override_ranges") or []:
        if str(rule.get("source_id")) == str(tid) and int(rule.get("from_frame", 0)) <= f:
            out = int(rule["target_id"])
    return out


def project_to_rows(project, lo, hi):
    """MOT rows (display frames lo..hi) + per-source-track spans."""
    W, H = project["video_source"]["size"]
    deleted = project.get("deleted_boxes") or {}
    rows = []
    for tid, tr in project["tracks"].items():
        kfs = tr.get("keyframes") or {}
        if not kfs:
            continue
        keys = sorted(int(k) for k in kfs)
        f0 = max(keys[0], lo - 1)
        f1 = hi - 1 if tr.get("manual_carry") else min(keys[-1], hi - 1)
        for f in range(f0, f1 + 1):
            if deleted.get(str(f), {}).get(str(tid)):
                continue
            b = frame_box(tr, f)
            if b is None:
                continue
            x1, y1 = max(0.0, b["x"]), max(0.0, b["y"])
            x2, y2 = min(float(W), b["x"] + b["w"]), min(float(H), b["y"] + b["h"])
            oid = output_id(project, tid, f)
            # app's track_priority on output-id collisions: native id, then a keyframe at f, then lower id
            prio = (0 if oid == int(tid) else 1, 0 if str(f) in kfs else 1, int(tid))
            rows.append((f + 1, oid, x1, y1, max(1.0, x2 - x1), max(1.0, y2 - y1),
                         0 if b.get("occluded") else 1, int(tid), prio))
    best = {}
    for r in rows:
        k = (r[0], r[1])
        if k not in best or r[8] < best[k][8]:
            best[k] = r
    rows = sorted((r[:8] for r in best.values()), key=lambda r: (r[0], r[1]))
    return rows


def cmd_tomot(args):
    project = json.load(open(args.project, encoding="utf-8"))
    rows = project_to_rows(project, args.lo, args.hi)
    with open(args.out, "w", encoding="utf-8") as f:
        for F, oid, x, y, w, h, vis, src in rows:
            f.write(f"{F},{oid},{x:.2f},{y:.2f},{w:.2f},{h:.2f},1,1,{vis}\n")
    ids = sorted({r[1] for r in rows})
    print(f"{len(rows)} rows, {len(ids)} output ids ({ids[0]}..{ids[-1]}), "
          f"{len(project['tracks'])} source tracks -> {args.out}")


def cmd_edit(args):
    if app_running() and not args.force:
        sys.exit("FastLabeler is running: close it first (its Save would overwrite this edit)")
    project = json.load(open(args.project, encoding="utf-8"))
    edits = json.load(open(args.edits, encoding="utf-8"))
    tracks = project["tracks"]
    W, H = project["video_source"]["size"]

    def mk(b, outside=False):
        x, y, w, h = [float(v) for v in b]
        return {"x": x, "y": y, "w": w, "h": h, "outside": outside, "occluded": False,
                "source": "outside" if outside else "manual"}

    n = 0
    alias = {}  # track id merged away -> the track that absorbed it

    def resolve(t):
        while t in alias:
            t = alias[t]
        return t

    for e in edits:
        op, tid = e["op"], resolve(str(e.get("id")))
        if op == "merge":
            e = dict(e, **{"from": resolve(str(e["from"]))})
            if str(e["from"]) == tid:
                continue
        if op == "delete_track":
            if tid in tracks:
                del tracks[tid]
                project["id_override_ranges"] = [r for r in project.get("id_override_ranges", [])
                                                 if str(r.get("source_id")) != tid]
        elif op == "end":
            f = e["frame"] - 1
            tr = tracks[tid]
            box = frame_box(tr, f) or frame_box(tr, f - 1)
            for k in [k for k in tr["keyframes"] if int(k) >= f]:
                del tr["keyframes"][k]
            if box is not None:
                tr["keyframes"][str(f)] = mk([box["x"], box["y"], box["w"], box["h"]], outside=True)
        elif op == "relink":
            project.setdefault("id_override_ranges", []).append(
                {"source_id": tid, "target_id": str(e["to"]), "from_frame": e["frame"] - 1})
        elif op == "hide":
            project.setdefault("deleted_boxes", {}).setdefault(str(e["frame"] - 1), {})[tid] = True
        elif op == "add_track":
            assert tid not in tracks, f"track {tid} exists"
            kfs = {str(int(F) - 1): mk(b) for F, b in e["boxes"].items()}
            last = max(int(F) for F in e["boxes"])
            if last < len(project["images"]):
                kfs[str(last)] = mk(e["boxes"][str(last)], outside=True)
            tracks[tid] = {"id": tid, "label": "person", "manual_carry": True, "keyframes": kfs}
        elif op == "extend":
            # add keyframes (display-frame keys) to an existing track, dropping any outside
            # marker at/after the first new frame, and re-ending the track after the last one
            tr = tracks[tid]
            first = min(int(F) for F in e["boxes"]) - 1
            for k in [k for k, v in tr["keyframes"].items() if v.get("outside") and int(k) >= first]:
                del tr["keyframes"][k]
            for F, b in e["boxes"].items():
                tr["keyframes"][str(int(F) - 1)] = mk(b)
            last = max(int(k) for k, v in tr["keyframes"].items() if not v.get("outside"))
            if last + 1 < len(project["images"]) and not any(
                    v.get("outside") and int(k) > last for k, v in tr["keyframes"].items()):
                lb = tr["keyframes"][str(last)]
                tr["keyframes"][str(last + 1)] = mk([lb["x"], lb["y"], lb["w"], lb["h"]], outside=True)
        elif op == "clear_range":
            # drop (non-outside) keyframes of a track inside display frames [lo, hi]
            tr = tracks[tid]
            for k in [k for k, v in tr["keyframes"].items()
                      if e["lo"] - 1 <= int(k) <= e["hi"] - 1 and not v.get("outside")]:
                del tr["keyframes"][k]
        elif op == "shift":
            # move/resize every keyframe of a track inside display frames [lo, hi]
            for k, v in tracks[tid]["keyframes"].items():
                if e["lo"] - 1 <= int(k) <= e["hi"] - 1 and not v.get("outside"):
                    v["x"] += e.get("dx", 0); v["y"] += e.get("dy", 0)
                    v["w"] = max(1.0, v["w"] + e.get("dw", 0)); v["h"] = max(1.0, v["h"] + e.get("dh", 0))
        elif op == "split":
            # the track changed person at display frame F: keyframes >= F move to track new_id,
            # the old track ends (outside marker) at F
            tr = tracks[tid]; f = e["frame"] - 1; nid = str(e["new_id"])
            assert nid not in tracks, f"track {nid} exists"
            moved = {k: v for k, v in tr["keyframes"].items() if int(k) >= f}
            for k in moved:
                del tr["keyframes"][k]
            prev = frame_box(tr, f - 1)
            if prev is not None and str(f) not in tr["keyframes"]:
                tr["keyframes"][str(f)] = mk([prev["x"], prev["y"], prev["w"], prev["h"]], outside=True)
            if str(f) not in moved and "box" in e:
                moved[str(f)] = mk(e["box"])
            tracks[nid] = {"id": nid, "label": tr.get("label", "person"), "manual_carry": True, "keyframes": moved}
        elif op == "merge":
            # track `from` is the continuation of track id: drop id's trailing outside markers,
            # take over all keyframes of `from` (interpolation bridges the gap), delete `from`
            tr, src = tracks[tid], tracks[str(e["from"])]
            last_real = max(int(k) for k, v in tr["keyframes"].items() if not v.get("outside"))
            for k in [k for k, v in tr["keyframes"].items() if v.get("outside") and int(k) > last_real]:
                del tr["keyframes"][k]
            for k, v in src["keyframes"].items():
                if int(k) > last_real:
                    tr["keyframes"][k] = v
            del tracks[str(e["from"])]
            alias[str(e["from"])] = tid
        elif op == "unhide_all":
            for tr in tracks.values():
                tr.pop("hidden", None)
        elif op == "set_box":
            tracks[tid]["keyframes"][str(e["frame"] - 1)] = mk(e["xywh"])
        elif op == "trim_start":
            tr = tracks[tid]
            for k in [k for k in tr["keyframes"] if int(k) < e["frame"] - 1]:
                del tr["keyframes"][k]
        else:
            raise ValueError(op)
        n += 1
    shutil.copy(args.project, args.project + ".bak")
    tmp = args.project + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(project, f)
    os.replace(tmp, args.project)
    print(f"applied {n} edits -> {args.project} (backup .bak); tracks now {len(tracks)}")


def cmd_renumber(args):
    """Bake id overrides / deleted boxes / hidden flags into plain tracks and renumber the
    OUTPUT ids contiguously from --first_id in order of first appearance. Every output id
    becomes one track; gaps inside it get an outside marker; keyframes are re-sparsified
    (--eps px) from the per-frame boxes."""
    import bisect
    if app_running() and not args.force:
        sys.exit("FastLabeler is running: close it first")
    project = json.load(open(args.project, encoding="utf-8"))
    rows = project_to_rows(project, args.lo, args.hi)
    per = {}
    for F, oid, x, y, w, h, vis, src in rows:
        per.setdefault(oid, {})[F] = (x, y, w, h, vis)
    order = sorted(per, key=lambda o: (min(per[o]), o))
    idmap = {o: args.first_id + i for i, o in enumerate(order)}
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import importlib.util
    spec = importlib.util.spec_from_file_location("m15", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                                         "15_mot_to_fastlabeler.py"))
    m15 = importlib.util.module_from_spec(spec); spec.loader.exec_module(m15)
    n_images = len(project["images"])
    tracks = {}
    for o in order:
        nid = str(idmap[o])
        frames = sorted(per[o])
        segs, cur = [], [frames[0]]
        for F in frames[1:]:
            if F == cur[-1] + 1:
                cur.append(F)
            else:
                segs.append(cur)
                cur = [F]
        segs.append(cur)
        kfs = {}
        for seg in segs:
            boxes = [list(per[o][F][:4]) for F in seg]
            keep = m15.sparsify(seg, boxes, args.eps)
            for i in keep:
                F = seg[i]; x, y, w, h = boxes[i]
                kfs[str(F - 1)] = {"x": round(x, 2), "y": round(y, 2), "w": round(w, 2), "h": round(h, 2),
                                   "outside": False, "occluded": per[o][F][4] == 0, "source": "manual"}
            Fe = seg[-1]  # 0-based key of the frame after the segment
            if Fe < n_images:
                x, y, w, h = boxes[-1]
                kfs[str(Fe)] = {"x": round(x, 2), "y": round(y, 2), "w": round(w, 2), "h": round(h, 2),
                                "outside": True, "occluded": False, "source": "outside"}
        tracks[nid] = {"id": nid, "label": "person", "manual_carry": True, "keyframes": kfs}
    project["tracks"] = tracks
    project["id_override_ranges"], project["frame_id_overrides"], project["deleted_boxes"] = [], {}, {}
    shutil.copy(args.project, args.project + ".bak")
    tmp = args.project + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(project, f)
    os.replace(tmp, args.project)
    with open(args.map_out, "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in idmap.items()}, f, indent=1)
    print(f"renumbered {len(order)} output ids -> {args.first_id}..{args.first_id + len(order) - 1}; "
          f"keyframes {sum(len(t['keyframes']) for t in tracks.values())}; map -> {args.map_out}")


def _smooth(v, k_med=5, k_avg=11, mode="sg"):
    """median (k_med) then a symmetric window (k_avg) that shrinks at the ends: 'avg' = moving
    average, 'sg' = quadratic Savitzky-Golay (no bias for accelerating motion)."""
    import numpy as np
    a = np.asarray(v, float); n = len(a)
    m = np.empty(n); h = k_med // 2
    for i in range(n):
        r = min(h, i, n - 1 - i); m[i] = np.median(a[i - r:i + r + 1])
    b = np.empty(n); h = k_avg // 2
    for i in range(n):
        r = min(h, i, n - 1 - i)
        w = m[i - r:i + r + 1]
        if mode == "avg" or r < 2:
            b[i] = w.mean()
        else:
            t = np.arange(-r, r + 1, dtype=float)
            b[i] = np.polyfit(t, w, 2)[2]  # value of the local quadratic at t = 0
    return b


def _dp_keep(frames, corners, eps):
    """Douglas-Peucker on the 4-D corner trajectory: keep indices so that linear interpolation
    between kept frames stays within eps px (max abs over x1,y1,x2,y2) of every frame."""
    import numpy as np
    fr = np.asarray(frames, float); c = np.asarray(corners, float)
    keep = {0, len(fr) - 1}; stack = [(0, len(fr) - 1)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        r = ((fr[a + 1:b] - fr[a]) / (fr[b] - fr[a]))[:, None]
        dev = np.abs(c[a] + (c[b] - c[a]) * r - c[a + 1:b]).max(axis=1)
        i = int(dev.argmax())
        if dev[i] > eps:
            m = a + 1 + i; keep.add(m); stack += [(a, m), (m, b)]
    return sorted(keep)


def cmd_rekey(args):
    """Renumber every track contiguously from --first_id (order of first visible frame) and,
    for tracks NOT in --keep (hand-edited ones are kept verbatim), re-pick the keyframes:
    per visible segment, the per-frame boxes (app interpolation) are smoothed (median
    --k_med, moving average --k_avg) and reduced to the Douglas-Peucker keyframes with
    tolerance --eps px, so still / constant-velocity stretches get 2 keyframes and turning
    points get one each. Empty tracks are dropped. Writes the keyframe/id report to --report."""
    if app_running() and not args.force:
        sys.exit("FastLabeler is running: close it first")
    project = json.load(open(args.project, encoding="utf-8"))
    keep_ids = {s.strip() for s in (args.keep or "").split(",") if s.strip()}
    if keep_ids == {"*"}:  # renumber only, every track verbatim
        keep_ids = set(project["tracks"])
    n_images = len(project["images"])
    tracks = project["tracks"]
    first = {}
    for tid, tr in tracks.items():
        vis = [int(k) for k, v in tr["keyframes"].items() if not v.get("outside")]
        if vis:
            first[tid] = min(vis)
    order = sorted(first, key=lambda t: (first[t], int(t)))
    idmap = {t: str(args.first_id + i) for i, t in enumerate(order)}
    new_tracks, report = {}, {"idmap": idmap, "dropped_empty": sorted(set(tracks) - set(first), key=int), "tracks": {}}
    for tid in order:
        tr = tracks[tid]; nid = idmap[tid]
        if tid in keep_ids:
            new_tracks[nid] = dict(tr, id=nid)
            report["tracks"][nid] = {"src": tid, "kept": True, "kf": len(tr["keyframes"])}
            continue
        kfs = tr["keyframes"]; keys = sorted(int(k) for k in kfs)
        f0, f1 = keys[0], keys[-1]
        if tr.get("manual_carry") and not kfs[str(f1)].get("outside"):
            f1 = n_images - 1
        boxes = {}
        for f in range(f0, f1 + 1):
            b = frame_box(tr, f)
            if b is not None:
                boxes[f] = b
        segs, cur = [], []
        for f in sorted(boxes):
            if cur and f != cur[-1] + 1:
                segs.append(cur); cur = []
            cur.append(f)
        if cur:
            segs.append(cur)
        out = {}
        for seg in segs:
            raw = [[boxes[f][k] for k in ("x", "y", "w", "h")] for f in seg]
            cols = list(zip(*raw))
            sm = [_smooth(c, args.k_med, args.k_avg, args.smooth) for c in cols] if len(seg) >= 3 else [list(c) for c in cols]
            corners = [[sm[0][i], sm[1][i], sm[0][i] + sm[2][i], sm[1][i] + sm[3][i]] for i in range(len(seg))]
            keep = _dp_keep(seg, corners, args.eps)
            if args.max_gap:  # cap the spacing so every stretch has a checkable keyframe
                dense_keep = []
                for a, b in zip(keep, keep[1:]):
                    dense_keep.append(a)
                    n_extra = (b - a - 1) // args.max_gap
                    dense_keep += [a + (b - a) * (j + 1) // (n_extra + 1) for j in range(n_extra)]
                keep = sorted(set(dense_keep + [keep[-1]]))
            for i in keep:
                f = seg[i]
                out[str(f)] = {"x": round(float(sm[0][i]), 2), "y": round(float(sm[1][i]), 2),
                               "w": round(float(sm[2][i]), 2), "h": round(float(sm[3][i]), 2),
                               "outside": False, "occluded": bool(boxes[f].get("occluded")), "source": "manual"}
            fe = seg[-1] + 1
            if fe < n_images:
                last = out[str(seg[-1])]
                out[str(fe)] = {"x": last["x"], "y": last["y"], "w": last["w"], "h": last["h"],
                                "outside": True, "occluded": False, "source": "outside"}
        new_tracks[nid] = {"id": nid, "label": tr.get("label", "person"), "manual_carry": True, "keyframes": out}
        report["tracks"][nid] = {"src": tid, "kept": False, "kf_before": len(kfs), "kf": len(out),
                                 "frames": len(boxes), "segments": len(segs)}
    project["tracks"] = new_tracks
    project["deleted_boxes"] = {f: {idmap[t]: v for t, v in d.items() if t in idmap}
                                for f, d in (project.get("deleted_boxes") or {}).items()}
    project["deleted_boxes"] = {f: d for f, d in project["deleted_boxes"].items() if d}
    project["id_override_ranges"] = [dict(r, source_id=idmap[str(r["source_id"])], target_id=idmap.get(str(r["target_id"]), str(r["target_id"])))
                                     for r in project.get("id_override_ranges") or [] if str(r["source_id"]) in idmap]
    project["frame_id_overrides"] = {f: {idmap[t]: idmap.get(str(v), v) for t, v in d.items() if t in idmap}
                                     for f, d in (project.get("frame_id_overrides") or {}).items()}
    shutil.copy(args.project, args.project + ".bak")
    tmp = args.project + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(project, f)
    os.replace(tmp, args.project)
    with open(args.report, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
    kb = sum(r.get("kf_before", 0) for r in report["tracks"].values() if not r["kept"])
    ka = sum(r["kf"] for r in report["tracks"].values() if not r["kept"])
    print(f"{len(order)} tracks -> ids {args.first_id}..{args.first_id + len(order) - 1} "
          f"(kept {sorted(idmap[t] for t in keep_ids if t in idmap)}, dropped empty {report['dropped_empty']}); "
          f"auto keyframes {kb} -> {ka}; report -> {args.report}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("tomot")
    a.add_argument("--project", required=True)
    a.add_argument("--out", required=True)
    a.add_argument("--lo", type=int, default=1)
    a.add_argument("--hi", type=int, default=10 ** 9)
    b = sub.add_parser("edit")
    b.add_argument("--project", required=True)
    b.add_argument("--edits", required=True)
    b.add_argument("--force", action="store_true")
    c = sub.add_parser("renumber")
    c.add_argument("--project", required=True)
    c.add_argument("--lo", type=int, required=True)
    c.add_argument("--hi", type=int, required=True)
    c.add_argument("--first_id", type=int, default=20)
    c.add_argument("--eps", type=float, default=1.0)
    c.add_argument("--map_out", required=True)
    c.add_argument("--force", action="store_true")
    d = sub.add_parser("rekey")
    d.add_argument("--project", required=True)
    d.add_argument("--keep", default="", help="comma list of source track ids to copy verbatim (hand-edited)")
    d.add_argument("--first_id", type=int, default=200)
    d.add_argument("--eps", type=float, default=8.0, help="DP tolerance px on smoothed corners")
    d.add_argument("--k_med", type=int, default=5)
    d.add_argument("--k_avg", type=int, default=11)
    d.add_argument("--smooth", choices=["sg", "avg"], default="sg")
    d.add_argument("--max_gap", type=int, default=0, help="max frames between keyframes (0 = DP only)")
    d.add_argument("--report", required=True)
    d.add_argument("--force", action="store_true")
    args = ap.parse_args()
    {"tomot": cmd_tomot, "edit": cmd_edit, "renumber": cmd_renumber, "rekey": cmd_rekey}[args.cmd](args)


if __name__ == "__main__":
    main()
