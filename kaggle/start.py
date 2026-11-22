# Kaggle "Mira Brain" script: always runs the newest brain from GitHub (blackadmen732-wq/mira, kaggle/brain.py).
import subprocess, sys, urllib.request
src = urllib.request.urlopen("https://raw.githubusercontent.com/blackadmen732-wq/mira/main/kaggle/brain.py", timeout=60).read()
open("/kaggle/working/brain.py", "wb").write(src)
sys.exit(subprocess.call([sys.executable, "-u", "/kaggle/working/brain.py"]))
