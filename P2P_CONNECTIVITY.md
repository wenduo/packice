# Packice Peer 互连指南

## 当前状态：单节点架构

**重要**：当前 Packice 实现（v2）是**单节点架构**，Peer 之间**还不能自动发现和连接**。

### 现有功能

✅ **单节点功能**（已完成）：
- 进程内 Peer（DirectTransport）
- 本地跨进程 Peer（UdsTransport）
- 网络 Peer（HttpTransport，骨架）
- 零拷贝数据访问

❌ **多节点功能**（未实现）：
- 节点自动发现
- 分布式 Resolver
- 节点间数据同步
- Gossip 协议

---

## 当前如何连接多个节点

虽然没有自动 P2P 功能，但可以通过**客户端协调**实现多节点数据共享。

### 方式 1：客户端手动协调（当前可用）

```python
import packice

# 连接到两个独立的节点
node_a = packice.connect("http://node-a:8080")
node_b = packice.connect("http://node-b:8080")

# 在节点 A 创建数据
writer_a = node_a.create(size=1024)
writer_a.buffer[:] = b"data from node A"
writer_a.seal()
object_id = writer_a.id

# 手动复制到节点 B
reader_a = node_a.get(object_id)
writer_b = node_b.create(size=1024)
writer_b.buffer[:] = bytes(reader_a.buffer)  # 复制数据
writer_b.seal()

# 现在两个节点都有这个数据
print(f"Node A: {object_id}")
print(f"Node B: {writer_b.id}")
```

### 方式 2：通过共享存储（当前可用）

```bash
# 节点 A: 使用共享 NFS 目录
python -m packice.interface.cli \
  --impl fs \
  --transport http \
  --port 8080 \
  --data-dir /shared/packice

# 节点 B: 使用同一个共享目录
python -m packice.interface.cli \
  --impl fs \
  --transport http \
  --port 8081 \
  --data-dir /shared/packice
```

**优点**：两个节点访问相同的文件系统，数据自动共享
**缺点**：需要 NFS/EFS 等共享存储，不适合跨数据中心

### 方式 3：UDS + 本地多进程（当前可用）

```python
# 进程 1: 启动节点
python -m packice.interface.cli --impl mem --transport uds

# 进程 2, 3, 4...: 都连接到同一个 UDS socket
import packice
client = packice.connect("/tmp/packice.sock")

# 所有进程共享同一个 Peer，天然互通
```

**优点**：零配置，高性能
**缺点**：仅限同一台机器

---

## 未来的 P2P 架构（规划中）

设计文档 (`docs/design.md`) 规划了完整的 P2P 层：

### 架构组件

```
┌─────────────────────────────────────────┐
│         应用客户端                      │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│          Packice Peer                   │
│  ┌──────────────────────────────────┐   │
│  │  Tracker Client (节点发现)      │   │
│  ├──────────────────────────────────┤   │
│  │  Gossip Protocol (状态同步)     │   │
│  ├──────────────────────────────────┤   │
│  │  P2P Transport (数据传输)       │   │
│  ├──────────────────────────────────┤   │
│  │  Peer (核心逻辑)                │   │
│  └──────────────────────────────────┘   │
└─────────────────────────────────────────┘
               │
               ▼
     其他 Packice Peers
```

### 1. Tracker（对象发现服务）

**功能**：轻量级元数据服务，记录哪些节点有哪些对象。

```python
# 伪代码（未来实现）
class Tracker:
    """
    中心化或分布式的对象位置服务
    """
    def register_object(self, object_id: str, peer_address: str):
        """节点封存对象后，向 Tracker 注册"""
        pass

    def find_peers(self, object_id: str) -> List[str]:
        """查询哪些节点有指定对象"""
        pass
```

**工作流程**：
```
1. Node A seal 对象 → 向 Tracker 注册
2. Node B acquire(read) miss → 查询 Tracker
3. Tracker 返回候选节点列表 [Node A, Node C]
4. Node B 从候选节点拉取数据
```

### 2. Gossip（节点发现和状态传播）

**功能**：去中心化的节点发现，传播节点健康状态和对象位置信息。

```python
# 伪代码（未来实现）
class GossipProtocol:
    """
    无需中心服务器，节点间互相通知
    """
    def broadcast_presence(self):
        """周期性广播：我在线，我有这些对象"""
        pass

    def handle_peer_info(self, peer_info):
        """接收其他节点的信息"""
        pass
```

**工作流程**：
```
1. 每个节点周期性广播：
   - 节点地址
   - 可用对象列表
   - 健康状态
2. 节点收到 gossip 消息后更新本地路由表
3. acquire(read) miss 时查询本地路由表
```

### 3. P2P Transport（高效数据传输）

**功能**：优化的点对点数据传输，支持多种协议。

```python
# 已有骨架（packice/p2p/transport.py）
class P2PTransport:
    def transfer(self, source: RemoteBlob, dest: Blob):
        """
        从远程节点高效传输数据到本地
        支持：
        - HTTP/HTTPS
        - TCP 直连
        - RDMA (未来)
        - 断点续传
        - 多源并行下载
        """
        pass
```

**优化特性**：
- 分块传输 + 校验
- 多源聚合下载（类似 BitTorrent）
- 自动选择最优节点（延迟、带宽）
- 传输层加密

---

## Copy-on-Miss 机制（v0 设计）

v0 设计中定义了节点间数据复制的流程：

### 完整流程

```
Client → Node B: acquire(objid, READ)
          ↓
Node B: 本地没有数据 (miss)
          ↓
Node B → Tracker: find_peers(objid)
          ↓
Tracker → Node B: [Node A, Node C]
          ↓
Node B → Node A: acquire(objid, READ)
          ↓
Node A → Node B: (Lease, Blob handle)
          ↓
Node B: acquire(objid, CREATE) 本地
          ↓
Node B: 流式复制数据 (Node A → Node B)
          ↓
Node B: seal() 本地副本
          ↓
Node B: release() 远程租约
          ↓
Node B → Tracker: register(objid, Node B)
          ↓
Node B → Client: (Lease, Blob handle)
```

### Python 示例（未来 API）

```python
import packice

# 未来的自动 P2P 版本
client = packice.connect("http://node-b:8080")

# acquire 时自动触发 copy-on-miss
reader = client.get("some-object-id")
# Node B 在后台：
# 1. 查询 Tracker
# 2. 从 Node A 拉取数据
# 3. 缓存到本地
# 4. 返回本地副本的租约

data = bytes(reader.buffer)  # 读取的是本地缓存
```

---

## 实现路线图

### Phase 1: 基础 P2P（Q1 2026）

- [ ] 实现 Tracker 服务器
  - HTTP API：`/register`, `/find`, `/heartbeat`
  - 内存存储（单机版）
- [ ] Peer 集成 Tracker 客户端
  - seal() 后自动注册
  - acquire(READ) miss 时查询
- [ ] 完善 P2P Transport
  - HTTP 远程拉取
  - 流式复制大对象

**里程碑**：两个节点可以通过 Tracker 互相发现和拉取数据

### Phase 2: 去中心化（Q2 2026）

- [ ] Gossip 协议实现
  - 节点发现
  - 心跳检测
  - 故障转移
- [ ] 分布式 Tracker
  - 一致性哈希
  - 副本同步
- [ ] 智能路由
  - 延迟感知
  - 负载均衡

**里程碑**：无需中心 Tracker，节点自组织

### Phase 3: 高级特性（Q3 2026）

- [ ] 多源下载
  - 类似 BitTorrent 的分片
  - 并行下载
- [ ] 主动复制
  - 热数据自动复制
  - 副本数控制
- [ ] 跨数据中心优化
  - WAN 加速
  - 智能缓存

---

## 现在如何手动实现类似功能

虽然自动 P2P 未实现，但可以手动构建：

### 示例：简单的手动 Tracker

```python
import packice
from typing import Dict, List
import requests

class SimpleTracker:
    """简单的对象位置跟踪器"""
    def __init__(self):
        self.registry: Dict[str, List[str]] = {}

    def register(self, object_id: str, peer_url: str):
        """注册对象位置"""
        if object_id not in self.registry:
            self.registry[object_id] = []
        if peer_url not in self.registry[object_id]:
            self.registry[object_id].append(peer_url)

    def find_peers(self, object_id: str) -> List[str]:
        """查找拥有对象的节点"""
        return self.registry.get(object_id, [])

class P2PPeer:
    """带手动 P2P 功能的 Peer 包装器"""
    def __init__(self, local_url: str, tracker: SimpleTracker):
        self.local_url = local_url
        self.tracker = tracker
        self.client = packice.connect(local_url)

    def create_and_register(self, data: bytes, object_id: str = None):
        """创建对象并注册到 Tracker"""
        writer = self.client.create(size=len(data))
        writer.buffer[:] = data
        writer.seal()

        # 注册到 Tracker
        self.tracker.register(writer.id, self.local_url)
        return writer.id

    def get_or_fetch(self, object_id: str):
        """获取对象，如果本地没有则从其他节点拉取"""
        try:
            # 尝试本地获取
            return self.client.get(object_id)
        except KeyError:
            # 本地没有，查询 Tracker
            peers = self.tracker.find_peers(object_id)
            if not peers:
                raise KeyError(f"Object {object_id} not found in network")

            # 从第一个可用节点拉取
            for peer_url in peers:
                if peer_url == self.local_url:
                    continue
                try:
                    # 从远程节点读取
                    remote_client = packice.connect(peer_url)
                    remote_reader = remote_client.get(object_id)
                    data = bytes(remote_reader.buffer)
                    remote_reader.close()

                    # 缓存到本地
                    local_writer = self.client.create(size=len(data))
                    local_writer.buffer[:] = data
                    local_writer.seal()

                    # 注册本地副本
                    self.tracker.register(object_id, self.local_url)

                    # 返回本地副本
                    return self.client.get(object_id)
                except Exception as e:
                    print(f"Failed to fetch from {peer_url}: {e}")
                    continue

            raise RuntimeError(f"Failed to fetch object {object_id} from any peer")

# 使用示例
tracker = SimpleTracker()

# 启动三个节点
peer_a = P2PPeer("http://node-a:8080", tracker)
peer_b = P2PPeer("http://node-b:8081", tracker)
peer_c = P2PPeer("http://node-c:8082", tracker)

# Node A 创建数据
object_id = peer_a.create_and_register(b"shared data", "obj-123")

# Node B 可以自动拉取
reader = peer_b.get_or_fetch(object_id)
print(bytes(reader.buffer))  # b"shared data"

# Node C 也可以拉取
reader = peer_c.get_or_fetch(object_id)
print(bytes(reader.buffer))  # b"shared data"
```

### 运行完整示例

1. **启动节点**：
```bash
# 终端 1
python -m packice.interface.cli --impl mem --transport http --port 8080

# 终端 2
python -m packice.interface.cli --impl mem --transport http --port 8081

# 终端 3
python -m packice.interface.cli --impl mem --transport http --port 8082
```

2. **运行 P2P 客户端**（使用上面的代码）

---

## 设计决策

### 为什么当前没有 P2P？

1. **先完善单节点**：确保核心抽象稳定
2. **避免过早优化**：P2P 增加复杂度，先验证需求
3. **灵活性优先**：当前架构易于添加 P2P 层

### 架构优势

即使没有自动 P2P，当前架构也支持：
- ✅ 通过客户端手动协调多节点
- ✅ 通过共享存储自然集群
- ✅ 为未来 P2P 预留接口（RemoteBlob, P2PTransport）

---

## 参考资料

### 相关设计文档

- **v0 设计**：最早的 Resolver + Copy-on-Miss 设计
- **v2 设计**：当前架构，P2P 标记为 Planned
- **BitTorrent**：多源下载的灵感来源
- **Gossip Protocol**：去中心化节点发现

### 类似项目

- **SeaweedFS**：分布式对象存储，Master-Volume 架构
- **Ceph**：CRUSH 算法进行数据分布
- **IPFS**：内容寻址 + DHT 节点发现

---

## 总结

| 特性 | 当前状态 | 未来计划 |
|------|----------|----------|
| 单节点缓存 | ✅ 完成 | 持续优化 |
| 手动多节点 | ✅ 可用 | 保持支持 |
| 自动节点发现 | ❌ 未实现 | Phase 1 |
| Tracker 服务 | ❌ 未实现 | Phase 1 |
| Gossip 协议 | ❌ 未实现 | Phase 2 |
| 多源下载 | ❌ 未实现 | Phase 3 |

**建议**：
- 当前环境：使用客户端协调或共享存储
- 等待 P2P：关注项目 Roadmap
- 贡献代码：P2P 层是开放的贡献领域！

---

**问题反馈**：如果你有 P2P 相关需求，欢迎在 GitHub Issues 中讨论！
