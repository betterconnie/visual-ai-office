# Connect your own AIs

The short version: while your AI works, have it tell the server over HTTP "who I am and how I'm doing". The server organizes this and the page acts it out.

## Before you start

1. Open `office.config.json` and set `"demo"` to `false`.
2. Start the server: `python3 server.py` (add `--port N` to change the port).
3. The examples below assume the server is at `http://127.0.0.1:8765`.

The config file looks like this:

```json
{
  "port": 8765,
  "bind": ["127.0.0.1"],
  "demo": false,
  "cast": {
    "fox": {"name": "狐狸", "role": "總協調，派工給大家"}
  }
}
```

## Three rules

- Every POST must carry the header `X-Office: 1`, and the body is JSON.
- Success returns `204` (no content).
- There are only seven character ids: `boss`, `fox`, `bird`, `bear`, `cat`, `raccoon`, `crab`. `boss` is you.

## Examples you can copy

### 1. Start working

```
curl -X POST http://127.0.0.1:8765/update \
  -H 'X-Office: 1' -H 'Content-Type: application/json' \
  -d '{"id": "bird", "online": true, "busy": true, "doing": "查資料"}'
```

On screen: Bird sits back down at its desk and types.

### 2. Stop working

```
curl -X POST http://127.0.0.1:8765/update \
  -H 'X-Office: 1' -H 'Content-Type: application/json' \
  -d '{"id": "bird", "online": true, "busy": false}'
```

On screen: Bird gets up and goes to the lounge.

### 3. Send a message to another AI

```
curl -X POST http://127.0.0.1:8765/talk \
  -H 'X-Office: 1' -H 'Content-Type: application/json' \
  -d '{"from": "fox", "to": "cat", "kind": "task", "tag": "新圖示"}'
```

Set `kind` to `"task"` to assign work, `"report"` to report back, and `""` for ordinary talk. `tag` is a project or topic name and is shown in the replay.

### 4. Quota almost gone, lots of work queued

```
curl -X POST http://127.0.0.1:8765/update \
  -H 'X-Office: 1' -H 'Content-Type: application/json' \
  -d '{"id": "raccoon", "hp": 20, "queue": 6}'
```

On screen: Raccoon hunches over and sweats. When `hp` reaches `0` it collapses.

### 5. See the full current status

```
curl http://127.0.0.1:8765/status.json
```

This is exactly what the page reads.

## API at a glance

### `POST /update`: report one character's status

`id` is required; send only the other fields you have:

| Field | Meaning |
|---|---|
| `online` | Online or not (true/false) |
| `busy` | Working or not (true/false) |
| `busy_n` | How many sessions are open at once |
| `hp` | Remaining quota, 0 to 100 |
| `queue` | Number of queued jobs |
| `state` | `"fail"` = task failed, `"ghost"` = here but not picking up messages, `null` = clear |
| `seek` | Id of the character being looked for; `null` = clear |
| `doing` | What it is doing (text) |
| `note` | Note (text) |

A character that hasn't reported for more than 10 minutes counts as offline (except the boss). So an AI that stays online should report at least every 10 minutes.

### `POST /talk`: who contacts whom

`{"from": character id, "to": character id, "kind": "task" | "report" | "", "tag": "project or topic name"}`

### `POST /mail`: mail arrived

Send `{}` and Fox walks to the mailbox to collect it.

### `POST /api`: outside services (not shown on screen right now; kept for later)

```
curl -X POST http://127.0.0.1:8765/api \
  -H 'X-Office: 1' -H 'Content-Type: application/json' \
  -d '{"voice": {"state": "send", "balance": "剩 120 點"}}'
```

The available services are `voice`, `video` and `paint`. `state` is `"send"` (sending), `"fail"` (failed) or `null` (clear); `balance` is a piece of text.

### `GET /status.json`: full current status

## How status becomes a picture

| What you send | On screen |
|---|---|
| `online` and `busy` | Working at their desk |
| `online` but not `busy` | Goes to the lounge |
| `hp` is 0 | Collapses |
| `hp` below 30, or `queue` 5 or more | Struggling (hunched over, sweating) |
| `state: "fail"` | Angry |
| `state: "ghost"` | Semi-transparent |
| `seek` is set | Walks to the other one's door and paces |
| not `online` | Empty seat with an "Out" sign |
| `queue` of `boss` | Number of folders on the boss's desk |

## Common setups

### Setup 1: have the AI call at three moments

The simplest. Just tell your AI:

> Your character id in this office is `bear`.
> When you start working, when you finish, and when you send a message to another AI, report once by calling the URL below with curl.
> (Paste examples 1, 2 and 3 above.)

Many AI tools can also run a command automatically at certain moments (often called a hook). If yours can, put the curl there so it doesn't depend on the AI remembering.

Downside: AIs sometimes forget to report.

### Setup 2: a small script that reports on a timer

The script checks on the AI by itself (for example, whether the program is running, or whether its work log changed recently) and reports once a minute. The upside is that it doesn't depend on the AI remembering, and the design document prefers this kind: read the logs the tools leave behind first.

Here is a macOS/Linux example: check whether a program is running; if so, it counts as online and busy. Replace `my-ai-tool` with your program's name.

```sh
#!/bin/sh
while true; do
  if pgrep -f my-ai-tool > /dev/null; then
    BODY='{"id": "raccoon", "online": true, "busy": true}'
  else
    BODY='{"id": "raccoon", "online": false}'
  fi
  curl -s -X POST http://127.0.0.1:8765/update \
    -H 'X-Office: 1' -H 'Content-Type: application/json' -d "$BODY"
  sleep 60
done
```

You can mix the two: the script handles "online or not, busy or not", and the AI itself handles "who it messages".

## Privacy

- Only send short information like "who, when, doing what". Don't send message bodies or confidential data.
- The server has no login protection. Only run it on your own computer or a private network.
