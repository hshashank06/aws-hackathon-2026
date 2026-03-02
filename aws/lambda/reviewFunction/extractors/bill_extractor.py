"""
extractors/bill_extractor.py
============================
Builds a Bedrock Claude prompt from Textract output to extract
hospital bill payment fields via semantic understanding.
No regex or Comprehend — Claude interprets any label variation.

Output schema
-------------
{
  "billNo":          str,   # e.g. "BILL-79780"
  "totalBillAmount": str,   # e.g. "₹108599"
  "amountToBePayed": str,   # e.g. "₹34956"  (patient's share)
}
"""

from __future__ import annotations

import json
import logging
from typing import Any

import bedrock_utils

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """\
You are a medical billing document parser.

Below is text and key-value pairs extracted from a hospital bill using OCR.

RAW TEXT:
{raw_text}

KEY-VALUE PAIRS:
{key_values}

Extract exactly these fields and return ONLY valid JSON with no explanation:
{{
  "billNo":          "bill or invoice identifier (e.g. BILL-79780)",
  "totalBillAmount": "total amount including all charges (e.g. ₹108599)",
  "amountToBePayed": "amount the patient must pay after insurance (e.g. ₹34956)"
}}

Rules:
- Preserve the ₹ symbol in all amount fields
- Remove commas from numbers (₹1,08,599 → ₹108599)
- Use "" for any field that cannot be found
- billNo labels: Bill No, Invoice No, Receipt No, Bill ID, Bill Number, etc.
- totalBillAmount labels: Total, Grand Total, Gross Amount, Total Bill, Total Charges, etc.
- amountToBePayed labels: Balance Due, Net Payable, Amount Due, Patient Share,
  Outstanding, Amount Payable, Patient Responsibility, Patient Liability, Co-pay, etc.
"""


def extract_payment(textract_result: dict[str, Any]) -> dict[str, str]:
    """
    Use Bedrock Claude to semantically extract payment fields from Textract output.

    Parameters
    ----------
    textract_result : output of textract_utils.extract_document()

    Returns
    -------
    payment dict ready for the review record.
    """
    prompt = _PROMPT_TEMPLATE.format(
        raw_text   = textract_result.get("raw_text", ""),
        key_values = json.dumps(
            textract_result.get("key_values", {}), indent=2, ensure_ascii=False
        ),
    )

    result = bedrock_utils.extract_structured_fields(prompt)

    payment = {
        "billNo":          result.get("billNo",          ""),
        "totalBillAmount": result.get("totalBillAmount", ""),
        "amountToBePayed": result.get("amountToBePayed", ""),
    }

    logger.info("Extracted payment: %s", payment)
    return payment
