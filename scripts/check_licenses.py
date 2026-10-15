"""openDox - Medical transcription platform.

Copyright (C) 2025  S2A Open Technologies gGmbH
SPDX-FileCopyrightText: 2025 S2A Open Technologies gGmbH
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

Check every backend (pip-licenses) and frontend (license-checker-rseidelsohn)
dependency's declared license against an allowlist of AGPL-3.0-or-later
compatible licenses, and optionally regenerate THIRD_PARTY_NOTICES.md.

Manual-run tool, like ``safety check``/``npm audit`` elsewhere in this repo
(no CI pipeline exists to enforce it automatically — see docs/CONTRIBUTING.md).

Backend note: pip-licenses reports every package in the active venv, which
currently includes dev-only tooling (pytest, ruff, pip-licenses, reuse
itself) since pyproject.toml has no runtime/dev dependency-group split —
this mirrors the project's existing flat-dependency-list convention rather
than inventing a new one.

Usage:
    python scripts/check_licenses.py                  # print report, exit 1 on findings
    python scripts/check_licenses.py --write-notices   # also (re)write notices file
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_RAW_ALLOWED_LICENSES = {
    "mit",
    "mit license",
    "mit-0",
    "mit*",
    "bsd",
    "bsd license",
    "bsd-2-clause",
    "bsd-3-clause",
    "0bsd",
    "zlib",
    "zlib license",
    "apache",
    "apache-2.0",
    "apache software license",
    "apache license 2.0",
    "isc",
    "mpl-2.0",
    "mozilla public license 2.0",
    "mozilla public license 2.0 (mpl 2.0)",
    "psf-2.0",
    "python software foundation license",
    "lgpl",
    "lgpl-2.1",
    "lgpl-3.0",
    "gnu lesser general public license",
    "gnu lesser general public license v3 (lgplv3)",
    "gnu library or lesser general public license (lgpl)",
    "cc0-1.0",
    "unlicense",
    "public domain",
    "blueoak-1.0.0",
    "cc-by-3.0",
    "cc-by-4.0",
    "agpl-3.0",
    "agpl-3.0-or-later",
    "gnu affero general public license v3",
    "python-2.0",
}


def _normalize(s: str) -> str:
    """Lowercase and drop parens/whitespace noise for allowlist comparisons."""
    return " ".join(s.replace("(", " ").replace(")", " ").lower().split())


# Aliases as reported by pip-licenses (PyPI classifiers, often verbose) and
# license-checker-rseidelsohn (SPDX identifiers, from each package's
# package.json "license" field) for licenses compatible with distributing a
# combined/derivative work under AGPL-3.0-or-later: permissive licenses,
# weak-copyleft licenses that permit relicensing under AGPL for the combined
# work, and public-domain-equivalent dedications. Normalized once at import
# time so lookups and allowlist entries use the same paren/whitespace rules.
ALLOWED_LICENSES = {_normalize(s) for s in _RAW_ALLOWED_LICENSES}


def _license_ok(raw: str) -> bool:
    """True if every AND-clause of a (possibly compound) license string is allowed.

    Handles strings like "MPL-2.0 AND (Apache-2.0 OR MIT)" or
    "Apache Software License; MIT License" (pip-licenses' own separator for
    multi-licensed packages) by requiring every AND-clause to resolve, and
    any OR-clause to have at least one allowed alternative. Only the first
    line is considered — some packages (e.g. tiktoken) report the full
    embedded LICENSE file text instead of just the short name, with the
    actual short name on line 1.
    """
    if not raw or raw.strip().upper() == "UNKNOWN":
        return False
    first_line = raw.strip().splitlines()[0]
    for and_clause in first_line.replace(";", " AND ").split(" AND "):
        or_alternatives = [_normalize(c) for c in and_clause.split(" OR ") if c.strip()]
        if not any(alt in ALLOWED_LICENSES for alt in or_alternatives):
            return False
    return True


def get_backend_licenses() -> list[dict]:
    """Run pip-licenses in the active venv and return the parsed package list."""
    result = subprocess.run(
        [sys.executable, "-m", "piplicenses", "--format=json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [
        {"name": p["Name"], "version": p["Version"], "license": p["License"]}
        for p in json.loads(result.stdout)
    ]


def get_frontend_licenses() -> list[dict]:
    """Run license-checker-rseidelsohn and return the parsed package list.

    ``--production`` only: devDependencies (eslint, vitest, ...) are never
    part of the shipped frontend bundle, so they're outside the scope of a
    distribution license-compatibility check.
    """
    frontend_dir = REPO_ROOT / "frontend"
    own_pkg = json.loads((frontend_dir / "package.json").read_text())
    own_key = f"{own_pkg['name']}@{own_pkg['version']}"

    result = subprocess.run(
        ["npx", "license-checker-rseidelsohn", "--json", "--production"],
        cwd=frontend_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    packages = []
    for key, info in data.items():
        if key == own_key:
            continue  # the project's own package.json entry, not a dependency
        name, _, version = key.rpartition("@")
        licenses = info.get("licenses", "UNKNOWN")
        packages.append({"name": name, "version": version, "license": licenses})
    return packages


def check(packages: list[dict], ecosystem: str) -> list[dict]:
    """Return the subset of ``packages`` whose license isn't in the allowlist."""
    return [p for p in packages if not _license_ok(p["license"])]


def _license_cell(raw: str) -> str:
    """First line only, table-safe — some packages report embedded full LICENSE text."""
    first_line = raw.strip().splitlines()[0] if raw.strip() else "UNKNOWN"
    return first_line + ("…" if "\n" in raw.strip() else "")


_MIT_TEXT = [
    "Permission is hereby granted, free of charge, to any person obtaining a copy",
    'of this software and associated documentation files (the "Software"), to deal',
    "in the Software without restriction, including without limitation the rights",
    "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell",
    "copies of the Software, and to permit persons to whom the Software is",
    "furnished to do so, subject to the following conditions:",
    "",
    "The above copyright notice and this permission notice shall be included in all",
    "copies or substantial portions of the Software.",
    "",
    'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR',
    "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,",
    "FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE",
    "AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER",
    "LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,",
    "OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE",
    "SOFTWARE.",
]

# Files and code shipped inside the repository (not installed packages), so they
# never show up in the dependency lists above.
BUNDLED_NOTICES = [
    "## Bundled files and adapted code",
    "",
    "### Silero VAD model",
    "",
    "`backend/components/assets/silero_vad_v6.onnx` — voice activity detection model,",
    "https://github.com/snakers4/silero-vad, MIT License.",
    "Copyright (c) 2020-present Silero Team",
    "",
    *_MIT_TEXT,
    "",
    "### faster-whisper VAD code",
    "",
    "`backend/components/modules/silero_vad.py` adapts the speech-timestamp logic and",
    "the batched model call from `faster_whisper/vad.py`,",
    "https://github.com/SYSTRAN/faster-whisper, MIT License.",
    "Copyright (c) 2023 SYSTRAN",
    "",
    *_MIT_TEXT,
    "",
    "### Test audio",
    "",
    "`tests/fixtures/speech_pause_de.wav` — synthetic speech generated with Piper TTS",
    "(voice `de_DE-thorsten-medium`, trained on the CC0 Thorsten-Voice dataset).",
    "",
]


def write_third_party_notices(backend: list[dict], frontend: list[dict]) -> None:
    """Regenerate THIRD_PARTY_NOTICES.md from current dependency license data.

    Regenerated, not hand-maintained — same convention as
    scripts/bump_version.py for pyproject.toml's version.
    """
    lines = [
        "# Third-Party Notices",
        "",
        "openDox is licensed under the GNU Affero General Public License",
        "v3.0-or-later (see `LICENSE`). It depends on the third-party packages",
        "listed below, each under its own license. This file is generated by",
        "`python scripts/check_licenses.py --write-notices` — do not hand-edit.",
        "",
        f"## Backend (Python, {len(backend)} packages)",
        "",
        "| Package | Version | License |",
        "|---|---|---|",
    ]
    for p in sorted(backend, key=lambda p: p["name"].lower()):
        lines.append(
            f"| {p['name']} | {p['version']} | {_license_cell(p['license'])} |"
        )

    lines += [
        "",
        f"## Frontend (npm, {len(frontend)} packages)",
        "",
        "| Package | Version | License |",
        "|---|---|---|",
    ]
    for p in sorted(frontend, key=lambda p: p["name"].lower()):
        lines.append(
            f"| {p['name']} | {p['version']} | {_license_cell(p['license'])} |"
        )
    lines.append("")
    lines += BUNDLED_NOTICES

    (REPO_ROOT / "THIRD_PARTY_NOTICES.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def main() -> int:
    """Run both ecosystem license checks and print a report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-notices",
        action="store_true",
        help="Regenerate THIRD_PARTY_NOTICES.md from the current dependency set",
    )
    args = parser.parse_args()

    backend = get_backend_licenses()
    frontend = get_frontend_licenses()

    if args.write_notices:
        write_third_party_notices(backend, frontend)
        print(
            f"Wrote THIRD_PARTY_NOTICES.md ({len(backend)} backend + "
            f"{len(frontend)} frontend packages)"
        )

    flagged_backend = check(backend, "backend")
    flagged_frontend = check(frontend, "frontend")

    if not flagged_backend and not flagged_frontend:
        print(
            f"OK: {len(backend)} backend + {len(frontend)} frontend "
            "package licenses all recognized as AGPL-3.0-compatible."
        )
        return 0

    print(
        "Licenses needing manual review (not necessarily incompatible — "
        "just not on the allowlist):"
    )
    for p in flagged_backend:
        print(f"  [backend]  {p['name']} {p['version']}: {p['license']}")
    for p in flagged_frontend:
        print(f"  [frontend] {p['name']} {p['version']}: {p['license']}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
