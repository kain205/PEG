"""Run Thach's v2 code (dataset/thach_v2/PEG-main) on our machine, all three tables, test or val.

Env per config = exactly his scripts/08_ablate_methods.py CONFIGS (imported), GMOT_TRACKER=beacon,
guard at the runtime default (on, his setting) unless --guard_off. Perception is cached per
(image source, de-glare flag) under results/thach_v2/cache_{real,synth}; the first run of a flag builds it live.
  python results/thach_v2/run.py --split test --tables t1 t2 t3 --configs base full full+M6
"""
import argparse, importlib.util, os, re, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = "D:/PROJECT/PEG/dataset/thach_v2/PEG-main"
PY = "D:/PROJECT/PEG/.venv/Scripts/python.exe"
spec = importlib.util.spec_from_file_location("abl", os.path.join(REPO, "scripts", "08_ablate_methods.py"))
abl = importlib.util.module_from_spec(spec); spec.loader.exec_module(abl)
CONFIGS = dict(abl.CONFIGS)
CLEAR = ["GMOT_TRACKER", "GMOT_BIRTH_SIZE_GUARD", "GLAREMOT_CONFIG", "GMOT_OUTPUT_MAX_GAP", "GMOT_EMIT_CAP",
         "GPEG_F", "GPEG_SIZE_LOCK", "GPEG_LAMP_FOLLOW", "GMOT_AM_DAMP", "GMOT_AM_SWAP", "GBEACON_H_DECAY",
         "GMOT_ADAPTIVE_Q", "GMOT_CONE", "GMOT_REID_DEEP",
         "GPEG_ODO", "GPEG_ODO_TAU", "GPEG_ODO_GAMMA", "GPEG_ARMED_SURVIVE"] + sorted({k for c in CONFIGS.values() for k in c[0]})


def name(cfg, table, split, guard_off):
    n = "th_" + cfg.replace("+", "p").replace("-", "m") + ("_ng" if guard_off else "")
    return n + {"t1": "", "t2": "_fs", "t3": "_rcv"}[table]


def report(cfg, table, split, guard_off):
    n = name(cfg, table, split, guard_off)
    out = os.path.join(HERE, "out")
    return {"t1": f"{out}/eval/benchmark_{n}_{split}.txt", "t2": f"{out}/eval_synthfs/benchmark_{n}_{split}.txt",
            "t3": f"{out}/eval_recovery/recovery_{n}_{split}.txt"}[table]


def run(cfg, table, split, guard_off, extra=None):
    rep = report(cfg, table, split, guard_off)
    if os.path.exists(rep):
        return rep
    env = {k: v for k, v in os.environ.items() if k not in CLEAR}
    env.update(CONFIGS[cfg][0]); env.update(extra or {})
    env["GMOT_TRACKER"] = "beacon"
    env["PYTHONIOENCODING"] = "utf-8"
    if guard_off:
        env["GMOT_BIRTH_SIZE_GUARD"] = "0"
    env["GLAREMOT_CONFIG"] = os.path.join(REPO, "configs", "ours_real.yaml" if table == "t1" else "ours_synth.yaml")
    n = name(cfg, table, split, guard_off)
    if table == "t3":
        argv = [PY, "scripts/07_eval_recovery.py", "--split", split, "--det_cache", "--tracker_name", n]
    else:
        argv = [PY, "scripts/06_eval_mot.py", "--split", split, "--det_cache", "--tracker_name", n]
        if table == "t2":
            argv += ["--data_root", "D:/PROJECT/PEG/datasets/synth", "--results_subdir", "eval_synthfs"]
    log = os.path.join(HERE, "logs", f"{table}_{split}_{n}.log")
    t0 = time.time()
    with open(log, "w", encoding="utf-8") as f:
        r = subprocess.run(argv, cwd=REPO, env=env, stdout=f, stderr=subprocess.STDOUT)
    print(f"{table} {split} {cfg}{' (guard off)' if guard_off else ''}: exit {r.returncode}, {time.time() - t0:.0f}s", flush=True)
    if r.returncode != 0 or not os.path.exists(rep):
        raise SystemExit(f"failed: see {log}")
    return rep


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test")
    ap.add_argument("--tables", nargs="+", default=["t1", "t2", "t3"])
    ap.add_argument("--configs", nargs="+", default=list(CONFIGS))
    ap.add_argument("--guard_off", action="store_true")
    a = ap.parse_args()
    for c in a.configs:
        for t in a.tables:
            run(c, t, a.split, a.guard_off)
