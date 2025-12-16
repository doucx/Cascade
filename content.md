这是本次重构后的第一个文档任务，旨在偿还高优先级文档技术债务。我将更新 `docs/how-to-guides/improving-robustness.md` 文件，增加关于资源安全和并发控制的章节。

## [WIP] docs: Add documentation for resource constraints and scheduling

### 用户需求
在 `improving-robustness.md` 中增加关于 `.with_constraints()` 和 `cs.run` 的 `system_resources` 参数的文档，确保用户了解如何使用新的资源调度功能。

### 评论
资源约束是 `Cascade` 健壮性的关键组成部分，它防止了资源超额使用导致的工作流崩溃。本次文档更新是高优先级的，它使得功能对用户可用且可见。

### 目标
在 `docs/how-to-guides/improving-robustness.md` 中，在 `.with_retry()` 之后添加 `资源安全与并发控制` 章节。

### 基本原理
按照项目规划，文档债必须在开始下一个核心功能之前偿还。我们将使用 `patch_file` 精确定位和插入新内容。

### 标签
#intent/document #flow/ready #priority/high #comp/docs #concept/constraint #scope/ux #ai/instruct #task/domain/documentation #task/object/improving-robustness-doc #task/action/update #task/state/begin

---

### Script

#### Acts 1: 更新 `improving-robustness.md` 文件

在 `improving-robustness.md` 中，在 `.with_retry()` 章节和末尾总结之间插入新的 `资源安全与并发控制` 章节。

~~~~~act
patch_file
docs/how-to-guides/improving-robustness.md
~~~~~
~~~~~markdown
# - 如果第三次仍然失败, 最终的异常才会被抛出, 导致工作流失败。
```

通过组合使用 `.with_cache()` 和 `.with_retry()`，你可以用声明式的方式，极大地提升工作流的稳定性和效率，而无需用 `try/except` 和 `if os.path.exists()` 把你的业务逻辑弄得一团糟。
~~~~~
~~~~~markdown
# - 如果第三次仍然失败, 最终的异常才会被抛出, 导致工作流失败。
```

## 资源安全与并发控制 (`.with_constraints()`)

当工作流包含资源密集型任务（例如，需要 GPU 或大量内存）时，你需要确保任务不会超额使用系统资源，导致整个进程崩溃或调度混乱。

### 1. 定义系统容量

首先，在运行工作流时，通过 `cs.run` 的 `system_resources` 参数定义系统的总资源容量。

```python
# 定义系统容量：只有 1 个 GPU 和 32GB 内存
system_config = {
    "gpu_slots": 1,
    "memory_gb": 32,
}

# 引擎将使用此配置来仲裁任务的执行顺序
# cs.run(target_task, system_resources=system_config)
```

### 2. 声明任务需求

使用 `.with_constraints()` 方法，声明一个任务需要多少资源才能运行。

```python
import cascade as cs

@cs.task
def train_model():
    print("Running memory-heavy task...")
    # ... task logic ...
    return "Model Trained"

# 声明此任务需要 1 个 gpu_slot 和 16GB 内存
constrained_task = train_model().with_constraints(
    gpu_slots=1, 
    memory_gb=16
)

# 调度器保证：
# 1. 如果系统总容量不够 (例如系统只有 8GB 内存)，任务将立即失败 (快速失败)。
# 2. 如果多个任务需要 gpu_slots=1，它们将被强制串行执行。
```

### 3. 动态约束

资源约束的值也可以是上游任务的 `LazyResult`。

```python
@cs.task
def calculate_required_cpu() -> int:
    # 假设根据数据大小动态计算出需要 4 个 CPU 核心
    return 4

# CPU 需求是动态计算出来的
required_cpu = calculate_required_cpu()

# 任务的约束是动态值
job = train_model().with_constraints(cpu_cores=required_cpu) 
```

通过组合使用 `.with_cache()`、`.with_retry()` 和 `.with_constraints()`，你可以用声明式的方式，极大地提升工作流的稳定性和效率，而无需用 `try/except` 和 `if os.path.exists()` 把你的业务逻辑弄得一团糟。
~~~~~

### 下一步建议
文档更新已完成。根据开发路线图和技术债务分析，下一个任务应是继续 **`cs.config` Provider** 的实现，以提供更强大的动态配置能力。
