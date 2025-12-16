好的，我们开始填充文档内容。遵从你的指示，我会将 `Cascade 使用手册 v2.0.md` 的内容拆分并填充到我们已经建立的 Diátaxis 结构中。

我将从最重要的部分开始：**教程 (Tutorial)**。这是新用户的第一个接触点，我们先将手册中的“快速上手”章节内容填充到对应的文件中。

## [WIP] docs: 填充“快速上手”教程

### 用户需求
将 `Cascade 使用手册 v2.0.md` 的内容拆分，并填充到新创建的文档结构中。

### 评论
这是一个非常有条理的开始。分阶段、分模块地填充文档内容，可以确保每个文档页面都聚焦于一个特定的主题，完全符合 Diátaxis 框架的最佳实践。首先完成“快速上手”教程，能最快地让文档网站对新用户产生价值。

### 目标
1.  从 `Cascade 使用手册 v2.0.md` 中提取“快速上手”章节的内容。
2.  将提取并适当调整格式后的内容写入 `docs/tutorial/getting-started.zh.md` 文件。

### 基本原理
教程的目的是手把手地引导用户完成一个完整的、虽小但有意义的任务。手册中的“快速上手：1分钟构建工作流”部分完美地契合了这一定义。我将提取该部分内容，并调整其 Markdown 标题层级，使其作为一篇独立的文档页面能够良好地展示。

### 标签
#intent/document #flow/ready #priority/high #comp/docs #scope/dx #ai/instruct #task/domain/docs #task/object/content-population #task/action/begin #task/state/continue

---

### Script

#### Acts 1: 填充“快速上手”教程内容

我们将手册第二节的内容提取出来，写入 `getting-started.zh.md` 文件。

~~~~~act
write_file
docs/tutorial/getting-started.zh.md
~~~~~
~~~~~markdown
# 快速上手

本教程将引导你完成第一个 `Cascade` 应用的创建，整个过程大约需要一分钟。

## 安装

`Cascade` 支持 Python 3.8+。通过 pip 安装：

```bash
pip install "cascade-py"
```

> 注意：根据你的 shell 配置，你可能需要使用 `pip3`。

## 您的第一个 Cascade 应用

让我们创建一个混合了配置和代码的脚本。这个脚本的目标是：读取一个配置文件中的版本号，并用它来构建一个 Docker 镜像标签。

首先，在你项目的根目录创建一个名为 `build.py` 的文件：

```python
# build.py
import cascade as cs

# 1. 使用 cs.config 声明一个对配置值的依赖
# 它会懒加载项目中的 YAML 文件来查找 'project.version'
# 注意: cs.config() 依赖 PyYAML, 请确保已安装 (`pip install PyYAML`)
project_version = cs.config("project.version")

# 2. 使用 @cs.task 定义一个 Python 任务
# 它依赖于从配置中获取的版本号
@cs.task
def generate_docker_tag(version: str, suffix: str) -> str:
    return f"my-app:{version}-{suffix}"

# 3. 连接声明式与命令式
# 注意：这里没有立即执行！
# project_version 是一个 LazyResult
image_tag = generate_docker_tag(version=project_version, suffix="latest")

# 4. 运行工作流，请求最终目标
if __name__ == "__main__":
    # 为了让这个例子能运行，我们需要一个配置文件。
    # cs.run() 会自动查找并加载名为 "cascade.yml" 或 "cascade.yaml" 的文件，
    # 并将其作为名为 "config_data" 的资源注入。
    # 
    # 你也可以手动指定配置字典，但使用资源是最佳实践。
    
    # 手动创建一个模拟的配置
    mock_config = {
        "project": {
            "version": "1.2.3"
        }
    }
    
    # 只有在调用 run() 时，所有依赖才会被解析和计算
    # 我们通过 `override_resource` 注入我们的 mock_config
    # 这样就不需要真的在项目里创建一个 cascade.yml 文件了
    
    from cascade.runtime.engine import Engine
    from cascade.testing import override_resource
    
    @cs.resource
    def config_data():
        yield mock_config

    engine = Engine()
    with override_resource(engine, "config_data", config_data):
        result = engine.run(image_tag)

    print(f"Docker 镜像标签: {result}")
```

现在，运行它：

```bash
$ python build.py
Docker 镜像标签: my-app:1.2.3-latest
```

恭喜！你刚刚构建并运行了你的第一个 `Cascade` 工作流。你已经体验到了其核心魅力：
- **声明式依赖**: 你声明了 `image_tag` 依赖于 `project_version`。
- **懒加载**: 直到调用 `run()` 之前，什么都没有发生。
- **无缝集成**: 来自配置的值 (`cs.config`) 和来自 Python 代码的值 (`@cs.task`) 被无缝地结合在了一起。

在接下来的指南中，我们将深入探索 `Cascade` 的更多强大功能。
~~~~~

### 下一步建议
我们已经成功填充了第一篇也是最重要的一篇文档。接下来，我建议我们继续这个过程，填充“操作指南”(How-to Guides) 和“核心概念”(Concepts) 部分。

例如，我们可以将手册的第 1 节“核心哲学”填充到 `docs/concepts/philosophy.zh.md` 中，将第 3 节“定义计算值”填充到 `docs/how-to-guides/defining-computations.zh.md` 中。

如果你同意，我将生成下一个填充计划，从“核心哲学”开始。
