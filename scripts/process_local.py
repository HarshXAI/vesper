#!/usr/bin/env python3
"""
Local document processing and embedding pipeline.
Processes SEC filings from MinIO, chunks text, generates embeddings, and stores in PostgreSQL.
"""

import os
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any
import numpy as np
import psycopg2
from psycopg2.extras import execute_batch
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
import boto3
from botocore.client import Config

# Configuration
MINIO_ENDPOINT = "http://minio:9000"  # Use service name when running in Docker
MINIO_ACCESS_KEY = "minioadminio"
MINIO_SECRET_KEY = "minioadmin"
BUCKET_BRONZE = "vesper-bronze"

DB_CONFIG = {
    "host": "postgres",  # Use service name when running in Docker
    "port": 5432,  # Internal port, not mapped port
    "database": "vesper",
    "user": "vesper",
    "password": "vesper"
}

CHUNK_SIZE = 512  # tokens
CHUNK_OVERLAP = 128  # tokens
EMBEDDING_MODEL = "sentence-transformers/all-mpnet-base-v2"  # 768 dimensions (closer to 1536)


class LocalProcessor:
    """Processes documents from MinIO and embeds them into PostgreSQL"""
    
    def __init__(self):
        print("🚀 Initializing LocalProcessor...")
        
        # Initialize MinIO client
        print("  Connecting to MinIO...")
        self.s3 = boto3.client(
            's3',
            endpoint_url=MINIO_ENDPOINT,
            aws_access_key_id=MINIO_ACCESS_KEY,
            aws_secret_access_key=MINIO_SECRET_KEY,
            config=Config(signature_version='s3v4'),
            region_name='us-east-1'
        )
        
        # Initialize embedding model
        print(f"  Loading embedding model: {EMBEDDING_MODEL}...")
        self.model = SentenceTransformer(EMBEDDING_MODEL)
        print(f"  Model loaded! Embedding dimension: {self.model.get_sentence_embedding_dimension()}")
        
        # Connect to PostgreSQL
        print("  Connecting to PostgreSQL...")
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.conn.autocommit = False
        print("  ✅ Initialization complete!")
    
    def list_documents(self, prefix: str = "bronze/sec-edgar/") -> List[str]:
        """List all documents in MinIO"""
        print(f"\n📂 Listing documents in s3://{BUCKET_BRONZE}/{prefix}")
        
        response = self.s3.list_objects_v2(Bucket=BUCKET_BRONZE, Prefix=prefix)
        
        # Group by directory (each filing has document.html + metadata.json)
        filings = {}
        for obj in response.get('Contents', []):
            key = obj['Key']
            if 'document.html' in key or 'metadata.json' in key:
                # Extract filing directory
                parts = key.split('/')
                if len(parts) >= 5:  # bronze/sec-edgar/CIK/FORM/ACCESSION/file
                    filing_dir = '/'.join(parts[:5])
                    if filing_dir not in filings:
                        filings[filing_dir] = {}
                    
                    if 'document.html' in key:
                        filings[filing_dir]['html'] = key
                    elif 'metadata.json' in key:
                        filings[filing_dir]['metadata'] = key
        
        # Filter complete filings (have both files)
        complete_filings = [
            f for f, files in filings.items() 
            if 'html' in files and 'metadata' in files
        ]
        
        print(f"  Found {len(complete_filings)} complete filings")
        return complete_filings
    
    def download_filing(self, filing_dir: str) -> tuple[str, dict]:
        """Download HTML and metadata for a filing"""
        html_key = f"{filing_dir}/document.html"
        metadata_key = f"{filing_dir}/metadata.json"
        
        # Download HTML
        html_obj = self.s3.get_object(Bucket=BUCKET_BRONZE, Key=html_key)
        html_content = html_obj['Body'].read().decode('utf-8')
        
        # Download metadata
        metadata_obj = self.s3.get_object(Bucket=BUCKET_BRONZE, Key=metadata_key)
        metadata = json.loads(metadata_obj['Body'].read().decode('utf-8'))
        
        return html_content, metadata
    
    def extract_text(self, html: str) -> str:
        """Extract clean text from HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove script and style tags
        for tag in soup(['script', 'style', 'meta', 'link']):
            tag.decompose()
        
        # Get text
        text = soup.get_text(separator=' ', strip=True)
        
        # Clean up whitespace
        text = ' '.join(text.split())
        
        return text
    
    def chunk_text(self, text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
        """Chunk text into overlapping segments"""
        # Simple word-based chunking (approximating tokens)
        words = text.split()
        chunks = []
        
        i = 0
        while i < len(words):
            chunk_words = words[i:i + chunk_size]
            chunk = ' '.join(chunk_words)
            
            if chunk:
                chunks.append(chunk)
            
            # Move forward by (chunk_size - overlap)
            i += (chunk_size - overlap)
            
            # Prevent infinite loop if overlap >= chunk_size
            if overlap >= chunk_size:
                i += 1
        
        return chunks
    
    def embed_chunks(self, chunks: List[str]) -> List[List[float]]:
        """Generate embeddings for chunks"""
        embeddings = self.model.encode(chunks, show_progress_bar=True, convert_to_numpy=True)
        return embeddings.tolist()
    
    def store_document(self, metadata: dict, chunks: List[str], embeddings: List[List[float]], s3_path: str):
        """Store document and embeddings in PostgreSQL"""
        cur = self.conn.cursor()
        
        try:
            # Use accession_number as document_id
            document_id = metadata['accession_number']
            
            # Check if document already exists
            cur.execute(
                "SELECT COUNT(*) FROM embeddings.document_chunks WHERE document_id = %s",
                (document_id,)
            )
            count = cur.fetchone()[0]
            
            if count > 0:
                print(f"    ⚠️  Document {document_id} already exists ({count} chunks), skipping...")
                return
            
            # Pad embeddings to 1536 dimensions if needed
            target_dim = 1536
            padded_embeddings = []
            for emb in embeddings:
                emb_array = np.array(emb)
                if len(emb_array) < target_dim:
                    # Pad with zeros
                    padded = np.pad(emb_array, (0, target_dim - len(emb_array)), mode='constant')
                else:
                    padded = emb_array[:target_dim]  # Truncate if larger
                padded_embeddings.append(padded.tolist())
            
            # Batch insert chunks with embeddings (document_id instead of source_id)
            chunk_data = [
                (
                    document_id,
                    i,
                    chunk,
                    hashlib.sha256(chunk.encode('utf-8')).hexdigest(),  # content_hash
                    padded_emb,
                    json.dumps({
                        "chunk_index": i,
                        "chunk_size": len(chunk.split()),
                        "company_name": metadata.get('company_name'),
                        "form_type": metadata.get('form_type'),
                        "filing_date": metadata.get('filing_date'),
                        "s3_path": s3_path
                    })
                )
                for i, (chunk, padded_emb) in enumerate(zip(chunks, padded_embeddings))
            ]
            
            execute_batch(
                cur,
                """
                INSERT INTO embeddings.document_chunks (
                    document_id, chunk_index, content, content_hash, embedding, metadata, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """,
                chunk_data,
                page_size=100
            )
            
            self.conn.commit()
            print(f"    ✅ Stored {len(chunks)} chunks for {metadata['company_name']}")
            
        except Exception as e:
            self.conn.rollback()
            print(f"    ❌ Error storing document: {e}")
            raise
        finally:
            cur.close()
    
    def process_all(self):
        """Process all documents in MinIO"""
        print("\n" + "="*80)
        print("🔄 Starting document processing pipeline")
        print("="*80)
        
        filings = self.list_documents()
        
        for i, filing_dir in enumerate(filings, 1):
            print(f"\n[{i}/{len(filings)}] Processing: {filing_dir}")
            
            try:
                # Download
                print(f"  📥 Downloading...")
                html, metadata = self.download_filing(filing_dir)
                print(f"    Company: {metadata['company_name']}")
                print(f"    Form: {metadata['form_type']}")
                print(f"    Date: {metadata['filing_date']}")
                print(f"    HTML size: {len(html):,} chars")
                
                # Extract text
                print(f"  📝 Extracting text...")
                text = self.extract_text(html)
                print(f"    Extracted: {len(text):,} chars, {len(text.split()):,} words")
                
                # Chunk
                print(f"  ✂️  Chunking text...")
                chunks = self.chunk_text(text)
                print(f"    Created: {len(chunks)} chunks")
                
                if len(chunks) == 0:
                    print(f"    ⚠️  No chunks created, skipping...")
                    continue
                
                # Embed
                print(f"  🧠 Generating embeddings...")
                embeddings = self.embed_chunks(chunks)
                print(f"    Generated: {len(embeddings)} embeddings x {len(embeddings[0])} dimensions")
                
                # Store
                print(f"  💾 Storing in database...")
                s3_path = f"s3://{BUCKET_BRONZE}/{filing_dir}"
                self.store_document(metadata, chunks, embeddings, s3_path)
                
            except Exception as e:
                print(f"  ❌ Failed: {e}")
                import traceback
                traceback.print_exc()
        
        # Print summary
        print("\n" + "="*80)
        print("📊 Processing Complete! Summary:")
        print("="*80)
        
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM sources WHERE source_type = 'sec_filing'")
        doc_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM embeddings.document_chunks")
        chunk_count = cur.fetchone()[0]
        
        cur.execute("""
            SELECT COUNT(*) 
            FROM embeddings.document_chunks 
            WHERE embedding IS NOT NULL
        """)
        embedded_count = cur.fetchone()[0]
        
        print(f"  📄 Documents: {doc_count}")
        print(f"  📦 Total chunks: {chunk_count}")
        print(f"  🧠 Embedded chunks: {embedded_count}")
        print(f"  ✅ Pipeline success rate: {embedded_count/chunk_count*100:.1f}%")
        
        cur.close()
    
    def close(self):
        """Close connections"""
        self.conn.close()
        print("\n👋 Connections closed")


if __name__ == "__main__":
    processor = LocalProcessor()
    try:
        processor.process_all()
    finally:
        processor.close()
