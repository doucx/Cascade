import pytest
from typer.testing import CliRunner
import cascade as cs

# Skip if typer is not installed
pytest.importorskip("typer")

runner = CliRunner()


def test_cli_generator_success():
    """Tests that the generated CLI runs the workflow correctly."""

    # 1. Define a workflow with Params
    name_param = cs.Param("name", description="The name to greet.")
    count_param = cs.Param(
        "count", default=1, type=int, description="Number of times to greet."
    )

    @cs.task
    def greet(name: str, count: int) -> str:
        return "\n".join([f"Hello, {name}!" for _ in range(count)])

    @cs.task
    def print_greeting(greeting: str):
        # We print to stdout, which the runner can capture
        print(greeting)

    workflow = print_greeting(greet(name=name_param, count=count_param))

    # 2. Generate the CLI application
    app = cs.cli(workflow)

    # 3. Invoke the CLI with arguments
    result = runner.invoke(app, ["--name", "Cascade", "--count", "2"])

    assert result.exit_code == 0
    assert "Hello, Cascade!\nHello, Cascade!" in result.stdout


def test_cli_generator_help_message():
    """Tests that the --help message is generated correctly from Param descriptions, including log_level."""

    name_param = cs.Param("name", description="The name to greet.")
    count_param = cs.Param(
        "count", default=1, type=int, description="Number of times to greet."
    )

    @cs.task
    def dummy(name: str, count: int):
        pass

    workflow = dummy(name=name_param, count=count_param)
    app = cs.cli(workflow)

    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "The name to greet." in result.stdout
    assert "Number of times to greet." in result.stdout
    assert "--name" in result.stdout
    assert "--count" in result.stdout
    assert "--log-level" in result.stdout
    assert "--log-format" in result.stdout
    assert "Format for logging" in result.stdout


def test_cli_json_log_format():
    """Tests that the CLI can produce JSON formatted logs."""
    @cs.task
    def simple_task():
        return "done"

    workflow = simple_task()
    app = cs.cli(workflow)

    result = runner.invoke(app, ["--log-format", "json"])

    assert result.exit_code == 0
    # Engine logs go to stderr by default
    logs = result.stderr.strip()
    
    # Check that each line is a valid JSON
    log_lines = [json.loads(line) for line in logs.splitlines()]

    # Find the specific log entry for run.started
    run_started_log = next((item for item in log_lines if item["event_id"] == "run.started"), None)
    
    # Assertions
    assert run_started_log is not None, "run.started event not found in logs"
    assert run_started_log["data"]["target_tasks"] == ["simple_task"]
    
    assert any(item["event_id"] == "task.started" and item["data"]["task_name"] == "simple_task" for item in log_lines)
    assert any(item["event_id"] == "run.finished_success" for item in log_lines)


def test_cli_missing_required_param():
    """Tests that the CLI correctly identifies and fails for missing required params."""
    required_param = cs.Param("required")  # No default value

    @cs.task
    def dummy_task(required: str):
        pass

    workflow = dummy_task(required=required_param)
    app = cs.cli(workflow)

    result = runner.invoke(app, [])

    assert result.exit_code != 0
    assert "Missing option '--required'" in result.stderr
