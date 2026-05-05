# Copilot Instructions for `pcda`

## Project Purpose
This repository contains a single Python CLI tool, `pcda.py`, that automates:
- PurelyMail domain onboarding
- Cloudflare DNS reconciliation for PurelyMail-required records
- DNS health checks via PurelyMail API summaries
- Domain inventory comparison between Cloudflare and PurelyMail

## Primary Files
- `pcda.py` - main and only application code
- `README.md` - user-facing usage and security guidance
- `LICENSE` - MIT license

## Development Priorities
1. Keep behavior safe and predictable in production DNS workflows.
2. Preserve non-interactive automation compatibility.
3. Avoid breaking existing command-line flags and output format unless necessary.
4. Prefer small, surgical edits over broad refactors.

## Security Rules
- Never hardcode API tokens in code, docs, examples, tests, or commit messages.
- Prefer environment variables over CLI token flags in examples.
- Do not print token values, authorization headers, or raw secrets in logs/errors.
- Keep all external API calls on HTTPS endpoints only.

## Coding Conventions
- Use Python 3.9-compatible syntax.
- Keep dependencies minimal (`requests` only unless explicitly approved).
- Add brief, meaningful docstrings for new public functions.
- Handle API failures with clear, actionable errors.
- Treat Cloudflare Email Routing lock errors as non-fatal when possible.

## Behavior Expectations
- `--check-dns-health` should be read-only.
- `--compare-domain` should be read-only.
- Add/reconcile flow can modify DNS records and should keep conflict handling explicit.
- Non-interactive mode should fail fast on missing required inputs.

## Validation Checklist
When making changes:
1. Run `python3 -m py_compile pcda.py`.
2. Run `uv run ./pcda.py --help`.
3. Verify updated commands/examples in `README.md`.
4. Ensure no secrets were added to tracked files.

## Documentation Expectations
- Update `README.md` when flags, behavior, or outputs change.
- Keep examples aligned with current command name (`pcda.py`).
