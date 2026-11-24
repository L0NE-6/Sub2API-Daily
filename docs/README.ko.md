<div align="center">

<sub><strong>L0NE-6 · DAILY SIGNAL</strong></sub>

# 🧩 Sub2API Daily

**Sub2API 일일 체크인 · 다중 계정 · 상태와 보상의 엄격한 재조회 · JSONL**

[简体中文](../README.md) · [English](README.en.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Português (BR)](README.pt-BR.md)

</div>

## 기능

Sub2API 사이트에 로그인하고 일일 체크인 상태를 읽은 뒤 보상을 요청하고, 다시 상태를 읽습니다. `reward_amount`, `new_balance`, `checked_in_at`이 모두 있고 이후 상태가 `checked_in_today=true`인 경우에만 `CLAIMED`로 보고합니다.

## 설정

`SUB2API_ACCOUNTS`는 `라벨|사이트|이메일|비밀번호`, `SUB2API_SESSIONS`는 `라벨|사이트|accessToken|userId` 형식입니다. JSON 배열과 단일 계정 변수도 지원합니다.

## 프로토콜

```http
GET  /api/v1/redeem/checkin/status
GET  /api/v1/redeem/checkin          # 상태 API 미지원 시 폴백
POST /api/v1/redeem/checkin          # body 없음
Authorization: Bearer <ACCESS_TOKEN>
```

응답에는 유한한 `reward_amount`, `new_balance`와 유효한 RFC3339 `checked_in_at`이 필요합니다. 재조회에서 `checked_in_today=true`를 확인하지 못하면 `UNCONFIRMED`입니다.

## 실행

```bash
python -m pip install -r requirements.txt
export SUB2API_ACCOUNTS='main|https://sub2api.example|user@example.com|password'
python sub2api_daily.py
python sub2api_daily.py --query
python sub2api_daily.py --only 1,3-4
```

## 개인정보

비밀번호, Token, 계정 파일, 보고서, 로그, 자격 증명이 포함된 스크린샷을 커밋하지 마세요. 출력에서는 식별자, 비밀값, 알림 비밀값을 가립니다.
