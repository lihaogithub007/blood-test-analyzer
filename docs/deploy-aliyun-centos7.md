# 部署到阿里云 Linux（CentOS 7）——blood-test-analyzer

本文档用于把本项目部署到 **阿里云 ECS（CentOS 7）** 上运行，并支持**公网访问**。

> 说明：本项目后端为 FastAPI（Python），数据库默认使用 SQLite（本机文件）。

---

## 0. 部署目标与访问方式

- **临时/快速公网访问**：直接暴露 `8000` 端口（HTTP）
  - 访问：`http://<公网IP>:8000/`
  - 优点：最快
  - 缺点：不安全、无 HTTPS、端口直暴露（不建议长期使用）
- **更推荐（后续）**：`nginx(80/443)` 反代到 `127.0.0.1:8000`，并配置域名 + HTTPS

本文档先覆盖“快速公网访问”的完整步骤；末尾给出“推荐形态”的下一步。

---

## 1. 前置条件

- **ECS 安全组入方向**：放行
  - `22/tcp`（SSH）
  - `8000/tcp`（临时公网访问；后续建议改为只放行 80/443）
- **服务器出网可用**：能访问智谱接口域名 `open.bigmodel.cn`
- **项目目录**：建议放到 `/opt/blood-test-analyzer`

---

## 2. 拉取代码

```bash
cd /opt
git clone <your_repo_ssh_url> blood-test-analyzer
cd /opt/blood-test-analyzer
```

---

## 3. 系统依赖（CentOS 7）

```bash
yum update -y
yum install -y git gcc make wget perl \
  zlib-devel bzip2-devel libffi-devel readline-devel sqlite-devel xz-devel tk-devel \
  ca-certificates

update-ca-trust force-enable
update-ca-trust extract
```

---

## 4. 安装 OpenSSL 1.1.1（解决 Python HTTPS/SSL）

CentOS 7 自带 OpenSSL 通常较旧；为确保 Python 3.10 的 `ssl` 模块可用，建议独立安装 OpenSSL 1.1.1 到 `/opt/openssl111`。

```bash
cd /usr/src
wget https://www.openssl.org/source/openssl-1.1.1w.tar.gz
tar -xzf openssl-1.1.1w.tar.gz
cd openssl-1.1.1w

./config --prefix=/opt/openssl111 --openssldir=/opt/openssl111 shared zlib
make -j"$(nproc)"
make install

/opt/openssl111/bin/openssl version
```

---

## 5. 安装 Python 3.10（绑定 OpenSSL 1.1.1）

> 注意：不要使用 `--enable-optimizations`（会触发 PGO，在 CentOS 7 上较常见失败）。

```bash
cd /usr/src
wget https://www.python.org/ftp/python/3.10.14/Python-3.10.14.tgz
tar -xzf Python-3.10.14.tgz
cd Python-3.10.14

make distclean || true
export CPPFLAGS="-I/opt/openssl111/include"
export LDFLAGS="-L/opt/openssl111/lib"
export LD_LIBRARY_PATH="/opt/openssl111/lib"

./configure --prefix=/usr/local --with-ensurepip=install \
  --with-openssl=/opt/openssl111 --with-openssl-rpath=auto

make -j"$(nproc)"
make altinstall
```

验证：

```bash
/usr/local/bin/python3.10 --version
/usr/local/bin/python3.10 -c "import ssl; print(ssl.OPENSSL_VERSION)"
```

如果出现 `CERTIFICATE_VERIFY_FAILED`，通常是 CA 证书链未正确启用，先执行第 3 节的 `ca-certificates + update-ca-trust`。

---

## 6. 配置项目环境变量（`.env`）

```bash
cd /opt/blood-test-analyzer
cp .env.example .env
vi .env
```

填入（示例）：

```text
ZHIPUAI_API_KEY=your_api_key_here
```

---

## 7. 创建虚拟环境并安装依赖

```bash
cd /opt/blood-test-analyzer
/usr/local/bin/python3.10 -m venv .venv
source .venv/bin/activate

pip install -U pip setuptools wheel
pip install -r requirements.txt
```

### 7.1 PyMuPDF（`pymupdf`）相关说明

在某些环境/镜像源下，`pymupdf` 可能会尝试从源码构建并下载 MuPDF 资源，耗时较长甚至卡住。建议：

- 先确保系统 CA 正常：`ca-certificates` + `update-ca-trust`
- 必要时可在执行安装时显式传入：

```bash
export SSL_CERT_FILE=/etc/pki/tls/certs/ca-bundle.crt
export SSL_CERT_DIR=/etc/pki/ca-trust/extracted/pem
```

若你已经在环境里验证过某个 `pymupdf` 版本可用，也可以把 `requirements.txt` 里的 `pymupdf` 固定到该版本，提升部署可重复性。

---

## 8. 启动（nohup + 对外开放 8000）

> 保持 `--workers 1`：SQLite 多 worker 并发写入容易出现锁问题。

```bash
cd /opt/blood-test-analyzer
source .venv/bin/activate

nohup uvicorn app:app --host 0.0.0.0 --port 8000 --workers 1 > uvicorn.log 2>&1 &
echo $!
```

查看日志：

```bash
tail -n 200 /opt/blood-test-analyzer/uvicorn.log
```

本机自测：

```bash
curl -sS http://127.0.0.1:8000/api/patients
```

公网访问：

- `http://<公网IP>:8000/`
- `http://<公网IP>:8000/api/patients`

---

## 9. 推荐的下一步（更适合长期对外服务）

- 使用 **systemd** 托管 uvicorn（开机自启、崩溃自动拉起、日志集中）
- 使用 **nginx** 反代（只开放 80/443），并配置 **域名 + HTTPS**

