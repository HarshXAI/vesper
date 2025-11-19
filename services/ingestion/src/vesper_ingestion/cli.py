"""
Command-Line Interface for VESPER Ingestion Service

Provides commands for fetching and storing SEC EDGAR filings.
"""
import click
import structlog
from datetime import datetime
from typing import Optional
from sqlalchemy import text

from vesper_ingestion.config import get_config
from vesper_ingestion.connectors.sec_edgar import SECEdgarConnector
from vesper_ingestion.storage.s3_storage import S3Storage

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ],
)

logger = structlog.get_logger()


@click.group()
@click.option("--log-level", default="INFO", help="Logging level")
@click.pass_context
def cli(ctx, log_level):
    """VESPER Data Ingestion Service"""
    ctx.ensure_object(dict)
    ctx.obj["log_level"] = log_level
    
    # Update log level
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer()
        ],
    )


@cli.command()
@click.option("--cik", "-c", multiple=True, required=True, help="Company CIK number(s)")
@click.option("--form-type", "-f", multiple=True, help="Form type(s) to fetch (e.g., 10-K, 10-Q)")
@click.option("--start-date", "-s", help="Start date (YYYY-MM-DD)")
@click.option("--end-date", "-e", help="End date (YYYY-MM-DD)")
@click.option("--max-per-cik", "-m", default=10, help="Maximum filings per CIK")
@click.option("--download/--no-download", default=True, help="Download filing content")
@click.option("--storage-prefix", default="bronze", help="Storage prefix (default: bronze)")
@click.pass_context
def fetch(
    ctx,
    cik: tuple,
    form_type: tuple,
    start_date: Optional[str],
    end_date: Optional[str],
    max_per_cik: int,
    download: bool,
    storage_prefix: str
):
    """
    Fetch SEC EDGAR filings and store in Bronze layer
    
    Examples:
    
        # Fetch latest 10-K filings for Apple
        vesper-ingest fetch -c 0000320193 -f 10-K -m 5
        
        # Fetch multiple companies and form types
        vesper-ingest fetch -c 0000320193 -c 0001018724 -f 10-K -f 10-Q
        
        # Fetch filings within a date range
        vesper-ingest fetch -c 0000320193 -f 10-K -s 2023-01-01 -e 2023-12-31
    """
    logger.info(
        "starting_ingestion_job",
        ciks=list(cik),
        form_types=list(form_type) if form_type else None,
        start_date=start_date,
        end_date=end_date,
        max_per_cik=max_per_cik
    )
    
    # Load configuration
    config = get_config()
    
    # Initialize connector
    connector = SECEdgarConnector(
        user_agent=config.sec_edgar.user_agent,
        rate_limit_delay=1.0 / config.sec_edgar.rate_limit  # Convert rate to delay
    )
    
    # Validate connection
    if not connector.validate_connection():
        logger.error("failed_to_connect_to_sec_edgar")
        click.echo("❌ Failed to connect to SEC EDGAR API", err=True)
        ctx.exit(1)
    
    click.echo("✅ Connected to SEC EDGAR API")
    
    # Fetch filings
    try:
        # Initialize database client
        from vesper_ingestion.db.docker_db import DockerDBClient
        db = DockerDBClient()
        
        # Create ingestion job record
        job_id = db.create_job(
            source="sec-edgar",
            cik_list=list(cik),
            form_types=list(form_type) if form_type else None,
            start_date=start_date,
            end_date=end_date
        )
        
        if job_id:
            logger.info("created_ingestion_job", job_id=job_id)
        
        filings = connector.fetch_filings(
            cik_list=list(cik),
            form_types=list(form_type) if form_type else None,
            start_date=start_date,
            end_date=end_date,
            max_per_cik=max_per_cik
        )
        
        click.echo(f"✅ Fetched {len(filings)} filing(s)")
        
        if not filings:
            logger.info("no_filings_found")
            click.echo("ℹ️  No filings found matching criteria")
            
            # Complete job
            if job_id:
                db.complete_job(job_id, "completed", 0, 0, 0)
            
            return
        
        # Initialize storage
        storage = S3Storage(
            bucket_name=config.storage.s3_bucket_name,
            endpoint_url=config.storage.s3_endpoint_url,
            aws_access_key_id=config.storage.aws_access_key_id,
            aws_secret_access_key=config.storage.aws_secret_access_key,
            region_name=config.storage.aws_region
        )
        
        # Upload filings
        click.echo(f"📤 Uploading {len(filings)} filing(s) to storage...")
        
        successful = 0
        failed = 0
        skipped = 0
        
        with click.progressbar(filings, label="Uploading") as bar:
            for filing in bar:
                try:
                    # Check if already exists in database
                    if db.filing_exists(filing.accession_number):
                        skipped += 1
                        logger.info(
                            "filing_already_exists",
                            accession_number=filing.accession_number
                        )
                        continue
                    
                    # Upload to S3
                    key = storage.upload_filing(filing, prefix=storage_prefix)
                    
                    # Save to database
                    db_success = db.insert_filing(
                        cik=filing.cik,
                        company_name=filing.company_name,
                        accession_number=filing.accession_number,
                        form_type=filing.form_type,
                        filing_date=filing.filing_date,
                        report_date=filing.report_date,
                        s3_key=key,
                        document_url=filing.document_url,
                        file_size=filing.file_size,
                        content_length=filing.content_length,
                        filing_metadata=filing.model_dump(exclude={'html_content', 'text_content'})
                    )
                    
                    if db_success:
                        successful += 1
                        logger.info(
                            "uploaded_filing",
                            cik=filing.cik,
                            accession_number=filing.accession_number,
                            key=key
                        )
                    else:
                        failed += 1
                        logger.error(
                            "failed_to_save_to_database",
                            cik=filing.cik,
                            accession_number=filing.accession_number
                        )
                        
                except Exception as e:
                    failed += 1
                    logger.error(
                        "failed_to_upload_filing",
                        cik=filing.cik,
                        accession_number=filing.accession_number,
                        error=str(e)
                    )
        
        # Summary
        if skipped > 0:
            click.echo(f"\n✅ Upload complete: {successful} successful, {failed} failed, {skipped} skipped (already exists)")
        else:
            click.echo(f"\n✅ Upload complete: {successful} successful, {failed} failed")
        
        # Complete job
        if job_id:
            db.complete_job(
                job_id=job_id,
                status="completed" if failed == 0 else "partial",
                total_filings=len(filings),
                successful_filings=successful,
                failed_filings=failed
            )
        
        logger.info(
            "ingestion_job_complete",
            total=len(filings),
            successful=successful,
            failed=failed,
            skipped=skipped
        )
        
    except Exception as e:
        logger.error("ingestion_job_failed", error=str(e))
        click.echo(f"❌ Ingestion job failed: {e}", err=True)
        ctx.exit(1)


@cli.command()
@click.option("--prefix", "-p", default="", help="Prefix to list (e.g., bronze/sec-edgar)")
@click.pass_context
def list_filings(ctx, prefix: str):
    """
    List filings in storage
    
    Examples:
    
        # List all filings
        vesper-ingest list-filings
        
        # List filings in bronze layer
        vesper-ingest list-filings -p bronze
        
        # List filings for specific company
        vesper-ingest list-filings -p bronze/sec-edgar/320193
    """
    config = get_config()
    
    # Initialize storage
    storage = S3Storage(
        bucket_name=config.storage.s3_bucket_name,
        endpoint_url=config.storage.s3_endpoint_url,
        aws_access_key_id=config.storage.aws_access_key_id,
        aws_secret_access_key=config.storage.aws_secret_access_key,
        region_name=config.storage.aws_region
    )
    
    try:
        keys = storage.list_filings(prefix=prefix)
        
        if not keys:
            click.echo("No filings found")
            return
        
        click.echo(f"Found {len(keys)} filing(s):\n")
        
        for key in keys:
            click.echo(f"  • {key}")
        
    except Exception as e:
        logger.error("failed_to_list_filings", error=str(e))
        click.echo(f"❌ Failed to list filings: {e}", err=True)
        ctx.exit(1)


@cli.command()
@click.option("--key", "-k", required=True, help="Filing key to retrieve")
@click.option("--output", "-o", help="Output file path (default: stdout)")
@click.pass_context
def get_filing(ctx, key: str, output: Optional[str]):
    """
    Retrieve a filing from storage
    
    Examples:
    
        # Print filing to stdout
        vesper-ingest get-filing -k bronze/sec-edgar/320193/10-K/0000320193-23-000077
        
        # Save to file
        vesper-ingest get-filing -k bronze/sec-edgar/320193/10-K/0000320193-23-000077 -o filing.html
    """
    config = get_config()
    
    # Initialize storage
    storage = S3Storage(
        bucket_name=config.storage.s3_bucket_name,
        endpoint_url=config.storage.s3_endpoint_url,
        aws_access_key_id=config.storage.aws_access_key_id,
        aws_secret_access_key=config.storage.aws_secret_access_key,
        region_name=config.storage.aws_region
    )
    
    try:
        filing = storage.download_filing(key)
        
        if output:
            with open(output, "w") as f:
                f.write(filing.html_content or "")
            click.echo(f"✅ Saved filing to {output}")
        else:
            click.echo(filing.html_content or "")
        
    except Exception as e:
        logger.error("failed_to_get_filing", key=key, error=str(e))
        click.echo(f"❌ Failed to retrieve filing: {e}", err=True)
        ctx.exit(1)


@cli.command()
@click.pass_context
def validate(ctx):
    """
    Validate connections to external services
    
    Checks connectivity to:
    - SEC EDGAR API
    - S3/MinIO storage
    - PostgreSQL database
    """
    config = get_config()
    
    click.echo("🔍 Validating connections...\n")
    
    # Validate SEC EDGAR
    click.echo("Checking SEC EDGAR API...")
    connector = SECEdgarConnector(
        user_agent=config.sec_edgar.user_agent,
        rate_limit_delay=1.0 / config.sec_edgar.rate_limit  # Convert rate to delay
    )
    
    if connector.validate_connection():
        click.echo("  ✅ SEC EDGAR API connection OK\n")
    else:
        click.echo("  ❌ SEC EDGAR API connection FAILED\n", err=True)
    
    # Validate S3/MinIO
    click.echo("Checking S3/MinIO storage...")
    try:
        storage = S3Storage(
            bucket_name=config.storage.s3_bucket_name,
            endpoint_url=config.storage.s3_endpoint_url,
            aws_access_key_id=config.storage.aws_access_key_id,
            aws_secret_access_key=config.storage.aws_secret_access_key,
            region_name=config.storage.aws_region
        )
        click.echo(f"  ✅ S3/MinIO storage OK (bucket: {config.storage.s3_bucket_name})\n")
    except Exception as e:
        click.echo(f"  ❌ S3/MinIO storage FAILED: {e}\n", err=True)
    
    # Validate PostgreSQL
    click.echo("Checking PostgreSQL database...")
    try:
        from vesper_ingestion.db.session import get_engine
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            click.echo(f"  ✅ PostgreSQL connection OK")
            click.echo(f"     Version: {version[:50]}...\n")
    except Exception as e:
        click.echo(f"  ❌ PostgreSQL connection FAILED: {e}\n", err=True)
    
    click.echo("✅ Validation complete")


@cli.command()
@click.option("--drop", is_flag=True, help="Drop existing tables before creating")
@click.pass_context
def init_db(ctx, drop):
    """
    Initialize database tables
    
    Creates the bronze schema and all required tables.
    
    Examples:
        # Create tables
        vesper-ingest init-db
        
        # Drop and recreate tables (WARNING: deletes all data)
        vesper-ingest init-db --drop
    """
    from vesper_ingestion.db.session import get_engine
    from vesper_ingestion.db.models import Base
    from sqlalchemy import text
    
    click.echo("🗄️  Initializing database...\n")
    
    engine = get_engine()
    
    try:
        # Create bronze schema
        click.echo("Creating bronze schema...")
        with engine.connect() as conn:
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS bronze"))
            conn.commit()
        click.echo("  ✅ Schema created\n")
        
        # Drop tables if requested
        if drop:
            click.echo("⚠️  Dropping existing tables...")
            if click.confirm("Are you sure? This will delete ALL data!", default=False):
                Base.metadata.drop_all(bind=engine)
                click.echo("  ✅ Tables dropped\n")
            else:
                click.echo("  ⏭️  Skipped\n")
        
        # Create tables
        click.echo("Creating tables...")
        Base.metadata.create_all(bind=engine)
        click.echo("  ✅ Tables created\n")
        
        # List created tables
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names(schema='bronze')
        
        click.echo(f"📊 Created {len(tables)} tables in bronze schema:")
        for table in tables:
            click.echo(f"  • {table}")
        
        click.echo("\n✅ Database initialized successfully!")
        
    except Exception as e:
        logger.error("database_init_failed", error=str(e))
        click.echo(f"\n❌ Database initialization failed: {e}", err=True)
        ctx.exit(1)


@cli.command()
@click.pass_context
def validate(ctx):
    """
    Validate connections to external services
    
    Checks connectivity to:
    - SEC EDGAR API
    - S3/MinIO storage
    - PostgreSQL database
    """
    config = get_config()
    
    click.echo("🔍 Validating connections...\n")
    
    # Validate SEC EDGAR
    click.echo("Checking SEC EDGAR API...")
    connector = SECEdgarConnector(
        user_agent=config.sec_edgar.user_agent,
        rate_limit_delay=1.0 / config.sec_edgar.rate_limit  # Convert rate to delay
    )
    
    if connector.validate_connection():
        click.echo("  ✅ SEC EDGAR API connection OK\n")
    else:
        click.echo("  ❌ SEC EDGAR API connection FAILED\n", err=True)
    
    # Validate S3/MinIO
    click.echo("Checking S3/MinIO storage...")
    try:
        storage = S3Storage(
            bucket_name=config.storage.s3_bucket_name,
            endpoint_url=config.storage.s3_endpoint_url,
            aws_access_key_id=config.storage.aws_access_key_id,
            aws_secret_access_key=config.storage.aws_secret_access_key,
            region_name=config.storage.aws_region
        )
        click.echo(f"  ✅ S3/MinIO storage OK (bucket: {config.storage.s3_bucket_name})\n")
    except Exception as e:
        click.echo(f"  ❌ S3/MinIO storage FAILED: {e}\n", err=True)
    
    # TODO: Validate PostgreSQL when we add database operations
    
    click.echo("✅ Validation complete")


@cli.command()
@click.option("--limit", "-l", default=10, help="Number of filings to show")
@click.pass_context
def query(ctx, limit: int):
    """
    Query recently ingested filings from database
    
    Examples:
        # Show last 10 filings
        vesper-ingest query
        
        # Show last 20 filings
        vesper-ingest query --limit 20
    """
    from vesper_ingestion.db.docker_db import DockerDBClient
    
    click.echo(f"📊 Querying last {limit} filings...\n")
    
    try:
        db = DockerDBClient()
        filings = db.get_recent_filings(limit=limit)
        
        if not filings:
            click.echo("No filings found in database")
            return
        
        click.echo(f"Found {len(filings)} filing(s):\n")
        
        # Print table header
        click.echo(f"{'CIK':<12} {'Company':<30} {'Form':<8} {'Date':<12} {'Accession Number':<25}")
        click.echo("-" * 95)
        
        # Print filings
        for filing in filings:
            company = filing['company_name'][:28] + '..' if len(filing['company_name']) > 30 else filing['company_name']
            click.echo(
                f"{filing['cik']:<12} {company:<30} {filing['form_type']:<8} "
                f"{filing['filing_date'][:10]:<12} {filing['accession_number']:<25}"
            )
        
    except Exception as e:
        logger.error("query_failed", error=str(e))
        click.echo(f"❌ Query failed: {e}", err=True)
        ctx.exit(1)


@cli.command()
@click.pass_context
def stats(ctx):
    """
    Show database statistics
    
    Displays:
    - Total filings ingested
    - Filings by form type
    - Total ingestion jobs
    
    Examples:
        vesper-ingest stats
    """
    from vesper_ingestion.db.docker_db import DockerDBClient
    
    click.echo("📊 Database Statistics\n")
    
    try:
        db = DockerDBClient()
        stats_data = db.get_stats()
        
        if not stats_data:
            click.echo("No statistics available")
            return
        
        click.echo(f"Total Filings:     {stats_data.get('total_filings', 0)}")
        click.echo(f"Total Jobs:        {stats_data.get('total_jobs', 0)}\n")
        
        if stats_data.get('filings_by_form'):
            click.echo("Filings by Form Type:")
            for form_type, count in stats_data['filings_by_form'].items():
                click.echo(f"  {form_type:<10} {count:>5}")
        
    except Exception as e:
        logger.error("stats_failed", error=str(e))
        click.echo(f"❌ Failed to get statistics: {e}", err=True)
        ctx.exit(1)


if __name__ == "__main__":
    cli()
