"""openDox - Medical transcription platform
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
"""

# Bump the single canonical app version across pyproject.toml and the
# frontend package, keeping both in sync.
#
# Usage:
#     python scripts/bump_version.py --current       # print current version
#     python scripts/bump_version.py patch|minor|major
#     python scripts/bump_version.py 1.2.3            # explicit version
#     python scripts/bump_version.py patch --commit   # also git add+commit+tag

import argparse
import re
import subprocess
import sys
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = PROJECT_ROOT / "pyproject.toml"
PACKAGE_JSON = PROJECT_ROOT / "frontend" / "package.json"

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def read_current_version() -> str:
    """Read the current app version from pyproject.toml.

    Returns:
        The current version string, e.g. "0.1.0".
    """
    with open(PYPROJECT, "rb") as f:
        return tomllib.load(f)["project"]["version"]


def compute_new_version(current: str, target: str) -> str:
    """Compute the new version from a bump component or explicit value.

    Args:
        current: Current version string, e.g. "0.1.0".
        target: "major", "minor", "patch", or an explicit "X.Y.Z" string.

    Returns:
        The new version string.

    Raises:
        ValueError: If target is neither a known bump component nor a
            valid "X.Y.Z" version string.
    """
    if VERSION_RE.match(target):
        return target

    major, minor, patch = (int(part) for part in current.split("."))
    if target == "major":
        return f"{major + 1}.0.0"
    if target == "minor":
        return f"{major}.{minor + 1}.0"
    if target == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"Invalid bump target: {target!r}")


def write_pyproject_version(new_version: str) -> None:
    """Replace the version line in pyproject.toml in place."""
    text = PYPROJECT.read_text(encoding="utf-8")
    updated = re.sub(
        r'^version = ".*"$',
        f'version = "{new_version}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    PYPROJECT.write_text(updated, encoding="utf-8")


def write_package_json_version(new_version: str) -> None:
    """Replace the top-level version field in frontend/package.json in place."""
    text = PACKAGE_JSON.read_text(encoding="utf-8")
    updated = re.sub(
        r'^(\s*)"version": ".*",$',
        rf'\1"version": "{new_version}",',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    PACKAGE_JSON.write_text(updated, encoding="utf-8")


def resync_package_lock() -> None:
    """Resync package-lock.json's embedded version fields via npm."""
    subprocess.run(
        ["npm", "install", "--package-lock-only"],
        cwd=PROJECT_ROOT / "frontend",
        check=True,
    )


def commit_and_tag(new_version: str) -> None:
    """Commit the version bump and create a git tag."""
    files = [
        str(PYPROJECT),
        str(PACKAGE_JSON),
        str(PROJECT_ROOT / "frontend" / "package-lock.json"),
    ]
    subprocess.run(["git", "add", *files], cwd=PROJECT_ROOT, check=True)
    subprocess.run(
        ["git", "commit", "-m", f"chore: bump version to v{new_version}"],
        cwd=PROJECT_ROOT,
        check=True,
    )
    subprocess.run(["git", "tag", f"v{new_version}"], cwd=PROJECT_ROOT, check=True)


def main() -> None:
    """Parse CLI arguments and bump the app version accordingly."""
    parser = argparse.ArgumentParser(
        description="Bump the app version across pyproject.toml and "
        "frontend/package.json."
    )
    parser.add_argument(
        "target",
        nargs="?",
        help='"major", "minor", "patch", or an explicit "X.Y.Z" version',
    )
    parser.add_argument(
        "--current", action="store_true", help="print current version and exit"
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="also git add+commit+tag the bumped files",
    )
    args = parser.parse_args()

    current = read_current_version()

    if args.current:
        print(current)
        return

    if not args.target:
        parser.error("target is required unless --current is given")

    new_version = compute_new_version(current, args.target)

    write_pyproject_version(new_version)
    write_package_json_version(new_version)
    resync_package_lock()

    if args.commit:
        commit_and_tag(new_version)

    print(f"{current} -> {new_version}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, subprocess.CalledProcessError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
