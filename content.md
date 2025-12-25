## [COMMIT] feat(spec): Implement Task Purity Model (CP-006)

### 用户需求
实现 CP-006 提案，将任务分为默认的“副作用任务 (Impure)”和显式的“纯函数任务 (Pure)”。Impure 任务应具有唯一的实例标识，而 Pure 任务应支持结构化去重。

### 评论
此变更解决了 Cascade 核心语义中的一个关键模糊点。通过将“副作用”作为默认行为，并要求用户显式声明 `pure=True`，我们使框架的行为更符合开发者的直觉，并防止了因意外去重而导致的难以追踪的 Bug。`HashingService` 现在通过为 Impure 任务注入实例 UUID 来保证其唯一性，同时保留了对 Pure 任务进行内容寻址优化的能力。

### 目标
1.  在 `Task` 定义和 `@task` 装饰器中引入 `pure` 参数。
2.  更新 `HashingService` 以根据 `pure` 属性调整哈希计算逻辑。
3.  确保所有相关测试通过，验证新模型的正确行为。
4.  提交所有相关更改作为一个逻辑上完整的单元。

### 基本原理
我们遵循了 TDD 流程。首先，扩展了 API 接口 (`Task` 类) 以支持 `pure` 属性。其次，创建了一个会失败的测试用例，暴露了现有哈希逻辑的缺陷 (RED)。然后，修改 `HashingService` 以在计算 Impure 任务的哈希时注入实例 `_uuid` 作为盐值 (Salt)，使测试通过 (GREEN)。最后，对测试文件进行了重构和清理。

### 标签
#intent/build #flow/ready #priority/high #comp/spec #comp/graph #concept/state #scope/core #ai/instruct #task/domain/core #task/object/task-purity #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交所有实现和测试文件

我们将把 `cascade-spec` 和 `cascade-graph` 中被修改的文件，以及新的测试文件，添加到 Git 暂存区，并创建一个内容详尽的提交。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/task.py
packages/cascade-graph/src/cascade/graph/hashing.py
tests/engine/graph/test_purity_model.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(spec): Implement Task Purity Model (CP-006)

Introduces a purity model to distinguish between side-effecting (impure) and deterministic (pure) tasks, resolving a core ambiguity in the graph-building process.

**Problem:**
Previously, all tasks were treated as pure and deduplicated based on their structural hash (function + arguments). This was counter-intuitive and dangerous for tasks with side-effects (e.g., random number generation, I/O), leading to incorrect graph consolidation.

**Solution:**
1.  **`@cs.task(pure: bool = False)`:** Tasks are now impure by default. Purity must be explicitly declared with `pure=True`.
2.  **`HashingService` Update:**
    -   For **impure** tasks (`pure=False`), the task instance's `_uuid` is now included as a "salt" in the structural hash calculation. This ensures every call to an impure task generates a unique node in the graph.
    -   For **pure** tasks (`pure=True`), the original content-addressable hashing logic is preserved, allowing for aggressive deduplication and caching.

This change aligns Cascade's behavior with developer expectations, enhances predictability, and prevents subtle bugs caused by incorrect task merging, while retaining powerful optimization capabilities for deterministic computations.
~~~~~

---


这是一个绝佳的问题，它正好触及了纯度模型的核心机制。

**简短的回答是：不，这两个 `f2` 调用不会产生同一个哈希，它们会是图中的两个独立节点。**

### 详细分析：不纯性会向上传播 (Impurity Propagates Upwards)

`HashingService` 的工作方式是**自底向上**的。一个父节点的哈希，取决于其所有子节点的哈希。让我们一步步拆解你的表达式：`n = f3(f2(f1(), f1()), f2(f1(), f1()))`

1.  **第一层：`f1()` (Impure)**
    *   由于 `f1` 是 Impure 的，每次调用 `f1()` 都会因为注入了唯一的 `Salt(uuid)` 而产生一个**全新的、独一无二的** `structural_id`。
    *   因此，在这个表达式中，我们实际上有**四个不同的 `f1` 节点**：
        *   `f1_A = f1()`
        *   `f1_B = f1()`
        *   `f1_C = f1()`
        *   `f1_D = f1()`
    *   它们的哈希 `hash(f1_A) != hash(f1_B) != hash(f1_C) != hash(f1_D)`。

2.  **第二层：`f2(...)` (Pure)**
    *   `f2` 本身是 Pure 的，这意味着它的哈希是**内容寻址 (Content-Addressable)** 的，其公式为：`hash(f2) = hash("f2_function" + inputs_hashes)`。
    *   我们来看两个 `f2` 调用的输入：
        *   第一个 `f2` 调用：`f2(f1_A, f1_B)`。它的哈希将是 `hash("f2_function" + hash(f1_A) + hash(f1_B))`。我们称之为 `f2_A`。
        *   第二个 `f2` 调用：`f2(f1_C, f1_D)`。它的哈希将是 `hash("f2_function" + hash(f1_C) + hash(f1_D))`。我们称之为 `f2_B`。
    *   因为 `hash(f1_A)` 与 `hash(f1_C)` 不同，`hash(f1_B)` 与 `hash(f1_D)` 也不同，所以两个 `f2` 调用的**输入哈希列表是不同的**。
    *   因此，`hash(f2_A) != hash(f2_B)`。系统会创建**两个不同的 `f2` 节点**。

3.  **第三层：`f3(...)` (Pure)**
    *   `f3` 接收 `f2_A` 和 `f2_B` 作为输入。由于 `hash(f2_A)` 和 `hash(f2_B)` 是不同的，`f3` 会根据这两个唯一的输入哈希，生成一个最终的、唯一的 `f3` 节点。

#### 图结构可视化

这个表达式构建的计算图如下所示：

```
   f1_A  f1_B   f1_C  f1_D  (Impure: 4 distinct nodes)
     \    /       \    /
      f2_A         f2_B    (Pure, but inputs differ -> 2 distinct nodes)
        \         /
           f3_A          (Pure: 1 final node)
```

#### 结论与缓存行为

*   **结论**：一个 Pure 函数如果依赖于 Impure 任务的结果，那么这个 Pure 函数的**具体节点实例**也会变得唯一。可以说，**不纯性会沿着依赖图向上传播**，污染所有依赖它的下游节点，使它们也变得唯一。
*   **缓存行为**：
    *   `f1_A`, `f1_B`, `f1_C`, `f1_D` 会各自执行，因为它们是不同的 Impure 节点。
    *   `f2_A` 和 `f2_B` 会各自执行，因为它们是不同的 Pure 节点（输入不同）。
    *   `f3_A` 会执行。
    *   **整个图都不会有任何缓存命中**，这完全符合预期，因为整个计算流的起点就是非确定性的。

您的分析非常深刻，这证明了我们刚刚实现的逻辑是正确且符合预期的。

现在，我们已经完成了所有的实现和验证，是时候将这个功能作为一个完整的单元提交了。我将为您生成最终的 `[COMMIT]` 计划。

