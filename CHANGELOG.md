# Changelog

All notable changes to this project will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).  
This project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [1.0.0] — 2026-05-05

Initial public release.

### Added

- **Add/reconcile mode** — creates all 7 PurelyMail-required DNS records in Cloudflare and registers the domain via the PurelyMail API
- **DNS health check mode** (`--check-dns-health`) — read-only MX/SPF/DKIM/DMARC status for one domain or all PurelyMail domains; exit codes `0`/`1`/`2`
- **Domain compare mode** (`--compare-domain`) — read-only side-by-side view of Cloudflare zones vs PurelyMail domains with health status
- **Interactive TUI** — guided prompts for all required values; tokens hidden with `getpass`
- **Non-interactive mode** (`--non-interactive`) — all values from CLI flags or environment variables; fails fast on missing inputs
- **Pre-flight conflict detection** — checks all DNS records before making any changes; surfaces conflicts for interactive resolution or fails fast in non-interactive mode
- **Idempotent execution** — already-correct records are skipped without error
- **Cloudflare Email Routing handling** — detects MX lock error codes 1046/890190 and prints actionable warnings instead of crashing
- **Domain format validation** — rejects malformed domain names at the CLI boundary
- **CLI token warning** — warns when API tokens are passed via CLI flags (shell history risk)
- **Retry logic** — retries PurelyMail domain registration up to 5 times with 15-second delays to allow DNS propagation
- **Inline uv script metadata** — zero-install execution with `uv run ./pcda.py`
- Single-file, single-dependency (`requests`) design

[Unreleased]: https://github.com/psems/purelymail-cloudflare-domain-automation/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/psems/purelymail-cloudflare-domain-automation/releases/tag/v1.0.0
