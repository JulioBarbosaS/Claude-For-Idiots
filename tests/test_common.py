import io, random, re, sys, time, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
import _cfi_common as c


class TestCompileGlob(unittest.TestCase):
    def test_double_star_matches_zero_leading_dirs(self):
        self.assertTrue(c.matches_any("migrations/0001.py", ["**/migrations/**"]))

    def test_double_star_matches_nested_leading_dirs(self):
        self.assertTrue(c.matches_any("app/db/migrations/0001.py", ["**/migrations/**"]))

    def test_single_star_does_not_cross_separator(self):
        self.assertFalse(c.matches_any("src/app/page.tsx", ["*.tsx"]))
        self.assertTrue(c.matches_any("page.tsx", ["*.tsx"]))

    def test_root_config_glob(self):
        self.assertTrue(c.matches_any("next.config.mjs", ["*.config.*"]))
        self.assertFalse(c.matches_any("src/next.config.mjs", ["*.config.*"]))

    def test_prefix_glob_matches_nested(self):
        self.assertTrue(c.matches_any("src/a/b/c.ts", ["src/**"]))


class TestCharacterClass(unittest.TestCase):
    def test_digit_class_matches_numeric_migration(self):
        self.assertTrue(c.matches_any("migrations/0001_init.py", ["**/migrations/[0-9]*"]))

    def test_digit_class_rejects_non_numeric_file(self):
        self.assertFalse(c.matches_any("migrations/runner.ts", ["**/migrations/[0-9]*"]))

    def test_negated_class_excludes_listed_chars(self):
        self.assertTrue(c.matches_any("migrations/a.py", ["**/migrations/[!0-9]*"]))
        self.assertFalse(c.matches_any("migrations/0.py", ["**/migrations/[!0-9]*"]))

    def test_unterminated_bracket_is_literal_and_does_not_raise(self):
        try:
            result = c.matches_any("a[b", ["a[b"])
        except re.error:
            self.fail("compile_glob raised re.error on an unterminated '['")
        self.assertTrue(result)

    def test_invalid_character_range_does_not_raise(self):
        # A backwards range like [9-0] or [z-a] is valid glob-class SYNTAX
        # (a well-formed [...]) but not a valid regex range once translated,
        # so re.compile() raises re.error/re.PatternError while COMPILING
        # the pattern -- before .match() is ever called, and well before
        # _find_class_end's "unterminated bracket" fallback would ever kick
        # in. This is config.json-controlled input (migrations.protected_paths,
        # architecture.allowed_paths), same trust boundary as the rest of
        # this module: it must fail open (never match), never raise.
        for bad in ["**/migrations/[9-0]*", "**/migrations/[z-a]*"]:
            try:
                result = c.matches_any("migrations/0001_init.py", [bad])
            except re.error:
                self.fail(f"compile_glob raised re.error on {bad!r}")
            self.assertFalse(result, bad)


class TestGlobReDoS(unittest.TestCase):
    """CRITICAL-2 (fix round 1): repeated '**/' must not backtrack catastrophically.

    `(?:[^/]+/)*` emitted once per '**/' token concatenates into nested,
    overlapping quantifiers when the pattern repeats the token, which blows
    up exponentially on a non-matching path. A fixed implementation collapses
    the repeated token before translating, so this must stay well under a
    generous ceiling even though an unpatched version does not finish in
    under two minutes for the same input.
    """

    def test_repeated_doublestar_slash_does_not_backtrack_catastrophically(self):
        pattern = "**/" * 40 + "nomatch_never"
        rel_path = "a/" * 40 + "nomatch"
        start = time.monotonic()
        result = c.matches_any(rel_path, [pattern])
        elapsed = time.monotonic() - start
        self.assertFalse(result)
        self.assertLess(elapsed, 2.0, f"compile_glob took {elapsed:.2f}s -- ReDoS regression")

    def test_repeated_bare_doublestar_does_not_backtrack_catastrophically(self):
        pattern = "**" * 40 + "nomatch_never"
        rel_path = "a" * 80 + "nomatch"
        start = time.monotonic()
        result = c.matches_any(rel_path, [pattern])
        elapsed = time.monotonic() - start
        self.assertFalse(result)
        self.assertLess(elapsed, 2.0, f"compile_glob took {elapsed:.2f}s -- ReDoS regression")

    def test_repeated_star_does_not_backtrack_catastrophically(self):
        pattern = "*" * 60 + "nomatch_never"
        rel_path = "a" * 80 + "nomatch"
        start = time.monotonic()
        result = c.matches_any(rel_path, [pattern])
        elapsed = time.monotonic() - start
        self.assertFalse(result)
        self.assertLess(elapsed, 2.0, f"compile_glob took {elapsed:.2f}s -- ReDoS regression")

    def test_collapsed_doublestar_slash_still_matches_correctly(self):
        # Collapsing repeated '**/' must not change matching semantics.
        self.assertTrue(c.matches_any("app/db/migrations/0001.py",
                                       ["**/**/migrations/**"]))
        self.assertFalse(c.matches_any("app/db/migrations", ["**/**/x/**"]))


class TestGlobListWorkBudget(unittest.TestCase):
    """CRITICAL-A (fix round 3): the per-pattern/per-path caps bound a SINGLE
    compile_glob().match() call, but matches_any() iterates a whole list with
    no limit on how many patterns it tries. protected_paths/allowed_paths
    come from config.json, which comes from a cloned repo -- third-party
    input. A pattern near the per-pattern cap already costs a measurable
    fraction of a second; a list of hundreds of them must not multiply that
    cost by the list length, or a config.json alone can push a hook past
    Claude Code's 60s PreToolUse timeout.
    """

    # Near both caps: long literal run + wildcards + long literal run, so it
    # both maximizes token count (near MAX_GLOB_PATTERN_CHARS) and forces the
    # DP to scan the full path (near MAX_GLOB_PATH_CHARS) before failing to
    # match -- the worst case for a single compile_glob().match() call.
    _EXPENSIVE_PATTERN = "a" * 510 + "*" * 10 + "a" * 500 + "z"
    _NONMATCHING_PATH = "a" * (c.MAX_GLOB_PATH_CHARS - 1)

    def test_total_cost_does_not_scale_with_pattern_count(self):
        # The property under test: elapsed time for matches_any() stays
        # bounded by a small constant, REGARDLESS of how many expensive,
        # non-matching patterns the list holds. An unbounded implementation
        # makes this grow linearly (0.42s/pattern per the round-3 review
        # measurement); a bounded one does not, even at 600 patterns.
        for count in (1, 50, 600):
            start = time.monotonic()
            result = c.matches_any(self._NONMATCHING_PATH,
                                    [self._EXPENSIVE_PATTERN] * count)
            elapsed = time.monotonic() - start
            self.assertFalse(result)
            self.assertLess(
                elapsed, 3.0,
                f"{count} expensive patterns took {elapsed:.2f}s -- "
                "matches_any has no aggregate work budget")

    def test_a_pattern_list_whose_cost_exceeds_the_budget_returns_on_incomplete(self):
        # Deterministic (non-timing) version of the same property: build a
        # list of copies of the single most expensive possible pattern
        # (MAX_GLOB_PATTERN_CHARS tokens against a MAX_GLOB_PATH_CHARS
        # path), with enough copies that their cumulative cost is
        # mathematically guaranteed to exceed the aggregate budget -- the
        # count is DERIVED from the module's own constants, not hardcoded,
        # so this stays correct if MAX_GLOB_MATCH_WORK is ever retuned.
        path = "a" * c.MAX_GLOB_PATH_CHARS
        pattern = "?" * c.MAX_GLOB_PATTERN_CHARS
        single_cost = c.MAX_GLOB_PATTERN_CHARS * c.MAX_GLOB_PATH_CHARS
        count = c.MAX_GLOB_MATCH_WORK // single_cost + 2
        patterns = [pattern] * count
        self.assertGreater(single_cost * count, c.MAX_GLOB_MATCH_WORK)
        self.assertFalse(c.matches_any(path, patterns))
        self.assertTrue(c.matches_any(path, patterns, on_incomplete=True))

    def test_early_match_short_circuits_before_the_budget_matters(self):
        # A budget must never break ordinary, well-formed lists: the very
        # first (cheap) pattern in a normal-sized list still matches
        # immediately, even when later entries in the same list would have
        # been expensive.
        patterns = ["src/**", self._EXPENSIVE_PATTERN]
        self.assertTrue(c.matches_any("src/app/page.tsx", patterns))

    def test_realistic_pattern_list_is_unaffected_by_the_budget(self):
        # A real project's allowed_paths/protected_paths list (a handful of
        # short patterns) must keep matching exactly as before -- the budget
        # exists for pathological configs, not ordinary ones.
        patterns = ["app/**", "src/**", "components/**", "lib/**", "tests/**",
                    "*.config.*", "middleware.ts", "*.d.ts"]
        self.assertTrue(c.matches_any("src/app/page.tsx", patterns))
        self.assertFalse(c.matches_any("random/thing.py", patterns))


class TestCharacterClassNeverRaises(unittest.TestCase):
    """CRITICAL-B (fix round 3): compile_glob must never propagate re.error.

    _translate_class only escapes '\\' and a literal leading '^' -- it never
    validates the class body. A descending range ('[b-a]') reaches
    re.compile() unchanged and raises re.error, which was uncaught: a
    protected_paths/allowed_paths entry this shape crashed the hook (exit
    1, traceback) instead of failing open. Two rounds of review missed this
    because they were looking at backtracking, not validation.
    """

    def test_known_descending_range_does_not_raise(self):
        try:
            result = c.matches_any("b", ["[b-a]"])
        except re.error:
            self.fail("compile_glob raised re.error on a descending range")
        self.assertIsInstance(result, bool)

    def test_descending_range_behaves_as_non_matching_literal_class(self):
        # Documents the chosen fallback semantics: an invalid class matches
        # nothing, the same fail-open direction as an unterminated '[' or an
        # over-cap pattern -- never "matches everything" and never raises.
        self.assertFalse(c.matches_any("a", ["[b-a]"]))
        self.assertFalse(c.matches_any("b", ["[b-a]"]))
        self.assertFalse(c.matches_any("", ["[b-a]"]))

    def test_fuzzed_descending_ranges_never_raise(self):
        # Property test, not a PoC replay: generates many DIFFERENT
        # descending-range class bodies (random codepoints, random padding,
        # random negation) and confirms none of them ever raises, through
        # the real tokenizer path (compile_glob), not a hand-picked string.
        rng = random.Random(20260924)
        padding_chars = list("abcXYZ019!^-\\[]/*?.(){}|+$ ")
        paths = ["a", "z", "0-9", "abc/def.py", "[b-a]", "", "-", "^", "\\", "migrations/0001.py"]
        for _ in range(500):
            hi, lo = rng.sample(range(0x21, 0x7e), 2)
            if hi < lo:
                hi, lo = lo, hi
            # hi > lo in codepoint, written hi-lo -> guaranteed descending.
            range_body = chr(hi) + "-" + chr(lo)
            padding = "".join(rng.choice(padding_chars) for _ in range(rng.randint(0, 4)))
            position = rng.choice(("prefix", "suffix", "middle"))
            if position == "prefix":
                body = range_body + padding
            elif position == "suffix":
                body = padding + range_body
            else:
                half = len(padding) // 2
                body = padding[:half] + range_body + padding[half:]
            negate = rng.choice(("", "!"))
            pattern = "[" + negate + body + "]"
            for path in paths:
                try:
                    result = c.matches_any(path, [pattern])
                except re.error as exc:
                    self.fail(f"compile_glob raised re.error on pattern={pattern!r}: {exc}")
                self.assertIsInstance(result, bool)

    def test_fuzzed_arbitrary_bracket_junk_never_raises(self):
        # Broader, less targeted fuzz: arbitrary junk inside a class body,
        # not engineered to be any particular shape. Covers class-related
        # failure modes beyond descending ranges, should any exist.
        rng = random.Random(986123)
        junk_chars = list("abcXYZ019!^-\\[]/*?.(){}|+$~& \t")
        for _ in range(500):
            body = "".join(rng.choice(junk_chars) for _ in range(rng.randint(0, 10)))
            pattern = "[" + body + "]"
            try:
                result = c.matches_any("some/random/path.py", [pattern])
            except re.error as exc:
                self.fail(f"compile_glob raised re.error on pattern={pattern!r}: {exc}")
            self.assertIsInstance(result, bool)

    def test_well_formed_classes_are_unaffected(self):
        # Regression guard: the fix must not change matching for valid
        # classes -- only invalid ones get the new fallback behavior.
        self.assertTrue(c.matches_any("migrations/0001_init.py",
                                       ["**/migrations/[0-9]*"]))
        self.assertFalse(c.matches_any("migrations/runner.ts",
                                        ["**/migrations/[0-9]*"]))
        self.assertTrue(c.matches_any("migrations/a.py",
                                       ["**/migrations/[!0-9]*"]))


class TestReadEventDefensiveParsing(unittest.TestCase):
    """CRITICAL-1 (fix round 1): a pathologically nested JSON payload must
    fail open (return None), not crash the hook with RecursionError."""

    def test_deeply_nested_stdin_fails_open(self):
        payload = "[" * 60000 + "]" * 60000
        old_stdin = sys.stdin
        sys.stdin = io.StringIO(payload)
        try:
            start = time.monotonic()
            result = c.read_event()
            elapsed = time.monotonic() - start
        finally:
            sys.stdin = old_stdin
        self.assertIsNone(result)
        self.assertLess(elapsed, 5.0)

    def test_deeply_nested_config_fails_open(self, tmp_path=None):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp) / ".claude-for-idiots"
            cfg_dir.mkdir()
            payload = "[" * 60000 + "]" * 60000
            (cfg_dir / "config.json").write_text(payload)
            start = time.monotonic()
            result = c.load_config(tmp)
            elapsed = time.monotonic() - start
        self.assertIsNone(result)
        self.assertLess(elapsed, 5.0)


class TestRelativize(unittest.TestCase):
    def test_dot_dot_returns_none(self):
        self.assertIsNone(c.relativize("..", "/proj"))

    def test_traversal_back_to_project_root_returns_none(self):
        self.assertIsNone(c.relativize("sub/../..", "/proj"))

    def test_strips_dot_segments(self):
        self.assertEqual(c.relativize("./alembic/./versions/a.py", "/proj"),
                         "alembic/versions/a.py")

    def test_absolute_inside_project(self):
        self.assertEqual(c.relativize("/proj/src/x.ts", "/proj"), "src/x.ts")

    def test_outside_project_returns_none(self):
        self.assertIsNone(c.relativize("/etc/passwd", "/proj"))
        self.assertIsNone(c.relativize("../../etc/passwd", "/proj"))

    def test_non_ascii_path_is_ordinary(self):
        self.assertEqual(c.relativize("/proj/src/configuração.py", "/proj"),
                         "src/configuração.py")
        self.assertTrue(c.matches_any("src/configuração.py", ["src/**"]))

    def test_windows_style_separators_are_normalized(self):
        self.assertEqual(c.relativize("src\\app\\page.tsx", "/proj"), "src/app/page.tsx")

    def test_empty_path_returns_none(self):
        self.assertIsNone(c.relativize("", "/proj"))


class TestConfigHelpers(unittest.TestCase):
    def test_section_rejects_non_mapping(self):
        self.assertEqual(c.section({"architecture": "layered"}, "architecture"), {})
        self.assertEqual(c.section({"architecture": ["a"]}, "architecture"), {})
        self.assertEqual(c.section({}, "architecture"), {})

    def test_str_list_wraps_bare_string(self):
        self.assertEqual(c.str_list("src/**"), ["src/**"])
        self.assertEqual(c.str_list(["a", 2, None, "b"]), ["a", "b"])
        self.assertEqual(c.str_list(None), [])


class TestTargetPath(unittest.TestCase):
    def test_reads_file_path(self):
        self.assertEqual(c.target_path({"file_path": "a.py"}), "a.py")

    def test_falls_back_to_notebook_path(self):
        self.assertEqual(c.target_path({"notebook_path": "a.ipynb"}), "a.ipynb")

    def test_missing_returns_empty(self):
        self.assertEqual(c.target_path({}), "")
        self.assertEqual(c.target_path(None), "")


class TestLoadJsonFile(unittest.TestCase):
    """load_config(cwd) is now a thin wrapper over load_json_file(path) --
    these pin the generalized function's contract (bounded size/nesting,
    OSError/malformed -> None, non-object top-level -> None), since a
    second caller (require_feature_alignment.py, reading its own record
    file at a config-supplied path) now depends on the exact same
    guarantees load_config always had."""

    def _write(self, tmp, name, content):
        path = Path(tmp) / name
        path.write_text(content, encoding="utf-8")
        return str(path)

    def test_missing_file_returns_none(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(c.load_json_file(str(Path(tmp) / "nope.json")))

    def test_valid_object_is_returned(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "x.json", '{"a": 1}')
            self.assertEqual(c.load_json_file(path), {"a": 1})

    def test_non_object_top_level_returns_none(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            for content in ("[]", '"str"', "42", "null", "true"):
                path = self._write(tmp, "x.json", content)
                self.assertIsNone(c.load_json_file(path), content)

    def test_invalid_json_returns_none(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "x.json", "{not json")
            self.assertIsNone(c.load_json_file(path))

    def test_deeply_nested_json_returns_none_quickly(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "x.json", "[" * 60000 + "]" * 60000)
            start = time.monotonic()
            result = c.load_json_file(path)
            elapsed = time.monotonic() - start
        self.assertIsNone(result)
        self.assertLess(elapsed, 5.0)

    def test_load_config_is_load_json_file_at_the_config_path(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp) / ".claude-for-idiots"
            cfg_dir.mkdir()
            (cfg_dir / "config.json").write_text('{"architecture": {}}')
            self.assertEqual(c.load_config(tmp),
                             c.load_json_file(str(cfg_dir / "config.json")))


class TestIsPoliced(unittest.TestCase):
    """Moved from enforce_architecture.py so require_feature_alignment.py
    (Rule 10) can ask the exact same "is this code?" question instead of
    re-deriving it. Rule 5's own test_hooks.py suite still exercises this
    end to end through the real hook subprocess; these pin the shared
    function's contract directly."""

    def test_default_ignored_extensions_are_not_policed(self):
        for name in ["notes.md", "data.json", "config.yml", "Cargo.lock",
                     "logo.svg", "train.parquet", "model.pkl"]:
            self.assertFalse(c.is_policed(name), name)

    def test_common_code_extensions_are_policed(self):
        for name in ["x.py", "x.ts", "x.mjs", "x.astro", "x.sql", "x.sh"]:
            self.assertTrue(c.is_policed(name), name)

    def test_extensionless_files_are_never_policed(self):
        for name in ["Dockerfile", "LICENSE", "Makefile"]:
            self.assertFalse(c.is_policed(name), name)

    def test_dotenv_and_siblings_are_never_policed(self):
        for name in [".env", ".env.local", ".env.production"]:
            self.assertFalse(c.is_policed(name), name)

    def test_dotenv_stays_exempt_under_a_narrow_override(self):
        self.assertFalse(c.is_policed(".env.local", [".ts"]))

    def test_override_replaces_the_default_list(self):
        self.assertFalse(c.is_policed("x.ts", [".ts"]))
        self.assertTrue(c.is_policed("notes.md", [".ts"]))

    def test_override_normalizes_case_and_missing_dot(self):
        self.assertFalse(c.is_policed("x.TS", ["ts"]))

    def test_override_of_only_whitespace_falls_back_to_default(self):
        self.assertFalse(c.is_policed("notes.md", ["   "]))
        self.assertTrue(c.is_policed("x.ts", ["   "]))

    def test_no_override_uses_default_list(self):
        self.assertTrue(c.is_policed("x.ts", None))
        self.assertTrue(c.is_policed("x.ts", []))



class TestRelativizeRootedPathWithoutDrive(unittest.TestCase):
    """A rooted path with no drive letter is outside the project, on every
    platform and every Python.

    Python 3.13 changed `ntpath.isabs` so "/etc/cron.d/x.py" is no longer
    absolute on Windows. `relativize` used to ask `os.path.isabs` alone, so
    on that one combination the path fell through as if it were
    project-relative: the hooks policed it and DENIED a write plainly
    outside the project -- fail-closed, the one direction this project
    treats as inviolable. Caught by the CI matrix (windows/3.13 red,
    windows/3.9 green); no Linux run can reproduce it, because posixpath
    has always called this absolute.
    """

    def test_rooted_path_without_drive_is_outside_the_project(self):
        for raw in ("/etc/cron.d/x.py", "/tmp/z.py", "//server/share/x.py",
                    "\\\\etc\\\\cron.d\\\\x.py"):
            self.assertIsNone(c.relativize(raw, "/proj"), raw)

    def test_a_normal_relative_path_still_resolves(self):
        self.assertEqual(c.relativize("src/ok.py", "/proj"), "src/ok.py")


if __name__ == "__main__":
    unittest.main(verbosity=2)
