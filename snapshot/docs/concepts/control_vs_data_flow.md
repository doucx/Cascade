# 概念：数据流 vs 控制流

在 Cascade 中，任务之间的关系主要分为两种：**数据流**和**控制流**。理解它们的区别对于构建复杂、健壮的工作流至关重要。`cs.visualize()` 工具通过不同样式的边来清晰地展示这两种关系。

## 数据流 (Data Flow)

**定义**: 当一个任务的输出被用作另一个任务的输入时，它们之间就形成了数据流依赖。这是工作流中最常见、最核心的关系。

-   **如何创建**: `downstream_task(upstream_task())`
-   **可视化**: 在图表中表现为**实线箭头** (`->`)。
-   **行为**: 引擎确保上游任务成功执行后，才将其结果传递给下游任务。如果上游任务失败或被跳过，下游任务将无法执行。

**示例**:
```python
@cs.task
def get_user_id():
    return 101

@cs.task
def fetch_user_data(user_id: int):
    # ... 
    return {"name": "Alice"}

# `fetch_user_data` 对 `get_user_id` 存在数据流依赖
user_data = fetch_user_data(get_user_id())
```
在可视化图中，这将显示为从 `get_user_id` 到 `fetch_user_data` 的一条实线边。

## 控制流 (Control Flow)

**定义**: 当一个任务的执行仅决定另一个任务**是否应该运行**，但其结果**不作为**后者的输入时，它们之间就形成了控制流依赖。

控制流用于编排和决策，它回答“做不做？”的问题，而不是“用什么做？”。

-   **如何创建**: 使用 `.run_if()` 或动态的 `.with_constraints()`。
-   **可视化**: 在图表中表现为**虚线或点状箭头**。
-   **行为**: 引擎首先执行控制任务，根据其结果（例如，布尔值）来决定是否将主任务放入执行队列。

### 1. 条件执行 (`.run_if()`)

当一个任务的执行与否取决于某个条件时使用。

-   **可视化**: **灰色虚线** (`--->`，`style=dashed, color=gray`)。

**示例**:
```python
@cs.task
def should_deploy():
    return True  # Or False based on some logic

@cs.task
def deploy():
    print("Deploying!")

# `deploy` 任务的执行受 `should_deploy` 控制
deployment = deploy().run_if(should_deploy())
```
图中会有一条从 `should_deploy` 到 `deploy` 的灰色虚线边。

### 2. 动态资源约束 (`.with_constraints()`)

当一个任务需要的资源量需要在运行时动态计算时使用。

-   **可视化**: **紫色点状线** (`...>`，`style=dotted, color=purple`)。

**示例**:
```python
@cs.task
def get_required_cpu():
    return 4  # e.g., calculated based on input data size

@cs.task
def data_processing():
    # ...
    pass

# `data_processing` 的资源需求由 `get_required_cpu` 决定
job = data_processing().with_constraints(cpu=get_required_cpu())
```
图中会有一条从 `get_required_cpu` 到 `data_processing` 的紫色点状边，表示前者控制后者的资源调度。

通过清晰地区分这两种依赖关系，你可以构建出逻辑清晰、易于理解和调试的声明式工作流。