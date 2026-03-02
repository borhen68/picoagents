# Security Policy

## Supported Versions

Security fixes are primarily applied to the latest code on `main`.

| Version | Supported |
| --- | --- |
| `main` (latest) | Yes |
| Older commits/releases | Best effort |

## Reporting a Vulnerability

Please do not open a public issue for security reports.

Use one of these private paths:

1. Open a private GitHub Security Advisory for this repository.
2. If advisories are not available, contact the maintainer privately via GitHub and include `[SECURITY]` in the subject.

Please include:

- A clear description of the issue and impact
- Steps to reproduce
- Proof of concept (if safe to share)
- Suggested fix or mitigation (optional)
- Your preferred contact for follow-up

## Response Targets

- Acknowledgement: within 72 hours
- Initial triage: within 7 days
- Fix timeline: depends on severity and complexity

## Scope Notes

This project includes tool execution capabilities (shell/file/search/cron) and multi-channel gateways. Reports involving sandbox bypass, command execution abuse, path traversal, credential leakage, or unsafe default behavior are high priority.
