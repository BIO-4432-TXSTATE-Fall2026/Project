# Repository rules

- Do not retain compatibility shims, legacy modules, re-export aliases, or deprecated
import paths after a rename or relocation. Update every in-repository caller and test
to the canonical location, then remove the old code.
- Use Pixi as the project's authoritative environment and task runner.

## Git and GitHub rules

- Never force push. Do not use `git push --force`, `--force-with-lease`, or any
other variant that overwrites remote history.

### Commits

- Keep each commit short and focused: use one concise summary line. Do not add a
multi-paragraph body, a file-by-file list, or a restatement of the diff.
- Prefix every summary with the most specific applicable type, capitalized and
followed by a colon. For example: `Fix: reject malformed manifest sidecars`.
  
  | Prefix     | Use for                                   |
  | ---------- | ----------------------------------------- |
  | `Feat`     | A user-visible capability                 |
  | `Fix`      | Corrected behavior                        |
  | `Docs`     | Documentation-only changes                |
  | `Test`     | Tests or test infrastructure              |
  | `Refactor` | Behavior-preserving code restructuring    |
  | `Perf`     | Performance work                          |
  | `Style`    | Formatting-only changes                   |
  | `Build`    | Dependencies, packaging, or build tooling |
  | `CI`       | Continuous-integration configuration      |
  | `Chore`    | Maintenance that fits none of the above   |
  | `Security` | Security hardening or a vulnerability fix |
  | `Revert`   | Undoing an earlier commit                 |
  

### Pull requests

- Keep PRs narrow. Do not combine unrelated cleanup, refactors, formatting, or
follow-up work with the requested change.
- Make the PR title a short, specific summary.
- Keep the PR description brief: state what changed, why it matters when that is
not obvious, and the validation performed. Use at most five short bullets.
- Do not reproduce commit messages, enumerate files, paste logs, or write a
changelog-style narrative in the PR description.
- Do not open a PR unless the user asks to open one.

### Issues

- Do not create, comment on, close, or otherwise modify GitHub issues unless the
user explicitly asks for that action.
- When asked to create an issue, use a short, specific title and a concise
description of the problem, expected outcome, and any essential context.

