"""
Debug Script 3: Profiling Entry Point

Purpose:
  Provides a clean, simple entry point for running the full experiment
  with standard profiling tools like cProfile.

How to Run with cProfile:
  python -m cProfile -s tottime -o profile.out observatory/scripts/profile_entry.py

  Then, to view the stats:
  python -c "import pstats; p = pstats.Stats('profile.out'); p.sort_stats('tottime').print_stats(20)"

Expected Output:
  The full experiment will run for a short duration and then exit. The key
  output is the `profile.out` file, which contains detailed performance data.
  We will analyze this file to see which functions are consuming the most CPU time.
"""

import asyncio
from observatory.experiments import run_fireflies


# Use a smaller number of agents and shorter duration for quicker profiling runs
# And disable visualization as it adds noise to CPU profiles.
async def main():
    print("🚀 Starting Profiling Run (15 seconds, headless)...")
    await run_fireflies.run_experiment(
        num_agents=900,  # 30x30 grid, a significant but manageable number
        duration_seconds=15.0,
        visualize=False,
    )
    print("\n✅ Profiling run finished.")


if __name__ == "__main__":
    asyncio.run(main())
