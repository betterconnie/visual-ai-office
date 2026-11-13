#!/usr/bin/env python3
"""Claude Code hook -> Visual AI Office.  Claude Code 的 hook：把「開始工作／做完／開關對話」回報給可視化辦公室。

Reads the hook event JSON on stdin and POSTs one status line to the office server.
Sends only: which character, online/busy, and the working folder's name. Never the prompt or any conversation text.
Fails silently and quickly so it can never slow down or block Claude Code.

Env:  OFFICE_ID  (default "bear")   OFFICE_URL  (default "http://127.0.0.1:8765")
"""
import json, os, sys, urllib.request

# PostToolUse is the heartbeat: the office marks a character offline after 10 minutes of silence, and one turn can run longer.
STATE = {"SessionStart": (True, False), "UserPromptSubmit": (True, True), "PostToolUse": (True, True), "Stop": (True, False)}


def main():
    try:
        ev = json.load(sys.stdin)
    except Exception:
        ev = {}
    name = ev.get("hook_event_name") or (sys.argv[1] if len(sys.argv) > 1 else "")
    if name not in STATE:
        return
    online, busy = STATE[name]
    body = {"id": os.environ.get("OFFICE_ID", "bear"), "online": online, "busy": busy}
    if busy:
        body["doing"] = os.path.basename((ev.get("cwd") or os.getcwd()).rstrip("/\\"))[:40]
    req = urllib.request.Request(os.environ.get("OFFICE_URL", "http://127.0.0.1:8765").rstrip("/") + "/update",
                                 data=json.dumps(body).encode(), headers={"X-Office": "1", "Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=2)
    except Exception:
        pass  # office not running: do nothing


if __name__ == "__main__":
    main()
