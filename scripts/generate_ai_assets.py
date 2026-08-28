#!/usr/bin/env python3
# © 2026 NetApp, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# See the NOTICE file in the repo root for trademark and attribution details.

"""Generate GitHub Copilot and Cursor assets from the ``ai/`` source tree.

Copilot and Cursor read different files, and only ``AGENTS.md`` is read by both.
Rather than hand-maintaining two trees, everything is authored once under
``ai/`` and this script renders each dialect.

Source layout mirrors the repository's own ``<tool>/<product>/`` convention, so
the product is derived from the directory path rather than repeated in
frontmatter::

    ai/shared/repo-context.md          kind: shared  -> AGENTS.md + copilot-instructions.md
    ai/shared/review-contribution.md   kind: task    -> /review-contribution
    ai/shared/prompt-catalog.md        kind: doc     -> docs/ai-prompt-catalog.md
    ai/ontap/conventions.md            kind: product -> globs **/ontap/**
    ai/ontap/generate-python.md        kind: task    -> /ontap-generate-python
    ai/console/local/conventions.md    kind: product -> globs **/console/local/**
    ai/console/local/prompt-catalog.md kind: doc     -> docs/console-local-prompt-catalog.md

Product subfolders are preserved in the instruction and rule trees, which both
support recursive discovery. They are flattened into ``<product>-<task>`` names
for prompts and commands, because those tools discover only the top level and
because a slash-command name comes from the filename, not the folder.

Usage::

    python scripts/generate_ai_assets.py            # write
    python scripts/generate_ai_assets.py --check    # fail on drift (CI)
    python scripts/generate_ai_assets.py --self-test
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCE_DIR = REPO / "ai"

BANNER = (
    "<!-- Generated from {source} by scripts/generate_ai_assets.py. "
    "Do not edit; run `make ai-assets`. -->"
)

# Directories fully owned by the generator. Anything here that is not produced
# by a source file is stale and gets removed.
MANAGED_DIRS = (
    ".github/instructions",
    ".github/prompts",
    ".cursor/rules",
    ".cursor/commands",
)
MANAGED_FILES = ("AGENTS.md", ".github/copilot-instructions.md")

TOOLS = ("python", "ansible", "terraform", "go")
VALID_KINDS = ("shared", "product", "task", "doc")

# Expanded in any source body. They exist so the list of prompts is written in
# exactly one place - the sources themselves.
PROMPT_INDEX_TOKEN = "{{PROMPT_INDEX}}"
PROMPT_FILES_TOKEN = "{{PROMPT_FILES}}"


@dataclass
class Source:
    """One authored file under ``ai/``."""

    path: Path
    kind: str
    description: str
    body: str
    product: str | None
    product_dir: str | None
    globs: str
    output: str | None = None  # kind: doc only - explicit destination path

    @property
    def rel(self) -> str:
        return self.path.relative_to(REPO).as_posix()

    @property
    def command_id(self) -> str:
        """Flat, globally unique name used for slash commands."""
        stem = self.path.stem
        return f"{self.product}-{stem}" if self.product else stem


def _err(errors: list[str], msg: str) -> None:
    errors.append(msg)


def parse_frontmatter(text: str, rel: str, errors: list[str]) -> tuple[dict[str, str], str]:
    """Split a leading ``---`` block into a flat mapping plus the body."""
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        _err(errors, f"{rel}: missing YAML frontmatter")
        return {}, text
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            _err(errors, f"{rel}: cannot parse frontmatter line {line!r}")
            continue
        meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta, text[match.end() :]


def load_sources(errors: list[str]) -> list[Source]:
    """Read every ``ai/**/*.md`` file and derive product scope from its path."""
    sources: list[Source] = []
    for path in sorted(SOURCE_DIR.rglob("*.md")):
        if path.name == "README.md":
            continue  # documents the tree for humans; not a prompt source
        rel = path.relative_to(REPO).as_posix()
        meta, body = parse_frontmatter(path.read_text(), rel, errors)
        if not meta:
            continue

        kind = meta.get("kind", "")
        if kind not in VALID_KINDS:
            _err(errors, f"{rel}: 'kind' must be one of {list(VALID_KINDS)}, got {kind!r}")
            continue
        description = meta.get("description", "")
        if not description:
            _err(errors, f"{rel}: 'description' is required")

        # Directory path under ai/ is the product scope. ai/shared/ is not a product.
        parts = path.relative_to(SOURCE_DIR).parent.parts
        if parts and parts[0] == "shared":
            product_dir = product = None
        elif parts:
            product_dir = "/".join(parts)
            product = "-".join(parts)
        else:
            _err(errors, f"{rel}: files must live in ai/shared/ or ai/<product>/")
            continue

        globs = meta.get("globs") or (f"**/{product_dir}/**" if product_dir else "**")

        output = meta.get("output")
        if kind == "doc" and not output:
            _err(errors, f"{rel}: 'kind: doc' requires an 'output' path")
            continue
        if kind != "doc" and output:
            _err(errors, f"{rel}: 'output' is only valid on 'kind: doc'")

        sources.append(Source(path, kind, description, body, product, product_dir, globs, output))
    return sources


def validate(sources: list[Source], errors: list[str]) -> None:
    """Catch the two mistakes this layout makes easy."""
    seen: dict[str, str] = {}
    for src in sources:
        if src.kind != "task":
            continue
        if src.command_id in seen:
            _err(
                errors,
                f"{src.rel}: command name '{src.command_id}' collides with "
                f"{seen[src.command_id]} once flattened",
            )
        seen[src.command_id] = src.rel

    for src in sources:
        if src.kind != "product" or not src.product_dir:
            continue
        if not any((REPO / tool / src.product_dir).is_dir() for tool in TOOLS):
            _err(
                errors,
                f"{src.rel}: no <tool>/{src.product_dir}/ directory exists - "
                f"check the product directory name",
            )

    shared = [s for s in sources if s.kind == "shared"]
    if len(shared) != 1:
        _err(errors, f"expected exactly one 'kind: shared' source, found {len(shared)}")

    claimed: dict[str, str] = {}
    for src in sources:
        if src.kind != "doc" or not src.output:
            continue
        if src.output in MANAGED_FILES:
            _err(errors, f"{src.rel}: output '{src.output}' is already generated by another kind")
        if src.output in claimed:
            _err(
                errors,
                f"{src.rel}: output '{src.output}' is also claimed by {claimed[src.output]}",
            )
        claimed[src.output] = src.rel


def relative_prefix(output: str) -> str:
    """``../`` prefix that walks from an output file's directory to the repo root."""
    depth = len(Path(output).parent.parts)
    return "../" * depth


def rewrite_links(body: str, prefix: str) -> str:
    """Re-anchor repo-root-relative markdown links for an output location.

    Sources write links as ``[text](python/ontap/x.py)``. Outputs live at
    varying depths, so the prefix differs per destination. Fenced code blocks
    are skipped so example snippets are never rewritten.
    """
    if not prefix:
        return body

    def fix(match: re.Match[str]) -> str:
        target = match.group(2)
        if target.startswith(("http://", "https://", "mailto:", "#", "/", "../")):
            return match.group(0)
        return f"[{match.group(1)}]({prefix}{target})"

    out: list[str] = []
    in_fence = False
    for line in body.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append(line)
            continue
        out.append(line if in_fence else re.sub(r"\[([^\]]*)\]\(([^)]+)\)", fix, line))
    return "".join(out)


def tasks_in_order(sources: list[Source]) -> list[Source]:
    return sorted((s for s in sources if s.kind == "task"), key=lambda s: s.command_id)


def prompt_index(sources: list[Source]) -> str:
    """Markdown table of every task prompt, so the index cannot drift."""
    rows = ["| Prompt | What it does |", "|--------|--------------|"]
    for src in tasks_in_order(sources):
        rows.append(f"| `/{src.command_id}` | {src.description} |")
    return "\n".join(rows)


def prompt_files(sources: list[Source]) -> str:
    """Like ``prompt_index`` but citing each prompt's source file.

    Lets a reader open the real prompt to paste into an assistant that has no
    slash-command support, instead of maintaining a condensed copy that drifts.
    """
    rows = [
        "| Command | What it does | Prompt text |",
        "|---------|--------------|-------------|",
    ]
    for src in tasks_in_order(sources):
        rows.append(f"| `/{src.command_id}` | {src.description} | [{src.rel}]({src.rel}) |")
    return "\n".join(rows)


def render(sources: list[Source]) -> dict[str, str]:
    """Map every output path to its full contents."""
    outputs: dict[str, str] = {}
    tokens = {
        PROMPT_INDEX_TOKEN: prompt_index(sources),
        PROMPT_FILES_TOKEN: prompt_files(sources),
    }

    def emit(path: str, source: Source, frontmatter: str | None) -> None:
        body = source.body
        for token, table in tokens.items():
            body = body.replace(token, table)
        body = rewrite_links(body, relative_prefix(path)).strip()
        banner = BANNER.format(source=source.rel)
        head = f"{frontmatter}\n{banner}\n" if frontmatter else f"{banner}\n"
        outputs[path] = f"{head}\n{body}\n"

    for src in sources:
        if src.kind == "shared":
            # GitHub.com Copilot Chat reads only copilot-instructions.md; Cursor
            # reads only AGENTS.md. Identical bodies, so VS Code seeing both is
            # harmless.
            emit("AGENTS.md", src, None)
            emit(".github/copilot-instructions.md", src, None)

        elif src.kind == "product":
            stem = src.path.stem
            emit(
                f".github/instructions/{src.product_dir}/{stem}.instructions.md",
                src,
                f'---\napplyTo: "{src.globs}"\n---',
            )
            emit(
                f".cursor/rules/{src.product_dir}/{stem}.mdc",
                src,
                f'---\ndescription: "{src.description}"\n'
                f'globs: "{src.globs}"\nalwaysApply: false\n---',
            )

        elif src.kind == "task":
            emit(
                f".github/prompts/{src.command_id}.prompt.md",
                src,
                f'---\ndescription: "{src.description}"\n---',
            )
            emit(f".cursor/commands/{src.command_id}.md", src, None)

        elif src.kind == "doc":
            assert src.output  # guaranteed by load_sources
            emit(src.output, src, None)

    return outputs


def existing_managed_files(doc_outputs: set[str]) -> set[str]:
    """Generated files currently on disk, used to spot ones now orphaned.

    Doc outputs are passed in rather than hardcoded: they live in ``docs/``
    alongside hand-written files, so only the declared paths are ours.
    """
    found = {f for f in set(MANAGED_FILES) | doc_outputs if (REPO / f).exists()}
    for directory in MANAGED_DIRS:
        base = REPO / directory
        if base.is_dir():
            found |= {p.relative_to(REPO).as_posix() for p in base.rglob("*") if p.is_file()}
    return found


def self_test() -> int:
    """Guard the link-depth arithmetic - a wrong prefix renders fine but resolves nowhere."""
    cases = {
        "AGENTS.md": "",
        ".github/copilot-instructions.md": "../",
        ".github/prompts/ontap-generate-python.prompt.md": "../../",
        ".cursor/commands/ontap-generate-python.md": "../../",
        ".github/instructions/ontap/conventions.instructions.md": "../../../",
        ".cursor/rules/console/local/conventions.mdc": "../../../../",
        "docs/ai-prompt-catalog.md": "../",
        "docs/console-local-prompt-catalog.md": "../",
    }
    failures = 0
    for path, want in cases.items():
        got = relative_prefix(path)
        if got != want:
            print(f"FAIL prefix for {path}: want {want!r}, got {got!r}")
            failures += 1

    body = (
        "see [client](python/ontap/ontap_client.py) and [web](https://x.dev)\n"
        "```\n[not a link](python/ontap/skip.py)\n```\n"
        "and [notice](NOTICE)\n"
    )
    rewritten = rewrite_links(body, "../../")
    checks = [
        ("../../python/ontap/ontap_client.py" in rewritten, "root-relative link rewritten"),
        # Checks the *whole* original markdown link is byte-for-byte intact, not just
        # that the URL substring appears somewhere - a bare substring check here would
        # also match a wrongly-prefixed URL (e.g. "../../https://x.dev").
        ("[web](https://x.dev)" in rewritten, "url untouched"),
        ("[not a link](python/ontap/skip.py)" in rewritten, "fenced block untouched"),
        ("../../NOTICE" in rewritten, "bare filename rewritten"),
    ]
    for ok, label in checks:
        if not ok:
            print(f"FAIL {label}")
            failures += 1

    print("self-test passed" if not failures else f"self-test failed ({failures})")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify generated files match ai/ without writing (used by CI)",
    )
    parser.add_argument("--self-test", action="store_true", help="test internal helpers")
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    if not SOURCE_DIR.is_dir():
        print(f"::error::source directory {SOURCE_DIR} not found")
        return 1

    errors: list[str] = []
    sources = load_sources(errors)
    validate(sources, errors)
    if errors:
        for message in errors:
            print(f"::error::{message}")
        print(f"\n{len(errors)} problem(s) in ai/ - nothing generated.")
        return 1

    outputs = render(sources)
    doc_outputs = {s.output for s in sources if s.kind == "doc" and s.output}
    stale = existing_managed_files(doc_outputs) - set(outputs)

    if args.check:
        drift: list[str] = []
        for path, content in sorted(outputs.items()):
            target = REPO / path
            if not target.exists():
                drift.append(f"{path}: missing")
            elif target.read_text() != content:
                drift.append(f"{path}: out of date")
        drift += [f"{path}: stale, no longer generated" for path in sorted(stale)]
        if drift:
            for item in drift:
                print(f"::error::{item}")
            print(
                f"\n{len(drift)} generated file(s) do not match ai/.\n"
                "Run 'make ai-assets' and commit the result."
            )
            return 1
        print(f"AI assets up to date — {len(outputs)} file(s) match ai/.")
        return 0

    for path, content in sorted(outputs.items()):
        target = REPO / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    for path in sorted(stale):
        (REPO / path).unlink()
        print(f"  removed stale {path}")

    counts: dict[str, int] = {}
    for src in sources:
        counts[src.kind] = counts.get(src.kind, 0) + 1
    summary = ", ".join(f"{n} {kind}" for kind, n in sorted(counts.items()))
    print(f"Generated {len(outputs)} file(s) from {len(sources)} source(s) ({summary}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
