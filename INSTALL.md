# Packice 安装指南

## 快速修复（如果遇到 ModuleNotFoundError）

如果你看到 `ModuleNotFoundError: No module named 'requests'` 错误：

```bash
# 方法 1: 使用 pip 直接安装
pip install requests

# 方法 2: 从 pyproject.toml 安装
pip install -e .

# 方法 3: 使用 uv（推荐，如果已安装）
uv pip install -e .
```

---

## 标准安装方法

### 方法 1: 开发模式安装（推荐）

```bash
# 克隆仓库
git clone https://github.com/your-org/packice.git
cd packice

# 安装依赖（可编辑模式）
pip install -e .

# 或使用 uv（更快）
uv pip install -e .
```

### 方法 2: 从 PyPI 安装（未来）

```bash
pip install packice
```

---

## 依赖说明

### 核心依赖

- **requests** (>=2.31.0)
  - 仅用于 HTTP 传输层
  - 如果只使用 UDS 或 DirectTransport，理论上不需要
  - 但建议安装以支持完整功能

### 可选依赖

```bash
# 安装开发依赖
pip install -e ".[dev]"
```

包含：
- pytest: 单元测试
- pytest-asyncio: 异步测试支持

---

## 验证安装

### 1. 检查安装

```python
python3 -c "import packice; print('Packice installed successfully!')"
```

### 2. 运行示例

```bash
# 基础示例
python examples/basic_usage.py

# 完整演示
python demo.py

# UDS 跨进程示例
python examples/uds_example.py
```

---

## 不同环境的安装

### macOS

```bash
# 使用 Homebrew Python
brew install python@3.11
python3.11 -m pip install -e .

# 或使用系统 Python
pip3 install -e .
```

### Linux (Ubuntu/Debian)

```bash
# 安装 Python 3.11+
sudo apt update
sudo apt install python3.11 python3.11-pip

# 安装 packice
pip3 install -e .
```

### Windows

```bash
# 使用 Python 3.11+
python -m pip install -e .
```

### Docker 环境

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . /app

# 安装依赖
RUN pip install -e .

# 运行节点
CMD ["python", "-m", "packice.interface.cli", "--impl", "mem", "--transport", "uds"]
```

---

## 虚拟环境（推荐）

### 使用 venv

```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate  # macOS/Linux
# 或
venv\Scripts\activate     # Windows

# 安装 packice
pip install -e .
```

### 使用 uv（更快）

```bash
# 安装 uv（如果还没有）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 创建并激活虚拟环境
uv venv
source .venv/bin/activate

# 安装依赖
uv pip install -e .
```

---

## 常见问题

### Q: 为什么需要 requests？

A: `requests` 库用于 HTTP 传输层的客户端。如果你只使用：
- 进程内模式 (`packice.connect()`)
- UDS 模式 (`packice.connect("/tmp/packice.sock")`)
- DirectTransport

理论上不需要 requests。但为了支持完整功能，建议安装。

### Q: 能否移除 requests 依赖？

A: 可以。你可以：
1. 只使用 UDS/Direct 传输（无需 requests）
2. 或者我们可以将 HttpTransport 重写为使用标准库 `urllib`

### Q: 安装失败怎么办？

```bash
# 1. 升级 pip
pip install --upgrade pip

# 2. 清理缓存
pip cache purge

# 3. 重新安装
pip install -e . --no-cache-dir

# 4. 如果还是失败，手动安装依赖
pip install requests>=2.31.0
```

### Q: 如何卸载？

```bash
pip uninstall packice
```

---

## 最小化安装（无 HTTP 支持）

如果你确定不需要 HTTP 传输，可以：

```python
# 修改 packice/interface/client.py
# 将 HttpTransport 的导入改为懒加载

# 原来的导入
# from ..transport.http import HttpTransport

# 修改为
try:
    from ..transport.http import HttpTransport
    HTTP_AVAILABLE = True
except ImportError:
    HTTP_AVAILABLE = False

# 在 Client.__init__ 中
if target.startswith("http://") or target.startswith("https://"):
    if not HTTP_AVAILABLE:
        raise ImportError("HTTP transport requires 'requests' library. Install with: pip install requests")
    self.transport = HttpTransport(target)
```

但这需要修改代码，不推荐。

---

## 生产环境部署

### 使用 requirements.txt

```bash
# 生成 requirements.txt
pip freeze > requirements.txt

# 或手动创建
cat > requirements.txt << 'EOF'
requests>=2.31.0
EOF

# 安装
pip install -r requirements.txt
```

### 使用 Poetry

```bash
# 初始化 Poetry 项目
poetry init

# 添加依赖
poetry add requests

# 安装
poetry install
```

---

## 验证所有功能

运行完整测试套件：

```bash
# 1. 基础功能
python examples/basic_usage.py

# 2. UDS 传输
python examples/uds_example.py

# 3. 性能测试
python demo.py

# 4. 所有示例
for example in examples/*.py; do
    echo "Running $example..."
    python "$example"
done
```

---

## 下一步

安装完成后，参考以下文档：

- `RUN_NODE.md` - 如何运行 Packice 节点
- `demo.py` - 功能演示
- `VERSION_EVOLUTION.md` - 架构演进
- `docs/design.md` - 设计文档

开始使用：

```python
import packice

# 最简单的方式
client = packice.connect()
writer = client.create(size=1024)
writer.buffer[:] = b"Hello, Packice!"
writer.seal()
print("Success!")
```
