#!/usr/bin/env python3
"""Install only the small context server environment; never starts robot software."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv

root = Path(__file__).resolve().parents[1]
environment = root / ".junction-setup" / "context-mcp"
python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
requirements = root / "context_mcp" / "requirements.lock"
if not requirements.exists():
    requirements = root / "context_mcp" / "requirements.txt"
uv = shutil.which("uv")
if uv:
    env = {**os.environ, "UV_CACHE_DIR": str(root / ".junction-setup" / "uv-cache"), "UV_PYTHON_INSTALL_DIR": str(root / ".junction-setup" / "python-runtimes")}
    if not python.exists():
        subprocess.run([uv, "venv", "--python", "3.12", str(environment)], env=env, check=True)
    subprocess.run([uv, "pip", "install", "--python", str(python), "-r", str(requirements)], env=env, check=True)
else:
    if sys.version_info < (3, 11):
        raise SystemExit("Use Python 3.11+ (3.12 recommended), or install uv first.")
    if not python.exists():
        venv.EnvBuilder(with_pip=True).create(environment)
    subprocess.run([str(python), "-m", "pip", "install", "-r", str(requirements)], check=True)
subprocess.run([str(python), str(root / "context_mcp" / "server.py"), "--help"], check=True, stdout=subprocess.DEVNULL)
print("Context MCP installed. Start with:")
print(str(python) + " " + str(root / "context_mcp" / "server.py"))
