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
        path="packages/cascade-py/src/cascade/examples/patterns/llm_openai.py",
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
