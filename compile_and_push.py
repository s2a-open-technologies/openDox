import os
import subprocess
import shutil

NODE_FOLDER = os.path.join(os.getcwd(), "frontend")
DIST_FOLDER = os.path.join(NODE_FOLDER, "dist")
FINAL_FOLDER = os.path.join(os.getcwd(), "app", "static")

# Enter frontend and compile

print("---BETRETE NODE FOLDER---")
os.chdir(NODE_FOLDER)
print(NODE_FOLDER)

print("---STARTE COMPILE VORGANG---")
try:
    subprocess.run(["/home/crizz/.nvm/versions/node/v22.18.0/bin/node", "run", "build"], check=True)
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
