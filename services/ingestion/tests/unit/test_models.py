"""
Unit tests for Filing data models
"""
import pytest
from datetime import datetime
from vesper_ingestion.models.filing import Filing, FilingMetadata


def test_filing_creation():
    """Test creating a Filing object"""
    filing = Filing(
        cik="0000320193",
        accession_number="0000320193-23-000077",
        filing_date="2023-11-03",
        form_type="10-K",
        document_url="https://www.sec.gov/Archives/edgar/data/320193/000032019323000077/aapl-20230930.htm"
    )
    
    assert filing.cik == "0000320193"
    assert filing.accession_number == "0000320193-23-000077"
    assert filing.filing_date == "2023-11-03"
    assert filing.form_type == "10-K"
    assert filing.html_content is None
    assert filing.text_content is None


def test_filing_with_content():
    """Test Filing with HTML content"""
    html = "<html><body>Test content</body></html>"
    
    filing = Filing(
        cik="0000320193",
        accession_number="0000320193-23-000077",
        filing_date="2023-11-03",
        form_type="10-K",
        document_url="https://www.sec.gov/test.htm",
        html_content=html
    )
    
    assert filing.html_content == html
    assert len(filing.html_content) > 0


def test_filing_metadata():
    """Test FilingMetadata model"""
    metadata = FilingMetadata(
        file_size=1024,
        content_type="text/html",
        checksum="abc123",
        source_url="https://www.sec.gov/test.htm",
        retrieval_timestamp="2024-01-01T00:00:00"
    )
    
    assert metadata.file_size == 1024
    assert metadata.content_type == "text/html"
    assert metadata.checksum == "abc123"


def test_filing_serialization():
    """Test Filing model serialization"""
    filing = Filing(
        cik="0000320193",
        accession_number="0000320193-23-000077",
        filing_date="2023-11-03",
        form_type="10-K",
        document_url="https://www.sec.gov/test.htm"
    )
    
    # Serialize to dict
    data = filing.model_dump()
    
    assert data["cik"] == "0000320193"
    assert data["form_type"] == "10-K"
    assert "html_content" in data
    
    # Serialize to JSON
    json_str = filing.model_dump_json()
    assert isinstance(json_str, str)
    assert "0000320193" in json_str


def test_filing_deserialization():
    """Test Filing model deserialization"""
    data = {
        "cik": "0000320193",
        "accession_number": "0000320193-23-000077",
        "filing_date": "2023-11-03",
        "form_type": "10-K",
        "document_url": "https://www.sec.gov/test.htm"
    }
    
    filing = Filing(**data)
    
    assert filing.cik == "0000320193"
    assert filing.form_type == "10-K"


def test_filing_validation():
    """Test Filing validation"""
    # Should work with minimal fields
    filing = Filing(
        cik="320193",
        accession_number="0000320193-23-000077",
        filing_date="2023-11-03",
        form_type="10-K",
        document_url="https://www.sec.gov/test.htm"
    )
    
    assert filing.cik == "320193"
    
    # Should raise validation error for missing required field
    with pytest.raises(ValueError):
        Filing(
            cik="320193",
            # Missing accession_number
            filing_date="2023-11-03",
            form_type="10-K",
            document_url="https://www.sec.gov/test.htm"
        )
