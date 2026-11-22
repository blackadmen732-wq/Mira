#!/usr/bin/env python3
# Mira's eyes and hands (owner's request, Nov 22 2026): see the screen, move the mouse, type, press keys, open pages.
# A tiny MCP server (stdio, Python standard library only) that Claude Code loads as the "computer" tools.
# The terminal itself is Claude Code's own Bash tool.
# Needs (Linux): xdotool, scrot or ImageMagick `import`, optional tesseract (reads the words on screen, so a model
# that can't see pictures still knows where to click), wmctrl (window list). install.sh installs them.
# On a Chromebook this reaches the Linux apps (terminal, Linux Chrome/Firefox, VS Code...), not ChromeOS itself.
# Stop: Ctrl+C in Mira, or move the mouse into the top-left corner (every action checks it first).
import base64, json, os, shutil, subprocess, sys, tempfile

VERSION = "2024-11-05"
MAX_W = int(os.environ.get("MIRA_SCREEN_WIDTH", "1280"))      # screenshots are shrunk to this width for the model
STATE = {"scale": 1.0}

TOOLS = [
    {"name": "screen_look", "description": "Take a screenshot. Returns the picture plus the words on screen with their x,y "
     "positions (in the same coordinates the mouse tools use). Look before you click.",
     "inputSchema": {"type": "object", "properties": {"words": {"type": "boolean", "description": "also read the words (default true)"}}}},
    {"name": "mouse_click", "description": "Click at x,y (coordinates from screen_look).",
     "inputSchema": {"type": "object", "required": ["x", "y"], "properties": {
         "x": {"type": "number"}, "y": {"type": "number"}, "button": {"type": "string", "enum": ["left", "right", "middle"]},
         "double": {"type": "boolean"}}}},
    {"name": "mouse_move", "description": "Move the mouse to x,y.",
     "inputSchema": {"type": "object", "required": ["x", "y"], "properties": {"x": {"type": "number"}, "y": {"type": "number"}}}},
    {"name": "mouse_drag", "description": "Drag from x1,y1 to x2,y2 with the left button.",
     "inputSchema": {"type": "object", "required": ["x1", "y1", "x2", "y2"], "properties": {k: {"type": "number"} for k in ("x1", "y1", "x2", "y2")}}},
    {"name": "scroll", "description": "Scroll the window under the mouse.",
     "inputSchema": {"type": "object", "required": ["direction"], "properties": {
         "direction": {"type": "string", "enum": ["up", "down", "left", "right"]}, "amount": {"type": "integer"}}}},
    {"name": "type_text", "description": "Type text where the cursor is.",
     "inputSchema": {"type": "object", "required": ["text"], "properties": {"text": {"type": "string"}}}},
    {"name": "press_key", "description": "Press a key or combo, e.g. Return, Escape, ctrl+c, ctrl+shift+t, alt+Tab.",
     "inputSchema": {"type": "object", "required": ["keys"], "properties": {"keys": {"type": "string"}}}},
    {"name": "open_url", "description": "Open a web page (http/https) in the default browser.",
     "inputSchema": {"type": "object", "required": ["url"], "properties": {"url": {"type": "string"}}}},
    {"name": "list_windows", "description": "List open windows (id and title).", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "focus_window", "description": "Bring the first window whose title contains `title` to the front.",
     "inputSchema": {"type": "object", "required": ["title"], "properties": {"title": {"type": "string"}}}},
]


class Stop(Exception): pass


def run(*cmd, inp=None):
    r = subprocess.run(cmd, input=inp, capture_output=True, text=True, timeout=30)
    if r.returncode: raise RuntimeError((r.stderr or r.stdout or f"{cmd[0]} failed").strip()[:300])
    return r.stdout


def need(tool):
    if not shutil.which(tool): raise RuntimeError(f"{tool} isn't installed. Run: bash ~/mira/install.sh")


def real(v): return str(int(round(float(v) * STATE["scale"])))   # model coordinates -> real screen pixels


def guard():
    """Owner's emergency stop: mouse in the top-left corner (within 5 px) blocks every action."""
    try:
        loc = dict(p.split(":") for p in run("xdotool", "getmouselocation").split()[:2])
        if int(loc["x"]) <= 5 and int(loc["y"]) <= 5: raise Stop("Stopped: the mouse is in the top-left corner (emergency stop). Move it away to continue.")
    except Stop: raise
    except Exception: pass


def screenshot():
    path = tempfile.mktemp(suffix=".png")
    if shutil.which("scrot"): run("scrot", "-o", path)
    elif shutil.which("import"): run("import", "-window", "root", path)
    else: raise RuntimeError("No screenshot tool. Run: bash ~/mira/install.sh")
    w = int(run("identify", "-format", "%w", path)) if shutil.which("identify") else MAX_W
    STATE["scale"] = max(1.0, w / MAX_W)
    if w > MAX_W and shutil.which("convert"): run("convert", path, "-resize", f"{MAX_W}x", path)
    return path, w


def words(path):
    if not shutil.which("tesseract"): return "(install tesseract to also get the words on screen)"
    out, lines = run("tesseract", path, "-", "tsv"), {}
    for row in out.splitlines()[1:]:
        c = row.split("\t")
        if len(c) < 12 or not c[11].strip() or float(c[10] or -1) < 50: continue
        key = (c[2], c[3], c[4])                                  # block, paragraph, line
        x, y, wd, ht = map(int, c[6:10]); lines.setdefault(key, []).append((x, y, wd, ht, c[11]))
    res = []
    for ws in lines.values():
        x0, y0 = ws[0][0], min(w[1] for w in ws); x1 = max(w[0] + w[2] for w in ws); y1 = max(w[1] + w[3] for w in ws)
        res.append(f"({(x0 + x1) // 2},{(y0 + y1) // 2}) " + " ".join(w[4] for w in ws))
    return "Words on screen (center x,y then text):\n" + "\n".join(res[:250]) if res else "No readable words on screen."


def call(name, a):
    if name == "screen_look":
        path, w = screenshot()
        try:
            img = base64.b64encode(open(path, "rb").read()).decode()
            text = f"Screenshot ({MAX_W if w > MAX_W else w}px wide; use these coordinates)."
            if a.get("words", True): text += "\n" + words(path)
        finally: os.unlink(path)
        return [{"type": "text", "text": text}, {"type": "image", "data": img, "mimeType": "image/png"}]
    if name == "open_url":
        u = str(a["url"])
        if not u.startswith(("http://", "https://")): raise RuntimeError("only http/https links")
        subprocess.Popen(["xdg-open", u], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); return f"opened {u}"
    if name == "list_windows":
        if shutil.which("wmctrl"): return run("wmctrl", "-l") or "no windows"
        need("xdotool"); ids = run("xdotool", "search", "--onlyvisible", "--name", ".").split()
        return "\n".join(f"{i} {run('xdotool', 'getwindowname', i).strip()}" for i in ids[:60]) or "no windows"
    need("xdotool"); guard()
    if name == "mouse_click":
        b = {"left": "1", "middle": "2", "right": "3"}[a.get("button", "left")]
        run("xdotool", "mousemove", real(a["x"]), real(a["y"]), "click", *(["--repeat", "2"] if a.get("double") else []), b)
        return f"clicked {a.get('button', 'left')} at {a['x']},{a['y']}"
    if name == "mouse_move": run("xdotool", "mousemove", real(a["x"]), real(a["y"])); return "moved"
    if name == "mouse_drag":
        run("xdotool", "mousemove", real(a["x1"]), real(a["y1"]), "mousedown", "1", "mousemove", real(a["x2"]), real(a["y2"]), "mouseup", "1")
        return "dragged"
    if name == "scroll":
        b = {"up": "4", "down": "5", "left": "6", "right": "7"}[a["direction"]]
        run("xdotool", "click", "--repeat", str(max(1, min(int(a.get("amount", 3)), 30))), b); return f"scrolled {a['direction']}"
    if name == "type_text": run("xdotool", "type", "--delay", "8", "--", str(a["text"])); return f"typed {len(str(a['text']))} characters"
    if name == "press_key": run("xdotool", "key", "--", *str(a["keys"]).split()); return f"pressed {a['keys']}"
    if name == "focus_window":
        ids = run("xdotool", "search", "--onlyvisible", "--name", str(a["title"])).split()
        if not ids: return f"no window with '{a['title']}' in its title"
        run("xdotool", "windowactivate", ids[0]); return f"focused {run('xdotool', 'getwindowname', ids[0]).strip()}"
    raise RuntimeError(f"unknown tool {name}")


def handle(msg):
    mid, method, p = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if method == "initialize":
        return {"protocolVersion": p.get("protocolVersion", VERSION), "capabilities": {"tools": {}},
                "serverInfo": {"name": "mira-computer", "version": "1.0"}}
    if method == "tools/list": return {"tools": TOOLS}
    if method == "tools/call":
        try:
            out = call(p.get("name"), p.get("arguments") or {})
            return {"content": out if isinstance(out, list) else [{"type": "text", "text": str(out)}]}
        except Exception as e: return {"content": [{"type": "text", "text": str(e)}], "isError": True}
    if method == "ping": return {}
    if mid is not None: raise LookupError(method)
    return None


def main():
    for line in sys.stdin:
        if not line.strip(): continue
        try: msg = json.loads(line)
        except ValueError: continue
        try: res = handle(msg)
        except LookupError: res = None; reply = {"jsonrpc": "2.0", "id": msg.get("id"), "error": {"code": -32601, "message": "method not found"}}
        else: reply = {"jsonrpc": "2.0", "id": msg.get("id"), "result": res}
        if msg.get("id") is None: continue                        # notifications get no answer
        sys.stdout.write(json.dumps(reply) + "\n"); sys.stdout.flush()


if __name__ == "__main__":
    main()
