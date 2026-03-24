from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def as_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


def seed_int(value: str) -> int:
    return int(hashlib.sha1(value.encode("utf-8")).hexdigest()[:8], 16)


def make_accounts(profile: str = "default") -> list[dict[str, Any]]:
    base = [
        ("acct-operating-001", "Operating Account", "5169268", "Single"),
        ("acct-payments-002", "Payments Clearing", "2301881", "Dual"),
        ("acct-wire-003", "Wire Settlement", "9001455", "Dual"),
    ]
    if profile == "wire-heavy":
        base[2] = ("acct-wire-003", "Wire Command Center", "9001455", "Dual")

    accounts: list[dict[str, Any]] = []
    for idx, (acct_id, name, acct_no, control_type) in enumerate(base, start=1):
        bal = Decimal("150000.00") * idx + Decimal("86465.31")
        accounts.append(
            {
                "id": acct_id,
                "name": name,
                "accountNumber": acct_no,
                "isSearchable": True,
                "isFrozen": False,
                "controlType": control_type,
                "availableBalance": float(bal),
                "balance": float(bal),
                "additionalBalances": {
                    "relatedAvailableBalance": 0.0,
                    "totalAccessibleBalance": float(bal),
                },
            }
        )
    return accounts


def make_transactions(account_id: str, profile: str = "default", count: int = 36) -> list[dict[str, Any]]:
    descriptions = [
        "Supplier disbursement",
        "Incoming RTP",
        "Treasury transfer",
        "Client settlement",
        "Ops fee reversal",
        "Payroll funding",
    ]
    code_map = [
        ("167", "INCOMING RTP", "C"),
        ("195", "ACH DEBIT", "D"),
        ("142", "WIRE CREDIT", "C"),
        ("399", "TRANSFER", "D"),
    ]
    if profile == "wire-heavy":
        code_map = [
            ("142", "WIRE CREDIT", "C"),
            ("142", "WIRE CREDIT", "C"),
            ("195", "ACH DEBIT", "D"),
            ("399", "TRANSFER", "D"),
        ]
    elif profile == "returns":
        code_map = [
            ("195", "ACH DEBIT", "D"),
            ("195", "ACH DEBIT", "D"),
            ("167", "INCOMING RTP", "C"),
            ("399", "TRANSFER", "D"),
        ]

    now = datetime.now(UTC)
    items: list[dict[str, Any]] = []
    for i in range(count):
        seed = seed_int(f"{profile}:{account_id}:{i}")
        code, desc, direction = code_map[seed % len(code_map)]
        amount = Decimal((seed % 90000) / 100 + 10).quantize(Decimal("0.01"))
        control = f"{(seed % 10**15):015d}"
        posting = (now - timedelta(hours=i * 6)).replace(microsecond=0).isoformat()
        items.append(
            {
                "description": f"{descriptions[seed % len(descriptions)]} - REF# {seed % 2000000}",
                "transactionCode": code,
                "transactionCodeDescription": desc,
                "postingDate": posting,
                "amount": float(amount),
                "serialNumber": control,
                "controlNumber": control,
                "confirmationNumber": control,
                "transactionType": direction,
                "status": "POSTED",
            }
        )
    return items


def default_state(profile: str = "default") -> dict[str, Any]:
    accounts = make_accounts(profile)
    return {
        "profile": profile,
        "accounts": accounts,
        "transactions": {acct["id"]: make_transactions(acct["id"], profile=profile) for acct in accounts},
        "payments": {},
        "token": "mock-access-token",
    }


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.state = self._load()

    def _load(self) -> dict[str, Any]:
        if self.path.exists():
            return json.loads(self.path.read_text(encoding="utf-8"))
        state = default_state()
        self.save(state)
        return state

    def save(self, state: dict[str, Any] | None = None) -> None:
        if state is not None:
            self.state = state
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    def create_payment(self, payload: dict[str, Any], rail: str, direction: str) -> tuple[int, dict[str, Any]]:
        source_id = str(payload.get("sourcePaymentId") or payload.get("clientReference") or now_iso())
        amount = as_decimal(payload.get("amount"))
        seed = seed_int(f"{rail}:{direction}:{source_id}:{amount}:{self.state.get('profile', 'default')}")
        payment_id = f"MOCK-{rail}-{seed:08X}"
        profile = str(self.state.get("profile") or "default")
        wire_missing = rail == "WIRE" and not payload.get("beneficiaryBankRouting")
        repair_threshold = Decimal("50000.00") if profile == "repair" else Decimal("2500000.00")
        repair_needed = amount > repair_threshold
        status = "ACCEPTED"
        code = "ACCEPTED"
        reason = "Accepted by mock provider."
        http_status = 202
        imad = None

        if wire_missing:
            status = "REJECTED"
            code = "WIRE_BAD_DATA"
            reason = "Missing beneficiary bank routing."
            http_status = 422
        elif repair_needed:
            status = "REPAIR_REQUIRED"
            code = "AMOUNT_REVIEW"
            reason = "Amount exceeds straight-through threshold."

        if rail == "WIRE" and status != "REJECTED":
            imad = f"IMAD{datetime.now(UTC).strftime('%Y%m%d')}{seed % 100000:05d}"

        payment = {
            "paymentId": payment_id,
            "status": status,
            "code": code,
            "reason": reason,
            "imad": imad,
            "amount": str(amount),
            "transmittedAmount": str(amount),
            "rail": rail,
            "direction": direction,
            "sourcePaymentId": payload.get("sourcePaymentId"),
            "clientReference": payload.get("clientReference"),
            "pollCount": 0,
            "createdAt": now_iso(),
        }
        self.state["payments"][payment_id] = payment
        self.save()
        return http_status, {
            "paymentId": payment_id,
            "status": status,
            "code": code,
            "reason": reason,
            "imad": imad,
            "transmittedAmount": str(amount),
        }

    def poll_payment(self, payment_id: str, rail: str) -> tuple[int, dict[str, Any]]:
        payment = self.state["payments"].get(payment_id)
        if not payment:
            return 404, {"message": "Payment not found.", "code": "NOT_FOUND", "status": "FAILED"}

        payment["pollCount"] = int(payment.get("pollCount") or 0) + 1
        current = str(payment.get("status") or "ACCEPTED").upper()
        profile = str(self.state.get("profile") or "default")

        if current in {"REJECTED", "RETURNED", "SETTLED", "COMPLETED"}:
            self.save()
            return 200, {
                "paymentId": payment_id,
                "status": current,
                "code": payment.get("code"),
                "reason": payment.get("reason"),
                "imad": payment.get("imad"),
                "transmittedAmount": payment.get("transmittedAmount"),
            }

        if current == "REPAIR_REQUIRED":
            payment["status"] = "PENDING_REPAIR"
            payment["code"] = "REPAIR"
            payment["reason"] = "Awaiting repair or approval."
        elif payment["pollCount"] == 1:
            payment["status"] = "IN_PROCESS"
            payment["code"] = "PROCESSING"
            payment["reason"] = "Payment is processing."
        else:
            amount = as_decimal(payment.get("amount"))
            seed = seed_int(f"{payment_id}:{profile}")
            if rail == "ACH" and (profile == "returns" or seed % 9 == 0):
                payment["status"] = "RETURNED"
                payment["code"] = "R01"
                payment["reason"] = "Insufficient funds."
            elif rail == "WIRE" and seed % 11 == 0:
                payment["status"] = "REJECTED"
                payment["code"] = "WIRE_REJECT_BAD_DATA"
                payment["reason"] = "Beneficiary data rejected by receiving FI."
            else:
                payment["status"] = "SETTLED"
                payment["code"] = "SETTLED"
                payment["reason"] = "Settlement complete."
                if rail == "WIRE" and not payment.get("imad"):
                    payment["imad"] = f"IMAD{datetime.now(UTC).strftime('%Y%m%d')}{seed % 100000:05d}"
                self._append_transaction(payment, amount)

        self.save()
        return 200, {
            "paymentId": payment_id,
            "status": payment["status"],
            "code": payment.get("code"),
            "reason": payment.get("reason"),
            "imad": payment.get("imad"),
            "transmittedAmount": payment.get("transmittedAmount"),
        }

    def _append_transaction(self, payment: dict[str, Any], amount: Decimal) -> None:
        if payment.get("transactionEmitted"):
            return
        account_id = self.state["accounts"][0]["id"]
        control = f"{seed_int(payment['paymentId']) % 10**15:015d}"
        direction = "D" if str(payment.get("direction")).upper() == "DEBIT" else "C"
        transaction = {
            "description": payment.get("clientReference") or payment.get("sourcePaymentId") or "Mock payment",
            "transactionCode": "142" if payment.get("rail") == "WIRE" else "195",
            "transactionCodeDescription": "WIRE CREDIT" if payment.get("rail") == "WIRE" else "ACH DEBIT",
            "postingDate": now_iso(),
            "amount": float(amount),
            "serialNumber": control,
            "controlNumber": control,
            "confirmationNumber": control,
            "transactionType": direction,
            "status": "POSTED",
        }
        self.state["transactions"][account_id].insert(0, transaction)
        payment["transactionEmitted"] = True


def json_response(handler: BaseHTTPRequestHandler, status: int, body: dict[str, Any]) -> None:
    raw = json.dumps(body).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


class MockHandler(BaseHTTPRequestHandler):
    server_version = "MockCubi/1.0"

    @property
    def store(self) -> StateStore:
        return self.server.store  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stdout.write("%s - - [%s] %s\n" % (self.client_address[0], self.log_date_time_string(), fmt % args))

    def _body_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _require_bearer(self) -> bool:
        auth = self.headers.get("Authorization") or ""
        return auth.startswith("Bearer ") and len(auth.split(" ", 1)[1].strip()) > 0

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/health":
            json_response(
                self,
                200,
                {
                    "status": "ok",
                    "mode": "mock",
                    "profile": self.store.state.get("profile", "default"),
                    "token_url": "/security/v1/oauth2/token",
                    "accounts": len(self.store.state["accounts"]),
                    "payments": len(self.store.state["payments"]),
                },
            )
            return

        if not self._require_bearer():
            json_response(self, 401, {"statusCode": 401, "message": "Unauthorized. Access token is invalid."})
            return

        if path == "/accounts/v1/":
            accounts = self.store.state["accounts"]
            json_response(
                self,
                200,
                {
                    "pageSize": 100,
                    "pageOffset": 0,
                    "totalPages": 1,
                    "totalItemCount": len(accounts),
                    "items": accounts,
                },
            )
            return

        if path.startswith("/accounts/v1/") and path.endswith("/transactions"):
            parts = path.strip("/").split("/")
            account_id = parts[2]
            query = parse_qs(parsed.query)
            items = list(self.store.state["transactions"].get(account_id, []))
            q = (query.get("q", [""])[0] or "").strip().lower()
            date_from = (query.get("dateFrom", [""])[0] or "").strip()
            date_to = (query.get("dateTo", [""])[0] or "").strip()
            statuses = {s.upper() for s in (query.get("status", [""])[0] or "").split(",") if s.strip()}
            if q:
                items = [
                    item
                    for item in items
                    if q in " ".join(
                        [
                            str(item.get("description") or ""),
                            str(item.get("transactionCode") or ""),
                            str(item.get("transactionCodeDescription") or ""),
                            str(item.get("controlNumber") or ""),
                            str(item.get("confirmationNumber") or ""),
                        ]
                    ).lower()
                ]
            if date_from:
                items = [item for item in items if str(item.get("postingDate") or "") >= date_from]
            if date_to:
                items = [item for item in items if str(item.get("postingDate") or "") <= date_to]
            if statuses:
                items = [item for item in items if str(item.get("status") or "").upper() in statuses]
            limit = max(1, int((query.get("limit", ["100"])[0] or "100")))
            offset = max(0, int((query.get("offset", ["0"])[0] or "0")))
            paged = items[offset : offset + limit]
            json_response(self, 200, {"hasMorePages": offset + limit < len(items), "transactions": paged})
            return

        if path.startswith("/ach/v1/outgoing/") or path.startswith("/wires/v1/outgoing/"):
            payment_id = path.rstrip("/").split("/")[-1]
            rail = "WIRE" if path.startswith("/wires/") else "ACH"
            status, body = self.store.poll_payment(payment_id, rail)
            json_response(self, status, body)
            return

        json_response(self, 404, {"message": "Not found."})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/security/v1/oauth2/token":
            json_response(
                self,
                200,
                {
                    "access_token": self.store.state["token"],
                    "token_type": "Bearer",
                    "expires_in": 3600,
                },
            )
            return

        if not self._require_bearer():
            json_response(self, 401, {"statusCode": 401, "message": "Unauthorized. Access token is invalid."})
            return

        if path in {"/ach/v1/outgoing/debit", "/ach/v1/outgoing/credit", "/wires/v1/outgoing"}:
            payload = self._body_json()
            rail = "WIRE" if path.startswith("/wires/") else "ACH"
            direction = "CREDIT" if path.endswith("/credit") else str(payload.get("direction") or "DEBIT").upper()
            status, body = self.store.create_payment(payload, rail, direction)
            json_response(self, status, body)
            return

        json_response(self, 404, {"message": "Not found."})


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a local Cubi-compatible mock endpoint.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8791)
    parser.add_argument("--state-file", default=str(Path(__file__).with_name("mock_cubi_state.json")))
    args = parser.parse_args()

    store = StateStore(Path(args.state_file))
    server = ThreadingHTTPServer((args.host, args.port), MockHandler)
    server.store = store  # type: ignore[attr-defined]
    print(f"Mock Cubi endpoint listening on http://{args.host}:{args.port}")
    print(f"State file: {args.state_file}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
