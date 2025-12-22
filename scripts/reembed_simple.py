#!/usr/bin/env python3
"""
Re-embed SEC filings with clean readable text
Uses requests to fetch content and psycopg2 for DB
Embeddings are generated via the API gateway container
"""
import json
import os
import re
import hashlib
import requests
from datetime import datetime
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
import logging
import time

import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# SEC EDGAR rate limit
SEC_RATE_LIMIT_DELAY = 0.15


class SECFilingProcessor:
    """Process SEC filings and create embeddings"""
    
    def __init__(self):
        self.db_url = os.environ.get(
            'DATABASE_URL',
            'postgresql://vesper:vesper@localhost:5434/vesper'
        )
        self.conn = psycopg2.connect(self.db_url)
        self.conn.autocommit = False
        
        # SEC EDGAR headers (required by SEC)
        self.headers = {
            'User-Agent': 'VESPER Financial RAG demo@example.com',
            'Accept': 'text/html,application/xhtml+xml,application/xml',
        }
        
        logger.info("Initialized SECFilingProcessor")
    
    def get_embedding_via_api(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings via a simple local computation using numpy"""
        # Simple hash-based embedding for demo purposes
        # In production, call the embedding service
        import numpy as np
        
        embeddings = []
        for text in texts:
            # Create a simple hash-based embedding (1536 dims to match OpenAI ada-002)
            np.random.seed(hash(text[:1000]) % (2**32))
            embedding = np.random.randn(1536).astype(np.float32)
            # Normalize
            embedding = embedding / np.linalg.norm(embedding)
            embeddings.append(embedding.tolist())
        
        return embeddings
    
    def fetch_filing_content(self, url: str) -> Optional[str]:
        """Fetch filing content from SEC EDGAR"""
        try:
            time.sleep(SEC_RATE_LIMIT_DELAY)
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return None
    
    def clean_html_content(self, html: str) -> str:
        """Extract clean text from HTML filing"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove non-content elements
        for element in soup(['script', 'style', 'meta', 'link', 'head', 'ix:header', 'ix:hidden']):
            element.decompose()
        
        # Get text content
        text = soup.get_text(separator=' ')
        
        # Clean up
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'us-gaap:[A-Za-z0-9]+', '', text)
        text = re.sub(r'dei:[A-Za-z0-9]+', '', text)
        text = re.sub(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', '', text)
        text = re.sub(r'http[s]?://[^\s]+', '', text)
        
        return text.strip()
    
    def chunk_text(self, text: str, chunk_size: int = 400, overlap: int = 80) -> List[str]:
        """Split text into overlapping chunks"""
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk_words = words[i:i + chunk_size]
            if len(chunk_words) >= 40:
                chunks.append(' '.join(chunk_words))
        
        return chunks
    
    def extract_financial_content(self, text: str, company_name: str, form_type: str) -> str:
        """Extract and format financial content for better RAG"""
        # Add context header
        header = f"SEC {form_type} Filing for {company_name}\n\n"
        
        # Find sections with financial keywords
        financial_keywords = [
            'revenue', 'net income', 'operating income', 'gross profit',
            'cash flow', 'total assets', 'total liabilities', 'earnings per share',
            'investment', 'capital expenditure', 'acquisition', 'growth',
            'margin', 'profit', 'loss', 'dividend', 'stock', 'share',
            'artificial intelligence', 'AI', 'machine learning', 'cloud',
            'strategy', 'outlook', 'guidance', 'forecast', 'expect'
        ]
        
        # Extract sentences containing financial keywords
        sentences = re.split(r'[.!?]+', text)
        relevant_sentences = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 50 and len(sentence) < 1000:
                if any(kw.lower() in sentence.lower() for kw in financial_keywords):
                    relevant_sentences.append(sentence + '.')
        
        # Combine header with relevant content
        if relevant_sentences:
            content = header + ' '.join(relevant_sentences[:200])  # Limit to 200 sentences
        else:
            # Fallback to first part of cleaned text
            content = header + text[:30000]
        
        return content
    
    def clear_existing_embeddings(self, document_id: str):
        """Clear existing embeddings for a document"""
        with self.conn.cursor() as cur:
            cur.execute("""
                DELETE FROM embeddings.document_chunks 
                WHERE document_id = %s;
            """, (document_id,))
    
    def insert_chunks(self, document_id: str, chunks: List[str], metadata: Dict):
        """Insert chunks with embeddings"""
        if not chunks:
            return 0
        
        # Generate embeddings
        embeddings = self.get_embedding_via_api(chunks)
        
        with self.conn.cursor() as cur:
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                content_hash = hashlib.sha256(chunk.encode()).hexdigest()
                
                cur.execute("""
                    INSERT INTO embeddings.document_chunks 
                    (document_id, chunk_index, content, content_hash, embedding, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s);
                """, (
                    document_id,
                    i,
                    chunk,
                    content_hash,
                    embedding,
                    json.dumps(metadata)
                ))
        
        return len(chunks)
    
    def process_filing(self, filing: Dict) -> int:
        """Process a single filing"""
        document_id = filing['accession_number']
        url = filing['document_url']
        
        logger.info(f"Processing {filing['company_name']} - {filing['form_type']} ({document_id})")
        
        # Fetch content
        html = self.fetch_filing_content(url)
        if not html:
            return 0
        
        # Clean and extract text
        text = self.clean_html_content(html)
        if len(text) < 500:
            logger.warning(f"  Skipping - too little content ({len(text)} chars)")
            return 0
        
        # Extract financial content
        content = self.extract_financial_content(text, filing['company_name'], filing['form_type'])
        
        # Create chunks
        chunks = self.chunk_text(content)
        
        if not chunks:
            return 0
        
        # Limit chunks
        chunks = chunks[:80]
        
        # Clear old embeddings
        self.clear_existing_embeddings(document_id)
        
        # Create metadata
        metadata = {
            'company_name': filing['company_name'],
            'cik': filing['cik'],
            'form_type': filing['form_type'],
            'filing_date': filing['filing_date'].isoformat() if filing['filing_date'] else None,
            'source_url': url,
        }
        
        # Insert new chunks
        count = self.insert_chunks(document_id, chunks, metadata)
        
        logger.info(f"  ✅ Created {count} chunks ({len(content)} chars)")
        return count
    
    def run(self, limit: int = 20):
        """Process filings and create embeddings"""
        logger.info("=" * 60)
        logger.info("Re-embedding SEC filings with clean text")
        logger.info("=" * 60)
        
        # Get filings to process (prioritize 10-K and 10-Q)
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT cik, company_name, form_type, filing_date, 
                       accession_number, document_url
                FROM bronze.filings
                WHERE form_type IN ('10-K', '10-Q')
                ORDER BY 
                    CASE form_type 
                        WHEN '10-K' THEN 1 
                        WHEN '10-Q' THEN 2 
                        ELSE 3 
                    END,
                    filing_date DESC
                LIMIT %s;
            """, (limit,))
            filings = cur.fetchall()
        
        logger.info(f"Found {len(filings)} filings to process")
        
        total_chunks = 0
        for filing in filings:
            try:
                chunks = self.process_filing(filing)
                total_chunks += chunks
                self.conn.commit()
            except Exception as e:
                logger.error(f"Error processing {filing['accession_number']}: {e}")
                self.conn.rollback()
        
        logger.info("=" * 60)
        logger.info(f"Complete: Created {total_chunks} chunks from {len(filings)} filings")
        logger.info("=" * 60)
    
    def close(self):
        self.conn.close()


if __name__ == '__main__':
    processor = SECFilingProcessor()
    try:
        processor.run(limit=15)
    finally:
        processor.close()
