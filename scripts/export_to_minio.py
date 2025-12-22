#!/usr/bin/env python3
"""
Export Medallion data to MinIO buckets
Bronze → vesper-bronze
Silver → vesper-silver  
Gold → vesper-gold
"""
import json
import os
from datetime import datetime
from typing import Dict, List
import logging

import psycopg2
from psycopg2.extras import RealDictCursor
from minio import Minio
from minio.error import S3Error

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MinIOExporter:
    """Export medallion data to MinIO"""
    
    def __init__(self):
        self.db_url = os.environ.get(
            'DATABASE_URL',
            'postgresql://vesper:vesper@localhost:5434/vesper'
        )
        self.conn = psycopg2.connect(self.db_url)
        
        # MinIO client
        self.minio = Minio(
            "localhost:9000",
            access_key="minioadminio",
            secret_key="minioadmin",
            secure=False
        )
        
        # Ensure buckets exist
        for bucket in ['vesper-bronze', 'vesper-silver', 'vesper-gold']:
            if not self.minio.bucket_exists(bucket):
                self.minio.make_bucket(bucket)
                logger.info(f"Created bucket: {bucket}")
    
    def export_bronze(self):
        """Export Bronze filings to MinIO"""
        logger.info("Exporting Bronze layer to MinIO...")
        
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, cik, company_name, form_type, filing_date, 
                       accession_number, s3_key, document_url, filing_metadata
                FROM bronze.filings
                ORDER BY filing_date DESC;
            """)
            filings = cur.fetchall()
        
        for filing in filings:
            # Convert to JSON
            data = {
                'id': filing['id'],
                'cik': filing['cik'],
                'company_name': filing['company_name'],
                'form_type': filing['form_type'],
                'filing_date': filing['filing_date'].isoformat() if filing['filing_date'] else None,
                'accession_number': filing['accession_number'],
                's3_key': filing['s3_key'],
                'document_url': filing['document_url'],
                'metadata': filing['filing_metadata'],
                'exported_at': datetime.utcnow().isoformat()
            }
            
            # Upload to MinIO
            object_name = f"sec-edgar/{filing['cik']}/{filing['form_type']}/{filing['accession_number']}.json"
            json_bytes = json.dumps(data, indent=2, default=str).encode('utf-8')
            
            from io import BytesIO
            self.minio.put_object(
                'vesper-bronze',
                object_name,
                BytesIO(json_bytes),
                len(json_bytes),
                content_type='application/json'
            )
        
        logger.info(f"✅ Exported {len(filings)} Bronze filings to vesper-bronze")
        return len(filings)
    
    def export_silver(self):
        """Export Silver filings to MinIO"""
        logger.info("Exporting Silver layer to MinIO...")
        
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT filing_id, accession_number, cik, ticker, company_name,
                       form_type, filing_date, period_end, fiscal_year, fiscal_quarter,
                       normalized_text, text_length, word_count, section_count,
                       table_count, has_financials, industry_sector, quality_score,
                       bronze_s3_path, document_hash, transform_version
                FROM silver.filings
                ORDER BY filing_date DESC;
            """)
            filings = cur.fetchall()
        
        from io import BytesIO
        
        for filing in filings:
            data = {
                'filing_id': filing['filing_id'],
                'accession_number': filing['accession_number'],
                'cik': filing['cik'],
                'ticker': filing['ticker'],
                'company_name': filing['company_name'],
                'form_type': filing['form_type'],
                'filing_date': filing['filing_date'].isoformat() if filing['filing_date'] else None,
                'period_end': filing['period_end'].isoformat() if filing['period_end'] else None,
                'fiscal_year': filing['fiscal_year'],
                'fiscal_quarter': filing['fiscal_quarter'],
                'normalized_text': filing['normalized_text'],
                'text_length': filing['text_length'],
                'word_count': filing['word_count'],
                'section_count': filing['section_count'],
                'table_count': filing['table_count'],
                'has_financials': filing['has_financials'],
                'industry_sector': filing['industry_sector'],
                'quality_score': filing['quality_score'],
                'bronze_s3_path': filing['bronze_s3_path'],
                'document_hash': filing['document_hash'],
                'transform_version': filing['transform_version'],
                'exported_at': datetime.utcnow().isoformat()
            }
            
            # Upload to MinIO
            object_name = f"filings/{filing['ticker']}/{filing['form_type']}/{filing['accession_number']}.json"
            json_bytes = json.dumps(data, indent=2, default=str).encode('utf-8')
            
            self.minio.put_object(
                'vesper-silver',
                object_name,
                BytesIO(json_bytes),
                len(json_bytes),
                content_type='application/json'
            )
        
        logger.info(f"✅ Exported {len(filings)} Silver filings to vesper-silver")
        return len(filings)
    
    def export_gold(self):
        """Export Gold metrics to MinIO"""
        logger.info("Exporting Gold layer to MinIO...")
        
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT cik, ticker, company_name, period_end, fiscal_year, fiscal_quarter,
                       total_revenue, net_income, total_assets, total_liabilities,
                       operating_cash_flow, revenue_growth, profit_margin, 
                       metric_confidence, source_filing_id
                FROM gold.company_metrics
                ORDER BY ticker, period_end DESC;
            """)
            metrics = cur.fetchall()
        
        from io import BytesIO
        
        # Group by company for aggregate files
        by_company = {}
        for m in metrics:
            ticker = m['ticker']
            if ticker not in by_company:
                by_company[ticker] = []
            by_company[ticker].append(m)
        
        for ticker, company_metrics in by_company.items():
            for metric in company_metrics:
                data = {
                    'cik': metric['cik'],
                    'ticker': metric['ticker'],
                    'company_name': metric['company_name'],
                    'period_end': metric['period_end'].isoformat() if metric['period_end'] else None,
                    'fiscal_year': metric['fiscal_year'],
                    'fiscal_quarter': metric['fiscal_quarter'],
                    'financials': {
                        'total_revenue': float(metric['total_revenue']) if metric['total_revenue'] else None,
                        'net_income': float(metric['net_income']) if metric['net_income'] else None,
                        'total_assets': float(metric['total_assets']) if metric['total_assets'] else None,
                        'total_liabilities': float(metric['total_liabilities']) if metric['total_liabilities'] else None,
                        'operating_cash_flow': float(metric['operating_cash_flow']) if metric['operating_cash_flow'] else None,
                    },
                    'ratios': {
                        'revenue_growth': float(metric['revenue_growth']) if metric['revenue_growth'] else None,
                        'profit_margin': float(metric['profit_margin']) if metric['profit_margin'] else None,
                    },
                    'metric_confidence': float(metric['metric_confidence']) if metric['metric_confidence'] else None,
                    'source_filing_id': metric['source_filing_id'],
                    'exported_at': datetime.utcnow().isoformat()
                }
                
                # Upload individual metric
                period = f"FY{metric['fiscal_year']}Q{metric['fiscal_quarter']}"
                object_name = f"metrics/{ticker}/{period}.json"
                json_bytes = json.dumps(data, indent=2, default=str).encode('utf-8')
                
                self.minio.put_object(
                    'vesper-gold',
                    object_name,
                    BytesIO(json_bytes),
                    len(json_bytes),
                    content_type='application/json'
                )
            
            # Also create a summary file for each company
            summary = {
                'ticker': ticker,
                'company_name': company_metrics[0]['company_name'],
                'cik': company_metrics[0]['cik'],
                'periods': len(company_metrics),
                'latest_period': f"FY{company_metrics[0]['fiscal_year']}Q{company_metrics[0]['fiscal_quarter']}",
                'metrics_summary': company_metrics,
                'exported_at': datetime.utcnow().isoformat()
            }
            
            summary_bytes = json.dumps(summary, indent=2, default=str).encode('utf-8')
            self.minio.put_object(
                'vesper-gold',
                f"summaries/{ticker}_summary.json",
                BytesIO(summary_bytes),
                len(summary_bytes),
                content_type='application/json'
            )
        
        logger.info(f"✅ Exported {len(metrics)} Gold metrics to vesper-gold")
        return len(metrics)
    
    def run(self):
        """Export all layers"""
        logger.info("=" * 60)
        logger.info("Exporting Medallion data to MinIO")
        logger.info("=" * 60)
        
        bronze_count = self.export_bronze()
        silver_count = self.export_silver()
        gold_count = self.export_gold()
        
        logger.info("=" * 60)
        logger.info(f"Export complete: {bronze_count} Bronze, {silver_count} Silver, {gold_count} Gold")
        logger.info("=" * 60)
    
    def close(self):
        self.conn.close()


if __name__ == '__main__':
    exporter = MinIOExporter()
    try:
        exporter.run()
    finally:
        exporter.close()
