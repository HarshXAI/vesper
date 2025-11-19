"""
Integration tests for the ingestion service

These tests require:
- MinIO running on localhost:9000
- Internet connection for SEC EDGAR API
"""
import pytest
import os
from vesper_ingestion.connectors.sec_edgar import SECEdgarConnector
from vesper_ingestion.storage.s3_storage import S3Storage
from vesper_ingestion.config import get_config


# Skip integration tests if not explicitly enabled
pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="Integration tests require RUN_INTEGRATION_TESTS=1"
)


@pytest.fixture
def config():
    """Get configuration"""
    return get_config()


@pytest.fixture
def sec_connector(config):
    """Create SEC EDGAR connector"""
    return SECEdgarConnector(
        user_agent=config.sec_edgar.user_agent,
        rate_limit=config.sec_edgar.rate_limit
    )


@pytest.fixture
def storage(config):
    """Create S3 storage"""
    return S3Storage(
        bucket_name=config.storage.s3_bucket_name,
        endpoint_url=config.storage.s3_endpoint_url,
        aws_access_key_id=config.storage.aws_access_key_id,
        aws_secret_access_key=config.storage.aws_secret_access_key,
        region_name=config.storage.aws_region
    )


def test_sec_edgar_connection(sec_connector):
    """Test connection to SEC EDGAR API"""
    assert sec_connector.validate_connection() is True


def test_fetch_apple_filings(sec_connector):
    """Test fetching Apple's 10-K filings"""
    filings = sec_connector.fetch_filings(
        cik_list=["0000320193"],  # Apple Inc.
        form_types=["10-K"],
        max_per_cik=2
    )
    
    assert len(filings) > 0
    assert len(filings) <= 2
    
    for filing in filings:
        assert filing.cik == "0000320193"
        assert filing.form_type == "10-K"
        assert filing.html_content is not None
        assert len(filing.html_content) > 0


def test_storage_upload_download(storage, sec_connector):
    """Test uploading and downloading a filing"""
    # Fetch a single filing
    filings = sec_connector.fetch_filings(
        cik_list=["0000320193"],
        form_types=["10-K"],
        max_per_cik=1
    )
    
    assert len(filings) == 1
    filing = filings[0]
    
    # Upload to storage
    key = storage.upload_filing(filing, prefix="test")
    
    assert key is not None
    assert "test/" in key
    
    # Check if exists
    exists = storage.filing_exists(key)
    assert exists is True
    
    # Download and verify
    downloaded_filing = storage.download_filing(key)
    
    assert downloaded_filing.cik == filing.cik
    assert downloaded_filing.accession_number == filing.accession_number
    assert downloaded_filing.html_content == filing.html_content


def test_end_to_end_ingestion(sec_connector, storage):
    """Test complete ingestion workflow"""
    # Fetch filings
    filings = sec_connector.fetch_filings(
        cik_list=["0001018724"],  # Amazon
        form_types=["10-Q"],
        max_per_cik=1
    )
    
    assert len(filings) > 0
    
    # Upload all filings
    uploaded_keys = []
    for filing in filings:
        key = storage.upload_filing(filing, prefix="integration-test")
        uploaded_keys.append(key)
    
    # Verify all uploads
    for key in uploaded_keys:
        assert storage.filing_exists(key) is True
    
    # List filings
    all_keys = storage.list_filings(prefix="integration-test")
    
    # At least our uploaded filings should be present
    assert len(all_keys) >= len(uploaded_keys)


def test_fetch_multiple_form_types(sec_connector):
    """Test fetching multiple form types"""
    filings = sec_connector.fetch_filings(
        cik_list=["0000320193"],
        form_types=["10-K", "10-Q"],
        max_per_cik=5
    )
    
    assert len(filings) > 0
    
    # Should have mix of 10-K and 10-Q
    form_types = {f.form_type for f in filings}
    assert len(form_types) > 0
    assert all(ft in ["10-K", "10-Q"] for ft in form_types)


def test_fetch_date_range(sec_connector):
    """Test fetching filings within date range"""
    filings = sec_connector.fetch_filings(
        cik_list=["0000320193"],
        form_types=["10-K"],
        start_date="2023-01-01",
        end_date="2023-12-31",
        max_per_cik=10
    )
    
    # Verify all filings are within date range
    for filing in filings:
        filing_date = filing.filing_date
        assert filing_date >= "2023-01-01"
        assert filing_date <= "2023-12-31"


def test_rate_limiting(sec_connector):
    """Test that rate limiting is working"""
    import time
    
    start_time = time.time()
    
    # Fetch multiple filings (should be rate limited)
    filings = sec_connector.fetch_filings(
        cik_list=["0000320193", "0001018724", "0001652044"],  # Apple, Amazon, Google
        form_types=["10-K"],
        max_per_cik=1
    )
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Should take at least some time due to rate limiting
    # With 10 requests/sec and ~3 companies, should take at least 0.3 seconds
    assert duration > 0.3


def test_storage_list_with_prefix(storage, sec_connector):
    """Test listing filings with specific prefix"""
    # Upload a filing to a specific prefix
    filings = sec_connector.fetch_filings(
        cik_list=["0000320193"],
        form_types=["10-K"],
        max_per_cik=1
    )
    
    if filings:
        key = storage.upload_filing(filings[0], prefix="test-prefix")
        
        # List with prefix
        keys = storage.list_filings(prefix="test-prefix")
        
        assert len(keys) > 0
        assert all("test-prefix" in k for k in keys)
