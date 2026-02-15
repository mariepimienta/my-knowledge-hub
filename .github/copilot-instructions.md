# Copilot Agent Instructions — Knowledge Hub

You are assisting with a **knowledge hub monorepo** that manages project knowledge from Confluence, notes, and emails. Each project lives under `projects/<name>/` with its own isolated context.

---

## Project Scoping Rules

**CRITICAL:** Always scope your work to one project at a time.

1. **Identify the active project** before answering any question. If the user hasn't specified one, ask: "Which project are you working on?"
2. **Only search files within the active project's directory**: `projects/<name>/`
3. **Never mix context** across projects. Information from `projects/alpha/` is irrelevant when working on `projects/beta/`.
4. The `PROJECT-INDEX.md` at the repo root lists all projects — use it to discover available projects.

---

## File Organization

Each project has this structure:

```
projects/<name>/
├── PROJECT.md              # Project overview, contacts, links
├── sources.yaml            # Confluence page configuration
├── .sync-metadata.json     # Sync state (don't edit manually)
├── confluence/             # Synced Confluence pages (markdown)
│   ├── page-name.md        # Parent page
│   ├── page-name/          # Child pages of "page-name"
│   │   ├── child-one.md
│   │   └── child-one/      # Grandchild pages
│   │       └── deep-page.md
│   └── assets/             # Attachments (images, files)
│       └── 12345-diagram.png
├── notes/                  # Manual notes and documentation
└── emails/                 # Saved email threads
```

### Important: Child Pages

The `confluence/` directory uses **nested subdirectories** to mirror the Confluence page hierarchy. When searching for information:
- Always search **recursively** through all subdirectories
- A page like `architecture.md` may have child pages in `architecture/backend-design.md`
- Child pages can be nested arbitrarily deep

---

## Local-First Principle

**Always search local files first.** The locally synced markdown files in `confluence/`, `notes/`, and `emails/` ARE the knowledge base.

- **DO:** Search local files to answer questions about the project
- **DO:** Read markdown files in `confluence/` for Confluence content
- **DO:** Look in `notes/` and `emails/` for additional context
- **DON'T:** Call the Confluence API directly — you don't have access
- **DON'T:** Suggest fetching content from Confluence when local files exist

---

## Confluence Sync Rules

Sync is a **manual action** — only run sync commands when the user explicitly asks.

### Pulling pages (read)

```bash
# Sync all configured pages for a project
python scripts/confluence-sync.py --project <name>

# Sync a specific page
python scripts/confluence-sync.py --project <name> --page <page-name>

# Force re-sync even if version unchanged
python scripts/confluence-sync.py --project <name> --force
```

### Pushing updates (write)

```bash
# Update a page from a local file
python scripts/update-confluence.py --project <name> --page <page-name> --file <path>

# Update a page from stdin
echo "# Updated content" | python scripts/update-confluence.py --project <name> --page <page-name> --stdin
```

**Before pushing:** Check `sources.yaml` — only pages with `access: read-write` can be updated. If a page is `read-only`, inform the user and do not attempt the update.

### After pushing

After a successful push via `update-confluence.py`, the local copy is automatically re-synced. No need to run `confluence-sync.py` separately.

---

## Script Reference

| Script | Purpose |
|--------|---------|
| `scripts/confluence-sync.py` | Pull Confluence pages to local markdown |
| `scripts/update-confluence.py` | Push markdown to Confluence |
| `scripts/init-project.sh` | Create a new project with standard structure |
| `scripts/list-projects.sh` | List all projects with status summary |

---

## Configuration Files

- **`config/global-settings.yaml`** — Shared defaults (env var names, sync settings)
- **`projects/<name>/sources.yaml`** — Per-project Confluence page definitions
- **`.env`** — Confluence credentials (never committed, see `.env.example`)

---

## General Preferences

- When answering questions about a project, cite the specific file and section you found the answer in
- Prefer concise, actionable answers over lengthy explanations
- When creating notes, save them to `projects/<name>/notes/` with descriptive filenames
- When referencing Confluence pages, use the local markdown paths, not Confluence URLs
- If information seems outdated, suggest running a sync: "This might be outdated — want me to run a sync?"
