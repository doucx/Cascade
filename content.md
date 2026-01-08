我已经识别出由于 `wiring` 包移动到 `backend` 目录下而导致的 `ModuleNotFoundError` 问题。这主要是因为 `builder.py` 和 `context.py` 等核心组件仍在使用旧的导入路径 `cascade.compiler.wiring`。我将通过 `sed` 命令进行全局替换来修复这些导入错误，并验证测试套件的收集情况。

## [WIP] refactor: 修正因将 wiring 包移入 backend 导致的导入路径错误

### 用户需求
修复因 `cascade.compiler.wiring` 包移动到 `backend` 目录下后，代码中残留的旧导入路径导致的 `ModuleNotFoundError`。

### 评论
这是一项必要的架构维护工作。将 `wiring` 归入 `backend` 是为了符合编译器分层设计的逻辑（即物理布线属于后端的职责），但必须确保所有引用都已正确重定向，以维持系统的可测试性。目前 Collection 阶段的报错证明了导入链条已断裂。

### 目标
1. 在全代码库（包括源码和测试）中将 `cascade.compiler.wiring` 替换为 `cascade.compiler.backend.wiring`。
2. 验证 `Builder` 和 `WiringContext` 等核心组件的导入是否恢复正常。
3. 通过 `pytest --collect-only` 确保测试套件能够被成功收集。

### 基本原理
由于 Python 的导入机制强依赖于包的层级结构，包位置的物理变动必须伴随着导入声明的全局更新。通过 `find` 和 `sed` 进行批量文本替换是处理此类重构问题的标准工程手段，能确保覆盖到隐藏在测试用例或辅助脚本中的所有引用。

### 标签
#intent/refine #flow/ready #priority/high 
#comp/engine #concept/executor #scope/core 
#ai/instruct 
#task/domain/compiler #task/object/wiring-package #task/action/move
#task/state/begin

---

### Script

#### Acts 1: 全局修复导入路径

我们将执行全局替换，并检查 `harness.py` 的物理位置以确保重构的完整性。

~~~~~act
run_command
~~~~~
~~~~~
# 1. 在 packages 目录下进行全局搜索并替换旧的包路径
find packages/ -type f -name "*.py" -exec sed -i 's/cascade\.compiler\.wiring/cascade.compiler.backend.wiring/g' {} +

# 2. 确认物理文件位置，验证 harness.py 是否已正确跟随包移动
find packages/cascade-compiler/src/cascade/compiler/ -name "harness.py"
~~~~~

### 下一步建议
- **执行冒烟测试**: 收集成功后，建议优先运行 `packages/cascade-compiler/tests/unit/backend/test_builder.py`，因为它是受影响最直接的单元测试。
- **清理旧路径**: 检查 `packages/cascade-compiler/src/cascade/compiler/` 下是否还残留空的 `wiring` 目录，如果有，应予以删除以保持代码树整洁。
- **同步文档**: 检查 `*.stitcher.yaml` 文件中的说明，确保其关于组件位置的描述与新的物理结构保持一致。
