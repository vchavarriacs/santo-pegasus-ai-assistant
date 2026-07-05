"""
Script de ingesta: procesa los PDFs de knowledge_base,
los divide en chunks y los indexa en Qdrant.

Parámetros alineados con la Guia de Ingeniería Back-end de Santo Pegasus:
  - Chunk size:  512 tokens (aprox. por palabras)
  - Overlap:     50 tokens
  - K retrieval: 4
  - Embeddings:  Cohere embed-multilingual-v3.0 (1024 dims)
"""

import os
import sys
import uuid
import requests
import pdfplumber
from pathlib import Path

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = os.getenv("QDRANT_PORT", "6333")
COHERE_API_KEY = os.getenv("COHERE_API_KEY")
COLLECTION_NAME = "santo_pegasus_kb"
CHUNK_SIZE = 512
CHUNK_OVERLAP = 50
EMBEDDING_MODEL = "embed-multilingual-v3.0"
VECTOR_SIZE = 1024
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
        chunks.append(" ".join(words[start:end]))
        start += chunk_size - overlap
    return chunks


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Llama a la API de Cohere en batches de 96 (límite del trial)."""
    all_embeddings = []
    batch_size = 96
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        response = requests.post(
            "https://api.cohere.com/v1/embed",
            headers={
                "Authorization": f"Bearer {COHERE_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "texts": batch,
                "model": EMBEDDING_MODEL,
                "input_type": "search_document",
            },
        )
        response.raise_for_status()
        all_embeddings.extend(response.json()["embeddings"])
        print(f"  Batch {i // batch_size + 1}: {len(batch)} embeddings generados")
    return all_embeddings


def create_qdrant_collection():
    url = f"http://{QDRANT_HOST}:{QDRANT_PORT}/collections/{COLLECTION_NAME}"
    # Eliminar colección si ya existe para re-indexar limpio
    requests.delete(url)
    payload = {
        "vectors": {
            "size": VECTOR_SIZE,
            "distance": "Cosine",
        }
    }
    r = requests.put(url, json=payload)
    r.raise_for_status()
    print(f"Colección '{COLLECTION_NAME}' creada ({VECTOR_SIZE} dims, Cosine).")


def upsert_points(points: list[dict]):
    url = f"http://{QDRANT_HOST}:{QDRANT_PORT}/collections/{COLLECTION_NAME}/points"
    r = requests.put(url, json={"points": points})
    r.raise_for_status()


def ingest():
    if not COHERE_API_KEY:
        sys.exit("ERROR: COHERE_API_KEY no configurada. Ejecuta: set COHERE_API_KEY=tu-key")

    pdfs = sorted(KNOWLEDGE_BASE_PATH.glob("*.pdf"))
    if not pdfs:
        sys.exit(f"No se encontraron PDFs en {KNOWLEDGE_BASE_PATH}")

    create_qdrant_collection()
    total_chunks = 0

    for pdf_path in pdfs:
        print(f"\nProcesando: {pdf_path.name}")
        text = extract_text_from_pdf(pdf_path)
        chunks = chunk_text(text)
        print(f"  {len(chunks)} chunks generados")

        embeddings = get_embeddings(chunks)

        points = [
            {
                "id": str(uuid.uuid4()),
                "vector": embedding,
                "payload": {
                    "source": pdf_path.name,
                    "chunk_index": i,
                    "text": chunk,
                },
            }
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
        ]

        upsert_points(points)
        total_chunks += len(points)
        print(f"  {len(points)} vectores indexados en Qdrant")

    print(f"\nIngesta completa. Total: {total_chunks} chunks en '{COLLECTION_NAME}'.")


if __name__ == "__main__":
    ingest()
