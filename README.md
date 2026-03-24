# Cubi MCP Playground

`cubi-mcp-playground` is a local prototype repo for teams that want to work on Cubi-style integrations before sandbox onboarding is complete, while sandbox is down, or while they are still designing the user experience and testing flows.

It gives you three things in one place:

- a Cubi-compatible localhost HTTP mock
- an MCP server that can manage that mock
- a browser UI so someone can try the workflow without learning the MCP protocol first

The main design goal is to let an app stay in `CUBI_MODE=real` and point to localhost. That means your app still exercises token fetch, HTTP routing, path composition, create calls, polling, and health checks as if it were talking to a real environment.

## Why This Repo Exists

Most mock integrations stop at one of these:

- in-process fake classes for unit tests
- raw API fixtures with no running endpoint
- a mock HTTP server with no easy onboarding path

This repo is intended to cover the next layer up:

- manual UI design and workflow prototyping
- end-to-end application testing against a live local endpoint
- MCP-assisted setup so a user can ask a tool to stand up the mock and get the right env bundle back immediately

## What Is In The Repo

### Core Runtime

- [server/mock_cubi_server.py](C:/Temp/Github/Code/cubi-mcp-playground/server/mock_cubi_server.py)
  Standalone Cubi-compatible HTTP mock
- [server/manager.py](C:/Temp/Github/Code/cubi-mcp-playground/server/manager.py)
  Shared runtime manager used by both the UI server and the MCP server

### MCP Layer

- [server/mcp_server.py](C:/Temp/Github/Code/cubi-mcp-playground/server/mcp_server.py)
  Exposes the mock lifecycle and demo actions as MCP tools/resources

### Browser Playground

- [server/playground.py](C:/Temp/Github/Code/cubi-mcp-playground/server/playground.py)
  Small local web server for the browser UI
- [web/index.html](C:/Temp/Github/Code/cubi-mcp-playground/web/index.html)
- [web/app.js](C:/Temp/Github/Code/cubi-mcp-playground/web/app.js)
- [web/style.css](C:/Temp/Github/Code/cubi-mcp-playground/web/style.css)

### Profiles

- [profiles/default.json](C:/Temp/Github/Code/cubi-mcp-playground/profiles/default.json)
- [profiles/returns.json](C:/Temp/Github/Code/cubi-mcp-playground/profiles/returns.json)
- [profiles/repair.json](C:/Temp/Github/Code/cubi-mcp-playground/profiles/repair.json)
- [profiles/wire-heavy.json](C:/Temp/Github/Code/cubi-mcp-playground/profiles/wire-heavy.json)

These profiles are simple labels right now, but the mock behavior changes based on the selected profile:

- `default`
  balanced seed data and normal accepted -> processing -> settled progression
- `returns`
  ACH-heavy behavior and easy-to-demonstrate return outcomes
- `repair`
  much lower repair threshold so pending-repair states are easy to trigger
- `wire-heavy`
  more wire-oriented seeded transaction mix

## What The Mock Supports

The HTTP mock currently supports:

- `POST /security/v1/oauth2/token`
- `GET /accounts/v1/`
- `GET /accounts/v1/{account_id}/transactions`
- `POST /ach/v1/outgoing/debit`
- `POST /ach/v1/outgoing/credit`
- `POST /wires/v1/outgoing`
- `GET /ach/v1/outgoing/{payment_id}`
- `GET /wires/v1/outgoing/{payment_id}`
- `GET /health`

This is enough for:

- health checks
- account/transaction browsing
- demo payment creation
- status polling
- env wiring into a host app

## Prerequisites

You need:

- Python 3.12+ available on `PATH`
- PowerShell
- local ability to open a browser on `127.0.0.1`

The only external Python dependency for this repo is the MCP SDK:

- [requirements.txt](C:/Temp/Github/Code/cubi-mcp-playground/requirements.txt)

## Step-By-Step: First Run

### Step 1: Create A Virtual Environment

From the repo root:

```powershell
python -m venv .venv
```

### Step 2: Install Dependencies

```powershell
.venv\Scripts\python -m pip install -r requirements.txt
```

Today that installs:

- `mcp[cli]==1.26.0`

The browser playground and the mock HTTP server are stdlib-based, so the MCP SDK is the only runtime dependency you need.

### Step 3: Start The Browser Playground

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-playground.ps1
```

By default the playground starts on:

- `http://127.0.0.1:8765`

If you want a different UI port:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-playground.ps1 -Port 8780
```

### Step 4: Open The UI

Open:

- `http://127.0.0.1:8765`

At this point the UI server is running, but the Cubi mock endpoint is not running yet.

### Step 5: Start The Mock From The UI

In the browser:

1. Leave `Bind Host` as `127.0.0.1`
2. Leave `Port` as `8791` or choose another local port
3. Choose a profile such as `default`
4. Optionally check `Reset state on start`
5. Click `Start Mock`

The UI will:

- start the local Cubi-compatible HTTP mock
- show the `/health` payload
- generate the env bundle your app can consume
- generate an MCP config snippet for the MCP server

### Step 6: Point Your App At The Mock

Copy the `Env Bundle` block from the UI and place it into a local override env file for your app.

The most important values are:

```env
CUBI_MODE=real
CUBI_BASE_URL=http://127.0.0.1:8791
CUBI_TOKEN_URL=http://127.0.0.1:8791/security/v1/oauth2/token
CUBI_CLIENT_ID=mock-client
CUBI_CLIENT_SECRET=mock-secret
CUBI_ACCOUNTS_PATH=/accounts/v1/
CUBI_TRANSACTIONS_PATH_TEMPLATE=/accounts/v1/{account_id}/transactions
```

That keeps your app in real HTTP mode while pointing at localhost.

## Step-By-Step: Using The Browser UI

The UI is meant to be useful even for someone who does not care about MCP yet.

### Mock Runtime Panel

Use this panel to:

- choose the mock port
- choose a scenario profile
- start the mock
- stop the mock
- reset persisted state
- inspect the current `/health` result

### Env Bundle Panel

Use this when:

- you want to wire another app to the mock
- you want a teammate to copy the exact localhost config
- you want a stable local “sandbox replacement” file

### MCP Config Panel

Use this when:

- you want to connect Claude Code or another MCP client
- you want to see the exact command and cwd needed to launch the repo MCP server

### Accounts Panel

Click `Load` to fetch seeded accounts from the running mock. Clicking an account card loads recent transactions and displays them in the demo output panel.

### Demo Payment Panel

Use this to simulate create and poll flows without a second application.

Example:

1. Select `WIRE`
2. Leave direction as `DEBIT`
3. Enter amount `1200.00`
4. Click `Create`
5. Click `Poll Latest`

Typical progression:

- create -> `ACCEPTED`
- first poll -> `IN_PROCESS`
- later poll -> `SETTLED`

If you choose the `repair` profile or omit a wire routing value, you can quickly demo non-happy-path outcomes too.

## Step-By-Step: Running The MCP Server

The MCP server is separate from the browser UI. The UI is for people; the MCP server is for tools/agents/clients.

### Option 1: Run MCP Over Stdio

This is the simplest local integration pattern.

```powershell
.venv\Scripts\python -m server.mcp_server
```

This launches the MCP server in stdio mode.

### Option 2: Run MCP Over Streamable HTTP

This is useful for local inspector-style testing or for environments that prefer an HTTP MCP transport.

```powershell
.venv\Scripts\python -m server.mcp_server --transport streamable-http --host 127.0.0.1 --port 8811
```

Or via the helper script:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-mcp-http.ps1
```

## MCP Tools Included

The MCP server currently exposes these tools:

- `ensure_cubi_mock_running`
- `stop_cubi_mock`
- `reset_cubi_mock_state`
- `get_cubi_mock_env`
- `get_cubi_mock_health`
- `get_cubi_mock_mcp_config`
- `list_cubi_mock_accounts`
- `list_cubi_mock_transactions`
- `create_cubi_mock_payment`
- `poll_cubi_mock_payment`

It also exposes resources:

- `cubi-mock://env`
- `cubi-mock://health`

## Example MCP Usage Flow

If you connect an MCP client to this repo, the happy-path flow is:

1. Call `ensure_cubi_mock_running`
2. Read the returned env bundle
3. Start or reconfigure the target app to use those env vars
4. Optionally call `list_cubi_mock_accounts`
5. Optionally call `create_cubi_mock_payment`
6. Poll it with `poll_cubi_mock_payment`

This is the onboarding shortcut: a user does not need sandbox credentials just to begin building or demoing the workflow.

## Example Claude Code MCP Config

The manager and UI generate a config snippet, but the default shape is:

```json
{
  "mcpServers": {
    "cubi-mock-playground": {
      "command": "C:\\path\\to\\repo\\.venv\\Scripts\\python.exe",
      "args": ["-m", "server.mcp_server"],
      "cwd": "C:\\path\\to\\repo"
    }
  }
}
```

If you prefer streamable HTTP instead of stdio, run the HTTP MCP transport separately and point your client at that URL according to the client’s MCP configuration format.

## Example: Pointing Another App At The Mock

Suppose your target app already knows how to talk to Cubi and has env vars like:

- `CUBI_BASE_URL`
- `CUBI_TOKEN_URL`
- `CUBI_CLIENT_ID`
- `CUBI_CLIENT_SECRET`
- `CUBI_ACCOUNTS_PATH`
- `CUBI_TRANSACTIONS_PATH_TEMPLATE`

You do not need to patch the app code first. Start the mock and then apply:

```env
CUBI_MODE=real
CUBI_BASE_URL=http://127.0.0.1:8791
CUBI_TOKEN_URL=http://127.0.0.1:8791/security/v1/oauth2/token
CUBI_CLIENT_ID=mock-client
CUBI_CLIENT_SECRET=mock-secret
```

The app should then:

- fetch a token from localhost
- call accounts and transactions on localhost
- create/poll payments against localhost

That is usually a much better prototype path than building app-specific fake adapters first.

## File And Runtime Behavior

### State

The mock state is persisted under:

- `.runtime/mock_cubi_state.json`

That means:

- created payments survive server restarts
- poll counts survive restarts
- seeded profile data can be reset explicitly

### Process Tracking

The manager keeps process metadata in:

- `.runtime/mock_cubi_process.json`

This is how the UI and MCP server know whether a mock process is expected to be running.

## Common Commands

### Start The Browser Playground

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-playground.ps1
```

### Start MCP Over HTTP

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-mcp-http.ps1
```

### Start MCP Over Stdio

```powershell
.venv\Scripts\python -m server.mcp_server
```

### Start The Raw Mock Endpoint Only

```powershell
.venv\Scripts\python -m server.mock_cubi_server --host 127.0.0.1 --port 8791 --state-file .runtime\mock_cubi_state.json
```

## Troubleshooting

### The UI Loads But The Mock Is Offline

That usually means the playground server is up, but the mock has not been started yet. Click `Start Mock`.

### The Mock Will Not Start On The Default Port

Pick a different mock port in the UI, for example `8795`, and start again. Then copy the updated env bundle.

### My App Still Talks To Sandbox

That usually means the app did not load the local override env file. Confirm the effective values for:

- `CUBI_BASE_URL`
- `CUBI_TOKEN_URL`
- `CUBI_CLIENT_ID`
- `CUBI_CLIENT_SECRET`

### I Want A Clean Demo State

Use `Reset State`, then start the mock again with the profile you want.

## Suggested Next Enhancements

If this repo is going to become public or shared widely, the next useful additions would be:

- Docker support
- GitHub Actions smoke tests
- canned sample app integrations
- a richer profile system with explicit scenario fixtures
- one-click export of `.env.local` files for known host apps
