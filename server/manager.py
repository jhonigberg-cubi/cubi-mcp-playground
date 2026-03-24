from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .mock_cubi_server import default_state


class CubiMockManager:
    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = (root_dir or Path(__file__).resolve().parents[1]).resolve()
        self.runtime_dir = self.root_dir / ".runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.runtime_dir / "mock_cubi_state.json"
        self.pid_path = self.runtime_dir / "mock_cubi_process.json"
        self.mock_script = self.root_dir / "server" / "mock_cubi_server.py"

    def _write_process_meta(self, meta: dict[str, Any]) -> None:
        self.pid_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    def _read_process_meta(self) -> dict[str, Any] | None:
        if not self.pid_path.exists():
            return None
        return json.loads(self.pid_path.read_text(encoding="utf-8"))

    def _clear_process_meta(self) -> None:
        if self.pid_path.exists():
            self.pid_path.unlink()

    def _base_url(self, bind_host: str, port: int) -> str:
        return f"http://{bind_host}:{port}"

    def _request_json(self, method: str, url: str, body: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
        data = None
        request_headers = dict(headers or {})
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        req = Request(url, data=data, method=method, headers=request_headers)
        with urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    def _health(self, bind_host: str, port: int) -> dict[str, Any] | None:
        try:
            return self._request_json("GET", f"{self._base_url(bind_host, port)}/health")
        except (URLError, HTTPError, TimeoutError, OSError, json.JSONDecodeError):
            return None

    def _wait_for_health(self, bind_host: str, port: int, timeout_seconds: float = 8.0) -> dict[str, Any]:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            health = self._health(bind_host, port)
            if health and health.get("status") == "ok":
                return health
            time.sleep(0.25)
        raise RuntimeError(f"Mock endpoint failed to become healthy on {bind_host}:{port}.")

    def reset_state(self, profile: str = "default") -> dict[str, Any]:
        self.stop_mock()
        self.state_path.write_text(json.dumps(default_state(profile), indent=2), encoding="utf-8")
        return {
            "ok": True,
            "profile": profile,
            "state_file": str(self.state_path),
            "message": "State reset. Start the mock to use the new profile.",
        }

    def ensure_mock_running(self, bind_host: str = "127.0.0.1", port: int = 8791, profile: str = "default", reset: bool = False) -> dict[str, Any]:
        current = self._health(bind_host, port)
        if current and not reset:
            return {
                "ok": True,
                "started": False,
                "base_url": self._base_url(bind_host, port),
                "health": current,
                "env": self.get_env_bundle(bind_host, port),
                "mcp_config": self.get_mcp_config(),
            }

        if reset or not self.state_path.exists():
            self.state_path.write_text(json.dumps(default_state(profile), indent=2), encoding="utf-8")
        else:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
            state["profile"] = profile
            self.state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

        self.stop_mock()
        process = subprocess.Popen(
            [sys.executable, str(self.mock_script), "--host", bind_host, "--port", str(port), "--state-file", str(self.state_path)],
            cwd=str(self.root_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._write_process_meta(
            {
                "pid": process.pid,
                "bind_host": bind_host,
                "port": port,
                "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "profile": profile,
            }
        )
        health = self._wait_for_health(bind_host, port)
        return {
            "ok": True,
            "started": True,
            "pid": process.pid,
            "base_url": self._base_url(bind_host, port),
            "health": health,
            "env": self.get_env_bundle(bind_host, port),
            "mcp_config": self.get_mcp_config(),
        }

    def stop_mock(self) -> dict[str, Any]:
        meta = self._read_process_meta()
        if not meta:
            return {"ok": True, "stopped": False, "message": "Mock was not running."}

        pid = int(meta.get("pid") or 0)
        if pid > 0:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False, capture_output=True)
        self._clear_process_meta()
        return {"ok": True, "stopped": True, "pid": pid}

    def get_env_bundle(self, bind_host: str = "127.0.0.1", port: int = 8791) -> dict[str, Any]:
        base_url = self._base_url(bind_host, port)
        env = {
            "CUBI_MODE": "real",
            "CUBI_BASE_URL": base_url,
            "CUBI_TOKEN": "",
            "CUBI_TOKEN_URL": f"{base_url}/security/v1/oauth2/token",
            "CUBI_CLIENT_ID": "mock-client",
            "CUBI_CLIENT_SECRET": "mock-secret",
            "CUBI_SCOPE": "",
            "CUBI_AUDIENCE": "",
            "CUBI_CREATE_ACH_PATH": "",
            "CUBI_CREATE_ACH_DEBIT_PATH": "/ach/v1/outgoing/debit",
            "CUBI_CREATE_ACH_CREDIT_PATH": "/ach/v1/outgoing/credit",
            "CUBI_CREATE_WIRE_PATH": "/wires/v1/outgoing",
            "CUBI_STATUS_PATH_TEMPLATE": "",
            "CUBI_STATUS_ACH_PATH_TEMPLATE": "/ach/v1/outgoing/{payment_id}",
            "CUBI_STATUS_WIRE_PATH_TEMPLATE": "/wires/v1/outgoing/{payment_id}",
            "CUBI_ACCOUNTS_PATH": "/accounts/v1/",
            "CUBI_TRANSACTIONS_PATH_TEMPLATE": "/accounts/v1/{account_id}/transactions",
        }
        text = "\n".join(f"{key}={value}" for key, value in env.items())
        return {"base_url": base_url, "env": env, "dotenv": text}

    def get_mcp_config(self) -> dict[str, Any]:
        python_path = self.root_dir / ".venv" / "Scripts" / "python.exe"
        command = str(python_path if python_path.exists() else sys.executable)
        return {
            "mcpServers": {
                "cubi-mock-playground": {
                    "command": command,
                    "args": ["-m", "server.mcp_server"],
                    "cwd": str(self.root_dir),
                }
            }
        }

    def get_mock_health(self) -> dict[str, Any]:
        meta = self._read_process_meta()
        if not meta:
            return {"running": False, "health": None}
        bind_host = str(meta.get("bind_host") or "127.0.0.1")
        port = int(meta.get("port") or 8791)
        return {
            "running": True,
            "process": meta,
            "health": self._health(bind_host, port),
        }

    def _auth_headers(self, bind_host: str, port: int) -> dict[str, str]:
        token = self._request_json(
            "POST",
            f"{self._base_url(bind_host, port)}/security/v1/oauth2/token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        return {"Authorization": f"Bearer {token['access_token']}"}

    def list_accounts(self, bind_host: str = "127.0.0.1", port: int = 8791) -> dict[str, Any]:
        headers = self._auth_headers(bind_host, port)
        return self._request_json("GET", f"{self._base_url(bind_host, port)}/accounts/v1/", headers=headers)

    def list_transactions(self, account_id: str, bind_host: str = "127.0.0.1", port: int = 8791, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        headers = self._auth_headers(bind_host, port)
        query = urlencode({"limit": limit, "offset": offset})
        return self._request_json("GET", f"{self._base_url(bind_host, port)}/accounts/v1/{account_id}/transactions?{query}", headers=headers)

    def create_demo_payment(
        self,
        rail: str,
        direction: str,
        amount: str,
        source_payment_id: str,
        client_reference: str,
        bind_host: str = "127.0.0.1",
        port: int = 8791,
        beneficiary_bank_routing: str = "021000021",
    ) -> dict[str, Any]:
        headers = self._auth_headers(bind_host, port)
        payload = {
            "sourcePaymentId": source_payment_id,
            "clientReference": client_reference,
            "paymentType": rail,
            "direction": direction,
            "amount": amount,
            "beneficiaryBankRouting": beneficiary_bank_routing,
        }
        if rail.upper() == "WIRE":
            path = "/wires/v1/outgoing"
        elif direction.upper() == "CREDIT":
            path = "/ach/v1/outgoing/credit"
        else:
            path = "/ach/v1/outgoing/debit"
        return self._request_json("POST", f"{self._base_url(bind_host, port)}{path}", body=payload, headers=headers)

    def poll_payment(self, payment_id: str, rail: str, bind_host: str = "127.0.0.1", port: int = 8791) -> dict[str, Any]:
        headers = self._auth_headers(bind_host, port)
        path = "/wires/v1/outgoing/" if rail.upper() == "WIRE" else "/ach/v1/outgoing/"
        return self._request_json("GET", f"{self._base_url(bind_host, port)}{path}{payment_id}", headers=headers)
