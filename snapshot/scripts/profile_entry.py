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
    simple_countdown,
    heavy_complex_countdown,
    stable_complex_loop,
    noop,
    run_benchmark,
)
from cascade.runtime import Engine, MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor


async def profile_target(name: str, iterations: int):
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus())

    if name == "simple":
        target = simple_countdown(iterations)
    elif name == "heavy":
        target = heavy_complex_countdown(iterations)
    elif name == "stable":
        # Recreate the dependency chain locally to keep the script self-contained
        # for this specific test case, as per user instruction. Redundancy is fine.
        static_dep_chain = noop()
        for _ in range(10):
            static_dep_chain = noop(_dummy=static_dep_chain)
        target = stable_complex_loop([iterations], _dummy=static_dep_chain)
    else:
        print(f"Unknown target: {name}")
        return

    pr = cProfile.Profile()
    pr.enable()

    await run_benchmark(engine, target, iterations)

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
    target_name = sys.argv if len(sys.argv) > 1 else "simple"
    count = int(sys.argv) if len(sys.argv) > 2 else 1000

    print(f"Profiling {target_name} for {count} iterations...")
    asyncio.run(profile_target(target_name, count))