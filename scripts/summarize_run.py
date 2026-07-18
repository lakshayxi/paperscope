#!/usr/bin/env python3
"""Parse the BULK_SUMMARY_JSON line paperscope's CLI prints, and turn it into:
  1. a markdown table written to $GITHUB_STEP_SUMMARY (or stdout if unset), and
  2. a compact run_summary.json suitable for committing to the `data` branch --
     the full run log is uploaded separately as a workflow artifact, not committed here.

Usage: python scripts/summarize_run.py <log_file> <run_summary_output_path>
Exits non-zero if the summary couldn't be found, or if any venue reports a "partial"
status -- so a degraded run is visible in the job's exit code, not just its logs.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

MARKER = "BULK_SUMMARY_JSON="


def find_summary(log_text: str) -> list[dict] | None:
    for line in reversed(log_text.splitlines()):
        if line.startswith(MARKER):
            return json.loads(line[len(MARKER):])
    return None


def render_markdown(summary: list[dict]) -> str:
    lines = [
        "### PaperScope fetch summary",
        "",
        "| Venue | Status | New | Refreshed | Errors |",
        "|---|---|---|---|---|",
    ]
    for entry in summary:
        lines.append(
            f"| {entry.get('venue', '?')} | {entry.get('status', '?')} | "
            f"{entry.get('new', 0)} | {entry.get('refreshed', 0)} | {entry.get('errors', 0)} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit("usage: summarize_run.py <log_file> <run_summary_output_path>")
    log_path, out_path = Path(sys.argv[1]), Path(sys.argv[2])

    log_text = log_path.read_text()
    summary = find_summary(log_text)

    if summary is None:
        print("no BULK_SUMMARY_JSON line found in the run log -- treating as failure", file=sys.stderr)
        step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if step_summary:
            with open(step_summary, "a") as f:
                f.write("### PaperScope fetch summary\n\nNo summary produced -- run likely crashed.\n")
        sys.exit(1)

    markdown = render_markdown(summary)
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a") as f:
            f.write(markdown)
    else:
        print(markdown)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"generated_at": time.time(), "venues": summary}, indent=2, sort_keys=True))

    if any(entry.get("status") == "partial" for entry in summary):
        sys.exit(1)


if __name__ == "__main__":
    main()
