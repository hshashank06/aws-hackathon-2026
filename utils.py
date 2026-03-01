"""
Utility functions for converting JSONL files to DynamoDB JSON format.

DynamoDB JSON format wraps each value with a type descriptor:
  - String  → {"S": "value"}
  - Number  → {"N": "123"}      (stored as string)
  - Boolean → {"BOOL": true}
  - Null    → {"NULL": true}
  - List    → {"L": [...]}
  - Map     → {"M": {...}}

Each output line follows the DynamoDB S3 import format:
  {"Item": {"attr": {"S": "val"}, ...}}
"""

from __future__ import annotations

import json
import os
from pathlib import Path


# ---------------------------------------------------------------------------
# Core type-marshalling helpers
# ---------------------------------------------------------------------------

def _marshal_value(value) -> dict:
    """Recursively convert a Python value to its DynamoDB JSON representation."""
    if value is None:
        return {"NULL": True}
    if isinstance(value, bool):
        return {"BOOL": value}
    if isinstance(value, (int, float)):
        # DynamoDB stores numbers as strings to preserve precision
        return {"N": str(value)}
    if isinstance(value, str):
        return {"S": value}
    if isinstance(value, list):
        return {"L": [_marshal_value(item) for item in value]}
    if isinstance(value, dict):
        return {"M": {k: _marshal_value(v) for k, v in value.items()}}
    # Fallback: coerce to string
    return {"S": str(value)}


def _marshal_item(record: dict) -> dict:
    """Convert a flat/nested Python dict to a DynamoDB JSON attribute map."""
    return {key: _marshal_value(val) for key, val in record.items()}


# ---------------------------------------------------------------------------
# File-level conversion
# ---------------------------------------------------------------------------

def convert_jsonl_to_dynamodb(input_path: str | os.PathLike,
                               output_path: str | os.PathLike) -> int:
    """
    Read *input_path* (JSONL) and write *output_path* in DynamoDB JSON format.

    Each output line looks like:
        {"Item": { ... DynamoDB-typed attributes ... }}

    Parameters
    ----------
    input_path  : path to the source .jsonl file
    output_path : path where the converted file is written (overwritten if exists)

    Returns
    -------
    Number of records successfully converted.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with input_path.open("r", encoding="utf-8") as fin, \
         output_path.open("w", encoding="utf-8") as fout:
        for line_no, raw_line in enumerate(fin, start=1):
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                record = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                print(f"  [WARN] {input_path.name} line {line_no}: skipping – {exc}")
                continue

            dynamodb_item = {"Item": _marshal_item(record)}
            fout.write(json.dumps(dynamodb_item, ensure_ascii=False) + "\n")
            count += 1

    return count


# ---------------------------------------------------------------------------
# Batch conversion for a directory
# ---------------------------------------------------------------------------

def convert_all(source_dir: str | os.PathLike,
                dest_dir: str | os.PathLike) -> None:
    """
    Convert every *.jsonl* file found in *source_dir* and write the results to
    *dest_dir*.

    Output file naming: ``<original_stem_lowercase>_dynamodb.jsonl``

    Parameters
    ----------
    source_dir : directory that contains the original JSONL files
    dest_dir   : directory where the DynamoDB-format files are written
    """
    source_dir = Path(source_dir)
    dest_dir = Path(dest_dir)

    jsonl_files = sorted(source_dir.glob("*.jsonl"))
    if not jsonl_files:
        print(f"No .jsonl files found in {source_dir}")
        return

    for src_file in jsonl_files:
        out_name = f"{src_file.stem.lower()}_dynamodb.jsonl"
        out_file = dest_dir / out_name
        print(f"Converting  {src_file.name}  →  {out_file.relative_to(dest_dir.parent.parent) if dest_dir.parent.parent in out_file.parents else out_file.name} …", end=" ", flush=True)
        n = convert_jsonl_to_dynamodb(src_file, out_file)
        print(f"{n} records written.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    BASE_DIR = Path(__file__).parent
    SOURCE_DIR = BASE_DIR / "resources" / "data" / "original"
    DEST_DIR   = BASE_DIR / "resources" / "data" / "dynamodb"

    print(f"Source : {SOURCE_DIR}")
    print(f"Output : {DEST_DIR}")
    print()
    convert_all(SOURCE_DIR, DEST_DIR)
    print("\nDone.")
