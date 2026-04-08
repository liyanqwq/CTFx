# CTFx

A local-first CTF workspace manager and assistant CLI for Jeopardy and AWD competitions.

## Background

CTFx started from a bunch of PowerShell scripts I wrote for CTF competitions back in HKCERT 2024.

Later, in the HKCERT 2025 Final, I made a Python-based CTF Assistant for AWD matches. It worked pretty well, got some positive feedback, and helped our team achieve a solid result.

After that, I decided to turn those ideas and experiences into CTFx, hoping it can give CTF players a bit of extra help in the AI era.

## Features

- **Competition management** — create, list, and switch between CTF workspaces
- **Challenge scaffolding** — auto-generate category-specific solve templates (`pwn`, `crypto`, `forensics`, `rev`, `misc`)
- **Platform integration** — fetch challenges and submit flags via CTFd API using either team token or platform cookies
- **Terminal integration** — open shells, WSL, editors, and file explorers at challenge paths
- **AI context** — generate `prompt.md` with competition context plus CLI/MCP usage notes for LLM-assisted solving
- **WebUI** — React dashboard with challenge add/delete, editable challenge detail, flags table, and writeup editor
- **REST API + MCP** — machine-readable interface for Claude Desktop / Cursor integration
- **AWD mode** — SSH/SCP helpers, exploit runner, patch tracker, host map

## Installation

Requires Python 3.11+.

```sh
pip install ctfx
# or with uv (recommended)
uv tool install CTFx
```

### Install Guide

Install from PyPI:

```sh
pip install ctfx
ctfx --help
```

Upgrade to the latest release:

```sh
pip install -U ctfx
```

Install from a local checkout during development:

```sh
git clone https://github.com/liyanqwq/CTFx
cd CTFx
pip install -e .
ctfx --help
```

## Quick Start

```sh
# First run — initializes ~/.config/ctfx/config.json
ctfx setup

# Create a competition workspace
ctfx comp init --name HKCERT_CTF --year 2025 --mode jeopardy --platform ctfd

# Switch to it
ctfx use HKCERT_CTF_2025

# Add a challenge
ctfx add baby_pwn pwn

# Open in editor
ctfx code pwn/baby_pwn

# Open a terminal at the solve directory
ctfx cli pwn/baby_pwn/solve

# Start the WebUI + API + MCP server
ctfx serve

# Open WebUI in browser (auto-login)
ctfx webui
```

### Typical Flag Workflow

`CTFx` now separates local flag recording from remote submission:

1. Save a discovered flag locally in the WebUI or via API. This moves the challenge to `hoard`.
2. Review hoarded flags in the `Flags` page.
3. Submit the flag to the remote platform when ready.
4. A successful remote submission promotes the challenge to `solved`.

## Notes

- Paths passed to `ctfx cli`, `ctfx code`, `ctfx explorer`, API routes, and MCP tools are restricted to the active competition workspace. Escaping with `..` is rejected.
- Challenge categories, challenge names, and AWD service names are treated as path components and must not contain `/` or `\\`.
- If `terminal.python_cmd` contains spaces, quote the executable path normally. Example on Windows: `"C:\Program Files\Python313\python.exe" -u`
- `ctfx webui` generates a one-time login URL for the local WebUI. API and MCP still use the root token unless you are already authenticated in the browser.
- For platform-backed competitions, set either `team_token` or `team_cookies` in the competition profile before attempting remote submission.
- Challenge status flow is `fetched -> seen -> working -> hoard -> solved`.

## CLI Reference

```
ctfx comp list [query]                  List competitions
ctfx comp use <name>                    Set active competition
ctfx comp init                          Create new competition workspace
ctfx comp info                          Show active competition metadata

ctfx chal list [query] [--cat] [--status]   List challenges
ctfx chal add <name> [cat]             Add and scaffold a challenge
ctfx chal rm <name>                    Remove a challenge
ctfx chal info <name>                  Show challenge detail
ctfx chal status <name> <status>       Update challenge status

ctfx cli [path]                         Open terminal at path
ctfx wsl [path] [-- cmd]               Open WSL shell or run command
ctfx e [path]                          Open file explorer
ctfx code [path]                       Open editor
ctfx py [file]                         Run Python in configured environment

ctfx fetch [--cat] [--chal]            Fetch challenges from platform
ctfx submit <flag> [--chal]            Submit flag to platform
ctfx import <url>                      LLM-assisted challenge import

ctfx ai [--print]                      Generate AI context prompt.md with CLI/MCP notes
ctfx mcp [--out PATH]                  Generate MCP client config

ctfx webui / ctfx web / ctfx ui        Open WebUI in browser
ctfx token update                      Rotate root token

ctfx config show                       Display current configuration
ctfx config list                       Alias for config show
ctfx config set <key> <value>          Set a config value (dot-notation)

ctfx serve [--port] [--host]           Start WebUI + API + MCP server
ctfx setup                             Interactive configuration wizard
ctfx i                                 Interactive REPL

ctfx toolkit list [--cat] [--tag] [--set]    List tools across active sets
ctfx toolkit add [--set <id>]                Add a tool interactively
ctfx toolkit rm <tool-id> [--set <id>]       Remove a tool
ctfx toolkit info <tool-id>                  Show tool detail (prompt, ref, cmd)
ctfx toolkit import <url|file> [--as <id>]  Import a set
ctfx toolkit export <set-id> [--out file]    Export a set to JSON
ctfx toolkit update [<set-id>]              Re-fetch set(s) from source URL
ctfx toolkit set list                        List all sets
ctfx toolkit set create <name>              Create a new set
ctfx toolkit set enable/disable <set-id>    Toggle set activation
ctfx toolkit set rm <set-id>                Delete a set
```

### Aliases
| Short | Full |
|---|---|
| `ctfx use <comp>` | `ctfx comp use <comp>` |
| `ctfx init` | `ctfx comp init` |
| `ctfx add <chal> [cat]` | `ctfx chal add <chal> [cat]` |
| `ctfx e [path]` | `ctfx explorer [path]` |
| `ctfx i` | `ctfx interactive` |

## Configuration

Global config lives at `~/.config/ctfx/config.json`. Run `ctfx setup` to configure interactively, or use `ctfx config set` for individual keys.

```sh
ctfx config show                        # view all settings
ctfx config set serve.port 9000
ctfx config set terminal.editor_cmd cursor
ctfx config set terminal.wsl_distro ubuntu
ctfx config set basedir ~/ctf
```

Settable keys: `basedir`, `active_competition`, `serve.host`, `serve.port`, `terminal.cli_cmd`, `terminal.editor_cmd`, `terminal.wsl_distro`, `terminal.python_cmd`, `terminal.explorer_cmd`, `terminal.file_manager_cmd`, `auth.one_time_login_ttl_sec`, `auth.session_ttl_sec`, `auth.webui_cookie_name`

Key fields:
- `basedir` — root directory for all competition workspaces (default: `~/ctf`)
- `root_token` — auth secret for REST API, MCP, and WebUI; rotate with `ctfx token update` (not settable via `config set`)
- `serve.port` — default server port (default: `8694`)
- `terminal.*` — shell, editor, WSL distro, Python command

Example Windows Python configuration with spaces in the executable path:

```sh
ctfx config set terminal.python_cmd "\"C:\Program Files\Python313\python.exe\" -u"
```

## Server & Authentication

```sh
ctfx serve              # starts on 127.0.0.1:8694 by default
ctfx webui              # opens browser with auto one-time login
```

API and MCP endpoints require `Authorization: Bearer <root_token>`.

The WebUI authenticates through a one-time login URL and then uses a secure session cookie for subsequent browser requests.

Changing the active competition through the CLI or API also updates the in-process MCP server state, so MCP tools follow the currently selected competition.

MCP client config for Claude Desktop / Cursor:
```sh
ctfx mcp --out mcp.json
```

The generated MCP URL uses `/mcp/` with a trailing slash.

## Workspace Structure

```
~/ctf/
└── HKCERT_CTF_2025/
    ├── ctf.json
    ├── prompt.md
    └── pwn/
        └── baby_pwn/
            ├── src/
            ├── solve/
            │   └── exploit.py
            ├── wp.md
            └── chal.md
```

## AWD Mode

Set `"mode": "awd"` in `ctf.json` to enable AWD commands:

```sh
ctfx awd ssh <service> [--team NAME]    SSH into service host
ctfx awd scp <service> <src> <dst>      SCP file transfer
ctfx awd cmd <service> -- <command>     Run remote command
```

Security note:
- AWD SSH now relies on known host keys. Add the target host to your SSH known hosts first, otherwise the connection will be rejected instead of being auto-trusted.

## Personal Attacker Toolkit

CTFx includes a personal toolkit registry — a shareable catalogue of attack tools tagged by challenge category. The LLM queries it via MCP (`get_toolkit`) to select the right tool for each challenge.

### Quick Start

```sh
# Add a tool to your personal set (interactive)
ctfx toolkit add

# List all active tools
ctfx toolkit list

# Filter by category or tag
ctfx toolkit list --cat pwn --tag rop

# Import a shared set from a URL or local file
ctfx toolkit import https://gist.github.com/example/xxxx
ctfx toolkit import ~/Downloads/crypto-recipes.json --as crypto-recipes

# Export your personal set to share it
ctfx toolkit export personal --out my-toolkit.json

# Keep an imported set up to date
ctfx toolkit update
```

### Set Management

Multiple toolkit sets can be active simultaneously. Tools are merged in order — if two active sets define the same tool ID, the first set wins.

```sh
ctfx toolkit set list                  # show all sets with active status
ctfx toolkit set enable <set-id>       # add to active sets
ctfx toolkit set disable <set-id>      # remove from active sets (keeps file)
ctfx toolkit set rm <set-id>           # delete set
```

### Sharing Protocol

A toolkit set is a plain JSON file. Share it via any URL (GitHub Gist, raw file, etc.):

```json
{
  "id": "my-pwn-toolkit",
  "name": "My PWN Toolkit",
  "author": "you",
  "version": "1.0.0",
  "tools": [
    {
      "id": "pwntools-rop",
      "name": "pwntools ROP chain",
      "categories": ["pwn"],
      "tags": ["rop", "x86_64"],
      "cmd": "python {exploit}",
      "prompt": "Use when binary has NX enabled and you need to leak libc. Check checksec first."
    }
  ]
}
```

The `prompt` field tells the LLM *when and how* to use the tool — this is the most important field for MCP accuracy.

### MCP Integration

When working on a challenge, call `get_toolkit` first to retrieve relevant tools:

```
get_toolkit(category="pwn")           → filtered list with prompts
run_toolkit_tool("john-zip", {"file": "hash.txt"})  → stdout/stderr/returncode
```

## Platform Support

| Platform | Fetch | Submit |
|---|---|---|
| CTFd | yes | yes |
| rCTF | planned | planned |
| Manual | via `ctfx add` | no |

## Development

```sh
git clone https://github.com/liyanqwq/CTFx
cd CTFx
pip install -e .
ctfx --help
```

Frontend (React + Vite):
```sh
cd frontend
npm install
npm run dev       # dev server
npm run build     # outputs to ctfx/server/static/
```
