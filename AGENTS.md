# AGENTS.md

Instructions for AI coding agents working in this repository.

## Commits and pull requests

- **Never add `Co-Authored-By: Claude ...` (or any other AI co-author trailer) to
  commit messages.** Commits are authored by the repository owner only.
- Never add "Generated with Claude Code", "🤖 Generated with ...", or any similar
  attribution footer to commit messages or pull request descriptions.
- Write commit subjects in the imperative mood, lowercase after the type prefix:
  `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`, `data:`.
- Do not commit anything under `data/` (raw ONS downloads are cached there and are
  reproducible from the API).

## Scientific conduct

- Never hard-code, round up, or invent a number that appears in `README.md`.
  Every figure quoted in the README must be reproducible by
  `python scripts/run_analysis.py` and must come from `results/`.
- If a result changes after a code change, update the README in the same commit.
- Flag degenerate regimes explicitly rather than silently dropping them. 2023 is
  the canonical case (see README): over 90% of half-hours price at zero, so
  connectedness estimates on windows covering it are numerical noise.

## Code

- Python 3.12+, type hints on public functions, `ruff` clean.
- The Diebold-Yilmaz machinery lives in the external `connectedness` package. Do
  not re-implement it here; this repository is the Brazilian application plus the
  dynamic-directional extension in `src/pororoca/dynamics.py`.
