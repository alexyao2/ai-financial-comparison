#runs experiment from start to finish
import argparse
import shutil
import asyncio
import json
import html
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent

def batch_report(output, frequencies, exit_codes):
    summaries = []
    statuses = []
    
    for frequency in frequencies:
        folder = output / frequency
        status_path = folder / "status.json"

        if not status_path.exists():
            statuses.append({
                "frequency": frequency,
                "strategy": "experiment",
                "status": "missing",
                "exit_code": None,
            })
            continue
        
        saved_status = json.loads(status_path.read_text())
        for strategy, details in saved_status.items():
            statuses.append({
                **details,
                "frequency": frequency,
                "strategy": strategy
            })
        summary_path = folder / "summary.csv"
        if summary_path.exists():
            try: 
                summary = pd.read_csv(summary_path)
            except pd.errors.EmptyDataError:
                continue

            complete = [
                name for name, details in saved_status.items()
                if details["status"] == "complete"
            ]
            summary = summary[summary["strategy"].isin(complete)].copy()
            summary.insert(0, "frequency", frequency)
            summaries.append(summary)

    combined = (
        pd.concat(summaries, ignore_index=True) if summaries else pd.DataFrame()
    )
    combined.to_csv(output / "summary.csv", index=False)
    (output / "status.json").write_text(
        json.dumps({
            "exit_codes": exit_codes,
            "strategy": statuses,
        }, indent=2), encoding="utf-8"
    )

    results_table = (combined.to_html(index=False, float_format=lambda value: f"{value:,.4f}")
        if not combined.empty else "<p>No completed results yet.</p>")

    status_table = pd.DataFrame(statuses).to_html(index=False)
    links = "\n".join(
        f'<li><a href="{frequency}/report.html">'
        f'{html.escape(frequency)} report</a></li>'
        for frequency in frequencies
        if (output / frequency / "report.html").exists()
    )

    document = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Rebalance frequency comparison</title>
<style>
body {{ font: 15px system-ui; margin: 40px; }}
table {{ border-collapse: collapse; }}
td, th {{ padding: 8px; border: 1px solid #ddd; }}
</style>
</head>
<body>
<h1>Rebalance frequency comparison</h1>
<p>Completed strategies only. Failed strategies appear in the status table.
Returns and drawdowns are decimal fractions.</p>
<h2>Results</h2>
{results_table}
<h2>Execution status</h2>
{status_table}
<h2>Individual reports</h2>
<ul>{links}</ul>
</body>
</html>
"""
    (output / "report.html").write_text(document, encoding="utf-8")



async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument(
        "--providers",
        nargs="+",
        default=["nvidia_nemotron", "nvidia_google", "gemini", "groq"],
    )
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true",
                        help="Delete the selected output run before starting")
    args = parser.parse_args()

    output = args.output.resolve()
    
    if args.overwrite:
        runs_root = (ROOT / "runs").resolve()
        if output == runs_root or runs_root not in output.parents:
            parser.error("--overwrite requires an output folder inside runs/.")
        if output.exists():
            if not output.is_dir():
                parser.error("Output exists but is not a directory.")
            shutil.rmtree(output)
    elif output.exists():
        parser.error("Output exists already, use --overwrite to replace it.")
    output.mkdir(parents=True, exist_ok=True)

    frequencies = ["monthly", "quarterly", "annually"]
    exit_codes = {}
    environment = os.environ.copy()
    environment["API_RETRY_DELAY_SECONDS"] = "30"

    for index, frequency in enumerate(frequencies):
        command = [
            sys.executable,
            "-u",
            str(ROOT / "run_experiment.py"),
            "--providers", * args.providers,
            "--start", args.start,
            "--end", args.end,
            "--frequency", frequency,
            "--output", str(output / frequency),
        ]
        if args.live:
            command.append("--live")
        if args.fresh:
            command.append("--fresh")
        print(f"\nStarting experiment with {frequency} frequency", flush = True)
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd = ROOT,
            env = environment,
        )
        exit_codes[frequency] = await process.wait()

        batch_report(output, frequencies[:index + 1], exit_codes)
        if index < len(frequencies) - 1:
            print("Waiting 30 seconds before the next experiment...", flush=True)
            await asyncio.sleep(30)
    print(f"\nFinal report: {output / 'report.html'}")
    return int(any(code != 0 for code in exit_codes.values()))


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
