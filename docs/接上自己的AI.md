# 接上自己的 AI

結論先講：讓你的 AI 在做事的時候，用 HTTP 告訴伺服器「我是誰、現在怎樣」。伺服器把這些整理好，網頁就照著演。

## 開始之前

1. 打開 `office.config.json`，把 `"demo"` 改成 `false`。
2. 啟動伺服器：`python3 server.py`（要換連接埠就加 `--port N`）。
3. 下面的範例都假設伺服器在 `http://127.0.0.1:8765`。

設定檔長這樣：

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

## 三個規則

- 所有 POST 都要帶標頭 `X-Office: 1`，內容是 JSON。
- 成功會回 `204`（沒有內容）。
- 角色 id 只有這七個：`boss`、`fox`、`bird`、`bear`、`cat`、`raccoon`、`crab`。`boss` 是你自己。

## 可以直接複製的範例

### 1. 開始工作

```
curl -X POST http://127.0.0.1:8765/update \
  -H 'X-Office: 1' -H 'Content-Type: application/json' \
  -d '{"id": "bird", "online": true, "busy": true, "doing": "查資料"}'
```

畫面：藍鳥坐回位子上打字。

### 2. 結束工作

```
curl -X POST http://127.0.0.1:8765/update \
  -H 'X-Office: 1' -H 'Content-Type: application/json' \
  -d '{"id": "bird", "online": true, "busy": false}'
```

畫面：藍鳥起身去休息區。

### 3. 傳訊息給別的 AI

```
curl -X POST http://127.0.0.1:8765/talk \
  -H 'X-Office: 1' -H 'Content-Type: application/json' \
  -d '{"from": "fox", "to": "cat", "kind": "task", "tag": "新圖示"}'
```

`kind` 填 `"task"` 是派工，`"report"` 是回報，`""` 是一般講話。`tag` 是專案或主題名，會顯示在辦公室動態上。

### 4. 額度快用完、排了很多工作

```
curl -X POST http://127.0.0.1:8765/update \
  -H 'X-Office: 1' -H 'Content-Type: application/json' \
  -d '{"id": "raccoon", "hp": 20, "queue": 6}'
```

畫面：浣熊駝背冒汗。`hp` 變成 `0` 就會倒地。

### 5. 看目前全部狀態

```
curl http://127.0.0.1:8765/status.json
```

網頁就是讀這一份。

## 介面一覽

### `POST /update`：回報一個角色的狀態

`id` 必填，其餘欄位只送你有的就好：

| 欄位 | 意思 |
|---|---|
| `online` | 在不在線（true／false） |
| `busy` | 有沒有在工作（true／false） |
| `busy_n` | 同時開了幾個對話 |
| `hp` | 剩餘額度，0～100 |
| `queue` | 排隊中的工作數 |
| `state` | `"fail"`＝任務失敗、`"ghost"`＝人在但訊息沒接、`null`＝清除 |
| `seek` | 正在找的角色 id；`null`＝清除 |
| `doing` | 在做什麼（文字） |
| `note` | 備註（文字） |

超過 10 分鐘沒回報的角色，會被當成離線（老闆除外）。所以一直在線的 AI，至少每 10 分鐘要回報一次。

### `POST /talk`：誰找誰

`{"from": 角色 id, "to": 角色 id, "kind": "task" | "report" | "", "tag": "專案或主題名"}`

### `POST /mail`：收信

送 `{}`，狐狸會走去郵筒收信。

### `POST /api`：對外呼叫的服務（目前畫面上不顯示，保留給之後用）

```
curl -X POST http://127.0.0.1:8765/api \
  -H 'X-Office: 1' -H 'Content-Type: application/json' \
  -d '{"voice": {"state": "send", "balance": "剩 120 點"}}'
```

可用的服務有 `voice`、`video`、`paint`。`state` 是 `"send"`（送出中）、`"fail"`（失敗）或 `null`（清除）；`balance` 是一段文字。

### `GET /status.json`：目前全部狀態

## 狀態怎麼變成畫面

| 你送的資料 | 畫面 |
|---|---|
| `online` 且 `busy` | 在位子上工作 |
| `online` 但不 `busy` | 去休息區 |
| `hp` 是 0 | 倒地 |
| `hp` 低於 30，或 `queue` 5 以上 | 很辛苦（駝背、冒汗） |
| `state: "fail"` | 生氣 |
| `state: "ghost"` | 變半透明 |
| `seek` 有值 | 走到對方門口踱步 |
| 不 `online` | 座位空著，掛「外出中」 |
| `boss` 的 `queue` | 老闆桌上的公文夾數 |

## 常見接法

### 接法一：讓 AI 在三個時間點各打一次

最簡單。直接跟你的 AI 說：

> 你在這間辦公室的角色 id 是 `bear`。
> 開始工作時、結束工作時、傳訊息給別的 AI 時，各用 curl 打一次下面的網址回報。
> （把上面範例 1、2、3 貼給它）

很多 AI 工具也支援在特定時間自動執行指令（常叫做 hook）。如果你的工具有，把 curl 放進去，就不用靠 AI 記得。

缺點：AI 有時會忘記回報。

### 接法二：寫一個小腳本定時回報

腳本自己去看 AI 的狀況（例如程式有沒有在跑、工作紀錄檔最近有沒有變動），每分鐘回報一次。好處是不靠 AI 記得，設計文件也比較推薦這種：優先讀工具自己留下的紀錄。

下面是一個 macOS／Linux 的例子：看某支程式有沒有在跑，有就算在線又在忙。把 `my-ai-tool` 換成你的程式名稱。

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

兩種可以混著用：腳本負責「在不在線、忙不忙」，AI 自己負責「傳訊息給誰」。

## 隱私提醒

- 只送「誰、何時、在做什麼」這種簡短資訊，不要把訊息內文或機密資料送進來。
- 伺服器沒有登入保護，請只在自己的電腦或私人網路上開。
