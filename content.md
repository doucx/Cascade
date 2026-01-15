我们将通过“切断旧链条”来完成这次迁移的硬性物理分离。我们将删除 `cascade-runtime` 和 `cascade-common` 中用于兼容的薄封装文件，并确保所有相关包的 `pyproject.toml` 正确声明了对 `cascade-bus` 的依赖。

## [WIP] 删除 `cascade-runtime` 和 `cascade-common` 中用于兼容的薄封装文件

## 标签
#intent/refine #flow/ready #priority/high
#comp/runtime #comp/common #comp/bus #comp/build
#ai/instruct
#task/domain/infrastructure #task/object/cascade-bus #task/action/cleanup-wrappers #task/state/continue

---

### Script

#### Acts 1: 删除旧的薄封装文件

我们将物理移除位于 `runtime` 和 `common` 包中的旧总线逻辑文件（包括我们上一步创建的薄封装）。

~~~~~act
run_command
~~~~~
~~~~~
# 删除 runtime 中的观测性总线相关文件
rm packages/cascade-runtime/src/cascade/runtime/services/observability/bus.py
rm packages/cascade-runtime/src/cascade/runtime/services/observability/events.py

# 删除 common 中的消息总线相关文件
rm -rf packages/cascade-common/src/cascade/common/messaging
~~~~~

### 下一步建议

旧的逻辑入口已经全部拆除。虽然现在代码无法直接运行（因为 import 尚未更新），但架构上的物理隔离已经彻底完成。

由于你计划使用脚本统一清理 import，你可以开始执行该脚本了。脚本的目标应该是：
1. 将 `from cascade.runtime.services.observability.bus import ...` 替换为 `from cascade.bus.core import ...`。
2. 将 `from cascade.runtime.services.observability.events import ...` 替换为 `from cascade.bus.events import ...`。
3. 将 `from cascade.common.messaging.bus import ...` 替换为 `from cascade.bus.feedback import ...`。

在 import 清理完成后，系统将恢复可运行状态，且所有的 Bus 调用都将汇聚到 `cascade-bus`。之后我们可以继续对 `stitcher` 或 `quipu` 执行相同的流程。
