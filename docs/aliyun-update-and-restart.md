# 阿里云 Linux：git 更新代码并重启项目（blood-test-analyzer）

本文档用于在阿里云 Linux 服务器上完成以下动作：

- 从 GitHub 拉取最新代码（`git pull`）
- 如有依赖变化，更新 Python 依赖
- 重启后端服务（支持 **nohup** 或 **systemd** 两种运行方式）

> 约定：项目目录为 `/opt/blood-test-analyzer`，Python venv 为 `/opt/blood-test-analyzer/.venv`。

---

## 0. 更新前的安全检查（建议）

### 0.1 确认当前在哪个目录

```bash
cd /opt/blood-test-analyzer
pwd
```

### 0.2 查看当前版本与是否有本地改动

```bash
git status -sb
git log -3 --oneline
```

如果 `git status` 显示有本地修改，建议先处理：

- 不需要的本地改动：丢弃（谨慎）或备份后再更新
- 必须保留的本地改动：先提交到你自己的分支或复制备份

---

## 1. 拉取最新代码

```bash
cd /opt/blood-test-analyzer
git pull
```

如果你不是 `main` 分支，先切到目标分支：

```bash
git branch --show-current
git checkout main
git pull
```

---

## 2. 更新依赖（如有变更）

### 2.1 激活虚拟环境

```bash
cd /opt/blood-test-analyzer
source .venv/bin/activate
python --version
pip --version
```

### 2.2 安装/更新依赖

```bash
pip install -U pip setuptools wheel
pip install -r requirements.txt
```

> 如果你的环境曾遇到 HTTPS 证书链问题，可在当前 shell 增加：
>
> ```bash
> export SSL_CERT_FILE=/etc/pki/tls/certs/ca-bundle.crt
> export SSL_CERT_DIR=/etc/pki/ca-trust/extracted/pem
> ```

---

## 3. 重启项目

根据你当前使用的启动方式选择一种即可。

---

### 方式 A：nohup（你用 nohup 启动的情况）

#### 3.A.1 找到旧进程并停止

```bash
ps -ef | grep "uvicorn app:app" | grep -v grep
```

找到 PID 后：

```bash
kill <PID>
```

如果没停掉，再强制：

```bash
kill -9 <PID>
```

#### 3.A.2 重新 nohup 启动

```bash
cd /opt/blood-test-analyzer
source .venv/bin/activate

nohup uvicorn app:app --host 0.0.0.0 --port 8000 --workers 1 > uvicorn.log 2>&1 &
echo $!
```

#### 3.A.3 验证与看日志

```bash
curl -sS http://127.0.0.1:8000/api/patients
tail -n 200 /opt/blood-test-analyzer/uvicorn.log
```

---

### 方式 B：systemd（推荐/长期）

#### 3.B.1 重启服务

```bash
systemctl restart blood-test
systemctl status blood-test --no-pager
```

#### 3.B.2 查看日志

```bash
journalctl -u blood-test --no-pager -n 200
```

实时跟踪：

```bash
journalctl -u blood-test -f
```

---

## 4. 常见问题

### 4.1 `git pull` 冲突

```bash
git status
```

按提示处理冲突（解决冲突后 `git add ...`，再 `git commit`），然后继续重启步骤。

### 4.2 `uvicorn: command not found`

说明没激活 venv 或依赖没装好：

```bash
cd /opt/blood-test-analyzer
source .venv/bin/activate
pip install -r requirements.txt
```

### 4.3 端口占用

```bash
ss -lntp | grep :8000 || netstat -lntp | grep :8000
```

