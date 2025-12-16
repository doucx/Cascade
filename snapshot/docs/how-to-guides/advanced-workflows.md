# 操作指南：构建复杂工作流

一旦你掌握了定义单个计算值的基础，就可以开始将它们组合起来，构建真正强大的、端到端的工作流。`Cascade` 的核心价值在于其无缝的可组合性。

## 无缝依赖混合

这是 `Cascade` `1+1 > 2` 的关键。因为所有东西都是 `LazyResult`，它们可以自由地相互依赖，无论其来源如何。

```python
import cascade as cs

# 场景：使用 Shell 命令的结果作为 Python 任务的输入
# 1. 从 Shell 获取当前的 git commit hash
commit_hash = cs.shell("git rev-parse --short HEAD")

# 2. 定义一个 Python 任务
@cs.task
def create_build_artifact(version: str) -> str:
    # 模拟创建构建产物
    artifact_name = f"artifact-{version}.zip"
    print(f"Creating {artifact_name}...")
    return artifact_name

# 3. 将 Shell 的 LazyResult 连接到 Python 任务
# 依赖关系被自动建立：create_build_artifact 依赖于 commit_hash
artifact = create_build_artifact(version=commit_hash)
```

## 参数化你的工作流 (`cs.param`)

使用 `cs.Param` 来定义在运行时（通过 `cs.run` 的 `params` 参数或 `cs.cli` 的命令行参数）注入的值。这使得你的工作流可以复用和配置。

```python
import cascade as cs

# 定义一个名为 'env' 的参数，默认值为 'staging'
env = cs.Param("env", default="staging", description="目标环境 (staging/production)")

@cs.task
def get_db_url(environment: str) -> str:
    if environment == "production":
        return "prod_db_url"
    return "stage_db_url"

db_url = get_db_url(environment=env)

# 运行时可以覆盖默认值
# from cascade.runtime.engine import Engine
# engine = Engine()
# prod_url = engine.run(db_url, params={"env": "production"}) 
# assert prod_url == "prod_db_url"
```

## 条件执行 (`.run_if()`)

使用 `.run_if()` 方法，可以让一个任务只在某个条件（一个返回布尔值的 `LazyResult`）为 `True` 时执行。

```python
import cascade as cs

# 定义一个布尔类型的参数来控制是否部署
should_deploy = cs.Param("deploy", default=False, type=bool)

# .run_if() 会将 should_deploy 作为其条件依赖
deployment_status = cs.shell(
    "kubectl apply -f deployment.yaml", 
    check=True
).run_if(should_deploy)
```
当以 `params={"deploy": False}` 运行时，`shell` 命令将永远不会被执行。

## 处理集合：映射 (`.map()`)

使用 `.map()`，您可以将一个任务工厂（如 `@task` 函数或 `cs.shell`）应用到一个集合的每个元素上，这会自动创建一组并行执行的任务。

```python
import cascade as cs

# files_to_process 可以是一个列表，也可以是上游任务的 LazyResult
files_to_process = ["data1.csv", "data2.csv", "data3.csv"]

@cs.task
def process_file(filepath: str) -> str:
    # ... 复杂的处理逻辑 ...
    return f"processed_{filepath}"

# 将 process_file 任务映射到文件列表上
# .map() 返回一个 MappedLazyResult，它在运行时会解析为一个结果列表
processed_files = process_file.map(filepath=files_to_process)

@cs.task
def summarize(processed: list[str]):
    print(f"完成了 {len(processed)} 个文件的处理。")
    return f"Processed {len(processed)} files."

# `summarize` 任务会等待所有 `process_file` 子任务完成后再执行
final_summary = summarize(processed=processed_files)
```

## 动态路由 (`cs.router`)

`cs.Router` 可以根据一个 `selector` 的值，动态地从多个上游 `LazyResult` 中选择一个作为下游任务的输入。

```python
import cascade as cs

# selector 可以是 Param，也可以是其他任务的结果
data_source_type = cs.Param("data_source", default="db")

@cs.task
def from_db(): return "Data from DB"

@cs.task
def from_api(): return "Data from API"

# Router 会根据 data_source_type 的值，选择一个上游
data_input = cs.Router(
    selector=data_source_type,
    routes={
        "db": from_db(),
        "api": from_api()
    }
)

@cs.task
def process_data(data: str):
    return f"Final data: {data}"

result = process_data(data=data_input)

#
# from cascade.runtime.engine import Engine
# engine = Engine()
# res_api = engine.run(result, params={"data_source": "api"}) 
# assert "API" in res_api
```