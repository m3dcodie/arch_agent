# Releasing and Versioning

This project follows Semantic Versioning. Use Git tags for releases (e.g. `v1.0.0`).

Recommended manual release steps

1. Update the version in `pyproject.toml` (the `project.version` field).
2. Update the CLI version constant in `adag/cli.py` (click.version_option).
3. Update the version badge in `README.md` or replace it with a dynamic GitHub tag badge:
   `https://img.shields.io/github/v/tag/<owner>/<repo>?label=version`.
4. Add a new entry for the release in `CHANGELOG.md` (date + summary of notable changes).
5. Commit the changes and create an annotated tag:

```bash
git add pyproject.toml adag/cli.py README.md CHANGELOG.md docs/RELEASING.md
git commit -m "chore(release): vX.Y.Z"
git tag -a vX.Y.Z -m "vX.Y.Z"
```

6. Push the branch and tag to the remote (force-push only if you intentionally rewrite remote history):

```bash
git push origin main
git push origin vX.Y.Z
```

Notes and automation

- If you keep a linear history (recommended for most projects), avoid rewriting remote history
  after the initial cleanup. Use tags to mark releases instead.
- You can automate releases with a GitHub Action that triggers on `push` to `refs/tags/v*` and
  creates a GitHub Release, publishes to PyPI, or builds release artifacts.
- To keep the README badge up-to-date automatically, prefer the Shields.io GitHub tag badge
  (`https://img.shields.io/github/v/tag/<owner>/<repo>`), which reads the latest Git tag.

If you want, I can add a GitHub Actions workflow to automate creating releases from tags and
publishing to PyPI or GitHub Releases.
