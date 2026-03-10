"""
vault_ingest.py — Vault RAG Ingestion Engine for Orbit

Chunks markdown files from /vault/ into a ChromaDB collection
for retrieval-augmented generation by the Wizard.

Usage:
    python vault_ingest.py              # Ingest all vault files
    python vault_ingest.py --full       # Force full re-index (clear + rebuild)
"""

import os
import hashlib
import argparse
import chromadb

VAULT_PATH = os.getenv("VAULT_PATH", os.path.join(os.path.dirname(__file__), "vault"))
DB_PATH = os.path.join(os.path.dirname(__file__), "wizard_memory")

client = chromadb.PersistentClient(path=DB_PATH)
collection = client.get_or_create_collection(
    name="vault_rag",
    metadata={"hnsw:space": "cosine"}
)


def chunk_markdown(content, file_path, max_chunk_size=1500):
    """
    Split markdown content into semantic chunks based on headings.
    Each chunk includes the file source and section heading for context.
    """
    chunks = []
    current_chunk = ""
    current_heading = os.path.basename(file_path).replace(".md", "").replace("_", " ").title()

    for line in content.split("\n"):
        # Detect heading boundaries
        if line.startswith("## ") or line.startswith("# "):
            # Save current chunk if it has content
            if current_chunk.strip():
                chunks.append({
                    "content": current_chunk.strip(),
                    "heading": current_heading,
                    "source": file_path,
                })
            current_heading = line.lstrip("#").strip()
            current_chunk = line + "\n"
        elif len(current_chunk) > max_chunk_size:
            # Force-split long sections
            chunks.append({
                "content": current_chunk.strip(),
                "heading": current_heading,
                "source": file_path,
            })
            current_chunk = line + "\n"
        else:
            current_chunk += line + "\n"

    # Don't forget the last chunk
    if current_chunk.strip():
        chunks.append({
            "content": current_chunk.strip(),
            "heading": current_heading,
            "source": file_path,
        })

    return chunks


def get_vault_files(vault_path):
    """Recursively find all .md files in the vault."""
    md_files = []
    for root, dirs, files in os.walk(vault_path):
        for f in files:
            if f.endswith(".md"):
                md_files.append(os.path.join(root, f))
    return md_files


def compute_hash(content):
    """MD5 hash for content deduplication."""
    return hashlib.md5(content.encode()).hexdigest()


def ingest_vault(full_reindex=False):
    """Main ingestion loop — chunks vault files and upserts into ChromaDB."""

    if full_reindex:
        print("🔄 Full re-index requested. Clearing vault_rag collection...")
        client.delete_collection("vault_rag")
        coll = client.get_or_create_collection(
            name="vault_rag",
            metadata={"hnsw:space": "cosine"}
        )
    else:
        coll = collection

    vault_files = get_vault_files(VAULT_PATH)
    if not vault_files:
        print(f"⚠️  No markdown files found in {VAULT_PATH}")
        return

    total_chunks = 0
    skipped = 0
    upserted = 0

    # Track what's in the vault for orphan cleanup
    active_ids = set()

    for file_path in vault_files:
        rel_path = os.path.relpath(file_path, os.path.dirname(__file__))

        with open(file_path, "r") as f:
            content = f.read()

        chunks = chunk_markdown(content, rel_path)

        for i, chunk in enumerate(chunks):
            chunk_id = compute_hash(f"{rel_path}::{chunk['heading']}::{i}")
            content_hash = compute_hash(chunk["content"])
            active_ids.add(chunk_id)

            # Check if this chunk already exists with the same content hash
            existing = coll.get(ids=[chunk_id], include=["metadatas"])
            if existing and existing["ids"] and not full_reindex:
                existing_meta = existing["metadatas"][0] if existing["metadatas"] else {}
                if existing_meta.get("content_hash") == content_hash:
                    skipped += 1
                    total_chunks += 1
                    continue

            # Determine category from path
            category = "general"
            if "accounts" in rel_path:
                category = "account"
            elif "regulatory" in rel_path:
                category = "regulatory"
            elif "pricing" in rel_path:
                category = "pricing"
            elif "contacts" in rel_path:
                category = "contact"

            coll.upsert(
                documents=[chunk["content"]],
                metadatas=[{
                    "source": rel_path,
                    "heading": chunk["heading"],
                    "category": category,
                    "content_hash": content_hash,
                    "chunk_index": i,
                }],
                ids=[chunk_id],
            )
            upserted += 1
            total_chunks += 1

    # Orphan cleanup — remove documents that no longer exist in the vault
    try:
        all_docs = coll.get(include=["metadatas"])
        if all_docs and all_docs["ids"]:
            orphan_ids = [doc_id for doc_id in all_docs["ids"] if doc_id not in active_ids]
            if orphan_ids:
                coll.delete(ids=orphan_ids)
                print(f"🧹 Cleaned {len(orphan_ids)} orphaned chunks")
    except Exception as e:
        print(f"⚠️  Orphan cleanup failed: {e}")

    print(f"✅ Vault ingestion complete: {total_chunks} chunks total, {upserted} upserted, {skipped} skipped (unchanged)")


def query_vault(query_text, n_results=5, category_filter=None):
    """
    Query the vault collection for relevant context.
    Returns a formatted string suitable for injection into an LLM prompt.
    """
    where = None
    if category_filter:
        where = {"category": category_filter}

    results = collection.query(
        query_texts=[query_text],
        n_results=n_results,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    if not results or not results["documents"] or not results["documents"][0]:
        return "No relevant vault context found."

    context_parts = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        source = meta.get("source", "unknown")
        heading = meta.get("heading", "")
        relevance = f"{(1 - dist) * 100:.0f}%"
        context_parts.append(
            f"--- Source: {source} | Section: {heading} | Relevance: {relevance} ---\n{doc}"
        )

    return "\n\n".join(context_parts)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest vault files into ChromaDB")
    parser.add_argument("--full", action="store_true", help="Force full re-index")
    args = parser.parse_args()

    ingest_vault(full_reindex=args.full)
