#!/usr/bin/env python3
"""
Quick processing and embedding script for Bronze → Gold pipeline
Runs as ECS Fargate task with VPC access to RDS
"""
import json
import os
import re
import boto3
from bs4 import BeautifulSoup
import psycopg2
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Tuple
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class QuickProcessor:
    """Minimal HTML processor for SEC filings"""
    
    def __init__(self):
        self.s3 = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'ap-south-1'))
    
    def download_from_s3(self, bucket: str, key: str) -> str:
        """Download file from S3"""
        logger.info(f"Downloading s3://{bucket}/{key}")
        response = self.s3.get_object(Bucket=bucket, Key=key)
        return response['Body'].read().decode('utf-8')
    
    def parse_html(self, html_content: str) -> str:
        """Extract clean text from HTML"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(['script', 'style']):
            script.decompose()
        
        # Get text
        text = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return text
    
    def chunk_text(self, text: str, chunk_size: int = 512, overlap: int = 128) -> List[str]:
        """Split text into overlapping chunks"""
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk_words = words[i:i + chunk_size]
            if len(chunk_words) > 50:  # Skip very small chunks
                chunks.append(' '.join(chunk_words))
        
        logger.info(f"Created {len(chunks)} chunks from {len(words)} words")
        return chunks


class VectorDBWriter:
    """Write embeddings to PostgreSQL with pgvector"""
    
    def __init__(self, db_url: str):
        self.conn = psycopg2.connect(db_url)
        self.conn.autocommit = False
        self.embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        logger.info("Initialized embedding model: all-MiniLM-L6-v2")
    
    def ensure_tables(self):
        """Create tables if they don't exist"""
        with self.conn.cursor() as cur:
            # Enable pgvector
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            
            # Documents table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id SERIAL PRIMARY KEY,
                    source_document TEXT NOT NULL,
                    document_type TEXT,
                    company_name TEXT,
                    cik TEXT,
                    form_type TEXT,
                    filing_date DATE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    metadata JSONB
                );
            """)
            
            # Document chunks table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS document_chunks (
                    id SERIAL PRIMARY KEY,
                    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
                    chunk_index INTEGER NOT NULL,
                    chunk_text TEXT NOT NULL,
                    embedding vector(384),
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
            
            # Create index on embeddings for fast similarity search
            cur.execute("""
                CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx 
                ON document_chunks USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100);
            """)
            
            self.conn.commit()
            logger.info("Database tables ensured")
    
    def insert_document(self, metadata: Dict) -> int:
        """Insert document metadata and return ID"""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO documents (
                    source_document, document_type, company_name, 
                    cik, form_type, filing_date, metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (
                metadata.get('accession_number', 'unknown'),
                'sec_filing',
                metadata.get('company_name', 'Unknown'),
                metadata.get('cik', 'unknown'),
                metadata.get('form_type', '10-Q'),
                metadata.get('filing_date'),
                json.dumps(metadata)
            ))
            doc_id = cur.fetchone()[0]
            self.conn.commit()
            logger.info(f"Inserted document ID: {doc_id}")
            return doc_id
    
    def insert_chunks(self, document_id: int, chunks: List[str], metadata: Dict):
        """Generate embeddings and insert chunks"""
        logger.info(f"Generating embeddings for {len(chunks)} chunks...")
        embeddings = self.embedding_model.encode(chunks, show_progress_bar=True)
        
        with self.conn.cursor() as cur:
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                cur.execute("""
                    INSERT INTO document_chunks (
                        document_id, chunk_index, chunk_text, embedding, metadata
                    )
                    VALUES (%s, %s, %s, %s, %s);
                """, (
                    document_id,
                    i,
                    chunk,
                    embedding.tolist(),
                    json.dumps({
                        **metadata,
                        'chunk_index': i,
                        'chunk_length': len(chunk)
                    })
                ))
            
            self.conn.commit()
            logger.info(f"Inserted {len(chunks)} chunks for document {document_id}")
    
    def close(self):
        self.conn.close()


def get_db_url_from_secrets() -> str:
    """Get database URL from AWS Secrets Manager"""
    secret_name = os.environ.get('DB_SECRET_NAME', 'vesper-dev-db-credentials')
    region = os.environ.get('AWS_REGION', 'ap-south-1')
    
    logger.info(f"Fetching DB credentials from {secret_name}")
    client = boto3.client('secretsmanager', region_name=region)
    response = client.get_secret_value(SecretId=secret_name)
    secret = json.loads(response['SecretString'])
    
    db_url = f"postgresql://{secret['username']}:{secret['password']}@{secret['host']}:{secret['port']}/{secret['dbname']}"
    logger.info(f"Connected to database: {secret['host']}")
    return db_url


def process_s3_documents(bucket: str, prefix: str = 'bronze/sec-edgar/'):
    """Process all documents in S3 Bronze layer"""
    processor = QuickProcessor()
    db_url = get_db_url_from_secrets()
    db_writer = VectorDBWriter(db_url)
    
    # Ensure tables exist
    db_writer.ensure_tables()
    
    # List all documents in Bronze
    s3 = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'ap-south-1'))
    paginator = s3.get_paginator('list_objects_v2')
    
    documents_processed = 0
    total_chunks = 0
    
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        if 'Contents' not in page:
            continue
        
        # Group files by document (HTML + metadata pairs)
        documents = {}
        for obj in page['Contents']:
            key = obj['Key']
            if key.endswith('document.html'):
                base_key = key.replace('/document.html', '')
                if base_key not in documents:
                    documents[base_key] = {}
                documents[base_key]['html'] = key
            elif key.endswith('metadata.json'):
                base_key = key.replace('/metadata.json', '')
                if base_key not in documents:
                    documents[base_key] = {}
                documents[base_key]['metadata'] = key
        
        # Process each document
        for base_key, files in documents.items():
            if 'html' not in files:
                logger.warning(f"Skipping {base_key} - no HTML file")
                continue
            
            try:
                logger.info(f"\n{'='*60}")
                logger.info(f"Processing: {base_key}")
                logger.info(f"{'='*60}")
                
                # Download HTML
                html_content = processor.download_from_s3(bucket, files['html'])
                
                # Download metadata if exists
                metadata = {}
                if 'metadata' in files:
                    metadata_json = processor.download_from_s3(bucket, files['metadata'])
                    metadata = json.loads(metadata_json)
                
                # Parse HTML
                text = processor.parse_html(html_content)
                logger.info(f"Extracted {len(text)} characters")
                
                # Chunk text
                chunks = processor.chunk_text(text, chunk_size=512, overlap=128)
                
                # Insert into database
                doc_id = db_writer.insert_document(metadata)
                db_writer.insert_chunks(doc_id, chunks, metadata)
                
                documents_processed += 1
                total_chunks += len(chunks)
                
                logger.info(f"✅ Completed document {documents_processed}")
                
            except Exception as e:
                logger.error(f"❌ Error processing {base_key}: {e}", exc_info=True)
                continue
    
    db_writer.close()
    
    logger.info(f"\n{'='*60}")
    logger.info(f"PROCESSING COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Documents processed: {documents_processed}")
    logger.info(f"Total chunks: {total_chunks}")
    logger.info(f"Average chunks per document: {total_chunks / documents_processed if documents_processed > 0 else 0:.1f}")


if __name__ == '__main__':
    import sys
    
    bucket = sys.argv[1] if len(sys.argv) > 1 else 'vesper-dev-bronze'
    prefix = sys.argv[2] if len(sys.argv) > 2 else 'bronze/sec-edgar/'
    
    logger.info(f"Starting processing pipeline")
    logger.info(f"Bucket: {bucket}")
    logger.info(f"Prefix: {prefix}")
    
    process_s3_documents(bucket, prefix)
