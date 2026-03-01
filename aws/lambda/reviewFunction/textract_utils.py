"""
textract_utils.py
=================
Wraps Amazon Textract AnalyzeDocument to extract structured text,
key-value pairs, and tables from a document stored in S3.

Public API
----------
  extract_document(s3_bucket, s3_key)
      → {
            "raw_text":   str,            # all WORD blocks joined
            "key_values": dict[str, str], # KEY → VALUE from FORMS
            "tables":     list[list[str]] # rows × cols
         }
"""

from __future__ import annotations

import logging
import os
from typing import Any

import boto3

logger = logging.getLogger(__name__)

AWS_REGION: str = os.environ.get("AWS_REGION", "us-east-1")

_textract = boto3.client("textract", region_name=AWS_REGION)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def extract_document(s3_bucket: str, s3_key: str) -> dict[str, Any]:
    """
    Run Textract AnalyzeDocument with FORMS and TABLES feature types.

    Returns
    -------
    {
      "raw_text":   str             – all WORDs joined by spaces
      "key_values": dict[str,str]  – form field name → value
      "tables":     list[list[str]]– first table (if any), rows × cols
    }
    """
    try:
        response = _textract.analyze_document(
            Document={"S3Object": {"Bucket": s3_bucket, "Name": s3_key}},
            FeatureTypes=["FORMS", "TABLES"],
        )
    except Exception as exc:
        logger.exception("Textract AnalyzeDocument failed for %s/%s", s3_bucket, s3_key)
        raise RuntimeError(f"Textract extraction failed: {exc}") from exc

    blocks = response.get("Blocks", [])
    block_map = {b["Id"]: b for b in blocks}

    raw_text   = _extract_raw_text(blocks)
    key_values = _extract_key_values(blocks, block_map)
    tables     = _extract_tables(blocks, block_map)

    logger.info(
        "Textract extracted %d chars, %d KV pairs, %d tables from %s",
        len(raw_text), len(key_values), len(tables), s3_key,
    )
    return {
        "raw_text":   raw_text,
        "key_values": key_values,
        "tables":     tables,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _extract_raw_text(blocks: list[dict]) -> str:
    words = [b["Text"] for b in blocks if b["BlockType"] == "WORD" and b.get("Text")]
    return " ".join(words)


def _extract_key_values(
    blocks: list[dict],
    block_map: dict[str, dict],
) -> dict[str, str]:
    """
    Reconstruct form KEY → VALUE pairs from Textract FORM relationship graph.
    """
    key_values: dict[str, str] = {}

    for block in blocks:
        if block["BlockType"] != "KEY_VALUE_SET":
            continue
        if "KEY" not in block.get("EntityTypes", []):
            continue

        key_text   = _get_text_from_relationships(block, block_map, "CHILD")
        value_block = _find_value_block(block, block_map)
        value_text  = _get_text_from_relationships(value_block, block_map, "CHILD") if value_block else ""

        if key_text:
            key_values[key_text.strip()] = value_text.strip()

    return key_values


def _find_value_block(
    key_block: dict,
    block_map: dict[str, dict],
) -> dict | None:
    for rel in key_block.get("Relationships", []):
        if rel["Type"] == "VALUE":
            for bid in rel["Ids"]:
                return block_map.get(bid)
    return None


def _get_text_from_relationships(
    block: dict | None,
    block_map: dict[str, dict],
    rel_type: str,
) -> str:
    if block is None:
        return ""
    texts: list[str] = []
    for rel in block.get("Relationships", []):
        if rel["Type"] == rel_type:
            for bid in rel["Ids"]:
                child = block_map.get(bid, {})
                if child.get("BlockType") in ("WORD", "SELECTION_ELEMENT"):
                    if child.get("BlockType") == "SELECTION_ELEMENT":
                        texts.append("SELECTED" if child.get("SelectionStatus") == "SELECTED" else "NOT_SELECTED")
                    else:
                        texts.append(child.get("Text", ""))
    return " ".join(texts)


def _extract_tables(
    blocks: list[dict],
    block_map: dict[str, dict],
) -> list[list[str]]:
    """
    Return the first TABLE found as a list-of-rows list-of-cells (strings).
    """
    tables: list[list[list[str]]] = []

    for block in blocks:
        if block["BlockType"] != "TABLE":
            continue

        rows: dict[int, dict[int, str]] = {}
        for rel in block.get("Relationships", []):
            if rel["Type"] != "CHILD":
                continue
            for bid in rel["Ids"]:
                cell = block_map.get(bid)
                if not cell or cell["BlockType"] != "CELL":
                    continue
                row_idx = cell.get("RowIndex", 1)
                col_idx = cell.get("ColumnIndex", 1)
                text = _get_text_from_relationships(cell, block_map, "CHILD")
                rows.setdefault(row_idx, {})[col_idx] = text.strip()

        if rows:
            max_col = max(max(cols) for cols in rows.values())
            table = [
                [rows[r].get(c, "") for c in range(1, max_col + 1)]
                for r in sorted(rows)
            ]
            tables.append(table)

    # Return first table only (most documents have one main table)
    return tables[0] if tables else []
