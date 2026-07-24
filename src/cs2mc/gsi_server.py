from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

PayloadHandler = Callable[[dict], None]
LogHandler = Callable[[str], None]


class GSIServer:
    def __init__(
        self,
        port: int,
        token: str,
        on_payload: PayloadHandler,
        on_log: LogHandler | None = None,
    ) -> None:
        self.port = port
        self.token = token
        self.on_payload = on_payload
        self.on_log = on_log or (lambda _: None)
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._server:
            return

        token = self.token
        on_payload = self.on_payload
        on_log = self.on_log

        class Handler(BaseHTTPRequestHandler):
            server_version = "CS2MC/0.1"

            def log_message(self, *_args) -> None:
                return

            def do_GET(self) -> None:
                if self.path == "/health":
                    body = b'{"ok":true}'
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self.send_response(404)
                self.end_headers()

            def do_POST(self) -> None:
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if length <= 0 or length > 2_000_000:
                        self.send_response(400)
                        self.end_headers()
                        return
                    raw = self.rfile.read(length)
                    payload = json.loads(raw.decode("utf-8"))
                    supplied = str((payload.get("auth") or {}).get("token") or "")
                    if token and supplied != token:
                        self.send_response(403)
                        self.end_headers()
                        return
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain")
                    self.end_headers()
                    self.wfile.write(b"OK")
                    on_payload(payload)
                except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
                    self.send_response(400)
                    self.end_headers()
                except (BrokenPipeError, ConnectionResetError):
                    return
                except Exception as exc:  # keep the local listener alive
                    on_log(f"GSI request error: {exc}")
                    try:
                        self.send_response(500)
                        self.end_headers()
                    except OSError:
                        pass

        self._server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        self.port = int(self._server.server_address[1])
        self._server.daemon_threads = True
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="CS2-GSI-Server",
            daemon=True,
        )
        self._thread.start()
        self.on_log(f"Listening for CS2 on 127.0.0.1:{self.port}")

    def stop(self) -> None:
        server = self._server
        if not server:
            return
        server.shutdown()
        server.server_close()
        self._server = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
