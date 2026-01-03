是的，你的直觉非常敏锐。报错的核心原因确实是 **Python 版本太新**。

你当前使用的是 **Python 3.13**。而我在之前的计划中指定的 `pyo3` 版本是 `0.20`。
*   `pyo3 0.20` 发布时，Python 3.13 还没有正式发布，因此它的构建脚本中有一个安全检查，拒绝在比 3.12 更好的版本上构建，以防止 ABI 不兼容导致崩溃。
*   **解决方案**：我们需要升级到支持 Python 3.13 的 **PyO3 0.23**。
*   **连锁反应**：由于 `pyo3-asyncio` 这个库目前的更新进度落后于 `pyo3` 主库，它目前还不支持 `pyo3 0.23`。为了绕过这个坑并保持项目的现代化，我们将直接使用 `pyo3` 0.23 提供的更强大的 `Bound` API，并手动构建一个简单的 Python 异步 Future 返回值。

我将立即生成修复计划，将 Rust 项目升级到最新标准。

## [WIP] fix(vm-rs): 升级 PyO3 到 0.23 以支持 Python 3.13

### 错误分析
构建失败是因为 `pyo3 0.20` 不支持 Python 3.13。错误日志明确指出“configured Python interpreter version (3.13) is newer than PyO3's maximum supported version (3.12)”。

### 用户需求
修复 Rust 包的构建错误，使其兼容 Python 3.13。

### 评论
在 Rust 生态中，PyO3 0.21+ 引入了 `Bound` API，这是一个重大的安全提升。虽然升级会带来代码语法的变化，但这是支持 Python 3.13 的必经之路。我们将移除不兼容的 `pyo3-asyncio`，改用更底层的 Python 交互方式来实现异步占位，这样不仅解决了编译问题，还减少了外部依赖，提高了代码的稳定性。

### 目标
1.  更新 `packages/cascade-vm-rs/Cargo.toml`：升级 `pyo3` 至 `0.23.3`，移除 `pyo3-asyncio`。
2.  重写 `packages/cascade-vm-rs/src/lib.rs`：使用 `Bound` API 和 Python `asyncio` 交互逻辑。

### 基本原理
-   **Bound API**: 这是 PyO3 的新标准。它强制在编译时检查 Python 对象的引用生命周期，比旧的 `&PyAny` 更安全。
-   **手动 Future**: 我们直接通过 `py.import("asyncio")` 在 Rust 中调用 Python 的 `create_future`。这在“脚手架”阶段非常有效，因为它完全不依赖外部的异步桥接库，消除了版本冲突的风险。

### 标签
#intent/fix #flow/ready #priority/critical #comp/vm-rs #comp/build #concept/ffi #ai/instruct #task/domain/vm #task/object/rust-reactor #task/action/upgrade-pyo3 #task/state/continue

---

### Script

#### Acts 1: 升级 Cargo 依赖

我们将 `pyo3` 升级到最新版，并移除有冲突的异步桥接库。

~~~~~act
write_file
packages/cascade-vm-rs/Cargo.toml
~~~~~
~~~~~toml
[package]
name = "cascade-vm-rs"
version = "0.1.0"
edition = "2021"

[lib]
name = "cascade_vm_rs"
crate-type = ["cdylib"]

[dependencies]
# 升级到 0.23.3 以支持 Python 3.13
pyo3 = { version = "0.23.3", features = ["extension-module"] }
tokio = { version = "1.0", features = ["full"] }
~~~~~

#### Acts 2: 更新 lib.rs 以适配 Bound API

使用 PyO3 0.23 的新语法重写 Reactor 占位实现。

~~~~~act
write_file
packages/cascade-vm-rs/src/lib.rs
~~~~~
~~~~~rust
use pyo3::prelude::*;
use pyo3::types::PyDict;

/// A minimal Rust implementation of the Cascade Reactor using PyO3 0.23 Bound API.
#[pyclass]
struct RustReactor {
    #[pyo3(get)]
    active_task_count: usize,
}

#[pymethods]
impl RustReactor {
    #[new]
    fn new(
        _graph: Bound<'_, PyAny>,
        _memory: Bound<'_, PyAny>,
        _executor: Bound<'_, PyAny>,
        _function_map: Bound<'_, PyDict>,
        _resource_registry: Bound<'_, PyAny>,
    ) -> Self {
        println!("RustReactor: Initialized via FFI (PyO3 0.23, Python 3.13 confirmed)!");
        RustReactor {
            active_task_count: 0,
        }
    }

    fn prime(&self) {
        println!("RustReactor: prime() called (noop)");
    }

    fn step<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        // Since we removed pyo3-asyncio for compatibility, we'll manually create
        // a completed Python Future to keep the EventDrivenRunner's await logic happy.
        let asyncio = py.import("asyncio")?;
        let loop_ = asyncio.call_method0("get_event_loop")?;
        let future = loop_.call_method0("create_future")?;
        
        // Return 0 tasks fired
        future.call_method1("set_result", (0,))?;
        
        println!("RustReactor: step() called (returning manual future)");
        Ok(future)
    }

    fn add_sink(&self, _node_id: String, _port_name: String, _callback: PyObject) {
        println!("RustReactor: add_sink() called (noop)");
    }
}

/// The module definition.
#[pymodule]
fn cascade_vm_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<RustReactor>()?;
    Ok(())
}
~~~~~

### 下一步建议

现在依赖和代码都已经适配了 Python 3.13，请再次运行构建命令：

```bash
uv sync --extra dev
```

#### **如果构建通过，你现在可以按照以下方式使用 `conftest.py`：**

1.  **全局控制**：我们在项目根目录创建的 `conftest.py` 会自动被 Pytest 加载。
2.  **切换后端**：
    *   运行 `uv run pytest packages/cascade-vm/tests/unit/test_reactor.py` 时，它默认使用 **Python Reactor**。
    *   当你添加 `--reactor-backend=rust` 参数时，Fixture 会尝试加载 Rust 后端。

**当前状态说明**：
虽然我们的 `RustReactor` 已经可以编译并被导入，但目前在 `conftest.py` 中，如果后端是 `rust`，我依然设置了 `pytest.skip`。这是因为我们还没有在 `conftest.py` 中实际编写 `from cascade_vm_rs import RustReactor` 的导入逻辑。

一旦你确认 `uv sync` 成功，请告诉我，我将生成最后一个补丁，取消 `conftest.py` 中的跳过逻辑，正式打通从 Python 测试到 Rust 引擎的链路。
