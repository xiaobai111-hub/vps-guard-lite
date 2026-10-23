# VPS Guard Lite — Telegram 服务器守护机器人

**Turn your VPS into its own watchdog.** 有人 SSH 登录你的服务器、有人被 fail2ban 封掉、磁盘快满了——第一时间在 Telegram 里通知你，每天早上再送一份服务器日报。

纯 Python 标准库，零第三方依赖；一个文件、一个安装脚本，3 分钟装好。脱胎于作者自用的一套全天候守护系统（已在真实 VPS 上 24×7 运行）。

## 功能

- `/status` 服务器状态：运行时间 / 负载 / 内存 / 磁盘 / 公网 IP
- `/doctor` 一键体检：关键服务状态、监听端口、24 小时 SSH 登录成功/失败统计
- `/bans` 查看 fail2ban 当前封禁列表
- **事件推送**：SSH 登录成功（含来源 IP）、fail2ban 新封禁、磁盘 ≥85% 告警
- **每日 08:00 自动日报**
- **安全设计**：只响应机主本人的 Chat ID，陌生人发消息直接忽略；Token 只存服务器本地 600 权限的环境文件，不经过任何第三方

## 环境要求

- Debian / Ubuntu（其他 systemd 发行版可手动部署）
- Python 3.8+（系统自带即可）
- 一个 Telegram 机器人（在 @BotFather 发 `/newbot` 免费创建）

## 快速安装（约 3 分钟）

```bash
git clone https://github.com/xiaobai111-hub/vps-guard-lite.git
cd vps-guard-lite
sudo bash install.sh
```

按提示输入 Bot Token 和你的 Chat ID，脚本自动部署并设置开机自启。

获取 Chat ID：先给自己的机器人随便发一条消息，再打开
`https://api.telegram.org/bot<你的Token>/getUpdates`，返回 JSON 里的 `chat.id` 就是。

装好后给机器人发 `/status` 验证。

## 卸载

```bash
sudo systemctl disable --now vps-guard
sudo rm /usr/local/bin/vps_guard.py /etc/vps-guard.env /etc/systemd/system/vps-guard.service
```

## 不想自己折腾？有远程部署服务

Lite 版是免费自助版。**全功能版**由作者远程部署到你的服务器，在 Lite 全部功能之外另含：

- 流量月账本与超额预警
- 配置变更看门狗（关键文件被改立刻告警）
- 全链路自检（每天自动验证核心服务真的通）
- 到期提醒管家（服务器/域名续费不再过期）
- 文件助手、远程遥控（重启服务 / 封禁 IP，均带二次确认）
- RSS 订阅推送、里程碑播报

价格：Lite 自助包免费（就是本仓库）｜标准版远程部署 ¥49（首批特价 ¥29.9）｜维护 ¥9.9/月

👉 在 Telegram 找 **[@NebulaGuardCNBot](https://t.me/NebulaGuardCNBot)**（星穹哨兵 NEBULA），点 `/buy` 即可下单，全程按钮操作。

---

*本项目由作者与他的 AI 助理 [Muse](https://muse.ai/join) 协作维护。想拥有同款助理，用邀请码 `VL5IEH` 注册，48 小时内在设置里兑换，我们各得一份词元奖励。*

## License

MIT
