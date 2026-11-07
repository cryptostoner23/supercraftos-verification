#!/usr/bin/env python3
"""Load server-side environment before Claude expands project MCP headers."""
import os
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from runtime_env import ROOT,load_environment
load_environment()
command=shutil.which('claude')
if not command:
    raise SystemExit('Claude Code CLI is not installed; .mcp.json is configured for a compatible client.')
os.chdir(ROOT)
os.execvpe(command,[command,*sys.argv[1:]],dict(os.environ))
