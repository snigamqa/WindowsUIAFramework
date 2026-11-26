#!/usr/bin/env python3
"""Build a traceability report: screen -> control -> test case -> script -> result -> evidence.

    python build_report.py --model model/app-model.json --cases cases/test-cases.json \
        --junit results/run1.xml results/run2.xml --evidence results/evidence --out report

--model is optional (imported cases without an app model still get a report).
Several --junit files are treated as repeated runs: all pass = passed, all fail = failed,
mixed = flaky.
"""
import argparse
import csv
import datetime
import glob
import html
import json
import os
import re
import xml.etree.ElementTree as ET

TC_RE = re.compile(r"TC-[A-Z0-9]+-\d+")


def load_json(path, default):
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def parse_junit(path):
    """Return {tc_id: (status, nodeid, message)} for one junit xml file."""
    out = {}
    root = ET.parse(path).getroot()
    for tc in root.iter("testcase"):
        props = {p.get("name"): p.get("value") for p in tc.iter("property")}
        name = tc.get("name", "")
        classname = tc.get("classname", "")
        tc_id = props.get("tc_id")
        if not tc_id:
            m = TC_RE.search(name) or TC_RE.search(classname)
            tc_id = m.group(0) if m else None
        if not tc_id:
            continue
        status, message = "passed", ""
        for tag, st in (("failure", "failed"), ("error", "failed"), ("skipped", "skipped")):
            el = tc.find(tag)
            if el is not None:
                status = st
                message = (el.get("message") or el.text or "").strip()[:500]
                break
        nodeid = "%s::%s" % (classname.replace(".", "/"), name) if classname else name
        out[tc_id] = (status, nodeid, message)
    return out


def merge_runs(run_results):
    """run_results: list of {tc_id: (status, nodeid, message)}."""
    merged = {}
    ids = set().union(*[set(r) for r in run_results]) if run_results else set()
    for tc_id in ids:
        statuses, nodeid, message = [], "", ""
        for r in run_results:
            if tc_id in r:
                st, nid, msg = r[tc_id]
                statuses.append(st)
                nodeid = nodeid or nid
                if st == "failed" and not message:
                    message = msg
            else:
                statuses.append("not run")
        if "not run" in statuses:
            final = "incomplete"
        elif all(s == "passed" for s in statuses):
            final = "passed"
        elif all(s == "failed" for s in statuses):
            final = "failed"
        elif all(s == "skipped" for s in statuses):
            final = "skipped"
        elif "passed" in statuses and "failed" in statuses:
            final = "flaky"
        else:
            final = "failed" if "failed" in statuses else "skipped"
        merged[tc_id] = {"status": final, "node": nodeid, "message": message, "runs": statuses}
    return merged


def find_evidence(evidence_dir, tc_id):
    if not evidence_dir or not os.path.isdir(evidence_dir):
        return []
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(evidence_dir, tc_id + "*")))


def build(model, cases_doc, results, evidence_dir):
    screens = {s["id"]: s for s in model.get("screens", [])}
    controls = {}
    for s in model.get("screens", []):
        for c in s.get("controls", []):
            c = dict(c)
            c["screen_id"] = s["id"]
            controls[c["id"]] = c

    rows, cases_out = [], []
    covered_controls = set()
    for case in cases_doc.get("cases", []):
        if case.get("retired"):
            continue
        res = results.get(case["id"])
        if case.get("automation") == "manual":
            status = "manual"
        elif res:
            status = res["status"]
        else:
            status = "not run"
        evid = find_evidence(evidence_dir, case["id"])
        entry = {
            "id": case["id"], "title": case.get("title", ""), "category": case.get("category", ""),
            "priority": case.get("priority", ""), "screen_id": case.get("screen_id"),
            "control_ids": case.get("control_ids", []), "oracle": case.get("oracle", ""),
            "automation": case.get("automation", ""), "source": case.get("source", ""),
            "source_id": case.get("source_id"), "status": status,
            "script": res["node"] if res else "", "message": res["message"] if res else "",
            "runs": res["runs"] if res else [], "evidence": evid,
        }
        cases_out.append(entry)
        links = case.get("control_ids") or [None]
        for cid in links:
            if cid:
                covered_controls.add(cid)
            ctl = controls.get(cid, {})
            rows.append({
                "screen_id": case.get("screen_id") or ctl.get("screen_id") or "",
                "screen_title": screens.get(case.get("screen_id") or ctl.get("screen_id") or "", {}).get("title", ""),
                "control_id": cid or "", "control": ("%s '%s'" % (ctl.get("control_type", ""), ctl.get("name", ""))).strip() if ctl else "",
                "automation_id": ctl.get("automation_id", "") if ctl else "",
                "case_id": case["id"], "source_id": case.get("source_id") or "",
                "case_title": case.get("title", ""), "oracle": case.get("oracle", ""),
                "script": entry["script"], "status": status, "evidence": ";".join(evid),
            })

    uncovered = [c for c in controls.values() if c.get("interactive") and c["id"] not in covered_controls]
    screens_without_cases = [s for sid, s in screens.items()
                             if not any(c["screen_id"] == sid for c in cases_out)]
    unlinked_cases = [c for c in cases_out if not c["control_ids"]]
    counts = {}
    for c in cases_out:
        counts[c["status"]] = counts.get(c["status"], 0) + 1
    interactive_total = sum(1 for c in controls.values() if c.get("interactive"))
    return {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "app": model.get("app", {}), "counts": counts, "total_cases": len(cases_out),
        "interactive_controls": interactive_total,
        "covered_controls": len([c for c in controls.values() if c.get("interactive") and c["id"] in covered_controls]),
        "cases": cases_out, "rows": rows,
        "gaps": {
            "uncovered_controls": [{"id": c["id"], "screen_id": c["screen_id"], "type": c.get("control_type"),
                                    "name": c.get("name"), "automation_id": c.get("automation_id")} for c in uncovered],
            "screens_without_cases": [{"id": s["id"], "title": s.get("title")} for s in screens_without_cases],
            "unlinked_cases": [c["id"] for c in unlinked_cases],
        },
        "skipped_controls": model.get("skipped", []),
    }


def e(x):
    return html.escape(str(x if x is not None else ""))


def table(headers, rows):
    head = "".join("<th>%s</th>" % e(h) for h in headers)
    body = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % c for c in r) for r in rows)
    return "<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (head, body)


def badge(status):
    return '<span class="b %s">%s</span>' % (re.sub(r"[^a-z]", "", status.lower()), e(status))


def render_html(rep, evidence_rel):
    c = rep["counts"]
    cov = (100.0 * rep["covered_controls"] / rep["interactive_controls"]) if rep["interactive_controls"] else 0
    unconfirmed = [x for x in rep["cases"] if x["oracle"] in ("observed", "inferred")]
    parts = ["""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Traceability report</title><style>
:root{--bg:#fff;--fg:#1c1c1c;--mut:#666;--line:#ddd;--card:#f6f6f6}
@media (prefers-color-scheme:dark){:root{--bg:#161616;--fg:#eee;--mut:#aaa;--line:#333;--card:#222}}
body{font:14px/1.45 system-ui,sans-serif;background:var(--bg);color:var(--fg);margin:24px}
h1{font-size:22px}h2{font-size:17px;margin-top:32px}
.cards{display:flex;flex-wrap:wrap;gap:10px}.card{background:var(--card);padding:10px 14px;border-radius:8px;min-width:110px}
.card b{display:block;font-size:22px}
.wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13px}
th,td{border:1px solid var(--line);padding:5px 8px;text-align:left;vertical-align:top}
th{background:var(--card)}.mut{color:var(--mut)}
.b{padding:1px 7px;border-radius:10px;font-size:12px;color:#fff;background:#777}
.passed{background:#2e7d32}.failed{background:#c62828}.flaky{background:#ef6c00}
.notrun{background:#757575}.incomplete{background:#ef6c00}.manual{background:#1565c0}.skipped{background:#8d6e63}
.warn{border-left:4px solid #ef6c00;background:var(--card);padding:8px 12px;margin:12px 0}
</style></head><body>"""]
    parts.append("<h1>Traceability report: %s</h1><p class='mut'>Generated %s</p>" % (
        e(rep["app"].get("name", "application")), e(rep["generated_at"])))
    cards = [("Cases", rep["total_cases"])] + [(k, v) for k, v in sorted(c.items())]
    cards.append(("Control coverage", "%.0f%%" % cov))
    parts.append('<div class="cards">%s</div>' % "".join(
        '<div class="card"><b>%s</b>%s</div>' % (e(v), e(k)) for k, v in cards))
    if unconfirmed:
        parts.append('<div class="warn"><b>%d cases have unconfirmed expectations</b> (oracle: observed or inferred). '
                     'They describe what the app did or what is conventional, not an approved requirement. '
                     'Review them before treating results as verification.</div>' % len(unconfirmed))

    parts.append("<h2>Traceability matrix</h2><div class='wrap'>")
    rows = []
    for r in rep["rows"]:
        ev = " ".join('<a href="%s/%s">%s</a>' % (e(evidence_rel), e(f), e(f)) for f in r["evidence"].split(";") if f)
        rows.append([e(r["screen_id"] + " " + r["screen_title"]), e(r["control_id"] + " " + r["control"]),
                     e(r["automation_id"]), e(r["case_id"] + (" (" + r["source_id"] + ")" if r["source_id"] else "")),
                     e(r["case_title"]), e(r["script"]), badge(r["status"]), ev])
    parts.append(table(["Screen", "Control", "AutomationId", "Test case", "Title", "Script", "Result", "Evidence"], rows))
    parts.append("</div>")

    g = rep["gaps"]
    parts.append("<h2>Coverage gaps</h2>")
    parts.append("<p>Interactive controls with no test case: <b>%d</b></p><div class='wrap'>%s</div>" % (
        len(g["uncovered_controls"]),
        table(["Control", "Screen", "Type", "Name", "AutomationId"],
              [[e(x["id"]), e(x["screen_id"]), e(x["type"]), e(x["name"]), e(x["automation_id"])]
               for x in g["uncovered_controls"]]) if g["uncovered_controls"] else ""))
    parts.append("<p>Screens with no test cases: <b>%d</b>. Cases not linked to a control: <b>%d</b>.</p>" % (
        len(g["screens_without_cases"]), len(g["unlinked_cases"])))

    bad = [x for x in rep["cases"] if x["status"] in ("failed", "flaky", "incomplete")]
    parts.append("<h2>Failures, incomplete runs, and flaky tests</h2>")
    if bad:
        parts.append("<div class='wrap'>%s</div>" % table(
            ["Case", "Title", "Result", "Runs", "Message", "Evidence"],
            [[e(x["id"]), e(x["title"]), badge(x["status"]), e(", ".join(x["runs"])), e(x["message"]),
              " ".join('<a href="%s/%s">%s</a>' % (e(evidence_rel), e(f), e(f)) for f in x["evidence"])] for x in bad]))
    else:
        parts.append("<p class='mut'>None.</p>")

    parts.append("<h2>Oracle review list</h2>")
    if unconfirmed:
        parts.append("<div class='wrap'>%s</div>" % table(
            ["Case", "Title", "Oracle", "Result"],
            [[e(x["id"]), e(x["title"]), e(x["oracle"]), badge(x["status"])] for x in unconfirmed]))
    else:
        parts.append("<p class='mut'>All expectations come from approved specs or cases.</p>")

    parts.append("<h2>Controls the explorer skipped</h2>")
    sk = rep["skipped_controls"]
    parts.append(("<div class='wrap'>%s</div>" % table(
        ["Screen", "Control", "Name", "Reason"],
        [[e(x.get("screen")), e(x.get("control")), e(x.get("name")), e(x.get("reason"))] for x in sk]))
        if sk else "<p class='mut'>None.</p>")
    parts.append("</body></html>")
    return "".join(parts)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model")
    ap.add_argument("--cases", required=True)
    ap.add_argument("--junit", nargs="*", default=[])
    ap.add_argument("--evidence")
    ap.add_argument("--out", default="report")
    args = ap.parse_args()

    if not os.path.isfile(args.cases):
        ap.error("case catalog not found: %s" % args.cases)
    if args.model and not os.path.isfile(args.model):
        ap.error("app model not found: %s" % args.model)
    missing_junit = [path for path in args.junit if not os.path.isfile(path)]
    if missing_junit:
        ap.error("JUnit file(s) not found: %s" % ", ".join(missing_junit))

    model = load_json(args.model, {})
    cases = load_json(args.cases, {"cases": []})
    runs = [parse_junit(p) for p in args.junit]
    results = merge_runs(runs)
    rep = build(model, cases, results, args.evidence)

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "traceability.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=2, ensure_ascii=False)
    with open(os.path.join(args.out, "traceability.csv"), "w", newline="", encoding="utf-8-sig") as f:
        cols = ["screen_id", "screen_title", "control_id", "control", "automation_id", "case_id",
                "source_id", "case_title", "oracle", "script", "status", "evidence"]
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rep["rows"])
    evidence_rel = os.path.relpath(args.evidence, args.out).replace("\\", "/") if args.evidence else "evidence"
    with open(os.path.join(args.out, "traceability.html"), "w", encoding="utf-8") as f:
        f.write(render_html(rep, evidence_rel))
    print("Report written to %s: %d cases, statuses %s, control coverage %d/%d" % (
        args.out, rep["total_cases"], rep["counts"], rep["covered_controls"], rep["interactive_controls"]))


if __name__ == "__main__":
    main()
