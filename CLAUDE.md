# copio (template)

This repo is a Copier template. `template/` becomes a product; `tests/` generates one and tests it.

- Run `uv run pytest -q` before every commit; CI also runs the generated product's checks and e2e.
- The template has a `_tasks` entry, so every `copier copy`/`update` needs `--trust`.
- Never commit secret values. `.env.example` lists names only.
- Never copy code from NG or Skylit repositories.
- Spec: docs/superpowers/specs/2026-10-30-boilerplate-milestone-1-design.md
