#!/usr/bin/env python
"""
Quick test script for local development

Tests the ingestion service end-to-end without installing the package.
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from vesper_ingestion.connectors.sec_edgar import SECEdgarConnector
from vesper_ingestion.storage.s3_storage import S3Storage
from vesper_ingestion.config import get_config
import structlog

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer()
    ],
)

logger = structlog.get_logger()


def test_connection():
    """Test SEC EDGAR connection"""
    print("=" * 60)
    print("Testing SEC EDGAR Connection")
    print("=" * 60)
    
    connector = SECEdgarConnector(
        user_agent="VESPER Test vesper@test.com",
        rate_limit=10.0
    )
    
    if connector.validate_connection():
        print("✅ SEC EDGAR connection OK")
        return True
    else:
        print("❌ SEC EDGAR connection FAILED")
        return False


def test_fetch_filing():
    """Test fetching a single filing"""
    print("\n" + "=" * 60)
    print("Testing Filing Fetch (Apple 10-K)")
    print("=" * 60)
    
    connector = SECEdgarConnector(
        user_agent="VESPER Test vesper@test.com",
        rate_limit=10.0
    )
    
    try:
        filings = connector.fetch_filings(
            cik_list=["0000320193"],  # Apple
            form_types=["10-K"],
            max_per_cik=1
        )
        
        if filings:
            filing = filings[0]
            print(f"✅ Fetched filing:")
            print(f"   CIK: {filing.cik}")
            print(f"   Form: {filing.form_type}")
            print(f"   Date: {filing.filing_date}")
            print(f"   Accession: {filing.accession_number}")
            print(f"   Content length: {len(filing.html_content or '')} bytes")
            return filing
        else:
            print("⚠️  No filings found")
            return None
            
    except Exception as e:
        print(f"❌ Failed to fetch filing: {e}")
        return None


def test_storage(filing):
    """Test storage upload/download"""
    if not filing:
        print("\n⚠️  Skipping storage test (no filing)")
        return False
    
    print("\n" + "=" * 60)
    print("Testing S3/MinIO Storage")
    print("=" * 60)
    
    try:
        storage = S3Storage(
            bucket_name="vesper-bronze",
            endpoint_url="http://localhost:9000",
            aws_access_key_id="minioadmin",
            aws_secret_access_key="minioadmin",
            region_name="us-east-1"
        )
        
        print("✅ Storage initialized")
        
        # Upload
        key = storage.upload_filing(filing, prefix="test")
        print(f"✅ Uploaded to: {key}")
        
        # Check exists
        exists = storage.filing_exists(key)
        print(f"✅ Filing exists: {exists}")
        
        # Download
        downloaded = storage.download_filing(key)
        print(f"✅ Downloaded filing")
        print(f"   CIK: {downloaded.cik}")
        print(f"   Accession: {downloaded.accession_number}")
        
        # Verify content matches
        if downloaded.html_content == filing.html_content:
            print("✅ Content verification passed")
        else:
            print("⚠️  Content mismatch")
        
        return True
        
    except Exception as e:
        print(f"❌ Storage test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n🚀 VESPER Ingestion Service - Quick Test")
    print("=" * 60)
    
    # Test connection
    if not test_connection():
        print("\n❌ Connection test failed. Exiting.")
        return 1
    
    # Test fetch
    filing = test_fetch_filing()
    
    # Test storage
    test_storage(filing)
    
    print("\n" + "=" * 60)
    print("✅ All tests complete!")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
