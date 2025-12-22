#!/usr/bin/env python3
"""
Re-embed SEC filings with clean readable text
Fetches actual content from SEC EDGAR and creates proper embeddings
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
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# SEC EDGAR rate limit: 10 requests per second
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
        
        # Use a good embedding model
        logger.info("Loading embedding model...")
        self.model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
        self.embedding_dim = 768
        logger.info(f"Loaded model with {self.embedding_dim} dimensions")
        
        # SEC EDGAR headers (required by SEC)
        self.headers = {
            'User-Agent': 'VESPER Financial RAG demo@example.com',
            'Accept': 'text/html,application/xhtml+xml,application/xml',
        }
    
    def fetch_filing_content(self, url: str) -> Optional[str]:
        """Fetch filing content from SEC EDGAR"""
        try:
            time.sleep(SEC_RATE_LIMIT_DELAY)  # Rate limiting
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return None
    
    def clean_html_content(self, html: str) -> str:
        """Extract clean text from HTML filing"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove script, style, and other non-content elements
        for element in soup(['script', 'style', 'meta', 'link', 'head']):
            element.decompose()
        
        # Get text content
        text = soup.get_text(separator=' ')
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        # Remove common XBRL artifacts
        text = re.sub(r'us-gaap:[A-Za-z]+', '', text)
        text = re.sub(r'dei:[A-Za-z]+', '', text)
        text = re.sub(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', '', text)
        
        return text.strip()
    
    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
        """Split text into overlapping chunks"""
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk_words = words[i:i + chunk_size]
            if len(chunk_words) >= 50:  # Minimum chunk size
                chunks.append(' '.join(chunk_words))
        
        return chunks
    
    def extract_key_sections(self, text: str, form_type: str) -> Dict[str, str]:
        """Extract key sections based on form type"""
        sections = {}
        
        if form_type == '10-K':
            # Annual report sections
            section_patterns = [
                ('business', r'(?:ITEM\s*1[\.\s]+BUSINESS|PART\s*I.*?ITEM\s*1)(.*?)(?=ITEM\s*1A|ITEM\s*2|$)', 0),
                ('risk_factors', r'(?:ITEM\s*1A[\.\s]+RISK\s*FACTORS)(.*?)(?=ITEM\s*1B|ITEM\s*2|$)', 0),
                ('mda', r'(?:ITEM\s*7[\.\s]+MANAGEMENT.*?DISCUSSION)(.*?)(?=ITEM\s*7A|ITEM\s*8|$)', 0),
                ('financials', r'(?:ITEM\s*8[\.\s]+FINANCIAL\s*STATEMENTS)(.*?)(?=ITEM\s*9|$)', 0),
            ]
        elif form_type == '10-Q':
            # Quarterly report sections
            section_patterns = [
                ('financials', r'(?:PART\s*I.*?ITEM\s*1[\.\s]+FINANCIAL)(.*?)(?=ITEM\s*2|$)', 0),
                ('mda', r'(?:ITEM\s*2[\.\s]+MANAGEMENT.*?DISCUSSION)(.*?)(?=ITEM\s*3|ITEM\s*4|$)', 0),
            ]
        else:
            # 8-K - just use full text
            sections['content'] = text[:10000]
            return sections
        
        text_upper = text.upper()
        for section_name, pattern, _ in section_patterns:
            match = re.search(pattern, text_upper, re.DOTALL | re.IGNORECASE)
            if match:
                start = match.start(1)
                end = match.end(1)
                sections[section_name] = text[start:min(end, start + 15000)]
        
        return sections
    
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
        embeddings = self.model.encode(chunks, show_progress_bar=False)
        
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
                    embedding.tolist(),
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
        
        # Extract key sections
        sections = self.extract_key_sections(text, filing['form_type'])
        
        # Create chunks from all sections
        all_chunks = []
        for section_name, section_text in sections.items():
            chunks = self.chunk_text(section_text)
            for chunk in chunks:
                all_chunks.append(chunk)
        
        # If no sections found, chunk the full text
        if not all_chunks:
            all_chunks = self.chunk_text(text[:50000])
        
        if not all_chunks:
            return 0
        
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
        count = self.insert_chunks(document_id, all_chunks[:100], metadata)  # Limit to 100 chunks per doc
        
        logger.info(f"  ✅ Created {count} chunks")
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
        processor.run(limit=15)  # Process top 15 10-K/10-Q filings
    finally:
        processor.close()
