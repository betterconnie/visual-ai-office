#!/usr/bin/env python3
"""可視化辦公室伺服器。只用 Python 3 標準函式庫（3.9 以上）。

啟動：python3 server.py [--port N] [--lang zh|en]   （設定讀同資料夾的 office.config.json）
- 示範模式（"demo": true，預設）：伺服器自己演一段循環的「一天」，不需要任何外部資料。
- 正式模式（"demo": false）：由你自己的程式用 POST /update、/talk、/mail、/api 回報狀態。
"""
import argparse, functools, http.server, json, pathlib, re, threading, time
from urllib.parse import unquote

HERE = pathlib.Path(__file__).resolve().parent
ART = HERE / "art"
IDS = ("boss", "fox", "bird", "bear", "cat", "raccoon", "crab")
DEFAULT_CAST = {
    "boss": {"name": "老闆", "role": "所有對外行動由老闆核准"},
    "fox": {"name": "狐狸", "role": "總協調，派工給大家"},
    "bird": {"name": "藍鳥", "role": "研究、寫作"},
    "bear": {"name": "小熊", "role": "判斷、把關、最後品管"},
    "cat": {"name": "紫貓", "role": "美術、影音"},
    "raccoon": {"name": "浣熊", "role": "寫程式、自動化"},
    "crab": {"name": "螃蟹", "role": "批次工作，關在隔離沙盒"},
}
OFFLINE_AFTER = 600   # 超過 10 分鐘沒 /update 就算離線（老闆除外）
TALK_KEEP = 1800      # 傳話只留 30 分鐘
LOCK = threading.Lock()


def load_config():
    try:
        cfg = json.loads((HERE / "office.config.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        cfg = {}
    cast = {k: dict(v) for k, v in DEFAULT_CAST.items()}
    for k, v in (cfg.get("cast") or {}).items():
        if k in cast and isinstance(v, dict):
            cast[k].update(v)
    return {"port": int(cfg.get("port", 8765)), "bind": cfg.get("bind") or ["127.0.0.1"],
            "demo": bool(cfg.get("demo", True)), "cast": cast,
            "lang": cfg.get("lang") if cfg.get("lang") in ("zh", "en") else None}


CFG = load_config()
DEMO = CFG["demo"]
LANG = CFG["lang"]  # "zh"／"en"／None（None：網頁看瀏覽器語言，示範文字用中文）；--lang 可覆蓋

# ── 重點回放：發生過的事（誰找誰、交代、回報、做完、卡住）。正式模式才存檔，示範模式只放記憶體 ──
EVENTS_FILE = HERE / "events.json"
EVENTS = []
if not DEMO:
    try:
        EVENTS = json.loads(EVENTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        EVENTS = []
_ev_keys = {(e["type"], e["who"], e.get("to"), int(e["t"])) for e in EVENTS}
_prev = {}
GOOD = ("task", "report", "talk", "chat", "done")  # 算進每週榜單的事


def add_event(t, type_, who, to=None, tag=""):
    k = (type_, who, to, int(t))
    if k in _ev_keys or any(e["type"] == type_ and e["who"] == who and e.get("to") == to and abs(e["t"] - t) < 20 for e in EVENTS[-30:]):
        return
    _ev_keys.add(k)
    EVENTS.append({"t": t, "type": type_, "who": who, "to": to, "tag": tag or ""})
    EVENTS.sort(key=lambda e: e["t"])
    del EVENTS[:-1500]
    if not DEMO:
        try:
            EVENTS_FILE.write_text(json.dumps(EVENTS, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass


def flags(who, now):
    """專案牆上的標記，全部由真實狀態推出來：
    loop 鬼打牆＝連續忙 45 分鐘以上、這段時間沒有任何回報或完成；thief 薪水小偷＝有工作在等卻閒著 30 分鐘以上，或有人找卻不接；
    gone 沒請假就消失＝不在線上，卻還有人在找他或有工作排著；work_min＝已經連續工作幾分鐘。"""
    for k, w in who.items():
        if k == "boss":
            continue
        p = _prev.get(k)
        dur = now - p["since"] if p else 0
        recent = any(e["who"] == k and now - e["t"] < 2700 for e in EVENTS[-300:])
        f = []
        if w.get("online") and w.get("busy"):
            w["work_min"] = int(dur / 60)
            if dur >= 2700 and not recent:
                f.append("loop")
        elif w.get("online") and (w.get("state") == "ghost" or ((w.get("queue") or 0) > 0 and dur >= 1800)):
            f.append("thief")
        elif not w.get("online") and ((w.get("queue") or 0) > 0 or any(x.get("seek") == k for x in who.values())):
            f.append("gone")
        w["flags"] = f


def note_events(who, talks, now):
    """把傳話記成事件，並比對上一次的狀態，記下上線／下線、做完、倒下、失敗、沒接、找人。"""
    for x in talks:
        if now - x["t"] < 3600:
            add_event(x["t"], "chat" if x["to"] == "boss" else x.get("kind") or "talk", x["from"], x["to"], x.get("tag", ""))
    for k, w in who.items():
        if k == "boss":
            continue
        cur = {"on": bool(w.get("online")), "busy": bool(w.get("busy")), "state": w.get("state"), "seek": w.get("seek"),
               "ko": w.get("hp") is not None and w["hp"] <= 0, "doing": w.get("doing") or "", "since": now}
        old = _prev.get(k)
        if old:
            cur["since"] = old["since"] if old["busy"] == cur["busy"] else now
            if old["busy"] and not cur["busy"] and now - old["since"] >= 120:
                add_event(now, "done", k, tag=old["doing"][:16])
            if cur["on"] != old["on"]:
                add_event(now, "in" if cur["on"] else "out", k)
            if cur["ko"] and not old["ko"]:
                add_event(now, "ko", k)
            if cur["state"] != old["state"] and cur["state"] in ("fail", "ghost"):
                add_event(now, cur["state"], k)
            if cur["seek"] and cur["seek"] != old["seek"]:
                add_event(now, "seek", k, cur["seek"])
        _prev[k] = cur


def recent_shots(n=9):
    """重點回放的九格：同兩個人 10 分鐘內的來回訊息合併成一格。新的在前。"""
    out, rank = [], {"task": 3, "report": 2, "talk": 1}
    for e in reversed(EVENTS):
        pair = e["type"] in rank and e.get("to")
        g = out[-1] if out else None
        if pair and g and g.get("pair") == frozenset((e["who"], e["to"])) and g["first"] - e["t"] < 600:
            g["n"] += 1
            g["first"] = e["t"]
            g["who"], g["to"] = e["who"], e["to"]          # 最早那一則是誰先開口
            if rank[e["type"]] > rank[g["type"]]:
                g["type"] = e["type"]
            g["tag"] = g["tag"] or e.get("tag", "")
            continue
        if len(out) == n:
            break
        out.append({**e, "n": 1, "first": e["t"], "pair": frozenset((e["who"], e["to"])) if pair else None})
    return [{k: v for k, v in g.items() if k != "pair"} for g in out]


def board(now):
    """每週榜單：這週（週一 00:00 起）在重點回放出現最多次的人。只算正面的事（GOOD）。"""
    lt = time.localtime(now)
    monday = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1)) - lt.tm_wday * 86400

    def rank(a, b):
        out = {}
        for e in EVENTS:
            if a <= e["t"] < b and e["type"] in GOOD:
                for k in {e["who"], e.get("to")} - {None, "boss"}:
                    r = out.setdefault(k, {"id": k, "n": 0, "c": {}, "tags": {}})
                    r["n"] += 1
                    r["c"][e["type"]] = r["c"].get(e["type"], 0) + 1
                    if e.get("tag"):
                        r["tags"][e["tag"]] = r["tags"].get(e["tag"], 0) + 1
        rows = sorted(out.values(), key=lambda r: -r["n"])
        for r in rows:
            r["tags"] = [t for t, _ in sorted(r["tags"].items(), key=lambda x: -x[1])[:3]]
        return rows
    today = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))  # 每日之星：每天半夜歸零，last＝昨天的第一名
    last = rank(today - 86400, today)
    return {"since": today, "rows": rank(today, now + 1), "last": last[0]["id"] if last else None}


# ── 示範模式：依時間決定的場景表，每幕 24 秒，循環播放 ──
SCENE_LEN = 24
SCENES = [
    {"name": "早上上工", "boss": 0, "api": {"voice": {"state": "send", "balance": "$12"}},
     "who": {"fox": {"hp": 90, "busy_n": 3, "doing": "排今天的工作"}, "bird": {"hp": 75, "doing": "查資料"},
             "bear": {"hp": 60, "doing": "看昨天的成品"}, "cat": {"hp": 45, "doing": "畫角色"},
             "raccoon": {"hp": 85, "doing": "寫網頁"}, "crab": {"hp": 70, "doing": "批次轉檔"}},
     "talks": [("fox", "bird", "task", "研究"), ("fox", "raccoon", "task", "網站")]},
    {"name": "回報與討論", "boss": 0, "api": {"video": {"state": "send", "balance": "$30"}},
     "who": {"fox": {"hp": 88, "busy_n": 3, "doing": "整理回報"}, "bird": {"hp": 70, "doing": "寫摘要"},
             "bear": {"hp": 58, "doing": "品管"}, "cat": {"hp": 25, "doing": "趕影片"},
             "raccoon": {"hp": 80, "queue": 6, "doing": "修程式"}, "crab": {"hp": 66, "doing": "批次轉檔"}},
     "talks": [("bird", "fox", "report", "研究"), ("bear", "cat", "", "影片")]},
    {"name": "沙盒交件", "boss": 2, "api": {"paint": {"state": "send", "balance": "$5"}},
     "who": {"fox": {"hp": 85, "doing": "派品管"}, "bird": {"hp": 68, "doing": "寫草稿"},
             "bear": {"hp": 55, "busy_n": 3, "doing": "同時審三件"}, "cat": {"hp": 20, "doing": "趕影片"},
             "raccoon": {"hp": 78, "queue": 5, "doing": "修程式"}, "crab": {"hp": 60, "doing": "交批次結果"}},
     "talks": [("crab", "fox", "report", "批次"), ("fox", "bear", "task", "品管")]},
    {"name": "額度用完、找不到人", "boss": 2, "api": {"video": {"state": "send", "balance": "$28"}},
     "who": {"fox": {"hp": 82, "doing": "盯進度"}, "bird": {"hp": 64, "seek": "raccoon", "doing": "找浣熊"},
             "bear": {"hp": 52, "doing": "品管"}, "cat": {"hp": 0, "note": "額度用完，明天恢復"},
             "raccoon": {"online": False, "busy": False, "busy_n": 0}, "crab": {"hp": 58, "doing": "批次轉檔"}},
     "talks": [("fox", "cat", "", "額度")]},
    {"name": "任務失敗、訊息沒人接", "boss": 3, "api": {"video": {"state": "fail", "balance": "$0"}},
     "who": {"fox": {"hp": 80, "busy_n": 3, "doing": "處理狀況"}, "bird": {"hp": 60, "seek": "bear", "doing": "等小熊回覆"},
             "bear": {"hp": 50, "state": "ghost", "note": "藍鳥的訊息 6 分鐘沒接"},
             "cat": {"hp": 0, "note": "額度用完，明天恢復"},
             "raccoon": {"hp": 76, "state": "fail", "note": "部署失敗"}, "crab": {"hp": 55, "doing": "批次轉檔"}},
     "talks": [("raccoon", "fox", "report", "部署")]},
    {"name": "修好了", "boss": 3, "api": {"paint": {"state": "send", "balance": "$5"}},
     "who": {"fox": {"hp": 78, "doing": "重新派工"}, "bird": {"hp": 58, "doing": "改稿"},
             "bear": {"hp": 48, "doing": "品管"}, "cat": {"hp": 60, "doing": "重畫背景"},
             "raccoon": {"hp": 72, "doing": "修部署"}, "crab": {"hp": 50, "doing": "批次轉檔"}},
     "talks": [("fox", "raccoon", "task", "修正"), ("bird", "bear", "", "草稿")]},
    {"name": "收信", "boss": 1, "api": {"voice": {"state": "send", "balance": "$10"}},
     "who": {"fox": {"hp": 76, "busy": False, "busy_n": 0}, "bird": {"hp": 55, "doing": "改稿"},
             "bear": {"hp": 45, "doing": "最後品管"}, "cat": {"hp": 55, "doing": "重畫背景"},
             "raccoon": {"hp": 70, "doing": "修部署"}, "crab": {"hp": 48, "doing": "批次轉檔"}},
     "talks": [("bear", "fox", "report", "品管"), ("raccoon", "fox", "report", "修正")]},
    {"name": "全員休息", "boss": 1, "api": {},
     "who": {k: {"hp": hp, "busy": False, "busy_n": 0} for k, hp in
             (("fox", 75), ("bird", 54), ("bear", 44), ("cat", 52), ("raccoon", 68), ("crab", 46))},
     "talks": []},
]
# 示範文字的英文版（lang 是 en 時用）
EN = {
    "排今天的工作": "Planning the day", "查資料": "Researching", "看昨天的成品": "Reviewing output", "畫角色": "Drawing sprites",
    "寫網頁": "Building a site", "批次轉檔": "Batch converting", "整理回報": "Sorting reports", "寫摘要": "Writing summary",
    "品管": "QA", "趕影片": "Rushing a video", "修程式": "Fixing code", "派品管": "Assigning QA", "寫草稿": "Writing a draft",
    "同時審三件": "Reviewing 3 jobs", "交批次結果": "Handing in batch", "盯進度": "Checking status", "找浣熊": "Finding Raccoon",
    "處理狀況": "Handling issues", "等小熊回覆": "Waiting on Bear", "重新派工": "Reassigning work", "改稿": "Revising draft",
    "重畫背景": "Redrawing scene", "修部署": "Fixing deploy", "最後品管": "Final QA",
    "額度用完，明天恢復": "Out of quota, back tomorrow", "藍鳥的訊息 6 分鐘沒接": "Bird's message: no reply for 6 min", "部署失敗": "Deploy failed",
    "研究": "Research", "網站": "Website", "影片": "Video", "批次": "Batch", "額度": "Quota", "部署": "Deploy", "修正": "Fix", "草稿": "Draft",
}


def tr(text):
    return EN.get(text, text) if LANG == "en" else text


CYCLE = SCENE_LEN * len(SCENES)
MAIL_SCENE = 6  # 「收信」那一幕：狐狸去收信


def demo_scene(now):
    k = int(now // SCENE_LEN)
    sc, start = SCENES[k % len(SCENES)], k * SCENE_LEN
    who = {}
    for i in IDS:
        w = {"online": True, "busy": i != "boss", "busy_n": int(i != "boss"), "queue": 0, "doing": "", "note": ""}
        w.update(sc["who"].get(i, {}))
        w["doing"], w["note"] = tr(w["doing"]), tr(w["note"])
        who[i] = w
    who["boss"].update(queue=sc["boss"], waiting=[])
    talks = [{"from": a, "to": b, "t": start, "kind": kd, "tag": tr(tg)} for a, b, kd, tg in sc["talks"]]
    mail = now // CYCLE * CYCLE + MAIL_SCENE * SCENE_LEN
    if mail > now:
        mail -= CYCLE
    return who, talks, json.loads(json.dumps(sc["api"])), mail


def demo_backfill(now, cycles=2):
    """啟動時把前兩輪補演一遍，第一次打開就有重點回放和榜單可看。"""
    t = (now // SCENE_LEN - cycles * len(SCENES)) * SCENE_LEN
    while t < now:
        who, talks, _, _ = demo_scene(t)
        note_events(who, talks, t)
        t += SCENE_LEN


# ── 正式模式：由 POST 回報的狀態 ──
STATE = {}   # id → 最近一次 /update 合併後的欄位，外加 "_t"（最後更新時間）
TALKS = []   # [{"from", "to", "t", "kind", "tag"}]
MAIL = [0]
API = {}


def live(now):
    who = {}
    for i in IDS:
        s = STATE.get(i, {})
        w = {"online": False, "busy": False, "busy_n": 0, "queue": 0, "doing": "", "note": ""}
        if s:
            w["online"] = True
            w.update({k: v for k, v in s.items() if k != "_t"})
            if now - s["_t"] > OFFLINE_AFTER:
                w.update(online=False, busy=False, busy_n=0)
        who[i] = w
    who["boss"].update(online=True, waiting=[])
    talks = [x for x in TALKS if now - x["t"] < TALK_KEEP]
    return who, talks, json.loads(json.dumps(API)), MAIL[0]


def sprite_times(suffix):
    n = len(suffix)
    return {f.name[:-n]: int(f.stat().st_mtime) for f in (ART / "角色").glob("*" + suffix) if f.name[:-n] in IDS}


def status():
    now = time.time()
    with LOCK:
        who, talks, api, mail = demo_scene(now) if DEMO else live(now)
        note_events(who, talks, now)
        flags(who, now)
        for k, w in who.items():  # 忙了多久：網頁在角色頭上顯示「⏱ 12 分」
            if w.get("busy") and k in _prev:
                w["since"] = int(_prev[k]["since"] * 1000)
        projs = apply_rules(projects(now))
        pty = party(projs, now)
        events, brd = recent_shots(), board(now)
    return {"time": now, "reason_ok": True, "lang": LANG, "cast": CFG["cast"], "who": who, "talks": talks, "mail": mail,
            "api": api, "chat": {}, "projects": projs, "events": events, "board": brd,
            "pads": PADS["pads"], "padrules": PADS["rules"], "wall": WALL, "party": pty, "launched": launched(),
            "sheets": sprite_times("_sheet.jpg"), "sits": sprite_times("_sit.png"), "walks": sprite_times("_walk.png")}


# ── 寫入端點的驗證 ──
def _int(lo, hi):
    return lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and lo <= v <= hi


FIELDS = {
    "online": lambda v: isinstance(v, bool), "busy": lambda v: isinstance(v, bool),
    "busy_n": _int(0, 99), "queue": _int(0, 999), "hp": lambda v: v is None or _int(0, 100)(v),
    "state": lambda v: v in (None, "fail", "ghost"), "seek": lambda v: v is None or v in IDS,
    "doing": lambda v: isinstance(v, str) and len(v) <= 200, "note": lambda v: isinstance(v, str) and len(v) <= 200,
}
CLEARABLE = ("hp", "state", "seek")  # 傳 null 表示清除


def do_update(d):
    i = d.get("id")
    assert i in IDS and all(k in FIELDS and FIELDS[k](v) for k, v in d.items() if k != "id")
    s = STATE.setdefault(i, {})
    for k, v in d.items():
        if k == "id":
            continue
        if v is None:
            s.pop(k, None)
        else:
            s[k] = int(v) if k in ("busy_n", "queue", "hp") else v
    s["_t"] = time.time()


def do_talk(d):
    a, b, kind, tag = d.get("from"), d.get("to"), d.get("kind") or "", d.get("tag") or ""
    assert a in IDS and b in IDS and a != b and kind in ("task", "report", "") and isinstance(tag, str)
    TALKS.append({"from": a, "to": b, "t": time.time(), "kind": kind, "tag": tag[:16]})
    TALKS[:] = [x for x in TALKS if time.time() - x["t"] < TALK_KEEP][-200:]


PROGRESS = {}  # 專案名 → [做完幾步, 共幾步]，由 /project 回報


def do_project(d):
    """回報一個專案的進度：{"name": "網站改版", "done": 3, "total": 8}。total 給 0 就是拿掉進度條。
    打勾：{"name": "網站改版", "stage": "測試", "undo": false}（這張卡要先設定好階段）。"""
    if d.get("stage"):
        assert stage_done(str(d["name"])[:40], str(d["stage"]).strip()[:12], bool(d.get("undo")))
        return
    name, done, total = str(d["name"])[:40], int(d.get("done", 0)), int(d.get("total", 0))
    assert name and 0 <= done <= total <= 9999
    if total:
        PROGRESS[name] = [done, total]
    else:
        PROGRESS.pop(name, None)


ROLE = {"boss": ("決定與核准", "Decides & approves"), "lead": ("主要製作", "Lead maker"), "coord": ("派工協調", "Coordinator"),
        "help": ("執行支援", "Support"), "talk": ("討論", "Discussion")}


def projects(now):
    """專案牆：把這七天帶同一個專案名（tag）的事件歸成一張卡，算出誰參與、各自的角色、多久沒動。"""
    proj = {}
    for e in EVENTS:
        tag = e.get("tag")
        if not tag or now - e["t"] > 7 * 86400 or e["type"] in ("party", "launch"):  # 慶功、升空不是一個專案
            continue
        p = proj.setdefault(tag, {"last": 0, "mem": {}})
        p["last"] = max(p["last"], e["t"])
        for k, side in ((e["who"], "from"), (e.get("to"), "to")):
            if k:
                c = p["mem"].setdefault(k, {"task_out": 0, "task_in": 0, "report": 0, "report_in": 0, "done": 0, "talk": 0})
                ty = e["type"]
                if ty == "task":
                    c["task_out" if side == "from" else "task_in"] += 1
                elif ty == "report":
                    c["report" if side == "from" else "report_in"] += 1
                elif ty == "done":
                    c["done"] += 1
                else:
                    c["talk"] += 1
    for name in PROGRESS:
        proj.setdefault(name, {"last": 0, "mem": {}})
    out = []
    for name, p in proj.items():
        people = []
        for k, c in p["mem"].items():
            r = ("boss" if k == "boss" else "lead" if c["done"] else "coord" if c["task_out"] > c["task_in"] or c["report_in"] else
                 "help" if c["task_in"] or c["report"] else "talk")
            people.append({"id": k, "role": ROLE[r][LANG == "en"], "n": sum(c.values()),
                           "did": {x: c[x] for x in ("task_out", "task_in", "report", "done") if c[x]}})
        if not any(m["id"] == "boss" for m in people):
            people.append({"id": "boss", "role": ROLE["boss"][LANG == "en"], "n": 0, "did": {}})
        people.sort(key=lambda m: (m["id"] != "boss", -m["n"]))
        done, total = PROGRESS.get(name, (0, 0))
        if DEMO and not total:  # 示範模式的進度是編的（跟其他示範內容一樣），讓人看得到進度條長怎樣
            total = 6 + sum(map(ord, name)) % 7
            done = 1 + sum(map(ord, name)) % total
        out.append({"name": name, "active": now - p["last"] < 300, "last": p["last"], "people": people, "done": done, "total": total, "src": ""})
    out.sort(key=lambda p: (not p["active"], p["name"]) if DEMO else (not p["active"], -p["last"]))
    out = out[:8]
    if DEMO:  # 示範模式不顯示專案名，照顯示順序叫專案 A、B、C（拿來錄影、截圖也不會露出任何真的名字）
        for i, p in enumerate(out):
            p["name"] = ("Project " if LANG == "en" else "專案 ") + chr(65 + i)
    for name in WALL.get("added", []):  # 手動種的盆栽（專案）：還沒有任何紀錄也顯示
        if not any(p["name"] == name for p in out):
            done, total = PROGRESS.get(name, (0, 0))
            out.append({"name": name, "active": False, "last": 0, "added": True, "done": done, "total": total, "src": "",
                        "people": [{"id": "boss", "role": ROLE["boss"][LANG == "en"], "n": 0, "did": {}}]})
    return out


# ── 發射台、專案牆、慶功 ──
LAUNCH_FILE, WALL_FILE = HERE / "launchpad.json", HERE / "wall.json"  # 使用者的設定（不進 git）
UNITS = ("集", "版", "週", "期", "回合", "Sprint", "篇", "件")
UNIT_EN = {"集": "Episode", "版": "Version", "週": "Week", "期": "Term", "回合": "Round", "Sprint": "Sprint", "篇": "Post", "件": "Item"}
EP_RE = re.compile(r"(?:ep\s*(\d+))|(?:第\s*(\d+)\s*(?:集|版|週|期|回合|篇|件))|(?:(?:sprint|episode|version|week|term|round|post|item)\s*(\d+))", re.I)


def _load(f, default):
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return default


PADS = _load(LAUNCH_FILE, {"pads": [], "rules": {}})   # {"pads": [三個專案名], "rules": {專案名: 進度怎麼算}}
WALL = _load(WALL_FILE, {"order": [], "hidden": [], "added": []})   # 專案牆的順序和隱藏
PARTY = {"name": "", "t": 0}
_ck = {}


def _save(f, d):
    f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def ep_tag(base, ep, r):
    u = r.get("unit") or "集"
    if LANG == "en":
        return f"{base} {UNIT_EN.get(u, u)} {ep}"
    return f"{base} Ep{ep}" if u == "集" else f"{base} Sprint {ep}" if u == "Sprint" else f"{base} 第{ep}{u}"


def launched_eps(base):
    out = set()
    for e in EVENTS:
        t = e.get("tag") or ""
        if e["type"] == "launch" and t.startswith(base):
            m = EP_RE.search(t[len(base):])
            if m:
                out.add(int(m.group(1) or m.group(2) or m.group(3)))
    return out


def current_ep(base, r):
    """每一輪一支火箭：現在是第幾輪。使用者指定過就用指定的；否則是上一支升空的下一輪。"""
    if r.get("ep"):
        return int(r["ep"])
    done = launched_eps(base)
    return max(done) + 1 if done else 1


def milestone(name, who="fox"):
    """一集（一輪、一個清單）完成：大家到休息區乾杯，老闆走到發射台點火、火箭升空（動態牆記兩筆）。"""
    now = time.time()
    PARTY.update(name=name, t=now)
    add_event(now, "party", who, None, name)
    add_event(now + 1, "launch", "boss", None, name)


def launched():
    """最近升空的兩支：[最新, 上一支]。升空的火箭停在自己的平台上方，下一支升空才換掉。"""
    names = [e.get("tag") for e in reversed(EVENTS) if e["type"] == "launch" and e.get("tag")]
    return (names + [None, None])[:2]


def stage_done(name, stage, undo=False):
    """把一個階段標成做完或取消；全部做完就慶功，每一輪模式會自動換下一輪。"""
    r = PADS["rules"].get(name)
    if not r or r.get("mode") not in ("episode", "list") or stage not in (r.get("stages") or []):
        return False
    stages, got, at = r["stages"], [x for x in r.get("got") or [] if x in r["stages"]], dict(r.get("at") or {})
    if undo:
        got, _ = [x for x in got if x != stage], at.pop(stage, None)
    elif stage not in got:
        got.append(stage)
        at[stage] = time.time()
    r.update(got=got, at=at)
    if r["mode"] == "list":  # 一張清單：全部勾完慶功一次，勾勾留著
        if len(got) >= len(stages) and not r.get("fired"):
            milestone(name)
            r["fired"] = True
        elif len(got) < len(stages):
            r["fired"] = False
    elif len(got) >= len(stages):
        ep = current_ep(name, r)
        milestone(ep_tag(name, ep, r))
        r.update(got=[], at={}, ep=ep + 1)
    _save(LAUNCH_FILE, PADS)
    return True


def apply_rules(projs):
    for p in projs:
        r = PADS["rules"].get(p["name"])
        if not r or r.get("mode") in (None, "auto"):
            continue
        stages = r.get("stages") or []
        got = [x for x in r.get("got") or [] if x in stages]
        nxt = next((x for x in stages if x not in got), "")
        if r["mode"] == "episode":
            p.update(done=len(got), total=len(stages), stages=stages, got=got, at=r.get("at") or {}, stage=nxt, epmode=True,
                     unit=r.get("unit") or "集", cur=current_ep(p["name"], r), src="")
        elif r["mode"] == "list":
            p.update(done=len(got), total=len(stages), stages=stages, got=got, at=r.get("at") or {}, stage=nxt, listmode=True, src="")
        elif r["mode"] == "manual":
            p.update(done=int(r.get("done") or 0), total=int(r.get("total") or 0), src="")
    return projs


def party(projs, now):
    """回報進度（/project 的 done、total）做滿了也算完成一次。"""
    for p in projs:
        if p["total"] and not p.get("epmode") and not p.get("listmode") and not DEMO:  # 示範模式的進度是編的，不自動慶功
            was, _ck[p["name"]] = _ck.get(p["name"]), (p["done"], p["total"])
            if was and was[0] < was[1] and p["done"] >= p["total"]:
                milestone(p["name"])
    return dict(PARTY) if now - PARTY["t"] < 90 else None


def _rule(r, old):
    assert r.get("mode") in ("auto", "episode", "list", "manual")
    stages = [str(x).strip()[:12] for x in r.get("stages") or [] if str(x).strip()][:10]
    keep = (old or {}).get("stages") == stages
    done, total = int(r.get("done") or 0), int(r.get("total") or 0)
    assert 0 <= done <= total <= 9999
    return {"mode": r["mode"], "done": done, "total": total, "stages": stages, "unit": r.get("unit") if r.get("unit") in UNITS else "集",
            "got": [x for x in (old or {}).get("got") or [] if x in stages] if keep else [], "at": ((old or {}).get("at") or {}) if keep else {},
            "ep": int(r.get("ep") or 0) or (old or {}).get("ep")}


def do_launchpad(d):
    """發射台設定：{"pads": [最多三個專案名], "rules": {專案名: {"mode", "stages", "unit", "ep", "done", "total"}}}"""
    pads = [str(x)[:40] for x in d.get("pads") or []][:3]
    rules = {str(k)[:40]: _rule(r, PADS["rules"].get(str(k)[:40])) for k, r in (d.get("rules") or {}).items()}
    PADS.update(pads=pads, rules={**PADS["rules"], **rules})
    _save(LAUNCH_FILE, PADS)


def do_rule(d):
    """單一專案的進度設定：{"name", "rule": {...} 或 null（拿掉）}"""
    name = str(d["name"]).strip()[:40]
    assert name
    if d.get("rule") is None:
        PADS["rules"].pop(name, None)
    else:
        PADS["rules"][name] = _rule(d["rule"], PADS["rules"].get(name))
    _save(LAUNCH_FILE, PADS)


def do_wall(d):
    """專案牆：{"order": [卡片名], "hidden": [卡片名]}"""
    clean = lambda xs: list(dict.fromkeys(str(x)[:40] for x in xs or []))[:200]
    for k in ("order", "hidden", "added"):  # added＝手動種的專案
        if k in d:
            WALL[k] = clean(d[k])
    _save(WALL_FILE, WALL)


def do_api(d):
    for k, v in d.items():
        assert k in ("voice", "video", "paint") and isinstance(v, dict)
        assert v.get("state") in (None, "send", "fail") and isinstance(v.get("balance", ""), str)
    for k, v in d.items():
        if v.get("state") is None:
            API.pop(k, None)
        else:
            API[k] = {"state": v["state"], "balance": v.get("balance", "")[:40]}


def do_sprites(d):
    """網頁把去背切好的角色圖存回來，下次開就不用重切。走路、坐椅是兩格，角色表是 13 格。"""
    pair = d["id"].endswith(("_walk", "_walkb", "_coffee", "_sit"))
    assert (d["id"].rsplit("_", 1)[0] if pair else d["id"]) in IDS
    assert len(d["sprites"]) == (2 if pair else 13)
    assert all(s["url"].startswith("data:image/png;base64,") for s in d["sprites"])
    cut = ART / "角色" / "cut"
    cut.mkdir(exist_ok=True)
    (cut / (d["id"] + ".json")).write_text(json.dumps({"stamp": int(d["stamp"]), "v": d.get("v"), "sprites": d["sprites"]}), encoding="utf-8")


POSTS = {"/project": (do_project, 2000), "/update": (do_update, 20000), "/talk": (do_talk, 20000), "/mail": (lambda d: MAIL.__setitem__(0, time.time()), 20000),
         "/api": (do_api, 20000), "/sprites": (do_sprites, 8_000_000), "/launchpad": (do_launchpad, 20000), "/rule": (do_rule, 4000), "/wall": (do_wall, 20000)}
SETTINGS = ("/sprites", "/launchpad", "/rule", "/wall")  # 示範模式也照存的設定（不是狀態回報）


def static_ok(path):
    """只放行網頁需要的檔案；server.py、設定檔、events.json 一律不給。"""
    p = unquote(path.split("?", 1)[0].split("#", 1)[0])
    if p in ("/", "/index.html", "/manifest.json") or re.fullmatch(r"/icon-[\w-]+\.png", p):
        return (HERE / p.lstrip("/")).exists()
    if p.startswith("/art/"):
        f = (HERE / p.lstrip("/")).resolve()
        return f.is_file() and f.is_relative_to(ART.resolve())
    return False


class H(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0] == "/status.json":
            body = json.dumps(status(), ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return self.wfile.write(body)
        if not static_ok(self.path):
            return self.send_error(404)
        super().do_GET()

    def do_HEAD(self):
        if not static_ok(self.path):
            return self.send_error(404)
        super().do_HEAD()

    def do_POST(self):
        # X-Office 標頭擋掉別的網站代送（跨站請求帶不了自訂標頭）
        if self.headers.get("X-Office") != "1":
            return self.send_error(403)
        if self.path not in POSTS:
            return self.send_error(404)
        fn, limit = POSTS[self.path]
        try:
            n = int(self.headers.get("Content-Length") or 0)
            assert n <= limit
            d = json.loads(self.rfile.read(n) or b"{}")
            assert isinstance(d, dict)
            if self.path in SETTINGS or not DEMO or d.get("stage"):  # 示範模式忽略狀態回報；設定和打勾照存，才試得出效果
                with LOCK:
                    fn(d)
        except Exception:
            return self.send_error(400)
        self.send_response(204)
        self.end_headers()

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, *a):
        pass


def selftest():
    who, talks, _, _ = demo_scene(0)
    assert set(who) == set(IDS) and who["boss"]["online"]
    assert len(SCENES) >= 8 and all(a in IDS and b in IDS for s in SCENES for a, b, _, _ in s["talks"])
    assert not static_ok("/server.py") and not static_ok("/office.config.json") and not static_ok("/events.json")
    texts = {w.get(k, "") for s in SCENES for w in s["who"].values() for k in ("doing", "note")} | {t[3] for s in SCENES for t in s["talks"]}
    assert all(x in EN for x in texts - {""}), texts - set(EN) - {""}
    assert not static_ok("/art/../server.py") and not static_ok("/art/%2e%2e/server.py")
    assert not static_ok("/launchpad.json") and not static_ok("/wall.json")
    r = _rule({"mode": "episode", "stages": ["a", "b"], "unit": "版"}, None)
    assert r["stages"] == ["a", "b"] and r["unit"] == "版" and r["got"] == []


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="可視化辦公室伺服器")
    ap.add_argument("--port", type=int, default=CFG["port"])
    ap.add_argument("--lang", choices=("zh", "en"), help="畫面與示範文字的語言（預設看設定檔的 lang）")
    args = ap.parse_args()
    port, LANG = args.port, args.lang or LANG
    selftest()
    if DEMO:
        demo_backfill(time.time())
    handler = functools.partial(H, directory=str(HERE))
    servers = [http.server.ThreadingHTTPServer((ip, port), handler) for ip in CFG["bind"]]
    for ip in CFG["bind"]:
        print(f"辦公室開門：http://{ip}:{port}" + ("（示範模式）" if DEMO else ""))
    for s in servers[1:]:
        threading.Thread(target=s.serve_forever, daemon=True).start()
    servers[0].serve_forever()
