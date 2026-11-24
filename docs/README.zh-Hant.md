<div align="center">

<sub><strong>L0NE-6 · DAILY SIGNAL</strong></sub>

# 🧩 Sub2API Daily

**Sub2API 每日簽到 · 多帳號 · 狀態與領取欄位嚴格回讀 · JSONL**

[简体中文](../README.md) · [English](README.en.md) · **繁體中文** · [日本語](README.ja.md) · [한국어](README.ko.md) · [Português (BR)](README.pt-BR.md)
> 版本：**v1.0.0**（2026-11-24）

</div>

## 功能

登入 Sub2API 站點，讀取每日簽到狀態並領取獎勵，之後再次讀取今日狀態。只有領取回應包含 `reward_amount`、`new_balance`、`checked_in_at`，且後續狀態為 `checked_in_today=true` 時，才回報 `CLAIMED`。

## 設定

`SUB2API_ACCOUNTS` 格式為 `備註|站點|電子郵件|密碼`；`SUB2API_SESSIONS` 格式為 `備註|站點|accessToken|userId`。也支援 JSON 帳號清單與單帳號變數。

## 協議

```http
GET  /api/v1/redeem/checkin/status
GET  /api/v1/redeem/checkin          # 狀態接口不支援時回退
POST /api/v1/redeem/checkin          # 無 body
Authorization: Bearer <ACCESS_TOKEN>
```

領取回應必須有有限數值 `reward_amount`、`new_balance` 與有效 RFC3339 的 `checked_in_at`；回讀狀態必須為 `checked_in_today=true`。缺少欄位或回讀失敗標記 `UNCONFIRMED`。

## 執行

```bash
python -m pip install -r requirements.txt
export SUB2API_ACCOUNTS='主號|https://sub2api.example|user@example.com|password'
python sub2api_daily.py
python sub2api_daily.py --query
python sub2api_daily.py --only 1,3-4
```

## 隱私

不要提交密碼、Token、帳號檔案、報告、日誌或含憑證的截圖。腳本會遮蔽帳號標識、秘密與推送憑證。
