# 筋トレ記録（ラズパイ版）

毎日のメニューのチェックリスト、体重・ウエスト・セットごとの記録、グラフ表示、
未完了時の Discord 催促をまとめたセットです。依存は Python 3 標準ライブラリのみ。

## 構成

```
/opt/training-log/
├── server.py        記録API（127.0.0.1:8765、SQLite保存）
├── reminder.py      未完了なら Discord Webhook に催促
├── reminder.env     Webhook URL など（example をコピーして作成）
├── data/training.db 自動作成
├── public/          nginx で配信する静的ファイル（PWA）
│   ├── index.html
│   ├── plan.json    メニュー定義（ページと催促の両方が読む）
│   ├── sw.js / manifest.webmanifest / icon.*
└── deploy/          systemd ユニットと nginx 設定例
```

## セットアップ

```bash
sudo mkdir -p /opt/training-log && sudo chown pi:pi /opt/training-log
git clone https://github.com/masashi-bayman/To-build-muscle.git /opt/training-log

# API
sudo cp /opt/training-log/deploy/training-log.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now training-log
curl -s localhost:8765/api/days   # {} が返ればOK

# nginx（設定は snippet にして、既存サイトの server {} から include する）
sudo cp /opt/training-log/deploy/nginx-training.conf /etc/nginx/snippets/training.conf
sudo vi /etc/nginx/sites-enabled/<既存サイト>   # server { の中に  include snippets/training.conf;  を追加
sudo nginx -t && sudo systemctl reload nginx
```

`User=pi` は実際のユーザー名に合わせてください。

## 更新（GitHub の変更をラズパイに反映）

```bash
cd /opt/training-log && git pull
sudo systemctl restart training-log   # server.py を変えたときだけ
```

`plan.json` や `index.html` の変更は `git pull` だけで反映されます（ページを再読み込み）。
`data/` と `reminder.env` は `.gitignore` 済みなので、`git pull` で消えたり上書きされたりしません。

## 催促通知（Discord）

```bash
cp /opt/training-log/deploy/reminder.env.example /opt/training-log/reminder.env
chmod 600 /opt/training-log/reminder.env
vi /opt/training-log/reminder.env   # Webhook URL・メンション・ページURL

sudo cp /opt/training-log/deploy/training-reminder.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now training-reminder.timer

# 手動テスト
sudo systemctl start training-reminder.service
systemctl list-timers training-reminder.timer
```

- 19:00〜23:00 の30分おきに実行し、今日のメニュー（体幹含む）と体重が全部埋まるまで送り続けます。完了すると黙ります。
- 間隔を変えるなら timer の `OnCalendar` を編集（例: 15分おき `19..22:00/15`）。
- `DISCORD_MENTION` に自分のユーザーIDを入れると、スマホのプッシュが確実に鳴ります。
- 体重の催促が不要なら `reminder.env` に `TL_REMIND_WEIGHT=0`。
- ラズパイのタイムゾーンが `Asia/Tokyo` になっているか確認（`timedatectl`）。

## メニューの変更

`public/plan.json` を編集するだけで、ページと催促の両方に反映されます。

- `schedule`: 曜日（0=日〜6=土）→ メニュー名
- `items` / `core`: `sets` セット数、`unit` 回/秒、`kg` ダンベル初期重量（0で自重）、
  `video` は YouTube 検索ワード（ページに「やり方の動画を見る」リンクとして出ます）

特定の動画に固定したい場合は、`index.html` の `ytUrl()` を
`it.video.startsWith("http") ? it.video : 検索URL` のように変えて、`video` に動画URLを直接書いてください。

## セキュリティ

記録APIには認証がありません。Cloudflare Tunnel で外に出す場合は、
`/training/` を Cloudflare Zero Trust Access（メール認証など）の対象にしてください。

外部公開してもディスクをゴミで埋められないよう、サーバーが受け付ける日付は
「1年前〜1か月先」に制限しています（`TL_PAST_DAYS` / `TL_FUTURE_DAYS` で変更可）。

## バックアップ

`data/training.db` をコピーするだけです。ページ下部の「CSVを書き出す」でも取り出せます。
オフライン時の入力は端末に保存され、次にページを開いたときサーバーへ送られます。
