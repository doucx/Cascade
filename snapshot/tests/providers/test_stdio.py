import pytest
import cascade as cs
import io

@pytest.mark.asyncio
async def test_stdout_write(capsys):
    """
    Tests that cs.io.stdout.write correctly prints to standard output.
    """
    workflow = cs.io.stdout.write("Hello, Interactive World!")
    
    cs.run(workflow)
    
    captured = capsys.readouterr()
    assert captured.out == "Hello, Interactive World!\n"

@pytest.mark.asyncio
async def test_stdin_read_line(monkeypatch):
    """
    Tests that cs.io.stdin.read_line correctly reads from standard input.
    """
    # Simulate user typing 'test input' and pressing Enter
    mock_stdin = io.StringIO("test input\n")
    monkeypatch.setattr('sys.stdin', mock_stdin)
    
    @cs.task
    def process_input(user_text: str):
        return f"Received: {user_text.upper()}"

    # Define the workflow
    user_line = cs.io.stdin.read_line()
    workflow = process_input(user_line)
    
    result = cs.run(workflow)
    
    assert result == "Received: TEST INPUT"

@pytest.mark.asyncio
async def test_prompt_composition(capsys, monkeypatch):
    """
    Tests the composition of write and read to simulate a user prompt.
    """
    mock_stdin = io.StringIO("Cascade User\n")
    monkeypatch.setattr('sys.stdin', mock_stdin)
    
    @cs.task
    def create_greeting(name: str):
        return f"Hello, {name}!"

    # The "prompt" pattern
    prompt_message = "Please enter your name: "
    write_prompt = cs.io.stdout.write(prompt_message)
    
    # Reading depends implicitly on the prompt being written first
    # We can model this explicitly if needed, but for CLI it's often sequential
    # A better pattern would be to make read depend on write's completion.
    # cs.io.stdout.write returns None, so a pure data dependency isn't ideal.
    # Let's test the simple sequential case, which `run` will handle correctly.
    
    # A more robust workflow would use depends_on if we had it,
    # or chain them with a task that ignores the None result.
    
    @cs.task
    def read_after_write(_: None) -> str:
        return cs.io.stdin.read_line()

    user_name = read_after_write(write_prompt)
    workflow = create_greeting(user_name)

    result = cs.run(workflow)

    # Verify the output and the final result
    captured = capsys.readouterr()
    assert captured.out == prompt_message + "\n"
    assert result == "Hello, Cascade User!"