#!/usr/bin/env python3
"""Every file a real project of each stack legitimately contains must be
allowed by the Rule 5 hook.

Why this exists: every OTHER test in this suite builds an imaginary tree in
a tempdir. None of them ever ran the hook against what a real scaffold
(`create-next-app`, `nest new`, `flutter create`, ...) actually produces, so
a catalog `allowed_paths` list could look reasonable and still block most of
a real project without any test noticing. An audit of
`references/architecture-catalog.md` against real project layouts found 42
of 63 real files denied -- including `app/page.tsx` for Next.js (App Router
without `--src-dir` is the default), `main.py` for FastAPI, and
`integration_test/` for Flutter (Flutter's own official integration-test
directory, blocked by the same skill's Rule 2 that requires it).

Run with:  python3 tests/test_real_projects.py

Methodology note -- why this does NOT just stat the checked-in fixture
files in place: Rule 5 only polices file *placement*, not edits. The hook
short-circuits to allow whenever `os.path.exists(cwd/rel)` is already true
("an existing file is an edit, not a placement" -- see
`hooks/enforce_architecture.py`). Fixture files are checked into git, so
they always exist on disk; testing them in place would make every case
here vacuously pass no matter what `allowed_paths` said. To actually
exercise the contract, each fixture is copied into a scratch directory and,
for every file, that ONE file is deleted immediately before invoking the
hook (then restored) -- reproducing "the agent is about to create this file
here" instead of "this file is already here."
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
HOOK = ROOT / "hooks" / "enforce_architecture.py"

# Mirrors references/architecture-catalog.md. When the catalog changes, this
# table changes with it -- that is the point: this test is the objective
# lock that keeps allowed_paths honest against real project trees.
STACKS = {
    "nextjs-approuter": ["app/**", "src/**", "components/**", "lib/**",
                         "e2e/**", "tests/**", "prisma/**", "public/**",
                         "scripts/**", "*.config.*", "middleware.ts",
                         "instrumentation.ts", "*.d.ts"],
    "fastapi": ["app/**", "tests/**", "alembic/**", "migrations/**",
                "scripts/**", "*.py"],
    "flutter": ["lib/**", "test/**", "integration_test/**",
                "test_driver/**", "tool/**",
                "android/**/build.gradle.kts", "android/**/build.gradle",
                "android/**/settings.gradle.kts",
                "android/**/gradle.properties",
                "android/**/MainActivity.kt", "android/**/MainActivity.java",
                "ios/Runner/AppDelegate.swift", "ios/Runner/Info.plist",
                "ios/Runner/*.entitlements",
                "macos/Runner/AppDelegate.swift",
                "macos/Runner/MainFlutterWindow.swift",
                "macos/Runner/Info.plist", "macos/Runner/*.entitlements",
                "linux/runner/**", "windows/runner/**", "web/index.html"],
    "nestjs": ["src/**", "test/**", "prisma/**", "scripts/**",
               "*.config.*", "*.ts"],
    "astro": ["src/**", "tests/**", "public/**", "scripts/**",
              "*.config.*"],
    # Added beyond the original brief: every stack in the catalog that
    # declares `enforce` needs its allowed_paths locked against a real
    # tree, not just the ones with `enforce: deny`.
    "python-cli": ["src/**", "tests/**", "scripts/**", "docs/**", "*.py"],
    "data-ml": ["src/**", "tests/**", "notebooks/**", "data/**",
                "scripts/**", "*.py"],
}


def run_hook(cwd, rel_path):
    event = {"cwd": str(cwd), "tool_name": "Write",
             "tool_input": {"file_path": str(cwd / rel_path)}}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event),
                          capture_output=True, text=True, timeout=30)


class TestRealProjects(unittest.TestCase):
    def test_no_legitimate_file_is_blocked(self):
        failures = []
        with tempfile.TemporaryDirectory() as tmp:
            for stack, allowed in STACKS.items():
                src = FIXTURES / stack
                project = Path(tmp) / stack
                shutil.copytree(src, project)
                cfg_dir = project / ".claude-for-idiots"
                cfg_dir.mkdir(parents=True, exist_ok=True)
                (cfg_dir / "config.json").write_text(json.dumps({
                    "architecture": {"name": stack, "enforce": "deny",
                                     "allowed_paths": allowed, "layers": {}}}))
                for path in sorted(project.rglob("*")):
                    if not path.is_file():
                        continue
                    rel = path.relative_to(project).as_posix()
                    if rel.startswith(".claude-for-idiots/"):
                        continue
                    # Simulate "about to be created": Rule 5 exempts edits
                    # to files that already exist, so the file must be
                    # absent at the moment the hook runs.
                    path.unlink()
                    proc = run_hook(project, rel)
                    path.touch()
                    if proc.stdout.strip():
                        failures.append(stack + ": " + rel)
        self.assertEqual(failures, [], "arquivos legítimos bloqueados:\n" +
                         "\n".join(failures))


if __name__ == "__main__":
    unittest.main(verbosity=2)
