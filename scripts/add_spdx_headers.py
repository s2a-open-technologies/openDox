"""openDox - Medical transcription platform.

Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>
SPDX-FileCopyrightText: 2025 Christopher Abanilla <christopher.abanilla@gmx.de>
SPDX-License-Identifier: AGPL-3.0-or-later

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

One-off (but reusable — run it again after adding new headered files)
maintenance script: inserts REUSE-compliant SPDX short-form tags right
after the existing "Copyright (C) <year> Christopher Abanilla ..." line in
every file that already carries the project's full-text AGPL header,
regardless of comment style (Python docstring, TS/TSX block comment,
Dockerfile "#" comments) — the insertion works by slicing off whatever
precedes "Copyright (C)" on that line and reusing it as the prefix for the
two new lines, so no per-extension special-casing is needed.

Deliberately does NOT touch files with no header at all (SPDX-headers-adding
a header for the first time is a bigger, more varied editorial decision —
see AGENTS.md/the audit-checklist plan for the handful of files handled by
hand instead) or tests/**, alembic/versions/** (covered by REUSE.toml's bulk
annotation instead, see the REUSE spec's mechanism for exactly this case).

Usage:
    python scripts/add_spdx_headers.py            # apply
    python scripts/add_spdx_headers.py --dry-run  # list files that would change
"""

import argparse
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

INCLUDE_EXTENSIONS = {".py", ".ts", ".tsx", ".css"}
INCLUDE_BASENAMES = {"Dockerfile"}

EXCLUDE_DIR_PARTS = {
    "node_modules",
    ".venv",
    "dist",
    "backend/static",
    "alembic/versions",
    ".git",
}

COPYRIGHT_RE = re.compile(r"Copyright \(C\) (\d{4})\s+Christopher Abanilla")
# Split so this file's own source doesn't itself look like an (invalid,
# templated) SPDX tag to `reuse lint`'s line scanner or to this script's own
# "already done" check below.
SPDX_MARKER = "SPDX-" + "License-Identifier"
SPDX_LICENSE_EXPR = "AGPL-3.0-" + "or-later"


def _iter_candidate_files():
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        if any(part in rel for part in EXCLUDE_DIR_PARTS):
            continue
        if path.suffix in INCLUDE_EXTENSIONS or path.name in INCLUDE_BASENAMES:
            yield path


def add_spdx_to_file(path: Path) -> bool:
    """Insert SPDX tags after the Copyright line. Returns True if changed."""
    text = path.read_text(encoding="utf-8")
    if SPDX_MARKER in text:
        return False  # already done

    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        match = COPYRIGHT_RE.search(line)
        if not match:
            continue
        year = match.group(1)
        prefix = line[: match.start()]
        newline = "\n" if line.endswith("\n") else ""
        spdx_lines = [
            f"{prefix}SPDX-FileCopyrightText: {year} Christopher Abanilla "
            f"<christopher.abanilla@gmx.de>{newline}",
            f"{prefix}{SPDX_MARKER}: {SPDX_LICENSE_EXPR}{newline}",
        ]
        lines[i + 1 : i + 1] = spdx_lines
        path.write_text("".join(lines), encoding="utf-8")
        return True
    return False


def main() -> int:
    """Walk the repo and add SPDX tags to every already-headered file."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    changed = []
    skipped_no_copyright = []
    for path in sorted(_iter_candidate_files()):
        rel = path.relative_to(REPO_ROOT)
        if args.dry_run:
            text = path.read_text(encoding="utf-8")
            if SPDX_MARKER in text:
                continue
            if COPYRIGHT_RE.search(text):
                changed.append(rel)
            else:
                skipped_no_copyright.append(rel)
        else:
            if add_spdx_to_file(path):
                changed.append(rel)

    for rel in changed:
        print(f"{'would update' if args.dry_run else 'updated'}: {rel}")
    if args.dry_run and skipped_no_copyright:
        print(
            f"\n{len(skipped_no_copyright)} file(s) with no Copyright line "
            "(need a header added by hand first):"
        )
        for rel in skipped_no_copyright:
            print(f"  {rel}")

    print(f"\n{len(changed)} file(s) {'would be' if args.dry_run else ''} updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
