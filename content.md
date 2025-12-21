简要回答
这是一个关乎 Cascade 架构能否支撑高性能 Agent 的关键转折点。根据你提供的《通过优雅的声明式语法，实现命令式循环的性能.md》，我们将正式启动 **TCO 零开销优化 (TCO Zero-Overhead Optimization)** 的第一阶段：**结构哈希与缓存蓝图**。

目前的 `uuid4` 标识符机制导致每次递归都重建图，这是性能瓶颈的根源。本计划将首先分析核心数据结构，为实现“稳定结构哈希 (Structural Hashing)”做准备。

## [WIP] feat: 启动 TCO 零开销优化第一阶段 - 结构哈希设计

### 用户需求
为了让 Cascade 的递归 Agent 达到与命令式 `while True` 循环相当的性能，必须消除每次递归调用时重建计算图（Graph Building）的 CPU 开销。

### 评论
当前的 TCO 实现虽然防止了堆栈溢出，但在图构建上极其“浪费”。Agent 的递归通常是**拓扑结构不变，仅输入数据变化**。如果 Engine 能识别出“这是同一个图结构”，它就可以跳过构建阶段，直接复用已编译的执行计划。

### 目标
1.  分析 `LazyResult`、`Task` 和 `GraphBuilder` 的现有代码。
2.  确定如何基于 `task.func` (代码引用) 和 `args/kwargs` (参数结构) 生成一个**确定性的、稳定的结构哈希**，替代随机的 UUID。
3.  设计在 `GraphBuilder` 中引入缓存层的切入点。

### 基本原理
我们将遵循“读取-分析-设计”的路径。在修改代码之前，我们需要精确了解 `LazyResult` 在内存中的布局，以及如何处理嵌套的依赖（例如，作为参数的另一个 `LazyResult`），以确保哈希算法既能捕捉结构变化，又能忽略无关的运行时噪音（如内存地址）。

### 标签
#intent/architect #intent/perf #flow/draft #priority/critical
#comp/runtime #comp/engine #concept/caching #concept/state
#task/domain/core #task/object/tco-optimization #task/action/structural-hashing #task/state/begin

---

### Script

#### Acts 1: 读取核心图构建与类型定义文件
我们需要深入检查 `LazyResult` 的定义以及 `GraphBuilder` 的遍历逻辑，以确定在哪里注入哈希计算和缓存查找逻辑。

~~~~~act
read_file
packages/cascade-interfaces/src/cascade/spec/lazy_types.py
~~~~~

~~~~~act
read_file
packages/cascade-interfaces/src/cascade/spec/task.py
~~~~~

~~~~~act
read_file
packages/cascade-runtime/src/cascade/graph/build.py
~~~~~

### 下一步建议
在分析完这些文件后，我将提出一个具体的“结构哈希算法”设计文档（RFC），定义如何递归地计算一个 `LazyResult` 的哈希值，并演示它如何区分拓扑改变与单纯的数据改变。
