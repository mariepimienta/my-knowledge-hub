# Knowledge Hub

A monorepo for managing project knowledge — Confluence pages, notes, and emails — with shared tooling and AI agent support.

## Quick Start

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Set up Confluence credentials
cp .env.example .env
# Edit .env with your values

# 3. Create your first project
bash scripts/init-project.sh my-project

# 4. Add pages to projects/my-project/sources.yaml, then sync
python scripts/confluence-sync.py --project my-project
```

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `CONFLUENCE_BASE_URL` | Your Confluence instance URL | `https://your-domain.atlassian.net/wiki` |
| `CONFLUENCE_EMAIL` | Your Atlassian account email | `user@example.com` |
| `CONFLUENCE_API_TOKEN` | Atlassian API token ([create one](https://id.atlassian.com/manage-profile/security/api-tokens)) | `ABCdef123...` |

## Workflow

### Pulling Confluence Pages

1. Configure pages in `projects/<name>/sources.yaml`:
   ```yaml
   pages:
     - name: architecture
       page_id: "12345678"
       local_path: confluence/architecture.md
       access: read-only
       sync_children: true
   ```

2. Sync:
   ```bash
   # All pages for a project
   python scripts/confluence-sync.py --project my-project

   # A specific page
   python scripts/confluence-sync.py --project my-project --page architecture

   # Force re-sync
   python scripts/confluence-sync.py --project my-project --force
   ```

3. Synced pages appear as markdown in `projects/<name>/confluence/`. Child pages are nested in subdirectories mirroring the Confluence hierarchy.

### Pushing to Confluence

Only pages with `access: read-write` in `sources.yaml` can be updated.

```bash
# From a file
python scripts/update-confluence.py --project my-project --page architecture --file content.md

# From stdin
cat content.md | python scripts/update-confluence.py --project my-project --page architecture --stdin
```

The local copy is automatically re-synced after a successful push.

## Scripts Reference

| Script | Description |
|--------|-------------|
| `scripts/confluence-sync.py` | Pull Confluence pages to local markdown |
| `scripts/update-confluence.py` | Push local markdown to Confluence |
| `scripts/init-project.sh <name>` | Create a new project with standard structure |
| `scripts/list-projects.sh` | List all projects with status summary |

## Project Structure

```
my-knowledge-hub/
├── .github/
│   └── copilot-instructions.md    # AI agent instructions
├── config/
│   └── global-settings.yaml       # Shared configuration
├── scripts/
│   ├── lib/
│   │   ├── config.py              # Config loading utilities
│   │   └── confluence_client.py   # Confluence API client
│   ├── confluence-sync.py         # Pull from Confluence
│   ├── update-confluence.py       # Push to Confluence
│   ├── init-project.sh            # Create new project
│   └── list-projects.sh           # List projects
├── projects/
│   └── <project-name>/
│       ├── PROJECT.md              # Project overview
│       ├── sources.yaml            # Confluence page config
│       ├── .sync-metadata.json     # Sync state
│       ├── confluence/             # Synced pages + assets
│       ├── notes/                  # Manual notes
│       └── emails/                 # Email threads
├── .env.example                    # Credential template
├── PROJECT-INDEX.md                # Auto-generated project list
├── requirements.txt                # Python dependencies
└── README.md
```

## .gitignore Considerations

The `.gitignore` excludes `.env` (credentials) and Python artifacts. Synced Confluence content (`projects/*/confluence/`) is **not** gitignored by default — commit it if you want version history, or add it to `.gitignore` if you prefer to always sync fresh.
