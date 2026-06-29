"""
Script de ingesta: procesa los PDFs de knowledge_base,
los divide en chunks y los indexa en Qdrant via la API de n8n.

Parámetros alineados con la Guia de Ingeniería Back-end de Santo Pegasus:
  - Chunk size:  512 tokens
  - Overlap:     50 tokens
  - K retrieval: 4
  - Embeddings:  text-embedding-3-small (OpenAI)
"""

import os
import sys
import json
import uuid
import requests
import pdfplumber
from pathlib import Path

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = os.getenv("QDRANT_PORT", "6333")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
COLLECTION_NAME = "santo_pegasus_kb"
CHUNK_SIZE = 512
CHUNK_OVERLAP = 50
EMBEDDING_MODEL = "text-embedding-3-small"
KNOWLEDGE_BASE_PATH = Path(__file__).parent.parent / "knowledge_base"


def extract_text_from_pdf(pdf_path: Path) -> str:
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def get_embedding(text: str) -> list[float]:
    response = requests.post(
        "https://api.openai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        json={"input": text, "model": EMBEDDING_MODEL},
    )
    response.raise_for_status()
    return response.json()["data"][0]["embedding"]


def create_qdrant_collection(vector_size: int = 1536):
    url = f"http://{QDRANT_HOST}:{QDRANT_PORT}/collections/{COLLECTION_NAME}"
    payload = {
        "vectors": {
            "size": vector_size,
            "distance": "Cosine",
        }
    }
    r = requests.put(url, json=payload)
    if r.status_code not in (200, 409):
        r.raise_for_status()
    print(f"Colección '{COLLECTION_NAME}' lista.")


def upsert_points(points: list[dict]):
    url = f"http://{QDRANT_HOST}:{QDRANT_PORT}/collections/{COLLECTION_NAME}/points"
    r = requests.put(url, json={"points": points})
    r.raise_for_status()


def ingest():
    if not OPENAI_API_KEY:
        sys.exit("ERROR: OPENAI_API_KEY no configurada.")

    pdfs = list(KNOWLEDGE_BASE_PATH.glob("*.pdf"))
    if not pdfs:
        sys.exit(f"No se encontraron PDFs en {KNOWLEDGE_BASE_PATH}")

    create_qdrant_collection()

    for pdf_path in pdfs:
        print(f"Procesando: {pdf_path.name}")
        text = extract_text_from_pdf(pdf_path)
        chunks = chunk_text(text)
        print(f"  {len(chunks)} chunks generados")

        points = []
        for i, chunk in enumerate(chunks):
            embedding = get_embedding(chunk)
            points.append({
                "id": str(uuid.uuid4()),
                "vector": embedding,
                "payload": {
                    "source": pdf_path.name,
                    "chunk_index": i,
                    "text": chunk,
                },
            })

        upsert_points(points)
        print(f"  {len(points)} vectores indexados en Qdrant")

    print("\nIngesta completa.")


if __name__ == "__main__":
    ingest()
