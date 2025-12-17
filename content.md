你的分析完全正确，测试失败了。这是一个非常好的错误捕获，它暴露了我们 API 设计中的一个微妙问题。

## [WIP] fix: Refactor `cs.template` to support dynamic context dictionaries

### 错误分析
测试失败的根本原因是 `TypeError: <Task template> argument after ** must be a mapping, not LazyResult`。

这个错误发生在 `llm_openai.py` 的这一行：
`final_prompt = cs.template(prompt_template, **context)`

这里的 `context` 是 `cs.Param("context", ...)` 的返回值，它是一个 `LazyResult` 对象，而不是一个 Python 字典。Python 的 `**` 解包操作符是在**图构建时**（即调用 `cs.template(...)` 的那一刻）执行的，它要求操作数必须是一个实际的 `dict`。它无法解包一个代表未来值的 `LazyResult`。

我们不能动态地根据一个 `LazyResult` 的内容来决定一个函数调用有哪些关键字参数。

### 用户需求
修复 `cs.template` 的调用方式，使其能够接受一个 `LazyResult` 作为其渲染上下文的来源，从而修复 LLM 模式中的 `TypeError`。

### 评论
这个修复虽然小，但意义重大。它澄清了 `Cascade` 中静态图定义与动态值解析之间的界限。通过修改 `cs.template` 的接口，我们使其行为更加明确和健壮，能够更好地处理动态数据结构。

### 目标
1.  修改 `src/cascade/providers/template.py` 中 `render_template` 任务的签名，使其能显式接受一个 `context` 字典参数。
2.  修改 `src/cascade/examples/patterns/llm_openai.py` 中对 `cs.template` 的调用，以符合新的、更安全的 API。

### 基本原理
我们将把 `render_template` 任务的签名从 `(template_string, **kwargs)` 修改为 `(template_string, context=None, **kwargs)`。在任务内部，我们会将 `context` 字典（如果提供）和 `kwargs` 合并。这样，在调用端，我们就可以将代表上下文的 `LazyResult` 作为一个普通的关键字参数 `context` 传递进去，从而避免使用 `**` 操作符，解决了 `TypeError` 的问题。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #comp/providers #scope/api #task/domain/core #task/object/template-provider #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修改 `template` 提供者以接受显式上下文

我们将更新 `src/cascade/providers/template.py`，使其能够处理一个名为 `context` 的字典参数。

~~~~~act
patch_file
src/cascade/providers/template.py
~~~~~
~~~~~python
@task(name="template")
def render_template(template_string: str, **context) -> str:
    """
    Renders a Jinja2 template string with the provided context.

    Args:
        template_string: The Jinja2 template string.
        **context: Keyword arguments to be used as variables in the template.
                   These can be literals or LazyResults.

    Returns:
        The rendered string.
    """
    template = jinja2.Template(template_string)
    return template.render(**context)
~~~~~
~~~~~python
from typing import Dict, Any, Optional

@task(name="template")
def render_template(
    template_string: str, context: Optional[Dict[str, Any]] = None, **kwargs
) -> str:
    """
    Renders a Jinja2 template string with the provided context.

    Args:
        template_string: The Jinja2 template string.
        context: A dictionary of context variables.
        **kwargs: Additional context variables passed as keyword arguments.

    Returns:
        The rendered string.
    """
    template = jinja2.Template(template_string)
    final_context = {}
    if context:
        final_context.update(context)
    final_context.update(kwargs)
    return template.render(**final_context)
~~~~~

#### Acts 2: 修正 LLM 模式中的 `template` 调用

现在我们更新 `llm_openai.py`，使用新的 `context` 参数，而不是 `**` 解包。

~~~~~act
patch_file
src/cascade/examples/patterns/llm_openai.py
~~~~~
~~~~~python
# 步骤 A: 渲染 Prompt
final_prompt = cs.template(prompt_template, **context)
~~~~~
~~~~~python
# 步骤 A: 渲染 Prompt
final_prompt = cs.template(template_string=prompt_template, context=context)
~~~~~
