"""
pdf_processor/summarizer.py
AI summarization of PDF text.

Supports:
- Google Generative Language API (GOOGLE_API_KEY; Gemini models)
"""
import logging
import time
from typing import Optional

import requests

from config.settings import (
    GOOGLE_API_KEY,
    GOOGLE_MODEL,
    PDF_AI_MAX_CHARS,
    PDF_DEFAULT_AI_PROMPT,
)

log = logging.getLogger(__name__)


def summarize(
    text: str,
    prompt: Optional[str] = None,
    model: str = GOOGLE_MODEL,
    max_tokens: int = 1500,
    api_key: Optional[str] = None,
) -> str:
    """
    Summarize a block of text using Gemini (Google Generative Language API).

    Args:
        text:       Full document text to summarize.
        prompt:     Custom instruction; falls back to default prompt.
        model:      Gemini model identifier.
        max_tokens: Maximum tokens in the generated summary.
        api_key:    If provided, used as the API key. Otherwise uses GOOGLE_API_KEY from env/.env.

    Returns:
        Summary string, or an error notice string if summarization fails.
    """
    instruction = prompt or PDF_DEFAULT_AI_PROMPT

    # Truncate to avoid exceeding context limits
    truncated = text[:PDF_AI_MAX_CHARS]
    if len(text) > PDF_AI_MAX_CHARS:
        log.info(
            f"Text truncated from {len(text):,} to {PDF_AI_MAX_CHARS:,} chars for summarization"
        )

    user_message = f"{instruction}\n\nDocument text:\n{truncated}"

    key = api_key or GOOGLE_API_KEY
    if not key:
        msg = "AI summarization requires GOOGLE_API_KEY. Set it in your environment or .env file."
        log.warning(msg)
        return f"[{msg}]"

    log.info(f"Calling Google model ({model}) for summarization ...")
    return _summarize_google(
        prompt=user_message,
        model=model,
        api_key=key,
        max_tokens=max_tokens,
    )


def _summarize_google(prompt: str, model: str, api_key: str, max_tokens: int) -> str:
    """
    Summarize using Google Generative Language API (Gemini).

    Uses the v1beta REST endpoint (no extra SDK dependencies).
    """
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": 0.2,
        },
    }

    tried = []
    for candidate_model in _model_fallback_chain(model):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{candidate_model}:generateContent"
        for attempt in range(3):
            try:
                resp = requests.post(url, params={"key": api_key}, json=payload, timeout=60)
                resp.raise_for_status()
                data = resp.json()
                parts = (
                    data.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [])
                )
                texts = [p.get("text", "") for p in parts if isinstance(p, dict)]
                summary = "\n".join([t for t in texts if t]).strip()
                if candidate_model != model:
                    log.warning(f"Requested model '{model}' unavailable; used fallback '{candidate_model}'.")
                return summary if summary else str(data)
            except requests.HTTPError as e:
                status = getattr(e.response, "status_code", None)
                tried.append(candidate_model)
                if status == 404:
                    log.warning(f"Model not found: {candidate_model}. Trying fallback model ...")
                    break
                if status == 429 and attempt < 2:
                    wait_s = _retry_after_seconds(getattr(e.response, "headers", {}), attempt)
                    log.warning(f"Rate limited by Google API (429). Retrying in {wait_s}s ...")
                    time.sleep(wait_s)
                    continue
                msg = f"Google summarization error: {e}"
                log.error(msg)
                return f"[{msg}]"
            except Exception as e:
                msg = f"Google summarization error: {e}"
                log.error(msg)
                return f"[{msg}]"

    msg = f"Google summarization error: no available model from {tried}"
    log.error(msg)
    return f"[{msg}]"


def _model_fallback_chain(model: str) -> list[str]:
    """Return model candidates, starting with requested model, without duplicates."""
    candidates = [
        model,
        "gemini-1.5-flash-latest",
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
    ]
    result = []
    seen = set()
    for m in candidates:
        if m and m not in seen:
            seen.add(m)
            result.append(m)
    return result


def _retry_after_seconds(headers: dict, attempt: int) -> int:
    """Compute wait time for 429 retries, honoring Retry-After when available."""
    value = headers.get("Retry-After") if isinstance(headers, dict) else None
    if value:
        try:
            return max(1, int(value))
        except ValueError:
            pass
    return min(8, 2 ** attempt)


def summarize_pages(
    pages: dict,
    prompt: Optional[str] = None,
    model: str = GOOGLE_MODEL,
    max_tokens: int = 1500,
    api_key: Optional[str] = None,
) -> str:
    """
    Summarize a dict of {page_num: text} by concatenating all page text first.

    Args:
        pages: Dict mapping 1-based page number → extracted text.
        (other args same as summarize())

    Returns:
        Summary string.
    """
    full_text = "\n\n".join(
        f"[Page {pg}]\n{text}" for pg, text in sorted(pages.items()) if text.strip()
    )

    if not full_text.strip():
        return "[No text content found to summarize.]"

    return summarize(full_text, prompt=prompt, model=model, max_tokens=max_tokens, api_key=api_key)
