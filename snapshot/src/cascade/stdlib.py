import asyncio
from typing import Optional, Tuple
from .spec.task import task

async def _run_shell_command(
    command: str, check: bool = True
) -> str:
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

# Create a pre-instantiated task for users to import and use directly.
shell = task(_run_shell_command, name="shell")