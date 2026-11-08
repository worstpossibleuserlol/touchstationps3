#!/usr/bin/env python3
"""Add dated GPLv2 downstream notices to modified upstream Android text files."""
from __future__ import annotations

import argparse
import datetime as dt
import subprocess
from pathlib import Path

TEXT_MARKERS = {
    ".kt": "//",
    ".java": "//",
    ".kts": "//",
    ".gradle": "//",
    ".xml": "<!--",
    ".pro": "#",
    ".properties": "#",
}

def git_lines(root: Path, *args: str) -> list[str]:
    output = subprocess.check_output(
        ["git", "-C", str(root), *args],
        text=True,
        stderr=subprocess.STDOUT,
    )
    return [line for line in output.splitlines() if line.strip()]

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()

    source = args.source.resolve()
    root = Path(subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "--show-toplevel"],
        text=True,
    ).strip())
    prefix = source.relative_to(root).as_posix().rstrip("/") + "/"

    changed = set(git_lines(root, "diff", "--name-only", "HEAD"))
    changed.update(git_lines(root, "ls-files", "--others", "--exclude-standard"))
    changed = sorted(p for p in changed if p.startswith(prefix))

    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    upstream_sha = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    manifest = [
        "# TouchStation downstream modification record",
        "",
        f"- Upstream base: ARMSX2/ARMSX3 commit {upstream_sha}",
        f"- Notice date: {today} (UTC)",
        "- License for the downstream combined work: GPL-2.0-only, subject to the licenses of independent third-party components.",
        "",
        "The following paths were modified or added by the TouchStation build patches relative to the pinned upstream checkout.",
        "",
        "| Path | Handling |",
        "|---|---|",
    ]

    for rel in changed:
        path = root / rel
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        marker = TEXT_MARKERS.get(suffix)
        try:
            raw = path.read_bytes()
            content = raw.decode("utf-8")
        except (UnicodeDecodeError, OSError):
            content = None

        if content is not None and marker:
            if "TouchStation downstream modification notice" not in content[:1200]:
                if marker == "<!--":
                    notice = f"<!-- TouchStation downstream modification notice: modified or added by TouchStation on {today}; distributed under GPL-2.0-only. -->\n"
                    if content.startswith("<?xml"):
                        newline = content.find("\n")
                        content = content[:newline + 1] + notice + content[newline + 1:]
                    else:
                        content = notice + content
                else:
                    content = (
                        f"{marker} TouchStation downstream modification notice: "
                        f"modified or added by TouchStation on {today}; distributed under GPL-2.0-only.\n"
                        + content
                    )
                path.write_text(content, encoding="utf-8")
            handling = "dated inline source notice"
        elif content is not None:
            handling = "listed here; format has no configured safe comment syntax"
        else:
            handling = "binary asset; listed here (inline source comments are not possible)"
        manifest.append(f"| {rel} | {handling} |")

    (root / "TOUCHSTATION_MODIFICATIONS.md").write_text(
        "\n".join(manifest) + "\n", encoding="utf-8"
    )
    print(f"Recorded {len(changed)} changed/added upstream paths in TOUCHSTATION_MODIFICATIONS.md")

if __name__ == "__main__":
    main()
