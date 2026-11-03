"""خادم خفيف بالمكتبة القياسية فقط (بديل عن FastAPI): نفس واجهة API ونفس ملفات الواجهة.

مفيد على Termux إن تعذّر تثبيت FastAPI/pydantic.  التشغيل:
    python server_lite.py            # المنفذ 8000
    PORT=9000 python server_lite.py
"""
import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

import api
import autorefresh

FRONTEND = Path(__file__).resolve().parent.parent / "docs"
MAX_BODY = 64 * 1024


class Handler(BaseHTTPRequestHandler):
    server_version = "SiiMatchMindLite/0.3"

    def log_message(self, fmt, *args):
        if os.environ.get("SMM_LOG"):
            super().log_message(fmt, *args)

    def _send(self, status, payload, ctype="application/json; charset=utf-8", extra=None):
        data = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _handle(self):
        u = urlparse(self.path)
        if u.path.startswith("/api/"):
            body = None
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                return self._send(413, {"error": {"code": "too_large", "params": {}}})
            if n:
                try:
                    body = json.loads(self.rfile.read(n).decode("utf-8"))
                except ValueError:
                    return self._send(400, {"error": {"code": "invalid_body", "params": {}}})
            hdrs = dict(self.headers)
            hdrs["x-smm-peer"] = self.client_address[0]
            status, obj = api.dispatch(self.command, u.path, dict(parse_qsl(u.query)), hdrs, body)
            return self._send(status, obj, extra={"Cache-Control": "no-store"})
        rel = "index.html" if u.path in ("", "/") else u.path.lstrip("/")
        f = (FRONTEND / rel).resolve()
        if FRONTEND.resolve() not in f.parents and f != FRONTEND.resolve() or not f.is_file():
            return self._send(404, b"Not found", "text/plain; charset=utf-8")
        ctype = mimetypes.guess_type(str(f))[0] or "application/octet-stream"
        if f.name in ("privacy.html", "terms.html") and os.environ.get("SMM_CONTACT_EMAIL"):      # بريد التواصل من متغير بيئة، فلا يُمحى بالتحديث
            body = f.read_bytes().replace(b"CONTACT_EMAIL", os.environ["SMM_CONTACT_EMAIL"].encode("utf-8"))
            return self._send(200, body, "text/html; charset=utf-8")
        if f.suffix == ".webmanifest":
            ctype = "application/manifest+json"
        self._send(200, f.read_bytes(), ctype + ("; charset=utf-8" if ctype.startswith(("text/", "application/json")) else ""))

    do_GET = do_POST = do_DELETE = do_HEAD = _handle


def serve(host="127.0.0.1", port=8000):
    srv = ThreadingHTTPServer((host, port), Handler)
    autorefresh.start()
    print(f"SiiMatchMind AI (lite) يعمل على http://{host}:{port}")
    srv.serve_forever()


if __name__ == "__main__":
    serve(os.environ.get("HOST", "127.0.0.1"), int(os.environ.get("PORT", "8000")))
