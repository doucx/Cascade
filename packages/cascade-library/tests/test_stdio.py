import pytest
import cascade as cs
import io
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver


@pytest.fixture
def engine():
    """Provides a default Cascade Engine for tests."""
    return cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus()
    )


@pytest.mark.asyncio
async def test_stdout_write(engine, capsys):
    """
    Tests that cs.io.stdout.write correctly prints to standard output.
    """
    workflow = cs.io.stdout.write("Hello, Interactive World!")

    await engine.run(workflow)

    captured = capsys.readouterr()
    assert captured.out == "Hello, Interactive World!\n"


@pytest.mark.asyncio
async def test_stdin_read_line(engine, monkeypatch):
    """
    Tests that cs.io.stdin.read_line correctly reads from standard input.
    """
    # Simulate user typing 'test input' and pressing Enter
    mock_stdin = io.StringIO("test input\n")
    monkeypatch.setattr("sys.stdin", mock_stdin)

    @cs.task
    def process_input(user_text: str):
        return f"Received: {user_text.upper()}"

    # Define the workflow
    user_line = cs.io.stdin.read_line()
    workflow = process_input(user_line)

    result = await engine.run(workflow)

    assert result == "Received: TEST INPUT"


@pytest.mark.asyncio
async def test_prompt_composition(engine, capsys, monkeypatch):
    """
    Tests the composition of write and read to simulate a user prompt.
    """
    mock_stdin = io.StringIO("Cascade User\n")
    monkeypatch.setattr("sys.stdin", mock_stdin)

    @cs.task
    def create_greeting(name: str):
        return f"Hello, {name}!"

    # The "prompt" pattern
    prompt_message = "Please enter your name: "
    write_prompt = cs.io.stdout.write(prompt_message)

    # Create a data dependency to ensure write_prompt runs before read_line.
    # The result of write_prompt (None) is passed to read_line,
    # which now accepts it as a positional argument.
    user_name = cs.io.stdin.read_line(write_prompt)
    workflow = create_greeting(user_name)

    result = await engine.run(workflow)

    # Verify the output and the final result
    captured = capsys.readouterr()
    assert captured.out == prompt_message + "\n"
    assert result == "Hello, Cascade User!"
