我们将创建一个 `[COMMIT]` 计划，提交 `cs.cli` 对 `--log-level` 选项的支持。

## [COMMIT] feat(cli): Add --log-level option to generated CLI

### 用户需求
使 `cs.cli` 生成的命令行工具自动支持 `--log-level` 选项，以控制运行时日志输出，保持与 `cs.run` API 的一致性。

### 评论
该功能极大地增强了 `Cascade` 作为独立 CLI 工具的可控性。通过将 `log_level` 硬编码为 Typer 选项，我们确保所有生成的应用都能即时利用日志过滤功能，提升了开发者体验 (DX)。

### 目标
创建一个 Git 提交，包含 `src/cascade/tools/cli.py` 中对 `log_level` 参数的动态注入和处理逻辑，以及对相关测试的更新。

### 基本原理
通过元编程向 `cs.cli` 内部的 `main` 函数签名中注入 `log_level` 参数，并在实际调用 `cascade.run` 时通过 `kwargs` 提取并传递该参数。这是一种非侵入式地扩展生成的 CLI 接口的有效方法。

### 标签
#intent/build #flow/ready #priority/high
#comp/cli #comp/tests #concept/ui #scope/dx
#ai/instruct
#task/domain/cli #task/object/cli-options #task/action/implementation
#task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交 CLI 增强功能及其测试

将所有修改文件添加到 Git 暂存区，并执行提交。

~~~~~act
git_add
src/cascade/tools/cli.py
tests/tools/test_cli.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(cli): Add --log-level option to generated CLI

Enhances `cascade.cli` to automatically include a `--log-level` option (defaults to INFO) in the generated Typer application signature.

The core implementation in `cli.py` now explicitly injects the `log_level` parameter into the dynamic signature and extracts it from `kwargs` before passing it down to `cascade.run()`.

This ensures that users can control the verbosity of the runtime logs when executing workflows via the generated command-line interface.
~~~~~

### 下一步建议
至此，我们已经完成了用户提出的日志流向和日志等级的实现，并在主要的入口 (`cs.run` 和 `cs.cli`) 中暴露了控制参数。

根据 `规范/潜在改进点与未来工作.md`，我们已经完成了大部分**阶段四：生态系统与核心工具**的工作。唯一尚未实现的重大改进是**高级求解器**。

我建议下一步着手实现 **高级求解器 (`CSPSolver`)** 的架构和基础实现，以解决我们在 `开发/债务分析251216.md` 中识别出的**架构债**（贪婪/非优化调度）。

**具体建议：**
1.  分析并规划 `CSPSolver` 适配器的架构。
2.  在 `pyproject.toml` 中添加 `python-constraint` 可选依赖。
3.  实现 `CSPSolver` 的核心 `resolve` 逻辑。
