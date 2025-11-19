"""
CLI for VESPER Document Processing Service
"""
import sys
import click
import structlog
from pathlib import Path
from vesper_processing.html_parser import HTMLParser
from vesper_processing.section_extractor import SectionExtractor
from vesper_processing.config import get_config

# Configure logging to stderr so stdout is clean for JSON output
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr)
)

logger = structlog.get_logger()


@click.group()
@click.version_option()
def cli():
    """VESPER Document Processing Service"""
    pass


@cli.command()
@click.option(
    '--input', '-i',
    type=click.Path(exists=True),
    required=True,
    help='Input HTML file'
)
@click.option(
    '--output', '-o',
    type=click.Path(),
    help='Output text file (optional)'
)
@click.option(
    '--extract-sections/--no-extract-sections',
    default=True,
    help='Extract sections'
)
@click.option(
    '--extract-tables/--no-extract-tables',
    default=True,
    help='Extract tables'
)
@click.option(
    '--classify-tables/--no-classify-tables',
    default=False,
    help='Classify table types (requires --extract-tables)'
)
@click.option(
    '--parse-financials/--no-parse-financials',
    default=False,
    help='Parse financial values from tables (requires --classify-tables)'
)
def parse(input: str, output: str, extract_sections: bool, extract_tables: bool, 
          classify_tables: bool, parse_financials: bool):
    """Parse HTML filing and extract text"""
    try:
        logger.info("starting_parse", input_file=input)
        
        # Read HTML file
        with open(input, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Parse HTML
        parser = HTMLParser(remove_tables=not extract_tables)
        clean_text = parser.parse(html_content)
        
        click.echo(f"✅ Parsed HTML: {len(clean_text)} characters")
        
        # Extract sections
        if extract_sections:
            extractor = SectionExtractor()
            sections = extractor.extract(clean_text)
            click.echo(f"✅ Extracted {len(sections)} sections")
            
            for section in sections:
                click.echo(f"  - {section.title} ({len(section.content)} chars)")
        
        # Extract tables (with optional classification and parsing)
        processed_tables = None
        if extract_tables:
            if classify_tables or parse_financials:
                # Use TableExtractor for classification and financial parsing
                from vesper_processing.table_extractor import TableExtractor
                table_extractor = TableExtractor()
                
                # Validate flag dependencies
                if parse_financials and not classify_tables:
                    click.echo("⚠️  Warning: --parse-financials requires --classify-tables, enabling classification", err=True)
                    classify_tables = True
                
                processed_tables = table_extractor.extract_tables(
                    html_content,
                    classify=classify_tables,
                    parse_financial=parse_financials
                )
                
                click.echo(f"✅ Extracted {len(processed_tables)} tables")
                
                # Show table type summary if classified
                if classify_tables:
                    type_counts = {}
                    for table in processed_tables:
                        table_type = table.table_type or 'other'
                        type_counts[table_type] = type_counts.get(table_type, 0) + 1
                    
                    click.echo("📊 Table types:")
                    for table_type, count in sorted(type_counts.items()):
                        click.echo(f"  - {table_type}: {count}")
                
                # Show table details
                for table in processed_tables:
                    caption_text = table.caption or f"Table {table.table_id}"
                    type_info = f" [{table.table_type}]" if classify_tables else ""
                    parsed_info = " (parsed)" if parse_financials and table.metadata.get("parsed_values") else ""
                    click.echo(f"  - {caption_text}{type_info} ({len(table.rows)} rows){parsed_info}")
            else:
                # Use basic HTMLParser extraction
                tables = parser.extract_tables(html_content)
                click.echo(f"✅ Extracted {len(tables)} tables")
                
                for idx, (caption, rows) in enumerate(tables):
                    caption_text = caption or f"Table {idx + 1}"
                    click.echo(f"  - {caption_text} ({len(rows)} rows)")
        
        # Save output
        if output:
            import json
            from pathlib import Path
            
            output_path = Path(output)
            
            # Save text content
            with open(output, 'w', encoding='utf-8') as f:
                f.write(clean_text)
            click.echo(f"✅ Saved text to {output}")
            
            # Save classified/parsed tables to JSON if enabled
            if processed_tables and (classify_tables or parse_financials):
                tables_output = output_path.with_suffix('.tables.json')
                with open(tables_output, 'w', encoding='utf-8') as f:
                    json.dump([t.model_dump() for t in processed_tables], f, indent=2)
                click.echo(f"✅ Saved tables to {tables_output}")
        else:
            # Print preview
            click.echo("\n" + "="*80)
            click.echo("TEXT PREVIEW (first 1000 chars):")
            click.echo("="*80)
            click.echo(clean_text[:1000])
            click.echo("...")
            
            # Print table summary if classified
            if processed_tables and classify_tables:
                click.echo("\n" + "="*80)
                click.echo("PRIMARY FINANCIAL STATEMENTS:")
                click.echo("="*80)
                for table in processed_tables:
                    if table.table_type in ['balance_sheet', 'income_statement', 'cash_flow', 'shareholders_equity']:
                        click.echo(f"  ✓ {table.table_type.upper()}: {table.caption or 'No caption'}")
        
        logger.info("parse_complete", output_file=output, classified_tables=classify_tables, parsed_financials=parse_financials)
        
    except Exception as e:
        logger.error("parse_failed", error=str(e))
        click.echo(f"❌ Error: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.option(
    '--input', '-i',
    type=click.Path(exists=True),
    required=True,
    help='Input HTML file'
)
@click.option(
    '--section', '-s',
    help='Section to extract (e.g., "Item 1", "Item 7")'
)
def extract(input: str, section: str):
    """Extract specific section from filing"""
    try:
        logger.info("starting_extraction", input_file=input, section=section)
        
        # Read and parse
        with open(input, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        parser = HTMLParser()
        clean_text = parser.parse(html_content)
        
        # Extract sections
        extractor = SectionExtractor()
        sections = extractor.extract(clean_text)
        
        if not sections:
            click.echo("⚠️  No sections found")
            return
        
        # Filter by section if specified
        if section:
            sections = [s for s in sections if section.lower() in s.title.lower()]
            if not sections:
                click.echo(f"⚠️  Section '{section}' not found")
                return
        
        # Display sections
        for sec in sections:
            click.echo(f"\n{'='*80}")
            click.echo(f"SECTION: {sec.title}")
            click.echo(f"Type: {sec.section_type}")
            click.echo(f"Length: {len(sec.content)} characters")
            click.echo(f"{'='*80}\n")
            click.echo(sec.content[:2000])  # Preview
            if len(sec.content) > 2000:
                click.echo(f"\n... ({len(sec.content) - 2000} more characters)")
        
        logger.info("extraction_complete", sections_found=len(sections))
        
    except Exception as e:
        logger.error("extraction_failed", error=str(e))
        click.echo(f"❌ Error: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.option(
    '--input', '-i',
    type=click.Path(exists=True),
    required=True,
    help='Input HTML file'
)
@click.option(
    '--format', '-f',
    type=click.Choice(['text', 'csv', 'json']),
    default='text',
    help='Output format'
)
def tables(input: str, format: str):
    """Extract tables from filing"""
    try:
        logger.info("starting_table_extraction", input_file=input)
        
        # Read HTML
        with open(input, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Extract tables
        parser = HTMLParser()
        tables = parser.extract_tables(html_content)
        
        if not tables:
            click.echo("⚠️  No tables found")
            return
        
        click.echo(f"✅ Found {len(tables)} tables\n")
        
        # Display based on format
        if format == 'text':
            for idx, (caption, rows) in enumerate(tables):
                click.echo(f"{'='*80}")
                click.echo(f"TABLE {idx + 1}: {caption or 'Untitled'}")
                click.echo(f"{'='*80}")
                
                for row in rows[:5]:  # Show first 5 rows
                    click.echo(" | ".join(str(cell) for cell in row))
                
                if len(rows) > 5:
                    click.echo(f"... ({len(rows) - 5} more rows)")
                click.echo()
        
        elif format == 'csv':
            import csv
            import sys
            writer = csv.writer(sys.stdout)
            for caption, rows in tables:
                if caption:
                    writer.writerow([f"# {caption}"])
                for row in rows:
                    writer.writerow(row)
                writer.writerow([])  # Blank line between tables
        
        elif format == 'json':
            import json
            output = []
            for idx, (caption, rows) in enumerate(tables):
                output.append({
                    'table_id': idx,
                    'caption': caption,
                    'rows': rows,
                    'row_count': len(rows)
                })
            click.echo(json.dumps(output, indent=2))
        
        logger.info("table_extraction_complete", table_count=len(tables))
        
    except Exception as e:
        logger.error("table_extraction_failed", error=str(e))
        click.echo(f"❌ Error: {e}", err=True)
        raise click.Abort()


@cli.command('financial-tables')
@click.option(
    '--input', '-i',
    type=click.Path(exists=True),
    required=True,
    help='Input HTML file'
)
@click.option(
    '--parse-values/--no-parse-values',
    default=True,
    help='Parse financial values'
)
@click.option(
    '--format', '-f',
    type=click.Choice(['text', 'json']),
    default='text',
    help='Output format'
)
def financial_tables(input: str, parse_values: bool, format: str):
    """Extract and classify financial tables"""
    try:
        from vesper_processing.table_extractor import TableExtractor
        import json
        
        logger.info("starting_financial_table_extraction", input_file=input)
        
        # Read HTML file
        with open(input, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Extract tables
        extractor = TableExtractor()
        
        if format == 'json':
            # Extract all tables
            tables = extractor.extract_tables(
                html_content,
                classify=True,
                parse_financial=parse_values
            )
            
            # Convert to dict
            output = [
                {
                    'table_id': t.table_id,
                    'caption': t.caption,
                    'table_type': t.table_type,
                    'headers': t.headers,
                    'row_count': len(t.rows),
                    'metadata': t.metadata
                }
                for t in tables
            ]
            
            click.echo(json.dumps(output, indent=2))
        else:
            # Extract financial statements
            statements = extractor.extract_financial_statements(html_content)
            
            click.echo("\n" + "=" * 80)
            click.echo("FINANCIAL STATEMENTS")
            click.echo("=" * 80 + "\n")
            
            for name, table in statements.items():
                if table:
                    click.echo(f"✅ {name.replace('_', ' ').title()}")
                    click.echo(f"   Table ID: {table.table_id}")
                    click.echo(f"   Caption: {table.caption}")
                    click.echo(f"   Rows: {len(table.rows)}")
                    if 'periods' in table.metadata:
                        click.echo(f"   Periods: {', '.join(table.metadata['periods'])}")
                    click.echo()
                else:
                    click.echo(f"❌ {name.replace('_', ' ').title()}: Not found")
                    click.echo()
            
            # Show all classified tables
            all_tables = extractor.extract_tables(html_content, classify=True, parse_financial=False)
            
            click.echo("\n" + "=" * 80)
            click.echo(f"ALL CLASSIFIED TABLES ({len(all_tables)} total)")
            click.echo("=" * 80 + "\n")
            
            # Group by type
            by_type = {}
            for table in all_tables:
                table_type = table.table_type or 'other'
                if table_type not in by_type:
                    by_type[table_type] = []
                by_type[table_type].append(table)
            
            for table_type, tables in sorted(by_type.items()):
                click.echo(f"{table_type.replace('_', ' ').title()}: {len(tables)} tables")
                for table in tables[:3]:  # Show first 3
                    caption_preview = (table.caption[:60] + '...') if table.caption and len(table.caption) > 60 else table.caption
                    click.echo(f"  • {table.table_id}: {caption_preview or '(no caption)'}")
                if len(tables) > 3:
                    click.echo(f"  ... and {len(tables) - 3} more")
                click.echo()
        
        logger.info("financial_table_extraction_complete")
        
    except Exception as e:
        logger.error("financial_table_extraction_failed", error=str(e))
        click.echo(f"❌ Error: {e}", err=True)
        raise click.Abort()


@cli.command('silver-transform')
@click.option(
    '--input', '-i',
    type=click.Path(exists=True),
    required=True,
    help='Input Bronze HTML file'
)
@click.option(
    '--metadata', '-m',
    type=click.Path(exists=True),
    help='Input metadata JSON file (optional)'
)
@click.option(
    '--output', '-o',
    type=click.Path(),
    required=True,
    help='Output Silver JSON file'
)
@click.option(
    '--bronze-path',
    type=str,
    help='S3 path to Bronze layer source (for provenance)'
)
def silver_transform_command(input: str, metadata: str, output: str, bronze_path: str):
    """Transform Bronze filing to Silver layer"""
    try:
        import json
        from vesper_processing.transformers import SilverTransformer
        
        logger.info("starting_silver_transform", input_file=input, output_file=output)
        
        # Read HTML content
        with open(input, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Read metadata if provided
        metadata_dict = {}
        if metadata:
            with open(metadata, 'r', encoding='utf-8') as f:
                metadata_dict = json.load(f)
        
        # Create Bronze filing dict
        bronze_filing = {
            'html_content': html_content,
            'metadata': metadata_dict
        }
        
        # Transform to Silver
        transformer = SilverTransformer()
        silver_filing = transformer.transform(bronze_filing, bronze_path or input)
        
        # Write output
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(silver_filing.to_dict(), f, indent=2)
        
        # Display summary
        click.echo(f"✅ Silver transformation complete")
        click.echo(f"   Filing ID: {silver_filing.filing_id}")
        click.echo(f"   Ticker: {silver_filing.ticker or 'N/A'}")
        click.echo(f"   Company: {silver_filing.company_name or 'N/A'}")
        click.echo(f"   Form Type: {silver_filing.form_type or 'N/A'}")
        click.echo(f"   Text Length: {silver_filing.text_length:,} chars")
        click.echo(f"   Word Count: {silver_filing.word_count:,}")
        click.echo(f"   Sections: {silver_filing.section_count}")
        click.echo(f"   Tables: {silver_filing.table_count}")
        click.echo(f"   Has Financials: {'Yes' if silver_filing.has_financials else 'No'}")
        click.echo(f"   Quality Score: {silver_filing.quality_score:.2f}")
        
        if silver_filing.has_parsing_errors:
            click.echo(f"   ⚠️  Parsing Errors: {len(transformer.errors)}")
            for error in transformer.errors[:3]:
                click.echo(f"      - {error}")
        
        logger.info("silver_transform_complete", 
                   filing_id=silver_filing.filing_id,
                   quality_score=silver_filing.quality_score)
        
    except Exception as e:
        logger.error("silver_transform_failed", error=str(e))
        click.echo(f"❌ Error: {e}", err=True)
        raise click.Abort()


@cli.command('gold-aggregate')
@click.option(
    '-i', '--input',
    required=True,
    help='Input Silver JSON file'
)
@click.option(
    '-o', '--output',
    required=True,
    help='Output Gold JSON file'
)
def gold_aggregate_command(input: str, output: str):
    """Aggregate Silver filing into Gold KPIs"""
    
    try:
        import json
        from vesper_processing.transformers.gold_aggregator import GoldAggregator
        
        logger.info("starting_gold_aggregation", input_file=input, output_file=output)
        
        # Load Silver filing
        click.echo(f"📥 Loading Silver filing from: {input}")
        with open(input, 'r') as f:
            silver_filing = json.load(f)
        
        # Aggregate to Gold
        click.echo(f"🔄 Aggregating KPIs...")
        aggregator = GoldAggregator()
        gold_kpis = aggregator.aggregate(silver_filing)
        
        # Save output
        click.echo(f"💾 Saving Gold KPIs to: {output}")
        output_data = {
            'filing_id': silver_filing.get('filing_id'),
            'ticker': silver_filing.get('ticker'),
            'kpis': {
                'revenue': [k.to_dict() for k in gold_kpis.get('revenue', [])],
                'gross_margin': [k.to_dict() for k in gold_kpis.get('gross_margin', [])],
                'operating_income': [k.to_dict() for k in gold_kpis.get('operating_income', [])],
                'eps': [k.to_dict() for k in gold_kpis.get('eps', [])],
                'free_cash_flow': [k.to_dict() for k in gold_kpis.get('free_cash_flow', [])],
            },
            'summary': {
                'revenue_count': len(gold_kpis.get('revenue', [])),
                'gross_margin_count': len(gold_kpis.get('gross_margin', [])),
                'operating_income_count': len(gold_kpis.get('operating_income', [])),
                'eps_count': len(gold_kpis.get('eps', [])),
                'free_cash_flow_count': len(gold_kpis.get('free_cash_flow', [])),
            }
        }
        
        with open(output, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        click.echo(f"✅ Gold aggregation complete")
        click.echo(f"   Filing: {silver_filing.get('filing_id')}")
        click.echo(f"   Ticker: {silver_filing.get('ticker')}")
        click.echo(f"   Revenue KPIs: {len(gold_kpis.get('revenue', []))}")
        click.echo(f"   Gross Margin KPIs: {len(gold_kpis.get('gross_margin', []))}")
        click.echo(f"   Operating Income KPIs: {len(gold_kpis.get('operating_income', []))}")
        click.echo(f"   EPS KPIs: {len(gold_kpis.get('eps', []))}")
        click.echo(f"   Free Cash Flow KPIs: {len(gold_kpis.get('free_cash_flow', []))}")
        
        logger.info("gold_aggregation_complete", filing_id=silver_filing.get('filing_id'))
        
    except Exception as e:
        logger.error("gold_aggregation_failed", error=str(e))
        click.echo(f"❌ Error: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.option(
    '--input', '-i',
    type=click.Path(exists=True),
    required=True,
    help='Input document file (text or JSON)'
)
@click.option(
    '--output', '-o',
    type=click.Path(),
    required=True,
    help='Output JSON file with chunks'
)
@click.option(
    '--doc-id',
    help='Document ID (generated if not provided)'
)
@click.option(
    '--target-tokens',
    type=int,
    default=300,
    help='Target tokens per chunk (default: 300)'
)
@click.option(
    '--min-tokens',
    type=int,
    default=200,
    help='Minimum tokens per chunk (default: 200)'
)
@click.option(
    '--max-tokens',
    type=int,
    default=400,
    help='Maximum tokens per chunk (default: 400)'
)
@click.option(
    '--overlap',
    type=int,
    default=50,
    help='Overlap tokens between chunks (default: 50)'
)
def chunk(input, output, doc_id, target_tokens, min_tokens, max_tokens, overlap):
    """
    Chunk document into semantic chunks for embedding.
    
    Chunks document while respecting semantic boundaries (headings, paragraphs,
    tables) and maintaining 200-400 token chunks suitable for embedding models.
    
    Example:
        vesper-process chunk -i document.txt -o chunks.json --target-tokens 300
    """
    from vesper_processing.chunking import SemanticChunker
    import json
    
    logger.info("chunking_started", input=input, output=output)
    
    try:
        # Read input
        with open(input, 'r') as f:
            content = f.read()
        
        # Try to parse as JSON first
        try:
            data = json.loads(content)
            if isinstance(data, dict) and 'text' in data:
                text = data['text']
                if not doc_id:
                    doc_id = data.get('id') or data.get('doc_id')
                metadata = {k: v for k, v in data.items() if k not in ['text', 'id', 'doc_id']}
            else:
                text = content
                metadata = {}
        except json.JSONDecodeError:
            # Not JSON, treat as plain text
            text = content
            metadata = {}
        
        # Create chunker
        chunker = SemanticChunker(
            target_tokens=target_tokens,
            min_tokens=min_tokens,
            max_tokens=max_tokens,
            overlap_tokens=overlap
        )
        
        # Chunk document
        chunks = chunker.chunk_document(text, doc_id=doc_id, metadata=metadata)
        
        # Convert to output format
        output_data = {
            'doc_id': chunks[0].doc_id if chunks else None,
            'chunk_count': len(chunks),
            'total_tokens': sum(c.token_count for c in chunks),
            'avg_tokens': sum(c.token_count for c in chunks) / len(chunks) if chunks else 0,
            'chunks': [c.to_dict() for c in chunks]
        }
        
        # Write output
        with open(output, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        click.echo(f"✅ Chunking complete")
        click.echo(f"   Document ID: {output_data['doc_id']}")
        click.echo(f"   Chunks: {output_data['chunk_count']}")
        click.echo(f"   Total tokens: {output_data['total_tokens']}")
        click.echo(f"   Avg tokens/chunk: {output_data['avg_tokens']:.1f}")
        
        logger.info("chunking_complete", 
                   doc_id=output_data['doc_id'],
                   chunks=output_data['chunk_count'],
                   total_tokens=output_data['total_tokens'])
        
    except Exception as e:
        logger.error("chunking_failed", error=str(e))
        click.echo(f"❌ Error: {e}", err=True)
        raise click.Abort()


if __name__ == '__main__':
    cli()
