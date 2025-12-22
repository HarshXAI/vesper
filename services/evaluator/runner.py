"""
VESPER Evaluation Runner
=========================

Standalone script for running VESPER evaluation suite.
Can be invoked from Airflow DAGs or run directly.

Usage:
    python runner.py --eval-type all --output-dir ./results
    python runner.py --eval-type retrieval --queries ./queries.jsonl
    python runner.py --eval-type generation --sample-size 20
"""

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==============================================================================
# Configuration
# ==============================================================================

@dataclass
class EvalConfig:
    """Evaluation configuration."""
    api_base_url: str = os.getenv("VESPER_API_URL", "http://localhost:8000")
    mlflow_tracking_uri: str = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
    queries_path: str = os.getenv("EVAL_QUERIES_PATH", "./data/eval/queries.jsonl")
    output_dir: str = os.getenv("EVAL_OUTPUT_DIR", "./results")
    sample_size: int = int(os.getenv("EVAL_SAMPLE_SIZE", "50"))
    timeout_seconds: int = int(os.getenv("EVAL_TIMEOUT", "120"))
    
    # Quality thresholds
    ndcg10_threshold: float = 0.75
    recall5_threshold: float = 0.85
    mrr_threshold: float = 0.6
    faithfulness_threshold: float = 0.7


@dataclass
class EvalQuery:
    """Single evaluation query."""
    id: str
    query: str
    expected_doc_ids: list[str] = field(default_factory=list)
    category: str = "general"
    metadata: dict = field(default_factory=dict)


@dataclass
class RetrievalResult:
    """Result from a single retrieval evaluation."""
    query_id: str
    ndcg10: float
    recall5: float
    recall10: float
    mrr: float
    latency_ms: float
    num_retrieved: int
    error: Optional[str] = None


@dataclass
class GenerationResult:
    """Result from a single generation evaluation."""
    query_id: str
    faithfulness: float
    relevance: float
    latency_ms: float
    answer_length: int
    num_citations: int
    error: Optional[str] = None


@dataclass
class EvalReport:
    """Complete evaluation report."""
    timestamp: str
    config: dict
    retrieval_metrics: dict = field(default_factory=dict)
    generation_metrics: dict = field(default_factory=dict)
    retrieval_details: list[dict] = field(default_factory=list)
    generation_details: list[dict] = field(default_factory=list)
    alerts: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0


# ==============================================================================
# Evaluation Functions
# ==============================================================================

class VesperEvaluator:
    """VESPER evaluation runner."""
    
    def __init__(self, config: EvalConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "VesperEvaluator/1.0"
        })
    
    def load_queries(self, path: Optional[str] = None) -> list[EvalQuery]:
        """Load evaluation queries from JSONL file."""
        queries_path = Path(path or self.config.queries_path)
        
        if not queries_path.exists():
            logger.warning(f"Queries file not found: {queries_path}")
            return self._get_sample_queries()
        
        queries = []
        with open(queries_path, 'r') as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    queries.append(EvalQuery(**data))
        
        logger.info(f"Loaded {len(queries)} queries from {queries_path}")
        return queries
    
    def _get_sample_queries(self) -> list[EvalQuery]:
        """Return sample queries for testing."""
        return [
            EvalQuery(
                id="sample-1",
                query="What are the key risk factors?",
                expected_doc_ids=["doc-001"],
                category="risk"
            ),
            EvalQuery(
                id="sample-2",
                query="What is the revenue trend?",
                expected_doc_ids=["doc-002"],
                category="financials"
            ),
        ]
    
    def health_check(self) -> bool:
        """Check if the API is healthy."""
        try:
            response = self.session.get(
                f"{self.config.api_base_url}/health",
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data.get("status") == "healthy"
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def evaluate_retrieval(self, query: EvalQuery) -> RetrievalResult:
        """Evaluate retrieval for a single query."""
        start_time = time.time()
        
        try:
            response = self.session.post(
                f"{self.config.api_base_url}/v1/retrieve",
                json={"query": query.query, "top_k": 10},
                timeout=self.config.timeout_seconds
            )
            latency_ms = (time.time() - start_time) * 1000
            
            if response.status_code != 200:
                return RetrievalResult(
                    query_id=query.id,
                    ndcg10=0, recall5=0, recall10=0, mrr=0,
                    latency_ms=latency_ms, num_retrieved=0,
                    error=f"HTTP {response.status_code}"
                )
            
            result = response.json()
            retrieved_ids = [doc.get("id", "") for doc in result.get("documents", [])]
            expected_ids = set(query.expected_doc_ids)
            
            # Calculate metrics
            ndcg10 = self._calculate_ndcg(retrieved_ids[:10], expected_ids)
            recall5 = self._calculate_recall(retrieved_ids[:5], expected_ids)
            recall10 = self._calculate_recall(retrieved_ids[:10], expected_ids)
            mrr = self._calculate_mrr(retrieved_ids, expected_ids)
            
            return RetrievalResult(
                query_id=query.id,
                ndcg10=ndcg10,
                recall5=recall5,
                recall10=recall10,
                mrr=mrr,
                latency_ms=latency_ms,
                num_retrieved=len(retrieved_ids)
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return RetrievalResult(
                query_id=query.id,
                ndcg10=0, recall5=0, recall10=0, mrr=0,
                latency_ms=latency_ms, num_retrieved=0,
                error=str(e)
            )
    
    def evaluate_generation(self, query: EvalQuery) -> GenerationResult:
        """Evaluate generation for a single query."""
        start_time = time.time()
        
        try:
            response = self.session.post(
                f"{self.config.api_base_url}/v1/ask",
                json={"query": query.query, "stream": False},
                timeout=self.config.timeout_seconds
            )
            latency_ms = (time.time() - start_time) * 1000
            
            if response.status_code != 200:
                return GenerationResult(
                    query_id=query.id,
                    faithfulness=0, relevance=0,
                    latency_ms=latency_ms, answer_length=0, num_citations=0,
                    error=f"HTTP {response.status_code}"
                )
            
            result = response.json()
            answer = result.get("answer", "")
            citations = result.get("citations", [])
            
            # Calculate metrics
            faithfulness = self._calculate_faithfulness(answer, citations)
            relevance = self._calculate_relevance(query.query, answer)
            
            return GenerationResult(
                query_id=query.id,
                faithfulness=faithfulness,
                relevance=relevance,
                latency_ms=latency_ms,
                answer_length=len(answer),
                num_citations=len(citations)
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return GenerationResult(
                query_id=query.id,
                faithfulness=0, relevance=0,
                latency_ms=latency_ms, answer_length=0, num_citations=0,
                error=str(e)
            )
    
    def _calculate_ndcg(self, retrieved: list[str], expected: set[str]) -> float:
        """Calculate NDCG@k."""
        if not expected:
            return 0.0
        
        dcg = sum(
            1.0 / (i + 1) for i, doc_id in enumerate(retrieved)
            if doc_id in expected
        )
        idcg = sum(1.0 / (i + 1) for i in range(min(len(expected), len(retrieved))))
        
        return dcg / idcg if idcg > 0 else 0.0
    
    def _calculate_recall(self, retrieved: list[str], expected: set[str]) -> float:
        """Calculate recall@k."""
        if not expected:
            return 0.0
        return len(set(retrieved) & expected) / len(expected)
    
    def _calculate_mrr(self, retrieved: list[str], expected: set[str]) -> float:
        """Calculate Mean Reciprocal Rank."""
        for i, doc_id in enumerate(retrieved):
            if doc_id in expected:
                return 1.0 / (i + 1)
        return 0.0
    
    def _calculate_faithfulness(self, answer: str, citations: list[dict]) -> float:
        """Calculate faithfulness score based on citations."""
        if not citations:
            return 0.5  # Neutral if no citations
        
        # Check how many citations are referenced in the answer
        cited_count = sum(
            1 for c in citations 
            if c.get("text", "")[:50].lower() in answer.lower()
        )
        return min(1.0, cited_count / len(citations))
    
    def _calculate_relevance(self, query: str, answer: str) -> float:
        """Calculate relevance score based on keyword overlap."""
        if not answer:
            return 0.0
        
        query_words = set(query.lower().split())
        answer_words = set(answer.lower().split())
        
        overlap = len(query_words & answer_words) / len(query_words) if query_words else 0
        length_factor = min(1.0, len(answer) / 100)  # Prefer longer answers up to 100 chars
        
        return min(1.0, (overlap + length_factor) / 2 + 0.3)
    
    def run_evaluation(
        self, 
        eval_type: str = "all",
        queries: Optional[list[EvalQuery]] = None
    ) -> EvalReport:
        """Run full evaluation suite."""
        start_time = time.time()
        
        if queries is None:
            queries = self.load_queries()
        
        # Limit sample size
        if len(queries) > self.config.sample_size:
            queries = queries[:self.config.sample_size]
        
        report = EvalReport(
            timestamp=datetime.now().isoformat(),
            config=asdict(self.config)
        )
        
        # Run retrieval evaluation
        if eval_type in ("all", "retrieval"):
            logger.info("Running retrieval evaluation...")
            retrieval_results = []
            for q in queries:
                result = self.evaluate_retrieval(q)
                retrieval_results.append(result)
                if result.error:
                    logger.warning(f"Retrieval error for {q.id}: {result.error}")
            
            # Aggregate metrics
            valid_results = [r for r in retrieval_results if not r.error]
            if valid_results:
                report.retrieval_metrics = {
                    "ndcg10": sum(r.ndcg10 for r in valid_results) / len(valid_results),
                    "recall5": sum(r.recall5 for r in valid_results) / len(valid_results),
                    "recall10": sum(r.recall10 for r in valid_results) / len(valid_results),
                    "mrr": sum(r.mrr for r in valid_results) / len(valid_results),
                    "avg_latency_ms": sum(r.latency_ms for r in valid_results) / len(valid_results),
                    "num_queries": len(queries),
                    "num_successful": len(valid_results),
                    "num_errors": len(retrieval_results) - len(valid_results),
                }
            report.retrieval_details = [asdict(r) for r in retrieval_results]
        
        # Run generation evaluation
        if eval_type in ("all", "generation"):
            logger.info("Running generation evaluation...")
            gen_results = []
            gen_queries = queries[:min(20, len(queries))]  # Limit generation evals
            
            for q in gen_queries:
                result = self.evaluate_generation(q)
                gen_results.append(result)
                if result.error:
                    logger.warning(f"Generation error for {q.id}: {result.error}")
            
            # Aggregate metrics
            valid_gen = [r for r in gen_results if not r.error]
            if valid_gen:
                report.generation_metrics = {
                    "faithfulness": sum(r.faithfulness for r in valid_gen) / len(valid_gen),
                    "relevance": sum(r.relevance for r in valid_gen) / len(valid_gen),
                    "avg_latency_ms": sum(r.latency_ms for r in valid_gen) / len(valid_gen),
                    "avg_answer_length": sum(r.answer_length for r in valid_gen) / len(valid_gen),
                    "avg_citations": sum(r.num_citations for r in valid_gen) / len(valid_gen),
                    "num_queries": len(gen_queries),
                    "num_successful": len(valid_gen),
                    "num_errors": len(gen_results) - len(valid_gen),
                }
            report.generation_details = [asdict(r) for r in gen_results]
        
        # Check for alerts
        report.alerts = self._check_thresholds(report)
        report.duration_seconds = time.time() - start_time
        
        logger.info(f"Evaluation completed in {report.duration_seconds:.2f}s")
        return report
    
    def _check_thresholds(self, report: EvalReport) -> list[str]:
        """Check if metrics are below thresholds."""
        alerts = []
        
        rm = report.retrieval_metrics
        if rm:
            if rm.get("ndcg10", 1) < self.config.ndcg10_threshold:
                alerts.append(f"NDCG@10 ({rm['ndcg10']:.3f}) below threshold ({self.config.ndcg10_threshold})")
            if rm.get("recall5", 1) < self.config.recall5_threshold:
                alerts.append(f"Recall@5 ({rm['recall5']:.3f}) below threshold ({self.config.recall5_threshold})")
            if rm.get("mrr", 1) < self.config.mrr_threshold:
                alerts.append(f"MRR ({rm['mrr']:.3f}) below threshold ({self.config.mrr_threshold})")
        
        gm = report.generation_metrics
        if gm:
            if gm.get("faithfulness", 1) < self.config.faithfulness_threshold:
                alerts.append(f"Faithfulness ({gm['faithfulness']:.3f}) below threshold ({self.config.faithfulness_threshold})")
        
        return alerts
    
    def save_report(self, report: EvalReport, output_path: Optional[str] = None) -> str:
        """Save evaluation report to JSON file."""
        if output_path is None:
            output_dir = Path(self.config.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"eval_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(output_path, 'w') as f:
            json.dump(asdict(report), f, indent=2)
        
        logger.info(f"Report saved to {output_path}")
        return str(output_path)


# ==============================================================================
# MLflow Integration
# ==============================================================================

def log_to_mlflow(report: EvalReport, tracking_uri: str, experiment_name: str = "vesper-eval") -> None:
    """Log evaluation results to MLflow."""
    try:
        import mlflow
        
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment_name)
        
        with mlflow.start_run(run_name=f"eval-{datetime.now().strftime('%Y%m%d-%H%M')}"):
            # Log retrieval metrics
            for key, value in report.retrieval_metrics.items():
                if isinstance(value, (int, float)):
                    mlflow.log_metric(f"retrieval_{key}", value)
            
            # Log generation metrics
            for key, value in report.generation_metrics.items():
                if isinstance(value, (int, float)):
                    mlflow.log_metric(f"generation_{key}", value)
            
            # Log params
            mlflow.log_param("eval_timestamp", report.timestamp)
            mlflow.log_param("duration_seconds", report.duration_seconds)
            mlflow.log_param("num_alerts", len(report.alerts))
            
            # Log alerts as artifact
            if report.alerts:
                with open("/tmp/alerts.txt", 'w') as f:
                    f.write("\n".join(report.alerts))
                mlflow.log_artifact("/tmp/alerts.txt")
        
        logger.info("Results logged to MLflow")
        
    except ImportError:
        logger.warning("MLflow not installed, skipping logging")
    except Exception as e:
        logger.error(f"Failed to log to MLflow: {e}")


# ==============================================================================
# CLI
# ==============================================================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="VESPER Evaluation Runner")
    parser.add_argument(
        "--eval-type",
        choices=["all", "retrieval", "generation"],
        default="all",
        help="Type of evaluation to run"
    )
    parser.add_argument(
        "--queries",
        type=str,
        help="Path to queries JSONL file"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./results",
        help="Directory to save results"
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=50,
        help="Maximum number of queries to evaluate"
    )
    parser.add_argument(
        "--api-url",
        type=str,
        help="VESPER API base URL"
    )
    parser.add_argument(
        "--mlflow",
        action="store_true",
        help="Log results to MLflow"
    )
    parser.add_argument(
        "--skip-health-check",
        action="store_true",
        help="Skip API health check"
    )
    
    args = parser.parse_args()
    
    # Build config
    config = EvalConfig(
        output_dir=args.output_dir,
        sample_size=args.sample_size,
    )
    
    if args.api_url:
        config.api_base_url = args.api_url
    if args.queries:
        config.queries_path = args.queries
    
    # Run evaluation
    evaluator = VesperEvaluator(config)
    
    if not args.skip_health_check:
        if not evaluator.health_check():
            logger.error("API health check failed")
            sys.exit(1)
    
    report = evaluator.run_evaluation(eval_type=args.eval_type)
    
    # Save report
    output_path = evaluator.save_report(report)
    
    # Log to MLflow
    if args.mlflow:
        log_to_mlflow(report, config.mlflow_tracking_uri)
    
    # Print summary
    print("\n" + "=" * 60)
    print("VESPER EVALUATION REPORT")
    print("=" * 60)
    print(f"Timestamp: {report.timestamp}")
    print(f"Duration: {report.duration_seconds:.2f}s")
    print()
    
    if report.retrieval_metrics:
        print("Retrieval Metrics:")
        print(f"  NDCG@10:  {report.retrieval_metrics.get('ndcg10', 0):.4f}")
        print(f"  Recall@5: {report.retrieval_metrics.get('recall5', 0):.4f}")
        print(f"  MRR:      {report.retrieval_metrics.get('mrr', 0):.4f}")
        print(f"  Avg Latency: {report.retrieval_metrics.get('avg_latency_ms', 0):.0f}ms")
        print()
    
    if report.generation_metrics:
        print("Generation Metrics:")
        print(f"  Faithfulness: {report.generation_metrics.get('faithfulness', 0):.4f}")
        print(f"  Relevance:    {report.generation_metrics.get('relevance', 0):.4f}")
        print(f"  Avg Latency:  {report.generation_metrics.get('avg_latency_ms', 0):.0f}ms")
        print()
    
    if report.alerts:
        print("⚠️  ALERTS:")
        for alert in report.alerts:
            print(f"  - {alert}")
        print()
    else:
        print("✅ No alerts - all metrics within thresholds")
        print()
    
    print(f"Full report saved to: {output_path}")
    print("=" * 60)
    
    # Exit with error if there are alerts
    if report.alerts:
        sys.exit(1)


if __name__ == "__main__":
    main()
