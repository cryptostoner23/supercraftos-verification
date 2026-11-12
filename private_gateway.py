"""Single-operator HTTPS gateway. Expose this loopback port behind TLS, not the app."""
from __future__ import annotations
import hashlib
import hmac
import http.client
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import time
import threading
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
COOKIE = '__Host-supercraftos'
LOGIN = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SuperCraftOS · Sign in</title><style>body{color:#edf3fa;background:#07101b;font:16px/1.5 system-ui;max-width:500px;margin:15vh auto;padding:24px}input,button{font:inherit;padding:12px;border-radius:6px;border:1px solid #36516b;box-sizing:border-box}input{width:100%;background:#0d1927;color:white;margin:12px 0}button{background:#46dda0;color:#062719;cursor:pointer}#message{color:#ffb1a9}</style></head><body><h1>SuperCraftOS</h1><p>Open your private access link, or enter its access key.</p><form><label for="key">Access key</label><input id="key" type="password" required autocomplete="current-password"><button>Sign in</button></form><p id="message" role="alert"></p><script>const input=document.querySelector('#key');async function login(key){try{const r=await fetch('/auth/session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:key})});if(!r.ok)throw Error('Access key not accepted.');location.replace('/agents')}catch(e){document.querySelector('#message').textContent=e.message}}document.querySelector('form').onsubmit=e=>{e.preventDefault();login(input.value)};const token=location.hash.slice(1);if(token){history.replaceState(null,'',location.pathname);login(decodeURIComponent(token))}</script></body></html>'''


def load_access_key(path=ROOT/'data/access.key'):
    # A provisioned key (e.g. from the cloud deployment) takes precedence so the
    # same key can be baked into the iOS app build.
    env_key = os.getenv('SUPERCRAFTOS_ACCESS_KEY', '')
    if len(env_key) >= 32:
        return env_key
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        key = path.read_text().strip()
    else:
        key = secrets.token_urlsafe(32)
        with os.fdopen(fd, 'w') as stream: stream.write(key)
    if len(key) < 32:
        raise ValueError('access key must contain at least 32 characters')
    return key


class Gateway(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, *, key, origin, backend_port=8787):
        parsed = urlparse(origin)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.path not in {'', '/'} or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('SUPERCRAFTOS_PUBLIC_ORIGIN must be the public HTTPS origin')
        self.key, self.origin = key, origin.rstrip('/')
        self.backend_port = backend_port
        self.slots = threading.BoundedSemaphore(16)
        super().__init__(address, GatewayHandler)

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            try:
                request.sendall(b'HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            except OSError:
                pass
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()

    def session(self):
        payload = str(int(time.time()) + 7*86400) + '.' + secrets.token_hex(16)
        signature = hmac.new(self.key.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return payload + '.' + signature

    def valid_session(self, value):
        try:
            expiry, nonce, signature = value.split('.')
            payload = expiry + '.' + nonce
            expected = hmac.new(self.key.encode(), payload.encode(), hashlib.sha256).hexdigest()
            return int(expiry) > time.time() and hmac.compare_digest(signature, expected)
        except (ValueError, AttributeError):
            return False


class GatewayHandler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def setup(self):
        super().setup(); self.connection.settimeout(20)
    def respond(self, code, body, content_type='application/json', cookie=None):
        if not isinstance(body, bytes): body = json.dumps(body).encode()
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        if cookie: self.send_header('Set-Cookie', cookie)
        self.end_headers(); self.wfile.write(body)
    def authenticated(self):
        if self.valid_bearer():
            return True
        try:
            cookie = SimpleCookie(self.headers.get('Cookie', ''))
            return COOKIE in cookie and self.server.valid_session(cookie[COOKIE].value)
        except Exception:
            return False
    def valid_bearer(self):
        authorization = self.headers.get('Authorization', '')
        return authorization.startswith('Bearer ') and secrets.compare_digest(authorization[7:], self.server.key)
    def dispatch(self):
        if self.headers.get('Host') != urlparse(self.server.origin).netloc:
            return self.respond(403, {'error': 'invalid_host'})
        if self.headers.get('Upgrade'):
            return self.respond(401 if not self.authenticated() else 400, {'error': 'websocket_not_supported'})
        try:
            length = int(self.headers.get('Content-Length', 0))
            if not 0 <= length <= 65536 or self.headers.get('Transfer-Encoding'):
                raise ValueError()
        except ValueError:
            return self.respond(400, {'error': 'invalid_request'})
        path = urlparse(self.path).path
        if self.command == 'POST':
            # Native clients use the explicit bearer credential. Browser cookies require exact Origin.
            origin = self.headers.get('Origin')
            if origin != self.server.origin and not (origin is None and self.valid_bearer()):
                return self.respond(403, {'error': 'invalid_origin'})
        if path == '/auth/session' and self.command == 'POST':
            body = self.rfile.read(length) if length else None
            try: value = json.loads(body or b'{}')
            except ValueError: return self.respond(400, {'error': 'invalid_request'})
            token = value.get('token') if isinstance(value, dict) else None
            if not isinstance(token, str) or not secrets.compare_digest(token, self.server.key):
                return self.respond(401, {'error': 'invalid_credentials'})
            cookie = f'{COOKIE}={self.server.session()}; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=604800'
            return self.respond(200, {'authenticated': True}, cookie=cookie)
        if not self.authenticated():
            if self.command == 'GET' and path in {'/', '/agents'}:
                return self.respond(200, LOGIN.encode(), 'text/html; charset=utf-8')
            return self.respond(401, {'error': 'authentication_required'})
        if self.command not in {'GET', 'POST'}:
            return self.respond(405, {'error': 'method_not_allowed'})
        body = self.rfile.read(length) if length else None
        # The authenticated gateway is the only proxy permitted to rewrite the loopback boundary.
        connection = http.client.HTTPConnection('127.0.0.1', self.server.backend_port, timeout=190)
        headers = {'Host': f'127.0.0.1:{self.server.backend_port}'}
        for name in ('Content-Type', 'X-SuperCraftOS-Token', 'Idempotency-Key'):
            if self.headers.get(name): headers[name] = self.headers[name]
        if self.command == 'POST': headers['Origin'] = f'http://127.0.0.1:{self.server.backend_port}'
        try:
            connection.request(self.command, self.path, body, headers)
            response = connection.getresponse()
            data = response.read(50_000_001)
            if len(data) > 50_000_000:
                return self.respond(502, {'error': 'response_too_large'})
            self.send_response(response.status)
            for name, value in response.getheaders():
                if name.lower() in {'content-type', 'content-disposition', 'cache-control'}:
                    self.send_header(name, value)
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers(); self.wfile.write(data)
        except (OSError, http.client.HTTPException):
            return self.respond(502, {'error': 'backend_unavailable'})
        finally:
            connection.close()
    do_GET = dispatch
    do_POST = dispatch
    do_PUT = dispatch
    do_DELETE = dispatch


def main():
    from runtime_env import load_environment
    load_environment()
    origin = os.environ['SUPERCRAFTOS_PUBLIC_ORIGIN']
    server = Gateway(('127.0.0.1', int(os.getenv('SUPERCRAFTOS_GATEWAY_PORT') or 8790)),
                     key=load_access_key(), origin=origin,
                     backend_port=int(os.getenv('SUPERCRAFTOS_BACKEND_PORT') or 8787))
    try: server.serve_forever()
    finally: server.server_close()


if __name__ == '__main__': main()
