#!/usr/bin/env python3
"""
Run the full pipeline for a county
==================================

Runs, in order:
  1. 01_scrape_data.py                         (download raw contributions)
  2. 02_summarize_contributions.py
  3. 03_create_summary_stats.py

USAGE
-----
Can be run from anywhere:

    python data_script/run_all.py COUNTY YEAR NEWSROOM STATE DATA_SOURCE

Example:
    python data_script/run_all.py "HUDSON COUNTY" 2026 "Slice of Culture" NJ "NJ Election Law Enforcement Commission"

The steps are run from the repository root (the parent of this file's
folder), since their input/output paths are relative to it. The pipeline
stops at the first step that fails.
"""

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent


def parse_args():
    parser = argparse.ArgumentParser(
        description="Scrape, summarize and create summary stats for a county."
    )
    parser.add_argument(
        "county", help='County name as shown on the site, e.g. "HUDSON COUNTY"'
    )
    parser.add_argument("year", help='Election year, e.g. "2026"')
    parser.add_argument("newsroom", help='Newsroom name, e.g. "Slice of Culture"')
    parser.add_argument("state", help='Two-letter state code, e.g. "NJ"')
    parser.add_argument(
        "data_source",
        help='Data source, e.g. "NJ Election Law Enforcement Commission"',
    )
    return parser.parse_args()


def run_step(script, *script_args):
    cmd = [sys.executable, str(SCRIPT_DIR / script), *script_args]
    print(f"\n=== Running {script} ===", flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def main():
    args = parse_args()
    try:
        run_step("01_scrape_data.py", args.county, args.year)
        run_step(
            "02_summarize_contributions.py",
            args.county,
            args.year,
            args.newsroom,
            args.state,
            args.data_source,
        )
        run_step("03_create_summary_stats.py", args.county)
    except subprocess.CalledProcessError as e:
        print(f"\nStep failed (exit code {e.returncode}): {' '.join(e.cmd)}")
        sys.exit(e.returncode)

    print("\nAll steps completed.")


if __name__ == "__main__":
    main()
