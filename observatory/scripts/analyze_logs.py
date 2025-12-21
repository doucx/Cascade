import json
import pandas as pd

import cascade as cs


@cs.task
def load_and_parse_log(filepath: str) -> pd.DataFrame:
    """
    Reads a JSONL file line by line, parses each line as JSON,
    and returns a flattened pandas DataFrame.
    """
    print(f"INFO: Loading and parsing log file: {filepath}...")
    data = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"WARNING: Skipping malformed JSON line: {line.strip()}")
                continue

    # json_normalize is excellent for flattening nested JSON structures
    df = pd.json_normalize(data)

    # Rename columns for easier access (e.g., 'fps.min' -> 'fps_min')
    df.columns = df.columns.str.replace(".", "_", regex=False)
    print(f"INFO: Successfully loaded {len(df)} records.")
    return df


@cs.task
def analyze_correlations(df: pd.DataFrame) -> pd.DataFrame:
    """
    Selects key numerical metrics and computes their correlation matrix.
    """
    print("INFO: Analyzing correlations...")
    # Select the columns of interest for correlation analysis
    metrics_of_interest = [
        "ts",
        "fps_avg",
        "fps_min",
        "fps_max",
        "flush_duration_ms_avg",
        "render_jitter_ms_avg",
        "r_value_avg",
        "pulse_avg",
        "flash_count_avg",
    ]

    # Filter out columns that might not exist in all logs
    existing_metrics = [col for col in metrics_of_interest if col in df.columns]

    # Ensure all selected columns are numeric
    numeric_df = df[existing_metrics].apply(pd.to_numeric, errors="coerce")

    return numeric_df.corr()


@cs.task
def print_results(correlation_matrix: pd.DataFrame) -> None:
    """
    Formats and prints the correlation analysis results and key findings.
    """
    print("\n" + "=" * 80)
    print(" " * 25 + "LOG CORRELATION ANALYSIS RESULTS")
    print("=" * 80)

    print("\n[ Correlation Matrix ]\n")
    print(correlation_matrix.to_string(float_format="%.3f"))

    print("\n\n[ Key Findings ]\n")

    if "fps_min" not in correlation_matrix:
        print("WARNING: 'fps_min' column not found in correlation matrix.")
        return

    # Extract correlations related to fps_min
    fps_min_corr = correlation_matrix["fps_min"].sort_values(ascending=True)

    print("Correlations with 'fps_min':")
    print(fps_min_corr.to_string(float_format="%.3f"))

    print("\n--- Interpretation ---")

    # Check for the expected negative correlations
    flush_corr = fps_min_corr.get("flush_duration_ms_avg", 0)
    jitter_corr = fps_min_corr.get("render_jitter_ms_avg", 0)

    if flush_corr < -0.5:
        print(
            f"✅ Hypothesis Confirmed: A strong negative correlation ({flush_corr:.3f}) exists between 'fps_min' and 'flush_duration_ms_avg'."
        )
        print(
            "   This means as the time spent flushing updates increases, the minimum FPS drops significantly."
        )
    else:
        print(
            f"ℹ️ A moderate or weak negative correlation ({flush_corr:.3f}) was found between 'fps_min' and 'flush_duration_ms_avg'."
        )

    if jitter_corr < -0.5:
        print(
            f"✅ Hypothesis Confirmed: A strong negative correlation ({jitter_corr:.3f}) exists between 'fps_min' and 'render_jitter_ms_avg'."
        )
        print(
            "   This indicates that high render jitter (lag) is directly associated with dips in minimum FPS."
        )

    r_value_corr = fps_min_corr.get("r_value_avg", 0)
    if r_value_corr < -0.1:
        print(
            f"Interesting Insight: There is a negative correlation ({r_value_corr:.3f}) between 'fps_min' and the synchronization metric 'r_value_avg'."
        )
        print(
            "   This supports the idea that as the system becomes more synchronized (higher r_value), the performance becomes more 'spiky', leading to lower minimum FPS during the synchronized pulse."
        )

    print("\n" + "=" * 80)


def main():
    """
    Defines and runs the Cascade workflow.
    """
    # 1. Define workflow inputs
    log_filepath = cs.Param(
        "filepath", type=str, description="Path to the JSONL log file."
    )

    # 2. Build the workflow graph
    dataframe = load_and_parse_log(log_filepath)
    analysis_results = analyze_correlations(dataframe)
    final_report = print_results(analysis_results)

    # 3. Create and run the command-line interface
    cli = cs.create_cli(final_report)
    cli()


if __name__ == "__main__":
    main()
