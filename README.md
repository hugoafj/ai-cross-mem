# ai-cross-mem: Shared Memory System

Shared memory system across sessions for Claude Code and Devin/Windsurf. Automatically saves plans, decisions, and solved problems so you don't lose context when opening new sessions.

## Problem It Solves

When working with AI across different sessions, the agent doesn't remember what you did in previous sessions. You have to:
- Repeat context every time
- Manually document everything important
- Search through your commit/PR history

**ai-cross-mem** solves this by automatically saving important information in a shared location that all IDEs can read.

## Features

- ✅ **Automatic memory** - Saves plans, decisions, and problems without asking
- ✅ **Smart search** - Agent finds relevant memories when you ask
- ✅ **Cross-IDE** - Works in Claude Code and Devin/Windsurf
- ✅ **Simple** - Just Markdown files, no database
- ✅ **Portable** - Share memories between machines by copying `~/Documents/ai-cross-mem/`

## Installation

### Requirements

- Python 3.7+ installed
- Claude Code, Windsurf, or both (choose at install time)
- Windows PowerShell 5.1+ (Windows) or Bash 3.2+ (macOS)

### Windows

```powershell
cd C:\AI_Projects\ai-cross-mem
.\install.ps1 -Integration Both
```

Use `-Integration Claude` or `-Integration Windsurf` to install only one.
The default is `Both`. On macOS, use `bash install.sh claude`,
`bash install.sh windsurf`, or `bash install.sh both` (default: `both`).

### macOS

```bash
cd ~/ai_projects/ai-cross-mem
bash install.sh
```

The macOS installer requires Python 3. It installs only the selected integration(s); Claude and Windsurf use separate scripts, instructions, and hook state. Their memory files intentionally share `~/Documents/ai-cross-mem`. Existing configuration files are backed up before ai-cross-mem instructions are appended.

**PR validation note:** macOS installation and hook behavior still need testing on a Mac. Local validation was performed on Windows; the macOS integration test was skipped.

## Updating

The updater downloads the latest published release from `hugoafj/ai-cross-mem`, then reruns the installer for integrations recorded in the local install manifest:

```powershell
# Windows
python update.py
```

```bash
# macOS
python3 update.py
```

If a release declares deprecated files in `legacy-files.json`, the updater lists them and asks for confirmation before installation. It removes only those individual files from the supported skill directories, and only after the new installer succeeds; it never targets memories or global configuration. Use `--yes` to skip that confirmation in automation.

To test an update from a local project copy instead of downloading a release:

```bash
python update.py --source . --yes
```

The updater requires a published GitHub release. If no release has been published yet, it reports that clearly; local-source mode remains available for testing.

## What It Installs

The installation script:

1. ✅ Creates `~/Documents/ai-cross-mem/` for storing memories
2. ✅ Copies skill to `~/.claude/skills/ai-cross-mem/` (Claude)
3. ✅ Copies skill to `~/.codeium/windsurf/skills/ai-cross-mem/` (Devin)
4. ✅ Adds configuration to `~/.claude/AGENTS.md` and `~/.claude/CLAUDE.md`
5. ✅ Adds configuration to `~/.codeium/windsurf/AGENTS.md`

**Important**: The installers preserve existing configuration by appending ai-cross-mem instructions rather than replacing the configuration. Existing configuration is backed up before it is changed. The installers do not delete or overwrite saved memories.

## Usage

### Automatic

The system works automatically:

**Saves memory when**:
- You complete a plan
- You make an important technical decision
- You solve a complex problem
- You say: "save this to memory"

**Searches memory when**:
- You ask: "what did we do with X", "why did we decide Y"
- You reference something from previous sessions

### Manual

#### Save a memory

```bash
# 1. Create file with content
cat > /tmp/memory.md << 'EOF'
## Brief description
OAuth authentication implementation

## What
- Implemented OAuth 2.0 with Google and Microsoft
- Files: src/auth/oauth.py
- Endpoints: /auth/login, /auth/callback

## Why
Client requires corporate SSO for security
EOF

# 2. Save
python ~/.claude/skills/ai-cross-mem/scripts/save_memory.py \
  --type decision \
  --title "OAuth Implementation" \
  --content /tmp/memory.md
```

#### Search memories

```bash
# Search in current project
python ~/.claude/skills/ai-cross-mem/scripts/search_memory.py \
  --query "oauth"

# Search in all projects
python ~/.claude/skills/ai-cross-mem/scripts/search_memory.py \
  --all-projects \
  --query "authentication"
```

## Memory Structure

Memories are saved in: `~/Documents/ai-cross-mem/[project]/`

Each memory is a Markdown file:

```markdown
---
title: oauth-implementation
date: 2026-11-05
project: api-backend
type: decision
status: completed
tags: ["auth", "oauth", "security"]
---

## Brief description
OAuth 2.0 implementation with Google and Microsoft

## What
Implemented OAuth 2.0 flow:
- Files: src/auth/oauth.py:45-120
- Endpoints: /auth/login, /auth/callback, /auth/logout
- Providers: Google, Microsoft

## Why
**Context**: Client requires SSO for security policy

**Key decisions**:
1. authlib over python-oauth2 - better PKCE support
2. Redis for tokens - automatic TTL

**Trade-offs**:
- More complex but required by policy
```

## Memory Types

- **plan**: Executed or closed plans
- **decision**: Important technical decisions
- **problem**: Solved problems with their solution
- **user-request**: Anything you explicitly ask to save

## Examples

### Example 1: Question about previous work

**You**: "Why did we use Redis for OAuth tokens?"

**Claude**:
```
Found decision in memory:

📝 OAuth Implementation (2026-11-05)

We decided to use Redis for tokens because:
1. Automatic TTL - expires in 7 days without manual logic
2. Low volume - less than 10k users
3. Simple and reliable

The alternative was using the main DB, but Redis eliminates complexity with automatic TTL.
```

### Example 2: Search across projects

**You**: "Search in other projects for how we handled rate limiting"

**Claude**:
```
Found 2 memories in other projects:

1. api-gateway: "Rate Limiting with Redis" (2026-10-15)
   - Sliding window algorithm
   - 100 req/min per user

2. webhooks-service: "Rate Limiting Webhooks" (2026-09-20)
   - Token bucket algorithm
   - Different limits per tier

Want me to read any in detail?
```

## Verification

Test that installation worked:

```bash
# 1. Verify scripts installed
python ~/.claude/skills/ai-cross-mem/scripts/save_memory.py --help

# 2. Save test memory
echo "## Brief description
ai-cross-mem test

## What
Installed shared memory system

## Why
To test it works" > /tmp/test.md

python ~/.claude/skills/ai-cross-mem/scripts/save_memory.py \
  --project test \
  --type user-request \
  --title "Test" \
  --content /tmp/test.md

# 3. Search for memory
python ~/.claude/skills/ai-cross-mem/scripts/search_memory.py \
  --project test \
  --query "test"

# 4. Verify saved file
ls ~/Documents/ai-cross-mem/test/
```

### Installer tests

Run the installer checks from the repository's `ai-cross-mem` directory:

```bash
python -m unittest discover -s tests -v
```

On Windows, this runs the installer twice in an isolated temporary user folder and checks that it does not nest duplicate skill directories. On macOS, it runs the installer twice with an isolated temporary `HOME` and checks installed files, preserved settings, backups, and duplicate hook prevention. Uninstaller tests verify that tracked app files are removed while memories, unrelated settings, and user-added files are preserved. The workflow in `.github/workflows/installer-tests.yml` runs this suite on both Windows and macOS for pushes and pull requests.

## Uninstallation

```powershell
# Windows
.\uninstall.ps1

# Also remove saved memories (requires typing DELETE at the prompt)
.\uninstall.ps1 -DeleteMemories
```

```bash
# macOS
bash uninstall.sh

# Also remove saved memories (requires typing DELETE at the prompt)
bash uninstall.sh --delete-memories
```

The installer records its changes in an install manifest under the user's application-state directory (`%LOCALAPPDATA%\ai-cross-mem\install-manifest.json` on Windows; `~/Library/Application Support/ai-cross-mem/install-manifest.json` on macOS). The uninstaller removes only unchanged files recorded as installed, restores overwritten app files from backups, removes only marked ai-cross-mem sections from shared configuration, and removes only the recorded review hook. If a managed file was edited after installation, it is kept for manual review. Older installations without a manifest use a conservative cleanup that removes only recognizable files/sections.

Saved memories in `~/Documents/ai-cross-mem/` are always kept by default. `-DeleteMemories` / `--delete-memories` requires an additional exact `DELETE` confirmation before removing them.

## Troubleshooting

### Script doesn't find Python

```bash
# Verify Python installed
python --version  # or python3 --version

# Install Python if missing
# Windows: https://www.python.org/downloads/
# Mac: brew install python3
# Linux: sudo apt install python3
```

### Skill doesn't activate in Claude

1. Verify skill is installed:
   ```bash
   ls ~/.claude/skills/ai-cross-mem/
   ```

2. Verify CLAUDE.md references AGENTS.md:
   ```bash
   cat ~/.claude/CLAUDE.md
   ```

3. Restart Claude Code

### Doesn't find memories

- Verify correct project: project name is current folder name
- Verify exists: `ls ~/Documents/ai-cross-mem/[project]/`
- Try with `--all-projects` if searching in another project

## Project Structure

```
ai-cross-mem/
├── README.md                       # This file
├── install.ps1                     # Windows installer
├── install.sh                      # macOS installer
├── update.py                       # Cross-platform release updater
├── legacy-files.json               # Explicit list of deprecated installed files
├── uninstall.ps1                   # Windows uninstaller
├── uninstall.sh                    # macOS uninstaller
├── uninstall.py                    # Shared safe-uninstall implementation
├── install_state.py                # Records installer-owned changes
├── tests/                           # Installer, updater, and uninstaller tests
├── .github/workflows/               # Windows and macOS CI
│
├── skills/                         # Skills for each IDE
│   ├── claude/ai-cross-mem/
│   │   ├── SKILL.md                # Skill definition for Claude
│   │   └── scripts/
│   │       ├── __init__.py
│   │       ├── utils.py            # Shared functions
│   │       ├── save_memory.py      # Save memories
│   │       └── search_memory.py    # Search memories
│   │
│   └── windsurf/ai-cross-mem/
│       └── SKILL.md                # Skill for Devin
│
├── config/                         # Global configuration
│   ├── claude/
│   │   ├── CLAUDE.md               # Claude global config
│   │   └── AGENTS.md               # ai-cross-mem rules
│   └── windsurf/
│       └── AGENTS.md               # Devin rules
│
├── hooks/                          # Hooks
│   ├── claude/hooks.json
│   └── scripts/check_memory.py
│
└── templates/
    └── memory_template.md          # Template
```

## Roadmap

- [x] Basic Python scripts
- [x] Claude skill
- [x] Claude global configuration
- [x] Windows installation script
- [ ] update_memory.py script
- [ ] Devin/Windsurf skill
- [ ] 15-minute review hook
- [x] macOS installer
- [x] Windows and macOS uninstallation scripts
- [x] Automated installer/updater/uninstaller tests

---

**Version**: 1.0.0  
**Last updated**: 2026-11-22
**Author**: Hugo Flores (https://github.com/hugoafj)
