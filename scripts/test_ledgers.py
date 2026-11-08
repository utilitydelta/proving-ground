#!/usr/bin/env python3
"""Self-test for the register and scaffolding scripts, run in temp dirs: decisions.py, risks.py, new-id.sh,
new-session.sh, lint.py (default and --adoption), affected.sh.

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
        self.assert_decision_problem(decision().replace("store::put", "<path::Symbol in the human repo>"),
                                     "line 4 still holds a skeleton placeholder")
        self.assert_decision_problem(decision() + "<Why, in a sentence or two.>\n", "skeleton placeholder")

    def test_decisions_generic_types_are_not_placeholders(self):
        self.write(self.decisions, "001-x.md", decision() + "Keeps a Vec<u8> and a Map<K, V> per shard.\n")
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
        self.assert_risk_problem(risk().replace("harness/sim --seed 1", "<command, test or tape that shows it>"),
                                 "skeleton placeholder")

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
        for heading in ("## Ask", "## Acceptance", "## Delta", "## Builds on"):
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

    def test_lint_frozen_sessions(self):
        lint = [sys.executable, str(self.root / "scripts" / "lint.py")]
        done = self.root / "sessions" / "session-v1-task-done"
        live = self.root / "sessions" / "session-v2-task-live"
        for folder in (done, live):
            (folder / "findings").mkdir(parents=True)
            (folder / "units").mkdir()
            (folder / "report.md").write_text("# Report\n")
            (folder / "findings" / "001-x.md").write_text("---\nclass: regression\nstatus: open\n---\nClaim.\n")
            (folder / "units" / "u1.md").write_text("## Contract\nc\n\n## Changed by\n- first\n")
        (self.root / "INDEX.md").write_text("# Index\n\n## Sessions\n\nsession-v1-task-done: built x\n")
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base")
        self.assertEqual(subprocess.run(lint, capture_output=True).returncode, 0)
        # Allowed after finish: a finding's status and adopted_in, a unit's ## Changed by.
        for folder in (done, live):
            (folder / "findings" / "001-x.md").write_text(
                "---\nclass: regression\nstatus: adopted\nadopted_in: abc123\n---\nClaim.\n")
            (folder / "units" / "u1.md").write_text("## Contract\nc\n\n## Changed by\n- first\n- second\n")
        out = subprocess.run(lint, capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        # Refused in the finished session only: a report edit, a contract edit, a new file.
        for folder in (done, live):
            (folder / "report.md").write_text("# Report\nrewritten\n")
            (folder / "units" / "u1.md").write_text("## Contract\nchanged\n\n## Changed by\n- first\n- second\n")
            (folder / "extra.md").write_text("late\n")
            (folder / "findings" / "001-x.md").write_text(
                "---\nclass: one-way-door\nstatus: adopted\nadopted_in: abc123\n---\nClaim, reworded.\n")
        out = subprocess.run(lint, capture_output=True, text=True)
        self.assertEqual(out.returncode, 1)
        for name in ("report.md", "units/u1.md", "extra.md", "findings/001-x.md"):
            self.assertIn(f"sessions/session-v1-task-done/{name}:", out.stderr)
        self.assertNotIn("session-v2-task-live", out.stderr)

    def test_lint_adoption(self):
        lint = [sys.executable, str(self.root / "scripts" / "lint.py"), "--adoption"]
        (self.root / "AGENTS.md").write_text("# Rules\n\n## Project\n\n- **Human repo:** `<path>`.\n"
                                             "- **Workload shapes (optional):** docs/workload-shapes.md\n\n## Next\n<x y z>\n")
        (self.root / "examples" / "kv").mkdir(parents=True)
        (self.root / "project.env").write_text("HUMAN_REPO=examples/kv\n")
        out = subprocess.run(lint, capture_output=True, text=True, env=self.env)
        self.assertEqual(out.returncode, 1)
        for expected in ("HUMAN_REPO still points into examples/", "AGENTS.md:5: ## Project still holds a placeholder",
                         "docs/workload-shapes.md missing", "gate.sh still delegates"):
            self.assertIn(expected, out.stderr)
        self.assertNotIn("AGENTS.md:10", out.stderr)
        human = self.root / "product"
        human.mkdir()
        (self.root / "project.env").write_text("HUMAN_REPO=product\n")
        (self.root / "AGENTS.md").write_text("# Rules\n\n## Project\n\n- **Human repo:** `../product`.\n"
                                             "- **Workload shapes:** none\n")
        (self.root / "scripts" / "gate.sh").write_text("#!/usr/bin/env bash\necho OK product 0s\n")
        out = subprocess.run(lint, capture_output=True, text=True, env=self.env)
        self.assertEqual(out.returncode, 0, out.stderr)
        # The template's own lint never runs the adoption checks.
        self.assertEqual(subprocess.run(lint[:-1], capture_output=True, env=self.env).returncode, 0)


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

    def test_nothing_changed(self):
        out = self.affected()
        self.assertEqual((out.returncode, out.stdout), (0, ""))
        self.assertIn("nothing changed", out.stderr)

    def test_uncommitted_change_targeted_first_deduped(self):
        (self.human / "src" / "store" / "log.py").write_text("y\n")
        out = self.affected()
        self.assertEqual(out.stdout.splitlines(), ["store-test", "store-quick", "full-suite"], out.stderr)

    def test_untracked_file_and_single_segment_star(self):
        (self.human / "src" / "dns.py").write_text("new\n")
        self.assertEqual(self.affected().stdout.splitlines(), ["net-test", "full-suite"])

    def test_since_base_ref_and_no_match(self):
        (self.human / "README.md").write_text("y\n")
        subprocess.run(["git", "-C", str(self.human), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "c"],
                       check=True, capture_output=True)
        self.assertIn("nothing changed", self.affected().stderr)
        out = self.affected("HEAD~1")
        self.assertEqual(out.stdout, "")
        self.assertIn("no coverage row matches the 1 changed path(s); run the quick gate", out.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=1)
