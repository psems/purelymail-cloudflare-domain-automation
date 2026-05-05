# Security Policy

## Supported Versions

This project currently supports security updates for the latest release on `main`.

| Version | Supported |
|---|---|
| 1.x | Yes |
| < 1.0.0 | No |

## Reporting a Vulnerability

Please do **not** open a public GitHub issue for security vulnerabilities.

Instead, report vulnerabilities privately using one of these methods:

1. GitHub private vulnerability reporting (preferred):
   - Go to the repository Security tab
   - Open "Report a vulnerability"
2. Email the maintainer directly at: `Paul@SemsFamily.com`

When reporting, include:

- A clear description of the issue
- Steps to reproduce
- Potential impact
- Any proof-of-concept details (if available)

## Response Expectations

- Initial acknowledgment target: within 3 business days
- Status updates target: every 7 days while triaging/fixing
- Coordinated disclosure preferred after a fix is available

## Scope Notes

This project is a CLI tool for PurelyMail and Cloudflare DNS workflows. Reports are especially helpful for issues involving:

- Credential or token exposure
- Unsafe output/logging of sensitive data
- API misuse that could cause account/domain takeover risks
- Dependency vulnerabilities with known exploitability

Thank you for helping keep this project and its users secure.
