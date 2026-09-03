#!/usr/bin/env python3
"""
Parquet to CSV Converter Utility

Converts single or multiple .parquet files into CSV format.
Supports interactive wizard, batch parallel processing, merging multiple parquet files into a single CSV,
selective column export, custom output directories, and choice of processing engine (polars/pandas).

Usage Examples:
    # 1. Interactive Wizard Mode (no arguments needed):
    python convert_parquet_to_csv.py

    # 2. Convert all parquet files in a directory:
    python convert_parquet_to_csv.py data/

    # 3. Convert specific files:
    python convert_parquet_to_csv.py file1.parquet file2.parquet -o output_csvs/

    # 4. Merge multiple parquet files into one CSV:
    python convert_parquet_to_csv.py "data/*.parquet" --merge -o combined.csv

    # 5. Use polars engine with 8 parallel workers:
    python convert_parquet_to_csv.py data/ -e polars -w 8
"""

import argparse
import glob
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional, Tuple, Union

# Try importing high-performance engines
HAS_POLARS = False
HAS_PANDAS = False

try:
    import polars as pl
    HAS_POLARS = True
except ImportError:
    pass

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    pass

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False


def find_parquet_files(input_patterns: List[str], recursive: bool = False) -> List[Path]:
    """
    Expand directory paths, globs, and direct file paths into a sorted list of unique Parquet Path objects.
    """
    parquet_files = set()

    for pattern in input_patterns:
        path_obj = Path(pattern)
        if path_obj.is_dir():
            search_pattern = "**/*.parquet" if recursive else "*.parquet"
            found = list(path_obj.glob(search_pattern))
            search_pattern_upper = "**/*.PARQUET" if recursive else "*.PARQUET"
            found.extend(list(path_obj.glob(search_pattern_upper)))
            parquet_files.update(found)
        elif "*" in pattern or "?" in pattern or "[" in pattern:
            matched = glob.glob(pattern, recursive=recursive)
            for m in matched:
                p = Path(m)
                if p.is_file() and p.suffix.lower() == ".parquet":
                    parquet_files.add(p)
        elif path_obj.is_file():
            if path_obj.suffix.lower() == ".parquet":
                parquet_files.add(path_obj)
            else:
                print(f"Warning: Skipping non-parquet file '{pattern}'")
        else:
            matched = glob.glob(pattern, recursive=recursive)
            if matched:
                for m in matched:
                    p = Path(m)
                    if p.is_file() and p.suffix.lower() == ".parquet":
                        parquet_files.add(p)
            else:
                print(f"Warning: Input path or pattern '{pattern}' not found.")

    return sorted(list(parquet_files))


def convert_single_file(
    args_tuple: Tuple[Path, Path, str, Optional[List[str]], bool, bool]
) -> Tuple[Path, Path, bool, int, float, str]:
    """
    Worker function to convert a single parquet file to CSV.
    Returns: (input_path, output_path, success, row_count, elapsed_time, error_message)
    """
    input_path, output_path, engine, columns, overwrite, include_index = args_tuple
    start_time = time.time()

    if output_path.exists() and not overwrite:
        return (
            input_path,
            output_path,
            False,
            0,
            0.0,
            f"File already exists: {output_path} (use --overwrite or -f to overwrite)",
        )

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        rows = 0
        if engine == "polars" and HAS_POLARS:
            df = pl.read_parquet(str(input_path), columns=columns)
            rows = len(df)
            df.write_csv(str(output_path))
        elif engine == "pandas" and HAS_PANDAS:
            df = pd.read_parquet(str(input_path), columns=columns)
            rows = len(df)
            df.to_csv(str(output_path), index=include_index)
        else:
            if HAS_POLARS:
                df = pl.read_parquet(str(input_path), columns=columns)
                rows = len(df)
                df.write_csv(str(output_path))
            elif HAS_PANDAS:
                df = pd.read_parquet(str(input_path), columns=columns)
                rows = len(df)
                df.to_csv(str(output_path), index=include_index)
            else:
                return (
                    input_path,
                    output_path,
                    False,
                    0,
                    0.0,
                    "Neither polars nor pandas is installed.",
                )

        elapsed = time.time() - start_time
        return (input_path, output_path, True, rows, elapsed, "")
    except Exception as e:
        elapsed = time.time() - start_time
        return (input_path, output_path, False, 0, elapsed, str(e))


def merge_and_convert(
    files: List[Path],
    output_path: Path,
    engine: str,
    columns: Optional[List[str]] = None,
    overwrite: bool = False,
    include_index: bool = False,
) -> Tuple[bool, int, float, str]:
    """
    Merge multiple Parquet files into a single combined CSV file.
    """
    if output_path.exists() and not overwrite:
        return (
            False,
            0,
            0.0,
            f"Output file already exists: {output_path} (use --overwrite or -f to overwrite)",
        )

    start_time = time.time()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        total_rows = 0
        if engine == "polars" and HAS_POLARS:
            lazy_dfs = [pl.scan_parquet(str(f)) for f in files]
            combined_lazy = pl.concat(lazy_dfs, how="diagonal")
            if columns:
                combined_lazy = combined_lazy.select(columns)
            df = combined_lazy.collect()
            total_rows = len(df)
            df.write_csv(str(output_path))
        elif HAS_PANDAS:
            dfs = [pd.read_parquet(str(f), columns=columns) for f in files]
            combined_df = pd.concat(dfs, ignore_index=True)
            total_rows = len(combined_df)
            combined_df.to_csv(str(output_path), index=include_index)
        else:
            return False, 0, 0.0, "Neither polars nor pandas is installed."

        elapsed = time.time() - start_time
        return True, total_rows, elapsed, ""
    except Exception as e:
        elapsed = time.time() - start_time
        return False, 0, elapsed, str(e)


def convert_parquet_files(
    input_patterns: List[str],
    output_dir: Optional[Union[str, Path]] = None,
    merge: bool = False,
    merge_name: str = "merged_output.csv",
    engine: str = "auto",
    workers: int = 4,
    columns: Optional[List[str]] = None,
    recursive: bool = False,
    overwrite: bool = False,
    include_index: bool = False,
) -> None:
    """
    Main function to handle parquet to CSV conversion batching and options.
    """
    if not HAS_POLARS and not HAS_PANDAS:
        print("Error: Neither 'polars' nor 'pandas' package is installed.")
        print("Please install at least one: pip install polars OR pip install pandas pyarrow")
        sys.exit(1)

    if engine == "auto":
        engine = "polars" if HAS_POLARS else "pandas"

    print(f"[*] Scanning for parquet files matching: {input_patterns}")
    files = find_parquet_files(input_patterns, recursive=recursive)

    if not files:
        print("[!] No parquet files found matching specified inputs.")
        return

    print(f"[*] Found {len(files)} parquet file(s). Engine: [{engine.upper()}]")

    if merge:
        if output_dir:
            out_p = Path(output_dir)
            if out_p.suffix.lower() == ".csv":
                merged_output_path = out_p
            else:
                merged_output_path = out_p / merge_name
        else:
            merged_output_path = Path.cwd() / merge_name

        print(f"[*] Merging {len(files)} files into single CSV: {merged_output_path}")
        success, rows, elapsed, err = merge_and_convert(
            files=files,
            output_path=merged_output_path,
            engine=engine,
            columns=columns,
            overwrite=overwrite,
            include_index=include_index,
        )

        if success:
            print(f"[SUCCESS] Successfully merged {len(files)} files into '{merged_output_path}'")
            print(f"    - Total Rows: {rows:,}")
            print(f"    - Time Taken: {elapsed:.2f} seconds")
            print(f"    - Output Size: {merged_output_path.stat().st_size / (1024 * 1024):.2f} MB")
        else:
            print(f"[ERROR] Merge failed: {err}")
        return

    out_dir_path = Path(output_dir) if output_dir else None

    tasks = []
    for f in files:
        if out_dir_path:
            out_file = out_dir_path / f.with_suffix(".csv").name
        else:
            out_file = f.with_suffix(".csv")

        tasks.append((f, out_file, engine, columns, overwrite, include_index))

    print(f"[*] Converting {len(tasks)} files (Workers: {workers})...")
    start_all = time.time()

    successful_conversions = 0
    failed_conversions = 0
    skipped_conversions = 0
    total_rows = 0

    if workers > 1 and len(tasks) > 1:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(convert_single_file, task): task[0] for task in tasks}
            iterator = as_completed(futures)
            if HAS_TQDM:
                iterator = tqdm(iterator, total=len(tasks), desc="Converting Parquet to CSV")

            for future in iterator:
                in_p, out_p, success, rows, elapsed, err = future.result()
                if success:
                    successful_conversions += 1
                    total_rows += rows
                else:
                    if "already exists" in err:
                        skipped_conversions += 1
                    else:
                        failed_conversions += 1
                        print(f"\n[ERROR] Failed to convert {in_p.name}: {err}")
    else:
        iterator = tasks
        if HAS_TQDM:
            iterator = tqdm(tasks, desc="Converting Parquet to CSV")

        for task in iterator:
            in_p, out_p, success, rows, elapsed, err = convert_single_file(task)
            if success:
                successful_conversions += 1
                total_rows += rows
            else:
                if "already exists" in err:
                    skipped_conversions += 1
                else:
                    failed_conversions += 1
                    print(f"\n[ERROR] Failed to convert {in_p.name}: {err}")

    total_time = time.time() - start_all
    print("\n" + "=" * 50)
    print("CONVERSION SUMMARY")
    print("=" * 50)
    print(f"  * Total files found:      {len(files)}")
    print(f"  * Successfully converted: {successful_conversions}")
    print(f"  * Skipped (Exists):       {skipped_conversions}")
    print(f"  * Failed:                 {failed_conversions}")
    print(f"  * Total Rows Processed:   {total_rows:,}")
    print(f"  * Total Time Elapsed:     {total_time:.2f} seconds")
    print("=" * 50)


def run_interactive_wizard():
    """
    Interactive command-line wizard for guided Parquet to CSV conversion.
    """
    print("\n" + "=" * 55)
    print("      PARQUET TO CSV CONVERTER - INTERACTIVE MENU")
    print("=" * 55)
    print("Select conversion mode:")
    print("  [1] Convert all .parquet files in a folder / directory")
    print("  [2] Convert a specific .parquet file")
    print("  [3] Merge multiple .parquet files into 1 COMBINED .csv file")
    print("  [4] Exit")
    print("-" * 55)

    choice = input("Enter choice (1-4) [default: 1]: ").strip()
    if choice == "4":
        print("Exiting.")
        sys.exit(0)

    merge = (choice == "3")
    is_single_file_mode = (choice == "2")

    default_input = "data"
    if Path("data").exists():
        default_input = "data"
    elif is_single_file_mode:
        parquet_candidates = list(Path.cwd().glob("*.parquet")) + list(Path.cwd().glob("**/*.parquet"))
        if parquet_candidates:
            default_input = str(parquet_candidates[0])
        else:
            default_input = "file.parquet"

    print(f"\n--- STEP 1: Select Input ---")
    if is_single_file_mode:
        input_path = input(f"Enter parquet file path [default: {default_input}]: ").strip() or default_input
        recursive = False
    else:
        input_path = input(f"Enter folder path or glob pattern [default: {default_input}]: ").strip() or default_input
        rec_choice = input("Search subfolders recursively? (y/n) [default: n]: ").strip().lower()
        recursive = rec_choice in ("y", "yes")

    print(f"\n--- STEP 2: Select Output Folder ---")
    if merge:
        merge_name = input("Enter output CSV filename [default: merged_output.csv]: ").strip() or "merged_output.csv"
        out_dir = input("Enter output directory (or press Enter for current folder): ").strip() or None
    else:
        merge_name = "merged_output.csv"
        out_dir = input("Enter output directory (or press Enter to save alongside input): ").strip() or None

    print(f"\n--- STEP 3: Options ---")
    over_choice = input("Overwrite existing CSV files if present? (y/n) [default: n]: ").strip().lower()
    overwrite = over_choice in ("y", "yes")

    col_input = input("Select specific columns (space/comma separated, or press Enter for ALL): ").strip()
    columns = None
    if col_input:
        columns = [c.strip() for c in col_input.replace(",", " ").split() if c.strip()]

    eng_choice = input("Engine preference (polars/pandas/auto) [default: auto]: ").strip().lower()
    engine = eng_choice if eng_choice in ("polars", "pandas") else "auto"

    print("\nStarting conversion...\n")
    convert_parquet_files(
        input_patterns=[input_path],
        output_dir=out_dir,
        merge=merge,
        merge_name=merge_name,
        engine=engine,
        workers=4,
        columns=columns,
        recursive=recursive,
        overwrite=overwrite,
        include_index=False,
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert single or multiple .parquet files to .csv format with high performance.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  1. Interactive Wizard (No arguments needed):
     python convert_parquet_to_csv.py

  2. Direct CLI Conversion:
     python convert_parquet_to_csv.py data/

  3. Merge multiple parquet files:
     python convert_parquet_to_csv.py "data/*.parquet" --merge -o combined.csv
        """,
    )

    parser.add_argument(
        "inputs",
        nargs="*",
        default=[],
        help="Input parquet file paths, directories, or glob patterns (e.g. data/*.parquet)",
    )

    parser.add_argument(
        "-o",
        "--output-dir",
        type=str,
        default=None,
        help="Output directory for CSV files (or output path if --merge is used). Defaults to same folder as input.",
    )

    parser.add_argument(
        "-m",
        "--merge",
        action="store_true",
        help="Merge all matching parquet files into a single CSV file.",
    )

    parser.add_argument(
        "--merge-name",
        type=str,
        default="merged_output.csv",
        help="Filename for the merged CSV output (default: merged_output.csv).",
    )

    parser.add_argument(
        "-e",
        "--engine",
        choices=["auto", "polars", "pandas"],
        default="auto",
        help="Execution engine ('polars' for high-speed multi-threaded parsing, 'pandas', or 'auto').",
    )

    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=4,
        help="Number of parallel worker processes for batch file conversion (default: 4).",
    )

    parser.add_argument(
        "-c",
        "--columns",
        nargs="+",
        default=None,
        help="Specific column names to extract/export (space-separated).",
    )

    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively search input directories for .parquet files.",
    )

    parser.add_argument(
        "-f",
        "--overwrite",
        action="store_true",
        help="Overwrite existing CSV output files.",
    )

    parser.add_argument(
        "--index",
        action="store_true",
        help="Include DataFrame row index in output CSV (pandas engine only).",
    )

    return parser.parse_args()


if __name__ == "__main__":
    if len(sys.argv) == 1:
        run_interactive_wizard()
    else:
        args = parse_args()
        if not args.inputs:
            run_interactive_wizard()
        else:
            convert_parquet_files(
                input_patterns=args.inputs,
                output_dir=args.output_dir,
                merge=args.merge,
                merge_name=args.merge_name,
                engine=args.engine,
                workers=args.workers,
                columns=args.columns,
                recursive=args.recursive,
                overwrite=args.overwrite,
                include_index=args.index,
            )
