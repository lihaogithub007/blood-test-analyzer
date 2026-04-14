# Linux 运维：启动 / 停止 / 重启 / 查看日志（blood-test-analyzer）

本文档整理两种常用运行方式：

- **方式 A（临时/快速）**：`nohup` 后台运行（你现在使用的方式）
- **方式 B（推荐/长期）**：`systemd` 服务托管（更稳定、可自启、便于排障）

---

## 方式 A：nohup（临时/快速）

### 启动

```bash
cd /opt/blood-test-analyzer
source .venv/bin/activate

nohup uvicorn app:app --host 0.0.0.0 --port 8000 --workers 1 > uvicorn.log 2>&1 &
echo $!
```

> 建议保留 `--workers 1`：SQLite 并发写入更稳。

### 查看日志

```bash
tail -n 200 /opt/blood-test-analyzer/uvicorn.log
```

### 查看进程 / 端口

```bash
ps -ef | grep "uvicorn app:app" | grep -v grep
ss -lntp | grep :8000 || netstat -lntp | grep :8000
```

### 停止

找到 PID 后停止：

```bash
kill <PID>
```

如果优雅退出不生效，再强制：

```bash
kill -9 <PID>
```

### 重启

```bash
# 1) 停止旧进程（kill PID）
# 2) 再按“启动”命令重新 nohup
```

---

## 方式 B：systemd（推荐/长期）

### 1) 创建 service 文件

创建 `/etc/systemd/system/blood-test.service`：

```ini
[Unit]
Description=Blood Test Analyzer (FastAPI)
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/blood-test-analyzer
EnvironmentFile=/opt/blood-test-analyzer/.env

# 若你环境里遇到 HTTPS 证书链问题，可保留这两行
Environment=SSL_CERT_FILE=/etc/pki/tls/certs/ca-bundle.crt
Environment=SSL_CERT_DIR=/etc/pki/ca-trust/extracted/pem

ExecStart=/opt/blood-test-analyzer/.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8000 --workers 1
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

> `--host 127.0.0.1`：建议只监听本机，再由 nginx 对外提供 80/443。

### 2) 启动 / 停止 / 重启

```bash
systemctl daemon-reload
systemctl enable blood-test
systemctl start blood-test
systemctl status blood-test --no-pager
```

停止：

```bash
systemctl stop blood-test
```

重启：

```bash
systemctl restart blood-test
```

查看是否开机自启：

```bash
systemctl is-enabled blood-test
```

### 3) 查看日志

```bash
journalctl -u blood-test --no-pager -n 200
```

持续跟踪：

```bash
journalctl -u blood-test -f
```

---

## 常见问题速查

### 1) `uvicorn: command not found`

说明你没进入 venv 或依赖未装好：

```bash
cd /opt/blood-test-analyzer
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) 端口占用

```bash
ss -lntp | grep :8000 || netstat -lntp | grep :8000
```

如果是旧进程占用，先 stop/kill 再启动。

