# Packice 节点运行指南

本指南介绍如何启动和使用 Packice 节点。

---

## 快速开始

### 1. 启动最简单的内存节点（UDS）

```bash
# 使用内存存储 + Unix Domain Socket
python -m packice.interface.cli --impl mem --transport uds
```

节点将：
- 使用内存存储（MemoryPeer）
- 监听 `/tmp/packice.sock`
- 支持零拷贝访问

### 2. 连接并使用节点

```python
import packice

# 连接到 UDS 节点
client = packice.connect("/tmp/packice.sock")

# 创建对象
writer = client.create(size=1024)
writer.buffer[:] = b"Hello, Packice!"
writer.seal()

# 读取对象
reader = client.get(writer.id)
print(bytes(reader.buffer))
reader.close()

# 删除对象
client.delete(writer.id)
```

---

## 节点配置选项

### 命令行参数

```bash
python -m packice.interface.cli [选项]

选项:
  --impl {fs,mem}        存储实现方式
  --transport {http,uds} 传输协议
  --port PORT            HTTP 端口（默认: 8080）
  --socket SOCKET        UDS socket 路径（默认: /tmp/packice.sock）
  --data-dir DATA_DIR    文件系统数据目录（默认: ./data）
```

---

## 四种节点配置

### 1. 内存节点 + UDS（推荐：高性能本地缓存）

```bash
python -m packice.interface.cli \
  --impl mem \
  --transport uds \
  --socket /tmp/packice.sock
```

**特点**：
- ✅ 零拷贝内存访问
- ✅ 极高性能（680+ MB/s）
- ✅ 适合本地进程间通信
- ⚠️ 数据不持久化
- ⚠️ 仅限本地访问

**使用场景**：
- AI 模型加载缓存
- 容器 sidecar 模式
- 本地高性能数据共享

**客户端连接**：
```python
client = packice.connect("/tmp/packice.sock")
```

---

### 2. 文件系统节点 + UDS（推荐：持久化本地缓存）

```bash
python -m packice.interface.cli \
  --impl fs \
  --transport uds \
  --socket /tmp/packice.sock \
  --data-dir ./packice_data
```

**特点**：
- ✅ 数据持久化到磁盘
- ✅ 零拷贝文件访问
- ✅ 节点重启后数据保留
- ⚠️ 性能受磁盘限制
- ⚠️ 仅限本地访问

**使用场景**：
- 需要持久化的本地缓存
- 大文件共享
- 数据集缓存

**客户端连接**：
```python
client = packice.connect("/tmp/packice.sock")
```

---

### 3. 内存节点 + HTTP（网络内存缓存）

```bash
python -m packice.interface.cli \
  --impl mem \
  --transport http \
  --port 8080
```

**特点**：
- ✅ 网络访问（跨主机）
- ✅ 易于调试（HTTP/JSON）
- ⚠️ 数据不持久化
- ⚠️ HTTP 协议开销

**使用场景**：
- 分布式内存缓存
- 跨主机数据共享
- 开发和调试

**客户端连接**：
```python
client = packice.connect("http://localhost:8080")
```

---

### 4. 文件系统节点 + HTTP（网络文件缓存）

```bash
python -m packice.interface.cli \
  --impl fs \
  --transport http \
  --port 8080 \
  --data-dir ./packice_data
```

**特点**：
- ✅ 网络访问 + 持久化
- ✅ 数据在磁盘上
- ⚠️ 性能受磁盘和网络限制

**使用场景**：
- 分布式文件缓存
- 共享存储服务
- NFS 替代方案

**客户端连接**：
```python
client = packice.connect("http://server-ip:8080")
```

---

## 实战示例

### 示例 1：启动本地高性能缓存节点

```bash
# 终端 1: 启动节点
python -m packice.interface.cli --impl mem --transport uds

# 终端 2: 使用节点
python test_node.py /tmp/packice.sock
```

### 示例 2：启动持久化网络节点

```bash
# 创建数据目录
mkdir -p /var/lib/packice

# 启动节点
python -m packice.interface.cli \
  --impl fs \
  --transport http \
  --port 8080 \
  --data-dir /var/lib/packice

# 客户端访问（可以在其他机器上）
python3 << 'EOF'
import packice

client = packice.connect("http://your-server:8080")
writer = client.create(size=1024)
writer.buffer[:] = b"Distributed cache!"
writer.seal()
print(f"Object created: {writer.id}")
EOF
```

### 示例 3：多节点部署

```bash
# 节点 A（主机 A）
python -m packice.interface.cli \
  --impl mem \
  --transport http \
  --port 8080

# 节点 B（主机 B）
python -m packice.interface.cli \
  --impl fs \
  --transport http \
  --port 8081 \
  --data-dir /data/packice

# 客户端可以连接到任意节点
# 未来版本将支持 P2P 自动发现和数据同步
```

---

## 配置对比表

| 配置 | 性能 | 持久化 | 网络访问 | 推荐场景 |
|------|------|--------|----------|----------|
| mem + UDS | ⭐⭐⭐⭐⭐ | ❌ | ❌ | 本地高性能缓存 |
| fs + UDS | ⭐⭐⭐⭐ | ✅ | ❌ | 本地持久化缓存 |
| mem + HTTP | ⭐⭐⭐ | ❌ | ✅ | 分布式内存缓存 |
| fs + HTTP | ⭐⭐ | ✅ | ✅ | 分布式文件缓存 |

---

## 生产环境建议

### systemd 服务配置

创建 `/etc/systemd/system/packice.service`：

```ini
[Unit]
Description=Packice Cache Node
After=network.target

[Service]
Type=simple
User=packice
Group=packice
WorkingDirectory=/opt/packice
ExecStart=/usr/bin/python3 -m packice.interface.cli \
  --impl fs \
  --transport http \
  --port 8080 \
  --data-dir /var/lib/packice
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
sudo systemctl daemon-reload
sudo systemctl enable packice
sudo systemctl start packice
sudo systemctl status packice
```

### Docker 容器运行

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY packice /app/packice
COPY pyproject.toml /app/

# UDS 模式
EXPOSE 8080
VOLUME /tmp/packice.sock
VOLUME /data

CMD ["python", "-m", "packice.interface.cli", \
     "--impl", "fs", \
     "--transport", "uds", \
     "--socket", "/tmp/packice.sock", \
     "--data-dir", "/data"]
```

运行容器：
```bash
docker run -d \
  -v /tmp/packice.sock:/tmp/packice.sock \
  -v /data/packice:/data \
  --name packice-node \
  packice:latest
```

---

## 客户端使用

### Python SDK

```python
import packice

# 方式 1: 连接到 UDS 节点
client = packice.connect("/tmp/packice.sock")

# 方式 2: 连接到 HTTP 节点
client = packice.connect("http://localhost:8080")

# 方式 3: 进程内使用（无需节点）
client = packice.connect()  # 自动创建私有 Peer

# 方式 4: 共享内存 Peer
client = packice.connect("memory://shared")

# 统一的 API
writer = client.create(size=1024)
writer.buffer[:] = b"data"
writer.seal()

reader = client.get(writer.id)
data = bytes(reader.buffer)
reader.close()
```

### 上下文管理器

```python
import packice

client = packice.connect("/tmp/packice.sock")

# 自动资源管理
with client.create(size=1024) as obj:
    obj.buffer[:] = b"auto cleanup"
    obj.seal()
    # 退出时自动 close()
```

---

## 监控和调试

### 检查节点状态

```bash
# 检查 UDS socket
ls -lh /tmp/packice.sock

# 检查进程
ps aux | grep packice

# 测试连接
python test_node.py /tmp/packice.sock
```

### 日志

节点会输出到 stdout/stderr：
```
Using MemoryPeer
UDS Server listening on /tmp/packice.sock
Node started. Press Ctrl+C to stop.
```

### 性能测试

```bash
# 运行性能演示
python demo.py

# 预期结果
# 写入吞吐: 680+ MB/s
# 读取吞吐: 680+ MB/s
```

---

## 故障排查

### UDS 节点无法启动

**问题**：`Address already in use`

**解决**：
```bash
# 删除旧的 socket 文件
rm /tmp/packice.sock

# 重新启动节点
python -m packice.interface.cli --impl mem --transport uds
```

### HTTP 节点端口被占用

**问题**：`Port 8080 already in use`

**解决**：
```bash
# 使用其他端口
python -m packice.interface.cli --impl mem --transport http --port 8081
```

### 客户端连接失败

**问题**：`Connection refused`

**检查**：
```bash
# 1. 确认节点正在运行
ps aux | grep packice

# 2. 确认 socket/端口正确
ls /tmp/packice.sock  # UDS
netstat -tlnp | grep 8080  # HTTP

# 3. 测试连接
python test_node.py /tmp/packice.sock
```

---

## 下一步

- 查看 `demo.py` 了解更多使用示例
- 查看 `VERSION_EVOLUTION.md` 了解架构设计
- 查看 `docs/design.md` 了解完整设计文档
- 查看 `examples/` 目录查看更多示例

---

## 快速参考

```bash
# 启动内存节点（推荐开发）
python -m packice.interface.cli --impl mem --transport uds

# 启动持久化节点（推荐生产）
python -m packice.interface.cli --impl fs --transport http --port 8080

# 测试节点
python test_node.py /tmp/packice.sock

# 运行完整演示
python demo.py
```
