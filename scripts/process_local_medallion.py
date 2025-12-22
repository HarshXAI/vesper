#!/usr/bin/env python3
"""
Local Medallion Pipeline Processor
Transforms Bronze → Silver → Gold in local PostgreSQL
"""
import json
import os
import hashlib
import re
from datetime import datetime
from typing import List, Dict, Optional
import logging

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MedallionProcessor:
    """Process Bronze → Silver → Gold pipeline locally"""
    
    def __init__(self, db_url: str = None):
        self.db_url = db_url or os.environ.get(
            'DATABASE_URL',
            'postgresql://vesper:vesper@localhost:5434/vesper'
        )
        self.conn = psycopg2.connect(self.db_url)
        self.conn.autocommit = False
        logger.info(f"Connected to database")
    
    def get_bronze_filings(self, limit: int = 100) -> List[Dict]:
        """Fetch unprocessed Bronze filings"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    b.id, b.cik, b.company_name, b.form_type, 
                    b.filing_date, b.accession_number, b.s3_key,
                    b.document_url, b.filing_metadata, b.created_at
                FROM bronze.filings b
                LEFT JOIN silver.filings s ON b.accession_number = s.accession_number
                WHERE s.id IS NULL
                ORDER BY b.filing_date DESC
                LIMIT %s;
            """, (limit,))
            return cur.fetchall()
    
    def transform_to_silver(self, bronze: Dict) -> Dict:
        """Transform a Bronze filing to Silver format"""
        # Use filing metadata if available
        metadata = bronze.get('filing_metadata', {}) or {}
        
        # Generate description text
        text = f"SEC Filing: {bronze['form_type']} for {bronze['company_name']}. Filed on {bronze['filing_date']}. Document URL: {bronze.get('document_url', 'N/A')}"
        
        # Calculate stats
        word_count = len(text.split())
        text_length = len(text)
        
        # Determine CIK -> Ticker mapping (simplified)
        ticker = self._cik_to_ticker(bronze['cik'])
        
        # Calculate quality score
        quality_score = self._calculate_quality_score(text, bronze['form_type'])
        
        # Determine fiscal period from filing date
        filing_date = bronze['filing_date']
        fiscal_year = filing_date.year if filing_date else datetime.now().year
        fiscal_quarter = (filing_date.month - 1) // 3 + 1 if filing_date else 1
        
        # Generate filing ID
        filing_id = f"{bronze['cik']}_{bronze['form_type']}_{bronze['accession_number']}"
        document_hash = hashlib.sha256(text.encode()).hexdigest()
        
        return {
            'filing_id': filing_id,
            'accession_number': bronze['accession_number'],
            'cik': bronze['cik'],
            'ticker': ticker,
            'company_name': bronze['company_name'],
            'form_type': bronze['form_type'],
            'filing_date': bronze['filing_date'],
            'period_end': bronze['filing_date'],  # Simplified
            'fiscal_year': fiscal_year,
            'fiscal_quarter': fiscal_quarter,
            'normalized_text': text[:50000],  # Limit text size
            'text_length': text_length,
            'word_count': word_count,
            'section_count': text.count('\n\n') + 1,
            'table_count': text.lower().count('table'),
            'has_financials': any(kw in text.lower() for kw in ['revenue', 'income', 'assets', 'cash']),
            'industry_sector': self._get_industry(bronze['company_name']),
            'quality_score': quality_score,
            'bronze_s3_path': bronze.get('s3_key', ''),
            'document_hash': document_hash,
            'transform_version': '1.0',
        }
    
    def insert_silver(self, silver: Dict) -> int:
        """Insert Silver filing into database"""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO silver.filings (
                    filing_id, accession_number, cik, ticker, company_name,
                    form_type, filing_date, period_end, fiscal_year, fiscal_quarter,
                    normalized_text, text_length, word_count, section_count, table_count,
                    has_financials, industry_sector, quality_score, bronze_s3_path,
                    document_hash, transform_version
                ) VALUES (
                    %(filing_id)s, %(accession_number)s, %(cik)s, %(ticker)s, %(company_name)s,
                    %(form_type)s, %(filing_date)s, %(period_end)s, %(fiscal_year)s, %(fiscal_quarter)s,
                    %(normalized_text)s, %(text_length)s, %(word_count)s, %(section_count)s, %(table_count)s,
                    %(has_financials)s, %(industry_sector)s, %(quality_score)s, %(bronze_s3_path)s,
                    %(document_hash)s, %(transform_version)s
                )
                ON CONFLICT (filing_id) DO UPDATE SET
                    normalized_text = EXCLUDED.normalized_text,
                    quality_score = EXCLUDED.quality_score,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id;
            """, silver)
            result = cur.fetchone()
            return result[0] if result else 0
    
    def aggregate_to_gold(self, cik: str) -> Dict:
        """Aggregate Silver filings to Gold metrics for a company"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get latest Silver filings
            cur.execute("""
                SELECT 
                    cik, ticker, company_name, fiscal_year, fiscal_quarter,
                    period_end, has_financials, normalized_text, filing_id
                FROM silver.filings
                WHERE cik = %s AND form_type IN ('10-K', '10-Q')
                ORDER BY period_end DESC
                LIMIT 5;
            """, (cik,))
            filings = cur.fetchall()
            
            if not filings:
                return None
            
            latest = filings[0]
            
            # Extract mock financial metrics from text
            metrics = self._extract_mock_metrics(latest)
            
            return {
                'cik': latest['cik'],
                'ticker': latest['ticker'],
                'company_name': latest['company_name'],
                'period_end': latest['period_end'],
                'fiscal_year': latest['fiscal_year'],
                'fiscal_quarter': latest['fiscal_quarter'],
                'source_filing_id': latest['filing_id'],
                **metrics
            }
    
    def insert_gold(self, gold: Dict) -> int:
        """Insert Gold metrics into database"""
        if not gold:
            return 0
        
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO gold.company_metrics (
                    cik, ticker, company_name, period_end, fiscal_year, fiscal_quarter,
                    total_revenue, net_income, total_assets, total_liabilities,
                    operating_cash_flow, revenue_growth, profit_margin,
                    metric_confidence, source_filing_id
                ) VALUES (
                    %(cik)s, %(ticker)s, %(company_name)s, %(period_end)s, 
                    %(fiscal_year)s, %(fiscal_quarter)s,
                    %(total_revenue)s, %(net_income)s, %(total_assets)s, %(total_liabilities)s,
                    %(operating_cash_flow)s, %(revenue_growth)s, %(profit_margin)s,
                    %(metric_confidence)s, %(source_filing_id)s
                )
                ON CONFLICT (cik, period_end, fiscal_year, fiscal_quarter) 
                DO UPDATE SET
                    total_revenue = EXCLUDED.total_revenue,
                    net_income = EXCLUDED.net_income,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id;
            """, gold)
            result = cur.fetchone()
            return result[0] if result else 0
    
    def _clean_html(self, html: str) -> str:
        """Remove HTML tags and clean text"""
        # Simple HTML tag removal
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _cik_to_ticker(self, cik: str) -> str:
        """Map CIK to ticker symbol"""
        mapping = {
            '0000320193': 'AAPL',
            '0001018724': 'AMZN',
            '0001652044': 'GOOGL',
            '0001326801': 'META',
            '0000789019': 'MSFT',
        }
        return mapping.get(cik, cik[:5].upper())
    
    def _get_industry(self, company_name: str) -> str:
        """Get industry sector from company name"""
        name_lower = company_name.lower()
        if any(kw in name_lower for kw in ['apple', 'microsoft', 'google', 'alphabet', 'meta']):
            return 'Technology'
        if 'amazon' in name_lower:
            return 'Consumer Discretionary'
        return 'Technology'
    
    def _calculate_quality_score(self, text: str, form_type: str) -> float:
        """Calculate data quality score"""
        score = 0.5
        
        # Length bonus
        if len(text) > 10000:
            score += 0.2
        elif len(text) > 1000:
            score += 0.1
        
        # Financial content bonus
        financial_keywords = ['revenue', 'income', 'assets', 'cash', 'earnings', 'profit']
        matches = sum(1 for kw in financial_keywords if kw in text.lower())
        score += min(0.2, matches * 0.03)
        
        # Form type bonus
        if form_type in ('10-K', '10-Q'):
            score += 0.1
        
        return min(1.0, score)
    
    def _extract_mock_metrics(self, filing: Dict) -> Dict:
        """Extract mock financial metrics (placeholder for real extraction)"""
        # In production, this would use NLP/LLM to extract real numbers
        import random
        
        base_revenue = random.uniform(50, 400) * 1e9
        return {
            'total_revenue': base_revenue,
            'net_income': base_revenue * random.uniform(0.1, 0.3),
            'total_assets': base_revenue * random.uniform(1.5, 3.0),
            'total_liabilities': base_revenue * random.uniform(0.5, 1.5),
            'operating_cash_flow': base_revenue * random.uniform(0.15, 0.35),
            'revenue_growth': random.uniform(-0.1, 0.3),
            'profit_margin': random.uniform(0.1, 0.35),
            'metric_confidence': 0.6,  # Low confidence for mock data
        }
    
    def run_pipeline(self, limit: int = 100):
        """Run the full Bronze → Silver → Gold pipeline"""
        logger.info("=" * 60)
        logger.info("Starting Medallion Pipeline: Bronze → Silver → Gold")
        logger.info("=" * 60)
        
        # Step 1: Get Bronze filings
        bronze_filings = self.get_bronze_filings(limit)
        logger.info(f"📥 Found {len(bronze_filings)} Bronze filings to process")
        
        if not bronze_filings:
            logger.info("No new Bronze filings to process")
            return
        
        # Step 2: Transform to Silver
        silver_count = 0
        processed_ciks = set()
        
        for bronze in bronze_filings:
            try:
                silver = self.transform_to_silver(bronze)
                silver_id = self.insert_silver(silver)
                silver_count += 1
                processed_ciks.add(bronze['cik'])
                logger.info(f"  ✅ Silver: {bronze['company_name']} - {bronze['form_type']}")
            except Exception as e:
                logger.error(f"  ❌ Silver error: {bronze['company_name']}: {e}")
        
        self.conn.commit()
        logger.info(f"📊 Created {silver_count} Silver filings")
        
        # Step 3: Aggregate to Gold
        gold_count = 0
        for cik in processed_ciks:
            try:
                gold = self.aggregate_to_gold(cik)
                if gold:
                    gold_id = self.insert_gold(gold)
                    gold_count += 1
                    logger.info(f"  ✅ Gold: {gold['ticker']} - FY{gold['fiscal_year']}Q{gold['fiscal_quarter']}")
            except Exception as e:
                logger.error(f"  ❌ Gold error: CIK {cik}: {e}")
        
        self.conn.commit()
        logger.info(f"🏆 Created {gold_count} Gold metrics")
        
        logger.info("=" * 60)
        logger.info(f"Pipeline complete: {silver_count} Silver, {gold_count} Gold")
        logger.info("=" * 60)
    
    def close(self):
        self.conn.close()


if __name__ == '__main__':
    processor = MedallionProcessor()
    try:
        processor.run_pipeline(limit=100)
    finally:
        processor.close()
