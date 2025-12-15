import asyncio
from typing import Optional
from .spec.task import task

@task(name="shell")
async def shell(command: str, check: bool = True) -> str:
    """
    Asynchronously executes a shell command and returns its stdout.

    This is a pre-built Cascade task.

    Args:
        command: The shell command to execute.
        check: If True, raises a RuntimeError if the command returns a non-zero exit code.

    Returns:
        The stripped stdout of the command as a string.
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