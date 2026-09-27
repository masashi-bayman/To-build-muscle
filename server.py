#!/usr/bin/env python3
"""筋トレ記録 API（標準ライブラリのみ）
GET  /api/days            -> {"YYYY-MM-DD": {...}, ...}
PUT  /api/days/YYYY-MM-DD -> その日の記録を上書き保存
nginx から 127.0.0.1:8765 にリバースプロキシして使う想定。
"""
import json, os, re, sqlite3, threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DB_PATH = os.environ.get("TL_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "training.db"))
HOST = os.environ.get("TL_HOST", "127.0.0.1")
PORT = int(os.environ.get("TL_PORT", "8765"))
MAX_BODY = 64 * 1024
DATE_RE = re.compile(r"^/api/days/(\d{4}-\d{2}-\d{2})$")
lock = threading.Lock()


def db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("CREATE TABLE IF NOT EXISTS days (date TEXT PRIMARY KEY, body TEXT NOT NULL, updated_at TEXT NOT NULL)")
    return con


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj=None):
        data = json.dumps(obj if obj is not None else {}, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.split("?")[0] != "/api/days":
            return self._send(404, {"error": "not found"})
        with lock, db() as con:
            rows = con.execute("SELECT date, body FROM days ORDER BY date").fetchall()
        self._send(200, {d: json.loads(b) for d, b in rows})

    def do_PUT(self):
        m = DATE_RE.match(self.path)
        if not m:
            return self._send(404, {"error": "not found"})
        date = m.group(1)
        try:
            datetime.strptime(date, "%Y-%m-%d")
            n = int(self.headers.get("Content-Length", "0"))
            if n <= 0 or n > MAX_BODY:
                return self._send(413, {"error": "body size"})
            body = json.loads(self.rfile.read(n))
            if not isinstance(body, dict):
                raise ValueError
        except (ValueError, json.JSONDecodeError):
            return self._send(400, {"error": "bad request"})
        with lock, db() as con:
            con.execute(
                "INSERT INTO days(date, body, updated_at) VALUES(?,?,?) "
                "ON CONFLICT(date) DO UPDATE SET body=excluded.body, updated_at=excluded.updated_at",
                (date, json.dumps(body, ensure_ascii=False), datetime.now().isoformat(timespec="seconds")),
            )
        self._send(200, {"ok": True})

    def log_message(self, fmt, *args):
        pass  # journald を汚さない


if __name__ == "__main__":
    db().close()
    print(f"listening on {HOST}:{PORT}  db={DB_PATH}", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
