#!/usr/bin/env python3
"""Self-test for the register scripts, run in temp dirs: decisions.py, risks.py, new-id.sh, new-session.sh, lint.py.

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
control: none
status: {status}
decision: {decision}
session: session-v1
evidence: harness/sim --seed 1
---
# R{num}: a risk
"""


def decision(num="001", status="decided", by="bot", when="the read path lands", extra=""):
    return GOOD_DECISION.format(num=num, status=status, by=by, when=when, extra=extra)


def risk(num="001", lik=2, con=2, score=None, status="open", decision="none"):
    return GOOD_RISK.format(num=num, lik=lik, con=con, score=lik * con if score is None else score,
                            status=status, decision=decision)


class Registers(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.decisions = self.tmp / "decisions"
        self.risks = self.tmp / "risks"
        self.decisions.mkdir()
        self.risks.mkdir()
        self.env = dict(os.environ, DECISIONS_DIR=str(self.decisions), RISKS_DIR=str(self.risks))

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

    def test_risks_check_rules(self):
        self.write(self.risks, "R001-x.md", risk(lik=4, con=4, status="controlled"))
        self.assertEqual(self.run_script("risks.py", "check").returncode, 0)
        self.write(self.risks, "R001-x.md", risk(lik=4, con=4, status="proposed", decision="D-003"))
        self.assertEqual(self.run_script("risks.py", "check").returncode, 0)
        self.assert_risk_problem(risk(lik=2, con=3, score=5), "score '5' is not 2 x 3 = 6")
        self.assert_risk_problem(risk(lik=6, con=1), "likelihood '6' not 1-5")
        self.assert_risk_problem(risk(status="parked"), "status 'parked'")
        self.assert_risk_problem(risk(lik=3, con=4, status="open"), "score 12 needs a control")
        self.assert_risk_problem(risk(lik=2, con=3, status="accepted"), "accepted at score 6 without the decision")
        self.write(self.risks, "R001-x.md", risk(lik=2, con=3, status="accepted", decision="D-004"))
        self.assertEqual(self.run_script("risks.py", "check").returncode, 0)
        self.write(self.risks, "R001-x.md", risk(lik=2, con=2, status="accepted"))
        self.assertEqual(self.run_script("risks.py", "check").returncode, 0, "4 and under accepts without a decision")

    def test_risks_list_by_score_and_open(self):
        self.write(self.risks, "R001-low.md", risk("001", 1, 2))
        self.write(self.risks, "R002-high.md", risk("002", 5, 5, status="controlled"))
        self.write(self.risks, "R003-mid.md", risk("003", 2, 3))
        self.write(self.risks, "R004-acc.md", risk("004", 3, 3, status="accepted", decision="D-001"))
        listed = [l.split("\t")[0] for l in self.run_script("risks.py", "list").stdout.splitlines()]
        self.assertEqual(listed, ["R002", "R004", "R003", "R001"])
        opened = [l.split("\t")[0] for l in self.run_script("risks.py", "open").stdout.splitlines()]
        self.assertEqual(opened, ["R003"])


class Scaffolding(unittest.TestCase):
    """new-id.sh, new-session.sh and lint.py in a throwaway copy of the scripts, so they find their own root."""

    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        shutil.copytree(SCRIPTS, self.root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        (self.root / "project.env").write_text("HUMAN_REPO=../product\nSCRATCH_BUDGET=1K\n")
        (self.root / "sessions").mkdir()
        self.env = dict(os.environ)
        self.env.pop("DECISIONS_DIR", None)
        self.env.pop("RISKS_DIR", None)

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
        check = subprocess.run([str(self.root / "scripts" / "decisions.py"), "check"], capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stdout)
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
        for name in ("goal.md", "log.md", "human.md", "report.md", "session-state.md", "progress.md"):
            self.assertTrue((folder / name).is_file(), name)
        for name in ("findings", "scratch", "units", "jobs/pending", "jobs/running", "jobs/done"):
            self.assertTrue((folder / name).is_dir(), name)
        state = (folder / "session-state.md").read_text()
        for line in ("Status: building", "## Queue", "## Waiting", "## Done", "human head:", "lead head:"):
            self.assertIn(line, state)
        plain = pathlib.Path(self.run_script("new-session.sh", "task", "y").stdout.strip())
        self.assertEqual(plain.name, "session-v12-task-y")
        self.assertFalse((plain / "session-state.md").exists())

    def test_lint(self):
        lint = [sys.executable, str(self.root / "scripts" / "lint.py")]
        self.assertEqual(subprocess.run(lint, capture_output=True).returncode, 0)
        (self.root / "INDEX.md").write_text("x" * 401 + "\n")
        out = subprocess.run(lint, capture_output=True, text=True)
        self.assertIn("INDEX.md:1: 401 characters", out.stderr)
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


if __name__ == "__main__":
    unittest.main(verbosity=1)
