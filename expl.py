#!/usr/bin/env python3
"""expl.py -- compatibility shim.

PaperScope's CLI moved to the `paperscope` package (see src/paperscope/cli.py). This
script explicitly translates the old `bulk`/`forum` commands into their new-CLI
equivalents (not a blind argv passthrough) and clearly refuses commands that don't have
an equivalent yet.

    python expl.py bulk --venues iclr --years 2026 --per-venue 20
      -> paperscope fetch venue --family iclr --years 2026 --papers 20

    python expl.py forum --url "https://openreview.net/forum?id=XXX"
      -> paperscope fetch forum --url "..."

Prefer calling `paperscope` directly for new work; this shim exists so existing muscle
memory and scripts keep working during the transition.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from paperscope.cli import main as paperscope_main  # noqa: E402

_NOT_YET_AVAILABLE = {
    "analyze": "Corpus analysis moves to `paperscope generate` in a later phase.",
    "skill": "Skill-file generation moves to `paperscope build-skill` in a later phase.",
    "all": "The full bulk->analyze->skill pipeline isn't available under the new CLI yet.",
}


def _warn(msg: str) -> None:
    print(f"[expl.py shim] {msg}", file=sys.stderr)


def translate(argv: list[str]) -> list[str] | None:
    """Return the equivalent `paperscope` argv, or None if there's no translation."""
    if not argv:
        return None
    command, rest = argv[0], argv[1:]

    if command in _NOT_YET_AVAILABLE:
        _warn(f"`{command}` is not available yet. {_NOT_YET_AVAILABLE[command]}")
        return None

    if command == "bulk":
        new_argv = ["fetch", "venue"]
        i = 0
        while i < len(rest):
            arg = rest[i]
            if arg == "--venues":
                new_argv.append("--family")
                i += 1
                while i < len(rest) and not rest[i].startswith("--"):
                    new_argv.append(rest[i])
                    i += 1
                continue
            if arg == "--per-venue":
                new_argv.append("--papers")
                i += 1
                if i < len(rest):
                    new_argv.append(rest[i])
                    i += 1
                continue
            if arg in ("--compress", "--output", "--force"):
                _warn(f"`{arg}` has no equivalent in the new two-tier storage model and is ignored.")
                i += 1
                if arg == "--output" and i < len(rest) and not rest[i].startswith("--"):
                    i += 1  # also skip its value
                continue
            new_argv.append(arg)
            i += 1
        _warn("translating `bulk` -> `fetch venue`: " + " ".join(new_argv))
        return new_argv

    if command == "forum":
        new_argv = ["fetch", "forum"]
        i = 0
        while i < len(rest):
            arg = rest[i]
            if arg == "--save":
                _warn("`--save` has no equivalent yet -- the new CLI prints the forum record "
                      "but doesn't write it into a corpus file. Redirect stdout if you need it saved.")
                i += 1
                continue
            new_argv.append(arg)
            i += 1
        _warn("translating `forum` -> `fetch forum`: " + " ".join(new_argv))
        return new_argv

    return None


def main() -> None:
    argv = sys.argv[1:]
    translated = translate(argv)
    if translated is None and argv and argv[0] not in _NOT_YET_AVAILABLE:
        _warn(f"unrecognized legacy command `{argv[0] if argv else ''}` -- see `paperscope --help`.")
        sys.exit(1)
    if translated is None:
        sys.exit(1)
    paperscope_main(translated)


if __name__ == "__main__":
    main()
