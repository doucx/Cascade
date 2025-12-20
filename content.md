简要回答：
已完成 **第一章：全视之眼** 的全部工作，包括高性能渲染器的核心组件、压力测试框架的集成，以及关键的健壮性（终端自适应和优雅关闭）修复。现在将所有文件系统变更作为一个完整的逻辑单元提交。

摘要头：
## [COMMIT] feat(observatory): Implement ForestRenderer with Numpy and Diff-Rendering

### 标签
#intent/build #intent/fix #flow/ready #priority/high
#comp/observatory #concept/ui #scope/core #scope/dx
#ai/instruct
#task/domain/observatory
#task/object/renderer-proto
#task/action/implementation
#task/state/end

### 错误分析
本次工作解决了两个关键的工程问题：
1.  **性能瓶颈**: 在 100x100 网格中，Python 原生的列表操作无法实现 30FPS 的目标。通过引入 `numpy` 和**差异渲染**，将矩阵操作向量化，并将 IO 操作限定在最小的变动集，达到了高性能指标。
2.  **异步竞态与环境适应性**:
    *   修复了 `stress_test_loader` 和 `_render_loop` 之间的启动顺序竞争，通过显式等待 `_running` 状态保证了测试的稳定性。
    *   通过 `shutil.get_terminal_size()` 实现了终端尺寸自适应，并修正了 `stop()` 流程中的缓冲区清理逻辑，消除了退出时的渲染伪影。

### 用户需求
实现一个高性能、低延迟、基于差异渲染的 CLI 可视化基座 (`ForestRenderer`)，作为“创世网格”的唯一调试和观测工具。

### 评论
`ForestRenderer` 的实现是基础设施层面的一次重大突破，它将我们的观测能力从脆弱的 `print` 日志提升到了**实时帧级调试**。通过将渲染逻辑与业务逻辑彻底分离，并以异步队列连接，我们为未来 10,000 个并发 Agent 的模拟铺平了道路，确保了逻辑线程和 IO 线程之间的隔离性。

### 目标
将所有新增和修改的文件提交到 Git 仓库，并结束 **Project Protoplasm - 第一章** 宏观任务。

### 基本原理
所有实现均遵循“验证基础设施极限”的预研目标。核心依赖于 `numpy` 进行数据密集型运算，符合在 Python 中实现高性能科学计算的最佳实践。

---

### Script

#### Acts 1: 添加所有新增和修改的渲染器文件到暂存区

~~~~~act
git_add
observatory/protoplasm/renderer/driver.py
observatory/protoplasm/renderer/matrix.py
observatory/protoplasm/renderer/buffer.py
observatory/protoplasm/renderer/visualizer_proto.py
observatory/protoplasm/renderer/__init__.py
~~~~~

#### Acts 2: 提交变更

~~~~~act
git_commit
~~~~~
~~~~~text
feat(observatory): Implement high-performance CLI ForestRenderer

Implements the core CLI rendering engine as the first deliverable of Project Protoplasm.

This renderer uses a decoupled architecture:
1.  **Numpy Matrix:** Stores and processes physical states (brightness/afterglow) with vectorized decay operations.
2.  **Double Buffering:** Compares the previous frame buffer against the current frame buffer (`RenderBuffer.compute_diff`) using Numpy masks.
3.  **ANSI Driver:** Generates minimal ANSI control sequences (`\033[R;CH`) to redraw only changed pixels, drastically reducing IO latency and achieving high FPS (>30 FPS target achieved).

Fixes:
-   **Stability:** Introduced dynamic terminal sizing via `shutil.get_terminal_size()` and an elegant shutdown sequence to prevent CLI artifacts on exit.
-   **Asynchronicity:** Fixed a race condition in the stress test loader by explicitly waiting for the render loop to start.
~~~~~

### 下一步建议

**下一阶段：第二章：神经直连**

既然观测基座已稳定，下一个风险点是高并发下的通信瓶颈。我们将开始实现 `DirectChannel` 原型，并将其与现有的 `LocalBusConnector` 进行吞吐量对比测试。

建议的任务是：

1.  创建 `observatory/protoplasm/networking` 目录。
2.  实现 `DirectChannel`，这是一个基于 `asyncio.Queue` 的零拷贝通信原语。
3.  设计一个测试，量化它与 `LocalBusConnector` 在 10,000 个并发 Agent 下的延迟差异。
