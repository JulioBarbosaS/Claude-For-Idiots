# Task 7 report — travar a consistência

**Status:** done, committed.

**Scope:** one file, `tests/test_repo_consistency.py`. No changes to `SKILL.md`, `hooks/`, or `references/` (all reverted after mutation proofs, see below).

**Tests:** all four suites green — `test_common.py` 53/53, `test_hooks.py` 128/128, `test_real_projects.py` 1/1, `test_repo_consistency.py` 10/10 (192/192 total; 8 pre-existing + 2 new).

## Base check

HEAD started at `9685e6c` — a stale merge-commit tip from `main`, **not** the branch tip (confirmed with `git merge-base --is-ancestor d53e435 HEAD` → not an ancestor). This worktree's own branch (`worktree-agent-aec6159ee3e548f4a`) had no unique commits beyond that stale tip and a clean working tree, so it was safe to `git reset --hard d53e435` (the real tip of `plan/brainstorming-0.5.0`) before touching anything. Re-verified afterward: `hooks/require_feature_alignment.py` and `## Rule 10` in `references/rules.md` both present.

## Step 1 — does the hook new enter the fail-open sweep alone?

Yes, by glob (`hooks/*.py` minus `_cfi_common.py` by exact name), confirmed two ways:

1. Ran `_discover_hook_scripts()`'s exact logic standalone — `require_feature_alignment.py` is in the list.
2. **Mutation proof:** temporarily replaced the hook's fail-open net —

   ```python
   # before
   if __name__ == "__main__":
       try:
           main()
       except Exception:
           sys.exit(0)
   # after (mutation)
   if __name__ == "__main__":
       main()  # MUTATION: dropped the fail-open net
   ```

   Ran `python3 -m unittest tests.test_repo_consistency.TestRepoConsistency.test_every_hook_survives_malformed_stdin -v`. Literal failure:

   ```
   AssertionError: Lists differ: ['require_feature_alignment.py exited 1 on[915 chars]int'] != []
   ...
   require_feature_alignment.py exited 1 on payload 'tool_input_is_string': ...
     File ".../hooks/require_feature_alignment.py", line 125, in main
       file_path = cfi.target_path(event.get("tool_input"))
     File ".../hooks/_cfi_common.py", line 563, in target_path
       value = (tool_input or {}).get(key)
   AttributeError: 'str' object has no attribute 'get'
   require_feature_alignment.py exited 1 on payload 'cwd_is_int': ...
     File ".../hooks/_cfi_common.py", line 108, in load_config
       return load_json_file(os.path.join(cwd, CONFIG_REL))
   TypeError: expected str, bytes or os.PathLike object, not int
   ----------------------------------------------------------------------
   Ran 1 test in 1.723s
   FAILED (failures=1)
   ```

   Reverted with `git checkout -- hooks/require_feature_alignment.py`; re-ran the same test → `OK`. No test change was needed for Step 1 — the existing sweep already covers the new hook.

## Step 2 — rule ↔ template lock (new test)

`test_rules_doc_matches_claude_template_numbered_list`: extracts `## Rule N` numbers from `references/rules.md` (regex `^## Rule (\d+)\b`) and numbered-list item numbers from `assets/CLAUDE.template.md`'s "## Rules (always apply)" section (regex `^(\d+)\.\s+\*\*`), asserts the two sets are equal. Same defect class as the existing catalog↔STACKS check: two hand-maintained copies of the same list (currently 10 rules on each side) that nothing keeps in sync.

**Mutation proof:** inserted a fake `## Rule 11 — MUTATION: ...` heading into `references/rules.md` (not added to the template). Ran the new test alone. Literal failure:

```
AssertionError: Items in the first set but not the second:
'11' : references/rules.md's '## Rule N' headings and assets/CLAUDE.template.md's numbered rule list have drifted apart -- add/renumber the rule on both sides together:
only in rules.md: ['11']
only in CLAUDE.template.md: []
----------------------------------------------------------------------
Ran 1 test in 0.001s
FAILED (failures=1)
```

Reverted with `git checkout -- references/rules.md`; `git status --porcelain` confirmed clean before moving on.

## Step 3 — hook ↔ settings lock, reverse direction (new test)

`test_settings_template_registers_every_shipped_hook`: reuses `_discover_hook_scripts()` (same glob + exact-name exclusion of `_cfi_common.py` the fail-open sweep already uses — no new exclusion criterion invented) to get the shipped hook set, and the same `re.findall(r"hooks/(\w+\.py)", ...)` extraction `test_settings_template_references_shipped_hooks` already uses for the registered set. Asserts `shipped - referenced == set()` — the direction the existing test (`referenced <= shipped`) does not check: a hook that exists on disk but was never wired into `assets/settings.template.json`, i.e. "wrote the hook, forgot to register it," the most likely mistake for a future Rule 11.

**Mutation proof:** created an untracked fixture `hooks/_mutation_unregistered_hook.py` (a `.py` file under `hooks/`, not `_cfi_common.py`, so not excluded by the reused criterion, and never referenced in `settings.template.json`). Ran the new test alone. Literal failure:

```
AssertionError: {'_mutation_unregistered_hook.py'} is not false : hook(s) shipped under hooks/ but never wired into assets/settings.template.json -- a user who follows the template will never run them: {'_mutation_unregistered_hook.py'}
----------------------------------------------------------------------
Ran 1 test in 0.001s
FAILED (failures=1)
```

Reverted by `rm hooks/_mutation_unregistered_hook.py` (untracked file — `git checkout --` does not apply to files never added to git; deleting it is the correct undo here, not a `cp`-based restore of tracked content). `git status --porcelain` confirmed clean afterward except the intended `tests/test_repo_consistency.py` diff.

## Verification — all four suites

```
$ python3 -m unittest tests.test_common tests.test_hooks tests.test_real_projects tests.test_repo_consistency
----------------------------------------------------------------------
Ran 192 tests in 25.370s
OK
```

Broken down: `test_common.py` 53/53, `test_hooks.py` 128/128, `test_real_projects.py` 1/1, `test_repo_consistency.py` 10/10 (8 pre-existing + `test_rules_doc_matches_claude_template_numbered_list` + `test_settings_template_registers_every_shipped_hook`).

## Concerns / notes for whoever adds Rule 11

- The rule↔template regex ties `rule_numbers` to `## Rule N` headings and `template_numbers` to lines matching `^(\d+)\.\s+\*\*` inside `CLAUDE.template.md`. If the template's rule list ever stops bolding the rule's opening phrase (`**Never hand-edit...**` style), the regex needs updating — same fragility class as every other regex-scraped check already in this file, called out inline in the test's own failure message.
- `_discover_hook_scripts()`'s exclusion is by **exact filename** (`_cfi_common.py`), not by a `_`-prefix convention — confirmed by testing with a fixture filename that itself started with `_` and was still picked up as "shipped." Reusing this exact criterion (rather than inventing a prefix-based one) keeps Step 1's sweep and Step 3's new check aligned, but it means a second shared/imported module would need to be added to that exclusion list by name if one is ever introduced.
