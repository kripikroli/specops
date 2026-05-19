"""SpecOps Demo — Browser-based visual examples runner.

Launches a local web server with a professional UI for browsing,
viewing code, and running examples with live streaming output.

Usage:
    specops-demo          # CLI entry point
    uv run specops-demo   # Via uv
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
import webbrowser
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI(title="SpecOps Demo")

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"
EXCLUDE_DIRS = {"shared", "__pycache__", "providers"}
EXCLUDE_FILES = {"run_all.py", "__init__.py"}

# Tag/module mapping from docstrings
MODULE_TAGS: dict[str, str] = {
    "trace": "Tracing",
    "replay": "Replay",
    "eval": "Eval",
    "heal": "Heal",
    "health": "Health",
    "rca": "RCA",
    "simulation": "Simulation",
    "chaos": "Chaos",
    "regression": "Regression",
    "coordination": "Coordination",
    "adapter": "Adapters",
    "langgraph": "Adapters",
    "crewai": "Adapters",
    "async": "Tracing",
    "plain": "Tracing",
    "multi_agent": "Coordination",
}


def _extract_metadata(path: Path) -> dict[str, str]:
    """Extract description and tags from example file docstring."""
    try:
        content = path.read_text()
    except OSError:
        return {"description": path.stem, "tag": "Other"}

    # Extract first docstring
    match = re.search(r'"""(.+?)"""', content, re.DOTALL)
    desc = (
        match.group(1).strip().split("\n")[0]
        if match
        else path.stem.replace("_", " ").title()
    )

    # Determine tag from filename
    tag = "Other"
    stem = path.stem.lower()
    for key, val in MODULE_TAGS.items():
        if key in stem:
            tag = val
            break

    return {"description": desc, "tag": tag}


def discover_examples() -> list[dict[str, Any]]:
    """Discover all runnable examples dynamically."""
    examples: list[dict[str, Any]] = []

    if not EXAMPLES_DIR.exists():
        return examples

    # Core examples (root .py files)
    for p in sorted(EXAMPLES_DIR.glob("*.py")):
        if p.name in EXCLUDE_FILES:
            continue
        meta = _extract_metadata(p)
        examples.append(
            {
                "id": p.stem,
                "name": p.stem.replace("_", " ").title(),
                "path": str(p.relative_to(EXAMPLES_DIR.parent)),
                "abs_path": str(p),
                "category": "core",
                **meta,
            }
        )

    # Provider examples
    providers_dir = EXAMPLES_DIR / "providers"
    if providers_dir.exists():
        for p in sorted(providers_dir.glob("*/*.py")):
            if p.name == "__init__.py":
                continue
            provider = p.parent.name
            meta = _extract_metadata(p)
            examples.append(
                {
                    "id": f"{provider}/{p.stem}",
                    "name": f"[{provider.title()}] {p.stem.replace('_', ' ').title()}",
                    "path": str(p.relative_to(EXAMPLES_DIR.parent)),
                    "abs_path": str(p),
                    "category": "provider",
                    "provider": provider,
                    **meta,
                }
            )

    return examples


@app.get("/api/examples")
async def list_examples() -> JSONResponse:
    """Return discovered examples."""
    return JSONResponse(discover_examples())


@app.get("/api/code/{example_id:path}")
async def get_code(example_id: str) -> JSONResponse:
    """Return source code for an example."""
    examples = discover_examples()
    for ex in examples:
        if ex["id"] == example_id:
            try:
                code = Path(ex["abs_path"]).read_text()
                return JSONResponse({"code": code, "path": ex["path"]})
            except OSError:
                return JSONResponse({"error": "File not found"}, status_code=404)
    return JSONResponse({"error": "Example not found"}, status_code=404)


@app.websocket("/ws/run/{example_id:path}")
async def run_example(websocket: WebSocket, example_id: str) -> None:
    """Run an example and stream output via WebSocket."""
    await websocket.accept()
    examples = discover_examples()
    target = None
    for ex in examples:
        if ex["id"] == example_id:
            target = ex
            break

    if not target:
        await websocket.send_json({"type": "error", "data": "Example not found"})
        await websocket.close()
        return

    await _run_and_stream(websocket, target["abs_path"], target["id"])


@app.websocket("/ws/run-all")
async def run_all(websocket: WebSocket) -> None:
    """Run all examples sequentially, streaming results."""
    await websocket.accept()
    examples = discover_examples()
    mock = True  # Run All uses mock mode for safety

    await websocket.send_json(
        {
            "type": "run_all_start",
            "data": {"total": len(examples)},
        }
    )

    passed = 0
    failed = 0
    for i, ex in enumerate(examples):
        await websocket.send_json(
            {
                "type": "example_start",
                "data": {"id": ex["id"], "name": ex["name"], "index": i},
            }
        )
        success = await _run_and_stream(websocket, ex["abs_path"], ex["id"], mock=mock)
        if success:
            passed += 1
            await websocket.send_json(
                {
                    "type": "example_result",
                    "data": {"id": ex["id"], "status": "pass", "index": i},
                }
            )
        else:
            failed += 1
            await websocket.send_json(
                {
                    "type": "example_result",
                    "data": {"id": ex["id"], "status": "fail", "index": i},
                }
            )

    await websocket.send_json(
        {
            "type": "run_all_complete",
            "data": {"passed": passed, "failed": failed, "total": len(examples)},
        }
    )
    await websocket.close()


async def _run_and_stream(
    websocket: WebSocket, script_path: str, example_id: str, *, mock: bool = False
) -> bool:
    """Execute a script and stream stdout/stderr lines via WebSocket."""
    env = {**os.environ}
    src_dir = str(Path(__file__).resolve().parent.parent)
    env["PYTHONPATH"] = src_dir + os.pathsep + env.get("PYTHONPATH", "")
    if mock:
        env["SPECOPS_EXAMPLE_MODE"] = "mock"

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
    except OSError as e:
        await websocket.send_json({"type": "error", "data": str(e)})
        return False

    async def stream_pipe(pipe: asyncio.StreamReader, stream: str) -> None:
        while True:
            line = await pipe.readline()
            if not line:
                break
            try:
                await websocket.send_json(
                    {
                        "type": "output",
                        "data": {
                            "line": line.decode(errors="replace"),
                            "stream": stream,
                            "id": example_id,
                        },
                    }
                )
            except WebSocketDisconnect:
                proc.kill()
                return

    assert proc.stdout is not None
    assert proc.stderr is not None
    await asyncio.gather(
        stream_pipe(proc.stdout, "stdout"),
        stream_pipe(proc.stderr, "stderr"),
    )
    await proc.wait()

    success = proc.returncode == 0
    await websocket.send_json(
        {
            "type": "done",
            "data": {
                "id": example_id,
                "returncode": proc.returncode,
                "success": success,
            },
        }
    )
    return success


@app.get("/")
async def index() -> HTMLResponse:
    """Serve the single-page UI."""
    return HTMLResponse(HTML_UI)


HTML_UI = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SpecOps Demo — Visual Examples Runner</title>
<style>
:root {
  --bg: #0d1117; --surface: #161b22; --border: #30363d;
  --text: #e6edf3; --text-muted: #8b949e; --accent: #58a6ff;
  --success: #3fb950; --error: #f85149; --warning: #d29922;
  --code-bg: #1c2128; --sidebar-w: 320px; --output-w: 420px;
  --font: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  --mono: 'SF Mono', 'Fira Code', 'JetBrains Mono', monospace;
}
[data-theme="light"] {
  --bg: #ffffff; --surface: #f6f8fa; --border: #d0d7de;
  --text: #1f2328; --text-muted: #656d76; --accent: #0969da;
  --success: #1a7f37; --error: #cf222e; --warning: #9a6700;
  --code-bg: #f6f8fa;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: var(--font); background: var(--bg); color: var(--text); height: 100vh; overflow: hidden; display: flex; flex-direction: column; }
header { display: flex; align-items: center; justify-content: space-between; padding: 12px 20px; border-bottom: 1px solid var(--border); background: var(--surface); }
header h1 { font-size: 18px; font-weight: 600; }
header h1 span { color: var(--accent); }
.header-actions { display: flex; gap: 8px; align-items: center; }
.btn { padding: 6px 14px; border-radius: 6px; border: 1px solid var(--border); background: var(--surface); color: var(--text); cursor: pointer; font-size: 13px; font-weight: 500; transition: all 0.15s; }
.btn:hover { border-color: var(--accent); color: var(--accent); }
.btn-primary { background: var(--accent); color: #fff; border-color: var(--accent); }
.btn-primary:hover { opacity: 0.9; }
.btn-run-all { background: var(--success); color: #fff; border-color: var(--success); }
.btn-run-all:hover { opacity: 0.9; }
.layout { display: flex; flex: 1; overflow: hidden; }
.sidebar { width: var(--sidebar-w); border-right: 1px solid var(--border); overflow-y: auto; background: var(--surface); flex-shrink: 0; }
.sidebar-header { padding: 12px 16px; border-bottom: 1px solid var(--border); font-size: 12px; font-weight: 600; text-transform: uppercase; color: var(--text-muted); letter-spacing: 0.5px; }
.example-item { padding: 10px 16px; cursor: pointer; border-bottom: 1px solid var(--border); transition: background 0.1s; }
.example-item:hover { background: var(--bg); }
.example-item.active { background: var(--bg); border-left: 3px solid var(--accent); }
.example-item .name { font-size: 13px; font-weight: 500; margin-bottom: 2px; }
.example-item .desc { font-size: 11px; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.example-item .tag { display: inline-block; font-size: 10px; padding: 1px 6px; border-radius: 10px; background: var(--accent); color: #fff; margin-top: 4px; opacity: 0.8; }
.example-item .status-icon { float: right; font-size: 14px; }
.main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.main-header { display: flex; align-items: center; justify-content: space-between; padding: 10px 16px; border-bottom: 1px solid var(--border); background: var(--surface); }
.main-header .filepath { font-family: var(--mono); font-size: 12px; color: var(--text-muted); }
.code-area { flex: 1; overflow: auto; padding: 16px; background: var(--code-bg); }
.code-area pre { font-family: var(--mono); font-size: 13px; line-height: 1.6; white-space: pre; tab-size: 4; color: var(--text); }
.output-panel { width: var(--output-w); border-left: 1px solid var(--border); display: flex; flex-direction: column; background: var(--surface); flex-shrink: 0; }
.output-header { padding: 10px 16px; border-bottom: 1px solid var(--border); font-size: 12px; font-weight: 600; text-transform: uppercase; color: var(--text-muted); letter-spacing: 0.5px; display: flex; justify-content: space-between; align-items: center; }
.output-content { flex: 1; overflow-y: auto; overflow-x: auto; padding: 12px; font-family: var(--mono); font-size: 12px; line-height: 1.5; }
.output-content .line { white-space: pre; }
.output-content .stderr { color: var(--error); }
.output-content .stdout { color: var(--text); }
.output-content .system { color: var(--accent); font-style: italic; }
.collapsible { border-top: 1px solid var(--border); }
.collapsible summary { padding: 8px 16px; font-size: 11px; font-weight: 600; text-transform: uppercase; color: var(--text-muted); cursor: pointer; letter-spacing: 0.5px; }
.collapsible .content { padding: 8px 16px; font-family: var(--mono); font-size: 11px; color: var(--text-muted); max-height: 120px; overflow-y: auto; }
.empty-state { display: flex; align-items: center; justify-content: center; height: 100%; color: var(--text-muted); font-size: 14px; flex-direction: column; gap: 8px; }
.run-all-results { padding: 12px; }
.run-all-item { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 12px; }
.run-all-item .icon { font-size: 14px; }
.run-all-item.pass .icon { color: var(--success); }
.run-all-item.fail .icon { color: var(--error); }
.run-all-item.running .icon { color: var(--warning); }
@media (max-width: 1200px) { :root { --output-w: 320px; --sidebar-w: 260px; } }
</style>
</head>
<body>
<header>
  <h1><span>SpecOps</span> Demo</h1>
  <div class="header-actions">
    <button class="btn btn-run-all" onclick="runAll()">▶ Run All</button>
    <button class="btn" onclick="toggleTheme()">◐ Theme</button>
  </div>
</header>
<div class="layout">
  <aside class="sidebar">
    <div class="sidebar-header">Examples <span id="example-count"></span></div>
    <div id="example-list"></div>
  </aside>
  <main class="main">
    <div class="main-header">
      <span class="filepath" id="filepath">Select an example</span>
      <button class="btn btn-primary" id="run-btn" onclick="runSelected()" disabled>▶ Run Example</button>
    </div>
    <div class="code-area"><pre id="code-view"><div class="empty-state">← Select an example to view its source code</div></pre></div>
  </main>
  <aside class="output-panel">
    <div class="output-header"><span>Output</span><button class="btn" onclick="clearOutput()" style="padding:2px 8px;font-size:11px;">Clear</button></div>
    <div class="output-content" id="output"></div>
    <details class="collapsible" open>
      <summary>Traces</summary>
      <div class="content" id="traces-panel">Run an example to see traces...</div>
    </details>
    <details class="collapsible" open>
      <summary>Health Score</summary>
      <div class="content" id="health-panel">Run an example to see health data...</div>
    </details>
    <details class="collapsible" open>
      <summary>Replay Summary</summary>
      <div class="content" id="replay-panel">Run an example to see replay data...</div>
    </details>
  </aside>
</div>
<script>
let examples = [];
let selected = null;
let ws = null;
let runAllResults = {};

async function init() {
  const res = await fetch('/api/examples');
  examples = await res.json();
  document.getElementById('example-count').textContent = `(${examples.length})`;
  renderList();
}

function renderList() {
  const el = document.getElementById('example-list');
  el.innerHTML = examples.map((ex, i) => `
    <div class="example-item ${selected === ex.id ? 'active' : ''}" onclick="selectExample('${ex.id}')" id="item-${i}">
      <span class="status-icon" id="status-${ex.id.replace(/\\//g, '-')}"></span>
      <div class="name">${ex.name}</div>
      <div class="desc">${ex.description}</div>
      <span class="tag">${ex.tag}</span>
    </div>
  `).join('');
}

async function selectExample(id) {
  selected = id;
  renderList();
  document.getElementById('run-btn').disabled = false;
  const res = await fetch(`/api/code/${encodeURIComponent(id)}`);
  const data = await res.json();
  document.getElementById('filepath').textContent = data.path || '';
  document.getElementById('code-view').textContent = data.code || data.error || '';
}

function runSelected() {
  if (!selected) return;
  clearOutput();
  appendOutput('system', `▶ Running ${selected}...\\n`);
  if (ws) ws.close();
  ws = new WebSocket(`ws://${location.host}/ws/run/${encodeURIComponent(selected)}`);
  ws.onmessage = (e) => handleMessage(JSON.parse(e.data));
  ws.onerror = () => appendOutput('stderr', 'WebSocket error\\n');
}

function runAll() {
  clearOutput();
  runAllResults = {};
  examples.forEach(ex => {
    const el = document.getElementById(`status-${ex.id.replace(/\\//g, '-')}`);
    if (el) el.textContent = '';
  });
  appendOutput('system', '▶ Running all examples (mock mode)...\\n\\n');
  if (ws) ws.close();
  ws = new WebSocket(`ws://${location.host}/ws/run-all`);
  ws.onmessage = (e) => handleMessage(JSON.parse(e.data));
  ws.onerror = () => appendOutput('stderr', 'WebSocket error\\n');
}

function handleMessage(msg) {
  switch (msg.type) {
    case 'output':
      appendOutput(msg.data.stream, msg.data.line);
      parseSpecialOutput(msg.data.line);
      break;
    case 'done':
      appendOutput('system', `\\n${msg.data.success ? '✓' : '✗'} Finished (exit ${msg.data.returncode})\\n`);
      break;
    case 'example_start':
      appendOutput('system', `\\n━━━ ${msg.data.name} ━━━\\n`);
      setStatus(msg.data.id, 'running');
      break;
    case 'example_result':
      setStatus(msg.data.id, msg.data.status);
      break;
    case 'run_all_start':
      appendOutput('system', `Running ${msg.data.total} examples...\\n`);
      break;
    case 'run_all_complete':
      appendOutput('system', `\\n${'═'.repeat(40)}\\n✓ ${msg.data.passed} passed, ✗ ${msg.data.failed} failed (${msg.data.total} total)\\n`);
      break;
    case 'error':
      appendOutput('stderr', `Error: ${msg.data}\\n`);
      break;
  }
}

function setStatus(id, status) {
  const el = document.getElementById(`status-${id.replace(/\\//g, '-')}`);
  if (!el) return;
  if (status === 'pass') el.textContent = '✓';
  else if (status === 'fail') el.textContent = '✗';
  else el.textContent = '⟳';
  el.style.color = status === 'pass' ? 'var(--success)' : status === 'fail' ? 'var(--error)' : 'var(--warning)';
}

function parseSpecialOutput(line) {
  if (line.includes('Trace') || line.includes('span') || line.includes('otel'))
    document.getElementById('traces-panel').textContent += line;
  if (line.includes('health') || line.includes('score') || line.includes('Grade'))
    document.getElementById('health-panel').textContent += line;
  if (line.includes('replay') || line.includes('Replay') || line.includes('session'))
    document.getElementById('replay-panel').textContent += line;
}

function appendOutput(stream, text) {
  const el = document.getElementById('output');
  const span = document.createElement('span');
  span.className = `line ${stream}`;
  span.textContent = text;
  el.appendChild(span);
  el.scrollTop = el.scrollHeight;
}

function clearOutput() {
  document.getElementById('output').innerHTML = '';
  document.getElementById('traces-panel').textContent = '';
  document.getElementById('health-panel').textContent = '';
  document.getElementById('replay-panel').textContent = '';
}

function toggleTheme() {
  const t = document.documentElement.getAttribute('data-theme');
  document.documentElement.setAttribute('data-theme', t === 'light' ? '' : 'light');
}

init();
</script>
</body>
</html>
"""


def main() -> None:
    """Entry point for the specops-demo CLI command."""
    import uvicorn

    port = int(os.environ.get("SPECOPS_DEMO_PORT", "8420"))
    host = os.environ.get("SPECOPS_DEMO_HOST", "127.0.0.1")

    print("\n  SpecOps Demo — Visual Examples Runner")
    print(f"  http://{host}:{port}\n")

    webbrowser.open(f"http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
