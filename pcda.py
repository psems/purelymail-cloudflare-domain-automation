#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.9"
# dependencies = ["requests"]
# ///
"""
pcda.py - PurelyMail + Cloudflare Domain Automation CLI

Automates PurelyMail domain onboarding and DNS reconciliation in Cloudflare.

Primary commands:
- add/reconcile domain DNS records and register domain in PurelyMail
- check DNS health from PurelyMail status summaries
- compare Cloudflare zones against PurelyMail domains

Security:
- Prefer environment variables for tokens over CLI flags.
- Avoid committing credentials and avoid storing tokens in shell history.

Dependencies:
    Managed by the uv inline script metadata above.

Usage:
    python pcda.py [domain]
    python pcda.py --check-dns-health --domain example.com
    python pcda.py --compare-domain --non-interactive
    python pcda.py --domain example.com --non-interactive
    python pcda.py \
        --domain example.com \
        --purelymail-token "$PURELYMAIL_TOKEN" \
        --cloudflare-api-token "$CLOUDFLARE_API_TOKEN" \
        --cloudflare-account-id "$CLOUDFLARE_ACCOUNT_ID" \
        --non-interactive

    Interactive mode prompts for missing values. Non-interactive mode uses CLI
    flags and/or environment variables only and fails if a required value is
    missing. For security, prefer environment variables over token CLI flags.

Environment variables (optional pre-fill):
    PURELYMAIL_TOKEN        - Your PurelyMail API token (Account > API)
    CLOUDFLARE_API_TOKEN    - A Cloudflare API token with Zone:DNS:Edit permission
    CLOUDFLARE_ACCOUNT_ID   - Cloudflare account ID (scopes zone lookup; optional)
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import sys
import time
import requests

PURELYMAIL_BASE = "https://purelymail.com/api/v0"
CLOUDFLARE_BASE = "https://api.cloudflare.com/client/v4"

_DOMAIN_RE = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$"
)


def _validate_domain(domain: str) -> None:
    """Exit with a clear error if domain is not a valid FQDN."""
    if not domain or not _DOMAIN_RE.match(domain):
        print(f"Error: '{domain}' is not a valid domain name.", file=sys.stderr)
        sys.exit(1)


# ── TUI config collection ─────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add a domain to PurelyMail and create required Cloudflare DNS records."
    )
    parser.add_argument("domain", nargs="?", help="Domain to configure")
    parser.add_argument("--domain", dest="domain_flag", help="Domain to configure")
    parser.add_argument(
        "--purelymail-token",
        dest="pm_token",
        help="PurelyMail API token (overrides PURELYMAIL_TOKEN)",
    )
    parser.add_argument(
        "--cloudflare-api-token",
        dest="cf_token",
        help="Cloudflare API token (overrides CLOUDFLARE_API_TOKEN)",
    )
    parser.add_argument(
        "--cloudflare-account-id",
        dest="cf_account_id",
        help="Cloudflare account ID (overrides CLOUDFLARE_ACCOUNT_ID)",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Do not prompt; require all required values via flags or environment variables.",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--check-dns-health",
        action="store_true",
        help="Check PurelyMail DNS health status (MX/SPF/DKIM/DMARC) without changing DNS.",
    )
    mode_group.add_argument(
        "--compare-domain",
        action="store_true",
        help="Compare Cloudflare zones vs PurelyMail domains and show setup status.",
    )
    return parser.parse_args()


def _get_config_value(cli_value: str | None, env_var: str) -> str:
    if cli_value:
        return cli_value.strip()
    return os.environ.get(env_var, "").strip()


def _warn_cli_secret_use(args: argparse.Namespace) -> None:
    if args.pm_token or args.cf_token:
        print(
            "Warning: passing API tokens via CLI flags can leak into shell history.",
            file=sys.stderr,
        )
        print("Prefer PURELYMAIL_TOKEN / CLOUDFLARE_API_TOKEN environment variables.", file=sys.stderr)

def _prompt_secret(prompt_label: str, env_var: str) -> str:
    """Prompt for a secret value, using the env var as a default if set."""
    existing = os.environ.get(env_var, "")
    if existing:
        hint = f"{prompt_label} [already set — press Enter to keep]: "
        value = getpass.getpass(hint)
        return value if value.strip() else existing
    return getpass.getpass(f"{prompt_label}: ")


def _prompt_text(prompt_label: str, env_var: str, required: bool = True) -> str:
    """Prompt for a plain-text value, using the env var as a default if set."""
    existing = os.environ.get(env_var, "")
    if existing:
        hint = f"{prompt_label} [{existing}]: "
        value = input(hint).strip()
        return value if value else existing
    value = input(f"{prompt_label}: ").strip()
    if required and not value:
        print(f"Error: {prompt_label} is required.")
        sys.exit(1)
    return value


def collect_config(args: argparse.Namespace) -> dict:
    """Collect configuration from CLI flags, env vars, and optionally prompts."""
    domain = (args.domain_flag or args.domain or "").lower().strip()
    pm_token = _get_config_value(args.pm_token, "PURELYMAIL_TOKEN")
    cf_token = _get_config_value(args.cf_token, "CLOUDFLARE_API_TOKEN")
    cf_account_id = _get_config_value(args.cf_account_id, "CLOUDFLARE_ACCOUNT_ID")

    interactive = not args.non_interactive and sys.stdin.isatty()

    if interactive and not (domain and pm_token and cf_token):
        print("=== PurelyMail + Cloudflare domain setup ===")
        print("(Press Enter to accept a pre-filled value; tokens are not echoed.)\n")

        if not domain:
            domain = _prompt_text("Domain", "").lower().strip()
        if not pm_token:
            pm_token = _prompt_secret("PurelyMail API token", "PURELYMAIL_TOKEN")
        if not cf_token:
            cf_token = _prompt_secret("Cloudflare API token", "CLOUDFLARE_API_TOKEN")
        if not cf_account_id:
            cf_account_id = _prompt_text(
                "Cloudflare Account ID (optional — press Enter to skip)",
                "CLOUDFLARE_ACCOUNT_ID",
                required=False,
            )

        print()

    if not domain:
        print("Error: domain is required. Provide it as an argument, --domain, or interactively.")
        sys.exit(1)
    _validate_domain(domain)
    if not pm_token:
        print("Error: PurelyMail API token is required. Use --purelymail-token or PURELYMAIL_TOKEN.")
        sys.exit(1)
    if not cf_token:
        print("Error: Cloudflare API token is required. Use --cloudflare-api-token or CLOUDFLARE_API_TOKEN.")
        sys.exit(1)

    return {
        "domain": domain,
        "pm_token": pm_token,
        "cf_token": cf_token,
        "cf_account_id": cf_account_id,
    }


def collect_dns_health_config(args: argparse.Namespace) -> dict:
    """Collect config for DNS health checks (PurelyMail only)."""
    domain = (args.domain_flag or args.domain or "").lower().strip()
    pm_token = _get_config_value(args.pm_token, "PURELYMAIL_TOKEN")

    interactive = not args.non_interactive and sys.stdin.isatty()
    if interactive and not pm_token:
        print("=== PurelyMail DNS health check ===")
        print("(Token input is hidden.)\n")
        pm_token = _prompt_secret("PurelyMail API token", "PURELYMAIL_TOKEN")
        print()

    if not pm_token:
        print("Error: PurelyMail API token is required. Use --purelymail-token or PURELYMAIL_TOKEN.")
        sys.exit(1)
    if domain:
        _validate_domain(domain)

    return {
        "domain": domain,
        "pm_token": pm_token,
    }


def collect_compare_config(args: argparse.Namespace) -> dict:
    """Collect config for compare-domain mode (PurelyMail + Cloudflare)."""
    pm_token = _get_config_value(args.pm_token, "PURELYMAIL_TOKEN")
    cf_token = _get_config_value(args.cf_token, "CLOUDFLARE_API_TOKEN")
    cf_account_id = _get_config_value(args.cf_account_id, "CLOUDFLARE_ACCOUNT_ID")

    interactive = not args.non_interactive and sys.stdin.isatty()
    if interactive and not pm_token:
        print("=== Compare Domain Setup ===")
        print("(Token input is hidden.)\n")
        pm_token = _prompt_secret("PurelyMail API token", "PURELYMAIL_TOKEN")
    if interactive and not cf_token:
        cf_token = _prompt_secret("Cloudflare API token", "CLOUDFLARE_API_TOKEN")
    if interactive and not cf_account_id:
        cf_account_id = _prompt_text(
            "Cloudflare Account ID (optional — press Enter to skip)",
            "CLOUDFLARE_ACCOUNT_ID",
            required=False,
        )
        print()

    if not pm_token:
        print("Error: PurelyMail API token is required. Use --purelymail-token or PURELYMAIL_TOKEN.")
        sys.exit(1)
    if not cf_token:
        print("Error: Cloudflare API token is required. Use --cloudflare-api-token or CLOUDFLARE_API_TOKEN.")
        sys.exit(1)

    return {
        "pm_token": pm_token,
        "cf_token": cf_token,
        "cf_account_id": cf_account_id,
    }

# ─────────────────────────────────────────────────────────────────────────────


def pm_headers(token: str) -> dict:
    return {
        "Purelymail-Api-Token": token,
        "Content-Type": "application/json",
    }


def cf_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


# ── PurelyMail helpers ────────────────────────────────────────────────────────

def _pm_check(data: dict, context: str) -> None:
    """Raise a clear error if PurelyMail returned an API-level failure."""
    if data.get("type") == "error":
        raise ValueError(f"PurelyMail error ({context}): {data.get('code')} — {data.get('message', data)}")


def get_ownership_code(pm_token: str) -> str:
    """Fetch the account-level ownership TXT record value from PurelyMail."""
    resp = requests.post(
        f"{PURELYMAIL_BASE}/getOwnershipCode",
        headers=pm_headers(pm_token),
        json={},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    _pm_check(data, "getOwnershipCode")
    code = (data.get("result") or {}).get("code")
    if not code or not isinstance(code, str):
        raise ValueError(f"Unexpected getOwnershipCode response: {data}")
    return code


def add_domain_to_purelymail(domain: str, pm_token: str) -> dict:
    """Add the domain to PurelyMail (DNS records must already be set)."""
    resp = requests.post(
        f"{PURELYMAIL_BASE}/addDomain",
        headers=pm_headers(pm_token),
        json={"domainName": domain},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("type") == "error" and data.get("message") == "Domain already exists":
        return {"type": "success", "result": {"alreadyExists": True}}
    _pm_check(data, "addDomain")
    return data


def list_domains(pm_token: str) -> list:
    """Return all PurelyMail domains with dnsSummary status."""
    resp = requests.post(
        f"{PURELYMAIL_BASE}/listDomains",
        headers=pm_headers(pm_token),
        json={},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    _pm_check(data, "listDomains")
    domains = (data.get("result") or {}).get("domains")
    if not isinstance(domains, list):
        raise ValueError(f"Unexpected listDomains response: {data}")
    return domains


def check_dns_health(domain: str, pm_token: str) -> int:
    """Print DNS health status for one domain or all domains."""
    domains = list_domains(pm_token)

    if domain:
        domains = [d for d in domains if d.get("name", "").lower() == domain]
        if not domains:
            print("Error: requested domain is not in this PurelyMail account.")
            return 1

    if not domains:
        print("No domains found in this PurelyMail account.")
        return 1

    any_fail = False
    print("=== PurelyMail DNS Health ===\n")
    for item in domains:
        name = item.get("name", "(unknown)")
        summary = item.get("dnsSummary") or {}
        mx = bool(summary.get("passesMx"))
        spf = bool(summary.get("passesSpf"))
        dkim = bool(summary.get("passesDkim"))
        dmarc = bool(summary.get("passesDmarc"))
        overall = mx and spf and dkim and dmarc
        any_fail = any_fail or (not overall)

        print(f"{name}")
        print(f"  MX:    {'PASS' if mx else 'FAIL'}")
        print(f"  SPF:   {'PASS' if spf else 'FAIL'}")
        print(f"  DKIM:  {'PASS' if dkim else 'FAIL'}")
        print(f"  DMARC: {'PASS' if dmarc else 'FAIL'}")
        print(f"  Overall: {'HEALTHY' if overall else 'NEEDS ATTENTION'}\n")

    return 0 if not any_fail else 2


def list_cloudflare_zones(cf_token: str, account_id: str = "") -> list:
    """Return all Cloudflare zone names visible to the API token."""
    zones = []
    page = 1
    while True:
        params: dict = {"page": page, "per_page": 50}
        if account_id:
            params["account.id"] = account_id
        resp = requests.get(
            f"{CLOUDFLARE_BASE}/zones",
            headers=cf_headers(cf_token),
            params=params,
            timeout=15,
        )
        if not resp.ok:
            raise requests.HTTPError(
                f"{resp.status_code} {resp.reason}",
                response=resp,
            )
        data = resp.json()
        zones.extend([z.get("name", "").lower() for z in data.get("result", []) if z.get("name")])
        info = data.get("result_info") or {}
        if page >= int(info.get("total_pages", 1) or 1):
            break
        page += 1
    return zones


def compare_domain_setup(pm_token: str, cf_token: str, cf_account_id: str = "") -> int:
    """Compare Cloudflare zones with PurelyMail domains and print setup status."""
    pm_items = list_domains(pm_token)
    pm_map = {
        item.get("name", "").lower(): (item.get("dnsSummary") or {})
        for item in pm_items
        if item.get("name")
    }
    cf_set = set(list_cloudflare_zones(cf_token, cf_account_id))
    pm_set = set(pm_map.keys())

    in_both = sorted(cf_set & pm_set)
    cf_only = sorted(cf_set - pm_set)
    pm_only = sorted(pm_set - cf_set)

    healthy = []
    needs_attention = []
    for domain in in_both:
        s = pm_map.get(domain, {})
        mx = bool(s.get("passesMx"))
        spf = bool(s.get("passesSpf"))
        dkim = bool(s.get("passesDkim"))
        dmarc = bool(s.get("passesDmarc"))
        if mx and spf and dkim and dmarc:
            healthy.append(domain)
        else:
            needs_attention.append((domain, mx, spf, dkim, dmarc))

    print("=== Domain Compare ===")
    print(f"Cloudflare zones: {len(cf_set)}")
    print(f"PurelyMail domains: {len(pm_set)}")
    print(f"In both (set up on PurelyMail): {len(in_both)}")
    print(f"Cloudflare only (not on PurelyMail): {len(cf_only)}")
    print(f"PurelyMail only (not on Cloudflare): {len(pm_only)}\n")

    print("=== In Both (Healthy) ===")
    if healthy:
        for domain in healthy:
            print(domain)
    else:
        print("(none)")
    print()

    print("=== In Both (Needs Attention) ===")
    if needs_attention:
        for domain, mx, spf, dkim, dmarc in needs_attention:
            print(f"{domain} | MX={mx} SPF={spf} DKIM={dkim} DMARC={dmarc}")
    else:
        print("(none)")
    print()

    print("=== Cloudflare Only (Not On PurelyMail) ===")
    if cf_only:
        for domain in cf_only:
            print(domain)
    else:
        print("(none)")
    print()

    print("=== PurelyMail Only (Not On Cloudflare) ===")
    if pm_only:
        for domain in pm_only:
            print(domain)
    else:
        print("(none)")

    return 0


# ── Cloudflare helpers ────────────────────────────────────────────────────────

def get_zone_id(domain: str, cf_token: str, account_id: str = "") -> str:
    """Look up the Cloudflare zone ID for the given domain."""
    params: dict = {"name": domain, "status": "active"}
    if account_id:
        params["account.id"] = account_id
    resp = requests.get(
        f"{CLOUDFLARE_BASE}/zones",
        headers=cf_headers(cf_token),
        params=params,
        timeout=15,
    )
    if not resp.ok:
        raise requests.HTTPError(
            f"{resp.status_code} {resp.reason}",
            response=resp,
        )
    data = resp.json()
    if not data["success"] or not data["result"]:
        raise ValueError(
            f"Zone '{domain}' not found in Cloudflare. "
            "Make sure the domain is added to your Cloudflare account."
        )
    return data["result"][0]["id"]


def list_dns_records(zone_id: str, cf_token: str) -> list:
    """Fetch all existing DNS records for a zone."""
    records = []
    page = 1
    while True:
        resp = requests.get(
            f"{CLOUDFLARE_BASE}/zones/{zone_id}/dns_records",
            headers=cf_headers(cf_token),
            params={"per_page": 100, "page": page},
            timeout=15,
        )
        if not resp.ok:
            raise requests.HTTPError(
                f"{resp.status_code} {resp.reason}",
                response=resp,
            )
        data = resp.json()
        records.extend(data["result"])
        if page >= data["result_info"]["total_pages"]:
            break
        page += 1
    return records


def _normalize_name(name: str, domain: str) -> str:
    """Return the bare host label, stripping the zone domain suffix if present."""
    fqdn_suffix = "." + domain.rstrip(".")
    bare = name.rstrip(".")
    if bare == domain.rstrip("."):
        return "@"
    if bare.endswith(fqdn_suffix):
        bare = bare[: -len(fqdn_suffix)]
    return bare.lower()


def _same_name(existing: dict, wanted: dict, domain: str) -> bool:
    return _normalize_name(existing["name"], domain) == wanted["name"].lower()


def _record_matches(existing: dict, wanted: dict, domain: str) -> bool:
    """True if an existing Cloudflare record satisfies the wanted spec."""
    if existing["type"] != wanted["type"]:
        return False
    if not _same_name(existing, wanted, domain):
        return False
    ex_content = existing.get("content", "").rstrip(".")
    wa_content = wanted.get("content", "").rstrip(".")
    if existing["type"] in ("MX", "CNAME"):
        return ex_content.lower() == wa_content.lower()
    return ex_content == wa_content


def _conflict_for(existing_records: list, wanted: dict, domain: str) -> dict | None:
    """Return the first existing record that conflicts with the wanted record.

    CNAME records are exclusive per name, so any different record at that name
    conflicts. SPF TXT records are also treated as conflicts when a different
    SPF TXT already exists at the same host, since multiple SPF records are not
    a valid end state.
    """
    for ex in existing_records:
        if not _same_name(ex, wanted, domain):
            continue
        if _record_matches(ex, wanted, domain):
            continue

        if wanted["type"] == "CNAME":
            return ex

        if wanted["type"] == "TXT":
            wanted_content = wanted.get("content", "")
            existing_content = ex.get("content", "")
            if wanted_content.startswith("v=spf1") and existing_content.startswith("v=spf1"):
                return ex
    return None


def _prompt_conflict(existing: dict, wanted: dict, interactive: bool) -> str:
    """Ask the user what to do when a conflicting record exists. Returns 'skip'|'replace'|'add'."""
    print()
    print(f"  [conflict] {wanted['type']} {wanted['name']}")
    print(f"    existing : {existing.get('content')}")
    print(f"    wanted   : {wanted.get('content')}")
    while True:
        choice = input("    Action — [s]kip / [r]eplace / [a]dd alongside: ").strip().lower()
        if choice in ("s", "skip"):
            return "skip"
        if choice in ("r", "replace"):
            return "replace"
        if choice in ("a", "add"):
            return "add"
        print("    Please enter s, r, or a.")


def _create_record(zone_id: str, record: dict, cf_token: str) -> None:
    resp = requests.post(
        f"{CLOUDFLARE_BASE}/zones/{zone_id}/dns_records",
        headers=cf_headers(cf_token),
        json=record,
        timeout=15,
    )
    if not resp.ok:
        body = resp.json()
        errors = body.get("errors", [])
        if any(
            error.get("code") in (1046, 890190)
            and "Email Routing" in error.get("message", "")
            for error in errors
        ):
            raise ValueError("cloudflare-email-routing-mx-lock")
        raise requests.HTTPError(
            f"{resp.status_code} {resp.reason} — {body}",
            response=resp,
        )


def _delete_record(zone_id: str, record_id: str, cf_token: str) -> None:
    resp = requests.delete(
        f"{CLOUDFLARE_BASE}/zones/{zone_id}/dns_records/{record_id}",
        headers=cf_headers(cf_token),
        timeout=15,
    )
    if not resp.ok:
        body = resp.json()
        errors = body.get("errors", [])
        if any(
            error.get("code") in (1046, 890190)
            and "Email Routing" in error.get("message", "")
            for error in errors
        ):
            raise ValueError("cloudflare-email-routing-mx-lock")
        raise requests.HTTPError(
            f"{resp.status_code} {resp.reason} — {body}",
            response=resp,
        )


def _extra_mx_records(existing_records: list, wanted: dict, domain: str) -> list:
    """Return apex MX records that do not match the wanted MX target."""
    extras = []
    for ex in existing_records:
        if ex["type"] != "MX":
            continue
        if not _same_name(ex, wanted, domain):
            continue
        if not _record_matches(ex, wanted, domain):
            extras.append(ex)
    return extras


def add_cloudflare_records(
    zone_id: str, domain: str, ownership_code: str, cf_token: str, interactive: bool
):
    """
    Check existing DNS records first, then create/replace/skip as directed.

    Records:
      MX    @                      → mailserver.purelymail.com (priority 50)
      TXT   @                      → v=spf1 include:_spf.purelymail.com ~all
      CNAME purelymail1._domainkey → key1.dkimroot.purelymail.com
      CNAME purelymail2._domainkey → key2.dkimroot.purelymail.com
      CNAME purelymail3._domainkey → key3.dkimroot.purelymail.com
      CNAME _dmarc                 → dmarcroot.purelymail.com
      TXT   @                   → <ownership code>
    """
    wanted = [
        {
            "type": "MX",
            "name": "@",
            "content": "mailserver.purelymail.com",
            "priority": 50,
            "ttl": 3600,
        },
        {
            "type": "TXT",
            "name": "@",
            "content": "v=spf1 include:_spf.purelymail.com ~all",
            "ttl": 3600,
        },
        {
            "type": "CNAME",
            "name": "purelymail1._domainkey",
            "content": "key1.dkimroot.purelymail.com",
            "ttl": 3600,
            "proxied": False,
        },
        {
            "type": "CNAME",
            "name": "purelymail2._domainkey",
            "content": "key2.dkimroot.purelymail.com",
            "ttl": 3600,
            "proxied": False,
        },
        {
            "type": "CNAME",
            "name": "purelymail3._domainkey",
            "content": "key3.dkimroot.purelymail.com",
            "ttl": 3600,
            "proxied": False,
        },
        {
            "type": "CNAME",
            "name": "_dmarc",
            "content": "dmarcroot.purelymail.com",
            "ttl": 3600,
            "proxied": False,
        },
        {
            "type": "TXT",
            "name": "@",
            "content": ownership_code,
            "ttl": 3600,
        },
    ]

    mx_blocked_by_email_routing = False

    print("  Fetching existing DNS records...")
    existing = list_dns_records(zone_id, cf_token)
    print(f"  Found {len(existing)} existing record(s).\n")

    planned_actions = []
    conflicts = []

    for record in wanted:
        content_display = record["content"]
        if content_display == ownership_code:
            content_display = "<ownership code>"
        label = f"{record['type']} {record['name']} → {content_display}"

        if record["type"] == "MX":
            extras = _extra_mx_records(existing, record, domain)
            for ex in extras:
                planned_actions.append(
                    {
                        "action": "delete-extra-mx",
                        "record": record,
                        "label": label,
                        "conflict": ex,
                    }
                )

        if any(_record_matches(ex, record, domain) for ex in existing):
            planned_actions.append({"action": "already-correct", "record": record, "label": label})
            continue

        conflict = _conflict_for(existing, record, domain)
        if conflict:
            conflicts.append({"record": record, "label": label, "conflict": conflict})
            continue

        planned_actions.append({"action": "create", "record": record, "label": label})

    if conflicts and not interactive:
        lines = ["DNS conflicts require manual resolution:"]
        for item in conflicts:
            conflict = item["conflict"]
            record = item["record"]
            lines.append(
                f"- existing {conflict['type']} {conflict['name']} -> {conflict.get('content')} ; "
                f"wanted {record['type']} {record['name']} -> {record.get('content')}"
            )
        raise ValueError("\n".join(lines))

    for item in conflicts:
        record = item["record"]
        label = item["label"]
        conflict = item["conflict"]
        action = _prompt_conflict(conflict, record, interactive)
        if action == "skip":
            planned_actions.append({"action": "skip", "record": record, "label": label})
            continue
        if action == "replace":
            planned_actions.append(
                {
                    "action": "replace",
                    "record": record,
                    "label": label,
                    "conflict": conflict,
                }
            )
            continue
        planned_actions.append({"action": "create", "record": record, "label": label})

    for planned in planned_actions:
        action = planned["action"]
        record = planned["record"]
        label = planned["label"]

        if action == "already-correct":
            print(f"  [skip]    {label} (already correct)")
            continue
        if action == "skip":
            print(f"  [skipped] {label}")
            continue
        if action == "delete-extra-mx":
            conflict = planned["conflict"]
            try:
                _delete_record(zone_id, conflict["id"], cf_token)
                print(
                    f"  [deleted] extra MX {conflict['name']} → {conflict['content']}"
                )
            except ValueError as exc:
                if str(exc) == "cloudflare-email-routing-mx-lock":
                    mx_blocked_by_email_routing = True
                    print(
                        "  [warn]    extra MX removal blocked by Cloudflare Email Routing"
                    )
                    continue
                raise
            continue
        if action == "replace":
            conflict = planned["conflict"]
            try:
                _delete_record(zone_id, conflict["id"], cf_token)
                print(f"  [deleted] existing {conflict['type']} {conflict['name']} → {conflict['content']}")
            except ValueError as exc:
                if str(exc) == "cloudflare-email-routing-mx-lock":
                    mx_blocked_by_email_routing = True
                    print(
                        "  [warn]    existing record replacement blocked by Cloudflare Email Routing"
                    )
                    print(f"  [skipped] {label}")
                    continue
                raise

        try:
            _create_record(zone_id, record, cf_token)
            print(f"  [ok]      {label}")
        except ValueError as exc:
            if str(exc) == "cloudflare-email-routing-mx-lock" and record["type"] == "MX":
                mx_blocked_by_email_routing = True
                print(f"  [warn]    {label} (blocked by Cloudflare Email Routing)")
                continue
            raise

    return {"mx_blocked_by_email_routing": mx_blocked_by_email_routing}


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()
    _warn_cli_secret_use(args)

    if args.check_dns_health:
        health_cfg = collect_dns_health_config(args)
        code = check_dns_health(health_cfg["domain"], health_cfg["pm_token"])
        sys.exit(code)

    if args.compare_domain:
        compare_cfg = collect_compare_config(args)
        code = compare_domain_setup(
            compare_cfg["pm_token"],
            compare_cfg["cf_token"],
            compare_cfg["cf_account_id"],
        )
        sys.exit(code)

    cfg = collect_config(args)

    domain = cfg["domain"]
    pm_token = cfg["pm_token"]
    cf_token = cfg["cf_token"]
    cf_account_id = cfg["cf_account_id"]

    print("=== Adding domain to PurelyMail via Cloudflare DNS ===\n")

    # 1. Get the PurelyMail ownership code (account-level, not per-domain)
    print("Fetching PurelyMail ownership code...")
    ownership_code = get_ownership_code(pm_token)
    # Ownership code is account-level; don't emit it to stdout/logs
    print("  Ownership code retrieved.\n")

    # 2. Find the Cloudflare zone for this domain
    print("Looking up Cloudflare zone...")
    zone_id = get_zone_id(domain, cf_token, cf_account_id)
    print("  Zone found.\n")

    # 3. Create DNS records in Cloudflare
    print("Creating DNS records in Cloudflare...")
    dns_result = add_cloudflare_records(
        zone_id,
        domain,
        ownership_code,
        cf_token,
        interactive=not args.non_interactive and sys.stdin.isatty(),
    )
    print()

    if dns_result["mx_blocked_by_email_routing"]:
        print("Warning: Cloudflare Email Routing is enabled for this zone and blocked MX record changes.")
        print("Disable Cloudflare Email Routing, then rerun this script to finish PurelyMail setup.")
        return

    # 4. Register the domain with PurelyMail (retry to allow DNS propagation)
    print("Adding domain to PurelyMail (this runs a DNS check)...")
    max_attempts = 5
    retry_delay = 15
    for attempt in range(1, max_attempts + 1):
        try:
            result = add_domain_to_purelymail(domain, pm_token)
            already = (result.get("result") or {}).get("alreadyExists")
            print(f"  Domain {'already registered' if already else 'successfully added'}.\n")
            break
        except ValueError as exc:
            if "DNS ownership checks did not pass" in str(exc) and attempt < max_attempts:
                print(f"  DNS check not ready yet (attempt {attempt}/{max_attempts}), "
                      f"retrying in {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                raise

    print("Done! Allow a few minutes for DNS to propagate if the check fails.")


if __name__ == "__main__":
    main()
