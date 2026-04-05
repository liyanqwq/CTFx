"""ScaffoldManager — category-specific exploit.py template generation."""

from __future__ import annotations

import os
from pathlib import Path

CATEGORIES_WITH_SCAFFOLD = {"pwn", "crypto", "forensics", "rev", "misc"}

_TEMPLATES: dict[str, str] = {
    "pwn": """#!/usr/bin/env python3
from pwn import *
import os

HOST = "chall.ctf.org"
PORT = 1337
BINARY = "./src/chall"
LIBC   = "./src/libc.so.6"

elf  = context.binary = ELF(BINARY, checksec=False)
libc = ELF(LIBC, checksec=False) if os.path.exists(LIBC) else None
context.log_level = "info"

def conn():
    if args.REMOTE:
        return remote(HOST, PORT)
    return process(BINARY)

def exploit():
    io = conn()
    # --- exploit here ---
    io.interactive()

if __name__ == "__main__":
    exploit()
""",
    "crypto": """#!/usr/bin/env python3
from Crypto.Util.number import *
from Crypto.Cipher import AES
import hashlib, itertools, string

# --- solve here ---
""",
    "forensics": """#!/usr/bin/env python3
from pathlib import Path

SRC = Path("../src")

# --- analyse here ---
""",
    "rev": """#!/usr/bin/env python3
# Tools: ghidra, ida, angr, z3

# --- solve here ---
""",
    "misc": """#!/usr/bin/env python3

# --- solve here ---
""",
}


class ScaffoldManager:
    """Generate per-category solve scaffolding."""

    @classmethod
    def generate(cls, category: str, chal_dir: Path, remote: str | None = None) -> None:
        category = category.lower()
        if category not in CATEGORIES_WITH_SCAFFOLD:
            return

        solve_dir = chal_dir / "solve"
        solve_dir.mkdir(parents=True, exist_ok=True)
        exploit_path = solve_dir / "exploit.py"
        content = _TEMPLATES[category]

        if remote and category == "pwn":
            content = content.replace('HOST = "chall.ctf.org"', f'HOST = "{remote.split()[-2] if remote.startswith("nc ") and len(remote.split()) >= 3 else "chall.ctf.org"}"')
            if remote.startswith("nc "):
                parts = remote.split()
                if len(parts) >= 3:
                    content = content.replace("PORT = 1337", f"PORT = {parts[-1]}")

        exploit_path.write_text(content, encoding="utf-8")
        try:
            os.chmod(exploit_path, 0o755)
        except OSError:
            pass
