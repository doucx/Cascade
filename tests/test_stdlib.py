import pytest
import cascade as cs

def test_shell_task_success():
    """Tests that a simple shell command runs and captures stdout."""
    # Using `echo` is a reliable cross-platform command
    result = cs.run(cs.shell("echo 'Hello, Cascade!'"))
    assert result == "Hello, Cascade!"

def test_shell_task_failure_with_check():
    """Tests that a failing command with check=True raises an error."""
    # `exit 1` is a simple way to force failure
    with pytest.raises(RuntimeError) as excinfo:
        cs.run(cs.shell("exit 1"))
    
    assert "failed with exit code 1" in str(excinfo.value)

def test_shell_task_integration():
    """Tests that the output of a shell task can be used by another task."""
    @cs.task
    def process_output(text: str):
        return f"Processed: {text.upper()}"

    command_output = cs.shell("echo 'data'")
    final_result = process_output(command_output)

    result = cs.run(final_result)
    assert result == "Processed: DATA"

def test_shell_map():
    """Tests mapping shell commands."""
    commands = ["echo 'foo'", "echo 'bar'"]
    
    # Map the shell task over a list of commands
    # This works because cs.shell is a Task instance, and Task implements LazyFactory
    results = cs.shell.map(command=commands)
    
    @cs.task
    def join_results(items: list[str]) -> str:
        return "|".join(items)
        
    final = join_results(results)
    
    assert cs.run(final) == "foo|bar"