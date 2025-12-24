import cProfile
import pstats
import asyncio
import io
import sys
import os

try:
    from pyinstrument import Profiler
except ImportError:
    Profiler = None

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

    if Profiler:
        profiler = Profiler(async_mode="enabled")
        with profiler:
            await run_benchmark(engine, target, use_vm=use_vm)
        profiler.print()
        # Save as HTML for deep inspection
        html_file = f"profile_{name}_{iterations}.html"
        with open(html_file, "w") as f:
            f.write(profiler.output_html())
        print(f"Pyinstrument HTML report saved to {html_file}")
    else:
        pr = cProfile.Profile()
        pr.enable()
        await run_benchmark(engine, target, use_vm=use_vm)
        pr.disable()

        s = io.StringIO()
        sortby = "cumulative"
        ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
        ps.print_stats(20)
        print(s.getvalue())


if __name__ == "__main__":
    target_name = sys.argv[1] if len(sys.argv) > 1 else "simple"
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 1000

    print(f"Profiling {target_name} for {count} iterations...")
    asyncio.run(profile_target(target_name, count))
