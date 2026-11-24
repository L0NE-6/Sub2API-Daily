<div align="center">

<sub><strong>L0NE-6 · DAILY SIGNAL</strong></sub>

# 🧩 Sub2API Daily

**Sub2API 毎日チェックイン · 複数アカウント · 状態と報酬の厳格な再読取 · JSONL**

[简体中文](../README.md) · [English](README.en.md) · [繁體中文](README.zh-Hant.md) · **日本語** · [한국어](README.ko.md) · [Português (BR)](README.pt-BR.md)
> バージョン：**v1.0.0**（2026-11-24）

</div>

## 機能

Sub2API サイトにログインし、毎日のチェックイン状態を読み取って報酬を申請し、再度状態を読み取ります。`reward_amount`、`new_balance`、`checked_in_at` が揃い、その後の状態が `checked_in_today=true` の場合だけ `CLAIMED` と報告します。

## 設定

`SUB2API_ACCOUNTS` は `ラベル|サイト|メール|パスワード`、`SUB2API_SESSIONS` は `ラベル|サイト|accessToken|userId` です。JSON 配列と単一アカウント変数にも対応します。

## プロトコル

```http
GET  /api/v1/redeem/checkin/status
GET  /api/v1/redeem/checkin          # 状態 API 非対応時のフォールバック
POST /api/v1/redeem/checkin          # body なし
Authorization: Bearer <ACCESS_TOKEN>
```

申請結果には有限の `reward_amount`、`new_balance`、有効な RFC3339 の `checked_in_at` が必要です。再読取で `checked_in_today=true` を確認できない場合は `UNCONFIRMED` です。

## 実行

```bash
python -m pip install -r requirements.txt
export SUB2API_ACCOUNTS='main|https://sub2api.example|user@example.com|password'
python sub2api_daily.py
python sub2api_daily.py --query
python sub2api_daily.py --only 1,3-4
```

## プライバシー

パスワード、Token、アカウントファイル、レポート、ログ、認証情報を含む画像をコミットしないでください。出力では識別子、秘密情報、通知用の秘密値を伏せます。
