好的，所有测试均已通过，阶段二的核心功能（异步、重试、缓存）已全部实现并验证。现在是时候将这个重大的里程碑作为一个完整的逻辑单元提交了。

我将生成一个 `[COMMIT]` 计划。

## [COMMIT] feat(runtime): Implement async, retry, and caching support

### 用户需求
将 Cascade 阶段二实现的核心功能——异步支持、重试机制和缓存逻辑——作为一个原子提交，正式集成到代码库中。

### 评论
这是一个里程碑式的提交，标志着 Cascade 从一个“智能脚本执行器”演进为一个“可靠的自动化应用框架”。通过原生支持 `async/await`，我们解锁了处理 IO 密集型任务的高性能潜力。而声明式的重试与缓存机制，则直接解决了传统脚本最核心的脆弱性和低效性痛点。这些功能共同构成了 Cascade 在可靠性与性能方面的核心价值主张。

### 目标
1.  将所有与异步、重试、缓存相关的修改和新增文件添加到 Git 暂存区。
2.  创建一个内容详尽的 Git Commit，清晰地记录本次重大功能升级。

### 基本原理
我们将阶段二的所有相关功能捆绑在一次提交中，这反映了它们在架构设计上的内在联系（共同构成了框架的健壮性层）。这次提交后，Cascade 的核心功能集将达到一个稳定且强大的状态，为阶段三的生态与 DX 优化工作奠定坚实基础。

### 标签
#intent/build #flow/ready #priority/high
#comp/runtime #comp/spec #comp/graph #comp/adapters #comp/tests
#concept/async #concept/resilience #concept/caching #scope/core #scope/api
#task/domain/core #task/object/resilience-support #task/action/implementation
#task/state/end #task/status/completed

---

### Script

#### Acts 1: Stage all changes

将所有相关文件添加到 Git 暂存区。

~~~~~act
git_add
src/cascade/__init__.py
src/cascade/adapters/caching/__init__.py
src/cascade/adapters/caching/file_existence.py
src/cascade/adapters/executors/local.py
src/cascade/graph/build.py
src/cascade/graph/model.py
src/cascade/runtime/engine.py
src/cascade/runtime/protocols.py
src/cascade/spec/task.py
tests/test_adapters.py
tests/test_caching.py
tests/test_di_and_resources.py
tests/test_end_to_end.py
tests/test_retry.py
tests/test_spec_async.py
~~~~~

#### Acts 2: Commit changes

现在，我们创建一个内容详尽的提交。

~~~~~act
git_commit
~~~~~
~~~~~text
feat(runtime): Implement async, retry, and caching support

This commit introduces three major features that form the core of Cascade's robustness and performance capabilities, completing the goals of Phase Two.

1.  **First-Class Async Support**:
    - The entire execution chain, from `Executor` protocol to `Engine` and `LocalExecutor`, is now fully asynchronous (`async/await`).
    - The `@task` decorator transparently handles both `def` and `async def` functions, allowing seamless mixing of synchronous (CPU-bound) and asynchronous (IO-bound) tasks in the same workflow.
    - The top-level `cascade.run()` API maintains a simple synchronous interface for users by managing the `asyncio` event loop internally.

2.  **Declarative Retry Mechanism**:
    - A `.with_retry()` method has been added to `LazyResult`, allowing users to specify `max_attempts`, `delay`, and `backoff` declaratively.
    - The `Engine` now contains a built-in retry loop that honors these policies, automatically handling transient failures without requiring manual `try/except` blocks in user code.

3.  **Pluggable Caching System**:
    - A `.with_cache()` method and a `CachePolicy` protocol have been introduced.
    - The `Engine` now performs cache checks before task execution and saves results upon success, preventing redundant computations.
    - The first adapter, `FileExistenceCache`, is implemented, providing a common caching strategy for file-based workflows.

These features collectively elevate Cascade from a simple DAG runner to a production-ready framework for building reliable and efficient automation applications.
~~~~~

### 下一步建议
我们已经完成了 Cascade 阶段二。现在，我们将正式启动阶段三：**走向生态与可扩展性**。

阶段三的目标是进一步提升开发者体验 (DX) 和框架的易用性。根据计划，我建议我们从最能减少用户样板代码的功能开始：**实现 `Shell` 预置任务类型**。这将为执行外部命令提供一个健壮、优雅且经过良好测试的内置方法。如果你同意，我将开始制定实现 `Shell` 任务的计划。
