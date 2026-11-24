<div align="center">

<sub><strong>L0NE-6 · DAILY SIGNAL</strong></sub>

# 🧩 Sub2API Daily

**Check-in diário do Sub2API · múltiplas contas · leitura rigorosa de estado e recompensa · JSONL**

[简体中文](../README.md) · [English](README.en.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · **Português (BR)**
> Versão: **v1.0.0** (2026-11-24)

</div>

## O que faz

Entra em um site Sub2API, lê o estado do check-in diário, solicita a recompensa e lê o estado novamente. Só informa `CLAIMED` quando a resposta contém `reward_amount`, `new_balance`, `checked_in_at` e o estado posterior confirma `checked_in_today=true`.

## Configuração

Use `SUB2API_ACCOUNTS` no formato `rótulo|site|email|senha` ou
`SUB2API_SESSIONS` no formato `rótulo|site|accessToken|userId`. Listas JSON e
variáveis de conta única também são aceitas.

## Protocolo

```http
GET  /api/v1/redeem/checkin/status
GET  /api/v1/redeem/checkin          # fallback quando o status não é suportado
POST /api/v1/redeem/checkin          # sem body
Authorization: Bearer <ACCESS_TOKEN>
```

A resposta de claim precisa de `reward_amount` e `new_balance` finitos, além de
`checked_in_at` RFC3339 válido. A leitura posterior precisa confirmar
`checked_in_today=true`; caso contrário, o resultado é `UNCONFIRMED`.

## Execução

```bash
python -m pip install -r requirements.txt
export SUB2API_ACCOUNTS='principal|https://sub2api.example|user@example.com|senha'
python sub2api_daily.py
python sub2api_daily.py --query
python sub2api_daily.py --only 1,3-4
```

## Privacidade

Não faça commit de senhas, tokens, arquivos de conta, relatórios, logs ou
capturas com credenciais. O script oculta identificadores, segredos e
credenciais de notificação.
