from __future__ import annotations

import argparse
from typing import Any

from mcp.server.fastmcp import FastMCP

from .manager import CubiMockManager

manager = CubiMockManager()
mcp = FastMCP("Cubi Mock Playground", stateless_http=True, json_response=True)


@mcp.tool()
def ensure_cubi_mock_running(bind_host: str = "127.0.0.1", port: int = 8791, profile: str = "default", reset: bool = False) -> dict[str, Any]:
    """Start the local Cubi-compatible mock server if needed and return env/config details."""
    return manager.ensure_mock_running(bind_host=bind_host, port=port, profile=profile, reset=reset)


@mcp.tool()
def stop_cubi_mock() -> dict[str, Any]:
    """Stop the local Cubi-compatible mock server."""
    return manager.stop_mock()


@mcp.tool()
def reset_cubi_mock_state(profile: str = "default") -> dict[str, Any]:
    """Reset the mock state to a named profile."""
    return manager.reset_state(profile=profile)


@mcp.tool()
def get_cubi_mock_env(bind_host: str = "127.0.0.1", port: int = 8791) -> dict[str, Any]:
    """Return the env bundle required for an app to talk to the local mock in real HTTP mode."""
    return manager.get_env_bundle(bind_host=bind_host, port=port)


@mcp.tool()
def get_cubi_mock_health() -> dict[str, Any]:
    """Return process and /health information for the local mock."""
    return manager.get_mock_health()


@mcp.tool()
def get_cubi_mock_mcp_config() -> dict[str, Any]:
    """Return a sample MCP config snippet for this repo."""
    return manager.get_mcp_config()


@mcp.tool()
def list_cubi_mock_accounts(bind_host: str = "127.0.0.1", port: int = 8791) -> dict[str, Any]:
    """Fetch accounts from the running mock server."""
    return manager.list_accounts(bind_host=bind_host, port=port)


@mcp.tool()
def list_cubi_mock_transactions(account_id: str, bind_host: str = "127.0.0.1", port: int = 8791, limit: int = 20, offset: int = 0) -> dict[str, Any]:
    """Fetch transactions for an account from the running mock server."""
    return manager.list_transactions(account_id=account_id, bind_host=bind_host, port=port, limit=limit, offset=offset)


@mcp.tool()
def create_cubi_mock_payment(
    rail: str = "WIRE",
    direction: str = "DEBIT",
    amount: str = "1500.00",
    source_payment_id: str = "DEMO-PAYMENT-1",
    client_reference: str = "CLIENT-DEMO-1",
    beneficiary_bank_routing: str = "021000021",
    bind_host: str = "127.0.0.1",
    port: int = 8791,
) -> dict[str, Any]:
    """Create a demo payment against the running mock server."""
    return manager.create_demo_payment(
        rail=rail,
        direction=direction,
        amount=amount,
        source_payment_id=source_payment_id,
        client_reference=client_reference,
        beneficiary_bank_routing=beneficiary_bank_routing,
        bind_host=bind_host,
        port=port,
    )


@mcp.tool()
def poll_cubi_mock_payment(payment_id: str, rail: str = "WIRE", bind_host: str = "127.0.0.1", port: int = 8791) -> dict[str, Any]:
    """Poll a demo payment from the running mock server."""
    return manager.poll_payment(payment_id=payment_id, rail=rail, bind_host=bind_host, port=port)


@mcp.resource("cubi-mock://env")
def cubi_mock_env_resource() -> str:
    """Default dotenv bundle for the local mock."""
    return manager.get_env_bundle()["dotenv"]


@mcp.resource("cubi-mock://health")
def cubi_mock_health_resource() -> str:
    """JSON health snapshot for the local mock."""
    return str(manager.get_mock_health())


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Cubi mock MCP server.")
    parser.add_argument("--transport", default="stdio", choices=["stdio", "streamable-http"])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8811)
    args = parser.parse_args()

    if args.transport == "streamable-http":
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.run(transport="streamable-http")
        return

    mcp.run()


if __name__ == "__main__":
    main()
