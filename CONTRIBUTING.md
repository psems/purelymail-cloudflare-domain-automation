# Contributing to pcda

Thanks for your interest in contributing. This is a small, focused tool — contributions that keep it that way are most welcome.

---

## Before You Start

- Open an issue first for non-trivial changes so we can align before you write code.
- Bug fixes and documentation improvements can go straight to a PR.
- Check existing issues and PRs before opening a duplicate.

---

## Design Philosophy

`pcda` is intentionally a **single Python file** with a single dependency (`requests`). Please keep contributions within that constraint:

- No new runtime dependencies without a very strong justification.
- No config file formats, plugins, or abstract base classes.
- Keep it runnable with `uv run ./pcda.py` and `python pcda.py` out of the box.
- Prefer clear, obvious code over clever abstractions.

---

## Development Setup

```bash
git clone https://github.com/psems/purelymail-cloudflare-domain-automation.git
cd purelymail-cloudflare-domain-automation

# Install the one runtime dependency
pip install requests

# Install dev tooling (optional but recommended)
pip install ruff
```

---

## Making Changes

1. Fork the repo and create a feature branch from `main`.
2. Make your changes to `pcda.py`.
3. Run the validation checklist (see below).
4. Open a pull request with a clear description of what changed and why.

---

## Validation Checklist

Run these before submitting a PR:

```bash
# 1. Compile check
python3 -m py_compile pcda.py && echo "OK"

# 2. --help runs without error
uv run ./pcda.py --help

# 3. Lint (ruff)
ruff check pcda.py
```

CI runs all three against Python 3.9 through 3.13.

---

## Security Rules

- **Never** hardcode API tokens, passwords, or secrets — not in code, not in tests, not in comments or commit messages.
- Do not print token values, authorization headers, or raw secrets in any output path.
- All external API calls must use HTTPS only.
- If you find a security vulnerability, please **do not open a public issue**. Contact the maintainer directly.

---

## Code Style

- Python 3.9-compatible syntax (no 3.10+ union syntax without `from __future__ import annotations`).
- `ruff` is the linter — match whatever style it enforces on the existing file.
- Add brief, meaningful docstrings for new public functions.
- Handle API failures with clear, actionable error messages.

---

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/) format:

```
feat: add --bulk-add flag for reading domains from a file
fix: handle Cloudflare rate limit 429 responses gracefully
docs: clarify CLOUDFLARE_ACCOUNT_ID is optional
chore: bump ruff lint rules
```

---

## What Makes a Good PR

- A clear title that explains what changed.
- A description that explains *why* the change is needed.
- No unrelated changes bundled in.
- README.md updated if any flags, behavior, or outputs changed.
- CHANGELOG.md updated with a new entry under `[Unreleased]`.
