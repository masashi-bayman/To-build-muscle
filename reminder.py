#!/usr/bin/env python3
"""今日のメニューが終わっていなければ Discord に催促を送る。
systemd timer で夜に30分おきなどに実行する想定。全部終わっていれば何もしない。
環境変数:
  DISCORD_WEBHOOK_URL  必須
  DISCORD_MENTION      任意（例: <@123456789012345678>）通知を強くしたいとき
  TL_URL               任意（記録ページのURL。メッセージに載せる）
  TL_DB                任意（server.py と同じDB）
  TL_REMIND_WEIGHT     任意（"0" で体重未入力の催促を切る）
"""
import json, os, sqlite3, sys, urllib.request
from datetime import date

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("TL_DB", os.path.join(BASE, "data", "training.db"))
PLAN_PATH = os.environ.get("TL_PLAN", os.path.join(BASE, "public", "plan.json"))
HOOK = os.environ.get("DISCORD_WEBHOOK_URL")


def main():
    if not HOOK:
        sys.exit("DISCORD_WEBHOOK_URL が未設定です")
    plan = json.load(open(PLAN_PATH, encoding="utf-8"))
    today = date.today()
    js_weekday = str((today.weekday() + 1) % 7)  # JS と同じ 0=日曜
    menu = plan["menus"][plan["schedule"][js_weekday]]
    items = menu["items"] + plan["core"]

    rec = {}
    if os.path.exists(DB_PATH):
        con = sqlite3.connect(DB_PATH)
        row = con.execute("SELECT body FROM days WHERE date=?", (today.isoformat(),)).fetchone()
        con.close()
        if row:
            rec = json.loads(row[0])
    ex = rec.get("ex") or {}
    left = [i["name"] for i in items if not (ex.get(i["id"]) or {}).get("done")]
    need_weight = os.environ.get("TL_REMIND_WEIGHT", "1") != "0" and rec.get("weight") in (None, "")

    if not left and not need_weight:
        return  # 完了。静かにしておく

    lines = []
    mention = os.environ.get("DISCORD_MENTION", "")
    head = f"{mention} " if mention else ""
    done = len(items) - len(left)
    lines.append(f"{head}**今日の筋トレ（{menu['name']}）まだです** {done}/{len(items)}")
    if left:
        lines.append("残り: " + "、".join(left))
    if need_weight:
        lines.append("体重もまだ入力されていません")
    if os.environ.get("TL_URL"):
        lines.append(os.environ["TL_URL"])

    payload = json.dumps({"content": "\n".join(lines), "allowed_mentions": {"parse": ["users"]}}).encode()
    req = urllib.request.Request(HOOK, data=payload, headers={"Content-Type": "application/json", "User-Agent": "training-reminder"})
    urllib.request.urlopen(req, timeout=10).read()


if __name__ == "__main__":
    main()
