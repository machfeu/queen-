"""
llm_client.py — Client LLM abstrait pour Queen V1.
Supporte Ollama (par défaut) et OpenAI-compatible APIs.
Aucune clé API hardcodée — tout via variables d'environnement.
"""

import json
import logging
import os
import time
from typing import Optional, Dict, Any

import requests

logger = logging.getLogger("queen.llm")

# ─── Configuration ────────────────────────────────────────────────────────────

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")  # "ollama" | "openai"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
# API key read at call time, never logged
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "120"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))


def _get_api_key() -> str:
    """Read API key from env at call time."""
    return os.getenv("OPENAI_API_KEY", "")


def generate(prompt: str, system: str = "", temperature: float = 0.7,
             max_tokens: int = 2048, json_mode: bool = False) -> str:
    """
    Generate text from LLM. Returns raw text string.
    Raises RuntimeError on persistent failure.
    """
    for attempt in range(LLM_MAX_RETRIES + 1):
        try:
            if LLM_PROVIDER == "ollama":
                return _ollama_generate(prompt, system, temperature, max_tokens, json_mode)
            else:
                return _openai_generate(prompt, system, temperature, max_tokens, json_mode)
        except Exception as e:
            logger.warning(f"LLM attempt {attempt + 1} failed: {e}")
            if attempt < LLM_MAX_RETRIES:
                time.sleep(2 ** attempt)
            else:
                raise RuntimeError(f"LLM failed after {LLM_MAX_RETRIES + 1} attempts: {e}")


def generate_json(prompt: str, system: str = "", temperature: float = 0.3,
                  max_tokens: int = 4096) -> Dict[str, Any]:
    """Generate and parse JSON from LLM."""
    raw = generate(prompt, system=system, temperature=temperature,
                   max_tokens=max_tokens, json_mode=True)
    # Try to extract JSON from response
    raw = raw.strip()
    if raw.startswith("```"):
        # Strip markdown code fences
        lines = raw.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw = "\n".join(lines)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try to find JSON object in text
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
        raise ValueError(f"Could not parse JSON from LLM response: {raw[:200]}")


# ─── Ollama Backend ──────────────────────────────────────────────────────────

def _ollama_generate(prompt: str, system: str, temperature: float,
                     max_tokens: int, json_mode: bool) -> str:
    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    if system:
        payload["system"] = system
    if json_mode:
        payload["format"] = "json"

    resp = requests.post(url, json=payload, timeout=LLM_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    return data.get("response", "")


# ─── OpenAI-Compatible Backend ───────────────────────────────────────────────

def _openai_generate(prompt: str, system: str, temperature: float,
                     max_tokens: int, json_mode: bool) -> str:
    url = f"{OPENAI_BASE_URL}/chat/completions"
    headers = {"Content-Type": "application/json"}
    api_key = _get_api_key()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": OPENAI_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    resp = requests.post(url, json=payload, headers=headers, timeout=LLM_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def health_check() -> Dict[str, Any]:
    """Check LLM availability."""
    try:
        if LLM_PROVIDER == "ollama":
            resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            return {"status": "ok", "provider": "ollama", "models": models}
        else:
            return {"status": "ok", "provider": "openai", "model": OPENAI_MODEL}
    except Exception as e:
        return {"status": "error", "provider": LLM_PROVIDER, "error": str(e)}
