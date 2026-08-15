# Harness Local

Harness Local is a small local MCP workspace bridge for ChatGPT. It exposes a controlled set of filesystem and shell tools for a selected local workspace, adds approval gates around mutating operations, and connects the local MCP server to OpenAI through Secure MCP Tunnel.

> **Security note:** this project is intentionally designed to keep the MCP server bound to localhost. OpenAI's current guidance is that ChatGPT does not connect directly to local MCP servers; use Secure MCP Tunnel for private, on-prem, or developer-machine MCP servers instead of exposing them directly to the public internet.

## What it provides

- A local FastAPI service on `127.0.0.1:43827`
- MCP tools for workspace inspection, file access, editing, and command execution
- Human approval for mutating tools such as writes and shell commands
- A lightweight browser UI for workspace selection, approvals, and history
- Secure MCP Tunnel integration for connecting ChatGPT to the local server

## Requirements

Before starting, install:

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/)
- OpenAI `tunnel-client` with access to Secure MCP Tunnel
- A ChatGPT/OpenAI account and workspace with the required MCP/developer-mode permissions

OpenAI currently documents custom MCP apps through ChatGPT Developer Mode. ChatGPT connects to remote MCP endpoints, and local/private MCP servers should be connected through Secure MCP Tunnel.

Official OpenAI reference: [Developer mode and MCP apps in ChatGPT](https://help.openai.com/en/articles/12584461-developer-mode-and-mcp-apps-in-chatgpt-beta)

## 1. Install the project

Clone the repository and install the locked dependencies:

```bash
git clone https://github.com/Hamza-69/harness.git
cd harness
uv sync
```

Run the local app once to confirm the server starts:

```bash
uv run harnesslocal
```

The UI should be available at:

```text
http://127.0.0.1:43827
```

The MCP endpoint is mounted under:

```text
http://127.0.0.1:43827/mcp
```

## 2. Create a Secure MCP Tunnel

In the OpenAI Platform, create or select a Secure MCP Tunnel for this MCP server.

You will need the tunnel credentials/identifiers exposed by OpenAI for your organization. This repository expects the following environment variables:

```bash
CONTROL_PLANE_API_KEY=
CONTROL_PLANE_TUNNEL_ID=
```

Copy the example shell environment file:

```bash
cp env_example.sh env.sh
```

Then fill in `env.sh` with the values for your tunnel:

```bash
export CONTROL_PLANE_API_KEY="..."
export CONTROL_PLANE_TUNNEL_ID="..."
export MCP_SERVER_URL="http://127.0.0.1:43827/mcp"
```

`env.sh` is ignored by Git, so local credentials are not committed accidentally.

## 3. Initialize the tunnel profile

This repository includes `init.sh` to create or refresh the `harness` tunnel profile from the values in `env.sh`.

Run:

```bash
./init.sh
```

The script loads `env.sh` and runs:

```bash
tunnel-client init \
  --profile harness \
  --tunnel-id "$CONTROL_PLANE_TUNNEL_ID" \
  --mcp-server-url "$MCP_SERVER_URL" \
  --force
```

With the example configuration above, `MCP_SERVER_URL` should point at:

```text
http://127.0.0.1:43827/mcp
```

You normally only need to rerun `./init.sh` when the tunnel ID, MCP server URL, or tunnel-client profile configuration changes. The `--force` flag replaces an existing `harness` profile with the current values.

## 4. Run Harness Local

You need both the local MCP server and the tunnel client running.

### Terminal 1 — local MCP server

```bash
uv run harnesslocal
```

### Terminal 2 — Secure MCP Tunnel

```bash
./run.sh
```

`run.sh` loads `env.sh` and runs:

```bash
tunnel-client run --profile harness
```

At this point the local server remains bound to localhost while the OpenAI tunnel provides the remote connection path.

## 5. Add the MCP app in ChatGPT

OpenAI's current ChatGPT flow for custom MCP apps is:

1. Enable **Developer Mode** for your ChatGPT workspace/account if required.
2. Go to **Settings / Workspace Settings → Apps → Create**.
3. Provide the MCP endpoint/tunnel information created for the server.
4. Choose the appropriate authentication option, if applicable.
5. Use **Scan Tools** and verify the tools exposed by Harness Local.
6. Create the app and enable the resulting development app in ChatGPT.

OpenAI notes that write/modify actions can require explicit confirmation in ChatGPT. Harness Local also applies its own local approval flow to mutating operations.

## Available MCP tools

Harness Local exposes workspace-scoped tools including:

| Tool | Purpose | Local approval |
| --- | --- | --- |
| `workspace_info` | Show the active workspace | No |
| `ls` | List files and directories | No |
| `glob` | Find files by pattern | No |
| `grep` | Search file contents | No |
| `read_file` | Read a file | No |
| `write_file` | Create or replace a file | Yes |
| `edit_file` | Apply a targeted edit | Yes |
| `execute` | Run a shell command | Yes |

All filesystem operations are scoped to the workspace selected in the local Harness UI.

## Typical workflow

1. Start `uv run harnesslocal`.
2. Open `http://127.0.0.1:43827` and select the project you want ChatGPT to work on.
3. Start `./run.sh` to bring up the Secure MCP Tunnel.
4. Enable the Harness MCP app in ChatGPT.
5. Ask ChatGPT to inspect or modify the selected workspace.
6. Approve mutating operations in the local Harness UI when prompted.

## Troubleshooting

### ChatGPT cannot see the MCP server

Confirm all three layers are running/configured:

```text
ChatGPT → OpenAI Secure MCP Tunnel → tunnel-client → localhost:43827/mcp
```

Then verify:

```bash
uv run harnesslocal
```

and, in another terminal:

```bash
./run.sh
```

### The local UI does not open

Check that nothing else is already using port `43827` and confirm the process is listening on `127.0.0.1`.

### Tools changed but ChatGPT still shows the old schema

OpenAI currently notes that MCP app/tool changes are not necessarily picked up automatically after approval. Refresh/rescan the app's actions in ChatGPT workspace settings when you change MCP tool definitions.

### Tunnel permissions fail

Secure MCP Tunnel access depends on your OpenAI organization/workspace permissions and feature availability. Check that your account has the required tunnel and developer-mode permissions in the relevant OpenAI organization/workspace.

## Security considerations

- Keep `env.sh`, API keys, tunnel credentials, databases, and other local secrets out of Git.
- Keep the MCP server bound to `127.0.0.1` unless you intentionally redesign the deployment.
- Review every mutating approval before accepting it.
- Only connect MCP servers you trust. OpenAI explicitly warns that untrusted MCP servers can introduce security risks such as prompt injection.
- Treat `execute` as privileged access to the selected workspace.

## Development

The package entry point is:

```bash
uv run harnesslocal
```

The main application lives under:

```text
src/harnesslocal/
```

After changing dependencies:

```bash
uv sync
```

After changing MCP tool definitions, restart the local server and refresh the app/tool definitions in ChatGPT.
