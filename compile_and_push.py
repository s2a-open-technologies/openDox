"""openDox - Medical transcription platform
Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>

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

import os
import shutil
import subprocess

NODE_FOLDER = os.path.join(os.getcwd(), "frontend")
DIST_FOLDER = os.path.join(NODE_FOLDER, "dist")
FINAL_FOLDER = os.path.join(os.getcwd(), "app", "static")

# Enter frontend and compile

print("---BETRETE NODE FOLDER---")
os.chdir(NODE_FOLDER)
print(NODE_FOLDER)

print("---STARTE COMPILE VORGANG---")
try:
    subprocess.run(["node", "run", "build"], check=True)
except Exception as e:
    print(f"---COMPILE VORGANG ABGEBROCHEN---\n{e}")
print("---COMPILE VORGANG ABGESCHLOSSEN---")

print("---KOPIERE DATEIEN---")
try:
    if os.path.exists(FINAL_FOLDER):
        shutil.rmtree(FINAL_FOLDER)
    shutil.copytree(DIST_FOLDER, FINAL_FOLDER)
except Exception as e:
    print(f"---KOPIERVORGANG ABGEBROCHEN---\n{e}")
print("---KOPIERVOGANG ERFOLGREICH---")
