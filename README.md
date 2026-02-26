# 島根ITデザインカレッジ向け Notion→Slack 滞納通知自動化（ポートフォリオ）

## プロジェクト概要
島根ITデザインカレッジの運用を想定し、
**Notionデータベースの支払い情報を集計して、Slackへ定期通知する仕組み**を構築しました。

本フォルダはポートフォリオ公開用のため、APIキー・Webhook URL・DB IDはすべてダミー化しています。

## 背景と課題
- 学費・家賃の滞納状況を手作業で確認して共有していた
- 共有フォーマットが統一されておらず、報告に時間がかかっていた
- 週次報告の抜け漏れリスクがあった

## 実装した内容
- Notion APIで2つのDB（学費 / 家賃）を取得
- `支払い済み金額` を集計
- `学科`（IT科 / VD科）× `年生`（1 / 2）で内訳を作成
- Slack向けに日本語メッセージを整形して投稿
- `cron` で定期実行（毎週金曜 9:00 を想定）

## 使用技術
- Python 3
- Notion API
- Slack Incoming Webhook
- cron（さくらレンタルサーバー想定）

## 成果
- 報告作業の自動化により、確認・共有の工数を削減
- 毎回同じフォーマットで通知でき、可読性が向上
- 週次通知の運用を安定化

## ファイル構成
- `notion_slack_summary_portfolio.py` : ポートフォリオ公開用のサンプル実装（機密情報なし）
- `requirements.txt` : 依存ライブラリ

## 実行方法（ダミー設定）
1. 依存関係をインストール
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. `notion_slack_summary_portfolio.py` の先頭にある設定値を実環境の値へ置き換え
- `NOTION_TOKEN`
- `SLACK_WEBHOOK_URL`
- `GAKUHI_DB_ID`
- `YACHIN_DB_ID`

3. 実行
```bash
python3 notion_slack_summary_portfolio.py
```

## 定期実行例（毎週金曜 9:00）
```cron
0 9 * * 5 cd /path/to/project && /usr/bin/env bash -lc 'source .venv/bin/activate && python3 notion_slack_summary_portfolio.py >> cron.log 2>&1'
```

## 担当
- 要件整理
- Notionデータモデルに合わせた集計ロジック設計
- Slack通知フォーマット設計（日本語業務文面）
- cron運用設計
