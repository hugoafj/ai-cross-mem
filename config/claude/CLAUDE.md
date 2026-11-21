# ============================================================
# ai-cross-mem: Shared Memory System
# Installed: 2026-11-05
# ============================================================

# Claude Code Global Configuration

Read global rules that include the ai-cross-mem system:

@~/.claude/AGENTS.md

## Notes about ai-cross-mem

- ai-cross-mem system saves memory across sessions automatically
- Memories are saved in `~/Documents/ai-cross-mem/[project]/`
- ai-cross-mem skill loads automatically from `~/.claude/skills/`
- Each project can have its own AGENTS.md that combines with this global one

## How It Works

When you open any project in Claude Code:
1. This global CLAUDE.md loads first
2. Loads AGENTS.md containing ai-cross-mem instructions
3. ai-cross-mem skill activates automatically when relevant
4. Current project memories are available for query

# ============================================================
# End of ai-cross-mem
# ============================================================
