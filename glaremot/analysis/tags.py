"""Cheap context tags for failure events (geometry, glare, occlusion, GT uncertainty).

Photometric tags need one image read per event (at ``key_frame``); ``images=False``
skips them (fast mode). Thresholds are constants below so they are easy to state in a report.
"""
import os

import cv2
import numpy as np

from ..photometric import mask_area_inside, saturated_core_mask, saturation_map
from ..tracking.occlusion_graph import covered_fraction
from .io import frame_image, load_uncertain

GLARE_SAT_THR = 0.15    # tag 'glare' when >= 15 % of the focus box is saturated (V>=.92, S<=.35)
SMALL_H = 60            # 'small': focus box height < 60 px
EDGE_PX = 10            # 'edge': focus box within 10 px of the image border
OCC_THR = 0.30          # 'occluded': >= 30 % of the box hidden behind a nearer GT box
NEAR_FR = 5             # near_gt_birth / near_gt_death window (frames)
CORE_PAD = 0.25         # lamp-core search box = focus box padded by 25 %


def _xyxy(b):
    _, x, y, w, h = b
    return (x, y, x + w, y + h)


def focus_box(ev, sd):
    """(kind, frame, (id,x,y,w,h)) of the box the event is about: GT box first, else the
    prediction; taken at key_frame or the nearest event frame that has it."""
    order = [ev.key_frame] + [f for f in range(ev.frame_start, ev.frame_end + 1) if f != ev.key_frame]
    for f in order:
        for g in ev.gt_ids:
            for b in sd.gt.get(f, []):
                if b[0] == g:
                    return "gt", f, b
    for f in order:
        for t in ev.pred_ids:
            for b in sd.trk.get(f, []):
                if b[0] == t:
                    return "pred", f, b
    return None, ev.key_frame, None


def _sched(mp, ev):
    if not mp or not ev.gt_ids:
        return None
    vals = [mp.get((ev.gt_ids[0], f - 1), 1.0) for f in range(ev.frame_start, ev.frame_end + 1)]
    return round(float(min(vals)), 3)


def annotate(events, sd, R, images=True):
    """Fill ``ev.tags`` for every event of one sequence (sd: SeqData, R: ClearResult)."""
    unc = load_uncertain(sd.seq_dir)
    gt_span = {}
    for f, rows in sd.gt.items():
        for r in rows:
            a = gt_span.setdefault(r[0], [f, f])
            a[0], a[1] = min(a[0], f), max(a[1], f)
    matched_frames = {}
    for f, ms in R.matches.items():
        for g, _, _ in ms:
            matched_frames.setdefault(g, []).append(f)
    mp = None
    if sd.dataset == "synth":
        from ..data.glare_m import glare_m_map
        mp = glare_m_map(sd.seq, glare_root=os.path.dirname(sd.seq_dir))
    img_cache = {}
    for ev in sorted(events, key=lambda e: e.key_frame):
        kind, f, b = focus_box(ev, sd)
        tg = {}
        if b is not None:
            x1, y1, x2, y2 = _xyxy(b)
            tg["gt_h_px"] = round(b[4], 1)
            tg["small"] = bool(b[4] < SMALL_H)
            tg["edge"] = bool(x1 < EDGE_PX or y1 < EDGE_PX or x2 > sd.W - EDGE_PX or y2 > sd.H - EDGE_PX)
            others = [o for o in sd.gt.get(f, []) if o[0] != b[0]]
            occ = max([covered_fraction((x1, y1, x2, y2), _xyxy(o)) for o in others
                       if o[1] + o[3] >= b[2] + b[4]] or [0.0])
            tg["occluded"] = bool(occ >= OCC_THR)
            tg["occ_frac"] = round(float(occ), 2)
        tg["crowd"] = len(sd.gt.get(f, []))
        tg["gt_uncertain"] = any((g, k) in unc for g in ev.gt_ids
                                 for k in range(ev.frame_start, ev.frame_end + 1))
        if ev.gt_ids:
            lo, hi = gt_span.get(ev.gt_ids[0], (ev.frame_start, ev.frame_end))
            tg["near_gt_birth"] = bool(ev.frame_start - lo <= NEAR_FR)
            tg["near_gt_death"] = bool(hi - ev.frame_end <= NEAR_FR)
            tg["after_gap"] = any(k < ev.frame_start for k in matched_frames.get(ev.gt_ids[0], []))
        if sd.dataset == "synth":
            tg["m_glare_sched"] = _sched(mp, ev)
        if images and b is not None:
            if f not in img_cache:
                img_cache.clear()
                img_cache[f] = frame_image(sd.seq_dir, f, sd.img_paths)
            im = img_cache[f]
            if im is not None:
                # work on a padded crop only (saturated_core_mask on a full frame costs ~0.3 s)
                bw, bh = x2 - x1, y2 - y1
                px, py = max(0.5 * bw, 64), max(0.5 * bh, 64)
                cx1, cy1 = int(max(0, x1 - px)), int(max(0, y1 - py))
                cx2, cy2 = int(min(sd.W, x2 + px)), int(min(sd.H, y2 + py))
                crop = im[cy1:cy2, cx1:cx2]
                sat, core = saturation_map(crop), saturated_core_mask(crop)
                rel = lambda pad: (x1 - cx1 - pad * bw, y1 - cy1 - pad * bh, x2 - cx1 + pad * bw, y2 - cy1 + pad * bh)
                tg["glare_sat"] = round(mask_area_inside(sat, rel(0)) / max(1.0, bw * bh), 3)
                tg["glare_core"] = int(mask_area_inside(core, rel(CORE_PAD)))
                tg["glare"] = bool(tg["glare_sat"] >= GLARE_SAT_THR)
        ev.tags = tg
    return events
