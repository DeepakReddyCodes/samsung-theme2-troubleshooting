import subprocess
try:
    subprocess.check_call(["git", "fetch", "https://github.com/DeepakReddyCodes/samsung-theme2-troubleshooting.git", "main"])
except Exception as e:
    print(e)
