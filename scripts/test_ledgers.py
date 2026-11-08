#!/usr/bin/env python3
"""Self-test for the register and scaffolding scripts, run in temp dirs: decisions.py, risks.py, findings.py,
skeleton.py, new-id.sh, new-session.sh, lint.py (default and --adoption), affected.sh, changed-tooling.sh.

  python3 scripts/test_ledgers.py
"""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

SCRIPTS = pathlib.Path(__file__).resolve().parent

GOOD_DECISION = """---
status: {status}
decided_by: {by}
touches: store::put
revisit_when: {when}
session: session-v1
{extra}---
# D-{num}: a decision

Why.
"""

GOOD_RISK = """---
likelihood: {lik}
consequence: {con}
score: {score}
control: {control}
status: {status}
decision: {decision}
session: session-v1
evidence: harness/sim --seed 1
---
# R{num}: a risk
"""


def decision(num="001", status="decided", by="bot", when="the read path lands", extra=""):
    return GOOD_DECISION.format(num=num, status=status, by=by, when=when, extra=extra)


def risk(num="001", lik=2, con=2, score=None, status="open", decision="none", control="none"):
    return GOOD_RISK.format(num=num, lik=lik, con=con, score=lik * con if score is None else score,
                            status=status, decision=decision, control=control)


GOOD_FINDING = """---
class: {cls}
status: {status}
touches: store::put
evidence: {evidence}
{extra}---
Claim.
"""


def finding(cls="regression", status="open", evidence="scripts/run.sh -- python3 harness/sim.py --seed 3", extra=""):
    return GOOD_FINDING.format(cls=cls, status=status, evidence=evidence, extra=extra)


class Registers(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.decisions = self.tmp / "decisions"
        self.risks = self.tmp / "risks"
        self.sessions = self.tmp / "sessions"
        self.decisions.mkdir()
        self.risks.mkdir()
        self.env = dict(os.environ, DECISIONS_DIR=str(self.decisions), RISKS_DIR=str(self.risks),
                        SESSIONS_DIR=str(self.sessions))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_script(self, *argv):
        return subprocess.run([str(SCRIPTS / argv[0]), *argv[1:]], capture_output=True, text=True, env=self.env)

    def write(self, folder, name, text):
        (folder / name).write_text(text)

    def assert_decision_problem(self, text, expected):
        self.write(self.decisions, "001-x.md", text)
        out = self.run_script("decisions.py", "check")
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn(expected, out.stdout)

    def test_decisions_empty_register_is_clean(self):
        for cmd in ([], ["provisional"], ["open"], ["stats"], ["check"]):
            self.assertEqual(self.run_script("decisions.py", *cmd).returncode, 0, cmd)
        self.decisions.rmdir()
        self.assertIn("0 decisions, 0 problems", self.run_script("decisions.py", "check").stdout)

    def test_decisions_well_formed_passes(self):
        self.write(self.decisions, "001-x.md", decision())
        self.write(self.decisions, "002-y.md", decision("002", "overturned", "human-informed", extra="replaced_by: D-001\n"))
        out = self.run_script("decisions.py", "check")
        self.assertEqual(out.returncode, 0, out.stdout)

    def test_decisions_check_catches_each_malformation(self):
        self.assert_decision_problem(decision().replace("touches: store::put\n", ""), "missing touches")
        self.assert_decision_problem(decision(status="maybe"), "status 'maybe'")
        self.assert_decision_problem(decision(by="agent"), "decided_by 'agent'")
        self.assert_decision_problem(decision(status="overturned"), "overturned without replaced_by")
        self.assert_decision_problem(decision(status="confirmed", by="bot"), "confirmed with decided_by bot")
        self.assert_decision_problem(decision(when="session-v9"), "revisit_when names a session")
        self.assert_decision_problem(decision(num="007"), "does not match file name")
        self.assert_decision_problem("# D-001: no frontmatter\n", "no --- frontmatter")
        self.assert_decision_problem(
            decision().replace("store::put", "<path::Symbol in the human repo, lead or a harness>"),
            "line 4 still holds a skeleton placeholder")
        self.assert_decision_problem(
            decision() + "<Why, in a sentence or two. Alternatives and why not. Evidence: command or file.>\n",
            "skeleton placeholder")

    def test_decisions_generic_types_are_not_placeholders(self):
        self.write(self.decisions, "001-x.md", decision() + "Keeps a Vec<u8> and a Map<K, V> per shard, run as "
                   "<tool> <the event that reopens it now>.\nQuoted: `<the event that reopens it>` stays prose.\n")
        out = self.run_script("decisions.py", "check")
        self.assertEqual(out.returncode, 0, out.stdout)

    def test_decisions_duplicate_ids(self):
        self.write(self.decisions, "001-x.md", decision())
        self.write(self.decisions, "001-y.md", decision())
        self.assertIn("D-001: duplicate id", self.run_script("decisions.py", "check").stdout)

    def test_decisions_stats_overturn_rate_and_provisional(self):
        files = [("decided", "bot", ""), ("decided", "bot", ""), ("decided", "human-asked", ""),
                 ("confirmed", "human-asked", ""), ("overturned", "human-asked", "replaced_by: D-001\n"),
                 ("overturned", "human-asked", "replaced_by: D-001\n"), ("confirmed", "human-informed", "")]
        for n, (status, by, extra) in enumerate(files, 1):
            self.write(self.decisions, f"{n:03d}-d.md", decision(f"{n:03d}", status, by, extra=extra))
        lines = {l.split("\t")[0]: l.split("\t") for l in self.run_script("decisions.py", "stats").stdout.splitlines()}
        self.assertEqual(lines["human-asked"][-1], "2/3 (66%)")
        self.assertEqual(lines["human-informed"][-1], "0/1 (0%)")
        self.assertEqual(lines["bot"][-1], "-")
        self.assertEqual(lines["provisional"], ["provisional", "3"])
        provisional = self.run_script("decisions.py", "provisional").stdout.splitlines()
        self.assertEqual([l.split("\t")[0] for l in provisional], ["D-001", "D-002", "D-003"])

    def assert_risk_problem(self, text, expected):
        self.write(self.risks, "R001-x.md", text)
        out = self.run_script("risks.py", "check")
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn(expected, out.stdout)

    def test_risks_empty_register_is_clean(self):
        for cmd in ([], ["open"], ["check"]):
            self.assertEqual(self.run_script("risks.py", *cmd).returncode, 0, cmd)

    def assert_risk_ok(self, text, why=""):
        self.write(self.risks, "R001-x.md", text)
        out = self.run_script("risks.py", "check")
        self.assertEqual(out.returncode, 0, why + out.stdout)

    def test_risks_check_rules(self):
        self.write(self.decisions, "003-made.md", decision("003", "decided", "human-asked"))
        self.write(self.decisions, "004-open.md", decision("004", "open", "none"))
        self.write(self.decisions, "005-nobody.md", decision("005", "deferred", "none"))
        self.assert_risk_problem(risk(lik=2, con=3, score=5), "score '5' is not 2 x 3 = 6")
        self.assert_risk_problem(risk(lik=6, con=1), "likelihood '6' not 1-5")
        self.assert_risk_problem(risk(status="parked"), "status 'parked'")
        # open and proposed are the queue: any score passes.
        self.assert_risk_ok(risk(lik=5, con=5, status="open"), "open at 25: ")
        self.assert_risk_ok(risk(lik=4, con=4, status="proposed", control="crc on read"), "proposed at 16: ")
        # Status and control agree at any score: controlled and proposed name a control, open may not.
        self.assert_risk_problem(risk(lik=1, con=2, status="proposed"), "proposed with control: none")
        self.assert_risk_problem(risk(lik=1, con=2, status="controlled"), "controlled with control: none")
        self.assert_risk_problem(risk(lik=1, con=2, status="controlled", control=" None "), "controlled with control")
        self.assert_risk_ok(risk(lik=1, con=2, status="controlled", control="fsync before ack"), "controlled at 2: ")
        # 12 and up, controlled or accepted: a control and an existing decision.
        self.assert_risk_problem(risk(lik=4, con=4, status="controlled", decision="D-003"), "with control: none")
        self.assert_risk_problem(risk(lik=4, con=4, status="accepted", decision="D-003"), "with control: none")
        self.assert_risk_problem(risk(lik=4, con=4, status="controlled", control="crc on read"),
                                 "must cite an existing decision")
        self.assert_risk_problem(risk(lik=4, con=4, status="controlled", control="crc on read", decision="D-009"),
                                 "must cite an existing decision")
        self.assert_risk_ok(risk(lik=4, con=4, status="controlled", control="crc on read", decision="D-004"),
                            "controlled at 16 citing an open decision that exists: ")
        # 5 to 11 accepted: the decision exists and has been made.
        self.assert_risk_problem(risk(lik=2, con=3, status="accepted"), "accepted at score 6 must cite")
        self.assert_risk_problem(risk(lik=2, con=3, status="accepted", decision="D-009"), "accepted at score 6 must cite")
        self.assert_risk_problem(risk(lik=2, con=3, status="accepted", decision="D-004"), "accepted at score 6 must cite")
        self.assert_risk_problem(risk(lik=2, con=3, status="accepted", decision="D-005"), "accepted at score 6 must cite")
        self.assert_risk_ok(risk(lik=2, con=3, status="accepted", decision="D-003"))
        self.assert_risk_ok(risk(lik=2, con=2, status="accepted"), "4 and under accepts without a decision: ")
        self.assert_risk_problem(risk().replace("harness/sim --seed 1", "<command, test or tape that shows the scenario>"),
                                 "skeleton placeholder")
        self.assert_risk_ok(risk().replace("harness/sim --seed 1", "`<command, test or tape that shows the scenario>`"),
                            "backticked placeholder text is prose: ")

    def write_finding(self, name, text, session="session-v1-task-a"):
        folder = self.sessions / session / "findings"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(text)

    def assert_finding_problem(self, text, expected):
        self.write_finding("001-x.md", text)
        out = self.run_script("findings.py", "check")
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn(expected, out.stdout)

    def test_findings_check(self):
        self.assertEqual(self.run_script("findings.py", "check").returncode, 0)
        self.write_finding("001-x.md", finding())
        self.write_finding("002-y.md", finding("one-way-door", "adopted", extra="adopted_in: abc123\n"))
        out = self.run_script("findings.py", "check")
        self.assertEqual(out.returncode, 0, out.stdout)
        self.assert_finding_problem(finding(cls="bug"), "class 'bug' not one of")
        self.assert_finding_problem(finding(status="fixed"), "status 'fixed' not one of")
        self.assert_finding_problem(finding(evidence=""), "missing evidence")
        self.assert_finding_problem(finding(extra="adopted_in: abc\n"), "adopted_in on a finding with status 'open'")
        self.assert_finding_problem("Claim only.\n", "no --- frontmatter")
        self.assert_finding_problem(finding(evidence="<one command that reproduces it from this repo>"),
                                    "skeleton placeholder")
        skeleton = subprocess.run([sys.executable, str(SCRIPTS / "skeleton.py"), "render", "finding", "001", "x",
                                   "session-v1", "2026-01-01"], capture_output=True, text=True).stdout
        self.assert_finding_problem(skeleton, "skeleton placeholder")

    def test_registers_check_every_md_but_readme(self):
        cases = [("decisions.py", self.decisions, "001-x.md", decision(), ["D-1-x.md", "x.md", "001_x.md"]),
                 ("risks.py", self.risks, "R001-x.md", risk(), ["r001-x.md", "001-x.md", "Rx.md"])]
        for script, folder, good, text, bad_names in cases:
            for bad in bad_names:
                with self.subTest(script=script, name=bad):
                    for p in folder.glob("*.md"):
                        p.unlink()
                    self.write(folder, "README.md", "# Register\n")
                    self.write(folder, good, text)
                    self.assertEqual(self.run_script(script, "check").returncode, 0, script)
                    self.write(folder, bad, text)
                    out = self.run_script(script, "check")
                    self.assertEqual(out.returncode, 1, out.stdout)
                    self.assertIn(f"{bad}: file name", out.stdout)
        self.write_finding("001-x.md", finding())
        self.write_finding("README.md", "# Findings\n")
        self.assertEqual(self.run_script("findings.py", "check").returncode, 0)
        self.write_finding("lost-ack.md", finding())
        out = self.run_script("findings.py", "check")
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("lost-ack.md: file name", out.stdout)

    def test_registers_report_undecodable_files(self):
        (self.decisions / "001-x.md").write_bytes(b"---\nstatus: \xff\xfe\n---\n")
        out = self.run_script("decisions.py", "check")
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        self.assertIn("001-x.md: not UTF-8", out.stdout)

    def test_findings_stats_rows(self):
        self.write_finding("001-a.md", finding("regression", "open"))
        self.write_finding("002-b.md", finding("regression", "adopted"))
        self.write_finding("001-c.md", finding("time-sink", "noise"), session="session-v2-task-b")
        rows = self.run_script("findings.py", "stats").stdout.splitlines()
        self.assertEqual(rows[0], "| Class | Open | Adopted | Rejected | Noise |")
        self.assertIn("| regression | 1 | 1 | 0 | 0 |", rows)
        self.assertIn("| time-sink | 0 | 0 | 0 | 1 |", rows)
        self.assertIn("| one-way-door | 0 | 0 | 0 | 0 |", rows)

    def test_risks_list_by_score_and_open(self):
        self.write(self.risks, "R001-low.md", risk("001", 1, 2))
        self.write(self.risks, "R002-high.md", risk("002", 5, 5, status="controlled"))
        self.write(self.risks, "R003-mid.md", risk("003", 2, 3))
        self.write(self.risks, "R004-acc.md", risk("004", 3, 3, status="accepted", decision="D-001"))
        listed = [l.split("\t")[0] for l in self.run_script("risks.py", "list").stdout.splitlines()]
        self.assertEqual(listed, ["R002", "R004", "R003", "R001"])
        opened = [l.split("\t")[0] for l in self.run_script("risks.py", "open").stdout.splitlines()]
        self.assertEqual(opened, ["R003"])


COVERAGE_HEADER = "glob\tcommand\ttier\tbudget_s\tplant\n"


class Scaffolding(unittest.TestCase):
    """new-id.sh, new-session.sh and lint.py in a throwaway copy of the scripts, so they find their own root."""

    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        shutil.copytree(SCRIPTS, self.root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        (self.root / "project.env").write_text("HUMAN_REPO=../product\nSCRATCH_BUDGET=1K\n")
        (self.root / "sessions").mkdir()
        (self.root / "harness").mkdir()
        (self.root / "harness" / "coverage.tsv").write_text(COVERAGE_HEADER + "src/*.py\tpython3 t.py --tree \"$TREE\"\t"
                                                            "quick\t1\t\n")
        self.env = dict(os.environ, RUN_DIR=str(self.root / ".run"))
        for key in ("DECISIONS_DIR", "RISKS_DIR", "HUMAN_REPO", "PG_TMP"):
            self.env.pop(key, None)

    def tearDown(self):
        shutil.rmtree(self.root)

    def run_script(self, *argv):
        return subprocess.run([str(self.root / "scripts" / argv[0]), *argv[1:]],
                              capture_output=True, text=True, env=self.env)

    def test_new_id_sequential_and_skeletons_lint_as_expected(self):
        first = self.run_script("new-id.sh", "decision", "first-call")
        second = self.run_script("new-id.sh", "decision", "second-call")
        self.assertEqual(pathlib.Path(first.stdout.strip()).name, "001-first-call.md", first.stderr)
        self.assertEqual(pathlib.Path(second.stdout.strip()).name, "002-second-call.md")
        self.assertIn("# D-002: second call", pathlib.Path(second.stdout.strip()).read_text())
        # A skeleton fails the register check until an agent fills its placeholders.
        check = subprocess.run([str(self.root / "scripts" / "decisions.py"), "check"], capture_output=True, text=True)
        self.assertEqual(check.returncode, 1, check.stdout)
        self.assertIn("skeleton placeholder", check.stdout)
        made = self.run_script("new-id.sh", "risk", "torn-write")
        self.assertEqual(pathlib.Path(made.stdout.strip()).name, "R001-torn-write.md")
        # An unscored risk skeleton must fail the lint until an agent scores it.
        self.assertEqual(subprocess.run([str(self.root / "scripts" / "risks.py"), "check"],
                                        capture_output=True).returncode, 1)

    def test_new_id_parallel_never_collides(self):
        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(lambda n: self.run_script("new-id.sh", "decision", f"call-{n}"), range(24)))
        self.assertTrue(all(r.returncode == 0 for r in results), [r.stderr for r in results if r.returncode])
        numbers = sorted(p.name.split("-")[0] for p in (self.root / "decisions").glob("*.md"))
        self.assertEqual(numbers, [f"{n:03d}" for n in range(1, 25)])

    def test_new_id_finding_needs_a_session(self):
        self.assertEqual(self.run_script("new-id.sh", "finding", "bad").returncode, 2)
        session = self.root / "sessions" / "session-v4-task-x"
        session.mkdir()
        out = self.run_script("new-id.sh", "finding", "lost-ack", str(session))
        self.assertEqual(pathlib.Path(out.stdout.strip()), session / "findings" / "001-lost-ack.md")

    def test_new_session_numbers_and_factory_skeleton(self):
        (self.root / "sessions" / "session-v9-task-old").mkdir()
        (self.root / "sessions" / "session-v10-tend-old").mkdir()
        self.assertEqual(self.run_script("new-session.sh", "deploy", "x").returncode, 2)
        out = self.run_script("new-session.sh", "factory", "night-build")
        folder = pathlib.Path(out.stdout.strip())
        self.assertEqual(folder.name, "session-v11-factory-night-build", out.stderr)
        for name in ("goal.md", "log.md", "human.md", "report.md", "scraps.md", "session-state.md", "progress.md"):
            self.assertTrue((folder / name).is_file(), name)
        for name in ("findings", "briefs", "reviews", "scratch", "units", "jobs/pending", "jobs/running", "jobs/done"):
            self.assertTrue((folder / name).is_dir(), name)
        goal = (folder / "goal.md").read_text()
        for heading in ("## Ask", "## Acceptance", "## Delta", "## Weight", "## Builds on"):
            self.assertIn(heading + "\n", goal)
        self.assertIn("WARNING: HUMAN_REPO", out.stderr)
        state = (folder / "session-state.md").read_text()
        for line in ("Status: building", "## Queue", "## Waiting", "## Done", "human head:", "lead head:"):
            self.assertIn(line, state)
        plain = pathlib.Path(self.run_script("new-session.sh", "task", "y").stdout.strip())
        self.assertEqual(plain.name, "session-v12-task-y")
        self.assertFalse((plain / "session-state.md").exists())

    def test_new_session_parallel_never_collides(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda n: self.run_script("new-session.sh", "task", f"s{n}"), range(12)))
        self.assertTrue(all(r.returncode == 0 for r in results), [r.stderr for r in results if r.returncode])
        numbers = sorted(int(p.name.split("-")[1][1:]) for p in (self.root / "sessions").glob("session-v*"))
        self.assertEqual(numbers, list(range(1, 13)))

    def test_lint(self):
        lint = [sys.executable, str(self.root / "scripts" / "lint.py")]
        self.assertEqual(subprocess.run(lint, capture_output=True).returncode, 0)
        (self.root / "INDEX.md").write_text("x" * 401 + "\n")
        out = subprocess.run(lint, capture_output=True, text=True)
        self.assertIn("INDEX.md:1: line of 401 characters", out.stderr)
        long_session = "session-v3-task-x: " + "y" * 140
        (self.root / "INDEX.md").write_text(f"# Index\n\n{long_session}\n\n## Sessions\n\n{long_session}\n")
        out = subprocess.run(lint, capture_output=True, text=True)
        self.assertIn("INDEX.md:7: session line of 159 characters (max 150)", out.stderr)
        self.assertNotIn("INDEX.md:3", out.stderr)
        (self.root / "INDEX.md").write_text("ok\n")
        skill = self.root / ".claude" / "skills" / "big"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("line\n" * 121)
        self.assertIn("121 lines", subprocess.run(lint, capture_output=True, text=True).stderr)
        (skill / "SKILL.md").write_text("ok\n")
        scratch = self.root / "sessions" / "session-v1-task-a" / "scratch"
        scratch.mkdir(parents=True)
        (scratch / "blob").write_bytes(b"x" * 4096)
        self.assertEqual(subprocess.run(lint, capture_output=True).returncode, 1)
        cheap = subprocess.run([*lint, "--cheap"], capture_output=True, text=True)
        self.assertEqual(cheap.returncode, 0)
        self.assertIn("warning: sessions/*/scratch", cheap.stderr)

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True)

    def test_lint_fails_when_a_register_script_crashes(self):
        lint = [sys.executable, str(self.root / "scripts" / "lint.py")]
        self.assertEqual(subprocess.run(lint, capture_output=True).returncode, 0)
        risks = self.root / "scripts" / "risks.py"
        good = risks.read_text()
        risks.write_text(good + "\ndef broken(:\n")
        out = subprocess.run(lint, capture_output=True, text=True)
        self.assertEqual(out.returncode, 1, out.stderr)
        self.assertRegex(out.stderr, r"risks\.py check exited 1: .*SyntaxError")
        risks.write_text(good)
        (self.root / "decisions").mkdir()
        (self.root / "decisions" / "001-x.md").write_bytes(b"---\nstatus: \xff\n---\n# D-001: x\n")
        out = subprocess.run(lint, capture_output=True, text=True)
        self.assertEqual(out.returncode, 1, out.stderr)
        self.assertIn("decisions.py check exited 1", out.stderr)

    def test_lint_frozen_sessions(self):
        lint = [sys.executable, str(self.root / "scripts" / "lint.py")]
        done = self.root / "sessions" / "session-v1-task-done"
        live = self.root / "sessions" / "session-v2-task-live"
        for folder in (done, live):
            (folder / "findings").mkdir(parents=True)
            (folder / "units").mkdir()
            (folder / "report.md").write_text("# Report\n")
            (folder / "findings" / "001-x.md").write_text(finding())
            (folder / "units" / "u1.md").write_text("## Contract\nc\n\n## Changed by\n- first\n")
        (self.root / "INDEX.md").write_text("# Index\n\n## Sessions\n\nsession-v1-task-done: built x\n")
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base")
        self.assertEqual(subprocess.run(lint, capture_output=True).returncode, 0)
        # Allowed after finish: a finding's status and adopted_in, a unit's ## Changed by.
        for folder in (done, live):
            (folder / "findings" / "001-x.md").write_text(finding(status="adopted", extra="adopted_in: abc123\n"))
            (folder / "units" / "u1.md").write_text("## Contract\nc\n\n## Changed by\n- first\n- second\n")
        out = subprocess.run(lint, capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        # Refused in the finished session only: a report edit, a contract edit, a new file.
        for folder in (done, live):
            (folder / "report.md").write_text("# Report\nrewritten\n")
            (folder / "units" / "u1.md").write_text("## Contract\nchanged\n\n## Changed by\n- first\n- second\n")
            (folder / "extra.md").write_text("late\n")
            (folder / "findings" / "001-x.md").write_text(
                finding("one-way-door", "adopted", extra="adopted_in: abc123\n").replace("Claim.", "Reworded."))
        out = subprocess.run(lint, capture_output=True, text=True)
        self.assertEqual(out.returncode, 1)
        for name in ("report.md", "units/u1.md", "extra.md", "findings/001-x.md"):
            self.assertIn(f"sessions/session-v1-task-done/{name}:", out.stderr)
        self.assertNotIn("session-v2-task-live", out.stderr)
        # Committed past the hook (--no-verify): still caught, since the diff runs from the INDEX commit.
        self.git("add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "late", "--no-verify")
        out = subprocess.run(lint, capture_output=True, text=True)
        self.assertEqual(out.returncode, 1)
        self.assertIn("sessions/session-v1-task-done/report.md:", out.stderr)
        # A session finished later is judged from its own INDEX commit: earlier edits to it are history.
        (self.root / "INDEX.md").write_text("# Index\n\n## Sessions\n\nsession-v1-task-done: built x\n"
                                            "session-v2-task-live: built y\n")
        self.git("add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "finish v2")
        out = subprocess.run(lint, capture_output=True, text=True)
        self.assertNotIn("session-v2-task-live", out.stderr)
        (live / "report.md").write_text("# Report\nafter finish\n")
        self.assertIn("sessions/session-v2-task-live/report.md:", subprocess.run(lint, capture_output=True,
                                                                                text=True).stderr)

    def test_lint_frozen_skips_out_of_git_with_a_line(self):
        out = subprocess.run([sys.executable, str(self.root / "scripts" / "lint.py")], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("SKIP frozen sessions", out.stderr)

    def test_lint_coverage_and_plants(self):
        lint = [sys.executable, str(self.root / "scripts" / "lint.py")]
        table = self.root / "harness" / "coverage.tsv"
        plants = self.root / "harness" / "py" / "plants"
        plants.mkdir(parents=True)
        (plants / "good.patch").write_text("# Breaks x.\n# check: false\ndiff --git a/x b/x\n")
        (plants / "row-graded.patch").write_text("# Breaks z; its row's command is the check.\ndiff --git a/z b/z\n")
        rows = ["glob\tcommand\ttier\tbudget_s\tplant",
                "# commented\tanything\tnope\tx\tmissing.patch",
                "src/*.py\tpython3 t.py --tree \"$TREE\"\ttargeted\t20\tharness/py/plants/good.patch",
                "src/*.py\tpython3 u.py --tree ${TREE}/src\tquick\t1.5\tharness/py/plants/row-graded.patch",
                "src/*.py\tmake -C \"$TREE\" test\tquick\t1\t"]
        table.write_text("\n".join(rows) + "\n")
        out = subprocess.run(lint, capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        rows += ["src/*.py\tpython3 v.py --tree $TREE\tslow\tabout 20\tharness/py/plants/gone.patch", "too\tfew",
                 "src/*.py\tpython3 w.py --tree examples/kv/product\tquick\t1\t",
                 "src/*.py\tscripts/run.sh -t 60 -- python3 x.py --tree \"$TREE\"\tquick\t1\t"]
        table.write_text("\n".join(rows) + "\n")
        (plants / "nocheck.patch").write_text("# Breaks y.\ndiff --git a/y b/y\n# check: after the diff\n")
        out = subprocess.run(lint, capture_output=True, text=True)
        self.assertEqual(out.returncode, 1)
        for expected in ("coverage.tsv:6: tier 'slow'", "coverage.tsv:6: budget_s 'about 20'",
                         "coverage.tsv:6: plant 'harness/py/plants/gone.patch'", "coverage.tsv:7: 2 columns",
                         "coverage.tsv:8: command does not read $TREE",
                         "coverage.tsv:9: command wraps scripts/run.sh",
                         "harness/py/plants/nocheck.patch: no '# check: <command>' line"):
            self.assertIn(expected, out.stderr)
        for absent in ("coverage.tsv:2", "coverage.tsv:3", "coverage.tsv:4", "coverage.tsv:5", "good.patch",
                       "row-graded.patch"):
            self.assertNotIn(absent, out.stderr)
        # The table must exist and hold a data row: rows are what the harness tier grades.
        for text in (None, "glob\tcommand\ttier\tbudget_s\tplant\n# a comment\n\n"):
            with self.subTest(table=text):
                table.unlink(missing_ok=True)
                if text is not None:
                    table.write_text(text)
                for p in plants.glob("nocheck.patch"):
                    p.unlink()
                (plants / "row-graded.patch").write_text("# x\n# check: false\ndiff --git a/z b/z\n")
                out = subprocess.run(lint, capture_output=True, text=True)
                self.assertEqual(out.returncode, 1, out.stderr)
                self.assertIn("harness/coverage.tsv: " + ("missing" if text is None else "no data rows"), out.stderr)

    def test_clean_tmp_default_ages_out_and_all_clears(self):
        run = self.root / ".run"
        for rel in ("tmp/gate.old", "tmp/gate.new", "out/x-old", "logs/gate-new", "build/pycache"):
            (run / rel).mkdir(parents=True)
        day_old = __import__("time").time() - 25 * 3600
        for rel in ("tmp/gate.old", "out/x-old", "build/pycache"):
            os.utime(run / rel, (day_old, day_old))
        env = dict(self.env, PG_TMP=str(run / "tmp"))
        out = subprocess.run([str(self.root / "scripts" / "clean-tmp.sh")], capture_output=True, text=True, env=env)
        self.assertEqual(out.returncode, 0, out.stderr)
        left = sorted(str(p.relative_to(run)) for p in run.glob("*/*"))
        self.assertEqual(left, ["build/pycache", "logs/gate-new", "tmp/gate.new"])
        out = subprocess.run([str(self.root / "scripts" / "clean-tmp.sh"), "--all"], capture_output=True, text=True,
                             env=env)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(sorted(str(p.relative_to(run)) for p in run.glob("*/*")), ["build/pycache"])
        self.assertIn("clean-tmp: 2 removed", out.stdout)

    def test_changed_tooling(self):
        script = [str(self.root / "scripts" / "changed-tooling.sh")]
        (self.root / "docs").mkdir()
        (self.root / "docs" / "a.md").write_text("a\n")
        (self.root / "project.env").write_text("HUMAN_REPO=../product\n")
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base")
        self.assertEqual(subprocess.run([*script, "HEAD"], capture_output=True).returncode, 1)
        (self.root / "docs" / "a.md").write_text("b\n")
        self.assertEqual(subprocess.run([*script, "HEAD"], capture_output=True).returncode, 1, "docs are not tooling")
        (self.root / ".claude").mkdir()
        (self.root / ".claude" / "settings.json").write_text("{}\n")
        out = subprocess.run([*script, "HEAD"], capture_output=True, text=True)
        self.assertEqual((out.returncode, out.stdout), (0, ".claude/settings.json\n"))
        self.assertEqual(subprocess.run([*script, "nope"], capture_output=True).returncode, 2)

    def test_lint_adoption(self):
        lint = [sys.executable, str(self.root / "scripts" / "lint.py"), "--adoption"]
        (self.root / "AGENTS.md").write_text("# Rules\n\n## Project\n\n- **Human repo:** `<path>`.\n"
                                             "- **Workload shapes (optional):** <docs/workload-shapes.md, or none>\n"
                                             "\n## Next\n<x y z>\n")
        (self.root / "examples" / "kv").mkdir(parents=True)
        (self.root / "project.env").write_text("HUMAN_REPO=examples/kv\nTEMPLATE_ORIGIN=owner/template\n")
        docs = self.root / "docs"
        docs.mkdir()
        (docs / "workload-shapes.md").write_text("| Shape |\n|---|\n| EXAMPLE ROW: ingest |\n")
        (docs / "ARCHITECTURE.md").write_text("| Subsystem | Location | State |\n|---|---|---|\n"
                                              "| Gate | `scripts/gate.sh <tree> [quick\\|full]` | Stub: example only |\n")
        # Its own gate.sh, never the repo's: adopting the real one must not break this test.
        gate = self.root / "scripts" / "gate.sh"
        gate.write_text("#!/usr/bin/env bash\n# ADOPT: product stages below.\n"
                        "stage unit quick -- python3 examples/kv-python/harness/t.py --tree \"$TREE\"\n")
        self.git("init", "-q")
        self.git("remote", "add", "origin", "git@github.com:owner/template.git")
        out = subprocess.run(lint, capture_output=True, text=True, env=self.env)
        self.assertEqual(out.returncode, 1)
        for expected in ("HUMAN_REPO still points into examples/", "AGENTS.md:5: ## Project still holds template text",
                         "AGENTS.md:6: ## Project still holds template text",
                         "docs/workload-shapes.md still holds its EXAMPLE ROW marker",
                         "docs/ARCHITECTURE.md:3: Gate row still says Stub", "scripts/gate.sh:3:",
                         "git origin git@github.com:owner/template.git is the template"):
            self.assertIn(expected, out.stderr)
        self.assertNotIn("AGENTS.md:10", out.stderr)
        self.assertNotIn("references examples", out.stderr, "HUMAN_REPO in examples/ already says it")
        human = self.root / "product"
        human.mkdir()
        self.git("remote", "set-url", "origin", "git@github.com:owner/template-fork.git")
        (self.root / "project.env").write_text("HUMAN_REPO=product\nTEMPLATE_ORIGIN=owner/template\n")
        (self.root / "AGENTS.md").write_text("# Rules\n\n## Project\n\n- **Human repo:** `../product`.\n"
                                             "- **Workload shapes:** docs/workload-shapes.md\n")
        (docs / "workload-shapes.md").write_text("| Shape |\n|---|\n| Ingest |\n")
        (docs / "ARCHITECTURE.md").write_text("| Gate | `scripts/gate.sh` | Working: unit, sim |\n")
        gate.write_text("#!/usr/bin/env bash\n# was: stage kv-example quick -- examples/kv-python/gate.sh\n"
                        "stage unit quick -- python3 harness/t.py --tree \"$TREE\"\n")
        out = subprocess.run(lint, capture_output=True, text=True, env=self.env)
        self.assertEqual(out.returncode, 0, out.stderr)
        gate.write_text(gate.read_text() + "  stage kv quick -- bash examples/kv-python/gate.sh\n")
        self.assertIn("scripts/gate.sh:4:", subprocess.run(lint, capture_output=True, text=True, env=self.env).stderr)
        gate.write_text("#!/usr/bin/env bash\n")
        # Leftover pointers at the example, outside examples/ and outside the README's Adopting it steps.
        (self.root / "README.md").write_text("# T\n\n## Adopting it\n\n1. Delete `examples/`.\n\n## Map\n\n"
                                             "See examples/kv-python.\n")
        (docs / "ARCHITECTURE.md").write_text("| Gate | `scripts/gate.sh` | Working |\n"
                                              "| Worked example | `examples/kv-python/` | Delete |\n")
        (self.root / "harness" / "README.md").write_text("Pattern: examples/kv-python/harness.\n")
        (self.root / "harness" / "coverage.tsv").write_text("glob\tcommand\n# examples/ in a comment\n")
        (self.root / "INDEX.md").write_text("| quick | 0.48 s (lint 0.06, kv-example 0.42) |\n")
        (self.root / "examples" / "kv" / "README.md").write_text("examples/kv inside examples/ is fine\n")
        out = subprocess.run(lint, capture_output=True, text=True, env=self.env)
        self.assertEqual(out.returncode, 1, out.stderr)
        for expected in ("README.md:9: references examples/", "docs/ARCHITECTURE.md:2: references examples/",
                         "harness/README.md:1: references examples/", "INDEX.md:1: references examples/"):
            self.assertIn(expected, out.stderr)
        for absent in ("README.md:5:", "coverage.tsv", "examples/kv/README.md", "scripts/lint.py"):
            self.assertNotIn(absent, out.stderr)
        (self.root / "README.md").write_text("# T\n")
        (docs / "ARCHITECTURE.md").write_text("| Gate | `scripts/gate.sh` | Working |\n")
        (self.root / "harness" / "README.md").write_text("Pattern: harness/py.\n")
        (self.root / "INDEX.md").write_text("| quick | 0.48 s |\n")
        # Workload shapes: none, said plainly, needs no file.
        (docs / "workload-shapes.md").unlink()
        (self.root / "AGENTS.md").write_text("## Project\n\n- **Workload shapes:** none\n")
        gate.write_text("#!/usr/bin/env bash\n")
        out = subprocess.run(lint, capture_output=True, text=True, env=self.env)
        self.assertEqual(out.returncode, 0, out.stderr)


class Affected(unittest.TestCase):
    """affected.sh over a throwaway human repo and coverage table."""

    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        shutil.copytree(SCRIPTS, self.root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        self.human = self.root / "human"
        (self.human / "src" / "store").mkdir(parents=True)
        (self.human / "src" / "net.py").write_text("x\n")
        (self.human / "src" / "store" / "log.py").write_text("x\n")
        (self.human / "README.md").write_text("x\n")
        for args in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "b"]):
            subprocess.run(["git", "-C", str(self.human), *args], check=True, capture_output=True)
        (self.root / "project.env").write_text("HUMAN_REPO=human\n")
        (self.root / "harness").mkdir()
        rows = [("glob", "command", "tier", "budget_s", "plant"),
                ("# src/**", "never", "full", "1", "-"),
                ("src/**", "full-suite", "full", "600", "p0"),
                ("src/store/*.py", "store-test", "targeted", "20", "p1"),
                ("src/*.py", "net-test", "targeted", "10", "p2"),
                ("**/log.py", "store-test", "targeted", "20", "p1"),
                ("src/store/*.py", "store-quick", "quick", "60", "p3")]
        (self.root / "harness" / "coverage.tsv").write_text("".join("\t".join(r) + "\n" for r in rows))
        self.env = dict(os.environ, RUN_DIR=str(self.root / ".run"))
        self.env.pop("HUMAN_REPO", None)

    def tearDown(self):
        shutil.rmtree(self.root)

    def affected(self, *args):
        return subprocess.run([str(self.root / "scripts" / "affected.sh"), *args], capture_output=True, text=True,
                              env=self.env)

    def printed(self, *commands):
        return [f"TREE={self.human} bash -c {c}" for c in commands]

    def test_run_executes_with_tree_and_reports_verdicts(self):
        rows = ["glob\tcommand\ttier\tbudget_s\tplant",
                "src/*.py\ttest -f \"$TREE/src/net.py\"\ttargeted\t1\t",
                "src/*.py\tfalse\tquick\t1\t"]
        (self.root / "harness" / "coverage.tsv").write_text("\n".join(rows) + "\n")
        (self.human / "src" / "net.py").write_text("changed\n")
        out = self.affected()
        self.assertEqual(out.stdout.splitlines()[0], f"TREE={self.human} bash -c " + "test\\ -f\\ \\\"\\$TREE/src/net.py\\\"")
        for args in (["--run"], ["HEAD", "--run"], ["--run", "HEAD"]):
            with self.subTest(args=args):
                out = self.affected(*args)
                self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
                lines = out.stdout.splitlines()
                self.assertRegex(lines[0], r'^OK \d+\.\d\ds test -f "\$TREE/src/net.py"$')
                self.assertRegex(lines[1], r"^FAIL \d+\.\d\ds false$")

    def test_run_with_a_path_no_row_covers_is_blind(self):
        rows = ["glob\tcommand\ttier\tbudget_s\tplant", "src/*.py\ttrue\ttargeted\t1\t",
                "README.md\ttrue\tfull\t1\t"]
        (self.root / "harness" / "coverage.tsv").write_text("\n".join(rows) + "\n")
        (self.human / "src" / "net.py").write_text("changed\n")
        (self.human / "README.md").write_text("changed\n")
        out = self.affected("--run")
        self.assertEqual(out.returncode, 2, out.stdout + out.stderr)
        self.assertRegex(out.stdout, r"(?m)^OK \d+\.\d\ds true$")
        self.assertRegex(out.stdout, r"(?m)^BLIND affected \(1 changed path\(s\) no row up to tier quick covers: "
                                     r"README.md\)$")
        out = self.affected("--run", "--tier", "full")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertNotIn("BLIND", out.stdout)

    def test_nothing_changed(self):
        out = self.affected()
        self.assertEqual((out.returncode, out.stdout), (0, ""))
        self.assertIn("nothing changed", out.stderr)

    def test_uncommitted_change_targeted_first_deduped(self):
        (self.human / "src" / "store" / "log.py").write_text("y\n")
        out = self.affected()
        self.assertEqual(out.stdout.splitlines(), self.printed("store-test", "store-quick"), out.stderr)
        out = self.affected("--tier", "harness")
        self.assertEqual(out.stdout.splitlines(), self.printed("store-test", "store-quick"), out.stderr)
        out = self.affected("--tier", "full", "HEAD")
        self.assertEqual(out.stdout.splitlines(), self.printed("store-test", "store-quick", "full-suite"), out.stderr)
        self.assertEqual(self.affected("--tier", "slow").returncode, 2)

    def test_untracked_file_and_single_segment_star(self):
        (self.human / "src" / "dns.py").write_text("new\n")
        self.assertEqual(self.affected("--tier", "full").stdout.splitlines(), self.printed("net-test", "full-suite"))

    def test_since_base_ref_and_no_match(self):
        (self.human / "README.md").write_text("y\n")
        subprocess.run(["git", "-C", str(self.human), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "c"],
                       check=True, capture_output=True)
        self.assertIn("nothing changed", self.affected().stderr)
        out = self.affected("HEAD~1")
        self.assertEqual(out.stdout, "")
        self.assertIn("no coverage row up to tier quick matches the 1 changed path(s); run the quick gate", out.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=1)
