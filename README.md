# CollabCode — Real-Time Collaborative Code Editor

A full-stack collaborative code editor where multiple users can write and run Python code together in real time, with each execution sandboxed in an isolated Docker container.

**Live demo (collaborative editing):** https://collab-code-editor-orpin.vercel.app
**Backend:** https://collab-code-editor-cnbj.onrender.com

> Note: the live demo showcases real-time collaboration (sync, cursors, presence). The Docker-based code execution feature requires privileged host access that standard free-tier PaaS providers (Render, Vercel, Railway) don't expose — see [Code Execution Demo](#code-execution-demo) below for a local recording of that feature working end-to-end. **A migration to a Docker-capable host (e.g. a cloud VM) is planned to bring live code execution to the public deployment as well.**

---

## Features

- **Real-time collaborative editing** — multiple users editing the same document simultaneously, synced over WebSockets
- **Live cursor tracking** — see where collaborators are typing
- **Presence awareness** — live "who's online" list per room
- **Shareable room links** — copy a link to invite collaborators directly into your session
- **Sandboxed code execution** — run Python code inside an isolated, disposable Docker container with:
  - Network access disabled
  - Memory and CPU limits enforced
  - Read-only filesystem
  - Execution timeout (kills infinite loops automatically)
  - Non-root execution user
- **Auto-reconnect** — automatically recovers from dropped connections
- **Debounced sync** — edits are batched client-side to avoid flooding the server on every keystroke

## Tech Stack

**Frontend:** React (Vite), Monaco Editor
**Backend:** FastAPI, WebSockets, Python
**Execution sandbox:** Docker (isolated per-run containers)
**Deployment:** Vercel (frontend), Render (backend)

## Architecture

```
┌─────────────┐         WebSocket          ┌──────────────┐
│   React +   │ ◄────────────────────────► │   FastAPI    │
│   Monaco    │      (edit/cursor/run)      │   Backend    │
└─────────────┘                             └──────┬───────┘
                                                     │
                                          spawns (in thread pool,
                                          non-blocking)
                                                     │
                                                     ▼
                                          ┌────────────────────┐
                                          │  Docker container   │
                                          │  --network none      │
                                          │  --read-only          │
                                          │  --memory 128m         │
                                          │  timeout: 5s             │
                                          └────────────────────┘
```

Each room maintains its own in-memory document state and version counter. Edits use a last-write-wins conflict strategy — a deliberate simplification over full Operational Transform / CRDTs, chosen to fit project scope while still handling concurrent edits without crashing or corrupting state.

Code execution runs in a background thread pool so a slow/long-running script from one user doesn't block WebSocket message handling for anyone else, in any room.

## Code Execution Demo

Since Docker isn't available on the free hosting tiers used for this deployment, here's the sandboxed execution feature running locally, tested against real attack scenarios: infinite loop timeout protection, blocked filesystem writes, blocked network access, and graceful handling of syntax/runtime errors.

## Running Locally

**Backend:**
```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
docker build -t code-sandbox .
uvicorn main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

Requires Docker Desktop running locally for the code execution feature to work.

## Known Limitations

- Room state is stored in-memory — a server restart clears all active documents. A production version would persist rooms to PostgreSQL/Redis.
- Conflict resolution uses last-write-wins rather than Operational Transform/CRDTs, which can occasionally overwrite concurrent edits in extreme timing cases.
- Docker-based execution requires a host with Docker access, so it isn't available on the current public deployment (Render/Vercel free tier). **Planned next step:** migrate the backend to a Docker-capable host (e.g. AWS EC2 or Oracle Cloud free tier) so code execution works live, not just locally.

## What I'd Improve With More Time[In progress]

- Deploy the backend to a Docker-capable host for a fully live execution demo
- Persist documents to a database so rooms survive server restarts
- Add Operational Transform (or a CRDT like Yjs) for true conflict-free concurrent editing
- Support additional languages beyond Python in the execution sandbox
