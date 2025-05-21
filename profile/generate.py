#!/usr/bin/env python3
"""
generate_glitch_alien_md.py
Read an ASCII alien from `alien.txt`, apply random “Zalgo” glitches,
and emit `glitched_alien.md` with:

1. A header      → "# 2398 Research Inc"
2. A fenced code → the glitched alien
3. A footer      → free-form Markdown (links, credits, etc.)

Usage:  python generate_glitch_alien_md.py
"""

from pathlib import Path
import random
import sys

# ──────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────
ALIEN_TXT       = Path("alien.txt")        # source art
OUTPUT_MD       = Path("README.md")
GLITCH_INTENSITY = 0.35

HEADER_MD = "# 2398 Research Inc\n\n"

FOOTER_MD = """
---
Built with 🛠️ & 👽 by **[2398 Research Inc](https://2398.ai)**  
Say hi [hello@2389.ai](mailto:hello@2389.ai)
"""

COMBINING = [chr(c) for c in range(0x0300, 0x036F + 1)]  # Unicode marks
STATIC_NOISE = ['`', '~', '*', '_', '-', '^']


# ──────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────
def read_alien(path: Path) -> list[str]:
    if not path.is_file():
        sys.exit(f"❌ {path} not found — put an ASCII alien there first.")
    return path.read_text(encoding="utf-8").splitlines()


def glitch_char(ch: str) -> str:
    if ch == " " or random.random() >= GLITCH_INTENSITY:
        return ch
    marks = ''.join(random.choice(COMBINING) for _ in range(random.randint(1, 3)))
    noise = random.choice(STATIC_NOISE) if random.random() < 0.3 else ""
    return ch + marks + noise


def glitch_line(line: str) -> str:
    return ''.join(glitch_char(c) for c in line)


def build_markdown(lines: list[str]) -> str:
    fence_open, fence_close = "```text\n", "\n```\n"
    glitched_art = "\n".join(glitch_line(l) for l in lines)
    return HEADER_MD + fence_open + glitched_art + fence_close + FOOTER_MD + "\n"


# ──────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────
def main() -> None:
    alien_lines = read_alien(ALIEN_TXT)
    OUTPUT_MD.write_text(build_markdown(alien_lines), encoding="utf-8")
    print(f"✅ Wrote {OUTPUT_MD.resolve()}")


if __name__ == "__main__":
    main()
