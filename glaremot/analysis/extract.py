"""Run-level extraction: events.jsonl + summary.md (with RECONCILIATION vs the benchmark txt)."""
import json
import os
import re
from collections import Counter, defaultdict

from ..config import load_config, results_dir
from ..eval import eval_recovery as er
from . import io as aio
from .events import extract_burn_episodes, extract_sequence
from .matching import evaluate
from .tags import annotate

BOOL_TAGS = ["glare", "small", "edge", "occluded", "gt_uncertain", "near_gt_birth",
             "near_gt_death", "after_gap"]
CONT = ("idsw", "frag", "id_off", "n_ep", "n_surv")


# --------------------------------------------------------------------------- #
# benchmark parsing + reconciliation
# --------------------------------------------------------------------------- #
def _report_files(subdir, prefix, tracker_name):
    """results/<subdir>/<prefix>_<tracker>_<split>.txt (exact tracker name: 'peg_fs' must not
    pick up 'peg_fs_noguard')."""
    pat = re.compile(rf"^{prefix}_{re.escape(tracker_name)}_(val|test|all|heldout)\.txt$")
    d = results_dir(load_config(), subdir)
    return sorted(os.path.join(d, f) for f in os.listdir(d) if pat.match(f))


def parse_benchmark(subdir, tracker_name):
    """First table of results/<subdir>/benchmark_<tracker>_*.txt -> ({seq: row}, path)."""
    files = _report_files(subdir, "benchmark", tracker_name)
    if not files:
        return {}, None
    rows = {}
    for ln in open(files[0], encoding="utf-8"):
        p = ln.split()
        if len(p) == 11 and re.match(r"^[\d.]+$", p[1]):
            rows[p[0]] = dict(IDF1=float(p[4]), IDSW=int(p[6]), FP=int(p[9]), FN=int(p[10]))
        elif p and p[0] == "-" * len(p[0]) and rows and "COMBINED" in rows:
            break
    return rows, files[0]


def reconcile_mot(mine, bench):
    """mine: {seq: dict(FP,FN,IDSW,IDTP,IDFN,IDFP)} -> (lines, all_ok)."""
    tot = Counter()
    for m in mine.values():
        tot.update(m)
    mine = dict(mine)
    mine["COMBINED"] = dict(tot)
    hdr = f"| seq | FP (bench/mine) | FN | IDSW | IDF1 | ok |\n|---|---|---|---|---|---|"
    lines, ok_all = [hdr], True
    for seq, m in mine.items():
        d = 2 * m["IDTP"] + m["IDFN"] + m["IDFP"]
        idf1 = round(100 * 2 * m["IDTP"] / d, 2) if d else 0.0
        b = bench.get(seq)
        if b is None:
            lines.append(f"| {aio.short_name(seq)} | {m['FP']} | {m['FN']} | {m['IDSW']} | {idf1} | no benchmark row |")
            continue
        ok = (b["FP"], b["FN"], b["IDSW"]) == (m["FP"], m["FN"], m["IDSW"]) and abs(b["IDF1"] - idf1) <= 0.01
        ok_all &= ok
        lines.append(f"| {aio.short_name(seq)} | {b['FP']}/{m['FP']} | {b['FN']}/{m['FN']} | "
                     f"{b['IDSW']}/{m['IDSW']} | {b['IDF1']}/{idf1} | {'OK' if ok else 'MISMATCH'} |")
    return lines, ok_all


def parse_recovery_report(subdir, tracker_name):
    files = _report_files(subdir, "recovery", tracker_name)
    if not files:
        return None, None
    t = open(files[0], encoding="utf-8").read()
    g = lambda pat: int(re.search(pat, t).group(1))
    return dict(idsw=g(r"IDSW\)\s*:\s*(\d+)"), frag=g(r"Frag\)\s*:\s*(\d+)"),
                id_off=g(r"ID turned off \(track gone\):\s*(\d+)"),
                n_surv=g(r"survived to burn end\s*:\s*(\d+)/"),
                n_ep=g(r"survived to burn end\s*:\s*\d+/(\d+)")), files[0]


def reconcile_recovery(mine, rep):
    hdr = "| seq | " + " | ".join(CONT) + " | ok |\n|---|" + "---|" * (len(CONT) + 1)
    lines, ok_all, tot = [hdr], True, Counter()
    for seq, (m, r) in mine.items():
        ok = all(m[k] == r[k] for k in CONT)
        ok_all &= ok
        tot.update(m)
        lines.append(f"| {aio.short_name(seq)} | " + " | ".join(f"{r[k]}/{m[k]}" for k in CONT)
                     + f" | {'OK' if ok else 'MISMATCH'} |")
    if rep:
        ok = all(rep[k] == tot[k] for k in CONT)
        ok_all &= ok
        lines.append("| TOTAL vs report | " + " | ".join(f"{rep[k]}/{tot[k]}" for k in CONT)
                     + f" | {'OK' if ok else 'MISMATCH'} |")
    return lines, ok_all


# --------------------------------------------------------------------------- #
# extraction
# --------------------------------------------------------------------------- #
def extract_run(results_subdir, tracker_name, data_root, dataset="real", split="test",
                images=True, recovery=False, seqs=None, log=print):
    run = aio.run_name(results_subdir, tracker_name)
    rdir = aio.run_dir(run)
    seqs = seqs or aio.default_seqs(results_subdir, tracker_name, data_root, split)
    events, mine, recon_rows = [], {}, {}
    for i, seq in enumerate(seqs, 1):
        sd = aio.load_seq(seq, data_root, results_subdir, tracker_name, dataset)
        if recovery:
            gt = er.load_mot(os.path.join(sd.seq_dir, "mot", "gt", "gt.txt"))
            trk = er.load_mot(os.path.join(aio.tracker_dir(results_subdir, tracker_name), f"{seq}.txt"))
            evs, cnt = extract_burn_episodes(seq, gt, trk, data_root)
            st = er.recovery_seq(seq, gt, trk, 0.5, glare_root=data_root)
            if st is not None:
                mine[seq] = (cnt, {k: st[k] for k in CONT})
            R, _ = evaluate(sd.gt, sd.trk, sd.T)
        else:
            evs, R, I = extract_sequence(seq, sd.gt, sd.trk, sd.T, dataset)
            mine[seq] = dict(FP=R.FP, FN=R.FN, IDSW=R.IDSW, IDTP=I.IDTP, IDFN=I.IDFN, IDFP=I.IDFP)
        annotate(evs, sd, R, images=images)
        events += evs
        log(f"[{i}/{len(seqs)}] {aio.short_name(seq)}: {len(evs)} events")
    with open(os.path.join(rdir, "events.jsonl"), "w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev.to_dict()) + "\n")
    aio.save_run_meta(run, dict(results_subdir=results_subdir, tracker_name=tracker_name,
                                data_root=data_root, dataset=dataset, split=split,
                                recovery=recovery, seqs=seqs))
    if recovery:
        rep, path = parse_recovery_report(results_subdir, tracker_name)
        rec_lines, ok = reconcile_recovery(mine, rep)
    else:
        bench, path = parse_benchmark(results_subdir, tracker_name)
        rec_lines, ok = reconcile_mot(mine, bench)
    write_summary(run, rdir, events, rec_lines, ok, path, seqs)
    return run, events, ok


def write_summary(run, rdir, events, rec_lines, ok, ref_path, seqs):
    L = [f"# Failure analysis: {run}", "",
         f"{len(events)} events over {len(seqs)} sequences.", "",
         f"## Reconciliation vs `{ref_path}` : {'ALL MATCH' if ok else 'MISMATCH'}", ""] + rec_lines
    ts = Counter((e.type, e.subtype) for e in events)
    sev = defaultdict(float)
    for e in events:
        sev[(e.type, e.subtype)] += e.severity
    L += ["", "## Events by type / subtype", "", "| type | subtype | events | severity sum |", "|---|---|---|---|"]
    L += [f"| {t} | {s} | {n} | {sev[(t, s)]:.0f} |" for (t, s), n in sorted(ts.items())]
    L += ["", "## Tags by type (events carrying the tag / total)", "",
          "| type | n | " + " | ".join(BOOL_TAGS) + " |", "|---|---|" + "---|" * len(BOOL_TAGS)]
    for typ in sorted({e.type for e in events}):
        es = [e for e in events if e.type == typ]
        L.append(f"| {typ} | {len(es)} | " + " | ".join(
            str(sum(1 for e in es if e.tags.get(t))) for t in BOOL_TAGS) + " |")
    by_seq = defaultdict(lambda: [0, 0.0])
    for e in events:
        by_seq[e.seq][0] += 1
        by_seq[e.seq][1] += e.severity
    L += ["", "## Top sequences by total severity", "", "| seq | events | severity |", "|---|---|---|"]
    for s, (n, sv) in sorted(by_seq.items(), key=lambda kv: -kv[1][1])[:10]:
        L.append(f"| {aio.short_name(s)} | {n} | {sv:.0f} |")
    L += ["", "## Top-20 events by severity", "", "| event_id | subtype | frames | severity | tags |", "|---|---|---|---|---|"]
    for e in sorted(events, key=lambda e: -e.severity)[:20]:
        tg = ",".join(t for t in BOOL_TAGS if e.tags.get(t))
        L.append(f"| {e.event_id} | {e.subtype} | {e.frame_start}-{e.frame_end} | {e.severity:.0f} | {tg} |")
    with open(os.path.join(rdir, "summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


def load_events(run):
    """events.jsonl -> list of dicts."""
    with open(os.path.join(aio.run_dir(run), "events.jsonl"), encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]
