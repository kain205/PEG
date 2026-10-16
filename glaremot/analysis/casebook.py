"""Agent verdicts per failure case + aggregate casebook + run-vs-run diff.

One ``review.json`` per case directory (no write conflicts between parallel subagents);
``report`` aggregates them into ``casebook.md``.
"""
import glob
import json
import os
import time
from collections import Counter, defaultdict

import yaml

from . import io as aio
from .extract import load_events
from .matching import iou_matrix

TAXONOMY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "taxonomy.yaml")


def load_taxonomy():
    with open(TAXONOMY, encoding="utf-8") as f:
        return yaml.safe_load(f)


def case_path(run, event_id):
    return os.path.join(aio.run_dir(run), "cases", event_id.replace("/", "__"))


def review_path(run, event_id):
    return os.path.join(case_path(run, event_id), "review.json")


def write_review(run, event_id, label, confidence, evidence, note="", reviewer="agent"):
    tax = load_taxonomy()
    if label not in tax:
        raise SystemExit(f"unknown label '{label}'. valid: {', '.join(tax)}")
    if label == "other" and not note:
        raise SystemExit("label 'other' requires --note")
    if not 0.0 <= confidence <= 1.0:
        raise SystemExit("--confidence must be in [0, 1]")
    if not evidence.strip():
        raise SystemExit("--evidence is required (what you saw in which tile)")
    if event_id not in {e["event_id"] for e in load_events(run)}:
        raise SystemExit(f"no such event in {run}: {event_id}")
    os.makedirs(case_path(run, event_id), exist_ok=True)
    rec = dict(event_id=event_id, label=label, confidence=confidence, evidence=evidence, note=note,
               reviewer=reviewer, time=time.strftime("%Y-%m-%d %H:%M:%S"))
    with open(review_path(run, event_id), "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=1)
    return f"review saved -> {review_path(run, event_id)}"


def load_reviews(run):
    out = {}
    for p in glob.glob(os.path.join(aio.run_dir(run), "cases", "*", "review.json")):
        with open(p, encoding="utf-8") as f:
            r = json.load(f)
        out[r["event_id"]] = r
    return out


INCIDENT_TYPES = ("FN_RUN", "FP_RUN", "LOC_PAIR", "IDSW", "BURN_EP")   # ID_FRAG/MERGE, LOW_IOU are summaries


def incidents(events):
    """Group events that are one physical error (e.g. a partial box = FP_RUN + FN_RUN + LOC_PAIR):
    same seq, overlapping frame spans (+-2) and a shared GT id, pred id or explicit link.
    Returns a list of sorted event-id lists."""
    evs = [e for e in events if e["type"] in INCIDENT_TYPES]
    par = {e["event_id"]: e["event_id"] for e in evs}

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    by_seq = defaultdict(list)
    for e in evs:
        by_seq[e["seq"]].append(e)
    for es in by_seq.values():
        for i, a in enumerate(es):
            for b in es[i + 1:]:
                if a["frame_start"] > b["frame_end"] + 2 or b["frame_start"] > a["frame_end"] + 2:
                    continue
                if (set(a["gt_ids"]) & set(b["gt_ids"]) or set(a["pred_ids"]) & set(b["pred_ids"])
                        or b["event_id"] in a.get("links", []) or a["event_id"] in b.get("links", [])):
                    par[find(a["event_id"])] = find(b["event_id"])
    groups = defaultdict(list)
    for e in evs:
        groups[find(e["event_id"])].append(e["event_id"])
    return [sorted(g) for g in groups.values()]


def _incident_table(evs, rev):
    """Label x incident table: reviewed incidents take the label of their most confident review;
    FP/FN frames and IDSW are summed over the incident's FP_RUN/FN_RUN/IDSW events."""
    inc = incidents(evs.values())
    tot = Counter()
    for e in evs.values():
        if e["type"] in ("FP_RUN", "FN_RUN", "IDSW"):
            tot[e["type"]] += e["severity"] if e["type"] != "IDSW" else 1
    rows, cov = defaultdict(Counter), Counter()
    for g in inc:
        rs = [rev[x] for x in g if x in rev]
        if not rs:
            continue
        lab = max(rs, key=lambda r: r["confidence"])["label"]
        rows[lab]["incidents"] += 1
        for x in g:
            e = evs[x]
            if e["type"] in ("FP_RUN", "FN_RUN"):
                rows[lab][e["type"]] += e["severity"]
                cov[e["type"]] += e["severity"]
            elif e["type"] == "IDSW":
                rows[lab]["IDSW"] += 1
                cov["IDSW"] += 1
            elif e["type"] == "BURN_EP":
                rows[lab]["BURN_EP"] += 1
    n_rev = sum(1 for g in inc if any(x in rev for x in g))
    L = ["## Label x incident (one physical error = one incident)", "",
         f"{len(inc)} incidents from {sum(len(g) for g in inc)} events ({', '.join(INCIDENT_TYPES)}); "
         f"{n_rev} have >= 1 review. Reviewed incidents cover FP frames {cov['FP_RUN']:.0f}/{tot['FP_RUN']:.0f}, "
         f"FN frames {cov['FN_RUN']:.0f}/{tot['FN_RUN']:.0f}, IDSW {cov['IDSW']}/{tot['IDSW']}.", "",
         "| label | incidents | FP frames | FN frames | IDSW | burn episodes |", "|---|---|---|---|---|---|"]
    for lab, c in sorted(rows.items(), key=lambda kv: -(kv[1]["FP_RUN"] + kv[1]["FN_RUN"])):
        L.append(f"| {lab} | {c['incidents']} | {c['FP_RUN']:.0f} | {c['FN_RUN']:.0f} | {c['IDSW']} | {c['BURN_EP']} |")
    return L + [""]


def report(run, n_examples=5):
    evs = {e["event_id"]: e for e in load_events(run)}
    rev = load_reviews(run)
    tax = load_taxonomy()
    by_label = defaultdict(list)
    for eid, r in rev.items():
        by_label[r["label"]].append(eid)
    L = [f"# Casebook: {run}", "",
         f"{len(rev)} reviewed / {len(evs)} events ({len(evs) - len(rev)} unreviewed).", "",
         "## Label x event type (dataset in brackets)", "",
         "| label | n | by type | definition |", "|---|---|---|---|"]
    for lab in sorted(by_label, key=lambda k: -len(by_label[k])):
        c = Counter(f"{evs[e]['type']}[{evs[e]['dataset']}]" for e in by_label[lab] if e in evs)
        L.append(f"| {lab} | {len(by_label[lab])} | " + ", ".join(f"{k} {v}" for k, v in c.most_common())
                 + f" | {tax.get(lab, '?')} |")
    L += [""] + _incident_table(evs, rev)
    L += ["## Examples per label", ""]
    for lab in sorted(by_label, key=lambda k: -len(by_label[k])):
        L += [f"### {lab}", ""]
        for eid in sorted(by_label[lab], key=lambda e: -evs.get(e, {}).get("severity", 0))[:n_examples]:
            r, e = rev[eid], evs.get(eid, {})
            rel = f"cases/{eid.replace('/', '__')}/sheet.png"
            L.append(f"- [{eid}]({rel}) sev {e.get('severity', 0):.0f}, conf {r['confidence']}: {r['evidence']}"
                     + (f" ({r['note']})" if r["note"] else ""))
        L.append("")
    p = os.path.join(aio.run_dir(run), "casebook.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    return f"casebook -> {p}  ({len(rev)} reviews)"


# --------------------------------------------------------------------------- #
# diff between two runs (e.g. PEG vs backbone)
# --------------------------------------------------------------------------- #
def _same(ea, eb, tra, trb):
    """Same failure in both runs: same seq/type, overlapping frames, and same GT id
    (gt-based events) or overlapping boxes at a shared frame (FP_RUN)."""
    if ea["seq"] != eb["seq"] or ea["type"] != eb["type"]:
        return False
    s, e = max(ea["frame_start"], eb["frame_start"]), min(ea["frame_end"], eb["frame_end"])
    if s > e:
        return False
    if ea["gt_ids"] or eb["gt_ids"]:
        return set(ea["gt_ids"]) & set(eb["gt_ids"]) != set()
    for f in range(s, e + 1, max(1, (e - s) // 4)):
        ba = [r for r in tra.get(f, []) if r[0] in ea["pred_ids"]]
        bb = [r for r in trb.get(f, []) if r[0] in eb["pred_ids"]]
        if ba and bb and iou_matrix([ba[0][1:]], [bb[0][1:]])[0, 0] >= 0.5:
            return True
    return False


def diff_runs(a, b, min_sev=5):
    """Events in b but not a ('fixed by a') and in a but not b ('introduced by a')."""
    ma, mb = aio.load_run_meta(a), aio.load_run_meta(b)
    ea, eb = load_events(a), load_events(b)
    trk = {}

    def tr(meta, seq):
        k = (meta["results_subdir"], meta["tracker_name"], seq)
        if k not in trk:
            trk[k] = aio.load_mot(os.path.join(aio.tracker_dir(k[0], k[1]), f"{seq}.txt"))
        return trk[k]

    def missing(xs, ys, mx, my):
        out = []
        for e in xs:
            if e["severity"] < min_sev:
                continue
            if not any(_same(e, y, tr(mx, e["seq"]), tr(my, e["seq"])) for y in ys if y["seq"] == e["seq"]):
                out.append(e)
        return out

    fixed = missing(eb, ea, mb, ma)
    intro = missing(ea, eb, ma, mb)
    L = [f"# Diff: A={a}  B={b}  (severity >= {min_sev})", "",
         f"- fixed by A (in B, not in A): {len(fixed)} events, severity {sum(e['severity'] for e in fixed):.0f}",
         f"- introduced by A (in A, not in B): {len(intro)} events, severity {sum(e['severity'] for e in intro):.0f}", ""]
    for title, es in (("Fixed by A", fixed), ("Introduced by A", intro)):
        L += [f"## {title}", "", "| type | events | severity |", "|---|---|---|"]
        c, sv = Counter(e["type"] for e in es), defaultdict(float)
        for e in es:
            sv[e["type"]] += e["severity"]
        L += [f"| {t} | {n} | {sv[t]:.0f} |" for t, n in c.most_common()]
        L += ["", "Top 15:", ""] + [f"- {e['event_id']} {e['subtype']} sev {e['severity']:.0f}"
                                     for e in sorted(es, key=lambda e: -e["severity"])[:15]] + [""]
    p = os.path.join(aio.fa_root(), f"diff_{a}__vs__{b}.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    return "\n".join(L[:4]) + f"\n-> {p}"
