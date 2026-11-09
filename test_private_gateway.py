import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socket
from pathlib import Path
import tempfile
import threading
import unittest

from private_gateway import Gateway, load_access_key, COOKIE


class Backend(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def do_GET(self):
        body = json.dumps({'path': self.path, 'host': self.headers['Host']}).encode()
        self.send_response(200); self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    do_POST = do_GET


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.backend = ThreadingHTTPServer(('127.0.0.1',0), Backend)
        self.gateway = Gateway(('127.0.0.1',0), key='fixture-'*8, origin='https://private.example', backend_port=self.backend.server_port)
        self.threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in (self.backend,self.gateway)]
        for thread in self.threads: thread.start()
        self.addCleanup(self.close)
    def close(self):
        for server in (self.gateway,self.backend): server.shutdown(); server.server_close()
        for thread in self.threads: thread.join(2)
    def request(self, path='/', method='GET', body=None, headers=None):
        client = http.client.HTTPConnection('127.0.0.1',self.gateway.server_port)
        client.request(method,path,json.dumps(body) if body is not None else None,{'Host':'private.example',**(headers or {})})
        response=client.getresponse(); value=response.read(); fields=dict(response.getheaders()); client.close()
        return response.status,value,fields
    def login(self):
        code,body,headers=self.request('/auth/session','POST',{'token':self.gateway.key},{'Origin':'https://private.example'})
        self.assertEqual(code,200)
        self.assertIn('HttpOnly',headers['Set-Cookie']);self.assertIn('Secure',headers['Set-Cookie'])
        return headers['Set-Cookie'].split(';')[0]
    def test_anonymous_api_and_websocket_are_denied(self):
        self.assertEqual(self.request('/api/status')[0],401)
        self.assertEqual(self.request('/api/status',headers={'Upgrade':'websocket'})[0],401)
        code,body,_=self.request()
        self.assertEqual(code,200);self.assertNotIn(self.gateway.key.encode(),body)
    def test_invalid_key_origin_and_host_are_rejected(self):
        self.assertEqual(self.request('/auth/session','POST',{'token':'wrong'},{'Origin':'https://private.example'})[0],401)
        self.assertEqual(self.request('/auth/session','POST',{'token':self.gateway.key},{'Origin':'https://evil.example'})[0],403)
        self.assertEqual(self.request(headers={'Host':'evil.example'})[0],403)
    def test_reusable_link_auth_and_authenticated_forwarding(self):
        cookie=self.login();self.login()
        code,body,_=self.request('/api/status',headers={'Cookie':cookie})
        self.assertEqual(code,200);self.assertEqual(json.loads(body)['host'],f'127.0.0.1:{self.backend.server_port}')
        self.assertEqual(self.request('/api/jobs','POST',{}, {'Cookie':cookie,'Origin':'https://evil.example'})[0],403)
        self.assertEqual(self.request('/api/jobs','POST',{}, {'Cookie':cookie,'Origin':'https://private.example'})[0],200)
        self.assertEqual(self.request('/api/jobs','POST',{}, {'Cookie':cookie,'Authorization':'Bearer wrong'})[0],403)
        self.assertEqual(self.request('/api/jobs','POST',{}, {'Authorization':'Bearer '+self.gateway.key})[0],200)
    def test_key_and_sessions_survive_restart(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'access.key'; first=load_access_key(path); second=load_access_key(path)
            self.assertEqual(first,second);self.assertEqual(path.stat().st_mode&0o777,0o600)
        session=self.gateway.session()
        other=Gateway(('127.0.0.1',0),key=self.gateway.key,origin='https://private.example')
        try:self.assertTrue(other.valid_session(session));self.assertFalse(other.valid_session(session+'x'))
        finally:other.server_close()

    def test_handler_capacity_is_bounded(self):
        for _ in range(16):
            self.assertTrue(self.gateway.slots.acquire(blocking=False))
        try:
            self.assertEqual(self.request('/api/status')[0], 503)
        finally:
            for _ in range(16): self.gateway.slots.release()
        self.assertEqual(self.request('/api/status')[0], 401)

    def test_unauthorized_body_is_not_read(self):
        with socket.create_connection(self.gateway.server_address, timeout=2) as client:
            client.sendall(b'POST /api/jobs HTTP/1.1\r\nHost: private.example\r\nOrigin: https://private.example\r\nContent-Length: 60000\r\n\r\n')
            self.assertIn(b'401', client.recv(4096).split(b'\r\n', 1)[0])


if __name__=='__main__':unittest.main()
