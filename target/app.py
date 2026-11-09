import os
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROLE = os.environ["ROLE"]


def get(url, timeout=None):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def handle():
    if ROLE == "gateway":
        get("http://auth:8000/")
        for attempt in range(2):
            try:
                return get("http://catalog:8000/", timeout=1)
            except Exception:
                if attempt:
                    raise
    if ROLE == "catalog":
        try:
            return get("http://cache:8000/", timeout=0.5)
        except Exception:
            time.sleep(0.8)
            return b"catalog-from-db"
    return ROLE.encode()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            body, code = handle(), 200
        except Exception as e:
            body, code = str(e).encode(), 500
        self.send_response(code)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
