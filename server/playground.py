from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .manager import CubiMockManager

ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"
manager = CubiMockManager(ROOT)


def json_response(handler: BaseHTTPRequestHandler, status: int, body: dict[str, Any]) -> None:
    raw = json.dumps(body).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


class PlaygroundHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _serve_file(self, path: Path, content_type: str) -> None:
        raw = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self._serve_file(WEB_DIR / "index.html", "text/html; charset=utf-8")
            return
        if path == "/app.js":
            self._serve_file(WEB_DIR / "app.js", "application/javascript; charset=utf-8")
            return
        if path == "/style.css":
            self._serve_file(WEB_DIR / "style.css", "text/css; charset=utf-8")
            return

        if path == "/api/status":
            health = manager.get_mock_health()
            meta = health.get("process") or {}
            bind_host = str(meta.get("bind_host") or "127.0.0.1")
            port = int(meta.get("port") or 8791)
            json_response(
                self,
                200,
                {
                    "mock": health,
                    "env": manager.get_env_bundle(bind_host=bind_host, port=port),
                    "mcp_config": manager.get_mcp_config(),
                    "profiles": ["default", "returns", "repair", "wire-heavy"],
                },
            )
            return

        if path == "/api/mock/accounts":
            meta = (manager.get_mock_health().get("process") or {})
            bind_host = str(meta.get("bind_host") or "127.0.0.1")
            port = int(meta.get("port") or 8791)
            try:
                json_response(self, 200, manager.list_accounts(bind_host=bind_host, port=port))
            except Exception as exc:
                json_response(self, 500, {"error": str(exc)})
            return

        if path == "/api/mock/transactions":
            meta = (manager.get_mock_health().get("process") or {})
            bind_host = str(meta.get("bind_host") or "127.0.0.1")
            port = int(meta.get("port") or 8791)
            query = parse_qs(parsed.query)
            account_id = str((query.get("account_id") or [""])[0])
            limit = int((query.get("limit") or ["10"])[0])
            try:
                json_response(self, 200, manager.list_transactions(account_id=account_id, bind_host=bind_host, port=port, limit=limit))
            except Exception as exc:
                json_response(self, 500, {"error": str(exc)})
            return

        json_response(self, 404, {"error": "Not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        body = self._body()

        try:
            if path == "/api/mock/ensure":
                result = manager.ensure_mock_running(
                    bind_host=str(body.get("bind_host") or "127.0.0.1"),
                    port=int(body.get("port") or 8791),
                    profile=str(body.get("profile") or "default"),
                    reset=bool(body.get("reset") or False),
                )
                json_response(self, 200, result)
                return

            if path == "/api/mock/stop":
                json_response(self, 200, manager.stop_mock())
                return

            if path == "/api/mock/reset":
                json_response(self, 200, manager.reset_state(profile=str(body.get("profile") or "default")))
                return

            if path == "/api/mock/payments":
                meta = (manager.get_mock_health().get("process") or {})
                bind_host = str(meta.get("bind_host") or "127.0.0.1")
                port = int(meta.get("port") or 8791)
                result = manager.create_demo_payment(
                    rail=str(body.get("rail") or "WIRE"),
                    direction=str(body.get("direction") or "DEBIT"),
                    amount=str(body.get("amount") or "1500.00"),
                    source_payment_id=str(body.get("source_payment_id") or "DEMO-PAYMENT-1"),
                    client_reference=str(body.get("client_reference") or "CLIENT-DEMO-1"),
                    beneficiary_bank_routing=str(body.get("beneficiary_bank_routing") or "021000021"),
                    bind_host=bind_host,
                    port=port,
                )
                json_response(self, 200, result)
                return

            if path == "/api/mock/payments/poll":
                meta = (manager.get_mock_health().get("process") or {})
                bind_host = str(meta.get("bind_host") or "127.0.0.1")
                port = int(meta.get("port") or 8791)
                result = manager.poll_payment(
                    payment_id=str(body.get("payment_id") or ""),
                    rail=str(body.get("rail") or "WIRE"),
                    bind_host=bind_host,
                    port=port,
                )
                json_response(self, 200, result)
                return
        except Exception as exc:
            json_response(self, 500, {"error": str(exc)})
            return

        json_response(self, 404, {"error": "Not found"})


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Cubi MCP playground UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), PlaygroundHandler)
    print(f"Cubi MCP playground listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
