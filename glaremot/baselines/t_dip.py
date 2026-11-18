"""DIP, "Detecting Invisible People" (Khurana, Dave, Ramanan, ICCV 2021; tarashakhurana/detecting-invisible-people
@ 3b01416, MIT), best-effort re-run on the shared cache: YOLOX-X dets, FastReID embeddings, MegaDepth disparity, GMC.

Configuration = run_forecast_filtering.sh: min_confidence 0.3, nn_budget 100, max_age 30, temporal_noise True,
tune_temporal_noise True (tn = {oc 600, of 1, pc 450, pf 2}), only_filtering False, default_matching True,
freespace_filtering True, ah_velocity False, velocity_weighting False, occluded_factor 1.06, filtering_factor 1.14,
motion_aware True, output_uncertainty True, only_extrapolate False, extrapolated_iou_match False, appearance_match
True, bugfix True; deep_sort_app.py defaults for the rest: nms_max_overlap 1.0, min_detection_height 0,
max_cosine_distance 0.2; Tracker(metric, max_age) -> max_iou_distance 0.7, n_init 3.

What runs unmodified from the clone: deep_sort/track.py (Track: 10-d state x, y, a, h, z + velocities; Occluded
predict with the a/h velocity couplings zeroed, track.py:164-181; per-detection z = box mean of the disparity map,
track.py:228-243; mark_missed / mark_occluded / max_age), deep_sort/kalman_filter.py (tn noise model, warp of the
position before predict, z = -1 replaced by the prediction in update, chi2 gate), linear_assignment.py (matching
cascade, Hungarian, gate_cost_matrix), iou_matching.py, nn_matching.py (cosine NN gallery), detection.py.
deep_sort/tracker.py cannot be imported, so its Tracker class is copied below (`_DIPTracker`) with the minimal fixes.

The algorithm per frame (deep_sort_app.py:207-293): update_metadata (depth map, ECC warp) -> predict (warp the
box, CV / Occluded motion) -> _match: confirmed tracks whose predicted z * 1.06 < mean nonzero disparity in their
predicted box become "newly occluded" (something nearer covers them); confirmed + occluded tracks go through the
appearance cascade (cosine <= 0.2, chi2 gate), then IoU matching (<= 0.7 cost) for tentative + just-missed tracks;
unmatched occluded tracks stay/become Occluded (deleted after max_age), other unmatched tracks are missed;
free-space filtering (bugfix=True: applied to BOTH the occluded and the plain unmatched tracks) deletes any of them
whose predicted z > box mean * 1.14 (the scene behind the box is farther than the track: nothing can hide it).
Output (deep_sort_app.py:265-293, only_filtering False): every Occluded track (flag 1, amodal extrapolation, until
max_age) and every Confirmed track with time_since_update <= 1 (i.e. matched, or missed this very frame: one frame
of extrapolation), flag 0; tentative tracks never. The flag / z / covariance columns are not part of MOT scoring,
so we return the box only; occluded rows ARE written (they are DIP's point).

Verified on the clone (2026-11-10): the released code does not run as shipped.
  a. deep_sort/tracker.py:94-95 `def update(..., tn=self.tn)` -> NameError at import time.
  b. deep_sort_app.py:231-253 calls tracker.update_metadata(..., only_filtering=, temporal_noise=, ah_velocity=,
     velocity_weighting=, tn=, motion_aware=) and tracker.update(..., default_matching=, freespace_filtering=,
     only_extrapolate=, extrapolated_iou_match=, appearance_match=, bugfix=); tracker.py:305 / :94 accept none of
     these (TypeError even after a.).
  c. deep_sort/tracker_mask.py matches deep_sort_app's update_metadata (tracker_mask.py:621-667) but imports
     detectron2 and a `predictor` module absent from the repo (tracker_mask.py:25-30); its update
     (tracker_mask.py:144-145) takes neither default_matching... nor only_extrapolate, which its body uses
     (tracker_mask.py:161) and calls self._match without them (tracker_mask.py:155-156, so _match would run with
     default_matching=False, not the shell's True).
  d. tracker.py:226 / tracker_mask.py:530 call kf.initiate(det, temporal_noise, tn) but kalman_filter.py:358 is
     initiate(measurement, tn=-1) (TypeError); tracker_mask.py:169-173 calls Track.update(..., temporal_noise=, tn=)
     but track.py:194 has no temporal_noise (TypeError); tracker_mask.py:219-222 passes temporal_noise= to
     linear_assignment.gate_cost_matrix, which has no such argument (linear_assignment.py:144-146).
  e. linear_assignment.py:3 imports sklearn.utils.linear_assignment_ (removed in scikit-learn 0.23); track.py:5
     imports skimage (only for the mask path).
Reconstruction choices / deviations (numbered; each cites the original):
  1. _match = tracker.py:151-219, which hard-codes exactly the branch that tracker_mask.py:210-384 selects for the
     shell flags (only_filtering False, default_matching True, appearance_match True, extrapolated_iou_match False,
     freespace_filtering True, bugfix True -> tracker_mask.py:248-253, :307-312, :326, :333-335, :351-361).
     only_extrapolate False makes tracker_mask.py:161-163 a no-op. ah_velocity / velocity_weighting are stored but
     read nowhere in the repo; max_height is passed to Track.predict but its use is commented out (track.py:171-172).
  2. Box mean, not mask mean (Mask-RCNN-free variant): tracker.py reason_for_occlusions/_reappearances (:335-418,
     mean of the NONZERO disparity in the predicted box) instead of the *_mask versions (tracker_mask.py:760-803).
     The "masks" there are the predicted boxes rasterised (tracker_mask.py:105-132) and bilinearly resized, so the
     two differ only by a one-cell dilation. Detection z: track.py compute_mean_depth (:228-243, plain mean over
     the box, -1 if the box is empty/outside) for both birth and update; tracker.py:252 has the typo
     `box[1] == box[2]` (y1 vs x2) where track.py:239 has `box[1] == box[3]`; we use track.py's check, because with
     tracker.py's a box less than one depth cell tall gives np.mean([]) = NaN and poisons the KF state.
  3. Noise model tn everywhere it is meant to go: initiate(det, tn) (fix of d.), predict / gating with tn (as
     tracker.py:91-92, :158-159), and Track.update(..., tn=tn) as tracker_mask.py:169-173 intends (tracker.py:112-114
     drops it, which would use the tn=-1 constants in the KF update only).
  4. Inputs are the shared cache, not DIP's files: depth map = extra["disp"] / 255 (MegaDepth
     best_generalization_net_G at 384x512 as tools/demo_images.py, 1/exp(log depth) / per-frame max, area-downsampled
     to 96x128 and quantised to uint8) instead of img1Depth/*.npy at 384x512 float (tracker.py:310-314). Box coords
     are mapped by the same scale_x/scale_y code with image_size = (h, w) (tracker.py:342-343). Quantisation can turn
     disparity < 0.5/255 into 0, which the nonzero-mean in reason_* then ignores (MegaDepth maps of these mine
     scenes are 152-251/255 on the frames checked, so it does not happen in practice).
  5. Camera motion: extra["gmc"] (BoT-SORT sparseOptFlow affine, previous -> current) instead of cv2 ECC
     MOTION_EUCLIDEAN (tracker.py:281-303, tracker_mask.py:654-666, also previous -> current). As in the original, no
     warp on the first frame (warp_matrix stays the int -1, kalman_filter.py:454) and the warp moves the position
     only, not velocity / covariance (kalman_filter.py:422-429, unchanged). Cameras are fixed, so it is ~identity.
  6. Appearance: FastReID MOT20 SBS-S50 2048-d (L2-normalised) instead of DeepSORT's MARS 128-d (TF1 model,
     tools/generate_detections.py); max_cosine_distance kept at 0.2, not tuned. On the 2 smoke seqs the nearest-
     gallery distance of a det has median 0.024 / p90 0.084 (98 % <= 0.2): the gate is loose, the chi2 gate and
     the cascade order do most of the work (892 cascade matches vs 18 IoU matches).
  7. Detections: YOLOX-X cache rows filtered at score >= 0.3 (min_confidence), detector NMS 0.7 (`nms`, override
     with GDIP_NMS). DIP's nms_max_overlap 1.0 (deep_sort_app.py:341-342, :218-222) is DeepSORT's EXTRA tracker-side
     NMS on top of MOT17 public FRCNN dets, which the detector had already NMSed; it is not "no NMS on raw detector
     output". The det_nms0.95 rows are close to raw YOLOX output (3-5 boxes >= 0.8 on one person, e.g.
     125_sequence_12q frames 122-125 of val_half), and DeepSORT, which has no score-based first stage, births one
     track per duplicate: on the 2 smoke seqs NMS 0.95 gives HOTA 25.0 / IDF1 28.7 / FP 791 / IDSW 39 (65 tracks
     for ~3 people), NMS 0.7 gives 51.7 / 79.7 / 53 / 4. 0.7 is the YOLOX default NMS the other adapters use, i.e.
     "the detector's own NMS" in our pipeline, which is what FRCNN's NMS was for DIP.
  8. sklearn.utils.linear_assignment_.linear_assignment (e.) is replaced by scipy.optimize.linear_sum_assignment
     (same optimum; ties may break differently). skimage.transform.resize is stubbed (mask path only). The stubs
     live in sys.modules only while the repo modules import.
  9. Output rows with a non-finite or non-positive width/height are dropped (unscorable; DIP writes them as they
     come). No min-area / aspect filter: deep_sort_app.py has none.
Counters per sequence (occlusion entries, free-space deletions, occluded rows written) are printed at exit.
"""
import atexit
import importlib
import os
import sys
import types

import numpy as np

from glaremot.baselines import adapters  # noqa: F401  (numpy alias shims: detection.py uses np.float)
from glaremot.baselines.adapters import _repo_import

REPO = "detecting-invisible-people"
TN = {"oc": 600, "of": 1, "pc": 450, "pf": 2}            # run_forecast_filtering.sh tune_temporal_noise
MIN_CONF, NN_BUDGET, MAX_AGE, MAX_COS = 0.3, 100, 30, 0.2
OCC_FACTOR, FILT_FACTOR = 1.06, 1.14
MAX_IOU_DIST, N_INIT = 0.7, 3

_M = {}
STATS = []


def _stub_missing():
    """sklearn.utils.linear_assignment_ (gone from scikit-learn) and skimage (mask path only). Returns the names it
    put in sys.modules: they are removed again once the repo modules have bound the functions (a spec-less stub
    left in sys.modules breaks importlib.util.find_spec("sklearn"), e.g. inside torch._dynamo)."""
    def linear_assignment(cost):
        from scipy.optimize import linear_sum_assignment
        r, c = linear_sum_assignment(cost)
        return np.stack([r, c], axis=1)

    def resize(*a, **k):
        raise NotImplementedError("skimage stub: DIP mask path is not used")

    def need(name):
        try:
            importlib.import_module(name)
            return False
        except ImportError:
            return True

    added = []
    for leaf, parents, attr, fn in (("sklearn.utils.linear_assignment_", ("sklearn", "sklearn.utils"),
                                     "linear_assignment", linear_assignment),
                                    ("skimage.transform", ("skimage",), "resize", resize)):
        if not need(leaf):
            continue
        for n in parents:
            if n not in sys.modules and need(n):
                sys.modules[n] = types.ModuleType(n)
                added.append(n)
        m = types.ModuleType(leaf)
        setattr(m, attr, fn)
        sys.modules[leaf] = m
        added.append(leaf)
    return added


def _load():
    if not _M:
        added = _stub_missing()
        try:
            _M["track"] = _repo_import(REPO, "deep_sort.track", pkg="deep_sort")
            for k in ("kalman_filter", "linear_assignment", "iou_matching", "nn_matching", "detection"):
                _M[k] = importlib.import_module("deep_sort." + k)
        finally:
            for n in added:
                sys.modules.pop(n, None)
    return _M


class _DIPTracker:
    """deep_sort/tracker.py Tracker (tracker.py:14-418), copied with the fixes listed in the module docstring."""

    def __init__(self, metric, max_iou_distance=0.7, max_age=30, n_init=3):
        m = _load()
        self.la, self.iou_matching, self.Track = m["linear_assignment"], m["iou_matching"], m["track"].Track
        self.TrackState = m["track"].TrackState
        self.metric = metric
        self.max_iou_distance = max_iou_distance
        self.max_age = max_age
        self.n_init = n_init
        self.frame_idx = -1
        self.sequence_info = {}
        self.max_height = -1
        self.image = []
        self.tn = -1
        self.warp_matrix = -1
        self.kf = m["kalman_filter"].KalmanFilter()
        self.tracks = []
        self._next_id = 1
        self.n_occ_enter = self.n_fs_del_occ = self.n_fs_del_unm = 0

    def update_metadata(self, idx, depth_map, image_size, max_height, warp_matrix, tn=-1):
        """tracker_mask.py:621-667 with the files replaced by cached arrays (deviations 4, 5)."""
        self.frame_idx = idx
        self.sequence_info = {"image_size": image_size}
        self.max_height = max_height
        self.image = depth_map
        self.tn = tn
        if self.frame_idx != 1:
            self.warp_matrix = warp_matrix

    def predict(self):                                       # tracker.py:85-92
        for track in self.tracks:
            track.predict(self.kf, self.max_height, tn=self.tn, warp_matrix=self.warp_matrix)

    def update(self, detections, occluded_factor=1.0, filtering_factor=1.0):   # tracker.py:94-149
        matches, unmatched_tracks, unmatched_detections, newly_occluded_tracks, previously_occluded_tracks = \
            self._match(detections, occluded_factor=occluded_factor, filtering_factor=filtering_factor)
        for track_idx, detection_idx in matches:
            self.tracks[track_idx].update(self.kf, detections[detection_idx], self.image, self.sequence_info,
                                          tn=self.tn)                             # deviation 3
        for track_idx in newly_occluded_tracks:
            self.n_occ_enter += self.tracks[track_idx].state == self.TrackState.Confirmed
            self.tracks[track_idx].mark_occluded()
        for track_idx in previously_occluded_tracks:
            self.tracks[track_idx].mark_deleted()
        for track_idx in unmatched_tracks:
            self.tracks[track_idx].mark_missed()
        for detection_idx in unmatched_detections:
            self._initiate_track(detections[detection_idx], tn=self.tn)
        self.tracks = [t for t in self.tracks if not t.is_deleted()]

        active_targets = [t.track_id for t in self.tracks if t.is_confirmed() or t.is_occluded()]
        features, targets = [], []
        for track in self.tracks:
            if not track.is_confirmed() and not track.is_occluded():
                continue
            features += track.features
            targets += [track.track_id for _ in track.features]
            track.features = []
        self.metric.partial_fit(np.asarray(features), np.asarray(targets), active_targets)

    def _match(self, detections, occluded_factor=1.0, filtering_factor=1.0):   # tracker.py:151-219 (deviation 1)
        la = self.la

        def gated_metric(tracks, dets, track_indices, detection_indices):
            features = np.array([dets[i].feature for i in detection_indices])
            targets = np.array([tracks[i].track_id for i in track_indices])
            cost_matrix = self.metric.distance(features, targets)
            return la.gate_cost_matrix(self.kf, cost_matrix, tracks, dets, track_indices, detection_indices,
                                       tn=self.tn)

        confirmed_tracks = [i for i, t in enumerate(self.tracks) if t.is_confirmed()]
        occluded_tracks = [i for i, t in enumerate(self.tracks) if t.is_occluded()]
        unconfirmed_tracks = [i for i, t in enumerate(self.tracks) if not t.is_confirmed() and not t.is_occluded()]

        newly_occluded_tracks, confirmed_tracks = self.reason_for_occlusions(self.tracks, confirmed_tracks,
                                                                             occluded_factor)
        newly_occluded_tracks = newly_occluded_tracks + occluded_tracks

        confirmed_tracks = confirmed_tracks + newly_occluded_tracks
        matches_a, unmatched_tracks_a, unmatched_detections = la.matching_cascade(
            gated_metric, self.metric.matching_threshold, 0, self.max_age, self.tracks, detections,
            confirmed_tracks)

        iou_track_candidates = unconfirmed_tracks + [
            k for k in unmatched_tracks_a if self.tracks[k].time_since_update == 1]
        unmatched_tracks_a = [k for k in unmatched_tracks_a if self.tracks[k].time_since_update != 1]
        matches_b, unmatched_tracks_b, unmatched_detections = la.min_cost_matching(
            self.iou_matching.iou_cost, self.max_iou_distance, self.tracks, detections, iou_track_candidates,
            unmatched_detections)

        matches = matches_a + matches_b
        unmatched_tracks = list(set(unmatched_tracks_a + unmatched_tracks_b))

        newly_occluded_tracks = [i for i in newly_occluded_tracks if i in unmatched_tracks]
        unmatched_tracks = [i for i in unmatched_tracks if i not in newly_occluded_tracks]

        pv1, occluded_tracks_ = self.reason_for_reappearances(self.tracks, newly_occluded_tracks, filtering_factor)
        pv2, unmatched_tracks = self.reason_for_reappearances(self.tracks, unmatched_tracks, filtering_factor)
        self.n_fs_del_occ += len(pv1)
        self.n_fs_del_unm += sum(self.tracks[i].state == self.TrackState.Confirmed for i in pv2)
        return matches, unmatched_tracks, unmatched_detections, occluded_tracks_, pv1 + pv2

    def _initiate_track(self, detection, tn=-1):          # tracker.py:221-231 (deviations 2, 3)
        mean_depth = self.Track.compute_mean_depth(None, self.image, detection, self.sequence_info)
        det = list(detection.to_xyah()) + [mean_depth]
        mean, covariance = self.kf.initiate(det, tn)
        self.tracks.append(self.Track(mean, covariance, self._next_id, self.n_init, self.max_age,
                                      detection.feature))
        self._next_id += 1

    def _box_mean(self, track):
        """Shared body of tracker.py:340-368 / :383-411: mean nonzero disparity in the predicted box, None where
        the original takes its fallback branch."""
        image = self.image
        scale_x = self.sequence_info["image_size"][1] / float(image.shape[1])
        scale_y = self.sequence_info["image_size"][0] / float(image.shape[0])
        box = track.to_tlbr()
        box = [box[0] / scale_x, box[1] / scale_y, box[2] / scale_x, box[3] / scale_y]
        box = [int(x) for x in box]
        box = [max(0, box[0]), max(0, box[1]),
               max(min(image.shape[1], box[2]), 0),
               max(min(image.shape[0], box[3]), 0)]
        # tracker.py:355 / :398 keep the `box[1] == box[2]` typo here; empty crops still fall back below
        if 0 in box[2:] or box[0] >= image.shape[1] or box[1] >= image.shape[0] or box[0] == box[2] \
                or box[1] == box[2]:
            return None
        box = image[box[1]:box[3], box[0]:box[2]]
        if len(np.unique(box)) == 1 or 0 in box.shape:
            return None
        return np.mean(box[np.nonzero(box)])

    def reason_for_occlusions(self, tracks, track_indices, occluded_factor=1.0):   # tracker.py:335-375
        if self.frame_idx == -1:
            return [], track_indices
        newly_occluded_tracks, unmatched_tracks = [], []
        for idx in track_indices:
            track = self.tracks[idx]
            box_mean = self._box_mean(track)
            predicted_depth = track.to_tlwhz()[4]
            if box_mean is not None and predicted_depth * occluded_factor < box_mean:
                newly_occluded_tracks.append(idx)
            else:
                unmatched_tracks.append(idx)
        return newly_occluded_tracks, unmatched_tracks

    def reason_for_reappearances(self, tracks, track_indices, filtering_factor=1.0):  # tracker.py:378-418
        if self.frame_idx == -1:
            return [], track_indices
        previously_occluded_tracks, occluded_tracks = [], []
        for idx in track_indices:
            track = self.tracks[idx]
            box_mean = self._box_mean(track)
            predicted_depth = track.to_tlwhz()[4]
            if box_mean is not None and predicted_depth > box_mean * filtering_factor:
                previously_occluded_tracks.append(idx)
            else:
                occluded_tracks.append(idx)
        return previously_occluded_tracks, occluded_tracks


class Tracker:
    nms, needs = float(os.environ.get("GDIP_NMS", 0.7)), ("emb", "gmc", "disp")     # deviation 7

    def __init__(self, fps, hw, seq=None):
        m = _load()
        self.Detection = m["detection"].Detection
        metric = m["nn_matching"].NearestNeighborDistanceMetric("cosine", MAX_COS, NN_BUDGET)
        self.t = _DIPTracker(metric, max_iou_distance=MAX_IOU_DIST, max_age=MAX_AGE, n_init=N_INIT)
        self.hw = hw
        self.st = {"seq": seq, "frames": 0, "rows": 0, "occ_rows": 0}
        STATS.append(self.st)

    def step(self, dets, extra):
        t = self.t
        keep = dets[:, 4] >= MIN_CONF                                        # deep_sort_app.py:215
        emb = extra["emb"][keep]
        detections = [self.Detection((x1, y1, x2 - x1, y2 - y1), s, e)
                      for (x1, y1, x2, y2, s), e in zip(dets[keep], emb)]
        max_height = max(d.tlwh[3] for d in detections) if detections else -1   # deep_sort_app.py:223-226
        depth = extra["disp"].astype(np.float32) / 255.0
        t.update_metadata(extra["frame"], depth, self.hw, max_height, extra["gmc"].astype(np.float64), tn=TN)
        t.predict()
        t.update(detections, occluded_factor=OCC_FACTOR, filtering_factor=FILT_FACTOR)

        out = []
        for track in t.tracks:                                               # deep_sort_app.py:265-293
            if track.is_tentative() or track.is_deleted():
                continue
            if track.is_confirmed() and track.time_since_update > 1:
                continue
            x, y, w, h = track.to_tlwhz()[:4]
            if not (np.isfinite([x, y, w, h]).all() and w > 0 and h > 0):    # deviation 9
                continue
            out.append((track.track_id, x, y, w, h))
            self.st["occ_rows"] += track.is_occluded()
        st = self.st
        st["frames"] += 1
        st["rows"] += len(out)
        st["occ_enter"], st["fs_del_occluded"], st["fs_del_confirmed"] = \
            t.n_occ_enter, t.n_fs_del_occ, t.n_fs_del_unm
        st["ids"] = t._next_id - 1
        return out


@atexit.register
def _report():
    for s in STATS:
        if s["frames"]:
            print(f"[dip] {s['seq']}: frames {s['frames']} rows {s['rows']} (occluded rows {s['occ_rows']}) | "
                  f"tracks born {s.get('ids', 0)} | Confirmed->Occluded {s.get('occ_enter', 0)} | free-space "
                  f"deletions: occluded {s.get('fs_del_occluded', 0)}, unmatched confirmed "
                  f"{s.get('fs_del_confirmed', 0)}", flush=True)
