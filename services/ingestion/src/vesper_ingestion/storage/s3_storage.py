"""
S3/MinIO Storage Backend

Stores filings in S3-compatible object storage (MinIO for local, S3 for production).
"""
import json
from typing import Optional
import boto3
from botocore.exceptions import ClientError
import structlog

from vesper_ingestion.storage.base import BaseStorage
from vesper_ingestion.models.filing import Filing

logger = structlog.get_logger()


class S3Storage(BaseStorage):
    """
    S3/MinIO storage backend for the Bronze layer
    """
    
    def __init__(
        self,
        bucket_name: str,
        endpoint_url: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        region_name: str = "us-east-1"
    ):
        """
        Initialize S3 storage
        
        Args:
            bucket_name: S3 bucket name
            endpoint_url: S3 endpoint URL (for MinIO)
            aws_access_key_id: AWS access key
            aws_secret_access_key: AWS secret key
            region_name: AWS region
        """
        self.bucket_name = bucket_name
        
        # Initialize S3 client
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name
        )
        
        logger.info(
            "s3_storage_initialized",
            bucket=bucket_name,
            endpoint=endpoint_url
        )
        
        # Ensure bucket exists
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """Create bucket if it doesn't exist"""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.debug("bucket_exists", bucket=self.bucket_name)
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.info("creating_bucket", bucket=self.bucket_name)
                self.s3_client.create_bucket(Bucket=self.bucket_name)
            else:
                raise
    
    def _get_filing_key(self, filing: Filing, prefix: str = "") -> str:
        """
        Generate S3 key for a filing
        
        Format: {prefix}/sec-edgar/{cik}/{form_type}/{accession_number}/
        """
        cik = filing.cik.lstrip('0')  # Remove leading zeros
        accession = filing.accession_number
        
        base_path = f"sec-edgar/{cik}/{filing.form_type}/{accession}"
        
        if prefix:
            return f"{prefix}/{base_path}"
        return base_path
    
    def upload_filing(self, filing: Filing, prefix: str = "") -> str:
        """
        Upload filing to S3/MinIO
        
        Uploads both the HTML content and metadata as separate objects.
        
        Args:
            filing: Filing object with content
            prefix: Optional prefix (e.g., 'raw', 'bronze')
            
        Returns:
            Base S3 key for the filing
        """
        if not filing.html_content:
            raise ValueError("Filing must have html_content to upload")
        
        base_key = self._get_filing_key(filing, prefix)
        
        logger.info(
            "uploading_filing",
            cik=filing.cik,
            accession_number=filing.accession_number,
            key=base_key
        )
        
        try:
            # Upload HTML content
            html_key = f"{base_key}/document.html"
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=html_key,
                Body=filing.html_content.encode('utf-8'),
                ContentType='text/html',
                Metadata={
                    'cik': filing.cik,
                    'form_type': filing.form_type,
                    'accession_number': filing.accession_number
                }
            )
            
            # Upload metadata
            metadata_key = f"{base_key}/metadata.json"
            metadata = filing.model_dump(
                exclude={'html_content', 'text_content'},
                mode='json'
            )
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=metadata_key,
                Body=json.dumps(metadata, indent=2, default=str).encode('utf-8'),
                ContentType='application/json'
            )
            
            logger.info(
                "uploaded_filing",
                cik=filing.cik,
                accession_number=filing.accession_number,
                html_key=html_key,
                metadata_key=metadata_key
            )
            
            return base_key
            
        except ClientError as e:
            logger.error(
                "failed_to_upload_filing",
                cik=filing.cik,
                accession_number=filing.accession_number,
                error=str(e)
            )
            raise
    
    def download_filing(self, key: str) -> Filing:
        """
        Download filing from S3/MinIO
        
        Args:
            key: Base S3 key for the filing
            
        Returns:
            Filing object with content
        """
        logger.info("downloading_filing", key=key)
        
        try:
            # Download metadata
            metadata_key = f"{key}/metadata.json"
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=metadata_key
            )
            metadata = json.loads(response['Body'].read().decode('utf-8'))
            
            # Download HTML content
            html_key = f"{key}/document.html"
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=html_key
            )
            html_content = response['Body'].read().decode('utf-8')
            
            # Reconstruct Filing object
            filing = Filing(**metadata)
            filing.html_content = html_content
            
            logger.info("downloaded_filing", key=key)
            return filing
            
        except ClientError as e:
            logger.error("failed_to_download_filing", key=key, error=str(e))
            raise
    
    def filing_exists(self, key: str) -> bool:
        """
        Check if a filing exists in S3/MinIO
        
        Args:
            key: Base S3 key for the filing
            
        Returns:
            True if both document and metadata exist
        """
        try:
            html_key = f"{key}/document.html"
            self.s3_client.head_object(Bucket=self.bucket_name, Key=html_key)
            
            metadata_key = f"{key}/metadata.json"
            self.s3_client.head_object(Bucket=self.bucket_name, Key=metadata_key)
            
            return True
        except ClientError:
            return False
    
    def list_filings(self, prefix: str = "") -> list[str]:
        """
        List all filings in S3/MinIO
        
        Args:
            prefix: Optional prefix to filter by
            
        Returns:
            List of base S3 keys
        """
        logger.info("listing_filings", prefix=prefix)
        
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(
                Bucket=self.bucket_name,
                Prefix=prefix,
                Delimiter='/'
            )
            
            keys = []
            for page in pages:
                if 'CommonPrefixes' in page:
                    for obj in page['CommonPrefixes']:
                        keys.append(obj['Prefix'].rstrip('/'))
            
            logger.info("listed_filings", count=len(keys))
            return keys
            
        except ClientError as e:
            logger.error("failed_to_list_filings", error=str(e))
            raise
