"""
Unit tests for S3Storage
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

from vesper_ingestion.storage.s3_storage import S3Storage
from vesper_ingestion.models.filing import Filing


@pytest.fixture
def mock_s3_client():
    """Create a mock S3 client"""
    with patch("vesper_ingestion.storage.s3_storage.boto3") as mock_boto3:
        mock_client = Mock()
        mock_boto3.client.return_value = mock_client
        yield mock_client


@pytest.fixture
def sample_filing():
    """Create a sample filing for testing"""
    return Filing(
        cik="0000320193",
        accession_number="0000320193-23-000077",
        filing_date="2023-11-03",
        form_type="10-K",
        document_url="https://www.sec.gov/test.htm",
        html_content="<html><body>Test content</body></html>"
    )


def test_storage_initialization(mock_s3_client):
    """Test S3Storage initialization"""
    mock_s3_client.head_bucket.return_value = {}
    
    storage = S3Storage(
        bucket_name="test-bucket",
        endpoint_url="http://localhost:9000",
        aws_access_key_id="test",
        aws_secret_access_key="test"
    )
    
    assert storage.bucket_name == "test-bucket"
    mock_s3_client.head_bucket.assert_called_once_with(Bucket="test-bucket")


def test_storage_creates_bucket_if_not_exists(mock_s3_client):
    """Test that storage creates bucket if it doesn't exist"""
    # Simulate bucket not found
    error_response = {"Error": {"Code": "404"}}
    mock_s3_client.head_bucket.side_effect = ClientError(error_response, "HeadBucket")
    
    storage = S3Storage(
        bucket_name="test-bucket",
        endpoint_url="http://localhost:9000",
        aws_access_key_id="test",
        aws_secret_access_key="test"
    )
    
    mock_s3_client.create_bucket.assert_called_once_with(Bucket="test-bucket")


def test_get_filing_key(mock_s3_client, sample_filing):
    """Test _get_filing_key method"""
    mock_s3_client.head_bucket.return_value = {}
    
    storage = S3Storage(
        bucket_name="test-bucket",
        endpoint_url="http://localhost:9000"
    )
    
    key = storage._get_filing_key(sample_filing)
    
    assert "sec-edgar" in key
    assert "320193" in key  # CIK without leading zeros
    assert "10-K" in key
    assert "0000320193-23-000077" in key


def test_get_filing_key_with_prefix(mock_s3_client, sample_filing):
    """Test _get_filing_key with prefix"""
    mock_s3_client.head_bucket.return_value = {}
    
    storage = S3Storage(
        bucket_name="test-bucket",
        endpoint_url="http://localhost:9000"
    )
    
    key = storage._get_filing_key(sample_filing, prefix="bronze")
    
    assert key.startswith("bronze/")


def test_upload_filing(mock_s3_client, sample_filing):
    """Test uploading a filing"""
    mock_s3_client.head_bucket.return_value = {}
    
    storage = S3Storage(
        bucket_name="test-bucket",
        endpoint_url="http://localhost:9000"
    )
    
    key = storage.upload_filing(sample_filing, prefix="bronze")
    
    # Should call put_object twice (HTML + metadata)
    assert mock_s3_client.put_object.call_count == 2
    assert "bronze/" in key


def test_upload_filing_without_content(mock_s3_client):
    """Test uploading a filing without content raises error"""
    mock_s3_client.head_bucket.return_value = {}
    
    storage = S3Storage(
        bucket_name="test-bucket",
        endpoint_url="http://localhost:9000"
    )
    
    filing = Filing(
        cik="0000320193",
        accession_number="0000320193-23-000077",
        filing_date="2023-11-03",
        form_type="10-K",
        document_url="https://www.sec.gov/test.htm"
        # No html_content
    )
    
    with pytest.raises(ValueError, match="must have html_content"):
        storage.upload_filing(filing)


def test_download_filing(mock_s3_client):
    """Test downloading a filing"""
    mock_s3_client.head_bucket.return_value = {}
    
    # Mock get_object responses
    metadata_response = {
        "Body": MagicMock(read=lambda: b'{"cik": "0000320193", "accession_number": "0000320193-23-000077", "filing_date": "2023-11-03", "form_type": "10-K", "document_url": "https://www.sec.gov/test.htm"}')
    }
    html_response = {
        "Body": MagicMock(read=lambda: b"<html><body>Test</body></html>")
    }
    
    mock_s3_client.get_object.side_effect = [metadata_response, html_response]
    
    storage = S3Storage(
        bucket_name="test-bucket",
        endpoint_url="http://localhost:9000"
    )
    
    filing = storage.download_filing("bronze/sec-edgar/320193/10-K/0000320193-23-000077")
    
    assert filing.cik == "0000320193"
    assert filing.html_content == "<html><body>Test</body></html>"


def test_filing_exists(mock_s3_client):
    """Test checking if filing exists"""
    mock_s3_client.head_bucket.return_value = {}
    mock_s3_client.head_object.return_value = {}
    
    storage = S3Storage(
        bucket_name="test-bucket",
        endpoint_url="http://localhost:9000"
    )
    
    exists = storage.filing_exists("bronze/sec-edgar/320193/10-K/0000320193-23-000077")
    
    assert exists is True
    assert mock_s3_client.head_object.call_count == 2  # HTML + metadata


def test_filing_does_not_exist(mock_s3_client):
    """Test checking if non-existent filing exists"""
    mock_s3_client.head_bucket.return_value = {}
    error_response = {"Error": {"Code": "404"}}
    mock_s3_client.head_object.side_effect = ClientError(error_response, "HeadObject")
    
    storage = S3Storage(
        bucket_name="test-bucket",
        endpoint_url="http://localhost:9000"
    )
    
    exists = storage.filing_exists("bronze/sec-edgar/nonexistent")
    
    assert exists is False


def test_list_filings(mock_s3_client):
    """Test listing filings"""
    mock_s3_client.head_bucket.return_value = {}
    
    # Mock paginator
    mock_paginator = Mock()
    mock_pages = [
        {
            "CommonPrefixes": [
                {"Prefix": "bronze/sec-edgar/320193/10-K/0000320193-23-000077/"},
                {"Prefix": "bronze/sec-edgar/320193/10-Q/0000320193-23-000078/"}
            ]
        }
    ]
    mock_paginator.paginate.return_value = mock_pages
    mock_s3_client.get_paginator.return_value = mock_paginator
    
    storage = S3Storage(
        bucket_name="test-bucket",
        endpoint_url="http://localhost:9000"
    )
    
    keys = storage.list_filings(prefix="bronze")
    
    assert len(keys) == 2
    assert "bronze/sec-edgar/320193/10-K/0000320193-23-000077" in keys
