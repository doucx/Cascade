好的，我们现在进入路线图的最后阶段。

这个阶段的核心是**验证**，而不是开发。我们将通过组合前两个阶段构建的原子化“积木”（`cs.http`, `cs.subflow` 等）来创建一个真实、有用的高级功能模式，以此证明“组合优于封装”的架构原则是成功且强大的。

## [WIP] docs(patterns): Create LLM orchestration pattern using composition

### 用户需求
根据路线图第三阶段的要求，创建一个官方的 LLM 调用参考模式。此模式必须仅使用现有的原子化提供者（`cs.http`, `cs.template`, `cs.Env`, `cs.Param`）进行组合，并通过 `cs.subflow` 进行封装和调用，以验证并展示新架构的组合能力。

### 评论
这是整个第二层核心能力重构的“毕业典礼”。通过成功实现这个复杂的、真实世界的用例，而无需向 `Cascade` 核心添加任何新的、特定于领域的 Provider，我们证明了该架构的灵活性和表达能力。这个模式将成为未来所有复杂功能组合的最佳实践范例。

### 目标
1.  创建示例模式的存放目录 `src/cascade/examples/patterns/`。
2.  在该目录中创建 `llm_openai.py` 文件，该文件将包含一个完整的、可复用的 OpenAI 调用工作流。
3.  创建对应的集成测试文件 `tests/examples/test_llm_pattern.py`。
4.  测试将使用 `cs.subflow` 调用 `llm_openai.py`，并通过 `monkeypatch` 模拟 `cs.http.post` 的行为，以验证整个流程的正确性，而无需真实的网络调用。

### 基本原理
我们将严格遵循路线图中的设计。`llm_openai.py` 文件本身就是一个完整的 `Cascade` 脚本。它使用 `cs.Env` 获取 API 密钥，使用 `cs.Param` 接收模型、提示模板和上下文等配置。然后，它使用 `cs.template` 组合这些信息来渲染最终的 prompt，接着调用 `cs.http.post` 将其发送到 OpenAI API。最后，一个简单的纯函数 `@cs.task` 负责解析返回的 `HttpResponse` 对象。整个组合好的 `LazyResult` 被赋给一个名为 `result` 的变量，作为 `subflow` 的 `target`。

### 标签
#intent/document #flow/ready #priority/high #comp/docs #comp/tests #scope/dx #ai/instruct #task/domain/docs #task/object/llm-pattern #task/action/creation #task/state/continue

---

### Script

#### Acts 1: 创建目录结构

首先，我们为新的示例模式和其测试创建必要的目录。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p src/cascade/examples/patterns tests/examples
~~~~~

#### Acts 2: 实现 LLM 调用模式文件

现在，我们创建 `llm_openai.py` 文件。这不属于 `cascade` 库的核心代码，而是一个展示如何使用库的“菜谱”或模式。

~~~~~act
write_file
src/cascade/examples/patterns/llm_openai.py
~~~~~
~~~~~python
import cascade as cs
from cascade.providers.http import HttpResponse

# 1. 定义子流程的输入参数
api_key = cs.Env("OPENAI_API_KEY", description="OpenAI API Key")
model = cs.Param("model", default="gpt-4-turbo")
prompt_template = cs.Param("prompt_template")
# context 将是一个字典，其值可以是 LazyResult 或字面量
context = cs.Param("context", default={})

# 2. 组合原子任务 (这就是模式的核心)
# 步骤 A: 渲染 Prompt
final_prompt = cs.template(prompt_template, **context)

# 步骤 B: 调用 HTTP API (使用第一阶段构建的积木)
api_response = cs.http.post(
    url="https://api.openai.com/v1/chat/completions",
    headers={
        "Content-Type": "application/json",
        # 使用 cs.template 动态构建认证头
        "Authorization": cs.template("Bearer {{ key }}", key=api_key)
    },
    json={
        "model": model,
        "messages": [{"role": "user", "content": final_prompt}]
    }
).with_retry(max_attempts=3, delay=5) # 精确地对网络调用进行重试

# 步骤 C: 解析响应 (一个简单的纯函数任务)
@cs.task
def parse_response(response: "HttpResponse"):
    if response.status >= 400:
        raise RuntimeError(f"API Error: {response.status} - {response.text()}")
    return response.json()["choices"][0]["message"]["content"]

parsed_text = parse_response(api_response)

# 3. 暴露最终结果作为子流程的 'target'
result = parsed_text
~~~~~

#### Acts 3: 实现集成测试

最后，我们创建一个测试来验证这个模式。测试将使用 `cs.subflow` 来调用它，并模拟网络请求。

~~~~~act
write_file
tests/examples/test_llm_pattern.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from unittest.mock import MagicMock
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver
from cascade.providers.http import HttpResponse

# 模拟一个成功的 OpenAI API 响应
mock_openai_response = {
    "choices": [{"message": {"content": "This is a mock summary."}}]
}

@pytest.fixture
def mock_http_post(monkeypatch):
    """Mocks cs.http.post to avoid real network calls."""
    mock_post_task = MagicMock()
    
    # The mock needs to return a coroutine that resolves to an HttpResponse
    async def fake_post(*args, **kwargs):
        return HttpResponse(
            status=200,
            headers={"Content-Type": "application/json"},
            body=str.encode(str(mock_openai_response).replace("'", '"')) # Basic JSON dump
        )
    
    # We need to mock the underlying task function that the provider returns
    monkeypatch.setattr("cascade.providers.http._http_post_task.func", fake_post)
    
    # We can also check calls on the task wrapper if needed, but mocking the func is direct
    return fake_post

@pytest.mark.asyncio
async def test_llm_pattern_via_subflow(mock_http_post, monkeypatch):
    """
    Tests the full LLM pattern by calling it as a subflow.
    """
    # Mock the environment variable
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")

    # Define the parent workflow
    article_text = "This is a long article about software architecture..."
    
    summary = cs.subflow(
        path="src/cascade/examples/patterns/llm_openai.py",
        target="result", # 'result' is the final LazyResult in the subflow file
        params={
            "model": "gpt-3.5-turbo",
            "prompt_template": "Please summarize: {{ article }}",
            "context": {"article": article_text}
        }
    )

    # Run the workflow
    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(summary)

    # Assert the final result
    assert result == "This is a mock summary."

    # Assert that the mocked HTTP function was called correctly
    # Note: Since we replaced the function, we can't use MagicMock's assert_called_...
    # To check calls, we'd need a more elaborate mock setup.
    # For this test, verifying the end-to-end data flow is sufficient.
    # A more advanced test could inject a spy to capture call arguments.
~~~~~

### 下一步建议
我们已经成功地使用组合模式实现了 `LLM` 调用的参考实现，并为其编写了测试，从而完成了路线图的所有三个阶段。

现在，这个逻辑上完整的工作单元已经准备好被提交了。我建议生成一个 `[COMMIT]` 计划来将这些新的示例和测试文件提交到版本控制中。
