#!/usr/bin/env python3
"""Repo-wide consistency guards -- "the CI that would have caught all of
this" for the hooks-reliability effort.

None of these tests exercise a single hook's logic (test_hooks.py does
that) or a single fixture tree (test_real_projects.py does that). They
instead lock relationships BETWEEN files that nothing else checks: a data
file hand-mirrored into a test table, a command a hook prints to the user
that has to actually run, a safety net every hook script is expected to
have, and documentation that must not quietly start overpromising again.
Every one of these is a class of defect this project has already shipped
once with all other tests green -- see the task-12 report for the mutation
that proves each check actually fails when the consistency it guards is
broken.

Run with:  python3 tests/test_repo_consistency.py

Standard library only (plus `bash` on PATH for the shell-syntax check,
which is skipped -- not failed -- when bash is unavailable).
"""
import glob
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = ROOT / "hooks"


# ---------------------------------------------------------------------------
# 1. Architecture catalog vs. the STACKS table in test_real_projects.py
# ---------------------------------------------------------------------------
#
# references/architecture-catalog.md is prose + a data file: for each stack
# it documents `allowed_paths` and the reasoning behind every entry.
# tests/test_real_projects.py keeps a STACKS dict that is, by its own
# comment, a hand-maintained MIRROR of that same data, used to run the real
# Rule-5 hook against real fixture trees. Nothing enforces that the mirror
# stays a mirror: edit one `allowed_paths` line in the catalog (the
# reasoning-carrying, human-edited source) without touching the other, and
# every existing suite stays green -- test_real_projects.py would keep
# testing the OLD list forever, silently decoupled from the doc a human
# reads to understand what's allowed. This is the exact failure class the
# brief calls out as the most valuable check in this file.
def _parse_catalog_allowed_paths(markdown_text):
    """{heading (text before its trailing parenthetical) -> allowed_paths
    list} for every `## ` section in the catalog that declares one.

    The list is written as a backtick-fenced JSON-ish array, `["a", "b"]`,
    that may wrap across several lines (see the FastAPI/NestJS/Next.js/
    Flutter sections) -- so this matches non-greedily across the whole
    section body with re.DOTALL and then pulls out every quoted string,
    rather than assuming one line.
    """
    sections = re.split(r"(?m)^## ", markdown_text)[1:]
    result = {}
    for section in sections:
        heading_line, _, body = section.partition("\n")
        heading = heading_line.split("(", 1)[0].strip()
        match = re.search(r"`allowed_paths`:\s*`\[(.*?)\]`", body, re.DOTALL)
        if not match:
            continue
        result[heading] = re.findall(r'"((?:[^"\\]|\\.)*)"', match.group(1))
    return result


# Catalog heading (text before its parenthetical) -> STACKS key. This maps
# NAMES, which is low-risk metadata a renamed heading would loudly break
# (KeyError / a missing-key assertion below) -- it is the allowed_paths
# CONTENT behind each name, not the name itself, that drifted silently in
# the past and is what this test actually guards.
CATALOG_HEADING_TO_STACK_KEY = {
    "FastAPI": "fastapi",
    "NestJS": "nestjs",
    "Next.js": "nextjs-approuter",
    "Flutter": "flutter",
    "Python CLI / automation": "python-cli",
    "Data / ML prototype": "data-ml",
    "Astro": "astro",
}


# ---------------------------------------------------------------------------
# 2. config.example.json's shell commands must actually parse
# ---------------------------------------------------------------------------
#
# `migrations.command` is not just documentation: block_migration_edits.py
# reads it straight out of config.json and prints it verbatim as "Change
# the models/schema and run: <command>" (see hooks/block_migration_edits.py).
# It shipped for a time as `--name <describe_change>`, which LOOKS like a
# placeholder but is `<`/`>` shell redirection to bash -- the exact command
# Rule 1 told the user to run did not run. `tests.feature_test_cmd` is
# deliberately excluded: `npm test -- <pattern>` documents a substitution
# slot (like a man-page placeholder), never printed by a hook or run
# verbatim -- unlike the fields below, which the project's own
# quality-tools.md says must be "commands you have actually run once in
# this project."
SHELL_COMMAND_FIELDS = [
    ("migrations", "command"),
    ("tests", "full_suite_cmd"),
    ("tests", "lint_cmd"),
    ("tests", "format_cmd"),
    ("tests", "run_cmd"),
]


def _discover_hook_scripts():
    """Every hook entrypoint under hooks/ -- NOT the shared library module.

    Discovered by glob, not hardcoded by name, so a hook added after this
    test was written is automatically covered too.
    """
    return sorted(
        Path(p) for p in glob.glob(str(HOOKS_DIR / "*.py"))
        if Path(p).name != "_cfi_common.py"
    )


def _malformed_stdin_payloads(tmp):
    """Raw stdin bytes covering the shape of every fail-open bug this
    execution found: a top-level JSON value that isn't an object, garbage
    that isn't JSON at all, JSON nested deep enough to have triggered
    RecursionError before MAX_JSON_NESTING existed, and event fields typed
    as something other than what the hooks assume (int/list/null instead of
    str) -- the exact TypeError/AttributeError shape of the other three
    bugs. `tool_input` deliberately carries both `command` and `file_path`
    so the same payload set exercises all three hooks regardless of which
    field each one actually reads.
    """
    base_input = {
        "command": "git push origin main",
        "file_path": str(Path(tmp) / "new_file.py"),
    }
    base_event = {"cwd": tmp, "tool_name": "Bash", "tool_input": base_input}

    def with_input(**overrides):
        merged = dict(base_input)
        merged.update(overrides)
        return json.dumps({**base_event, "tool_input": merged})

    return {
        "empty_stdin": "",
        "not_json": "{not json at all",
        "top_level_int": json.dumps(42),
        "top_level_null": json.dumps(None),
        "top_level_list": json.dumps([1, 2, 3]),
        "deeply_nested_json": "[" * 5000 + "]" * 5000,
        "command_is_int": with_input(command=12345),
        "command_is_list": with_input(command=["git", "push"]),
        "command_is_null": with_input(command=None),
        "file_path_is_int": with_input(file_path=12345),
        "file_path_is_null": with_input(file_path=None),
        "tool_input_is_null": json.dumps({**base_event, "tool_input": None}),
        "tool_input_is_string": json.dumps({**base_event, "tool_input": "oops"}),
        "cwd_is_int": json.dumps({**base_event, "cwd": 12345}),
    }


# A config with the exact regressions this execution found in glob-class
# compilation ([b-a]/[z-a], a descending range that used to raise
# re.PatternError/re.error) sitting in BOTH sections a hook might read, so
# the sweep below also exercises the config-parsing path, not just the
# event-parsing path.
_BAD_REGEX_CONFIG = {
    "migrations": {
        "tool": "x", "command": "x",
        "protected_paths": ["[b-a]", "[z-a]"],
    },
    "architecture": {
        "name": "x", "enforce": "deny",
        "allowed_paths": ["[b-a]"], "layers": {},
    },
}


class TestRepoConsistency(unittest.TestCase):
    def test_every_asset_json_parses(self):
        for path in glob.glob(str(ROOT / "assets" / "*.json")):
            with open(path, encoding="utf-8") as handle:
                json.load(handle)

    def test_version_has_a_changelog_entry(self):
        version = (ROOT / "VERSION").read_text().strip()
        changelog = (ROOT / "CHANGELOG.md").read_text()
        self.assertIn("## [" + version + "]", changelog)

    def test_config_example_skill_version_matches(self):
        version = (ROOT / "VERSION").read_text().strip()
        config = json.loads((ROOT / "assets" / "config.example.json").read_text())
        self.assertEqual(config["skill_version"], version)

    def test_settings_template_references_shipped_hooks(self):
        settings = json.loads(
            (ROOT / "assets" / "settings.template.json").read_text())
        referenced = set(re.findall(r"hooks/(\w+\.py)", json.dumps(settings)))
        shipped = {p.name for p in (ROOT / "hooks").glob("*.py")}
        self.assertTrue(referenced <= shipped,
                        "settings aponta para hooks inexistentes: "
                        + str(referenced - shipped))

    # -- 3. every shipped hook must be wired into settings.template.json ----
    #
    # The check above catches "settings points at a hook that doesn't
    # exist." It does not catch the opposite and more likely mistake: a
    # hook lands under hooks/ and nobody adds it to settings.template.json,
    # so it ships in the skill but never actually runs for a user who
    # follows the template. Same discovery mechanism as the fail-open sweep
    # (_discover_hook_scripts, glob over hooks/*.py excluding the shared
    # _cfi_common.py module) so a hook added later is covered here too,
    # without hand-listing hook names in two places.
    def test_settings_template_registers_every_shipped_hook(self):
        settings = json.loads(
            (ROOT / "assets" / "settings.template.json").read_text())
        referenced = set(re.findall(r"hooks/(\w+\.py)", json.dumps(settings)))
        shipped = {p.name for p in _discover_hook_scripts()}
        unregistered = shipped - referenced
        self.assertFalse(
            unregistered,
            "hook(s) shipped under hooks/ but never wired into "
            "assets/settings.template.json -- a user who follows the "
            "template will never run them: " + str(unregistered))

    # -- 1. catalog x STACKS table -----------------------------------------
    def test_architecture_catalog_matches_real_projects_stacks_table(self):
        sys.path.insert(0, str(ROOT / "tests"))
        import test_real_projects as trp  # the hand-maintained mirror

        catalog_text = (ROOT / "references" / "architecture-catalog.md").read_text(
            encoding="utf-8")
        catalog = _parse_catalog_allowed_paths(catalog_text)

        missing_from_catalog = set(CATALOG_HEADING_TO_STACK_KEY) - set(catalog)
        self.assertFalse(
            missing_from_catalog,
            "catalog heading(s) not found -- CATALOG_HEADING_TO_STACK_KEY in "
            "tests/test_repo_consistency.py is stale: " + str(missing_from_catalog))

        self.assertEqual(
            set(CATALOG_HEADING_TO_STACK_KEY.values()), set(trp.STACKS),
            "stack set differs between references/architecture-catalog.md "
            "(via CATALOG_HEADING_TO_STACK_KEY) and tests/test_real_projects.py's "
            "STACKS table -- a stack was added/removed in one but not the other")

        mismatches = []
        for heading, stack_key in CATALOG_HEADING_TO_STACK_KEY.items():
            catalog_paths = catalog[heading]
            stacks_paths = trp.STACKS[stack_key]
            if catalog_paths != stacks_paths:
                mismatches.append(
                    f"{heading}: catalog={catalog_paths} "
                    f"STACKS[{stack_key!r}]={stacks_paths}")
        self.assertEqual(
            mismatches, [],
            "references/architecture-catalog.md's allowed_paths no longer "
            "matches tests/test_real_projects.py's STACKS table -- update "
            "both together (and re-run tests/test_real_projects.py against "
            "the fixture tree):\n" + "\n".join(mismatches))

    # -- 1b. rules.md x CLAUDE.template.md's numbered rule list -------------
    #
    # Same defect class as the catalog/STACKS check above: references/
    # rules.md's `## Rule N` headings (the source, prose + reasoning) and
    # assets/CLAUDE.template.md's numbered "## Rules (always apply)" list
    # (what actually ships into a user's CLAUDE.md) are two hand-maintained
    # copies of the same rule set. Nothing stops one from gaining/losing a
    # rule -- e.g. a new Rule 11 documented in rules.md but never added to
    # the template a user actually receives -- while every other test stays
    # green.
    def test_rules_doc_matches_claude_template_numbered_list(self):
        rules_text = (ROOT / "references" / "rules.md").read_text(encoding="utf-8")
        rule_numbers = set(re.findall(r"(?m)^## Rule (\d+)\b", rules_text))
        self.assertTrue(
            rule_numbers,
            "no '## Rule N' headings found in references/rules.md -- "
            "heading format changed, update the regex above")

        template_text = (ROOT / "assets" / "CLAUDE.template.md").read_text(
            encoding="utf-8")
        template_numbers = set(re.findall(r"(?m)^(\d+)\.\s+\*\*", template_text))
        self.assertTrue(
            template_numbers,
            "no numbered rule items found in assets/CLAUDE.template.md -- "
            "list format changed, update the regex above")

        self.assertEqual(
            rule_numbers, template_numbers,
            "references/rules.md's '## Rule N' headings and "
            "assets/CLAUDE.template.md's numbered rule list have drifted "
            "apart -- add/renumber the rule on both sides together:\n"
            f"only in rules.md: {sorted(rule_numbers - template_numbers, key=int)}\n"
            f"only in CLAUDE.template.md: "
            f"{sorted(template_numbers - rule_numbers, key=int)}")

    # -- 2. embedded shell commands must actually parse ---------------------
    def test_config_example_shell_commands_are_syntactically_valid(self):
        # `shutil.which` is not enough: on the GitHub windows runner `bash`
        # IS on PATH but resolves to a stub that exits 1 with no stderr, so
        # every command would "fail" syntax checking and say nothing about
        # the commands under test. Probe with a known-good one and skip when
        # the checker itself is unusable.
        if shutil.which("bash") is None:
            self.skipTest("bash not found on PATH")
        try:
            probe = subprocess.run(["bash", "-n", "-c", "echo ok"],
                                   capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            self.skipTest("bash cannot be executed here")
        if probe.returncode != 0:
            self.skipTest("bash -n cannot validate syntax in this environment")

        config = json.loads((ROOT / "assets" / "config.example.json").read_text())
        failures = []
        for section, field in SHELL_COMMAND_FIELDS:
            command = config.get(section, {}).get(field)
            if not command:
                continue
            proc = subprocess.run(
                ["bash", "-n", "-c", command],
                capture_output=True, text=True, timeout=10)
            if proc.returncode != 0:
                failures.append(
                    f"{section}.{field} = {command!r}: {proc.stderr.strip()}")
        self.assertEqual(
            failures, [],
            "assets/config.example.json has a command that is not valid "
            "shell -- the hook prints this verbatim for the user to run:\n"
            + "\n".join(failures))

    # -- 4. every hook must fail open on ANY malformed input ----------------
    def test_every_hook_survives_malformed_stdin(self):
        hooks = _discover_hook_scripts()
        self.assertTrue(hooks, "no hook scripts found under hooks/ -- "
                                "glob pattern or HOOKS_DIR is wrong")

        failures = []
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp) / ".claude-for-idiots"
            cfg_dir.mkdir()
            (cfg_dir / "config.json").write_text(json.dumps(_BAD_REGEX_CONFIG))

            payloads = _malformed_stdin_payloads(tmp)
            for hook in hooks:
                for name, payload in payloads.items():
                    proc = subprocess.run(
                        [sys.executable, str(hook)],
                        input=payload, capture_output=True, text=True,
                        timeout=15)
                    if proc.returncode != 0:
                        failures.append(
                            f"{hook.name} exited {proc.returncode} on "
                            f"payload {name!r}: {proc.stderr.strip()[-400:]}")
        self.assertEqual(
            failures, [],
            "every hook must fail open (exit 0) on ANY malformed input -- "
            "this is the backstop against the next RecursionError/TypeError/"
            "re.error class of bug, and against a future hook shipping "
            "without it:\n" + "\n".join(failures))

    # -- 5. documentation must not promise a guarantee the hooks don't give -
    def test_docs_do_not_overclaim_hook_guarantees(self):
        # Mirrors the verification command from task-1 (which replaced this
        # exact language with honest "safety net, not a sandbox" wording) --
        # this test is what stops that language from quietly coming back.
        docs = [
            "README.md", "README.pt-br.md", "SKILL.md",
            "hooks/README.md", "references/rules.md",
        ]
        pattern = re.compile(
            r"guarantee[ds]?|garantid[oa]s?|\bimpossible\b|"
            r"literally can.?t|literalmente n[ãa]o consegue",
            re.IGNORECASE)
        failures = []
        for rel in docs:
            path = ROOT / rel
            if not path.exists():
                continue
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if pattern.search(line):
                    failures.append(f"{rel}:{lineno}: {line.strip()}")
        self.assertEqual(
            failures, [],
            "shipped docs must describe hooks as a safety net, not a "
            "guarantee (see task-1) -- found overclaiming language:\n"
            + "\n".join(failures))



    def test_every_skill_path_reference_exists(self):
        """Every repo file SKILL.md names in backticks is really there.

        SKILL.md routes the model to other files by path -- the update
        procedure, the rules, the glossary format. A pointer to a file that
        does not exist sends it looking for instructions it will never find,
        and nothing else in this suite notices: the prose still reads fine.
        This is the same defect class as the dangling `references/` pointer
        that reached the generated CLAUDE.md in 0.5.0, one level up.

        Only paths that look like repo files are checked -- a path under a
        user's project (`.claude-for-idiots/`, `docs/`, `.claude/`) is
        created in THEIR tree, not this one, so it is skipped on purpose.
        """
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        # A bare filename (`CLAUDE.md`, `_cfi_common.py`) is either a file in
        # the USER's project or a module named by basename, so only paths with
        # a directory component are repo paths this test can resolve.
        candidates = set(re.findall(
            r"`([A-Za-z0-9_][A-Za-z0-9_.-]*/[A-Za-z0-9_./-]*\.(?:md|py|json))`", text))
        user_tree = (".claude-for-idiots/", "docs/", ".claude/")
        missing = sorted(
            c for c in candidates
            if not c.startswith(user_tree) and not (ROOT / c).exists()
        )
        self.assertEqual(
            missing, [],
            f"SKILL.md points at repo files that do not exist: {missing}")

if __name__ == "__main__":
    unittest.main(verbosity=2)
