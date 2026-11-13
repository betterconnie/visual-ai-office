#!/usr/bin/env python3
"""One-line setup: connect Claude Code to the Visual AI Office.  一行安裝：把 Claude Code 接上可視化辦公室。

    python3 integrations/claude-code/install.py            # Claude Code = the bear
    python3 integrations/claude-code/install.py --id fox   # pick another character
    python3 integrations/claude-code/install.py --remove   # undo

Adds four hooks to ~/.claude/settings.json (a backup is written next to it first). Existing hooks are kept.
"""
import argparse, json, pathlib, shutil, sys, time

IDS = ("fox", "bird", "bear", "cat", "raccoon", "crab")
EVENTS = ("SessionStart", "UserPromptSubmit", "PostToolUse", "Stop")
MARK = "office_hook.py"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", default="bear", choices=IDS)
    ap.add_argument("--url", default="http://127.0.0.1:8765")
    ap.add_argument("--settings", default=str(pathlib.Path.home() / ".claude" / "settings.json"))
    ap.add_argument("--remove", action="store_true")
    a = ap.parse_args()
    path = pathlib.Path(a.settings)
    try:
        cfg = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        assert isinstance(cfg, dict)
    except Exception:
        sys.exit(f"{path} is not valid JSON. Nothing was changed.  設定檔不是合法的 JSON，沒有做任何修改。")
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + f".bak-{time.strftime('%Y%m%d-%H%M%S')}"))
    hooks = cfg.setdefault("hooks", {})
    for ev in EVENTS:  # drop our old entries first, so running twice never duplicates
        kept = []
        for group in hooks.get(ev, []):
            group["hooks"] = [h for h in group.get("hooks", []) if MARK not in h.get("command", "")]
            if group["hooks"]:
                kept.append(group)
        if kept:
            hooks[ev] = kept
        else:
            hooks.pop(ev, None)
    if not a.remove:
        script = pathlib.Path(__file__).resolve().with_name(MARK)
        py = "python" if sys.platform == "win32" else "python3"
        env = (f'set "OFFICE_ID={a.id}" && set "OFFICE_URL={a.url}" && ' if sys.platform == "win32"
               else f"OFFICE_ID={a.id} OFFICE_URL={a.url} ")
        for ev in EVENTS:
            hooks.setdefault(ev, []).append({"hooks": [{"type": "command", "command": f'{env}{py} "{script}"', "timeout": 5}]})
    if not hooks:
        cfg.pop("hooks", None)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(("Removed." if a.remove else f"Done. Claude Code now reports as '{a.id}'.") + " Start a new Claude Code session to load it.")
    print("已移除。" if a.remove else f"完成。Claude Code 之後會以「{a.id}」回報。" , "開一個新的 Claude Code 對話就會生效。")


if __name__ == "__main__":
    main()
