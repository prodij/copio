# Copio

Copio is a SaaS boilerplate: a [Copier](https://copier.readthedocs.io) template that generates a standalone product with a backend, frontend, background jobs, auth, billing and brand assets.

    uvx copier copy --trust gh:prodij/copio my-product

`--trust` is required for two small tasks, which run on the first copy only, never on an update. With a `logo_path`, one copies that SVG into `brand/logo.svg`. The other writes the brand files from `brand/`; it needs `uv` and, the first time, network. If it can't run, the copy still finishes and tells you to run `make regen`. Update later with `uvx copier update --trust`.

- Design: [docs/superpowers/specs/2026-10-30-boilerplate-milestone-1-design.md](docs/superpowers/specs/2026-10-30-boilerplate-milestone-1-design.md)
- The earlier Phase 1.0 diagnostic agent is preserved at the git tag `v1-diagnostic-archive`.
