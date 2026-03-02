"""
extractors/claim_extractor.py
=============================
Builds a Bedrock Claude prompt from Textract output to extract
insurance claim fields via semantic understanding.
No regex or Comprehend — Claude interprets any label variation.

Output schema
-------------
{
  "claimId":                  str,   # e.g. "CLM-528527"
  "claimAmountApproved":      str,   # e.g. "₹65583"
  "remainingAmountToBePaid":  str,   # e.g. "₹43016"
}
"""

from __future__ import annotations

import json
import logging
from typing import Any

import bedrock_utils

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """\
You are an insurance claim document parser.

Below is text and key-value pairs extracted from an insurance claim using OCR.

RAW TEXT:
{raw_text}

KEY-VALUE PAIRS:
{key_values}

Extract exactly these fields and return ONLY valid JSON with no explanation:
{{
  "claimId":                 "claim reference number (e.g. CLM-528527)",
  "claimAmountApproved":     "amount approved or sanctioned by the insurer (e.g. ₹65583)",
  "remainingAmountToBePaid": "amount the patient still needs to pay (e.g. ₹43016)"
}}

Rules:
- Preserve the ₹ symbol in all amount fields
- Remove commas from numbers (₹65,583 → ₹65583)
- Use "" for any field that cannot be found
- claimId labels: Claim No, Claim ID, Claim Reference, TPA Ref No, Claim Number, etc.
- claimAmountApproved labels: Sanctioned Amount, Approved Amount, Settlement Amount,
  Claim Approved, Payable by Insurer, Net Payable by TPA, etc.
- remainingAmountToBePaid labels: Co-pay, Patient Liability, Balance, Deductible,
  Amount Not Covered, Patient Share, Outstanding Amount, Amount Payable by Patient, etc.
"""


def extract_claim(textract_result: dict[str, Any]) -> dict[str, str]:
    """
    Use Bedrock Claude to semantically extract claim fields from Textract output.

    Parameters
    ----------
    textract_result : output of textract_utils.extract_document()

    Returns
    -------
    claim dict ready for the review record.
    """
    prompt = _PROMPT_TEMPLATE.format(
        raw_text   = textract_result.get("raw_text", ""),
        key_values = json.dumps(
            textract_result.get("key_values", {}), indent=2, ensure_ascii=False
        ),
    )

    result = bedrock_utils.extract_structured_fields(prompt)

    claim = {
        "claimId":                 result.get("claimId",                 ""),
        "claimAmountApproved":     result.get("claimAmountApproved",     ""),
        "remainingAmountToBePaid": result.get("remainingAmountToBePaid", ""),
    }

    logger.info("Extracted claim: %s", claim)
    return claim
