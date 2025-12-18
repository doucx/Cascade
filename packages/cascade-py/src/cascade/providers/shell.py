import asyncio
from cascade.spec.task import task
from cascade.providers import LazyFactory, Provider


class ShellProvider:
    name = "shell"

    def create_factory(self) -> LazyFactory:
        return _shell_task


# Define the task logic (moved from stdlib.py)
@task(name="shell")
async def _shell_task(command: str, check: bool = True) -> str:
    """
    Asynchronously executes a shell command and returns its stdout.
    """
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await proc.communicate()

    if check and proc.returncode != 0:
        raise RuntimeError(
            f"Command '{command}' failed with exit code {proc.returncode}:\n"
            f"STDOUT:\n{stdout.decode().strip()}\n"
            f"STDERR:\n{stderr.decode().strip()}"
        )

    return stdout.decode().strip()
