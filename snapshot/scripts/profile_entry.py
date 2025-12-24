import cProfile
import pstats
import asyncio
import io
import sys
import os

# Ensure we can import cascade from the current workspace
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../packages/cascade-engine/src")
    )
)
sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../packages/cascade-spec/src")
    )
)
sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../packages/cascade-graph/src")
    )
)

from observatory.benchmarks.tco_performance import (
    create_explicit_loop,
    create_heavy_explicit_loop,
    vm_countdown,
    run_benchmark,
)
from cascade.runtime import Engine, MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor


async def profile_target(name: str, iterations: int):
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus())

    if name == "graph":
        target = create_explicit_loop(iterations)
        use_vm = False
    elif name == "heavy":
        target = create_heavy_explicit_loop(iterations, complexity=20)
        use_vm = False
    elif name == "vm":
        target = vm_countdown(n=iterations)
        use_vm = True
    else:
        print(f"Unknown target: {name}")
        return

    pr = cProfile.Profile()
    pr.enable()

    await run_benchmark(engine, target, use_vm=use_vm)

    pr.disable()

    s = io.StringIO()
    sortby = "cumulative"
    ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
    ps.print_stats(20)  # Show top 20
    print(s.getvalue())

    # Also save to file for external tools like snakeviz
    filename = f"profile_{name}_{iterations}.prof"
    ps.dump_stats(filename)
    print(f"Full profile dumped to {filename}")


if __name__ == "__main__":
    target_name = sys.argv[1] if len(sys.argv) > 1 else "simple"
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 1000

    print(f"Profiling {target_name} for {count} iterations...")
    asyncio.run(profile_target(target_name, count))
