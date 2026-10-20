"""PEG-C port checks (WP2 C): Thach fork vs ours.
 1. flags OFF: his S0+P (tv51d09158) on TEST re-run under a new tracker name -> MOT txt byte-identical to the existing run.
 2. config P + V(K40,t0) + C48 + S1.5 + B(L90, all), guard ON in both: T3 on val 187_sequence_66q_new / 133_sequence_17q_new,
    his MOT txt vs ours (MOT txt only, no metrics printed).
Run: .venv/Scripts/python.exe results/peg_c/port_check.py [1|2]  -> results/peg_c/port_check_{1,2}.txt"""
import importlib.util, os, subprocess, sys
ROOT = "D:/PROJECT/PEG"
spec = importlib.util.spec_from_file_location("tv", os.path.join(ROOT, "results/thach_v2/tune_val.py"))
tv = importlib.util.module_from_spec(spec); spec.loader.exec_module(tv)
tv.GRID["P"] = [{"GPEG_SIZE_LOCK": "1"}]
OUT = os.path.join(ROOT, "results/thach_v2/out")
lines = []


def P(s):
    print(s, flush=True); lines.append(s)


def cmp_dirs(a, b, seqs=None):
    nfiles = nd = 0
    for fn in sorted(os.listdir(a)):
        if seqs and fn[:-4] not in seqs:
            continue
        nfiles += 1
        x, y = open(os.path.join(a, fn), "rb").read(), open(os.path.join(b, fn), "rb").read()
        if x != y:
            nd += 1
            P(f"  DIFF {fn} bytes {len(x)} vs {len(y)}")
    return nfiles, nd


which = sys.argv[1] if len(sys.argv) > 1 else "1"
if which == "1":
    ref_env = tv.env_of({"P": 0})
    tv.run.CONFIGS["tvPORTCHK"] = (ref_env, "portchk")
    for t, sub in (("t1", "eval"), ("t2", "eval_synthfs"), ("t3", "eval_recovery")):
        tv.run.run("tvPORTCHK", t, "test", False)
        new = os.path.join(OUT, sub, "trackers", tv.run.name("tvPORTCHK", t, "test", False), "data")
        old = os.path.join(OUT, sub, "trackers", tv.run.name("tv51d09158", t, "test", False), "data")
        n, d = cmp_dirs(new, old)
        P(f"{t}: {n} files compared, {d} differ  ({os.path.basename(os.path.dirname(new))} vs {os.path.basename(os.path.dirname(old))})")
    open(os.path.join(ROOT, "results/peg_c/port_check_1.txt"), "w").write("\n".join(lines) + "\n")
else:
    PEGC = {"GPEG_SIZE_LOCK": "1", "GPEG_VEL_K": "40", "GPEG_VEL_T": "0", "GPEG_CAP": "48", "GPEG_STITCH_K": "1.5",
            "GPEG_BACKFILL_L": "90", "GPEG_BACKFILL_MODE": "all"}
    env_h = dict(tv.env_of({})); env_h.update(PEGC)
    tv.run.CONFIGS["tvPORTOURS"] = (env_h, "portours")
    tv.run.run("tvPORTOURS", "t3", "val", False)
    his = os.path.join(OUT, "eval_recovery", "trackers", tv.run.name("tvPORTOURS", "t3", "val", False), "data")
    seqs = ["187_sequence_66q_new", "133_sequence_17q_new"]
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GPEG_", "GMOT_", "GBEACON_"))}
    env.update(PEGC); env["GMOT_TRACKER"] = "beacon"      # guard left at its default (on)
    subprocess.run([tv.run.PY, "scripts/07_eval_recovery.py", "--split", "val", "--percep_cache", "results/percep_cache/synth",
                    "--seqs", *seqs, "--tracker_name", "portchk_ours_val"], cwd=ROOT, env=env,
                   stdout=open(os.path.join(ROOT, "results/peg_c/port_check_ours.log"), "w"), stderr=subprocess.STDOUT, check=True)
    ours = os.path.join(ROOT, "results/eval_recovery/trackers/portchk_ours_val/data")
    n, d = cmp_dirs(his, ours, seqs)
    P(f"port vs ours (guard on, P+V40+C48+S1.5+B90all): {n} sequences compared, {d} differ byte-wise")
    for sq in seqs:
        a = open(os.path.join(his, sq + ".txt")).read().splitlines(); b = open(os.path.join(ours, sq + ".txt")).read().splitlines()
        mx = 0.0; nrow = 0
        if len(a) == len(b):
            for x, y in zip(a, b):
                px, py = x.split(","), y.split(",")
                if px[:2] != py[:2]:
                    mx = 1e9
                else:
                    nrow += 1
                    mx = max(mx, max(abs(float(u) - float(v)) for u, v in zip(px[2:6], py[2:6])))
        P(f"  {sq}: rows his {len(a)} ours {len(b)}, max |box diff| {mx:.3f} px over {nrow} rows")
    open(os.path.join(ROOT, "results/peg_c/port_check_2.txt"), "w").write("\n".join(lines) + "\n")
