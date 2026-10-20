"""PEG-C WP1b wiring check of C, S, B, BB from MOT txt + firing counters ONLY (no metrics are read).
Reference = same online flags with B/BB off (wire_online[_t1]); candidates wire_pegc_all / wire_pegc_hid [_t1].
Run: .venv/Scripts/python.exe results/peg_c/wire_check.py -> results/peg_c/wire_check.txt"""
import collections
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WIRE = os.path.join(ROOT, "results", "peg_c", "wire")
TOL = 0.02
L = 90
OUT = []


def P(s=""):
    print(s)
    OUT.append(s)


def load(base, name):
    d = os.path.join(ROOT, "results", base, "trackers", name, "data")
    res = {}
    for fn in sorted(os.listdir(d)):
        rows = []
        for ln in open(os.path.join(d, fn), encoding="utf-8").read().splitlines():
            p = ln.split(",")
            rows.append((int(p[0]), int(p[1]), ln, [float(v) for v in p[2:6]], p[6]))
        res[fn[:-4]] = rows
    return res


def counters(name):
    c = {}
    for ln in open(os.path.join(WIRE, name + ".jsonl"), encoding="utf-8"):
        r = json.loads(ln)
        c[r["seq"]] = r["counts"]
    return c


def geo(b):
    return (b[0] + b[2] / 2, b[1] + b[3] / 2, b[2], b[3])


def check_run(tag, base, ref_name, name, mode, gap_ref=None):
    gap_out = {}
    ref, cand, cnt = load(base, ref_name), load(base, name), counters(name)
    P(f"=== {tag}: {name} (mode {mode}) vs {ref_name}")
    keys = ["pegc_cap_block", "pegc_stitch", "pegc_backfill_records", "pegc_backfill_frames", "pegc_bb_tracks",
            "pegc_bb_frames", "pegc_rows_added"]
    tot = collections.Counter()
    viol = []
    for seq in sorted(ref):
        c = cnt.get(seq, {})
        for k in keys:
            tot[k] += c.get(k, 0)
        R = {(f, i): (ln, b) for f, i, ln, b, _ in ref[seq]}
        C = {(f, i): (ln, b, cf) for f, i, ln, b, cf in cand[seq]}
        # (2) order + uniqueness
        fr = [r[0] for r in cand[seq]]
        if fr != sorted(fr):
            viol.append((seq, "rows not sorted by frame"))
        if len(C) != len(cand[seq]):
            viol.append((seq, "duplicate (frame,id)"))
        # online rows present?
        missing = [k for k in R if k not in C]
        changed = sorted(k for k in R if k in C and C[k][0] != R[k][0])
        added = sorted(k for k in C if k not in R)
        tot["online_rows"] += len(R); tot["missing_online"] += len(missing)
        tot["changed"] += len(changed); tot["added"] += len(added)
        if missing:
            viol.append((seq, f"online row missing from candidate: {missing[0]}"))
        if mode == "hid" and changed:
            viol.append((seq, f"hidden mode changed existing row: {changed[0]}"))
        if mode == "hid" and (set(R) - set(C) or any(C[k][0] != R[k][0] for k in R if k in C)):
            viol.append((seq, "online row set not byte-identical"))
        for k in added:
            if C[k][2] != "0.0010":
                viol.append((seq, f"added row conf {C[k][2]} != 0.0010 at {k}"))
        # (3)/(4) structure: group changed+added by id
        touched = collections.defaultdict(set)
        for f, i in changed + added:
            touched[i].add(f)
        for i, fs in touched.items():
            online_fr = sorted(f for (f, j) in R if j == i)
            first = online_fr[0] if online_fr else None
            bb = [f for f in fs if first is None or f < first]          # before the id's first online row
            tot["bb_rows"] += len(bb)
            if bb and first is not None:
                tot["bb_back_extent_max"] = max(tot["bb_back_extent_max"], first - min(bb))
            rest = sorted(f for f in fs if f not in bb)
            runs, cur = [], []
            for f in rest:
                if cur and f != cur[-1] + 1:
                    runs.append(cur); cur = []
                cur.append(f)
            if cur:
                runs.append(cur)
            if mode == "hid":
                # hidden mode leaves the emitted coast rows of a gap untouched, so the gap (and its endpoints, the two
                # detection frames) is taken from the SAME tracking run in mode all: runs[seq][id] = [(f0, f1), ...]
                gaps = [g for g in gap_ref.get(seq, {}).get(i, []) if any(g[0] < f < g[1] for f in rest)]
                for f in rest:
                    if not any(g[0] < f < g[1] for g in gaps):
                        viol.append((seq, f"id {i} frame {f}: added row outside every mode-all gap"))
                runs = [[f for f in rest if g[0] < f < g[1]] for g in gaps]
            else:
                gap_out.setdefault(seq, {}).setdefault(i, []).extend((r[0] - 1, r[-1] + 1) for r in runs)
            for run in runs:
                if mode == "hid":
                    g = [g for g in gaps if g[0] < run[0] < g[1]][0]
                    f0, f1 = g
                else:
                    f0, f1 = run[0] - 1, run[-1] + 1
                ok_end = all((e, i) in R and (e, i) in C and C[(e, i)][0] == R[(e, i)][0] for e in (f0, f1))
                if not ok_end:
                    viol.append((seq, f"id {i} frames {run[0]}-{run[-1]}: endpoint rows {f0}/{f1} not identical in both runs"))
                    continue
                g0, g1 = geo(R[(f0, i)][1]), geo(R[(f1, i)][1])
                tot["b_runs"] += 1; tot["b_run_len_max"] = max(tot["b_run_len_max"], len(run))
                if len(run) > L:
                    viol.append((seq, f"id {i} run {run[0]}-{run[-1]} longer than L"))
                for f in run:
                    a = (f - f0) / float(f1 - f0)
                    exp = tuple((1 - a) * x + a * y for x, y in zip(g0, g1))
                    got = geo(C[(f, i)][1])
                    err = max(abs(x - y) for x, y in zip(exp, got))
                    tot["b_rows"] += 1; tot["b_err_max"] = max(tot["b_err_max"], err)
                    if err > TOL:
                        viol.append((seq, f"id {i} frame {f}: off the line by {err:.3f}px (exp {exp}, got {got})"))
        P(f"  {seq}: " + " ".join(f"{k[5:]}={c.get(k, 0)}" for k in keys) + f" | online {len(R)} changed {len(changed)} added {len(added)}")
    P("  TOTAL " + ", ".join(f"{k}={v}" if k != 'b_err_max' else f"{k}={v:.4f}" for k, v in sorted(tot.items())))
    P(f"  violations: {len(viol)}")
    for s, v in viol[:6]:
        P(f"    {s}: {v}")
    logp = os.path.join(WIRE, name + ".log")
    txt = open(logp, encoding="utf-8", errors="replace").read()
    bad = [w for w in ("Traceback", "AssertionError") if w in txt]
    P(f"  log errors (Traceback/AssertionError => lag guard fired): {bad or 'none'}")
    P()
    return gap_out


for suffix, base in (("", "eval_recovery"), ("_t1", "eval")):
    ref = "wire_online" + suffix
    tag = "T3 val" if not suffix else "T1 val"
    gaps = check_run(tag, base, ref, "wire_pegc_all" + suffix, "all")
    check_run(tag, base, ref, "wire_pegc_hid" + suffix, "hid", gaps)
open(os.path.join(ROOT, "results", "peg_c", "wire_check.txt"), "w", encoding="utf-8").write("\n".join(OUT) + "\n")
