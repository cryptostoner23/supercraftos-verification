"""Bounded local stress checks through HTTP and stdio entrypoints; no paid APIs."""
import concurrent.futures
import http.client
import json
import resource
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from supercraftos_cli import BoundedHTTPServer, Handler


def read_entrypoint(server):
    def read(index):
        begin = time.perf_counter()
        client = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
        paths = ['status', 'tools', 'integrations', 'registrations', 'workflows']
        client.request('GET', '/api/' + paths[index % len(paths)])
        response = client.getresponse()
        value = json.loads(response.read())
        client.close()
        if response.status != 200 or not isinstance(value, dict): raise RuntimeError('Invalid HTTP response')
        return (time.perf_counter() - begin) * 1000
    return read


def main():
    server = BoundedHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            latencies = sorted(pool.map(read_entrypoint(server), range(400)))
        requests = [{'jsonrpc': '2.0', 'id': i, 'method': 'tools/list'} for i in range(200)]
        data = '\n'.join(json.dumps(request) for request in requests) + '\n{invalid\n'
        process = subprocess.run([sys.executable, str(ROOT / 'main.py'), 'mcp'], input=data, text=True, capture_output=True, timeout=30, cwd=ROOT)
        responses = [json.loads(line) for line in process.stdout.splitlines()]
        if process.returncode or len(responses) != 201: raise RuntimeError('MCP stdio stress failed')
        if responses[-1].get('error', {}).get('code') != -32700: raise RuntimeError('MCP malformed input was not rejected')
        report = {'http': {'requests': len(latencies), 'concurrency': 8, 'successes': 400,
                           'p50_ms': round(statistics.median(latencies), 2), 'p95_ms': round(latencies[int(len(latencies) * .95)], 2)},
                  'mcp': {'catalog_requests': 200, 'malformed_json_rejected': True},
                  'harness_peak_rss_mb': round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2),
                  'scope': 'Local HTTP read endpoints and MCP discovery/parse errors; no live agent generation or third-party calls'}
        print(json.dumps(report, indent=2))
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=3)


if __name__ == '__main__':
    main()
