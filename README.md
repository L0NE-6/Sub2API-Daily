<div align="center">

<sub><strong>L0NE-6 · DAILY SIGNAL</strong></sub>

# 🧩 Sub2API Daily

**Sub2API 每日签到 · 多账号 · 状态与领取字段严格回读 · JSONL**

> 当前版本：**v1.0.0**（2026-11-24） · 由 L0NE-6 原创维护

[简体中文](README.md) · [English](docs/README.en.md) · [繁體中文](docs/README.zh-Hant.md) · [日本語](docs/README.ja.md) · [한국어](docs/README.ko.md) · [Português (BR)](docs/README.pt-BR.md)

🔐 站点登录 / Session · 🎁 每日签到 · 👥 多账号隔离 · 🧾 JSONL · 📢 可选推送 · 🐧 青龙友好 · ☁️ GitHub Actions

<img src="https://img.shields.io/badge/Version-v1.0.0-2ea44f?style=for-the-badge&logo=github" />
<img src="https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
<img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20%E9%9D%92%E9%BE%99-4EAA25?style=for-the-badge&logo=linux&logoColor=white" />
<img src="https://img.shields.io/badge/Deploy-%E9%9D%92%E9%BE%99%20%7C%20GitHub%20Actions-2088FF?style=for-the-badge&logo=githubactions&logoColor=white" />
<img src="https://img.shields.io/badge/License-MIT-F472B6?style=for-the-badge" />

</div>

---

<a id="usage-policy"></a>
## 🚫 使用边界

> [!IMPORTANT]
> **官方版本永久免费。** 未经作者书面许可，禁止付费包装、搬运引流、冒充作者，或使用作者身份与二维码制造官方授权假象。

禁止将本仓库、脚本、部署说明或 Release 包装成付费资源、内部版、独家版、会员权益、收费课程、代部署服务或包更新服务；禁止删除作者与版权信息后冒充原创。完整规则见 **[NOTICE.md](NOTICE.md)**。

---

## ✨ 30 秒速览

| 维度 | 说明 |
| :--- | :--- |
| **做什么** | 登录 Sub2API 站点，查询每日签到状态并领取奖励，随后再次回读今日状态。 |
| **输入** | 站点账号密码，或已有 `accessToken` / `refreshToken`；支持多账号。 |
| **输出** | 每账号一行 JSON，最后一行 `SUMMARY` JSON。 |
| **部署** | Windows / Linux / 青龙面板 / GitHub Actions。 |
| **依赖** | Python 3.9+；运行时依赖 `requests`。 |
| **成功判据** | 领取响应必须有 `reward_amount`、`new_balance`、`checked_in_at`，且再次查询 `checked_in_today=true`。 |

---

## 🧠 签到与严格回读

脚本优先查询：

```http
GET  /api/v1/redeem/checkin/status
```

站点不支持该路径时回退：

```http
GET  /api/v1/redeem/checkin
```

领取统一使用：

```http
POST /api/v1/redeem/checkin
Authorization: Bearer <ACCESS_TOKEN>
```

`POST` 不发送请求体。领取成功后，脚本要求：

- `reward_amount`：有限且非负的数字；
- `new_balance`：有限的数字；
- `checked_in_at`：有效 RFC3339 时间；
- 再次读取状态时 `checked_in_today=true`。

任一项缺失或无法回读，结果都是 `UNCONFIRMED`，不会伪报成功。传统回退状态可以用于查询，但如果没有严格领取字段，也会保持未确认。

---

## 🔑 账号格式

### 账号密码登录

```text
主号|https://sub2api.example|user@example.com|password
小号|https://sub2api2.example|user2@example.com|password2
```

### 已有 Session

```text
主号|https://sub2api.example|ACCESS_TOKEN|42
小号|https://sub2api2.example|ACCESS_TOKEN_2|43
```

也支持 JSON：

```json
[
  {
    "name": "主号",
    "site": "https://sub2api.example",
    "email": "user@example.com",
    "password": "password"
  },
  {
    "name": "小号",
    "site": "https://sub2api2.example",
    "accessToken": "ACCESS_TOKEN",
    "refreshToken": "REFRESH_TOKEN",
    "userId": "42"
  }
]
```

站点必须是站点根地址，不要填写 `/api/v1` 或 `/v1`。

---

## 🚀 青龙面板

1. 将 `sub2api_daily.py` 上传到青龙脚本目录。
2. 在青龙环境变量中新增 `SUB2API_ACCOUNTS` 或 `SUB2API_SESSIONS`。
3. 新建任务，命令使用 `task sub2api_daily.py`。
4. 在青龙依赖管理中安装 `requests`，或执行 `pip3 install requests`。

建议每天运行一次，例如 `17 7 * * *`。

---

## ☁️ GitHub Actions

工作流位于 `.github/workflows/sub2api.yml`：

- `push` 到 `main`：运行离线测试、编译检查和 Ruff；
- `schedule`：每天执行一次；
- `workflow_dispatch`：手动运行；
- 未配置 Secret 时跳过在线执行并输出 notice；
- JSONL 原始结果作为 artifact 保留。

Secret 可使用 `SUB2API_ACCOUNTS`、`SUB2API_SESSIONS` 或单账号变量。

---

## 🔧 环境变量

| 变量 | 必填 | 说明 |
| :--- | :---: | :--- |
| `SUB2API_ACCOUNTS` | 二选一 | 多账号，`备注\|站点\|邮箱\|密码` |
| `SUB2API_SESSIONS` | 二选一 | 多账号 Session，`备注\|站点\|accessToken\|userId` |
| `SUB2API_ACCOUNT_FILE` | 可选 | 本地账号文件 |
| `SUB2API_SITE` | 可选 | 单账号站点 |
| `SUB2API_EMAIL` | 可选 | 单账号邮箱 |
| `SUB2API_PASSWORD` | 可选 | 单账号密码 |
| `SUB2API_ACCESS_TOKEN` | 可选 | 单账号 accessToken |
| `SUB2API_USER_ID` | 可选 | 单账号 userId |
| `SUB2API_PROXY` | 可选 | HTTP(S) 代理 |
| `SUB2API_WAIT_SECONDS` | 可选 | 领取后回读等待秒数 |
| `PUSHPLUS_TOKEN` | 可选 | PushPlus |
| `BARK_URL` | 可选 | Bark |
| `WECOM_WEBHOOK` | 可选 | 企业微信机器人 |
| `DINGTALK_WEBHOOK` | 可选 | 钉钉机器人 |
| `GENERIC_WEBHOOK_URL` | 可选 | 通用 JSON webhook |

---

## ⌨️ 本地运行

```powershell
python -m pip install -r requirements.txt
$env:SUB2API_ACCOUNTS = "主号|https://sub2api.example|user@example.com|password"
python .\sub2api_daily.py
python .\sub2api_daily.py --query
python .\sub2api_daily.py --only 1,3-4
python .\sub2api_daily.py --no-notify
```

`--query` 只查询状态，不发送领取请求。

---

## ✅ 结果状态

| 状态 | 含义 | 是否成功 |
| :--- | :--- | :---: |
| `CLAIMED` | 领取字段完整且状态回读为今日已签 | ✅ |
| `ALREADY` | 服务端确认今日已经领取 | ✅ |
| `QUERY` | 查询模式，未发送领取请求 | ✅ |
| `INACTIVE` | 站点未开启签到 | ✅ |
| `MANUAL_REQUIRED` | 需要验证码、2FA 或浏览器操作 | ❌ |
| `AUTH_EXPIRED` | 登录态失效 | ❌ |
| `UNCONFIRMED` | 请求已发，但字段或状态回读不足 | ❌ |
| `API_ERROR` / `CONFIG_ERROR` | HTTP、JSON、配置或运行时错误 | ❌ |

---

## 🧪 测试与质量检查

```powershell
python -m unittest discover -s tests -v
python -m compileall -q .
python -m ruff check .
```

测试使用 fake session，不访问真实站点，不需要真实账号或 Token。

---

## 🔒 隐私说明

- 仓库不包含账号、密码、accessToken、refreshToken 或推送凭据。
- 账号只通过环境变量、青龙变量或 GitHub Secrets 注入。
- 输出会脱敏邮箱、手机号、密码、Token 和推送凭据。
- `.gitignore` 已排除本地账号文件、报告、缓存和日志。

---

## ☕ 支持与投喂

脚本完全免费。如果它确实帮你省了时间，欢迎自愿赞赏；不影响任何功能，也不影响 Issue 响应。

<p align="center">
  <img src="assets/donate-wechat.png" width="260" alt="微信赞赏码" />
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
  <img src="assets/donate-alipay.jpg" width="260" alt="支付宝收款码" />
</p>
<p align="center"><sub>💚 微信支付（左） &nbsp;|&nbsp; 💙 支付宝（右）</sub></p>

---

## ⚠️ 免责声明

本项目用于个人学习和合法的个人自动化。Sub2API 站点的活动规则、接口、奖励和账号资格由各站点决定；使用前请确认对应服务条款，并自行承担账号、网络和活动变化带来的风险。
