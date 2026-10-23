#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VPS Guard Lite — Telegram 服务器守护机器人（样品版 / 可交付版）

功能:
  /status   服务器状态: 运行时间 / 负载 / 内存 / 磁盘 / 公网IP
  /doctor   一键体检: 关键服务状态 / 监听端口 / 24h 登录成败统计 / 磁盘
  /bans     查看 fail2ban 当前封禁
  事件推送: SSH 登录成功(含来源IP) / fail2ban 新封禁 / 磁盘>=85% / 每日 08:00 日报

只依赖 Python 3 标准库。凭据从环境文件读取 (BOT_TOKEN / CHAT_ID), 不写死在代码里。
部署: 见同目录 install.sh 与 README.md
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error

API = "https://api.telegram.org/bot{token}/{method}"
STATE_PATH = os.environ.get("VPS_GUARD_STATE", "/var/lib/vps-guard/state.json")
REPORT_HOUR = 8  # 每日报表时间 (服务器本地时区小时)


def load_env():
    token = os.environ.get("BOT_TOKEN", "")
    chat_id = os.environ.get("CHAT_ID", "")
    if not token or not chat_id:
        env_file = os.environ.get("VPS_GUARD_ENV", "/etc/vps-guard.env")
        try:
            with open(env_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("BOT_TOKEN="):
                        token = line.split("=", 1)[1].strip()
                    elif line.startswith("CHAT_ID="):
                        chat_id = line.split("=", 1)[1].strip()
        except FileNotFoundError:
            pass
    if not token or not chat_id:
        print("缺少 BOT_TOKEN / CHAT_ID, 请检查 /etc/vps-guard.env", file=sys.stderr)
        sys.exit(1)
    return token, chat_id


TOKEN, CHAT_ID = load_env()


def tg(method, **params):
    url = API.format(token=TOKEN, method=method)
    data = json.dumps(params).encode("utf-8")
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError):
        return {"ok": False}


def send(text):
    return tg("sendMessage", chat_id=CHAT_ID, text=text)


def sh(cmd, timeout=15):
    try:
        out = subprocess.run(cmd, shell=True, capture_output=True,
                             text=True, timeout=timeout)
        return out.stdout.strip()
    except Exception:
        return ""


def load_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"offset": 0, "journal_cursor": "", "last_report_date": "",
                "disk_alerted": False}


def save_state(st):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f)
    os.replace(tmp, STATE_PATH)


def fmt_status():
    up = sh("uptime -p") or "-"
    load = sh("cat /proc/loadavg | awk '{print $1\" \"$2\" \"$3}'")
    mem = sh("free -m | awk '/^Mem:/{printf \"%d/%d MB (%.0f%%)\", $3, $2, $3*100/$2}'")
    disk = sh("df -h / | awk 'NR==2{print $3\"/\"$2\" (\"$5\")\"}'")
    ip = sh("curl -s --max-time 8 https://api.ipify.org") or "未知"
    return (f"🖥 服务器状态\n运行: {up}\n负载: {load}\n内存: {mem}\n"
            f"磁盘: {disk}\n公网IP: {ip}")


def fmt_doctor():
    lines = ["🩺 一键体检"]
    for svc in ("ssh", "sshd", "fail2ban", "xray", "nginx", "docker"):
        st = sh(f"systemctl is-active {svc} 2>/dev/null")
        if st:
            lines.append(f"服务 {svc}: {st}")
    ports = sh("ss -tlnp 2>/dev/null | awk 'NR>1{print $4}' | sed 's/.*://' "
               "| sort -un | tr '\\n' ' '")
    lines.append(f"监听端口: {ports or '-'}")
    ok = sh("journalctl -u ssh -u sshd --since '-24 hours' --no-pager 2>/dev/null "
            "| grep -c 'Accepted '") or "0"
    fail = sh("journalctl -u ssh -u sshd --since '-24 hours' --no-pager 2>/dev/null "
              "| grep -c 'Failed password'") or "0"
    lines.append(f"24h SSH: 成功 {ok} 次 / 失败 {fail} 次")
    disk_pct = sh("df / | awk 'NR==2{gsub(\"%\",\"\",$5); print $5}'") or "?"
    lines.append(f"磁盘使用: {disk_pct}%")
    return "\n".join(lines)


def fmt_bans():
    out = sh("fail2ban-client status sshd 2>/dev/null | grep 'Banned IP list' "
             "| sed 's/.*Banned IP list://'")
    ips = out.split() if out else []
    if not ips:
        return "🚫 当前无封禁 IP (或未安装 fail2ban)"
    return f"🚫 当前封禁 {len(ips)} 个 IP:\n" + "\n".join(ips[:50])


def poll_events(st):
    """用 journalctl 游标增量读取 sshd / fail2ban 事件并推送。"""
    cursor = st.get("journal_cursor", "")
    cmd = ("journalctl -u ssh -u sshd -u fail2ban --no-pager -o cat "
           "--show-cursor -n 200")
    if cursor:
        cmd += f" --after-cursor='{cursor}'"
    raw = sh(cmd, timeout=20)
    if not raw:
        return
    lines = raw.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("-- cursor:"):
            st["journal_cursor"] = line.split(":", 1)[1].strip()
            continue
        m = re.search(r"Accepted \w+ for (\S+) from ([\d.]+) port", line)
        if m:
            send(f"🔐 SSH 登录成功\n用户: {m.group(1)}\n来源: {m.group(2)}")
        m = re.search(r"(?:Ban|NOTICE.*Ban)\s+([\d.]+)", line)
        if m and "fail2ban" in line.lower():
            send(f"🚫 fail2ban 新封禁: {m.group(1)}")
    _ = i


def maybe_daily_report(st):
    now = time.localtime()
    today = time.strftime("%Y-%m-%d", now)
    if now.tm_hour >= REPORT_HOUR and st.get("last_report_date") != today:
        send("☀️ 每日报告\n" + fmt_status() + "\n" + fmt_doctor())
        st["last_report_date"] = today


def maybe_disk_alert(st):
    pct = sh("df / | awk 'NR==2{gsub(\"%\",\"\",$5); print $5}'")
    try:
        pct = int(pct)
    except (TypeError, ValueError):
        return
    if pct >= 85 and not st.get("disk_alerted"):
        send(f"⚠️ 磁盘告警: 根分区已使用 {pct}%")
        st["disk_alerted"] = True
    elif pct < 80:
        st["disk_alerted"] = False


def poll_commands(st):
    offset = st.get("offset", 0)
    res = tg("getUpdates", offset=offset, timeout=25)
    if not res.get("ok"):
        return
    for upd in res.get("result", []):
        st["offset"] = upd["update_id"] + 1
        msg = upd.get("message") or {}
        if str((msg.get("chat") or {}).get("id")) != str(CHAT_ID):
            continue  # 只响应机主本人
        text = (msg.get("text") or "").strip()
        if text == "/status":
            send(fmt_status())
        elif text == "/doctor":
            send(fmt_doctor())
        elif text == "/bans":
            send(fmt_bans())
        elif text in ("/start", "/menu"):
            send("VPS Guard Lite 已就绪\n/status 状态\n/doctor 体检\n/bans 封禁列表")


def main():
    st = load_state()
    send("✅ VPS Guard Lite 已上线, 发送 /status 查看服务器状态")
    last_poll = 0.0
    while True:
        try:
            poll_commands(st)  # 长轮询, 约 25s 一轮
            if time.time() - last_poll > 60:
                poll_events(st)
                maybe_daily_report(st)
                maybe_disk_alert(st)
                save_state(st)
                last_poll = time.time()
        except KeyboardInterrupt:
            break
        except Exception as e:  # 主循环兜底, 保证服务不因单次异常退出
            print(f"loop error: {e}", file=sys.stderr)
            time.sleep(5)


if __name__ == "__main__":
    main()
