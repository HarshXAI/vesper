#!/usr/bin/env python3
"""
VESPER Demo Seed Script
Generates demo data for 10 SEC filings (AAPL, AMZN, MSFT) with embeddings.

Usage:
    python scripts/demo_seed.py
    python scripts/demo_seed.py --ticker AAPL --count 5
    python scripts/demo_seed.py --regenerate-embeddings
"""

import argparse
import asyncio
import hashlib
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("demo_seed")

# Demo configuration
DEMO_TICKERS = ["AAPL", "AMZN", "MSFT"]
FILINGS_PER_TICKER = 4  # ~10 total filings

# SEC filing types for demo
FILING_TYPES = ["10-K", "10-Q", "8-K"]


@dataclass
class DemoFiling:
    """Represents a demo SEC filing."""
    
    filing_id: str
    ticker: str
    company_name: str
    cik: str
    filing_type: str
    filing_date: str
    period_end: str
    content: str
    sections: list[dict[str, Any]] = field(default_factory=list)
    chunks: list[dict[str, Any]] = field(default_factory=list)
    embedding_ids: list[str] = field(default_factory=list)


# Demo company data
DEMO_COMPANIES = {
    "AAPL": {
        "name": "Apple Inc.",
        "cik": "0000320193",
        "industry": "Technology Hardware",
        "description": "Apple Inc. designs, manufactures, and markets smartphones, personal computers, tablets, wearables, and accessories worldwide.",
    },
    "AMZN": {
        "name": "Amazon.com, Inc.",
        "cik": "0001018724",
        "industry": "Internet Retail",
        "description": "Amazon.com, Inc. engages in the retail sale of consumer products and subscriptions through online and physical stores.",
    },
    "MSFT": {
        "name": "Microsoft Corporation",
        "cik": "0000789019",
        "industry": "Software",
        "description": "Microsoft Corporation develops, licenses, and supports software, services, devices, and solutions worldwide.",
    },
}

# Demo filing content templates
FILING_TEMPLATES = {
    "10-K": {
        "sections": [
            {
                "title": "Business Overview",
                "content": """{company} is a leading {industry} company. For fiscal year {year}, 
the company reported total revenue of ${revenue}B, representing a {growth}% increase year-over-year.
Key business segments include {segments}. The company's strategy focuses on innovation, 
customer experience, and sustainable growth through both organic development and strategic acquisitions.""",
            },
            {
                "title": "Risk Factors",
                "content": """The company faces various risks including: (1) Intense competition in the 
{industry} market from both established players and new entrants; (2) Regulatory changes affecting 
data privacy, antitrust, and international trade; (3) Supply chain disruptions and dependency on 
key suppliers; (4) Cybersecurity threats and the need for continuous security investment;
(5) Economic uncertainty affecting consumer and enterprise spending patterns.""",
            },
            {
                "title": "Financial Performance",
                "content": """For fiscal year {year}, {company} achieved the following results:
- Total Revenue: ${revenue}B (up {growth}% YoY)
- Operating Income: ${op_income}B (operating margin: {op_margin}%)
- Net Income: ${net_income}B
- Earnings Per Share: ${eps}
- Free Cash Flow: ${fcf}B
The company returned ${returned}B to shareholders through dividends and share repurchases.""",
            },
            {
                "title": "Management's Discussion and Analysis",
                "content": """Management believes the company is well-positioned for continued growth.
Key initiatives for {year} include: expanding {initiative1}, investing in {initiative2}, and
enhancing operational efficiency. The company maintains a strong balance sheet with ${cash}B
in cash and investments, providing flexibility for strategic investments and shareholder returns.""",
            },
        ],
    },
    "10-Q": {
        "sections": [
            {
                "title": "Quarterly Financial Summary",
                "content": """For Q{quarter} {year}, {company} reported revenue of ${revenue}B,
representing a {growth}% increase compared to Q{quarter} of the prior year. Gross margin was
{gross_margin}% and operating margin was {op_margin}%. The company generated ${fcf}B in
operating cash flow during the quarter.""",
            },
            {
                "title": "Segment Performance",
                "content": """Revenue by segment for Q{quarter} {year}:
{segment_details}
All segments contributed to year-over-year growth, with particularly strong performance in
{top_segment} driven by {growth_driver}.""",
            },
        ],
    },
    "8-K": {
        "sections": [
            {
                "title": "Current Report",
                "content": """{company} (NASDAQ: {ticker}) announced today that {announcement}.
This {event_type} is expected to {impact}. Management commentary: "{quote}"
The company will provide additional details during {next_event}.""",
            },
        ],
    },
}

# Financial data templates per company
FINANCIAL_DATA = {
    "AAPL": {
        "revenue": 394.3,
        "growth": 8,
        "op_income": 114.3,
        "op_margin": 29,
        "net_income": 96.9,
        "eps": 6.16,
        "fcf": 99.6,
        "returned": 89.0,
        "cash": 166.0,
        "segments": "iPhone, Mac, iPad, Wearables, and Services",
        "initiative1": "AI and machine learning capabilities",
        "initiative2": "services ecosystem",
        "gross_margin": 44,
        "top_segment": "Services",
        "growth_driver": "App Store and subscription growth",
    },
    "AMZN": {
        "revenue": 574.8,
        "growth": 12,
        "op_income": 36.9,
        "op_margin": 6,
        "net_income": 30.4,
        "eps": 2.95,
        "fcf": 35.5,
        "returned": 6.0,
        "cash": 86.0,
        "segments": "Online Stores, AWS, Physical Stores, and Advertising",
        "initiative1": "AWS cloud infrastructure",
        "initiative2": "logistics network optimization",
        "gross_margin": 47,
        "top_segment": "AWS",
        "growth_driver": "enterprise cloud adoption",
    },
    "MSFT": {
        "revenue": 236.6,
        "growth": 16,
        "op_income": 98.5,
        "op_margin": 42,
        "net_income": 82.5,
        "eps": 11.07,
        "fcf": 87.4,
        "returned": 52.0,
        "cash": 111.0,
        "segments": "Productivity, Intelligent Cloud, and Personal Computing",
        "initiative1": "Azure and AI services",
        "initiative2": "Microsoft 365 platform",
        "gross_margin": 70,
        "top_segment": "Intelligent Cloud",
        "growth_driver": "Azure AI and OpenAI partnership",
    },
}


def generate_filing_content(
    ticker: str,
    filing_type: str,
    year: int,
    quarter: int | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Generate realistic filing content from templates."""
    company_data = DEMO_COMPANIES[ticker]
    financial_data = FINANCIAL_DATA[ticker]
    template = FILING_TEMPLATES[filing_type]
    
    sections = []
    full_content = f"# {company_data['name']} - {filing_type}\n\n"
    
    for section_template in template["sections"]:
        # Build context for template
        context = {
            "company": company_data["name"],
            "ticker": ticker,
            "industry": company_data["industry"],
            "year": year,
            "quarter": quarter or 4,
            **financial_data,
        }
        
        # Add 8-K specific content
        if filing_type == "8-K":
            context.update({
                "announcement": f"the appointment of a new Chief AI Officer",
                "event_type": "leadership change",
                "impact": "accelerate the company's AI initiatives",
                "quote": "We are excited to strengthen our leadership team as we continue to innovate.",
                "next_event": "the upcoming earnings call",
            })
        
        # Generate segment details for 10-Q
        if filing_type == "10-Q":
            segments = financial_data["segments"].split(", ")
            segment_lines = []
            for i, seg in enumerate(segments[:4]):
                rev = round(financial_data["revenue"] / 4 / len(segments) * (1 + i * 0.1), 1)
                segment_lines.append(f"- {seg}: ${rev}B")
            context["segment_details"] = "\n".join(segment_lines)
        
        # Format content
        section_content = section_template["content"].format(**context)
        
        sections.append({
            "title": section_template["title"],
            "content": section_content,
            "start_offset": len(full_content),
        })
        
        full_content += f"## {section_template['title']}\n\n{section_content}\n\n"
    
    return full_content, sections


def chunk_content(content: str, sections: list[dict[str, Any]], chunk_size: int = 500) -> list[dict[str, Any]]:
    """Chunk content into overlapping segments for embedding."""
    chunks = []
    chunk_overlap = 100
    
    for section in sections:
        section_text = section["content"]
        section_title = section["title"]
        
        # Split into chunks
        words = section_text.split()
        current_chunk = []
        current_length = 0
        
        for word in words:
            current_chunk.append(word)
            current_length += len(word) + 1
            
            if current_length >= chunk_size:
                chunk_text = " ".join(current_chunk)
                chunk_id = hashlib.sha256(chunk_text.encode()).hexdigest()[:16]
                
                chunks.append({
                    "chunk_id": chunk_id,
                    "section": section_title,
                    "text": chunk_text,
                    "word_count": len(current_chunk),
                    "char_count": len(chunk_text),
                })
                
                # Keep overlap
                overlap_words = int(len(current_chunk) * 0.2)
                current_chunk = current_chunk[-overlap_words:]
                current_length = sum(len(w) + 1 for w in current_chunk)
        
        # Add remaining content
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunk_id = hashlib.sha256(chunk_text.encode()).hexdigest()[:16]
            
            chunks.append({
                "chunk_id": chunk_id,
                "section": section_title,
                "text": chunk_text,
                "word_count": len(current_chunk),
                "char_count": len(chunk_text),
            })
    
    return chunks


def generate_demo_filings(tickers: list[str] | None = None, count_per_ticker: int = FILINGS_PER_TICKER) -> list[DemoFiling]:
    """Generate demo filings for specified tickers."""
    tickers = tickers or DEMO_TICKERS
    filings = []
    
    base_date = datetime(2024, 1, 15)
    
    for ticker in tickers:
        company = DEMO_COMPANIES.get(ticker)
        if not company:
            logger.warning(f"Unknown ticker: {ticker}, skipping")
            continue
        
        for i in range(min(count_per_ticker, len(FILING_TYPES) + 1)):
            filing_type = FILING_TYPES[i % len(FILING_TYPES)]
            filing_date = base_date - timedelta(days=i * 90)
            
            # Determine period
            if filing_type == "10-K":
                year = filing_date.year
                quarter = None
                period_end = datetime(year - 1, 12, 31)
            elif filing_type == "10-Q":
                year = filing_date.year
                quarter = (filing_date.month - 1) // 3 + 1
                period_end = datetime(year, quarter * 3, 30)
            else:  # 8-K
                year = filing_date.year
                quarter = None
                period_end = filing_date
            
            content, sections = generate_filing_content(ticker, filing_type, year, quarter)
            chunks = chunk_content(content, sections)
            
            filing = DemoFiling(
                filing_id=f"{ticker}-{filing_type}-{filing_date.strftime('%Y%m%d')}-{uuid4().hex[:8]}",
                ticker=ticker,
                company_name=company["name"],
                cik=company["cik"],
                filing_type=filing_type,
                filing_date=filing_date.strftime("%Y-%m-%d"),
                period_end=period_end.strftime("%Y-%m-%d"),
                content=content,
                sections=sections,
                chunks=chunks,
            )
            
            filings.append(filing)
            logger.info(f"Generated {filing_type} for {ticker}: {filing.filing_id}")
    
    return filings


async def generate_embeddings(
    chunks: list[dict[str, Any]],
    api_url: str | None = None,
) -> list[str]:
    """Generate embeddings for chunks using the API or mock."""
    api_url = api_url or os.getenv("VESPER_API_URL", "http://localhost:8000")
    embedding_ids = []
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for chunk in chunks:
            try:
                # Try to call embedding API
                response = await client.post(
                    f"{api_url}/api/v1/embeddings",
                    json={
                        "text": chunk["text"],
                        "metadata": {
                            "chunk_id": chunk["chunk_id"],
                            "section": chunk["section"],
                        },
                    },
                )
                
                if response.status_code == 200:
                    result = response.json()
                    embedding_ids.append(result.get("embedding_id", chunk["chunk_id"]))
                else:
                    # Use chunk_id as mock embedding_id
                    embedding_ids.append(f"emb_{chunk['chunk_id']}")
                    
            except Exception as e:
                logger.debug(f"Embedding API not available, using mock: {e}")
                embedding_ids.append(f"emb_{chunk['chunk_id']}")
    
    return embedding_ids


async def seed_database(filings: list[DemoFiling], db_url: str | None = None) -> dict[str, Any]:
    """Seed the database with demo filings."""
    api_url = os.getenv("VESPER_API_URL", "http://localhost:8000")
    results = {
        "filings_created": 0,
        "chunks_created": 0,
        "embeddings_created": 0,
        "errors": [],
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        for filing in filings:
            try:
                # Generate embeddings for chunks
                embedding_ids = await generate_embeddings(filing.chunks, api_url)
                filing.embedding_ids = embedding_ids
                results["embeddings_created"] += len(embedding_ids)
                
                # Try to seed via API
                try:
                    response = await client.post(
                        f"{api_url}/api/v1/demo/seed",
                        json={
                            "filing_id": filing.filing_id,
                            "ticker": filing.ticker,
                            "company_name": filing.company_name,
                            "cik": filing.cik,
                            "filing_type": filing.filing_type,
                            "filing_date": filing.filing_date,
                            "period_end": filing.period_end,
                            "content": filing.content,
                            "sections": filing.sections,
                            "chunks": filing.chunks,
                            "embedding_ids": filing.embedding_ids,
                        },
                    )
                    
                    if response.status_code in (200, 201):
                        results["filings_created"] += 1
                        results["chunks_created"] += len(filing.chunks)
                    else:
                        logger.warning(f"API seed failed for {filing.filing_id}: {response.status_code}")
                        
                except Exception as e:
                    logger.debug(f"API not available, saving to local file: {e}")
                
            except Exception as e:
                results["errors"].append(f"{filing.filing_id}: {str(e)}")
                logger.error(f"Error seeding {filing.filing_id}: {e}")
    
    return results


def save_demo_data(filings: list[DemoFiling], output_dir: Path) -> None:
    """Save demo data to JSON files for offline use."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save individual filings
    for filing in filings:
        filing_path = output_dir / f"{filing.filing_id}.json"
        with open(filing_path, "w") as f:
            json.dump({
                "filing_id": filing.filing_id,
                "ticker": filing.ticker,
                "company_name": filing.company_name,
                "cik": filing.cik,
                "filing_type": filing.filing_type,
                "filing_date": filing.filing_date,
                "period_end": filing.period_end,
                "content": filing.content,
                "sections": filing.sections,
                "chunks": filing.chunks,
                "embedding_ids": filing.embedding_ids,
            }, f, indent=2)
    
    # Save manifest
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump({
            "created_at": datetime.now().isoformat(),
            "filing_count": len(filings),
            "tickers": list(set(f.ticker for f in filings)),
            "filings": [f.filing_id for f in filings],
        }, f, indent=2)
    
    logger.info(f"Saved {len(filings)} filings to {output_dir}")


async def main():
    """Main entry point for demo seeding."""
    parser = argparse.ArgumentParser(description="VESPER Demo Seed Script")
    parser.add_argument("--ticker", type=str, help="Specific ticker to seed (default: all)")
    parser.add_argument("--count", type=int, default=FILINGS_PER_TICKER, help="Filings per ticker")
    parser.add_argument("--regenerate-embeddings", action="store_true", help="Regenerate all embeddings")
    parser.add_argument("--output-dir", type=str, default="data/demo", help="Output directory for demo data")
    parser.add_argument("--seed-db", action="store_true", help="Seed the database via API")
    
    args = parser.parse_args()
    
    tickers = [args.ticker] if args.ticker else DEMO_TICKERS
    output_dir = Path(args.output_dir)
    
    logger.info("=" * 60)
    logger.info("VESPER Demo Seed Script")
    logger.info("=" * 60)
    logger.info(f"Tickers: {', '.join(tickers)}")
    logger.info(f"Filings per ticker: {args.count}")
    logger.info(f"Output directory: {output_dir}")
    logger.info("=" * 60)
    
    # Generate demo filings
    filings = generate_demo_filings(tickers, args.count)
    logger.info(f"Generated {len(filings)} demo filings")
    
    # Save to local files
    save_demo_data(filings, output_dir)
    
    # Optionally seed the database
    if args.seed_db:
        logger.info("Seeding database via API...")
        results = await seed_database(filings)
        logger.info(f"Database seeding complete: {results}")
    
    # Summary
    logger.info("=" * 60)
    logger.info("Demo Seed Complete!")
    logger.info(f"  Filings: {len(filings)}")
    logger.info(f"  Total Chunks: {sum(len(f.chunks) for f in filings)}")
    logger.info(f"  Output: {output_dir}")
    logger.info("=" * 60)
    
    return filings


if __name__ == "__main__":
    asyncio.run(main())
