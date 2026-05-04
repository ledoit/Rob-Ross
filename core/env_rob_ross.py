"""Environment variable names: prefer ROB_ROSS_*, accept legacy ROBROSS_*."""

from __future__ import annotations

import os


def _get(primary: str, legacy: str, default: str) -> str:
    return os.getenv(primary) or os.getenv(legacy, default)


def ollama_model() -> str:
    return _get("ROB_ROSS_OLLAMA_MODEL", "ROBROSS_OLLAMA_MODEL", "mistral")


def embed_model_name() -> str:
    return _get(
        "ROB_ROSS_EMBED_MODEL",
        "ROBROSS_EMBED_MODEL",
        "sentence-transformers/all-MiniLM-L6-v2",
    )


def use_llm_rationale() -> bool:
    v = _get("ROB_ROSS_USE_LLM_RATIONALE", "ROBROSS_USE_LLM_RATIONALE", "0")
    return v.strip().lower() in {"1", "true", "yes"}
