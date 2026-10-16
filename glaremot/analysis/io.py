"""Loading + path conventions for the failure-analysis harness.

A *run* is one (results_subdir, tracker_name) pair, e.g. ``eval__peg``. Its MOT txt
live at ``results/<subdir>/trackers/<name>/data/<seq>.txt`` (frames 1-indexed); GT at
``<data_root>/<seq>/mot/gt/gt.txt``; image for MOT frame F is ``sorted(images)[F-1]``
(same ordering as ``eval_mot.track_sequence``; filenames are 0-indexed).
"""
import csv
import glob
import json
import os
import re
from dataclasses import dataclass, field

import cv2

from ..config import data_path, load_config, resolve, results_dir
from ..data.splits import make_splits

FA_ROOT = "failure_analysis"


def short_name(seq):
    """'136_sequence_2q_new' -> '136_2q' (readable, stable event ids)."""
    m = re.match(r"^(\d+)_sequence_(.+?)(?:_complete|_new|_in_progress)?$", seq)
    return f"{m.group(1)}_{m.group(2)}" if m else seq


def load_mot(path, is_gt=False):
    """MOT txt -> {frame(1-idx): [(id, x, y, w, h), ...]} keeping FILE ORDER (TrackEval's
    Hungarian tie-breaking depends on it). For GT, rows with col-7 flag == 0 are dropped
    (TrackEval ``zero_marked``); 9- and 10-col files are both accepted."""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for ln in f:
            p = ln.strip().split(",")
            if len(p) < 6:
                continue
            if is_gt and len(p) > 6 and int(float(p[6])) == 0:
                continue
            x, y, w, h = (float(v) for v in p[2:6])
            out.setdefault(int(float(p[0])), []).append((int(float(p[1])), x, y, w, h))
    return out


def list_frames(seq_dir):
    return sorted(glob.glob(os.path.join(seq_dir, "images", "*.jpg")))


def frame_image(seq_dir, F, paths=None):
    """BGR image for MOT frame F (1-indexed) or None."""
    paths = paths or list_frames(seq_dir)
    return cv2.imread(paths[F - 1]) if 1 <= F <= len(paths) else None


def load_uncertain(seq_dir):
    """{(track_id, frame)} from meta/uncertain_frames.csv. ``target_frame`` is taken as
    the 1-indexed MOT frame (the file matches GT rows under that reading)."""
    p = os.path.join(seq_dir, "meta", "uncertain_frames.csv")
    if not os.path.exists(p):
        return set()
    with open(p, encoding="utf-8") as f:
        return {(int(r["track_id"]), int(r["target_frame"])) for r in csv.DictReader(f)
                if r.get("track_id") and r.get("target_frame")}


def run_name(results_subdir, tracker_name):
    return f"{results_subdir}__{tracker_name}"


def fa_root():
    return results_dir(load_config(), FA_ROOT)


def run_dir(run):
    return results_dir(load_config(), FA_ROOT, run)


def tracker_dir(results_subdir, tracker_name):
    return os.path.join(results_dir(load_config(), results_subdir), "trackers",
                        tracker_name, "data")


def default_seqs(results_subdir, tracker_name, data_root, split="test"):
    """Split sequences that exist in data_root AND have a tracker txt."""
    td = tracker_dir(results_subdir, tracker_name)
    return [s for s in make_splits()[split]
            if os.path.isdir(os.path.join(data_root, s))
            and os.path.exists(os.path.join(td, f"{s}.txt"))]


@dataclass
class SeqData:
    seq: str
    seq_dir: str
    T: int                      # number of frames (= number of images)
    gt: dict                    # {frame: [(id,x,y,w,h)]}
    trk: dict
    dataset: str = "real"       # real | synth
    W: int = 0
    H: int = 0
    img_paths: list = field(default_factory=list)

    @property
    def short(self):
        return short_name(self.seq)


def load_seq(seq, data_root, results_subdir, tracker_name, dataset="real"):
    sdir = os.path.join(data_root, seq)
    paths = list_frames(sdir)
    im = cv2.imread(paths[0])
    H, W = im.shape[:2]
    return SeqData(
        seq=seq, seq_dir=sdir, T=len(paths),
        gt=load_mot(os.path.join(sdir, "mot", "gt", "gt.txt"), is_gt=True),
        trk=load_mot(os.path.join(tracker_dir(results_subdir, tracker_name), f"{seq}.txt")),
        dataset=dataset, W=W, H=H, img_paths=paths)


def save_run_meta(run, meta):
    with open(os.path.join(run_dir(run), "run.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)


def load_run_meta(run):
    with open(os.path.join(run_dir(run), "run.json"), encoding="utf-8") as f:
        return json.load(f)


def abs_data_root(p):
    return resolve(p)


def cfg_data_root(dataset):
    cfg = load_config()
    return data_path(cfg, "tracking" if dataset == "real" else "glare")
