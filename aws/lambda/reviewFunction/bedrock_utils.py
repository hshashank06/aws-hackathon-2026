"""
bedrock_utils.py
================
Wraps Amazon Bedrock via the Converse API (boto3 bedrock-runtime.converse).

The Converse API provides a single unified interface for all Bedrock models
(Amazon Nova, Anthropic Claude, Meta Llama, etc.) so switching models only
requires changing the BEDROCK_MODEL_ID environment variable.

Default model: amazon.nova-lite-v1:0
  - Fast, cheap, no AWS Marketplace subscription / payment required.
  - Set env var BEDROCK_MODEL_ID to switch to any other Bedrock model.

Medical extraction model: amazon.nova-pro-v1:0
  - Amazon Nova Pro -- high-accuracy, no marketplace subscription required.
  - Replaces Claude Sonnet 4.6 for structured medical record parsing.
  - Set env var MEDICAL_MODEL_ID to override.

Public API
----------
  generate_payment_description(payment, extracted_data, claim, raw_text)
  generate_text(prompt, max_tokens, label)
  extract_structured_fields(prompt)
  generate_embedding(text)

Note on anthropic_version
-------------------------
When using invoke_model directly with Anthropic models, the request body MUST
include "anthropic_version": "bedrock-2023-05-31".  This is a required Anthropic
API contract field -- NOT the model version.  The Converse API handles this
automatically so you do NOT need to include it.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import boto3

# Use the ROOT logger -- Lambda configures this handler to write to CloudWatch.
# Module-level loggers (getLogger(__name__)) propagate to root but their level
# may be NOTSET in some Lambda runtime versions.  Using the root logger directly
# guarantees every log line appears in /aws/lambda/reviewFunction.
logger = logging.getLogger()

AWS_REGION: str = os.environ.get("AWS_REGION", "us-east-1")

# Amazon Nova Lite -- no marketplace subscription / payment method required.
# Override with env var BEDROCK_MODEL_ID to use Claude, Llama, etc.
BEDROCK_MODEL_ID: str = os.environ.get(
    "BEDROCK_MODEL_ID",
    "amazon.nova-lite-v1:0",
)

# Amazon Nova Pro is used for medical record extraction where accuracy matters.
# Nova Pro matches Claude Sonnet capability without requiring a marketplace
# subscription / separate payment method.
# Override via MEDICAL_MODEL_ID env var with any model ID or full ARN.
# Alternatives (set as env var):
#   amazon.nova-lite-v1:0                             -- cheaper, faster
#   amazon.nova-premier-v1:0                          -- highest capability
#   us.amazon.nova-pro-v1:0                           -- cross-region inference
MEDICAL_MODEL_ID: str = os.environ.get(
    "MEDICAL_MODEL_ID",
    "amazon.nova-pro-v1:0",
)

EMBEDDING_MODEL_ID: str = os.environ.get(
    "BEDROCK_EMBEDDING_MODEL_ID",
    "amazon.titan-embed-text-v2:0",
)

_bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)

# Emitted once per cold start -- confirms module loaded and shows region/model.
logger.info(
    "[bedrock_utils] module loaded -- region=%s  model=%s  medical_model=%s  embedding=%s",
    AWS_REGION, BEDROCK_MODEL_ID, MEDICAL_MODEL_ID, EMBEDDING_MODEL_ID,
)


# ---------------------------------------------------------------------------
# Internal: Converse API wrapper
# ---------------------------------------------------------------------------

def _converse(
    user_text: str,
    *,
    system_text: str | None = None,
    max_tokens: int = 1024,
    temperature: float = 0.0,
    label: str = "converse",
    model_id: str | None = None,
) -> str:
    """
    Invoke any Bedrock model via the Converse API and return the response text.

    The Converse API uses a model-agnostic message format:
      messages = [{"role": "user", "content": [{"text": "..."}]}]
    This works identically for Nova, Claude, Llama, Mistral, etc.

    Pass model_id to override the default BEDROCK_MODEL_ID for this call.
    Returns the response text (stripped).  Raises on failure.
    """
    resolved_model = model_id or BEDROCK_MODEL_ID
    messages = [{"role": "user", "content": [{"text": user_text}]}]
    kwargs: dict[str, Any] = {
        "modelId":         resolved_model,
        "messages":        messages,
        "inferenceConfig": {"maxTokens": max_tokens, "temperature": temperature},
    }
    if system_text:
        kwargs["system"] = [{"text": system_text}]

    preview = (user_text[:300] + "...") if len(user_text) > 300 else user_text
    logger.info(
        "[bedrock_utils][%s] INVOKING Converse API  model=%s  max_tokens=%d  "
        "temperature=%s  prompt_len=%d  preview: %.300s",
        label, resolved_model, max_tokens, temperature, len(user_text), preview,
    )

    response = _bedrock.converse(**kwargs)

    usage       = response.get("usage", {})
    stop_reason = response.get("stopReason", "")
    text        = response["output"]["message"]["content"][0]["text"].strip()

    logger.info(
        "[bedrock_utils][%s] RESPONSE  stop=%s  in=%s  out=%s  chars=%d  preview: %.300s",
        label, stop_reason,
        usage.get("inputTokens", "?"), usage.get("outputTokens", "?"),
        len(text), text,
    )
    return text


# ---------------------------------------------------------------------------
# Public: free-form text generation
# ---------------------------------------------------------------------------

def generate_text(prompt: str, max_tokens: int = 800, label: str = "generate_text") -> str:
    """
    Send a free-form prompt to Bedrock (Converse API) and return the text.
    Used by bill_extractor / claim_extractor to generate Markdown descriptions
    directly from Textract raw_text / tables.

    Never raises -- returns an empty string on failure.
    """
    logger.info("[bedrock_utils][%s] START  prompt_len=%d", label, len(prompt))
    try:
        text = _converse(prompt, max_tokens=max_tokens, temperature=0, label=label)
        logger.info("[bedrock_utils][%s] SUCCESS  output_len=%d", label, len(text))
        return text
    except Exception as exc:
        logger.error(
            "[bedrock_utils][%s] FAILED -- %s: %s",
            label, type(exc).__name__, exc,
        )
        return ""


# ---------------------------------------------------------------------------
# Public: structured JSON field extraction
# ---------------------------------------------------------------------------

def extract_structured_fields(prompt: str) -> dict[str, Any]:
    """
    Send a structured extraction prompt to Bedrock (Converse API) and return
    the parsed JSON dict.  Uses the default Nova Lite model.

    temperature=0 for deterministic, schema-constrained output.
    Never raises -- returns {} on any failure.
    """
    return _extract_fields_with_model(prompt, model_id=None, label="extract_fields")


def extract_structured_fields_medical(prompt: str) -> dict[str, Any]:
    """
    Same as extract_structured_fields but uses MEDICAL_MODEL_ID (Amazon Nova Pro
    by default) for higher accuracy on medical record parsing.

    Never raises -- returns {} on any failure.
    """
    return _extract_fields_with_model(prompt, model_id=MEDICAL_MODEL_ID, label="extract_fields_medical")


def _extract_fields_with_model(prompt: str, *, model_id: str | None, label: str) -> dict[str, Any]:
    """Internal shared implementation for structured JSON extraction."""
    logger.info("[bedrock_utils][%s] START  model=%s  prompt_len=%d", label, model_id or BEDROCK_MODEL_ID, len(prompt))
    raw_text = "(no response yet)"
    try:
        raw_text = _converse(prompt, max_tokens=1024, temperature=0, label=label, model_id=model_id)

        # Strip markdown code fences that Nova/Claude may wrap around JSON
        clean = re.sub(r"^```(?:json)?\n?", "", raw_text)
        clean = re.sub(r"\n?```$",          "", clean).strip()

        logger.info(
            "[bedrock_utils][%s] Parsing JSON  clean_len=%d  preview: %.300s",
            label, len(clean), clean,
        )
        result = json.loads(clean)
        logger.info(
            "[bedrock_utils][%s] SUCCESS  field_count=%d  fields=%s",
            label, len(result), list(result.keys()),
        )
        return result
    except json.JSONDecodeError as exc:
        logger.warning(
            "[bedrock_utils][%s] JSON PARSE FAILED -- %s  raw: %.500s",
            label, exc, raw_text,
        )
        return {}
    except Exception as exc:
        logger.error(
            "[bedrock_utils][%s] INVOCATION FAILED -- %s: %s",
            label, type(exc).__name__, exc,
        )
        return {}


# ---------------------------------------------------------------------------
# Public: payment description (Markdown)
# ---------------------------------------------------------------------------

_BILLING_SYSTEM = (
    "You are a medical billing assistant. "
    "Produce a concise Markdown payment summary from the information provided. "
    "All amounts are in Indian Rupees. "
    "Output ONLY the Markdown -- no preamble, no disclaimer."
)


def generate_payment_description(
    payment: dict[str, Any],
    extracted_data: dict[str, Any],
    claim: dict[str, Any] | None = None,
    raw_text: str = "",
) -> str:
    """
    Return a Markdown payment description.

    Priority (best to worst):
      1. bill_extractor already set payment["description"] -- return it directly.
      2. raw_text provided -- pass to Claude/Nova so it can see every charge line.
      3. Fallback -- build a simple text block from already-extracted field values.

    Parameters
    ----------
    payment        : dict, may contain 'description' from bill_extractor
    extracted_data : dict with surgeryType, diagnosis, etc.
    claim          : optional dict with claimAmountApproved, etc.
    raw_text       : raw OCR text from the bill (preferred input to AI)
    """
    logger.info(
        "[bedrock_utils][payment_desc] START  has_prebuilt=%s  raw_text_len=%d  "
        "payment_keys=%s  claim_present=%s",
        bool(payment.get("description")), len(raw_text),
        list(payment.keys()), bool(claim),
    )

    # Priority 1
    if payment.get("description"):
        logger.info(
            "[bedrock_utils][payment_desc] Using pre-built description (%d chars)",
            len(payment["description"]),
        )
        return payment["description"]

    # Priority 2: pass raw_text directly
    if raw_text.strip():
        extra_ctx = ""
        if claim:
            extra_ctx = (
                "\n\nInsurance/Claim context:\n"
                f"  Claim ID              : {claim.get('claimId', 'N/A')}\n"
                f"  Original Bill Amount  : {claim.get('originalBillAmount', 'N/A')}\n"
                f"  Insurer Approved      : {claim.get('claimAmountApproved', 'N/A')}\n"
                f"  Patient Out-of-Pocket : {claim.get('remainingAmountToBePaid', 'N/A')}"
            )
        raw_prompt = (
            "Generate a payment summary section in Markdown from this hospital bill text.\n\n"
            f"HOSPITAL BILL RAW TEXT:\n{raw_text}{extra_ctx}\n\n"
            "Format requirements:\n"
            "- Start with '## Payment Summary'\n"
            "- Include Bill No, hospital name, patient name, dates if present\n"
            "- List each charge line as: **Charge Name**: amount\n"
            "- Show Sub Total, GST/Tax, and Grand Total prominently\n"
            "- If insurance info is present, show disbursed vs patient payable\n"
            "- End with bold: '**Total patient payable: X**'\n"
            "- Do NOT invent numbers not present in the text"
        )
        logger.info(
            "[bedrock_utils][payment_desc] Sending raw_text to Bedrock  "
            "raw_text_len=%d  prompt_len=%d",
            len(raw_text), len(raw_prompt),
        )
        result = generate_text(raw_prompt, max_tokens=700, label="payment_desc_raw")
        if result:
            logger.info(
                "[bedrock_utils][payment_desc] raw_text path SUCCESS  output_len=%d",
                len(result),
            )
            return result
        logger.warning("[bedrock_utils][payment_desc] raw_text path returned empty, falling back")

    # Priority 3: structured fallback
    logger.info("[bedrock_utils][payment_desc] Using structured-fields fallback")
    procedure      = extracted_data.get("diagnosis", "Medical Procedure")
    surgery        = extracted_data.get("surgeryType", "Treatment")
    total_bill     = payment.get("totalBillAmount", "N/A")
    patient_pays   = payment.get("amountToBePayed", "N/A")
    claim_approved = claim.get("claimAmountApproved", "N/A") if claim else "N/A"

    user_prompt = (
        "Generate a payment summary in Markdown using this data:\n\n"
        f"Procedure: {procedure}\n"
        f"Surgery / Treatment: {surgery}\n"
        f"Total Bill Amount: {total_bill}\n"
        f"Insurance Covered: {claim_approved}\n"
        f"Patient Payable: {patient_pays}\n\n"
        "Format: start with '## Payment Summary', list each item, end with patient payable."
    )
    try:
        return _converse(
            user_prompt, system_text=_BILLING_SYSTEM,
            max_tokens=600, label="payment_desc_fallback",
        )
    except Exception as exc:
        logger.error(
            "[bedrock_utils][payment_desc_fallback] FAILED -- %s: %s",
            type(exc).__name__, exc,
        )
        return (
            "## Payment Summary\n\n"
            f"- **Procedure:** {procedure}\n"
            f"- **Surgery/Treatment:** {surgery}\n"
            f"- **Total Bill Amount:** {total_bill}\n"
            f"- **Insurance Covered:** {claim_approved}\n"
            f"- **Patient Payable:** {patient_pays}\n"
        )


# ---------------------------------------------------------------------------
# Public: embedding generation  (Titan Embed Text v2 via invoke_model)
# Titan Embed does NOT support the Converse API -- must use invoke_model.
# ---------------------------------------------------------------------------

_EMBED_MAX_CHARS = 25_000


def generate_embedding(text: str) -> list[float]:
    """
    Call Amazon Bedrock Titan Embed Text v2 to produce a 1024-dim dense vector.

    Returns [] on any error so the indexing pipeline is never blocked.
    """
    text = text[:_EMBED_MAX_CHARS]
    body_payload = {
        "inputText":  text,
        "dimensions": 1024,
        "normalize":  True,
    }

    logger.info(
        "[bedrock_utils][embedding] INVOKING invoke_model  model=%s  input_chars=%d",
        EMBEDDING_MODEL_ID, len(text),
    )
    try:
        response = _bedrock.invoke_model(
            modelId     = EMBEDDING_MODEL_ID,
            contentType = "application/json",
            accept      = "application/json",
            body        = json.dumps(body_payload),
        )
        result: dict = json.loads(response["body"].read())
        embedding: list[float] = result["embedding"]
        logger.info(
            "[bedrock_utils][embedding] SUCCESS  dims=%d  input_chars=%d",
            len(embedding), len(text),
        )
        return embedding
    except Exception as exc:
        logger.error(
            "[bedrock_utils][embedding] FAILED -- %s: %s",
            type(exc).__name__, exc,
        )
        return []