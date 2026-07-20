### 💻 CollabCode
Real-Time Collaborative Code Editor with Sandboxed Execution

Features • Architecture • Getting Started • Project Structure • Known Limitations

---

CollabCode is a full-stack collaborative code editor where multiple users can write and run Python code together in real time, with each execution sandboxed inside an isolated, disposable Docker container.

## ✨ Features

- 🔄 **Real-Time Collaborative Editing:** Multiple users edit the same document simultaneously, synced over WebSockets.
- 🖱 **Live Cursor Tracking:** See exactly where collaborators are typing, in real time.
- 🟢 **Presence Awareness:** A live "who's online" list per room.
- 🔗 **Shareable Room Links:** Copy a link to invite collaborators directly into your session.
- 📦 **Sandboxed Code Execution:** Run Python code inside an isolated container with network access disabled, memory/CPU limits, a read-only filesystem, execution timeouts, and a non-root user.
- 🔁 **Auto-Reconnect:** Automatically recovers from dropped connections.
- ⚡ **Debounced Sync:** Edits are batched client-side to avoid flooding the server on every keystroke.

## 🏗 Architecture

CollabCode is built on a real-time-first stack: a WebSocket-driven backend keeps every client in sync, while code execution is fully isolated from the main server process.

### Tech Stack

| Category | Technologies |
|---|---|
| Frontend | React (Vite), Monaco Editor |
| Backend | FastAPI, WebSockets, Python |
| Execution Sandbox | Docker (isolated per-run containers) |
| Deployment (planned) | Vercel (frontend), Render (backend) — pending migration to a Docker-capable host |

### Request Flow

```
┌─────────────┐         WebSocket          ┌──────────────┐
│   React +   │ ◄────────────────────────► │    FastAPI   │
│   Monaco    │      (edit/cursor/run)       │   Backend    │
└─────────────┘                              └──────┬───────┘
                                                     │
                                          spawns (in thread pool,
                                          non-blocking)
                                                     │
                                                     ▼
                                          ┌────────────────────┐
                                          │  Docker container  │
                                          │  --network none    │
                                          │  --read-only       │
                                          │  --memory 128m     │
                                          │  timeout: 5s       │
                                          └────────────────────┘
```

Each room maintains its own in-memory document state and version counter. Edits use a last-write-wins conflict strategy — a deliberate simplification over full Operational Transform / CRDTs, chosen to fit project scope while still handling concurrent edits without crashing or corrupting state.

Code execution runs in a background thread pool so a slow or long-running script from one user doesn't block WebSocket message handling for anyone else, in any room.

## 🚀 Getting Started

### Prerequisites

- Node.js (v18 or higher)
- Python (v3.10 or higher)
- Docker Desktop (running, for the code execution feature)

### Backend Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
docker build -t code-sandbox .
uvicorn main:app --reload
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### Accessing the App

- Web App: http://localhost:5173
- Backend API: http://localhost:8000

## 📂 Project Structure

```
Collab-Code-Editor/
├── frontend/                # React + Vite client
│   ├── src/components/      # Editor, cursors, presence UI
│   └── src/lib/             # WebSocket client, utilities
├── backend/                 # FastAPI backend server
│   ├── main.py               # WebSocket + REST entrypoints
│   ├── sandbox/               # Docker execution logic
│   └── rooms/                  # In-memory room/document state
└── Dockerfile                # Sandbox container image
```

## ⚠️ Known Limitations

- **Code execution is local-only.** Docker-based execution requires privileged host access that standard free-tier PaaS providers (Render, Vercel, Railway) don't expose, so it isn't available on the current public deployment. **Planned next step:** migrate the backend to a Docker-capable host (e.g. AWS EC2 or Oracle Cloud free tier) so code execution works live, not just locally.
- Room state is stored in-memory — a server restart clears all active documents. A production version would persist rooms to PostgreSQL/Redis.
- Conflict resolution uses last-write-wins rather than Operational Transform/CRDTs, which can occasionally overwrite concurrent edits in extreme timing cases.

## 🔭 Planned Improvements *(in progress)*

- Deploy the backend to a Docker-capable host for a fully live execution demo
- Persist documents to a database so rooms survive server restarts
- Add Operational Transform (or a CRDT like Yjs) for true conflict-free concurrent editing
- Support additional languages beyond Python in the execution sandbox
