"""Step 23 -- verify / fix FastLabeler keyframes with Claude vision (the keyframes decide the
whole label: the app interpolates linearly between them, so only the keyframes need to be right).

run    for every non-outside keyframe of the given tracks: crop the frame around the box, draw the
       box (A, green) + up to 3 detector candidates (B/C/D), add reference crops of the same track
       (track start + previous keyframe), ask Claude: same person? whole body? which box is best?
       -> JSONL verdicts (resumable: already-judged keyframes are skipped) + crop jpgs for review.
apply  verdicts -> script-18 edits (set_box when B/C/D or a model box is better) + review.md of
       keyframes flagged as wrong person / person not visible / low confidence.

  PY=.venv/Scripts/python.exe
  $PY scripts/23_keyframe_check.py run --project results/label_MoRongMo/kf/project_base.json \
      --ids 206-220 --out results/label_MoRongMo/kf/chunk1 --workers 8
  $PY scripts/23_keyframe_check.py apply --project ... --verdicts results/label_MoRongMo/kf/chunk1/verdicts.jsonl \
      --out results/label_MoRongMo/kf/chunk1
Frame numbers are DISPLAY numbers (1-based); the jpg for F is images/frame_{F-35068:06d}.jpg.
"""
import argparse
import base64
import csv
import json
import os
import re
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGES = os.path.join(ROOT, "dataset", "MoRongMo", "app_35068_56611", "images")
START = 35068
DETS = os.path.join(ROOT, "results", "label_MoRongMo", "dets_conf010.csv")
MODEL = "claude-opus-5-5"
COLORS = {"A": (0, 255, 0), "B": (0, 165, 255), "C": (255, 255, 0), "D": (255, 0, 255)}

SYSTEM = """You check bounding-box KEYFRAMES for a person-tracking dataset (coal-mine workers in blue uniforms with helmets, fixed camera, 2688x1520 video). The labeling tool interpolates linearly between keyframes, so a keyframe box must be exactly right.

Box rule: one box = the WHOLE person: helmet/head to shoes, including arms (also outstretched) and legs; TIGHT: every edge within a few pixels of the body - a box with a margin of more than ~5% of the body size on any side is loose and must be fixed. If another person or object passes in front of a standing person, keep the full body box (the hidden part is still labeled); only cut the box at the image border. A box that cuts off the head, legs or feet, that is loose, or that covers two people, is wrong.

You get: reference crop(s) of the person this track follows (earlier keyframes of the same track), then the MAIN image with the current keyframe box A (green, thick) and sometimes alternative detector boxes B (orange), C (cyan), D (magenta). Letters are drawn at the top-left corner of each box.

Answer with ONE JSON object only, no prose:
{"person_visible": true|false,            // is the reference person visible in the main image at all
 "same_person": true|false,               // is box A on the reference person (false = A follows someone else / background)
 "a_full_body": true|false,               // does A satisfy the box rule for the person it is on
 "best": "A"|"B"|"C"|"D"|"none",          // the box that best satisfies the rule for the REFERENCE person; "none" if no drawn box is acceptable (ideal box would overlap it < ~90%, e.g. loose or cut)
 "box": [x1,y1,x2,y2] | null,             // ONLY when best is "none" and the reference person is visible: your own TIGHT whole-body box for the reference person, in pixel coordinates of the MAIN image as sent to you
 "confidence": 0.0-1.0,
 "note": "<= 12 words"}
Prefer A when A and the best alternative are both acceptable (ties go to A)."""


def load_key():
    p = os.path.join(ROOT, ".env")
    txt = open(p, encoding="utf-8").read().strip()
    for line in txt.splitlines():
        if "ANTHROPIC_API_KEY" in line and "=" in line:
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return txt.split("=", 1)[1].strip() if "=" in txt else txt


def frame_path(F):
    return os.path.join(IMAGES, f"frame_{F - START:06d}.jpg")


def iou(a, b):
    ax2, ay2, bx2, by2 = a[0] + a[2], a[1] + a[3], b[0] + b[2], b[1] + b[3]
    iw = max(0.0, min(ax2, bx2) - max(a[0], b[0])); ih = max(0.0, min(ay2, by2) - max(a[1], b[1]))
    i = iw * ih
    return i / (a[2] * a[3] + b[2] * b[3] - i + 1e-9)


def load_dets(path, conf_min=0.15):
    d = defaultdict(list)
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            if float(r["conf"]) >= conf_min:
                d[int(r["frame"])].append((float(r["x"]), float(r["y"]), float(r["w"]), float(r["h"]), float(r["conf"])))
    return d


def parse_ids(s, tracks):
    out = []
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-")
            out += [str(i) for i in range(int(a), int(b) + 1) if str(i) in tracks]
        elif part in tracks:
            out.append(part)
    return out


def keyframes(tr):
    """[(F display, [x,y,w,h])] for non-outside keyframes, sorted."""
    out = []
    for k, v in tr["keyframes"].items():
        if not v.get("outside"):
            out.append((int(k) + 1, [v["x"], v["y"], v["w"], v["h"]]))
    return sorted(out)


def crop_main(img, A, cands, max_side=900):
    H, W = img.shape[:2]
    x, y, w, h = A
    allb = [A] + [c[:4] for c in cands.values()]
    x1 = min(b[0] for b in allb); y1 = min(b[1] for b in allb)
    x2 = max(b[0] + b[2] for b in allb); y2 = max(b[1] + b[3] for b in allb)
    mx, my = max(90.0, 0.45 * w), max(90.0, 0.25 * h)
    cx1, cy1 = int(max(0, x1 - mx)), int(max(0, y1 - my))
    cx2, cy2 = int(min(W, x2 + mx)), int(min(H, y2 + my))
    crop = img[cy1:cy2, cx1:cx2].copy()
    s = min(1.0, max_side / max(crop.shape[:2]))
    if s < 1.0:
        crop = cv2.resize(crop, (int(crop.shape[1] * s), int(crop.shape[0] * s)), interpolation=cv2.INTER_AREA)

    def draw(b, letter, thick):
        p1 = (int((b[0] - cx1) * s), int((b[1] - cy1) * s)); p2 = (int((b[0] + b[2] - cx1) * s), int((b[1] + b[3] - cy1) * s))
        cv2.rectangle(crop, p1, p2, COLORS[letter], thick)
        (tw, th), _ = cv2.getTextSize(letter, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
        cv2.rectangle(crop, (p1[0], p1[1]), (p1[0] + tw + 6, p1[1] + th + 8), COLORS[letter], -1)
        cv2.putText(crop, letter, (p1[0] + 3, p1[1] + th + 3), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    for letter, c in cands.items():
        draw(c[:4], letter, 2)
    draw(A, "A", 3)
    return crop, (cx1, cy1, s)


def crop_ref(img, b, height=360):
    H, W = img.shape[:2]
    x, y, w, h = b
    mx, my = max(20.0, 0.12 * w), max(20.0, 0.06 * h)
    x1, y1 = int(max(0, x - mx)), int(max(0, y - my)); x2, y2 = int(min(W, x + w + mx)), int(min(H, y + h + my))
    crop = img[y1:y2, x1:x2].copy()
    s = min(1.0, height / max(1, crop.shape[0]))
    if s < 1.0:
        crop = cv2.resize(crop, (max(1, int(crop.shape[1] * s)), int(crop.shape[0] * s)), interpolation=cv2.INTER_AREA)
    p1 = (int((x - x1) * s), int((y - y1) * s)); p2 = (int((x + w - x1) * s), int((y + h - y1) * s))
    cv2.rectangle(crop, p1, p2, (0, 255, 0), 2)
    return crop


def b64(img):
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.standard_b64encode(buf.tobytes()).decode()


def pick_candidates(A, dets_F, n=3):
    cands = []
    for d in sorted(dets_F, key=lambda d: -d[4]):
        v = iou(A, d[:4])
        if v < 0.2 or v > 0.95:
            continue
        if any(iou(c[:4], d[:4]) > 0.9 for c in cands):
            continue
        cands.append(d)
        if len(cands) == n:
            break
    return {letter: list(c) for letter, c in zip("BCD", cands)}


def ask(client, refs, main, main_shape, nid, F, ref_desc):
    content = []
    for i, (desc, img) in enumerate(refs):
        content.append({"type": "text", "text": f"Reference {i + 1} ({desc}):"})
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64(img)}})
    content.append({"type": "text", "text": f"MAIN image ({main_shape[1]}x{main_shape[0]} px), track {nid}, frame {F}. {ref_desc} Judge box A."})
    content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64(main)}})
    content.append({"type": "text", "text": "Reply with the JSON object only."})
    resp = client.messages.create(
        model=MODEL, max_tokens=2500,
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": content}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    m = re.search(r"\{.*\}", text, re.S)
    verdict = json.loads(m.group(0)) if m else None
    usage = {"in": resp.usage.input_tokens, "out": resp.usage.output_tokens,
             "cache_read": getattr(resp.usage, "cache_read_input_tokens", 0) or 0,
             "cache_write": getattr(resp.usage, "cache_creation_input_tokens", 0) or 0}
    return verdict, text, usage, resp.stop_reason


def cmd_run(args):
    import anthropic
    client = anthropic.Anthropic(api_key=load_key(), max_retries=5)
    project = json.load(open(args.project, encoding="utf-8"))
    tracks = project["tracks"]
    ids = parse_ids(args.ids, tracks)
    dets = load_dets(args.dets)
    os.makedirs(os.path.join(args.out, "crops"), exist_ok=True)
    vpath = os.path.join(args.out, "verdicts.jsonl")
    done = set()
    if os.path.exists(vpath):
        for line in open(vpath, encoding="utf-8"):
            try:
                r = json.loads(line)
                if r.get("verdict") is not None:
                    done.add((r["id"], r["F"]))
            except Exception:
                pass
    jobs = []
    for nid in ids:
        kfs = keyframes(tracks[nid])
        if args.max_kf:
            kfs = kfs[:args.max_kf]
        for i, (F, A) in enumerate(kfs):
            if (nid, F) in done:
                continue
            refs = []
            if i > 0:
                refs.append(("track start", kfs[0]))
                if i > 1 and kfs[i - 1][0] != kfs[0][0]:
                    refs.append(("previous keyframe", kfs[i - 1]))
            elif len(kfs) > 1:
                refs.append(("next keyframe of the same track", kfs[1]))
            jobs.append((nid, i, F, A, refs, len(kfs)))
    print(f"{len(ids)} tracks, {len(jobs)} keyframes to judge ({len(done)} already done) -> {vpath}", flush=True)
    lock = threading.Lock()
    tot = {"in": 0, "out": 0, "cache_read": 0, "n": 0, "err": 0}

    def work(job):
        nid, i, F, A, refs, nkf = job
        img = cv2.imread(frame_path(F))
        if img is None:
            return {"id": nid, "F": F, "error": "no image"}
        cands = pick_candidates(A, dets.get(F, []))
        main, (cx1, cy1, s) = crop_main(img, A, cands)
        ref_imgs = []
        for desc, (Fr, Br) in refs:
            ri = cv2.imread(frame_path(Fr))
            if ri is not None:
                ref_imgs.append((f"{desc}, frame {Fr}", crop_ref(ri, Br)))
        crop_path = os.path.join(args.out, "crops", f"{nid}_{F}.jpg")
        cv2.imwrite(crop_path, main, [cv2.IMWRITE_JPEG_QUALITY, 80])
        ref_desc = ("Keyframe %d of %d." % (i + 1, nkf)) + ("" if cands else " No alternative boxes.")
        rec = {"id": nid, "src": None, "F": F, "A": A, "cands": cands, "crop": [cx1, cy1, s], "crop_path": crop_path, "kf_index": i, "n_kf": nkf}
        try:
            verdict, text, usage, stop = ask(client, ref_imgs, main, main.shape, nid, F, ref_desc)
            rec.update(verdict=verdict, raw=text, usage=usage, stop_reason=stop)
            if verdict and verdict.get("box"):
                bx = verdict["box"]
                rec["box_full"] = [cx1 + bx[0] / s, cy1 + bx[1] / s, (bx[2] - bx[0]) / s, (bx[3] - bx[1]) / s]
        except Exception as e:  # noqa: BLE001
            rec.update(verdict=None, error=f"{type(e).__name__}: {e}"[:300])
        return rec

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex, open(vpath, "a", encoding="utf-8") as fout:
        futs = [ex.submit(work, j) for j in jobs]
        for k, fut in enumerate(as_completed(futs), 1):
            rec = fut.result()
            with lock:
                fout.write(json.dumps(rec) + "\n"); fout.flush()
                u = rec.get("usage")
                if u:
                    tot["in"] += u["in"]; tot["out"] += u["out"]; tot["cache_read"] += u["cache_read"]; tot["n"] += 1
                if rec.get("verdict") is None:
                    tot["err"] += 1
                if k % 25 == 0 or k == len(jobs):
                    print(f"  {k}/{len(jobs)} done, {tot['err']} errors, tokens in {tot['in']} (+{tot['cache_read']} cached) out {tot['out']}, "
                          f"{time.time() - t0:.0f}s", flush=True)
    cost = tot["in"] * 4e-6 + tot["cache_read"] * 0.2e-6 + tot["out"] * 20e-6
    print(f"done: {tot['n']} judged, {tot['err']} errors, est. cost ${cost:.2f}")


def cmd_apply(args):
    project = json.load(open(args.project, encoding="utf-8"))
    recs = {}
    for line in open(args.verdicts, encoding="utf-8"):
        try:
            r = json.loads(line)
        except ValueError:
            continue  # a line torn by concurrent writers
        if r.get("verdict") is not None:
            recs[(r["id"], r["F"])] = r  # last wins
    edits, review, counts = [], [], defaultdict(int)
    for (nid, F), r in sorted(recs.items(), key=lambda kv: (int(kv[0][0]), kv[0][1])):
        v = r["verdict"]; best = v.get("best", "A"); conf = float(v.get("confidence", 0) or 0)
        flag = None
        if not v.get("person_visible", True):
            flag = "not visible"
        elif v.get("same_person") is False:
            flag = "wrong person"
        elif best in r.get("cands", {}) and conf >= args.min_conf:
            edits.append({"op": "set_box", "id": int(nid), "frame": F, "xywh": [round(x, 2) for x in r["cands"][best][:4]],
                          "why": f"best={best} conf={conf:.2f} {v.get('note', '')}"})
            counts["swapped"] += 1
        elif best == "none" and r.get("box_full") and conf >= args.min_conf:
            bf = r["box_full"]
            if bf[2] > 20 and bf[3] > 40 and iou(bf, r["A"]) > 0.2:
                edits.append({"op": "set_box", "id": int(nid), "frame": F, "xywh": [round(x, 2) for x in bf],
                              "why": f"model box conf={conf:.2f} {v.get('note', '')}"})
                counts["model_box"] += 1
            else:
                flag = "model box implausible"
        elif best != "A" and conf < args.min_conf:
            flag = f"low confidence ({best})"
        elif best == "A" and not v.get("a_full_body", True):
            flag = "A not full body, no alternative"
        if flag:
            review.append((nid, F, flag, v, r.get("crop_path")))
            counts[flag.split(" (")[0]] += 1
        else:
            counts["ok" if best == "A" else "fixed"] += 1
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "edits_auto.json"), "w", encoding="utf-8") as f:
        json.dump(edits, f, indent=1)
    with open(os.path.join(args.out, "review.md"), "w", encoding="utf-8") as f:
        f.write(f"# Keyframes to review ({len(review)})\n\n| id | frame | flag | best | conf | note | crop |\n|---|---|---|---|---|---|---|\n")
        for nid, F, flag, v, cp in review:
            f.write(f"| {nid} | {F} | {flag} | {v.get('best')} | {v.get('confidence')} | {v.get('note', '')} | {cp} |\n")
    print(f"{len(recs)} verdicts: {dict(counts)}; {len(edits)} auto edits -> {args.out}/edits_auto.json; "
          f"{len(review)} to review -> {args.out}/review.md")


REVIEW_SYSTEM = """You review a person-tracking label TRACK (coal-mine workers, fixed camera). You get the reference crop of the person the track follows (its first keyframe) and a strip of consecutive keyframe crops of that track; in each tile the green box A is the track's keyframe box, the tile label is the frame number, a '*' marks keyframes a first-pass check flagged (wrong person / not visible / low confidence). Keyframes are interpolated linearly in between, so a bad keyframe corrupts its neighbourhood.

Decide what to do with this window. Answer ONE JSON object only:
{"actions": [ {"type":"keep"} |
              {"type":"split","frame":F}            // from keyframe F onward the box follows a DIFFERENT person and stays on them: cut the track there (the rest becomes a new id)
            | {"type":"clear","lo":F1,"hi":F2}      // keyframes F1..F2 (inclusive) are on the wrong person / garbage / the person is hidden, but the track is back on the right person afterwards: drop them so interpolation bridges the gap
            | {"type":"end","frame":F}              // the person is gone from keyframe F to the end of the strip and the strip ends the track: end the track at F
            ],
 "confidence": 0.0-1.0,
 "note": "<= 20 words"}
Use the frame numbers printed on the tiles. Several actions are allowed (e.g. clear then split). When the flagged tiles actually look fine (same person, box acceptable), answer keep."""


def cmd_review(args):
    """Second API pass for flagged keyframes: one question per cluster of flags on a track, with a
    strip of the track's consecutive keyframe crops -> edits_review.json (split/clear/end ops)."""
    import anthropic
    client = anthropic.Anthropic(api_key=load_key(), max_retries=5)
    project = json.load(open(args.project, encoding="utf-8"))
    W, H = project["video_source"]["size"]
    recs = {}
    if os.path.exists(args.verdicts):
        for line in open(args.verdicts, encoding="utf-8"):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("verdict") is not None:
                recs[(r["id"], r["F"])] = r
    kf_box = {nid: dict(keyframes(tr)) for nid, tr in project["tracks"].items()}
    flagged = defaultdict(list)
    for (nid, F), r in recs.items():
        v = r["verdict"]
        bad = (not v.get("person_visible", True)) or v.get("same_person") is False or \
            (v.get("best", "A") != "A" and float(v.get("confidence", 0) or 0) < args.min_conf) or \
            (v.get("best") == "none" and not r.get("box_full"))
        if bad:
            flagged[nid].append(F)
    crops_dir = os.path.join(os.path.dirname(args.verdicts), "crops")
    out_dir = args.out; os.makedirs(os.path.join(out_dir, "strips"), exist_ok=True)
    next_id = [args.first_new_id]
    ops, log = [], []
    jobs = []
    if args.sweep:  # identity sweep: every track, consecutive windows of keyframes, no flags needed
        ids = parse_ids(args.ids, project["tracks"]) if args.ids else sorted(project["tracks"], key=int)
        for nid in ids:
            kfs = [F for F, _ in keyframes(project["tracks"][nid])]
            step = max(1, args.max_tiles - 2)
            for lo in range(0, max(1, len(kfs) - 2), step):
                win = kfs[lo:lo + args.max_tiles]
                jobs.append((nid, [], win, lo + args.max_tiles >= len(kfs), kfs[0]))
                if lo + args.max_tiles >= len(kfs):
                    break
    for nid, Fs in ([] if args.sweep else flagged.items()):
        kfs = [F for F, _ in keyframes(project["tracks"][nid])]
        idx = {F: i for i, F in enumerate(kfs)}
        Fs = sorted(F for F in Fs if F in idx)
        clusters, cur = [], []
        for F in Fs:
            if cur and idx[F] - idx[cur[-1]] > 4:
                clusters.append(cur); cur = []
            cur.append(F)
        if cur:
            clusters.append(cur)
        for cl in clusters:
            lo, hi = max(0, idx[cl[0]] - 3), min(len(kfs) - 1, idx[cl[-1]] + 3)
            win = kfs[lo:hi + 1]
            if len(win) > args.max_tiles:  # keep flagged ones + context, thin the middle
                keep = set(cl) | set(kfs[lo:lo + 2]) | set(kfs[hi - 1:hi + 1])
                step = max(1, len(win) // args.max_tiles)
                win = [F for i, F in enumerate(win) if F in keep or i % step == 0][:args.max_tiles]
            jobs.append((nid, cl, win, hi == len(kfs) - 1, kfs[0]))

    def work(job):
        nid, cl, win, is_tail, F0 = job
        tiles = []
        for F in win:
            im = cv2.imread(os.path.join(crops_dir, f"{nid}_{F}.jpg"))
            if im is None and F in kf_box.get(nid, {}):  # no saved crop (keyframes changed): render from the frame
                fr = cv2.imread(frame_path(F))
                if fr is not None:
                    im, _ = crop_main(fr, kf_box[nid][F], {})
            if im is None:
                continue
            s = 300.0 / im.shape[0]; im = cv2.resize(im, (max(1, int(im.shape[1] * s)), 300))
            lab = f"{F}{'*' if F in cl else ''}"
            cv2.rectangle(im, (0, 0), (12 + 11 * len(lab), 22), (0, 0, 0), -1)
            cv2.putText(im, lab, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255) if F in cl else (255, 255, 255), 1)
            tiles.append(im)
        if not tiles:
            return {"id": nid, "flags": cl, "error": "no tiles"}
        W = max(t.shape[1] for t in tiles); per = max(1, min(len(tiles), 1400 // W))
        tiles = [cv2.copyMakeBorder(t, 0, 2, 0, W - t.shape[1] + 2, cv2.BORDER_CONSTANT, value=(40, 40, 40)) for t in tiles]
        rows = []
        for k in range(0, len(tiles), per):
            rr = tiles[k:k + per]; rr += [np.full(rr[0].shape, 40, np.uint8)] * (per - len(rr)); rows.append(np.hstack(rr))
        strip = np.vstack(rows)
        sp = os.path.join(out_dir, "strips", f"{nid}_{(cl or win)[0]}.jpg"); cv2.imwrite(sp, strip, [cv2.IMWRITE_JPEG_QUALITY, 80])
        ref = cv2.imread(os.path.join(crops_dir, f"{nid}_{F0}.jpg"))
        if ref is None and F0 in kf_box.get(nid, {}):
            fr = cv2.imread(frame_path(F0))
            if fr is not None:
                ref, _ = crop_main(fr, kf_box[nid][F0], {})
        content = []
        if ref is not None:
            rs = 320.0 / ref.shape[0]; ref = cv2.resize(ref, (max(1, int(ref.shape[1] * rs)), 320))
            content += [{"type": "text", "text": f"Reference: track {nid} at its first keyframe (frame {F0}), the person to follow is in the green box A."},
                        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64(ref)}}]
        notes = "; ".join(f"{F}: {recs[(nid, F)]['verdict'].get('note', '')}" for F in cl if (nid, F) in recs)
        ask_txt = (f"Flagged keyframes: {cl}. First-pass notes: {notes}" if cl else
                   "No keyframe is flagged: this is an IDENTITY sweep. Check that every tile's box A is on the reference person "
                   "and the person is visible; report the first frame where the box follows a different person (split), "
                   "frames where the box holds no person / the wrong one briefly (clear), or where the person is gone until the end (end).")
        content += [{"type": "text", "text": f"Strip of consecutive keyframes of track {nid}, frames {win[0]}..{win[-1]} "
                     f"({'this is the END of the track' if is_tail else 'the track continues after this strip'}). {ask_txt}"},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64(strip)}},
                    {"type": "text", "text": "Reply with the JSON object only."}]
        try:
            resp = client.messages.create(model=MODEL, max_tokens=4000, output_config={"effort": "high"},
                                          system=[{"type": "text", "text": REVIEW_SYSTEM, "cache_control": {"type": "ephemeral"}}],
                                          messages=[{"role": "user", "content": content}])
            text = "".join(b.text for b in resp.content if b.type == "text")
            m = re.search(r"\{.*\}", text, re.S)
            return {"id": nid, "flags": cl, "window": win, "tail": is_tail, "strip": sp,
                    "decision": json.loads(m.group(0)) if m else None, "raw": text,
                    "usage": {"in": resp.usage.input_tokens, "out": resp.usage.output_tokens}}
        except Exception as e:  # noqa: BLE001
            return {"id": nid, "flags": cl, "window": win, "strip": sp, "decision": None, "error": f"{type(e).__name__}: {e}"[:300]}

    print(f"{sum(len(v) for v in flagged.values())} flagged keyframes on {len(flagged)} tracks -> {len(jobs)} questions", flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        log = list(ex.map(work, jobs))
    # confirm low-confidence non-keep decisions with a wider window; accept only if both agree
    confirm = []
    for res in log:
        d = res.get("decision") or {}
        acts = [a for a in d.get("actions", []) if a.get("type") != "keep"]
        conf = float(d.get("confidence", 0) or 0)
        if acts and args.min_conf - 0.3 <= conf < args.min_conf:
            kfs = [F for F, _ in keyframes(project["tracks"][res["id"]])]
            i0, i1 = kfs.index(res["window"][0]), kfs.index(res["window"][-1])
            win = kfs[max(0, i0 - 4):i1 + 5]
            step = max(1, len(win) // args.max_tiles)
            win = [F for i, F in enumerate(win) if i % step == 0 or F in res["window"][:1] + res["window"][-1:]][:args.max_tiles]
            confirm.append((res, (res["id"], [], win, i1 + 5 >= len(kfs), kfs[0])))
    if confirm:
        print(f"re-asking {len(confirm)} low-confidence decisions with a wider window", flush=True)
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            second = list(ex.map(work, [j for _, j in confirm]))
        for (res, _), res2 in zip(confirm, second):
            d1, d2 = res["decision"], res2.get("decision") or {}
            ok = False
            for a1 in d1.get("actions", []):
                for a2 in d2.get("actions", []):
                    if a1.get("type") == a2.get("type") and abs(int(a1.get("frame", a1.get("lo", 0))) - int(a2.get("frame", a2.get("lo", 0)))) <= 60:
                        ok = True
            res["confirm"] = {"decision": d2, "agree": ok}
            if ok:
                d1["confidence"] = max(float(d1.get("confidence", 0) or 0), args.min_conf)
                d1["note"] = (d1.get("note", "") + " [confirmed: " + d2.get("note", "") + "]")[:200]
    if True:
        for res in log:
            d = res.get("decision")
            if not d:
                continue
            for a in d.get("actions", []):
                t = a.get("type")
                if t == "split" and a.get("frame") and float(d.get("confidence", 0) or 0) >= args.min_conf:
                    ops.append({"op": "split", "id": int(res["id"]), "frame": int(a["frame"]), "new_id": next_id[0], "why": d.get("note", "")})
                    next_id[0] += 1
                elif t == "clear" and a.get("lo") and float(d.get("confidence", 0) or 0) >= args.min_conf:
                    ops.append({"op": "clear_range", "id": int(res["id"]), "lo": int(a["lo"]), "hi": int(a.get("hi", a["lo"])), "why": d.get("note", "")})
                elif t == "end" and a.get("frame") and float(d.get("confidence", 0) or 0) >= args.min_conf:
                    ops.append({"op": "end", "id": int(res["id"]), "frame": int(a["frame"]), "why": d.get("note", "")})
    seen, uniq = set(), []  # overlapping windows may repeat an op
    for o in ops:
        key = (o["op"], o["id"], o.get("frame"), o.get("lo"), o.get("hi"))
        if key not in seen:
            seen.add(key); uniq.append(o)
    ops = uniq
    tag = "sweep" if args.sweep else "review"
    with open(os.path.join(out_dir, f"{tag}_api.jsonl"), "w", encoding="utf-8") as f:
        for r in log:
            f.write(json.dumps(r) + "\n")
    with open(os.path.join(out_dir, f"edits_{tag}.json"), "w", encoding="utf-8") as f:
        json.dump(ops, f, indent=1)
    kinds = defaultdict(int)
    for o in ops:
        kinds[o["op"]] += 1
    n_err = sum(1 for r in log if r.get("decision") is None)
    print(f"{len(log)} answers ({n_err} failed): ops {dict(kinds)} -> {out_dir}/edits_{tag}.json; next free id {next_id[0]}")


FIX_SYSTEM = """You check person-tracking labels (coal-mine workers, fixed camera, 2688x1520). Label rule: a box covers the WHOLE person (helmet to shoes, arms included) even when another person or object passes in front and hides part of them - a standing person keeps their full box while occluded. The box shrinks only when the person really changes pose (crouches, sits, bends), moves, or leaves the image edge. Answer with ONE JSON object only."""


def _tile(img, region, boxes, label, height=300):
    """crop `region` [x1,y1,x2,y2] of img, draw boxes [(box_xywh, color, thick)], label top-left."""
    x1, y1, x2, y2 = [int(v) for v in region]
    crop = img[y1:y2, x1:x2].copy()
    s = height / max(1, crop.shape[0]); crop = cv2.resize(crop, (max(1, int(crop.shape[1] * s)), height))
    for b, col, t in boxes:
        cv2.rectangle(crop, (int((b[0] - x1) * s), int((b[1] - y1) * s)), (int((b[0] + b[2] - x1) * s), int((b[1] + b[3] - y1) * s)), col, t)
    cv2.rectangle(crop, (0, 0), (12 + 11 * len(label), 22), (0, 0, 0), -1)
    cv2.putText(crop, label, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
    return crop


def _strip(tiles, max_w=1500):
    W = max(t.shape[1] for t in tiles); per = max(1, min(len(tiles), max_w // W))
    tiles = [cv2.copyMakeBorder(t, 0, 2, 0, W - t.shape[1] + 2, cv2.BORDER_CONSTANT, value=(40, 40, 40)) for t in tiles]
    rows = []
    for k in range(0, len(tiles), per):
        rr = tiles[k:k + per]; rr += [np.full(rr[0].shape, 40, np.uint8)] * (per - len(rr)); rows.append(np.hstack(rr))
    return np.vstack(rows)


def _ask_json(client, system, content, max_tokens=4000):
    resp = client.messages.create(model=MODEL, max_tokens=max_tokens, output_config={"effort": "high"},
                                  system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                                  messages=[{"role": "user", "content": content + [{"type": "text", "text": "Reply with the JSON object only."}]}])
    text = "".join(b.text for b in resp.content if b.type == "text")
    m = re.search(r"\{.*\}", text, re.S)
    return (json.loads(m.group(0)) if m else None), text


def _region(boxes, W, H, mx=0.4, my=0.25):
    x1 = min(b[0] for b in boxes); y1 = min(b[1] for b in boxes)
    x2 = max(b[0] + b[2] for b in boxes); y2 = max(b[1] + b[3] for b in boxes)
    w, h = x2 - x1, y2 - y1
    return [max(0, x1 - max(60, mx * w)), max(0, y1 - max(60, my * h)), min(W, x2 + max(60, mx * w)), min(H, y2 + max(60, my * h))]


def shrink_candidates(kfs, W, H):
    """[(F, cur_box, proposed_box, refF)] where the box shrank from the bottom/side while the top
    stayed (occlusion), measured against the last 'full' keyframe."""
    out = []
    ref, refF = kfs[0][1], kfs[0][0]
    for F, b in kfs[1:]:
        rx1, ry1, rw, rh = ref; rx2, ry2 = rx1 + rw, ry1 + rh
        x1, y1, w, h = b; x2, y2 = x1 + w, y1 + h
        top_stable = abs(y1 - ry1) < 0.08 * rh and abs((x1 + x2) / 2 - (rx1 + rx2) / 2) < 0.4 * rw
        bottom_up = (ry2 - y2) > 0.10 * rh and ry2 < H - 4
        left_in = (x1 - rx1) > 0.2 * rw and abs(x2 - rx2) < 0.12 * rw and rx1 > 4
        right_in = (rx2 - x2) > 0.2 * rw and abs(x1 - rx1) < 0.12 * rw and rx2 < W - 4
        if top_stable and (bottom_up or left_in or right_in):
            p = [x1, y1, x2, y2]
            if bottom_up:
                p[3] = ry2
            if left_in:
                p[0] = rx1
            if right_in:
                p[2] = rx2
            out.append((F, b, [p[0], p[1], p[2] - p[0], p[3] - p[1]], refF))
        else:
            ref, refF = b, F
    return out


def cmd_unshrink(args):
    """Occlusion shrink: standing person, box bottom/side pulled in while the top stays. Geometry
    proposes the restored full box, Claude confirms per cluster (strip: reference keyframe + the
    shrunken keyframes with current box orange and proposed box green) -> edits_unshrink.json."""
    import anthropic
    client = anthropic.Anthropic(api_key=load_key(), max_retries=5)
    project = json.load(open(args.project, encoding="utf-8"))
    W, H = project["video_source"]["size"]
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    os.makedirs(os.path.join(args.out, "strips"), exist_ok=True)
    jobs = []
    for nid, tr in project["tracks"].items():
        if nid in skip:
            continue
        kfs = keyframes(tr)
        if len(kfs) < 2:
            continue
        kf_box = dict(kfs)
        cands = shrink_candidates(kfs, W, H)
        cl = []
        for c in cands:  # cluster by reference keyframe
            if cl and c[3] != cl[-1][3]:
                jobs.append((nid, cl, kf_box)); cl = []
            cl.append(c)
        if cl:
            jobs.append((nid, cl, kf_box))
    print(f"{sum(len(j[1]) for j in jobs)} shrunken keyframes in {len(jobs)} clusters on {len({j[0] for j in jobs})} tracks", flush=True)

    def work(job):
        nid, cl, kf_box = job
        refF = cl[0][3]; refb = kf_box[refF]
        region = _region([refb] + [c[1] for c in cl] + [c[2] for c in cl], W, H)
        show = cl if len(cl) <= 12 else [cl[int(i * (len(cl) - 1) / 11)] for i in range(12)]
        tiles = []
        im = cv2.imread(frame_path(refF))
        if im is not None:
            tiles.append(_tile(im, region, [(refb, (0, 255, 0), 2)], f"ref {refF}"))
        for F, b, p, _ in show:
            im = cv2.imread(frame_path(F))
            if im is None:
                continue
            tiles.append(_tile(im, region, [(b, (0, 165, 255), 2), (p, (0, 255, 0), 2)], f"{F}"))
        if len(tiles) < 2:
            return {"id": nid, "frames": [c[0] for c in cl], "decision": None, "error": "no tiles"}
        strip = _strip(tiles)
        sp = os.path.join(args.out, "strips", f"unshrink_{nid}_{cl[0][0]}.jpg"); cv2.imwrite(sp, strip, [cv2.IMWRITE_JPEG_QUALITY, 80])
        content = [{"type": "text", "text":
                    f"Track {nid}. First tile: reference keyframe {refF} with its full box (green). Next tiles: later keyframes "
                    f"(frame number on the tile) where the box got smaller: CURRENT box orange, PROPOSED restored full box green "
                    f"(bottom/side taken from the reference). Frames shown: {[c[0] for c in show]}.\n"
                    "For each shown frame decide: is the person still standing at the same spot in the same pose, only partly "
                    "hidden by someone/something (-> the green restored box is right), or did they really crouch/sit/move/leave "
                    "so the orange box is right?\n"
                    '{"restore_frames": [frames where green is right], "keep_frames": [frames where orange is right], '
                    '"confidence": 0.0-1.0, "note": "<= 20 words"}'},
                   {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64(strip)}}]
        try:
            d, text = _ask_json(client, FIX_SYSTEM, content)
            return {"id": nid, "frames": [c[0] for c in cl], "shown": [c[0] for c in show], "strip": sp, "decision": d, "raw": text}
        except Exception as e:  # noqa: BLE001
            return {"id": nid, "frames": [c[0] for c in cl], "strip": sp, "decision": None, "error": f"{type(e).__name__}: {e}"[:300]}

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        log = list(ex.map(work, jobs))
    ops = []
    prop = {(j[0], c[0]): c[2] for j in jobs for c in j[1]}
    for res, job in zip(log, jobs):
        d = res.get("decision")
        if not d or float(d.get("confidence", 0) or 0) < args.min_conf:
            continue
        rf = set(int(f) for f in d.get("restore_frames", []) or [])
        shown = set(res.get("shown", []))
        all_frames = [c[0] for c in job[1]]
        if rf and rf >= shown:  # every shown frame restored -> whole cluster
            target = all_frames
        else:
            target = [F for F in all_frames if F in rf]
        for F in target:
            p = prop[(res["id"], F)]
            ops.append({"op": "set_box", "id": int(res["id"]), "frame": F, "xywh": [round(v, 2) for v in p], "why": d.get("note", "")})
    with open(os.path.join(args.out, "unshrink_api.jsonl"), "w", encoding="utf-8") as f:
        for r in log:
            f.write(json.dumps(r) + "\n")
    with open(os.path.join(args.out, "edits_unshrink.json"), "w", encoding="utf-8") as f:
        json.dump(ops, f, indent=1)
    n_err = sum(1 for r in log if r.get("decision") is None)
    print(f"{len(log)} clusters answered ({n_err} failed): {len(ops)} keyframes restored -> {args.out}/edits_unshrink.json")


def cmd_extend(args):
    """Track ends inside the image: is the person still there (hidden) after the last keyframe? Probe
    frames after the end (+10..+150) in the same region; if a later track starts at that spot, ask
    whether it is the same person -> merge; else hold the box until the person is gone -> extend."""
    import anthropic
    client = anthropic.Anthropic(api_key=load_key(), max_retries=5)
    project = json.load(open(args.project, encoding="utf-8"))
    W, H = project["video_source"]["size"]
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    os.makedirs(os.path.join(args.out, "strips"), exist_ok=True)
    tracks = project["tracks"]
    kf = {nid: keyframes(tr) for nid, tr in tracks.items() if keyframes(tr)}
    starts = {nid: k[0] for nid, k in kf.items()}
    ends = {nid: k[-1] for nid, k in kf.items()}
    merged_away, ops, log = set(), [], []
    lock = threading.Lock()

    def border(b):
        return b[0] <= 4 or b[1] <= 4 or b[0] + b[2] >= W - 4 or b[1] + b[3] >= H - 4

    def work(nid):
        Fe, b = ends[nid]
        if nid in skip or border(b) or Fe >= args.hi - 10:
            return []
        out, held = [], 0
        for _ in range(8):
            hz = args.horizon
            probes = [F for F in (Fe + 10, Fe + 25, Fe + 50, Fe + 100, Fe + 150, Fe + 250, Fe + hz) if F <= args.hi and F > Fe]
            probes = sorted(set(p for p in probes if p - Fe <= hz))
            cands = sorted(((iou(b, starts[o][1]), o) for o in kf if o != nid and Fe < starts[o][0] <= Fe + hz), reverse=True)
            cand = cands[0][1] if cands and cands[0][0] >= 0.3 else None
            region = _region([b] + ([starts[cand][1]] if cand else []), W, H)
            tiles = []
            im = cv2.imread(frame_path(Fe))
            if im is None:
                break
            tiles.append(_tile(im, region, [(b, (0, 255, 0), 2)], f"last {Fe}"))
            for F in probes:
                im = cv2.imread(frame_path(F))
                if im is not None:
                    tiles.append(_tile(im, region, [(b, (0, 165, 255), 1)], f"{F}"))
            if cand:
                Fc, bc = starts[cand]
                im = cv2.imread(frame_path(Fc))
                if im is not None:
                    tiles.append(_tile(im, region, [(bc, (255, 255, 0), 2)], f"cand {cand} @{Fc}"))
            strip = _strip(tiles)
            sp = os.path.join(args.out, "strips", f"extend_{nid}_{Fe}.jpg"); cv2.imwrite(sp, strip, [cv2.IMWRITE_JPEG_QUALITY, 80])
            txt = (f"Track {nid} ends at frame {Fe} (first tile, green box = its last box). The next tiles show the SAME image "
                   f"region at later frames {probes} with that last box drawn thin orange for reference."
                   + (f" The last tile shows another track ({cand}, cyan box) that starts at frame {Fc} near that spot." if cand else "")
                   + "\nQuestions: (1) up to which of the probe frames is the same person still at that spot (even if partly hidden "
                     "by someone passing)? (2) " + ("is the cyan-box track the same person (so the two tracks should be joined)?" if cand else "n/a")
                   + '\n{"present_until": <probe frame or null if gone already at the first probe>, "gone": true|false (false if still there at the last probe), '
                     '"candidate_same_person": true|false|null, "confidence": 0.0-1.0, "note": "<= 20 words"}')
            try:
                d, text = _ask_json(client, FIX_SYSTEM, [{"type": "text", "text": txt},
                                                         {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64(strip)}}])
            except Exception as e:  # noqa: BLE001
                out.append({"id": nid, "Fe": Fe, "error": f"{type(e).__name__}: {e}"[:300]}); break
            rec = {"id": nid, "Fe": Fe, "cand": cand, "probes": probes, "strip": sp, "decision": d, "raw": text}
            out.append(rec)
            if not d or float(d.get("confidence", 0) or 0) < args.min_conf:
                break
            if cand and d.get("candidate_same_person") and cand not in skip:
                with lock:
                    if cand not in merged_away:
                        merged_away.add(cand)
                        ops.append({"op": "merge", "id": int(nid), "from": int(cand), "why": d.get("note", "")})
                break
            pu = d.get("present_until")
            if not pu:
                break
            pu = int(pu)
            with lock:
                ops.append({"op": "extend", "id": int(nid), "boxes": {str(pu): [round(v, 2) for v in b]}, "why": d.get("note", "")})
            held += 1
            if d.get("gone", True) or pu < probes[-1]:
                break
            Fe = pu  # still there at the last probe: look further
        return out

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for r in ex.map(work, sorted(kf, key=int)):
            log += r
    with open(os.path.join(args.out, "extend_api.jsonl"), "w", encoding="utf-8") as f:
        for r in log:
            f.write(json.dumps(r) + "\n")
    with open(os.path.join(args.out, "edits_extend.json"), "w", encoding="utf-8") as f:
        json.dump(ops, f, indent=1)
    kinds = defaultdict(int)
    for o in ops:
        kinds[o["op"]] += 1
    print(f"{len(log)} questions ({sum(1 for r in log if r.get('decision') is None)} failed): ops {dict(kinds)} -> {args.out}/edits_extend.json")


def cmd_blob(args):
    """Is each track a recognizable person? 3 sample keyframes per track -> delete_track for tracks
    that are only an unrecognizable patch (a back/shoulder fragment, equipment)."""
    import anthropic
    client = anthropic.Anthropic(api_key=load_key(), max_retries=5)
    project = json.load(open(args.project, encoding="utf-8"))
    W, H = project["video_source"]["size"]
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    os.makedirs(os.path.join(args.out, "strips"), exist_ok=True)

    def work(nid):
        kfs = keyframes(project["tracks"][nid])
        if not kfs:
            return None
        pick = sorted({0, len(kfs) // 2, len(kfs) - 1})
        tiles = []
        for i in pick:
            F, b = kfs[i]
            im = cv2.imread(frame_path(F))
            if im is not None:
                tiles.append(_tile(im, _region([b], W, H, 0.3, 0.15), [(b, (0, 255, 0), 2)], f"{F}", 360))
        if not tiles:
            return None
        strip = _strip(tiles)
        sp = os.path.join(args.out, "strips", f"blob_{nid}.jpg"); cv2.imwrite(sp, strip, [cv2.IMWRITE_JPEG_QUALITY, 80])
        txt = (f"Track {nid}: {len(tiles)} sample keyframes (green box). Is the boxed content a RECOGNIZABLE person - a head/helmet, "
               "face, arms or legs, or a clear human silhouette - at least in most samples? Or only an unidentifiable patch (a piece of "
               "back/shoulder, cloth, equipment, glare) that one would not label as a person?\n"
               '{"person": true|false, "confidence": 0.0-1.0, "note": "<= 15 words"}')
        try:
            d, text = _ask_json(client, FIX_SYSTEM, [{"type": "text", "text": txt},
                                                     {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64(strip)}}])
            return {"id": nid, "frames": [kfs[i][0] for i in pick], "strip": sp, "decision": d, "raw": text}
        except Exception as e:  # noqa: BLE001
            return {"id": nid, "strip": sp, "decision": None, "error": f"{type(e).__name__}: {e}"[:300]}

    ids = [nid for nid in sorted(project["tracks"], key=int) if nid not in skip]
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        log = [r for r in ex.map(work, ids) if r]
    ops, doubt = [], []
    for r in log:
        d = r.get("decision") or {}
        if d and d.get("person") is False:
            if float(d.get("confidence", 0) or 0) >= args.min_conf:
                ops.append({"op": "delete_track", "id": int(r["id"]), "why": d.get("note", "")})
            else:
                doubt.append((r["id"], d.get("confidence"), d.get("note")))
    with open(os.path.join(args.out, "blob_api.jsonl"), "w", encoding="utf-8") as f:
        for r in log:
            f.write(json.dumps(r) + "\n")
    with open(os.path.join(args.out, "edits_blob.json"), "w", encoding="utf-8") as f:
        json.dump(ops, f, indent=1)
    print(f"{len(log)} tracks judged: delete {[o['id'] for o in ops]}; doubtful {doubt} -> {args.out}/edits_blob.json")


def _m18():
    import importlib.util
    spec = importlib.util.spec_from_file_location("m18", os.path.join(os.path.dirname(os.path.abspath(__file__)), "18_project_edit.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def cmd_misses(args):
    """People the labels miss: detector boxes (conf >= --conf) not covered by any label box, linked
    into tracklets (IoU >= 0.4, gaps <= 15 frames); tracklets with >= --min_det detections become
    new tracks (smoothed + Douglas-Peucker keyframes) appended to the project."""
    m18 = _m18()
    project = json.load(open(args.project, encoding="utf-8"))
    W, H = project["video_source"]["size"]; n_images = len(project["images"])
    rows = m18.project_to_rows(project, args.lo, args.hi)
    labels = defaultdict(list)
    for F, oid, x, y, w, h, vis, src in rows:
        labels[F].append((x, y, w, h))
    dets = load_dets(args.dets, args.conf)
    tracklets, active = [], []  # active: [last_F, last_box, [(F, box)]]
    for F in range(args.lo, args.hi + 1):
        free = []
        for d in dets.get(F, []):
            b = d[:4]; area = b[2] * b[3]
            covered = False
            for lb in labels.get(F, []):
                if iou(b, lb) >= 0.3:
                    covered = True; break
                ix = max(0, min(b[0] + b[2], lb[0] + lb[2]) - max(b[0], lb[0])); iy = max(0, min(b[1] + b[3], lb[1] + lb[3]) - max(b[1], lb[1]))
                if ix * iy / area >= 0.5:
                    covered = True; break
            if not covered:
                free.append(b)
        used = set()
        for tr in active:
            best, bi = 0.4, -1
            for i, b in enumerate(free):
                if i in used:
                    continue
                v = iou(tr[1], b)
                if v > best:
                    best, bi = v, i
            if bi >= 0:
                used.add(bi); tr[0], tr[1] = F, free[bi]; tr[2].append((F, free[bi]))
        for i, b in enumerate(free):
            if i not in used:
                active.append([F, b, [(F, b)]])
        still = []
        for tr in active:
            (still if F - tr[0] <= 15 else tracklets).append(tr)
        active = still
    tracklets += active
    good = [t[2] for t in tracklets if len(t[2]) >= args.min_det and t[2][-1][0] - t[2][0][0] >= 25]
    nid = max(int(k) for k in project["tracks"]) + 1
    added = []
    for seg in good:
        frames = [F for F, _ in seg]
        cols = list(zip(*[b for _, b in seg]))
        sm = [m18._smooth(c, 5, 9, "sg") for c in cols] if len(seg) >= 3 else [list(c) for c in cols]
        corners = [[sm[0][i], sm[1][i], sm[0][i] + sm[2][i], sm[1][i] + sm[3][i]] for i in range(len(seg))]
        keep = m18._dp_keep(frames, corners, 6.0)
        kfs = {}
        for i in keep:
            kfs[str(frames[i] - 1)] = {"x": round(float(sm[0][i]), 2), "y": round(float(sm[1][i]), 2), "w": round(float(sm[2][i]), 2),
                                       "h": round(float(sm[3][i]), 2), "outside": False, "occluded": False, "source": "manual"}
        if frames[-1] < n_images:
            last = kfs[str(frames[-1] - 1)]
            kfs[str(frames[-1])] = dict(last, outside=True, source="outside")
        project["tracks"][str(nid)] = {"id": str(nid), "label": "person", "manual_carry": True, "keyframes": kfs}
        added.append((nid, frames[0], frames[-1], len(seg), len(keep))); nid += 1
    shutil_copy = __import__("shutil").copy
    shutil_copy(args.project, args.project + ".bak")
    with open(args.project, "w", encoding="utf-8") as f:
        json.dump(project, f)
    print(f"{len(tracklets)} uncovered tracklets, {len(good)} kept (>= {args.min_det} dets, >= 25 frames) -> new tracks:")
    for a in added:
        print("  id %d frames %d-%d dets %d keyframes %d" % a)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("run")
    a.add_argument("--project", required=True)
    a.add_argument("--ids", required=True, help="comma list / ranges of track ids, e.g. 206-220,250")
    a.add_argument("--out", required=True)
    a.add_argument("--dets", default=DETS)
    a.add_argument("--workers", type=int, default=8)
    a.add_argument("--max_kf", type=int, default=0, help="debug: only the first N keyframes per track")
    b = sub.add_parser("apply")
    b.add_argument("--project", required=True)
    b.add_argument("--verdicts", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--min_conf", type=float, default=0.6)
    c = sub.add_parser("review")
    c.add_argument("--project", required=True)
    c.add_argument("--verdicts", required=True)
    c.add_argument("--out", required=True)
    c.add_argument("--first_new_id", type=int, required=True, help="ids for split-off tracks start here")
    c.add_argument("--min_conf", type=float, default=0.6)
    c.add_argument("--max_tiles", type=int, default=14)
    c.add_argument("--workers", type=int, default=4)
    c.add_argument("--sweep", action="store_true", help="identity sweep over ALL keyframes (windows), not only flagged ones")
    c.add_argument("--ids", default="", help="sweep: restrict to these track ids")
    for name, fn in (("unshrink", cmd_unshrink), ("extend", cmd_extend), ("blob", cmd_blob), ("misses", cmd_misses)):
        s = sub.add_parser(name)
        s.add_argument("--project", required=True)
        s.add_argument("--out", default="")
        s.add_argument("--dets", default=DETS)
        s.add_argument("--conf", type=float, default=0.3)
        s.add_argument("--min_det", type=int, default=20)
        s.add_argument("--lo", type=int, default=35068)
        s.add_argument("--horizon", type=int, default=400, help="extend: how far after a track end to probe")
        s.add_argument("--skip", default="", help="comma list of track ids to leave alone (hand-edited)")
        s.add_argument("--min_conf", type=float, default=0.6 if name != "blob" else 0.7)
        s.add_argument("--workers", type=int, default=6)
        s.add_argument("--hi", type=int, default=56611)
        s.set_defaults(fn=fn)
    args = ap.parse_args()
    if getattr(args, "fn", None):
        args.fn(args)
    else:
        {"run": cmd_run, "apply": cmd_apply, "review": cmd_review}[args.cmd](args)


if __name__ == "__main__":
    main()
