"""Optional, `anthropic`-backed automation of the "ask the model" step in Phase 3B
generation. This is the ONLY file in `paperscope` that references `anthropic`, and even
here the import is inside `run_provider_generation`, not at module level -- importing
this module alone does not pull `anthropic` into `sys.modules`; only calling
`run_provider_generation` does. Requires the `[llm]` optional dependency.

The manual path (`paperscope export-prompt`, run through Claude Code by hand, then
`paperscope render`) is the primary supported workflow and needs none of this -- see
generation.py's module docstring. No live API call is made anywhere in this package
outside this function.
"""

from __future__ import annotations

from pathlib import Path

from paperscope.generation import parse_provider_response


def run_provider_generation(
    *, prompt_dir: Path, provider: str, model: str, max_tokens: int = 4096, temperature: float = 0.0
) -> dict:
    """Calls `provider` with the bundle written by `export_prompt` and returns the
    parsed (not yet validated) claims payload -- callers must still run
    `generation.validate_claims` before trusting or rendering it.
    """
    if provider != "anthropic":
        raise ValueError(f"unsupported provider: {provider!r} (only 'anthropic' is implemented)")

    import anthropic  # local import -- this file is the sole place anthropic is referenced

    prompt_dir = Path(prompt_dir)
    prompt_text = (prompt_dir / "prompt.md").read_text()
    schema_text = (prompt_dir / "response_schema.json").read_text()
    statistics_text = (prompt_dir / "statistics.json").read_text()
    evidence_text = (prompt_dir / "evidence.json").read_text()

    client = anthropic.Anthropic()
    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[{
            "role": "user",
            "content": (
                f"{prompt_text}\n\n---\nresponse_schema.json:\n{schema_text}\n\n"
                f"---\nstatistics.json:\n{statistics_text}\n\n---\nevidence.json:\n{evidence_text}"
            ),
        }],
    )
    raw_text = "".join(block.text for block in message.content if getattr(block, "type", None) == "text")
    return parse_provider_response(raw_text)
