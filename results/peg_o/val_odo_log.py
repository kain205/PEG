"""D2 stage 1: replay Thach-fork S0+P+PEG-O (default tau .06 gamma 1 = O[4]) on val T3 with every odometry call logged to
results/peg_o/val_odo_log.json. Needs results/thach_v2/envP.json-style env (see ENV below, rebuilt from tune_val).
Run from anywhere: .venv/Scripts/python.exe results/peg_o/val_odo_log.py  (cwd is switched to the Thach repo)."""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
if len(sys.argv) > 1 and sys.argv[1] == "--inner":
    os.chdir(os.path.join(ROOT, "dataset", "thach_v2", "PEG-main")); sys.path.insert(0, os.getcwd())
    J = json.load(open(os.environ["ENVJSON"]))
    for k in J["clear"]: os.environ.pop(k, None)
    os.environ.update(J["env"]); os.environ.update(GPEG_ODO="1", GPEG_ODO_TAU="0.06", GPEG_ODO_GAMMA="1", GMOT_TRACKER="beacon",
                      GLAREMOT_CONFIG=os.path.join(os.getcwd(), "configs", "ours_synth.yaml"))
    sys.argv = ["x", "--split", "val", "--det_cache", "--tracker_name", "dbg_D2_tmp"]
    import numpy as np
    import glaremot.tracking.beacon_tracker as bt
    from glaremot.tracking.tracker import GlareAwareTracker as G
    LOG = []; CUR = {}
    ow = G._weak_center_update
    def ww(kfin, zx, zy, r_x, r_y):
        Hm = kfin.H[:2, :]; y = np.array([[zx], [zy]]) - Hm @ kfin.x; P = kfin.P
        K = P @ Hm.T @ np.linalg.inv(Hm @ P @ Hm.T + np.diag([r_x, r_y]))
        CUR["gain"] = (float(K[0, 0]), float(K[1, 1]))
        return ow(kfin, zx, zy, r_x, r_y)
    G._weak_center_update = staticmethod(ww)
    orig = bt.PEG._odometry_update
    SEQ = {"name": None}
    def wrap(self, mt, W, H):
        CUR.clear(); f = self._cur_frame
        x1, y1, x2, y2 = [float(v) for v in mt.kf.get_state()[0][:4]]
        gap = int(mt.kf.time_since_update); anc0 = getattr(mt, "_odo_anchor", None)
        mt._odo_k = None; mt._odo_z = None
        orig(self, mt, W, H)
        anc1 = getattr(mt, "_odo_anchor", None)
        if anc1 is not None and anc1 is not anc0:
            mt._dbg_anc_frame = f
        upd = mt._odo_z is not None and "gain" in CUR
        c = ((x1 + x2) / 2, (y1 + y2) / 2)
        zc = None if mt._odo_z is None else float(np.hypot(mt._odo_z[0] - c[0], mt._odo_z[1] - c[1]))
        LOG.append(dict(seq=SEQ["name"], f=f, tid=mt.id, gap=gap, loss_start=f - gap + 1, k=mt._odo_k, upd=bool(upd),
                        anc_frame=getattr(mt, "_dbg_anc_frame", None), had_anchor=anc0 is not None, exiting=bool(getattr(mt, "exiting", False)),
                        cx=c[0], cy=c[1], w=x2 - x1, h=y2 - y1, zc=zc, gain=CUR.get("gain")))
    bt.PEG._odometry_update = wrap
    # sequence name: eval_mot/eval_recovery build a fresh tracker per sequence; tag via attach_perception order
    oa = bt.PEG.attach_perception
    def att(self, percep):
        SEQ["name"] = getattr(percep, "seq_name", None) or SEQ["name"]
        return oa(self, percep)
    from glaremot.eval import eval_recovery as ER
    import glaremot.eval.eval_mot as EM
    ots = EM.track_sequence
    def ts(seq, *a, **k):
        SEQ["name"] = os.path.basename(str(seq).rstrip("/\\")); return ots(seq, *a, **k)
    EM.track_sequence = ts
    try:
        ER.main()
    finally:
        json.dump(LOG, open(os.path.join(os.environ["OUTJSON"], "val_odo_log.json"), "w"))
else:
    env = dict(os.environ, ENVJSON=os.environ["ENVJSON"], OUTJSON=HERE, PYTHONIOENCODING="utf-8")
    sys.exit(subprocess.run([sys.executable, __file__, "--inner"], env=env).returncode)
