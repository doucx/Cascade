简要回答
好的，我们继续。

在深入研究代码以移除“调用时注入”模式 (`task(conn=cs.inject("db"))`) 后，我发现了一个关键问题：**此模式对于像 `cs.sql` 这样的动态 Provider 是必不可少的**。

`cs.sql("SELECT ...", db="my_db")` 这个工厂函数需要一种方法，来动态地告诉其内部任务 (`_sql_task`) 要注入名为 `"my_db"` 的资源。唯一能实现这一点的就是“调用时注入”模式。将其移除会破坏 `cs.sql` 以及未来任何需要动态指定资源名称的 Provider。

因此，我认为路线图中“废弃旧模式”的目标是基于一个不完全的假设。这两种注入模式并非“新”与“旧”的关系，而是“**静态用户模式**”与“**动态提供者模式**”的关系。

为了实现路线图“消除 API 歧义”的真正目标，最好的方法不是移除功能，而是通过**清晰的文档**来阐明这两种模式的用途。我将执行一个计划，创建路线图第四部分第三步所要求的文档，并在其中明确这一区别。

## [WIP] docs(concepts): 阐明资源注入模式与控制流

### 用户需求
根据路线图，需要消除 Cascade API 中的歧义，特别是围绕两种资源注入模式，以及数据依赖和控制依赖之间的区别。

### 评论
通过创建专门的文档，我们可以将 `cs.inject()` 的两种用法从潜在的“混淆点”转变为 Cascade 设计灵活性的一个清晰示例。我们将明确指导用户在日常工作中应始终使用函数签名注入，同时解释为什么 Provider 作者需要调用时注入这一更强大的工具。

### 目标
1.  创建新的文档页面 `docs/concepts/control_vs_data_flow.md`，解释数据流与控制流（`run_if`、动态约束）的区别。
2.  创建新的文档页面 `docs/how-to-guides/dependency-injection.md`，明确定义两种资源注入模式的用例，并将“函数签名注入”确立为用户的标准实践。

### 基本原理
文档是 API 的一部分。与其为了一个被误判为“过时”的模式而移除关键功能，不如通过完善文档来引导用户，这更能提升开发者体验。此计划将同时完成路线图第四部分的第二步和第三步。

### 标签
#intent/document #flow/ready #priority/high #comp/docs #concept/dependency-injection #concept/control-flow #scope/dx #ai/brainstorm #task/domain/documentation #task/object/api-clarification #task/action/writing #task/state/continue

---

### Script

#### Acts 1: 创建控制流与数据流说明文档
创建 `control_vs_data_flow.md` 文件。

~~~~~act
write_file
docs/concepts/control_vs_data_flow.md
~~~~~
~~~~~markdown
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
~~~~~

#### Acts 2: 创建依赖注入指南
创建 `dependency-injection.md` 文件，并明确两种模式的用法。

~~~~~act
write_file
docs/how-to-guides/dependency-injection.md
~~~~~
~~~~~markdown
# 操作指南：依赖注入

Cascade 的依赖注入 (DI) 系统允许你的任务在运行时自动获取共享资源，如数据库连接、API 客户端或配置文件。这使得任务本身保持纯粹的业务逻辑，而将资源管理的复杂性解耦出去。

## 核心概念

-   **资源 (`@cs.resource`)**: 一个使用 `yield` 的生成器函数，负责资源的创建（`yield` 之前）和清理（`yield` 之后）。
-   **注入 (`cs.inject`)**: 一个标记，用于在任务中声明对某个资源的依赖。

## 标准模式：在函数签名中注入 (推荐)

这是为工作流开发者设计的标准、最常用的模式。它通过在任务函数的参数中使用默认值来声明依赖。

**优点**:
-   **声明式**: 任务的依赖关系在其签名中一目了然。
-   **清晰**: 代码可读性强，易于理解和维护。

### ✅ 推荐做法 (Do This)

```python
import cascade as cs

# 1. 定义资源
@cs.resource
def database_connection():
    conn = connect_to_db()
    yield conn
    conn.close()

# 2. 在任务签名中声明依赖
@cs.task
def get_user(user_id: int, db=cs.inject("database_connection")):
    return db.query(f"SELECT * FROM users WHERE id={user_id}")

# 3. 正常调用任务
user_data = get_user(123)

# 4. 在运行引擎中注册资源
engine = cs.Engine(...)
engine.register(database_connection)
engine.run(user_data)
```

## 高级模式：在调用时注入

此模式主要为**库和 Provider 的作者**设计，用于构建需要动态指定资源名称的更高级抽象。

**优点**:
-   **动态性**: 允许将要注入的资源名称作为参数传递，实现更高的灵活性。

### ❌ 不推荐的日常用法 (Don't Do This for Regular Tasks)

```python
# 反模式：对于普通任务，这会使依赖关系变得不明确
@cs.task
def get_user(user_id: int, db): # 签名中看不出依赖
    ...

# 在调用时传入 inject，这很隐晦
user_data = get_user(123, db=cs.inject("database_connection"))
```

### ✅ 合理用例 (Provider 实现)

`cs.sql` Provider 是此模式的最佳示例。用户希望这样调用它：

`users = cs.sql("SELECT ...", db="analytics_db")`

为了实现这一点，`cs.sql` 内部的实现就需要使用“调用时注入”：

```python
# cascade/providers/sql.py (简化版)

def _sql_factory(query: str, db: str):
    """这是用户调用的 cs.sql()"""
    # 这里，'db' 的值 (如 "analytics_db") 是动态的。
    # 我们必须在调用时创建一个 Inject 对象。
    return _sql_task(query=query, conn=cs.inject(db))

@cs.task
def _sql_task(query: str, conn: Any):
    """这是实际执行的内部任务"""
    return conn.execute(query)
```

### 总结

-   **作为工作流开发者**，请**始终**使用**函数签名注入**模式。
-   **作为 Provider 或库开发者**，当你需要构建一个能处理动态资源目标的抽象时，**调用时注入**是一个强大而必要的工具。
~~~~~

### 下一步建议
我们已经完成了路线图的所有步骤。我建议我们现在创建一个最终的 `[COMMIT]` 计划，将所有这些改进作为一个逻辑单元进行提交。
