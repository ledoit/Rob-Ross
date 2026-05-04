"""Ingestion pipeline for heterogeneous taste sources."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from rich.console import Console

console = Console()


@dataclass
class PrincipleChunk:
    source_id: str
    principle: str
    evidence: str
    confidence: float
    tags: list[str]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_url(value: str) -> bool:
    parsed = urlparse(value)
    return bool(parsed.scheme and parsed.netloc)


def _extract_hex_colors(text: str) -> list[str]:
    return sorted(set(m.group(0).upper() for m in re.finditer(r"#[0-9A-Fa-f]{6}", text)))


def _read_source_content(source: str) -> tuple[str, str]:
    if _is_url(source):
        return source, f"URL_SOURCE:{source}"
    p = Path(source)
    if not p.exists():
        raise FileNotFoundError(f"Source does not exist: {source}")
    text = p.read_text(encoding="utf-8", errors="ignore")
    return p.name, text


def _llm_extract_principles(source_id: str, content: str) -> list[PrincipleChunk]:
    """Use Ollama through LlamaIndex where available, fallback to rule-based extraction."""
    try:
        from llama_index.llms.ollama import Ollama
    except Exception:
        return _heuristic_extract_principles(source_id, content)

    model_name = os.getenv("ROBROSS_OLLAMA_MODEL", "mistral")
    prompt = f"""
You are a design systems analyst.
Extract structural color-design principles from this source.
Return STRICT JSON array with objects:
source_id, principle, evidence, confidence (0-1), tags (string list).

Source ID: {source_id}
Content:
{content[:7000]}
"""
    try:
        llm = Ollama(model=model_name, request_timeout=120.0)
        raw = llm.complete(prompt).text.strip()
        data = json.loads(raw)
        chunks: list[PrincipleChunk] = []
        for item in data:
            chunks.append(
                PrincipleChunk(
                    source_id=item.get("source_id", source_id),
                    principle=str(item.get("principle", "")).strip(),
                    evidence=str(item.get("evidence", "")).strip(),
                    confidence=float(item.get("confidence", 0.5)),
                    tags=list(item.get("tags", [])),
                )
            )
        return [c for c in chunks if c.principle]
    except Exception:
        return _heuristic_extract_principles(source_id, content)


def _heuristic_extract_principles(source_id: str, content: str) -> list[PrincipleChunk]:
    hexes = _extract_hex_colors(content)
    principles: list[PrincipleChunk] = []
    if hexes:
        principles.append(
            PrincipleChunk(
                source_id=source_id,
                principle="Source expresses explicit color set with likely intentional role hierarchy.",
                evidence=f"Found {len(hexes)} hex colors: {', '.join(hexes[:8])}",
                confidence=0.74,
                tags=["palette", "hex", "source_direct"],
            )
        )
    lowered = content.lower()
    if "contrast" in lowered:
        principles.append(
            PrincipleChunk(
                source_id=source_id,
                principle="Readability/contrast is explicitly considered in this source.",
                evidence="Detected repeated mention of contrast-oriented language.",
                confidence=0.67,
                tags=["contrast", "readability"],
            )
        )
    if "dark" in lowered:
        principles.append(
            PrincipleChunk(
                source_id=source_id,
                principle="Dark-background preference appears central.",
                evidence="Detected dark/nocturnal language.",
                confidence=0.63,
                tags=["dark_mode", "mood"],
            )
        )
    if not principles:
        principles.append(
            PrincipleChunk(
                source_id=source_id,
                principle="General aesthetic guidance detected; classify manually during review.",
                evidence="No strong structural markers auto-detected.",
                confidence=0.40,
                tags=["review_required"],
            )
        )
    return principles


def _persist_processed_chunks(chunks: list[PrincipleChunk], processed_dir: Path) -> Path:
    processed_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = processed_dir / f"principles_{ts}.json"
    with out.open("w", encoding="utf-8") as f:
        json.dump([c.__dict__ for c in chunks], f, indent=2)
    return out


def _index_chunks_chroma(chunks: list[PrincipleChunk], vector_dir: Path) -> None:
    """Persist principle chunks to Chroma vector store via LlamaIndex."""
    try:
        import chromadb
        from llama_index.core import StorageContext, VectorStoreIndex
        from llama_index.core.schema import Document
        from llama_index.embeddings.huggingface import HuggingFaceEmbedding
        from llama_index.vector_stores.chroma import ChromaVectorStore
    except Exception as exc:
        console.print(f"[yellow]Skipping vector index (missing deps): {exc}[/yellow]")
        return

    vector_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(vector_dir))
    collection = client.get_or_create_collection("robross_principles")
    vector_store = ChromaVectorStore(chroma_collection=collection)
    embed_model = HuggingFaceEmbedding(model_name=os.getenv("ROBROSS_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"))

    docs = [
        Document(
            text=f"{c.principle}\nEvidence: {c.evidence}",
            metadata={"source_id": c.source_id, "confidence": c.confidence, "tags": ",".join(c.tags)},
        )
        for c in chunks
    ]
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    VectorStoreIndex.from_documents(docs, storage_context=storage_context, embed_model=embed_model)


def ingest_source(source: str, base_dir: str | Path) -> dict[str, Any]:
    base = Path(base_dir)
    processed_dir = base / "sources" / "processed"
    vector_dir = base / "vector_store"

    source_id, content = _read_source_content(source)
    chunks = _llm_extract_principles(source_id, content)
    processed_file = _persist_processed_chunks(chunks, processed_dir)
    _index_chunks_chroma(chunks, vector_dir)

    return {
        "source_id": source_id,
        "ingested_at": _iso_now(),
        "principles_extracted": len(chunks),
        "processed_file": str(processed_file),
        "principles": [c.__dict__ for c in chunks],
    }
