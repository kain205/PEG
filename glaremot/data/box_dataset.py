"""Sliding-window box-trajectory dataset for the forecaster (HBB, 4-D).

Emits per-scene windows of length T_p + T_f from the ``cache/tracks`` pickles
(built by `build_tracks.py`):

  past_traj_original_scale : [A_max, T_p, D=11]   (last channel = confidence m)
  fut_traj                 : [A_max, T_f, 4]      (cx, cy, logw, logh deltas)
  agent_padding_mask       : [A_max] bool
  anchor                   : [A_max, 4]           (decode anchor)
  valid_future             : [A_max, T_f] bool

Two PAST-only corruptions (the future target is always clean GT):
  * scheduled-sampling occlusion (ramped per epoch via ``set_epoch``);
  * online-history domain adaptation (``p_online``) — jitter + weak-update
    drag + EMA lag, matching what the tracker actually feeds at inference.
"""
import glob
import os
import pickle

import numpy as np
import torch
from torch.utils.data import Dataset

from .features import (BOX_DIM, D_FEAT, apply_occlusion_block,
                       apply_online_history, build_future_target,
                       build_past_features)


def list_cached_seqs(cache_dir):
    return sorted(os.path.splitext(os.path.basename(p))[0]
                  for p in glob.glob(os.path.join(cache_dir, "*.pkl")))


_BORDER = 0.07


def _inside_fraction(cx, cy, w, h):
    """Fraction of a normalized box (cx,cy,w,h) that lies inside the frame — the
    dense, GT-derived existence target (1.0 = fully in view, 0 = fully out)."""
    x1, y1, x2, y2 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    ix = max(0.0, min(1.0, x2) - max(0.0, x1))
    iy = max(0.0, min(1.0, y2) - max(0.0, y1))
    return float(np.clip(ix * iy / max(w * h, 1e-6), 0.0, 1.0))


def _is_border_exit(box):
    """True if the track's LAST box sits at a frame edge with outward motion —
    a genuine frame departure rather than an annotation gap. box: [T,4]."""
    cx, cy, w, h = box[-1]
    x1, y1, x2, y2 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    v = box[-1, :2] - box[-min(4, len(box)), :2]
    return bool((x1 < _BORDER and v[0] < -1e-4) or (1 - x2 < _BORDER and v[0] > 1e-4)
                or (y1 < _BORDER and v[1] < -1e-4) or (1 - y2 < _BORDER and v[1] > 1e-4))


class GlareBoxDataset(Dataset):
    def __init__(self, fcfg, cache_dir, seqs=None, stride=1,
                 p_occ=0.0, occ_max_frac=0.6, gamma=0.85, m_cap=0.5, seed=0,
                 p_online=0.0):
        self.cfg = fcfg
        self.Tp = fcfg.past_frames
        self.Tf = fcfg.future_frames
        self.A_max = fcfg.agents
        self.W = self.Tp + self.Tf
        self.p_occ = p_occ
        self.p_online = p_online
        self.occ_max_frac = occ_max_frac
        self.gamma = gamma
        self.m_cap = m_cap
        self.rng = np.random.default_rng(seed)

        paths = sorted(glob.glob(os.path.join(cache_dir, "*.pkl")))
        if seqs is not None:
            keep = set(seqs)
            paths = [p for p in paths if os.path.splitext(os.path.basename(p))[0] in keep]
        if not paths:
            raise FileNotFoundError(
                f"No track caches in {cache_dir}. Run scripts/08_build_tracks.py first.")

        self.seq_data = {}
        self.samples = []
        for p in paths:
            data = pickle.load(open(p, "rb"))
            seq = data["seq"]
            for tid, tr in data["tracks"].items():
                tr["fmap"] = {f: i for i, f in enumerate(tr["t"])}
            self.seq_data[seq] = data
            self._enumerate_windows(seq, data, stride)

    def _enumerate_windows(self, seq, data, stride):
        all_frames = sorted({f for tr in data["tracks"].values() for f in tr["t"]})
        if not all_frames:
            return
        fmin, fmax = all_frames[0], all_frames[-1]
        # per-track span + departure classification for the existence label.
        # A track ending BEFORE the scene does is only a real departure if its
        # last box is a BORDER-EXIT (near a frame edge with outward motion);
        # most mid-sequence track-ends are annotation gaps / full occlusions
        # where the person is STILL PRESENT (measured: ~86% of TRAIN ends) — those
        # are masked out of the existence loss, not labelled "gone".
        for tr in data["tracks"].values():
            tr["_tspan"] = (tr["t"][0], tr["t"][-1])
            tr["_border_exit"] = _is_border_exit(np.asarray(tr["box"], np.float32))
        past_win = list(range(self.Tp))
        fut_lo, fut_hi = self.Tp, self.W - 1            # future-step frame offsets
        for t0 in range(fmin, fmax - self.W + 2, stride):
            # MoFlow-E: an agent qualifies on the PAST window only (it needs a
            # full history to forecast from); its FUTURE presence becomes the
            # existence label instead of a hard filter, so windows where a
            # person walks out of frame are no longer discarded.
            agents, n_pos = [], 0
            for tid, tr in data["tracks"].items():
                if not all(t0 + k in tr["fmap"] for k in past_win):
                    continue
                agents.append(tid)
                # a clean low-existence signal in this window's future: a
                # border-exit departure falling inside [t0+Tp, t0+W-1], or a
                # future box that straddles a frame edge
                t_last = tr["_tspan"][1]
                if tr["_border_exit"] and t0 + fut_lo - 1 <= t_last < t0 + fut_hi:
                    n_pos += 1
                else:
                    for k in range(fut_lo, fut_hi + 1):
                        j = tr["fmap"].get(t0 + k)
                        if j is not None:
                            b = tr["box"][j]
                            if _inside_fraction(b[0], b[1], b[2], b[3]) < 0.9:
                                n_pos += 1
                                break
            if agents:
                self.samples.append((seq, t0, agents, n_pos))

    def set_epoch(self, epoch, total_epochs, p_occ_max=0.7):
        frac = min(1.0, epoch / max(1, total_epochs * 0.6))
        self.p_occ = p_occ_max * frac

    def __len__(self):
        return len(self.samples)

    def _past_arrays(self, tr, t0):
        """Past window [Tp] — must be fully present (guaranteed by enumeration)."""
        idx = [tr["fmap"][t0 + k] for k in range(self.Tp)]
        box = np.asarray(tr["box"], np.float32)[idx]     # [Tp,4] (cx,cy,w,h)
        m = np.asarray(tr["m"], np.float32)[idx]
        return box[:, 0], box[:, 1], box[:, 2], box[:, 3], m

    def _future_labels(self, tr, t0):
        """Future window [Tf]. Returns (fbox[Tf,4], box_valid[Tf], exist[Tf],
        exist_valid[Tf], vis[Tf]).
          - box_valid: a real annotated box exists at this step.
          - exist: dense GT existence target = inside-frame fraction of the GT
            box where annotated (1 fully in view, ramps to 0 as the box exits);
            0 after a confirmed BORDER-EXIT departure.
          - exist_valid: supervise existence here? True where annotated OR after
            a border-exit; FALSE after a mid-frame vanish (annotation gap /
            full occlusion — person likely still present, unlabelable).
          - vis = m where annotated (masked by box_valid otherwise)."""
        t_last = tr["_tspan"][1]
        border_exit = tr["_border_exit"]
        fbox = np.zeros((self.Tf, 4), np.float32)
        box_valid = np.zeros(self.Tf, np.bool_)
        exist = np.zeros(self.Tf, np.float32)
        exist_valid = np.zeros(self.Tf, np.bool_)
        vis = np.zeros(self.Tf, np.float32)
        for k in range(self.Tf):
            f = t0 + self.Tp + k
            j = tr["fmap"].get(f)
            if j is not None:
                b = tr["box"][j]
                fbox[k] = (b[0], b[1], b[2], b[3])
                vis[k] = tr["m"][j]
                box_valid[k] = True
                exist[k] = _inside_fraction(b[0], b[1], b[2], b[3])
                exist_valid[k] = True
            elif f > t_last:
                if border_exit:
                    exist[k] = 0.0           # confirmed departure -> gone
                    exist_valid[k] = True
                # else: mid-frame vanish -> leave exist_valid False (masked)
        return fbox, box_valid, exist, exist_valid, vis

    def sample_weights(self, pos_mult=25.0):
        """Per-sample sampler weights: windows that contain a clean low-existence
        future step (a border-exit departure or an edge-straddling box) are
        oversampled, so the existence head sees enough of the rare-but-clean
        'leaving' signal. Returns a float array len == len(self)."""
        import numpy as _np
        return _np.array([1.0 + pos_mult * s[3] for s in self.samples], _np.float64)

    def __getitem__(self, i):
        seq, t0, tids, _n_pos = self.samples[i]
        tracks = self.seq_data[seq]["tracks"]

        if len(tids) > self.A_max:
            anchor_k = self.Tp - 1
            def area(tid):
                tr = tracks[tid]; j = tr["fmap"][t0 + anchor_k]
                return tr["box"][j][2] * tr["box"][j][3]
            tids = sorted(tids, key=area, reverse=True)[:self.A_max]

        A = self.A_max
        past = np.zeros((A, self.Tp, D_FEAT), np.float32)
        fut = np.zeros((A, self.Tf, BOX_DIM), np.float32)
        pad = np.ones(A, np.bool_)
        anchor = np.zeros((A, BOX_DIM), np.float32)
        valid_fut = np.zeros((A, self.Tf), np.bool_)
        exist = np.zeros((A, self.Tf), np.float32)
        exist_valid = np.zeros((A, self.Tf), np.bool_)
        vis = np.zeros((A, self.Tf), np.float32)

        for a, tid in enumerate(tids):
            tr = tracks[tid]
            cx, cy, bw, bh, m = self._past_arrays(tr, t0)
            p_cx, p_cy = cx.copy(), cy.copy()
            p_bw, p_bh = bw.copy(), bh.copy()
            p_m = m.copy()

            if self.p_occ > 0 and self.rng.random() < self.p_occ:
                max_len = max(1, int(self.occ_max_frac * self.Tp))
                length = int(self.rng.integers(1, max_len + 1))
                start = int(self.rng.integers(1, self.Tp))
                p_cx, p_cy, p_bw, p_bh, p_m = apply_occlusion_block(
                    p_cx, p_cy, p_bw, p_bh, p_m, start, length, self.gamma, self.m_cap)

            if self.p_online > 0 and self.rng.random() < self.p_online:
                p_cx, p_cy, p_bw, p_bh, p_m = apply_online_history(
                    p_cx, p_cy, p_bw, p_bh, p_m, self.rng)

            feat, anc = build_past_features(p_cx, p_cy, p_bw, p_bh, p_m)
            fbox, box_valid, e_lab, e_valid, v_lab = self._future_labels(tr, t0)
            # box-delta target only where annotated; absent-future deltas stay 0
            # (masked out of the regression by valid_future, never supervised)
            tgt = build_future_target(fbox[:, 0], fbox[:, 1], fbox[:, 2], fbox[:, 3], anc)
            tgt[~box_valid] = 0.0
            past[a] = feat
            fut[a] = tgt
            anchor[a] = anc
            valid_fut[a] = box_valid
            exist[a] = e_lab
            exist_valid[a] = e_valid
            vis[a] = v_lab
            pad[a] = False

        return {
            "past_traj_original_scale": torch.from_numpy(past),
            "fut_traj": torch.from_numpy(fut),
            "agent_padding_mask": torch.from_numpy(pad),
            "anchor": torch.from_numpy(anchor),
            "valid_future": torch.from_numpy(valid_fut),
            "exist_future": torch.from_numpy(exist),
            "exist_valid": torch.from_numpy(exist_valid),
            "vis_future": torch.from_numpy(vis),
        }


def collate_box(batch):
    out = {}
    for k in batch[0]:
        out[k] = torch.stack([b[k] for b in batch], dim=0)
    out["batch_size"] = torch.tensor(len(batch))
    return out
