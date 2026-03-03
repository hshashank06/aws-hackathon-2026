"""
extractors/claim_extractor.py
=============================
Builds a Bedrock Claude prompt from Textract output to extract
insurance claim settlement fields via semantic understanding.

Output schema
-------------
{
  "claimId":                  str,   # e.g. "CLM-528527"
  "originalBillAmount":       str,   # total hospital bill as shown in the claim doc
  "claimAmountApproved":      str,   # amount disbursed by insurer to hospital
  "remainingAmountToBePaid":  str,   # patient's out-of-pocket share
  "description":              str,   # Markdown claim settlement summary
}

The caller (_action_extract_claim) also derives:
  payment.amountToBePayed = remainingAmountToBePaid
"""

from __future__ import annotations

import json
import logging
from typing import Any

import bedrock_utils

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """\
You are an insurance claim settlement document parser.

Below is text and key-value pairs extracted from an insurance claim settlement
or TPA (Third-Party Administrator) letter using OCR.

RAW TEXT:
{raw_text}

KEY-VALUE PAIRS:
{key_values}

Extract exactly these fields and return ONLY valid JSON with no explanation:
{{
  "claimId":                 "claim reference / TPA reference number (e.g. CLM-528527)",
  "originalBillAmount":      "the original hospital bill total shown in this document (e.g. \u20b9108599)",
  "claimAmountApproved":     "amount approved/sanctioned/disbursed by the insurer to the hospital (e.g. \u20b965583)",
  "remainingAmountToBePaid": "amount the patient still needs to pay out-of-pocket (e.g. \u20b943016)"
}}

Rules:
- Preserve the \u20b9 symbol in all amount fields
- Remove commas from numbers (\u20b965,583 \u2192 \u20b965583)
- Use "" for any field that cannot be found
- claimId labels: Claim No, Claim ID, Claim Reference, TPA Ref No, Claim Number, etc.
- originalBillAmount labels: Total Bill, Hospital Bill, Gross Amount, Bill Amount,
  Total Claim Amount, Claimed Amount, Total Charges, etc.
- claimAmountApproved labels: Sanctioned Amount, Approved Amount, Settlement Amount,
  Claim Approved, Payable by Insurer, Net Payable by TPA, Amount Disbursed,
  Amount Paid to Hospital, etc.
- remainingAmountToBePaid labels: Co-pay, Patient Liability, Balance, Deductible,
  Amount Not Covered, Patient Share, Outstanding Amount, Amount Payable by Patient,
  Patient Co-pay, Non-payable Amount, etc.
  NOTE: if the insurer covers 100% there is no patient share \u2014 use "\u20b90" for this field.
"""

_DESCRIPTION_PROMPT_TEMPLATE = """\
You are a medical insurance assistant.

Below is the text from an insurance claim settlement document.

RAW TEXT:
{raw_text}

KEY-VALUE PAIRS:
{key_values}

Generate a concise Markdown claim settlement summary using ONLY the information present above.

Format requirements:
- Start with "## Claim Settlement Summary"
- Include claim ID, insurer / TPA name if present
- Show the original hospital bill amount
- Show the amount approved by the insurer (disbursed to the hospital)
- Show the non-payable / disallowed amounts if mentioned
- Show the patient's out-of-pocket balance clearly
- Do NOT invent or assume any values not present in the text
- Return ONLY the Markdown, no preamble or disclaimer
"""


def extract_claim(textract_result: dict[str, Any]) -> dict[str, str]:
    """
    Use Bedrock Claude to semantically extract claim settlement fields from
    Textract output and generate a Markdown summary.

    Parameters
    ----------
    textract_result : output of textract_utils.extract_document()

    Returns
    -------
    claim dict with claimId, originalBillAmount, claimAmountApproved,
    remainingAmountToBePaid, description.
    """
    raw_text   = textract_result.get("raw_text", "")
    key_values = textract_result.get("key_values", {})

    # ── 1. Extract structured claim fields ────────────────────────────────
    extraction_prompt = _PROMPT_TEMPLATE.format(
        raw_text   = raw_text,
        key_values = json.dumps(key_values, indent=2, ensure_ascii=False),
    )
    result = bedrock_utils.extract_structured_fields(extraction_prompt)

    remaining = result.get("remainingAmountToBePaid", "")
    # If insurer covers 100%, remainingAmountToBePaid may be blank \u2014 default to \u20b90
    if not remaining:
        remaining = "\u20b90"

    # ── 2. Generate Markdown description from raw text ────────────────────
    description_prompt = _DESCRIPTION_PROMPT_TEMPLATE.format(
        raw_text   = raw_text,
        key_values = json.dumps(key_values, indent=2, ensure_ascii=False),
    )
    description = bedrock_utils.generate_text(description_prompt)

    claim = {
        "claimId":                 result.get("claimId",            ""),
        "originalBillAmount":      result.get("originalBillAmount", ""),
        "claimAmountApproved":     result.get("claimAmountApproved",""),
        "remainingAmountToBePaid": remaining,
        "description":             description,
    }

    logger.info("Extracted claim: %s", {k: v for k, v in claim.items() if k != "description"})
    return claim
