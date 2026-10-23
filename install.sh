#!/usr/bin/env bash
# VPS Guard Lite 一键安装 (Debian/Ubuntu, 需 root)
set -euo pipefail

if [ "$(id -u)" != "0" ]; then
  echo "请用 root 运行: sudo bash install.sh"; exit 1
fi

read -rp "请输入 Bot Token (从 @BotFather 获取): " BOT_TOKEN
read -rp "请输入你的 Telegram Chat ID: " CHAT_ID

install -m 755 vps_guard.py /usr/local/bin/vps_guard.py
mkdir -p /var/lib/vps-guard

printf 'BOT_TOKEN=%s\nCHAT_ID=%s\n' "$BOT_TOKEN" "$CHAT_ID" > /etc/vps-guard.env
chmod 600 /etc/vps-guard.env

cat > /etc/systemd/system/vps-guard.service <<'EOF'
[Unit]
Description=VPS Guard Lite - Telegram server monitor bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /usr/local/bin/vps_guard.py
EnvironmentFile=/etc/vps-guard.env
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now vps-guard
sleep 2
systemctl --no-pager status vps-guard | head -12
echo "安装完成。打开 Telegram 给你的机器人发送 /status 验证。"
echo "卸载: systemctl disable --now vps-guard && rm /usr/local/bin/vps_guard.py /etc/vps-guard.env /etc/systemd/system/vps-guard.service"
