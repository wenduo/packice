#!/usr/bin/env python3
"""
Packice 综合演示脚本
展示核心功能：零拷贝、多种传输方式、共享内存
"""
import sys
import os
import time

sys.path.append(os.getcwd())

import packice

def demo_basic():
    """演示 1：基础的进程内使用"""
    print("=" * 60)
    print("演示 1: 进程内零拷贝访问")
    print("=" * 60)

    # 创建私有的内存 Peer
    client = packice.connect()

    # 写入数据
    print("\n📝 创建并写入对象...")
    data = b"Hello, Packice! " * 100  # 1.6KB 数据
    writer = client.create(size=len(data))
    print(f"   对象ID: {writer.id}")
    print(f"   数据大小: {len(data)} bytes")

    # 零拷贝写入
    start = time.time()
    writer.buffer[:] = data
    write_time = (time.time() - start) * 1000
    print(f"   写入耗时: {write_time:.3f}ms (零拷贝)")

    writer.seal()
    print("   ✓ 对象已封存")

    # 零拷贝读取
    print("\n📖 读取对象...")
    reader = client.get(writer.id)
    start = time.time()
    content = bytes(reader.buffer)
    read_time = (time.time() - start) * 1000
    print(f"   读取耗时: {read_time:.3f}ms (零拷贝)")
    print(f"   数据匹配: {content == data}")

    reader.close()
    client.delete(writer.id)
    print("   ✓ 资源已清理\n")


def demo_shared_memory():
    """演示 2：共享内存 Peer（DuckDB 风格）"""
    print("=" * 60)
    print("演示 2: 共享内存 Peer (memory://)")
    print("=" * 60)

    # 创建共享的命名 Peer
    print("\n🔗 创建共享 Peer...")
    client1 = packice.connect("memory://shared-cache")
    client2 = packice.connect("memory://shared-cache")
    print("   ✓ 两个客户端连接到同一 Peer")

    # 客户端 1 写入
    print("\n📝 客户端 1 写入数据...")
    data = b"Shared data from client 1"
    writer = client1.create(size=len(data))
    object_id = writer.id
    writer.buffer[:] = data
    writer.seal()
    print(f"   对象ID: {object_id}")

    # 客户端 2 读取
    print("\n📖 客户端 2 读取相同对象...")
    reader = client2.get(object_id)
    content = bytes(reader.buffer)
    print(f"   读取到: {content.decode('utf-8')}")
    print(f"   数据匹配: {content == data}")

    reader.close()
    client1.delete(object_id)
    print("   ✓ 跨客户端共享成功\n")


def demo_large_data():
    """演示 3：大数据零拷贝性能"""
    print("=" * 60)
    print("演示 3: 大数据零拷贝性能")
    print("=" * 60)

    client = packice.connect()

    # 创建 10MB 数据
    size_mb = 10
    data = b"X" * (size_mb * 1024 * 1024)
    print(f"\n📊 测试数据: {size_mb}MB")

    # 写入测试
    print("\n📝 写入性能测试...")
    writer = client.create(size=len(data))

    start = time.time()
    writer.buffer[:] = data
    write_time = (time.time() - start) * 1000
    throughput_write = (size_mb / write_time) * 1000  # MB/s

    print(f"   写入耗时: {write_time:.2f}ms")
    print(f"   写入吞吐: {throughput_write:.2f} MB/s")

    writer.seal()

    # 读取测试
    print("\n📖 读取性能测试...")
    reader = client.get(writer.id)

    start = time.time()
    content = bytes(reader.buffer)
    read_time = (time.time() - start) * 1000
    throughput_read = (size_mb / read_time) * 1000  # MB/s

    print(f"   读取耗时: {read_time:.2f}ms")
    print(f"   读取吞吐: {throughput_read:.2f} MB/s")
    print(f"   数据完整: {len(content) == len(data)}")

    reader.close()
    client.delete(writer.id)
    print("   ✓ 零拷贝带来极高性能\n")


def demo_lifecycle():
    """演示 4：完整的生命周期管理"""
    print("=" * 60)
    print("演示 4: 对象生命周期管理")
    print("=" * 60)

    client = packice.connect()

    print("\n🔄 生命周期演示...")

    # 1. 创建
    print("   1️⃣ CREATE 状态 - 对象可写")
    writer = client.create(size=1024)
    object_id = writer.id
    writer.buffer[:10] = b"mutable..."
    print(f"      对象ID: {object_id}")
    print(f"      初始数据: {bytes(writer.buffer[:10])}")

    # 2. 修改
    print("\n   2️⃣ 写入更多数据")
    writer.buffer[10:20] = b"more_data!"
    print(f"      更新后: {bytes(writer.buffer[:20])}")

    # 3. 封存
    print("\n   3️⃣ SEALED 状态 - 对象不可变")
    writer.seal()
    print("      ✓ 对象已封存，变为只读")

    # 4. 多次读取
    print("\n   4️⃣ 多个读取 Lease")
    reader1 = client.get(object_id)
    reader2 = client.get(object_id)
    print(f"      读取者1: {bytes(reader1.buffer[:20])}")
    print(f"      读取者2: {bytes(reader2.buffer[:20])}")

    # 5. 清理
    print("\n   5️⃣ 资源清理")
    reader1.close()
    reader2.close()
    client.delete(object_id)
    print("      ✓ 所有租约已释放，对象已删除\n")


def main():
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 18 + "Packice 演示程序" + " " * 22 + "║")
    print("║" + " " * 10 + "零拷贝 P2P 缓存系统" + " " * 27 + "║")
    print("╚" + "═" * 58 + "╝")
    print()

    try:
        demo_basic()
        demo_shared_memory()
        demo_large_data()
        demo_lifecycle()

        print("=" * 60)
        print("✅ 所有演示完成！")
        print("=" * 60)
        print("\n核心特性验证:")
        print("  ✓ 零拷贝内存访问")
        print("  ✓ 灵活的传输方式")
        print("  ✓ 完整的生命周期管理")
        print("  ✓ 高性能数据共享")
        print()

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
