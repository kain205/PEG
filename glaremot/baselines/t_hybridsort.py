"""Hybrid-SORT-ReID (ymzis69/HybridSORT @ 396f8d3) on the cached detections + FastReID embeddings.

Official tracker class, unmodified: trackers/hybrid_sort_tracker/hybrid_sort_reid.py `Hybrid_Sort_ReID`, built and called
like `MOTEvaluatorDance.evaluate_hybrid_sort_reid` (yolox/evaluators/mot_evaluator_dance.py:720-930) does it for the
MOT17 ReID exp. Repo paths below are relative to results/baselines_t1/repos/HybridSORT.

Args object = `utils/args.py make_parser().parse_args([])` (defaults, loaded from the file itself) with the values of
exps/example/mot/yolox_x_mix_det_hybrid_sort_reid.py merged in by `args_merge_params_form_exp` (tools/run_hybrid_sort_dance.py:
`args_merge_params_form_exp(args, exp)`; only keys that already exist in args are merged). Resulting values:
  use_byte True                         exp:34     (default False, utils/args.py:57)
  dataset "mot17"                       exp:35     (default "mot17", utils/args.py:90)
  inertia 0.05                          exp:36     (default 0.2, utils/args.py:48)
  iou_thresh 0.25                       exp:37     (default 0.3, utils/args.py:46) -> iou_threshold of the tracker
  asso "Height_Modulated_IoU"           exp:38     (= hmiou, ASSO_FUNCS in hybrid_sort_reid.py:298-304)
  TCM_first_step True                   exp:39
  TCM_byte_step True                    exp:40
  TCM_first_step_weight 1.0             exp:41
  TCM_byte_step_weight 1.0              exp:42
  hybrid_sort_with_reid True            exp:43     (selects evaluate_hybrid_sort_reid, run_hybrid_sort_dance.py:143)
  with_fastreid True                    exp:44     (we feed cached FastReID MOT20 SBS-S50 features instead)
  EG_weight_high_score 1.3              exp:45
  EG_weight_low_score 1.2               exp:46
  with_longterm_reid_correction True    exp:49
  longterm_reid_correction_thresh 0.4   exp:50
  longterm_reid_correction_thresh_low 0.4  exp:51
  unchanged args.py defaults: track_thresh 0.6 (:45) -> det_thresh, deltat 3 (:49) -> delta_t,
  low_thresh 0.1 (:68), high_score_matching_thresh 0.8 (:69), alpha 0.8 (:71), with_longterm_reid False (:75),
  longterm_reid_weight 0.0 (:76), longterm_bank_length 30 (:81), adapfs False (:82), ECC False (:84),
  aspect_ratio_thresh 1.6 (:106). min_hits=3 and max_age=30 are the Hybrid_Sort_ReID constructor defaults
  (hybrid_sort_reid.py:308-309; the evaluator passes neither, args.min_hits is not read; the track_buffer it sets per
  MOT17 video is never read by the tracker).
Construction (evaluator :823-824): Hybrid_Sort_ReID(args, det_thresh=track_thresh, iou_threshold=iou_thresh,
  asso_func=asso, delta_t=deltat, inertia=inertia).
Call (evaluator :890): tracker.update(dets, info_imgs, img_size, id_feature=emb, warp_matrix=None). ECC is off, so the
  evaluator passes warp_matrix=None (:884-887). img_info = img_size = (h, w) -> scale = 1 (the tracker's own rescale).
Output filter (evaluator :907-909): tlwh = (x1, y1, x2-x1, y2-y1); drop w/h > 1.6 (dataset is "mot17") and
  w*h <= min_box_area. min_box_area: utils/args.py defines the dest twice, '--min-box-area' default 100 (:52) and
  '--min_box_area' default 10 (:109). argparse gives every dest its default once, from the first action, so the
  effective default is 100 (checked by parse_args([])). 100 is used.
Not applied: the per-video track_thresh / track_buffer overrides (evaluator :792-813) are MOT17/MOT20 specific per-sequence
  hacks; for non-MOT20-06/08 videos the second if/else resets track_thresh to the default anyway, and track_buffer is unused.
No detections in a frame: the evaluator would call update() with whatever YOLOX returned (a None would skip it). Here update()
  is called with an empty (0, 5) array and an empty (0, 2048) embedding array: the class handles it (no detection ->
  all trackers unmatched, predicted, aged), so tracker state stays consistent.
No interpolation, online.
Deviations from the official pipeline: none in the tracker; detections come from our YOLOX-X cache (conf >= 0.1, NMS 0.7
  re-applied by the harness) and the embeddings from our FastReID MOT20 SBS-S50 cache. The tracker's debug print() calls
  (correction messages) are silenced. numpy 2 shim: KalmanBoxTracker.predict's kalman_score (a (1,) array that numpy 1
  silently converted when stored into trks[t]) is returned as a float: identical value.
"""
import importlib.util
import os

import numpy as np

from glaremot.baselines.adapters import REPOS, _repo_import

_REPO = "HybridSORT"

# values of exps/example/mot/yolox_x_mix_det_hybrid_sort_reid.py that also exist in utils/args.py (merged by
# args_merge_params_form_exp)
EXP = dict(
    use_byte=True, dataset="mot17", inertia=0.05, iou_thresh=0.25, asso="Height_Modulated_IoU",
    TCM_first_step=True, TCM_byte_step=True, TCM_first_step_weight=1.0, TCM_byte_step_weight=1.0,
    hybrid_sort_with_reid=True, with_fastreid=True, EG_weight_high_score=1.3, EG_weight_low_score=1.2,
    with_longterm_reid_correction=True, longterm_reid_correction_thresh=0.4, longterm_reid_correction_thresh_low=0.4,
)


def _official_args():
    """utils/args.py defaults + the MOT17 ReID exp values, built from the repo's own parser (file loaded by path so
    the repo's `utils` package does not enter sys.modules)."""
    spec = importlib.util.spec_from_file_location("_hybridsort_args", os.path.join(REPOS, _REPO, "utils", "args.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    args = mod.make_parser().parse_args([])
    for k, v in EXP.items():
        if k in args.__dict__:
            args.__dict__[k] = v
    return args


class Tracker:
    nms, needs = 0.7, ("emb",)

    def __init__(self, fps, hw, seq=None):
        hs = _repo_import(_REPO, "trackers.hybrid_sort_tracker.hybrid_sort_reid", pkg="trackers")
        hs.print = lambda *a, **k: None          # module-level print() debug lines of the official code
        import trackers.hybrid_sort_tracker.association as assoc
        assoc.print = lambda *a, **k: None
        if not getattr(hs.KalmanBoxTracker.predict, "_peg_shim", False):
            # numpy 2: the official `trk[:] = [..., kalman_score, ...]` no longer accepts the (1,) array that
            # np.clip(self.kf.x[3], ...) returns (numpy 1 converted it silently). Same value, as a float.
            _predict = hs.KalmanBoxTracker.predict

            def predict(self):
                pos, kalman_score, simple_score = _predict(self)
                return pos, float(np.ravel(kalman_score)[0]), simple_score
            predict._peg_shim = True
            hs.KalmanBoxTracker.predict = predict
        self.args = a = _official_args()
        self.t = hs.Hybrid_Sort_ReID(a, det_thresh=a.track_thresh, iou_threshold=a.iou_thresh,
                                     asso_func=a.asso, delta_t=a.deltat, inertia=a.inertia)
        self.hw = hw

    def step(self, dets, extra):
        a = self.args
        emb = extra["emb"]
        if len(dets) == 0:
            dets = np.zeros((0, 5), np.float32)
            emb = np.zeros((0, 2048), np.float32)
        # copies: the tracker rescales boxes and L2-normalises features in place
        out = self.t.update(np.array(dets, dtype=np.float32), self.hw, self.hw,
                            id_feature=np.array(emb, dtype=np.float32), warp_matrix=None)
        res = []
        for t in out:
            tlwh = (t[0], t[1], t[2] - t[0], t[3] - t[1])
            if tlwh[2] / max(tlwh[3], 1e-6) > a.aspect_ratio_thresh:   # evaluator: vertical = w/h > 1.6 (mot17)
                continue
            if tlwh[2] * tlwh[3] > a.min_box_area:
                res.append((int(t[4]), *tlwh))
        return res
