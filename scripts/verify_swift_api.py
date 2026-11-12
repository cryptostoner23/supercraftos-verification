"""Test the actual HTTP status entrypoint with the compiled Swift CLI decoder."""
import json
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from supercraftos_cli import BoundedHTTPServer, Handler

server = BoundedHTTPServer(('127.0.0.1', 0), Handler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    with urllib.request.urlopen(f'http://127.0.0.1:{server.server_port}/api/status', timeout=5) as response:
        status = response.read().decode()
    binary = ROOT / 'swift-verification/.build/debug/supercraftos-check'
    result = subprocess.run([str(binary)], input=json.dumps({'operation': 'status', 'input': status}), capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise RuntimeError('Swift CLI could not decode actual API response')
    print(json.dumps({'entrypoint': '/api/status', 'swift_decoder': json.loads(result.stdout), 'status': 'passed'}))
finally:
    server.shutdown(); server.server_close(); thread.join(timeout=3)
