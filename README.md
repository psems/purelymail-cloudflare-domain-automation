# pcda — PurelyMail + Cloudflare Domain Automation

[![CI](https://github.com/psems/purelymail-cloudflare-domain-automation/actions/workflows/ci.yml/badge.svg)](https://github.com/psems/purelymail-cloudflare-domain-automation/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![uv](https://img.shields.io/badge/run%20with-uv-purple.svg)](https://github.com/astral-sh/uv)

A zero-dependency\* CLI tool that automates onboarding domains to [PurelyMail](https://purelymail.com) and keeping their required DNS records reconciled in [Cloudflare](https://cloudflare.com).

> \*Uses only `requests` — no framework, no config files, no database.

---

## Why pcda?

Manually adding a domain to PurelyMail requires creating seven specific DNS records in Cloudflare, then triggering a DNS ownership check via the PurelyMail API. Do this once and it's fine. Do it for dozens of domains (or automate it in CI) and it gets tedious and error-prone.

`pcda` handles all of it: pre-flight conflict detection, idempotent record creation, Cloudflare Email Routing lock handling, retry logic for DNS propagation delays, and read-only health/inventory audits — all from a single Python file with no install required.

---

## Features

| Feature | Details |
|---|---|
| **Add/reconcile mode** | Creates all 7 PurelyMail DNS records in Cloudflare, detects conflicts, and registers the domain via the PurelyMail API |
| **DNS health check** | Read-only MX/SPF/DKIM/DMARC status for one domain or all PurelyMail domains |
| **Domain inventory compare** | Side-by-side view of Cloudflare zones vs PurelyMail domains with health status |
| **Interactive & non-interactive** | Guided TUI prompts for human use; fully scriptable `--non-interactive` mode for CI/CD |
| **Conflict detection** | Detects and interactively resolves conflicting DNS records before making any changes |
| **Idempotent** | Safe to re-run; already-correct records are skipped |
| **Email Routing aware** | Handles Cloudflare Email Routing MX lock errors gracefully with actionable warnings |

---

## DNS Records Created

| Type | Name | Value | Notes |
|---|---|---|---|
| MX | `@` | `mailserver.purelymail.com` | Priority 50 |
| TXT | `@` | `v=spf1 include:_spf.purelymail.com ~all` | SPF |
| CNAME | `purelymail1._domainkey` | `key1.dkimroot.purelymail.com` | DKIM key 1 |
| CNAME | `purelymail2._domainkey` | `key2.dkimroot.purelymail.com` | DKIM key 2 |
| CNAME | `purelymail3._domainkey` | `key3.dkimroot.purelymail.com` | DKIM key 3 |
| CNAME | `_dmarc` | `dmarcroot.purelymail.com` | DMARC |
| TXT | `@` | `<account ownership code>` | Domain ownership proof |

---

## Requirements

- Python 3.9+
- [`uv`](https://github.com/astral-sh/uv) (recommended) or `pip install requests`
- [PurelyMail API token](https://purelymail.com/manage/account) (Account → API)
- [Cloudflare API token](https://dash.cloudflare.com/profile/api-tokens) with **Zone → DNS → Edit** permission

---

## Quickstart

```bash
# Clone
git clone https://github.com/psems/purelymail-cloudflare-domain-automation.git
cd purelymail-cloudflare-domain-automation

# Run interactively — prompts for tokens and domain
uv run ./pcda.py
```

---

## Usage

### Add or reconcile a domain

**Interactive** (prompts for all values, tokens are hidden):

```bash
uv run ./pcda.py example.com
```

**Non-interactive** (for scripts and CI):

```bash
export PURELYMAIL_TOKEN="..."
export CLOUDFLARE_API_TOKEN="..."
export CLOUDFLARE_ACCOUNT_ID="..."   # optional — scopes zone lookup to one account

uv run ./pcda.py --domain example.com --non-interactive
```

**Example output:**

```
=== Adding example.com to PurelyMail via Cloudflare DNS ===

Fetching PurelyMail ownership code...
  Ownership code retrieved.

Looking up Cloudflare zone for example.com...
  Zone found.

Creating DNS records in Cloudflare...
  Found 3 existing record(s).

  [skip]    MX @ → mailserver.purelymail.com (already correct)
  [ok]      TXT @ → v=spf1 include:_spf.purelymail.com ~all
  [ok]      CNAME purelymail1._domainkey → key1.dkimroot.purelymail.com
  [ok]      CNAME purelymail2._domainkey → key2.dkimroot.purelymail.com
  [ok]      CNAME purelymail3._domainkey → key3.dkimroot.purelymail.com
  [ok]      CNAME _dmarc → dmarcroot.purelymail.com
  [ok]      TXT @ → <ownership code>

Adding domain to PurelyMail (this runs a DNS check)...
  Domain successfully added.

Done! Allow a few minutes for DNS to propagate if the check fails.
```

---

### Check DNS health

Check one domain:

```bash
uv run ./pcda.py --check-dns-health --domain example.com
```

Check all PurelyMail domains at once:

```bash
uv run ./pcda.py --check-dns-health --non-interactive
```

**Example output:**

```
=== PurelyMail DNS Health ===

example.com
  MX:    PASS
  SPF:   PASS
  DKIM:  PASS
  DMARC: PASS
  Overall: HEALTHY
```

**Exit codes:**

| Code | Meaning |
|---|---|
| `0` | All checked domains are healthy |
| `1` | Input/config error |
| `2` | At least one domain needs attention |

---

### Compare Cloudflare zones vs PurelyMail domains

```bash
uv run ./pcda.py --compare-domain --non-interactive
```

**Example output:**

```
=== Domain Compare ===
Cloudflare zones:               12
PurelyMail domains:              9
In both (set up on PurelyMail):  8
Cloudflare only (not on PM):     4
PurelyMail only (not on CF):     1

=== In Both (Healthy) ===
example.com
myotherdomain.com

=== In Both (Needs Attention) ===
broken.com | MX=True SPF=False DKIM=True DMARC=True

=== Cloudflare Only (Not On PurelyMail) ===
staging.example.com
...
```

---

## Configuration Reference

All credentials can be supplied via environment variables, CLI flags, or interactive prompts. Environment variables are preferred for security.

| Variable | CLI Flag | Required | Description |
|---|---|---|---|
| `PURELYMAIL_TOKEN` | `--purelymail-token` | Yes (add/health/compare) | PurelyMail API token |
| `CLOUDFLARE_API_TOKEN` | `--cloudflare-api-token` | Yes (add/compare) | Cloudflare API token |
| `CLOUDFLARE_ACCOUNT_ID` | `--cloudflare-account-id` | No | Scopes Cloudflare zone lookup to a specific account |

> **Security:** Passing tokens via CLI flags can leak into shell history. Prefer environment variables. `pcda` will print a warning if CLI token flags are used.

---

## All Flags

```
usage: pcda.py [-h] [--domain DOMAIN] [--purelymail-token TOKEN]
               [--cloudflare-api-token TOKEN] [--cloudflare-account-id ID]
               [--non-interactive] [--check-dns-health | --compare-domain]
               [domain]

positional arguments:
  domain                     Domain to configure

options:
  --domain DOMAIN            Domain to configure (alternative to positional)
  --purelymail-token TOKEN   PurelyMail API token
  --cloudflare-api-token TOKEN  Cloudflare API token
  --cloudflare-account-id ID  Cloudflare account ID
  --non-interactive          Do not prompt; require values from flags/env vars
  --check-dns-health         Check DNS health (read-only)
  --compare-domain           Compare Cloudflare zones vs PurelyMail domains (read-only)
```

---

## Cloudflare Email Routing

If your zone has **Cloudflare Email Routing** enabled, Cloudflare manages the MX records and will block changes. `pcda` detects this and prints an actionable warning rather than failing:

```
Warning: Cloudflare Email Routing is enabled for this zone and blocked MX record changes.
Disable Cloudflare Email Routing, then rerun this script to finish PurelyMail setup.
```

Disable Email Routing in the Cloudflare dashboard (**Email → Email Routing → Disable**), then re-run `pcda`.

---

## Running Without uv

```bash
pip install requests
python pcda.py --help
```

---

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

---

## Author

**Paul G. Sems**

---

## License

MIT — see [LICENSE](LICENSE).
