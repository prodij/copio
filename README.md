# Copio

Copio is a SaaS boilerplate: a [Copier](https://copier.readthedocs.io) template that generates a standalone product with a backend, frontend, background jobs, auth, billing and brand assets.

    uvx copier copy --trust gh:prodij/copio my-product

`--trust` is required: on the first copy only, the template runs two small tasks. One copies your `logo_path` SVG into `brand/logo.svg`, and one writes the brand files from `brand/`. Update later with `uvx copier update --trust`.

- Design: [docs/superpowers/specs/2026-10-30-boilerplate-milestone-1-design.md](docs/superpowers/specs/2026-10-30-boilerplate-milestone-1-design.md)
- The earlier Phase 1.0 diagnostic agent is preserved at the git tag `v1-diagnostic-archive`.
