#!/usr/bin/env python3
"""
手动 P2P 示例：展示如何在没有自动 P2P 的情况下实现多节点数据共享

这个示例演示了三种方式：
1. 客户端手动协调（最简单）
2. 简单的 Tracker 实现
3. 自动 Copy-on-Miss
"""
import sys
import os
sys.path.append(os.getcwd())

import packice
from typing import Dict, List, Optional

# ============================================================================
# 方式 1: 客户端手动协调
# ============================================================================

def demo_manual_coordination():
    """最简单的方式：客户端手动在节点间复制数据"""
    print("=" * 60)
    print("演示 1: 客户端手动协调多节点")
    print("=" * 60)

    # 创建两个独立的进程内 Peer（模拟两个节点）
    print("\n📡 创建两个独立节点...")
    node_a = packice.connect()  # 节点 A
    node_b = packice.connect()  # 节点 B
    print("   ✓ Node A 创建")
    print("   ✓ Node B 创建")

    # 在节点 A 创建数据
    print("\n📝 在 Node A 创建数据...")
    data = b"Data from Node A"
    writer_a = node_a.create(size=len(data))
    writer_a.buffer[:] = data
    writer_a.seal()
    object_id = writer_a.id
    print(f"   对象ID: {object_id}")
    print(f"   数据: {data.decode('utf-8')}")

    # 手动从 A 复制到 B
    print("\n🔄 手动复制到 Node B...")
    reader_a = node_a.get(object_id)
    copied_data = bytes(reader_a.buffer)

    writer_b = node_b.create(size=len(copied_data))
    writer_b.buffer[:] = copied_data
    writer_b.seal()
    reader_a.close()

    print(f"   ✓ 复制完成")

    # 验证两个节点都有数据
    print("\n✅ 验证数据...")
    reader_b = node_b.get(writer_b.id)
    print(f"   Node A: {bytes(node_a.get(object_id).buffer)}")
    print(f"   Node B: {bytes(reader_b.buffer)}")
    reader_b.close()

    # 清理
    node_a.delete(object_id)
    node_b.delete(writer_b.id)
    print("   ✓ 清理完成\n")


# ============================================================================
# 方式 2: 简单的 Tracker
# ============================================================================

class SimpleTracker:
    """
    简单的对象位置跟踪器

    功能：
    - 记录哪些节点有哪些对象
    - 查询对象位置
    """
    def __init__(self):
        # object_id -> [peer_id, ...]
        self.registry: Dict[str, List[str]] = {}
        print("[Tracker] 初始化")

    def register(self, object_id: str, peer_id: str):
        """注册对象位置"""
        if object_id not in self.registry:
            self.registry[object_id] = []
        if peer_id not in self.registry[object_id]:
            self.registry[object_id].append(peer_id)
            print(f"[Tracker] 注册: {object_id[:8]}... -> {peer_id}")

    def find_peers(self, object_id: str) -> List[str]:
        """查找拥有对象的节点"""
        peers = self.registry.get(object_id, [])
        print(f"[Tracker] 查询: {object_id[:8]}... -> {peers}")
        return peers

    def unregister(self, object_id: str, peer_id: str):
        """取消注册"""
        if object_id in self.registry:
            self.registry[object_id] = [
                p for p in self.registry[object_id] if p != peer_id
            ]
            if not self.registry[object_id]:
                del self.registry[object_id]


class P2PPeer:
    """
    带 P2P 功能的 Peer 包装器

    功能：
    - 创建对象时自动注册到 Tracker
    - 读取对象时自动从其他节点拉取（Copy-on-Miss）
    """
    # 全局节点注册表（模拟网络）
    _peer_registry: Dict[str, 'P2PPeer'] = {}

    def __init__(self, peer_id: str, tracker: SimpleTracker):
        self.peer_id = peer_id
        self.tracker = tracker
        self.client = packice.connect()  # 每个 Peer 有自己的存储

        # 全局 object_id 到本地 object_id 的映射
        # 因为当前 Packice 每个节点的 object_id 是独立的
        self.global_to_local: Dict[str, str] = {}

        # 注册到全局（模拟网络可达）
        P2PPeer._peer_registry[peer_id] = self
        print(f"[{peer_id}] 节点启动")

    def create(self, data: bytes) -> str:
        """
        创建对象并注册到 Tracker

        Returns:
            global_object_id（用于跨节点标识）
        """
        writer = self.client.create(size=len(data))
        writer.buffer[:] = data
        writer.seal()
        local_id = writer.id

        # 本地 ID 就是全局 ID（创建者决定）
        global_id = local_id
        self.global_to_local[global_id] = local_id

        # 注册到 Tracker
        self.tracker.register(global_id, self.peer_id)
        print(f"[{self.peer_id}] 创建对象: {global_id[:8]}...")

        return global_id

    def get(self, global_object_id: str, auto_fetch: bool = True):
        """
        获取对象，支持 Copy-on-Miss

        Args:
            global_object_id: 全局对象ID
            auto_fetch: 如果本地没有，是否自动从其他节点拉取
        """
        # 检查是否有本地副本
        if global_object_id in self.global_to_local:
            local_id = self.global_to_local[global_object_id]
            try:
                reader = self.client.get(local_id)
                print(f"[{self.peer_id}] 本地命中: {global_object_id[:8]}...")
                return reader
            except KeyError:
                # 本地映射存在但对象已删除
                del self.global_to_local[global_object_id]

        if not auto_fetch:
            raise KeyError(f"Object {global_object_id} not found locally")

        # 本地没有，触发 Copy-on-Miss
        print(f"[{self.peer_id}] 本地未命中: {global_object_id[:8]}...")
        return self._fetch_from_network(global_object_id)

    def _fetch_from_network(self, global_object_id: str):
        """
        从网络拉取对象（Copy-on-Miss）

        流程：
        1. 查询 Tracker 获取候选节点
        2. 从候选节点读取数据
        3. 缓存到本地（用新的本地 ID）
        4. 建立全局 ID 到本地 ID 的映射
        5. 注册本地副本到 Tracker
        6. 返回本地副本
        """
        # 1. 查询 Tracker
        peers = self.tracker.find_peers(global_object_id)
        if not peers:
            raise KeyError(f"Object {global_object_id} not found in network")

        # 2. 从候选节点拉取
        for peer_id in peers:
            if peer_id == self.peer_id:
                continue  # 跳过自己

            try:
                # 获取远程 Peer（模拟网络调用）
                remote_peer = P2PPeer._peer_registry.get(peer_id)
                if not remote_peer:
                    continue

                print(f"[{self.peer_id}] 从 {peer_id} 拉取数据...")

                # 从远程读取（使用远程的本地 ID）
                remote_local_id = remote_peer.global_to_local.get(global_object_id)
                if not remote_local_id:
                    continue

                remote_reader = remote_peer.client.get(remote_local_id)
                data = bytes(remote_reader.buffer)
                remote_reader.close()

                # 3. 缓存到本地（创建新的本地对象）
                local_writer = self.client.create(size=len(data))
                local_writer.buffer[:] = data
                local_writer.seal()
                local_id = local_writer.id

                # 4. 建立映射
                self.global_to_local[global_object_id] = local_id

                # 5. 注册本地副本
                self.tracker.register(global_object_id, self.peer_id)
                print(f"[{self.peer_id}] 缓存完成: {global_object_id[:8]}... (本地ID: {local_id[:8]}...)")

                # 6. 返回本地副本
                return self.client.get(local_id)

            except Exception as e:
                print(f"[{self.peer_id}] 从 {peer_id} 拉取失败: {e}")
                import traceback
                traceback.print_exc()
                continue

        raise RuntimeError(f"Failed to fetch {global_object_id} from any peer")

    def delete(self, global_object_id: str):
        """删除对象并从 Tracker 注销"""
        try:
            if global_object_id in self.global_to_local:
                local_id = self.global_to_local[global_object_id]
                self.client.delete(local_id)
                del self.global_to_local[global_object_id]
            self.tracker.unregister(global_object_id, self.peer_id)
            print(f"[{self.peer_id}] 删除对象: {global_object_id[:8]}...")
        except KeyError:
            pass


def demo_with_tracker():
    """使用 Tracker 实现自动节点发现和 Copy-on-Miss"""
    print("=" * 60)
    print("演示 2: 带 Tracker 的自动 P2P")
    print("=" * 60)

    # 创建 Tracker
    print("\n🌐 启动 Tracker...")
    tracker = SimpleTracker()

    # 创建三个节点
    print("\n📡 启动三个节点...")
    peer_a = P2PPeer("node-a", tracker)
    peer_b = P2PPeer("node-b", tracker)
    peer_c = P2PPeer("node-c", tracker)

    # Node A 创建数据
    print("\n📝 Node A 创建数据...")
    data = b"Distributed data from Node A"
    object_id = peer_a.create(data)

    # Node B 自动拉取（Copy-on-Miss）
    print("\n🔄 Node B 请求数据（触发 Copy-on-Miss）...")
    reader_b = peer_b.get(object_id, auto_fetch=True)
    data_b = bytes(reader_b.buffer)
    reader_b.close()
    print(f"   ✓ Node B 获取到: {data_b.decode('utf-8')}")

    # Node C 也自动拉取
    print("\n🔄 Node C 请求数据（触发 Copy-on-Miss）...")
    reader_c = peer_c.get(object_id, auto_fetch=True)
    data_c = bytes(reader_c.buffer)
    reader_c.close()
    print(f"   ✓ Node C 获取到: {data_c.decode('utf-8')}")

    # 现在三个节点都有数据
    print("\n✅ 验证所有节点都有数据...")
    print(f"   Tracker 记录: {tracker.registry[object_id]}")

    # 清理
    print("\n🧹 清理...")
    peer_a.delete(object_id)
    peer_b.delete(object_id)
    peer_c.delete(object_id)
    print("   ✓ 清理完成\n")


# ============================================================================
# 方式 3: 性能对比
# ============================================================================

def demo_performance():
    """对比本地命中 vs Copy-on-Miss 的性能"""
    print("=" * 60)
    print("演示 3: 性能对比（本地 vs 远程）")
    print("=" * 60)

    import time

    tracker = SimpleTracker()
    peer_a = P2PPeer("node-a", tracker)
    peer_b = P2PPeer("node-b", tracker)

    # 创建 10MB 数据
    print("\n📊 创建 10MB 测试数据...")
    data = b"X" * (10 * 1024 * 1024)
    object_id = peer_a.create(data)

    # 本地读取（Node A）
    print("\n⚡ 本地读取性能（Node A）...")
    start = time.time()
    reader = peer_a.get(object_id)
    local_data = bytes(reader.buffer)
    local_time = (time.time() - start) * 1000
    reader.close()
    print(f"   耗时: {local_time:.2f}ms")
    print(f"   吞吐: {(10 / local_time) * 1000:.2f} MB/s")

    # 远程拉取（Node B，Copy-on-Miss）
    print("\n🌐 远程拉取性能（Node B，首次）...")
    start = time.time()
    reader = peer_b.get(object_id, auto_fetch=True)
    remote_data = bytes(reader.buffer)
    remote_time = (time.time() - start) * 1000
    reader.close()
    print(f"   耗时: {remote_time:.2f}ms")
    print(f"   吞吐: {(10 / remote_time) * 1000:.2f} MB/s")
    print(f"   开销: {remote_time / local_time:.1f}x")

    # 再次读取（已缓存）
    print("\n⚡ 缓存命中性能（Node B，第二次）...")
    start = time.time()
    reader = peer_b.get(object_id)
    cached_data = bytes(reader.buffer)
    cached_time = (time.time() - start) * 1000
    reader.close()
    print(f"   耗时: {cached_time:.2f}ms")
    print(f"   吞吐: {(10 / cached_time) * 1000:.2f} MB/s")

    # 验证数据一致性
    print("\n✅ 验证数据一致性...")
    assert local_data == remote_data == cached_data
    print("   ✓ 所有副本数据一致")

    # 清理
    peer_a.delete(object_id)
    peer_b.delete(object_id)
    print("\n")


# ============================================================================
# 主函数
# ============================================================================

def main():
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 16 + "手动 P2P 演示程序" + " " * 22 + "║")
    print("║" + " " * 8 + "展示如何在无自动 P2P 下实现多节点" + " " * 15 + "║")
    print("╚" + "═" * 58 + "╝")
    print()

    try:
        # 演示 1：手动协调
        demo_manual_coordination()

        # 演示 2：Tracker + Copy-on-Miss
        demo_with_tracker()

        # 演示 3：性能对比
        demo_performance()

        print("=" * 60)
        print("✅ 所有演示完成！")
        print("=" * 60)
        print("\n核心概念:")
        print("  ✓ 客户端手动协调（最简单）")
        print("  ✓ Tracker 元数据服务")
        print("  ✓ Copy-on-Miss 自动拉取")
        print("  ✓ 本地缓存加速")
        print()
        print("💡 提示:")
        print("  - 这些是手动实现，展示 P2P 原理")
        print("  - 未来版本将内置自动 P2P 功能")
        print("  - 详见 P2P_CONNECTIVITY.md")
        print()

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
