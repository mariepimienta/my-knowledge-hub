# Implementation Plan: Project Knowledge Hub Monorepo

Implemented on 2026-02-15. See README.md for usage documentation.

## Files Created

| # | File | Description |
|---|------|-------------|
| 1 | `.gitignore` | Python, env, OS ignores |
| 2 | `.env.example` | Auth env var template |
| 3 | `requirements.txt` | Python dependencies |
| 4 | `config/global-settings.yaml` | Shared configuration |
| 5 | `PROJECT-INDEX.md` | Auto-generated project list |
| 6 | `scripts/lib/__init__.py` | Package marker |
| 7 | `scripts/lib/config.py` | Config loading & env resolution |
| 8 | `scripts/lib/confluence_client.py` | Confluence API client |
| 9 | `scripts/confluence-sync.py` | Pull from Confluence |
| 10 | `scripts/update-confluence.py` | Push to Confluence |
| 11 | `scripts/init-project.sh` | Project scaffolding |
| 12 | `scripts/list-projects.sh` | Project listing |
| 13 | `.github/copilot-instructions.md` | Agent instructions |
| 14 | `README.md` | Setup & usage docs |

## Key Design Decisions

1. `markdown` library added for MD-to-HTML conversion in update script
2. Re-sync after push uses inline logic (avoids hyphenated import issues)
3. `sources.yaml` uses page names for CLI (not page IDs)
4. `global-settings.yaml` stores env var names, not values
5. Child page sync on by default, creates nested subdirectories
