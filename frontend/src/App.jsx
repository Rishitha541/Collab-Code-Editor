import { useState, useRef, useEffect, useCallback } from "react";
import Editor from "@monaco-editor/react";
import "./App.css";

const WS_BASE = "ws://127.0.0.1:8000/ws";
const DEBOUNCE_MS = 300;

function App() {
  const [username, setUsername] = useState("");
  const [roomId, setRoomId] = useState(() => {
    // Auto-fill room ID if someone opened a shared link like ?room=xyz123
    const params = new URLSearchParams(window.location.search);
    return params.get("room") || "room1";
  });
  const [connected, setConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState("disconnected");
  const [onlineUsers, setOnlineUsers] = useState([]);
  const [code, setCode] = useState("");
  const [version, setVersion] = useState(0);
  const [output, setOutput] = useState("Output will appear here when you run code.");
  const [outputStatus, setOutputStatus] = useState("idle"); // idle | running | success | error
  const [runningBy, setRunningBy] = useState(null);
  const [toast, setToast] = useState(null);

  const wsRef = useRef(null);
  const suppressNextChange = useRef(false);
  const debounceTimer = useRef(null);
  const intentionalClose = useRef(false);
  const toastTimer = useRef(null);

  const showToast = useCallback((message) => {
    setToast(message);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 2200);
  }, []);

  const handleMessage = useCallback((event) => {
    const data = JSON.parse(event.data);

    switch (data.type) {
      case "sync":
        suppressNextChange.current = true;
        setCode(data.content);
        setVersion(data.version);
        setOnlineUsers(data.online_users || []);
        break;
      case "edit":
        suppressNextChange.current = true;
        setCode(data.content);
        setVersion(data.version);
        break;
      case "user_joined":
        setOnlineUsers(data.online_users || []);
        break;
      case "user_left":
        setOnlineUsers(data.online_users || []);
        break;
      case "run_status":
        setOutputStatus("running");
        setRunningBy(data.requested_by);
        setOutput(`Running (requested by ${data.requested_by})...`);
        break;
      case "run_result": {
        let text = "";
        if (data.stdout) text += data.stdout;
        if (data.stderr) text += (text ? "\n--- stderr ---\n" : "") + data.stderr;
        if (!text) text = "(no output)";
        setOutput(text);
        setOutputStatus(data.success ? "success" : "error");
        setRunningBy(data.requested_by);
        break;
      }
      default:
        break;
    }
  }, []);

  const openSocket = useCallback(() => {
    setConnectionStatus((prev) => (prev === "disconnected" ? "connecting" : prev));

    const ws = new WebSocket(
      `${WS_BASE}/${roomId}?username=${encodeURIComponent(username)}`
    );

    ws.onopen = () => {
      setConnected(true);
      setConnectionStatus("connected");
      // Reflect the room in the URL so refreshing keeps you in the same room,
      // and so the "copy link" button always has an accurate URL.
      const url = new URL(window.location);
      url.searchParams.set("room", roomId);
      window.history.replaceState({}, "", url);
    };

    ws.onclose = () => {
      setConnected(false);
      if (!intentionalClose.current) {
        setConnectionStatus("reconnecting");
        setTimeout(openSocket, 2000);
      } else {
        setConnectionStatus("disconnected");
      }
    };

    ws.onerror = () => {
      setConnectionStatus("error");
    };

    ws.onmessage = handleMessage;
    wsRef.current = ws;
  }, [roomId, username, handleMessage]);

  const connect = () => {
    if (!username.trim()) {
      showToast("Enter your name first");
      return;
    }
    if (!roomId.trim()) {
      showToast("Enter a room ID first");
      return;
    }
    intentionalClose.current = false;
    openSocket();
  };

  const leaveRoom = () => {
    intentionalClose.current = true;
    wsRef.current?.close();
    setConnected(false);
    setConnectionStatus("disconnected");
    setOnlineUsers([]);
    setCode("");
    setVersion(0);
    setOutput("Output will appear here when you run code.");
    setOutputStatus("idle");
  };

  const copyRoomLink = async () => {
    const url = new URL(window.location);
    url.searchParams.set("room", roomId);
    try {
      await navigator.clipboard.writeText(url.toString());
      showToast("Room link copied — send it to a collaborator");
    } catch {
      showToast("Couldn't copy automatically — copy the URL bar instead");
    }
  };

  const handleEditorChange = (value) => {
    if (suppressNextChange.current) {
      suppressNextChange.current = false;
      return;
    }
    setCode(value ?? "");

    clearTimeout(debounceTimer.current);
    debounceTimer.current = setTimeout(() => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "edit", content: value ?? "" }));
      }
    }, DEBOUNCE_MS);
  };

  const runCode = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "run", code }));
    }
  };

  useEffect(() => {
    return () => {
      intentionalClose.current = true;
      wsRef.current?.close();
    };
  }, []);

  const statusLabel = {
    connected: "Connected",
    connecting: "Connecting…",
    reconnecting: "Reconnecting…",
    disconnected: "Disconnected",
    error: "Connection error",
  }[connectionStatus];

  return (
    <div className="app">
      {toast && <div className="toast">{toast}</div>}

      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">{"</>"}</span>
          <span className="brand-name">CollabCode</span>
        </div>

        {!connected ? (
          <div className="connect-form">
            <input
              placeholder="Your name"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && connect()}
            />
            <input
              placeholder="Room ID"
              value={roomId}
              onChange={(e) => setRoomId(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && connect()}
            />
            <button className="btn-primary" onClick={connect}>
              {connectionStatus === "connecting" || connectionStatus === "reconnecting"
                ? "Connecting…"
                : "Join room"}
            </button>
          </div>
        ) : (
          <div className="session-info">
            <span className={`status-dot status-${connectionStatus}`} />
            <span className="status-label">{statusLabel}</span>
            <span className="divider" />
            <span className="room-tag">room: {roomId}</span>
            <button className="btn-ghost" onClick={copyRoomLink} title="Copy shareable room link">
              Copy link
            </button>
            <span className="divider" />
            <div className="avatars">
              {onlineUsers.map((u, i) => (
                <span key={`${u}-${i}`} className="avatar" title={u}>
                  {u.slice(0, 2).toUpperCase()}
                </span>
              ))}
            </div>
            <button className="btn-ghost" onClick={leaveRoom}>
              Leave
            </button>
          </div>
        )}
      </header>

      <main className="workspace">
        <section className="editor-pane">
          <div className="pane-header">
            <span>editor.py</span>
            <span className="version-tag">v{version}</span>
          </div>
          <Editor
            height="100%"
            defaultLanguage="python"
            theme="vs-dark"
            value={code}
            onChange={handleEditorChange}
            options={{
              fontSize: 14,
              minimap: { enabled: false },
              automaticLayout: true,
              scrollBeyondLastLine: false,
            }}
          />
        </section>

        <section className="output-pane">
          <div className="pane-header">
            <span>Output</span>
            <button className="btn-run" onClick={runCode} disabled={!connected}>
              ▶ Run
            </button>
          </div>
          <div className={`output-body output-${outputStatus}`}>
            {runningBy && outputStatus !== "idle" && (
              <div className="output-meta">run by {runningBy}</div>
            )}
            <pre>{output}</pre>
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;