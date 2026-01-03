好的，我将立即修正这个疏忽，并为你提供详细的后续步骤说明。

## [WIP] fix(deps): 添加 pyo3-asyncio 以支持 Rust 异步方法

### 错误分析
我在 `packages/cascade-vm-rs/src/lib.rs` 中使用了 `pyo3_asyncio::tokio::future_into_py` 函数，以便将 Rust 的 `async` 块转换为 Python 中可 `await` 的协程。然而，我忘记在 `Cargo.toml` 中声明对 `pyo3-asyncio` 这个 crate 的依赖，这将导致编译失败。

### 用户需求
将 `pyo3-asyncio` 依赖项添加到 `cascade-vm-rs` 包中，并说明如何构建和测试这个新的 Rust 包。

### 评论
这是一个简单的依赖补丁，但对于确保 Python 和 Rust 之间的异步 FFI 桥接能够正常工作至关重要。

### 目标
1.  在 `packages/cascade-vm-rs/Cargo.toml` 的 `[dependencies]` 部分添加 `pyo3-asyncio`。

### 基本原理
`pyo3` 核心库处理同步的绑定，而 `pyo3-asyncio` 是一个专门的适配器，用于将 Rust 的 `Future` 和 Python 的 `Awaitable` 进行转换。为了让我们的异步 `step` 方法能够被 Python 的 `asyncio` 事件循环正确驱动，这个依赖是必需的。

### 标签
#intent/fix #flow/ready #priority/critical #comp/vm-rs #comp/build #concept/ffi #ai/instruct #task/domain/vm #task/object/rust-reactor #task/action/dependency-fix #task/state/continue

---

### Script

#### Acts 1: 添加 pyo3-asyncio 依赖

我们将 `pyo3-asyncio` 添加到 `Cargo.toml`。

~~~~~act
patch_file
packages/cascade-vm-rs/Cargo.toml
~~~~~
~~~~~toml.old
[dependencies]
pyo3 = { version = "0.20.0", features = ["extension-module"] }
tokio = { version = "1.0", features = ["full"] }
~~~~~
~~~~~toml.new
[dependencies]
pyo3 = { version = "0.20.0", features = ["extension-module"] }
pyo3-asyncio = { version = "0.20.0", features = ["tokio-runtime"] }
tokio = { version = "1.0", features = ["full"] }
~~~~~

### 下一步建议

我们已经完成了所有代码和配置的修改。现在，你需要手动执行几个命令来构建新包并验证我们的测试基础设施。

请在你的终端中，从项目根目录 (`/home/doucx/Documents/Projects/Cascade`) 执行以下步骤：

#### **步骤 1：同步开发环境并构建 Rust 包**

因为我们添加了一个新的本地包 (`cascade-vm-rs`)，你需要告诉 `uv` 去发现、构建并安装它。运行以下命令：

```bash
uv sync
```

这个命令会：
1.  读取根 `pyproject.toml` 中的 `[tool.uv.workspace]` 部分。
2.  发现新的 `packages/cascade-vm-rs` 成员。
3.  检测到它是一个 Maturin 项目，并调用 Rust 的 `cargo` 来编译 `src/lib.rs`。
4.  将编译好的二进制文件（一个 `.so` 或 `.pyd` 文件）安装到你的虚拟环境中，使其可以被 Python `import`。

#### **步骤 2：验证测试 Fixture 和后端切换**

现在，你可以使用我们之前创建的 `conftest.py` 来运行测试并切换后端。

**A. 使用默认的 Python 后端运行测试：**

```bash
uv run pytest packages/cascade-vm/tests/unit/test_reactor.py
```
*   **预期结果**: 所有测试都应该像以前一样**通过**。这验证了我们的修改没有破坏现有功能。

**B. 尝试使用新的 Rust 后端运行测试：**

```bash
uv run pytest packages/cascade-vm/tests/unit/test_reactor.py --reactor-backend=rust
```
*   **预期结果**: 你应该会看到测试被**跳过 (SKIPPED)**，并显示我们在 `conftest.py` 中定义的消息：“Rust reactor backend is not yet implemented. Skipping test.”。

一旦你确认了这两个命令的输出都符合预期，就意味着我们已经成功地完成了从“接口硬化”到“Rust 桥头堡建立”的全部四个阶段。我们的“一套测试，双重验证”的基础设施已经完全就位。
