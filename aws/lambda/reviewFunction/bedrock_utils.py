"""
bedrock_utils.py
================
Wraps Amazon Bedrock (claude-3-sonnet) to generate a structured Markdown
payment description from bill and procedure data.

Public API
----------
  generate_payment_description(payment, extracted_data)
      → str  (Markdown)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3

logger = logging.getLogger(__name__)

AWS_REGION: str = os.environ.get("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID: str = os.environ.get(
    "BEDROCK_MODEL_ID",
    "anthropic.claude-3-sonnet-20240229-v1:0",
)

_bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)

# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a medical billing assistant. "
    "Given structured bill and procedure information, produce a concise, "
    "Markdown-formatted payment summary. "
    "Use bullet points for the charge breakdown. "
    "All amounts are in Indian Rupees (₹). "
    "Do NOT add any commentary outside the summary block. "
    "Output ONLY the Markdown — no preamble, no disclaimer."
)

_USER_TEMPLATE = """\
Generate a payment summary section in Markdown using this data:

Procedure: {procedure}
Surgery / Treatment: {surgery}
Total Bill Amount: {total_bill}
Insurance Covered: {claim_approved}
Patient Payable: {patient_payable}

Charge breakdown (as available):
{breakdown}

Format requirements:
- Start with "## Payment Summary"
- List each charge as a bold label followed by the amount
- End with a one-line summary of what the patient owes
"""


def generate_payment_description(
    payment: dict[str, Any],
    extracted_data: dict[str, Any],
    claim: dict[str, Any] | None = None,
) -> str:
    """
    Call Bedrock Claude-3-Sonnet to generate a Markdown payment description.

    Parameters
    ----------
    payment        : dict with at least totalBillAmount, amountToBePayed
    extracted_data : dict with surgeryType, procedureDate, diagnosis, …
    claim          : optional dict with claimAmountApproved

    Returns
    -------
    Markdown string for payment.description  (falls back to a plain summary
    on Bedrock errors so the review submission is never blocked).
    """
    procedure     = extracted_data.get("diagnosis", "Medical Procedure")
    surgery       = extracted_data.get("surgeryType", "Treatment")
    total_bill    = payment.get("totalBillAmount", "N/A")
    patient_pays  = payment.get("amountToBePayed", "N/A")
    claim_approved = claim.get("claimAmountApproved", "N/A") if claim else "N/A"

    # Try to build a breakdown from key_values if the bill extractor passed them
    breakdown_lines = []
    for label, key in [
        ("Hospital Charges",       "hospitalCharges"),
        ("Doctor Fees",            "doctorFees"),
        ("Medicines & Consumables","medicines"),
        ("Lab & Diagnostics",      "labDiagnostics"),
        ("Room Charges",           "roomCharges"),
        ("Miscellaneous",          "miscellaneous"),
    ]:
        val = payment.get(key)
        if val:
            breakdown_lines.append(f"- {label}: {val}")

    if not breakdown_lines:
        breakdown_lines.append("(Itemised breakdown not available)")

    user_prompt = _USER_TEMPLATE.format(
        procedure     = procedure,
        surgery       = surgery,
        total_bill    = total_bill,
        claim_approved= claim_approved,
        patient_payable = patient_pays,
        breakdown     = "\n".join(breakdown_lines),
    )

    body_payload = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 600,
        "system": _SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_prompt}],
    }

    try:
        response = _bedrock.invoke_model(
            modelId     = BEDROCK_MODEL_ID,
            contentType = "application/json",
            accept      = "application/json",
            body        = json.dumps(body_payload),
        )
        result = json.loads(response["body"].read())
        text = result["content"][0]["text"].strip()
        logger.info("Bedrock payment description generated (%d chars)", len(text))
        return text
    except Exception as exc:
        logger.exception("Bedrock call failed, falling back to plain summary: %s", exc)
        return (
            f"## Payment Summary\n\n"
            f"- **Procedure:** {procedure}\n"
            f"- **Surgery/Treatment:** {surgery}\n"
            f"- **Total Bill Amount:** {total_bill}\n"
            f"- **Insurance Covered:** {claim_approved}\n"
            f"- **Patient Payable:** {patient_pays}\n"
        )
