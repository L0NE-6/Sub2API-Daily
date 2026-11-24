<div align="center">

<sub><strong>L0NE-6 · SUB2API SIGNAL</strong></sub>

# Sub2API Daily

**Sub2API 每日签到 · 多账号 · 状态与领取字段严格回读 · JSONL**

> 当前版本：**v1.0.0**（2026-11-24） · 支持账号密码或已有 Session，领取字段和今日状态双重确认

[简体中文](README.md) · [English](docs/README.en.md) · [繁體中文](docs/README.zh-Hant.md) · [日本語](docs/README.ja.md) · [한국어](docs/README.ko.md) · [Português (BR)](docs/README.pt-BR.md)

<img src="https://img.shields.io/badge/Features-Strict%20Readback-6F42C1?style=for-the-badge" alt="Features" />
<a href="https://github.com/L0NE-6/Sub2API-Daily/releases"><img src="https://img.shields.io/github/v/release/L0NE-6/Sub2API-Daily?style=for-the-badge&label=Release&color=2ea44f&logo=github" alt="Release" /></a>
<a href="https://github.com/L0NE-6/Sub2API-Daily/stargazers"><img src="https://img.shields.io/github/stars/L0NE-6/Sub2API-Daily?style=for-the-badge&label=Stars&color=FFC75F&logo=github" alt="Stars" /></a>
<img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
<img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20Qinglong-4EAA25?style=for-the-badge&logo=linux&logoColor=white" alt="Platform" />
<img src="https://img.shields.io/badge/License-MIT-F472B6?style=for-the-badge" alt="License" />

🔐 登录 / Session · 🎁 每日签到 · 👥 多账号 · 🧾 JSONL · 📢 可选推送 · 🐧 青龙 · ☁️ Actions

[⚡ 30 秒速览](#quick-look) · [🔁 协议与回读](#protocol) · [🔐 凭据](#credentials) · [🐧 青龙](#qinglong) · [☁️ Actions](#actions) · [⌨️ CLI](#cli-json) · [✅ 成功判据](#success) · [✦ 星轨](#star-trail)

</div>

---

<a id="usage-policy"></a>
## 🚫 使用边界与禁止倒卖

> [!IMPORTANT]
> **官方版本永久免费。** 未经作者书面许可，禁止倒卖、付费包装、搬运引流、冒充作者，或使用作者身份与二维码制造官方授权假象。

本仓库、脚本、部署说明和 Release 下载保持免费公开。禁止将本项目或其轻度改名版本包装为付费资源、内部版、独家版、会员权益、收费课程、代部署服务或包更新服务；禁止搬运到其他账号、群组、频道、网盘、电商平台或付费社群进行涨粉、截流、倒卖和引流；禁止删除作者与版权信息后冒充原创。

完整规则见 [NOTICE.md](NOTICE.md)。第三方以“下载费 / 激活费 / 内部版 / 代部署 / 会员门槛”等名义收费，均与作者无关，请停止付款并保留证据。

---

<a id="quick-look"></a>
## ⚡ 30 秒速览

| 维度 | 说明 |
| :--- | :--- |
| **做什么** | 登录 Sub2API 站点，查询每日签到状态并领取奖励。 |
| **输入** | 站点账号密码，或已有 `accessToken` / `refreshToken`；支持多账号。 |
| **协议** | 状态查询 → 空 body 领取 → 状态回读。 |
| **回读** | `reward_amount`、`new_balance`、`checked_in_at` 和 `checked_in_today`。 |
| **输出** | 每账号一条 JSON，最后一行 `SUMMARY` JSON。 |
| **成功判据** | 领取字段完整且再次查询 `checked_in_today=true`。 |

---

## 🧭 这是什么 / 覆盖范围

Sub2API 脚本面向自填站点根地址，支持邮箱密码登录或直接提供 Access Token。它先读取签到状态，再提交领取请求，最后重新读取状态。

### 覆盖范围

- `SUB2API_ACCOUNTS` 密码账号、`SUB2API_SESSIONS` Session 账号和 JSON 账号。
- `POST /api/v1/auth/login`、`POST /api/v1/auth/refresh`。
- `/redeem/checkin/status` 优先，旧路径 `/redeem/checkin` 查询兼容。
- 空 body 领取与 `reward_amount`、`new_balance`、`checked_in_at` 严格校验。
- 重复领取、站点未开启、人工验证、Token 禁用、角色禁止、未确认和鉴权失效分类。
- JSONL、Actions artifact 和可选通知。

---

<a id="protocol"></a>
## 🔁 协议与回读流程

### 请求链

```http
POST /api/v1/auth/login
POST /api/v1/auth/refresh
GET  /api/v1/redeem/checkin/status
GET  /api/v1/redeem/checkin
POST /api/v1/redeem/checkin
GET  /api/v1/redeem/checkin/status
Authorization: Bearer <ACCESS_TOKEN>
```

状态接口优先使用 `/status`；旧站点不支持时回退到 `/redeem/checkin`。领取 POST 不发送请求体。

| 字段 | 要求 |
| :--- | :--- |
| `reward_amount` | 有限且非负的数字。 |
| `new_balance` | 有限数字。 |
| `checked_in_at` | 有效 RFC3339 时间。 |
| `checked_in_today` | 再次查询必须为 true。 |
| `source` | 记录状态读取路径或登录来源。 |

`409` 或 `DAILY_CHECKIN_ALREADY_DONE` 只在后续状态回读确认已签时按 `ALREADY` 处理。Token 禁用和角色禁止不会被当作 `INACTIVE`。

---

<a id="credentials"></a>
## 🔐 凭据与环境变量

### 账号密码

```text
主号|https://sub2api.example|user@example.com|password
小号|https://sub2api2.example|user2@example.com|password2
```

### 已有 Session

```text
主号|https://sub2api.example|ACCESS_TOKEN|42
```

| 变量 | 必填 | 说明 |
| :--- | :---: | :--- |
| `SUB2API_ACCOUNTS` | 二选一 | 多账号密码列表。 |
| `SUB2API_SESSIONS` | 二选一 | 多账号 Session 列表。 |
| `SUB2API_ACCOUNT_FILE` | 否 | 本地账号文件。 |
| `SUB2API_SITE` | 否 | 单账号站点。 |
| `SUB2API_EMAIL` / `SUB2API_PASSWORD` | 否 | 单账号密码登录。 |
| `SUB2API_ACCESS_TOKEN` / `SUB2API_USER_ID` | 否 | 单账号 Session。 |
| `SUB2API_PROXY` | 否 | HTTP(S) 代理。 |
| `SUB2API_WAIT_SECONDS` | 否 | 回读等待秒数。 |
| `PUSHPLUS_TOKEN` / `BARK_URL` | 否 | 推送。 |
| `WECOM_WEBHOOK` / `DINGTALK_WEBHOOK` | 否 | 群机器人。 |
| `GENERIC_WEBHOOK_URL` | 否 | 通用 JSON webhook。 |

---

## 💻 本地快速开始

### PowerShell

```powershell
python -m pip install -r requirements.txt
$env:SUB2API_ACCOUNTS = "主号|https://sub2api.example|user@example.com|password"
python .\sub2api_daily.py
```

### Bash

```bash
python -m pip install -r requirements.txt
export SUB2API_ACCOUNTS='主号|https://sub2api.example|user@example.com|password'
python sub2api_daily.py
```

常用参数：`--query`、`--only 1,3-4`、`--accounts-file sub2api_accounts.txt`、`--wait-seconds 0.5`、`--no-notify`。

---

<a id="qinglong"></a>
## 🐧 青龙

1. 在青龙依赖管理中安装 `requests`，或执行 `pip3 install -r requirements.txt`。
2. 上传 `sub2api_daily.py` 到脚本目录。
3. 在环境变量中配置 `SUB2API_ACCOUNTS`、`SUB2API_SESSIONS`，或单账号变量。
4. 新建定时任务，命令使用 `task sub2api_daily.py`，不要直接写裸 `python`。
5. 建议北京时间：`17 7 * * *`。青龙按面板本地时间执行。

```bash
pip3 install -r requirements.txt
task sub2api_daily.py
```

---

<a id="actions"></a>
## ☁️ GitHub Actions、Secrets 与定时

工作流：`.github/workflows/sub2api.yml`。

| 事件 | 行为 |
| :--- | :--- |
| `push` 到 `main` | pytest、编译检查、Ruff。 |
| `schedule` | 先测试，再执行签到并上传 JSONL artifact。 |
| `workflow_dispatch` | 手动执行。 |
| 未配置 Secret | 输出 notice 并跳过在线执行。 |

### Secrets

| Secret | 说明 |
| :--- | :--- |
| `SUB2API_ACCOUNTS` | 密码账号列表。 |
| `SUB2API_SESSIONS` | Session 账号列表。 |
| `SUB2API_SITE` / `SUB2API_EMAIL` / `SUB2API_PASSWORD` | 单账号密码登录。 |
| `SUB2API_ACCESS_TOKEN` / `SUB2API_USER_ID` | 单账号 Session。 |
| `SUB2API_PROXY` / `SUB2API_WAIT_SECONDS` | 代理与回读等待。 |
| `PUSHPLUS_TOKEN` / `BARK_URL` | 推送。 |
| `WECOM_WEBHOOK` / `DINGTALK_WEBHOOK` | 群机器人。 |
| `GENERIC_WEBHOOK_URL` | 通用 JSON webhook。 |

内置定时为 UTC `17 23 * * *`，对应北京时间约 07:17。原始 JSONL 作为 `sub2api-report` artifact 保留。

---

<a id="cli-json"></a>
## ⌨️ CLI 与 JSON 输出

```powershell
python .\sub2api_daily.py
python .\sub2api_daily.py --query
python .\sub2api_daily.py --only 1,3-4
python .\sub2api_daily.py --no-notify
```

账号 JSON 示例：

```json
{"type":"account","provider":"sub2api","index":1,"label":"主号","status":"CLAIMED","ok":true,"message":"服务端确认签到","http_status":200,"reward_amount":"5","new_balance":"25","checked_in_at":"2026-11-24T08:00:00+08:00","source":"status","details":[]}
```

| 字段 | 说明 |
| :--- | :--- |
| `status` / `ok` | 结果状态与是否成功。 |
| `reward_amount` / `new_balance` | 奖励与新余额。 |
| `checked_in_at` | 服务端签到时间。 |
| `source` | 登录或状态读取来源。 |
| `details` | 非敏感补充信息。 |

---

<a id="result-codes"></a>
## 🧾 结果码

| 结果码 | 成功 | 含义 |
| :--- | :---: | :--- |
| `CLAIMED` | 是 | 领取字段完整且状态回读为今日已签。 |
| `ALREADY` | 是 | 服务端确认今日已经领取。 |
| `QUERY` | 是 | 查询模式，未发送领取请求。 |
| `INACTIVE` | 是 | 站点未开启签到。 |
| `MANUAL_REQUIRED` | 否 | 需要验证码、2FA 或浏览器操作。 |
| `AUTH_EXPIRED` | 否 | 登录态或 Token 失效。 |
| `UNCONFIRMED` | 否 | 请求已发，但字段或状态回读不足。 |
| `API_ERROR` | 否 | HTTP、JSON、配置或业务错误。 |
| `CONFIG_ERROR` | 否 | 站点或账号配置错误。 |

---

<a id="success"></a>
## ✅ 成功判据

| 场景 | 必须满足 |
| :--- | :--- |
| 本次签到 | `reward_amount`、`new_balance`、`checked_in_at` 均有效，且回读 `checked_in_today=true`。 |
| 今日已签到 | 运行前状态已为 true，或重复领取后回读确认 true。 |
| 查询模式 | 只读状态接口，不发送领取请求。 |
| 未确认 | 任一严格字段缺失或状态未翻转时失败。 |

---

## 🧪 测试与静态检查

```bash
python -m pytest -q
python -m compileall -q .
python -m ruff check .
```

离线测试覆盖密码与 Session 解析、站点规范化、严格领取字段、状态接口回退、已签到短路、重复领取、登录后领取、人工验证、Token 禁用、角色禁止、回读时刷新会话和鉴权失效。

---

## 🧱 设计原则

- **严格字段**：奖励、余额、时间、今日状态缺一不可。
- **有界兼容**：状态路径回退只用于查询，不改变成功标准。
- **禁用不是未开启**：Token 禁用、角色禁止和 INACTIVE 分开处理。
- **会话可恢复**：回读遇到过期 Session 时先刷新再复核。
- **空 body 领取**：不注入额外字段。

---

## 🔒 隐私

仓库不包含账号、密码、Access Token、refreshToken、邮箱、UID、日志或真实响应。`sub2api_accounts.txt`、`sub2api-report.json`、`sub2api-report.jsonl`、`auth.json`、Cookie 和缓存已由 `.gitignore` 排除。

---

## 📁 目录结构

```text
Sub2API-Daily/
├── .github/workflows/sub2api.yml
├── assets/
│   ├── donate-alipay.jpg
│   └── donate-wechat.png
├── docs/
│   ├── README.en.md
│   ├── README.zh-Hant.md
│   ├── README.ja.md
│   ├── README.ko.md
│   └── README.pt-BR.md
├── tests/test_sub2api_daily.py
├── CHANGELOG.md
├── LICENSE
├── NOTICE.md
├── THIRD_PARTY_NOTICES.md
├── sub2api_daily.py
├── pyproject.toml
├── README.md
└── requirements.txt
```

---

## 📦 版本与发布

- 当前清单版本：`v1.0.0`，日期 `2026-11-24`。
- 脚本版本与 `sub2api_daily.py` 内的 `VERSION` 保持一致。
- 更新记录见 [CHANGELOG.md](CHANGELOG.md)，下载入口见 [Releases](https://github.com/L0NE-6/Sub2API-Daily/releases)。
- Release 徽标由 GitHub 实时生成；如果页面尚未创建对应 Release，以 `CHANGELOG.md` 和仓库提交为准。

---

## ⚠️ 免责声明

本项目用于个人学习与个人自动化。Sub2API 站点 的活动规则、接口、奖励、风控策略和账号资格由服务方决定。使用前请确认对应服务条款，并自行承担接口变化、账号限制和网络环境带来的风险。

---

## ☕ 支持与投喂

脚本完全免费，赞赏纯自愿，不影响任何功能，也不影响 Issue 响应。

<p align="center">
  <img src="assets/donate-wechat.png" width="260" alt="微信赞赏码" />
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
  <img src="assets/donate-alipay.jpg" width="260" alt="支付宝收款码" />
</p>
<p align="center"><sub>💚 微信支付（左） &nbsp;|&nbsp; 💙 支付宝（右，支持信用卡 / 花呗）</sub></p>

> 收款码仅用于向作者自愿赞赏。任何第三方以代下载、代部署、内部资源或会员群为由收费，均与作者无关。

---

## 💬 反馈与贡献

- 提交 [Issue](https://github.com/L0NE-6/Sub2API-Daily/issues) 时附运行日志、脱敏后的错误字段和复现步骤。
- 发起 [Pull Request](https://github.com/L0NE-6/Sub2API-Daily/pulls) 时保持单文件运行、离线测试和凭据脱敏约束。
- 不要在任何 Issue、PR、截图或日志中粘贴真实 Token、Cookie、密码、UID、手机号或邮箱。

---

<a id="star-trail"></a>
## ✦ Star History / 星轨

<a href="https://star-history.com/#L0NE-6/Sub2API-Daily&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=L0NE-6/Sub2API-Daily&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=L0NE-6/Sub2API-Daily&type=Date" />
    <img alt="Sub2API-Daily Star History" src="https://api.star-history.com/svg?repos=L0NE-6/Sub2API-Daily&type=Date" />
  </picture>
</a>

<div align="center">
  <sub>L0NE-6 · DAILY SIGNAL &nbsp;|&nbsp; 点个 <b>Star</b>，让下一轮自动化有迹可循</sub>
</div>
