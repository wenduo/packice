#!/usr/bin/env python3
"""
测试运行中的 Packice 节点
"""
import sys
import os
sys.path.append(os.getcwd())

import packice

def test_node(socket_path="/tmp/packice_demo.sock"):
    """测试 UDS 节点"""
    print(f"🔗 连接到节点: {socket_path}")

    try:
        client = packice.connect(socket_path)
        print("✅ 连接成功！")

        # 创建对象
        print("\n📝 创建对象...")
        data = b"Hello from client!"
        writer = client.create(size=len(data))
        print(f"   对象ID: {writer.id}")

        # 写入数据
        writer.buffer[:] = data
        print(f"   已写入: {len(data)} 字节")

        # 封存
        writer.seal()
        print("   ✅ 已封存")

        # 读取
        print("\n📖 读取对象...")
        reader = client.get(writer.id)
        content = bytes(reader.buffer)
        print(f"   读取到: {content.decode('utf-8')}")
        print(f"   ✅ 数据匹配: {content == data}")

        # 清理
        reader.close()
        client.delete(writer.id)
        print("\n✅ 测试完成！")

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0

if __name__ == "__main__":
    socket_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/packice_demo.sock"
    sys.exit(test_node(socket_path))
