from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.dataset import (  # noqa: E402
    build_qc_report,
    flatten_dataset_records,
    load_raw_dataset,
    save_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Flatten EXACT dataset into one-sample-per-question JSON")
    parser.add_argument("--input", required=True, help="Raw dataset path")
    parser.add_argument("--output", required=True, help="Flattened dataset output path")
    parser.add_argument(
        "--qc-output",
        default="",
        help="Optional QC report path (default: <output>.qc.json)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    records = load_raw_dataset(args.input)
    flattened = flatten_dataset_records(records)
    save_json(args.output, flattened)

    qc_output = args.qc_output.strip() or f"{args.output}.qc.json"
    qc_report = build_qc_report(flattened)
    save_json(qc_output, qc_report)

    print(
        f"flattened_records={len(records)} "
        f"flattened_samples={len(flattened)} "
        f"output={args.output} qc={qc_output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
