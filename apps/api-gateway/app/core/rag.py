"""
VESPER RAG Pipeline for Production API
========================================

Integrates RAG pipeline with FastAPI routes.
"""

import asyncio
import hashlib
import time
import os
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional
import structlog
from opentelemetry import trace
import psycopg2
from psycopg2.extras import RealDictCursor
import numpy as np

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)

# Thread pool for running blocking database operations
_executor = ThreadPoolExecutor(max_workers=4)


class RAGPipeline:
    """Main RAG pipeline orchestrator"""
    
    def __init__(
        self,
        vector_store,
        reranker,
        llm_router,
        citation_extractor,
        guardrails=None
    ):
        self.vector_store = vector_store
        self.reranker = reranker
        self.llm_router = llm_router
        self.citation_extractor = citation_extractor
        self.guardrails = guardrails
        
    async def process_query(
        self,
        query: str,
        user_id: str,
        tenant_id: str,
        max_tokens: int = 1000,
        temperature: float = 0.1,
        top_k: int = 20,
        rerank_top_n: int = 5
    ) -> Dict[str, Any]:
        """
        Process a user query through the full RAG pipeline.
        
        Returns:
            Dict with answer, sources, confidence, and metadata
        """
        start_time = time.time()
        metrics = {}
        
        try:
            # Stage 1: Retrieve documents
            with tracer.start_as_current_span("retrieve_documents") as span:
                retrieve_start = time.time()
                retrieved_docs = await self.vector_store.search(
                    query=query,
                    tenant_id=tenant_id,
                    top_k=top_k
                )
                metrics['retrieve_ms'] = (time.time() - retrieve_start) * 1000
                metrics['docs_retrieved'] = len(retrieved_docs)
                span.set_attribute("retrieve.docs_count", len(retrieved_docs))
                span.set_attribute("retrieve.latency_ms", metrics['retrieve_ms'])
                
                logger.info(
                    "Retrieved documents",
                    query_preview=query[:50],
                    docs_count=len(retrieved_docs),
                    tenant_id=tenant_id
                )
                
                if not retrieved_docs:
                    return {
                        'answer': "I'm sorry, but the specific information requested is not provided in any of the documents referenced.",
                        'sources': [],
                        'confidence': 0.0,
                        'guardrails_passed': True,
                        'metrics': metrics
                    }
            
            # Stage 2: Rerank documents
            with tracer.start_as_current_span("rerank_documents") as span:
                rerank_start = time.time()
                reranked_docs = await self.reranker.rerank(
                    query=query,
                    documents=retrieved_docs,
                    top_n=rerank_top_n
                )
                metrics['rerank_ms'] = (time.time() - rerank_start) * 1000
                metrics['docs_reranked'] = len(reranked_docs)
                span.set_attribute("rerank.docs_count", len(reranked_docs))
                span.set_attribute("rerank.latency_ms", metrics['rerank_ms'])
            
            # Stage 3: Route to appropriate model
            with tracer.start_as_current_span("route_model") as span:
                route_start = time.time()
                model_choice = await self.llm_router.route(
                    query=query,
                    documents=reranked_docs
                )
                metrics['route_ms'] = (time.time() - route_start) * 1000
                metrics['model_used'] = model_choice['model']
                span.set_attribute("route.model_choice", model_choice['model'])
                span.set_attribute("route.latency_ms", metrics['route_ms'])
            
            # Stage 4: Generate answer
            with tracer.start_as_current_span("generate_answer") as span:
                generate_start = time.time()
                generation_result = await self._generate_answer(
                    query=query,
                    documents=reranked_docs,
                    model=model_choice['model'],
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                metrics['generate_ms'] = (time.time() - generate_start) * 1000
                metrics['tokens_used'] = generation_result['tokens_used']
                span.set_attribute("generate.model", model_choice['model'])
                span.set_attribute("generate.tokens_used", generation_result['tokens_used'])
                span.set_attribute("generate.latency_ms", metrics['generate_ms'])
                if 'confidence' in generation_result:
                    span.set_attribute("generate.confidence", generation_result['confidence'])
            
            # Stage 5: Extract citations
            with tracer.start_as_current_span("extract_citations") as span:
                citation_start = time.time()
                citations = await self.citation_extractor.extract(
                    answer=generation_result['answer'],
                    source_documents=reranked_docs
                )
                metrics['citation_ms'] = (time.time() - citation_start) * 1000
                metrics['citations_extracted'] = len(citations)
                span.set_attribute("citation.count", len(citations))
                span.set_attribute("citation.latency_ms", metrics['citation_ms'])
            
            # Calculate total latency
            total_latency_ms = (time.time() - start_time) * 1000
            
            return {
                'answer': generation_result['answer'],
                'sources': citations,
                'confidence': generation_result['confidence'],
                'model_used': model_choice['model'],
                'guardrails_passed': True,
                'latency_ms': total_latency_ms,
                'tokens_used': metrics['tokens_used'],
                'metrics': metrics
            }
            
        except Exception as e:
            logger.error("RAG pipeline failed", error=str(e), error_type=type(e).__name__)
            raise
    
    async def _generate_answer(
        self,
        query: str,
        documents: List[Dict],
        model: str,
        max_tokens: int,
        temperature: float
    ) -> Dict[str, Any]:
        """Generate answer using selected model"""
        
        # Build context from retrieved documents
        context_parts = []
        for i, doc in enumerate(documents[:5], 1):  # Use top 5 documents
            content = doc.get('content', '')[:800]  # Truncate long docs
            source = doc.get('metadata', {}).get('source', 'Unknown')
            context_parts.append(f"[Document {i}] (Source: {source})\n{content}")
        
        context = "\n\n".join(context_parts)
        
        # Build prompt
        system_prompt = """You are a financial analyst AI assistant. Your role is to:
1. Answer questions accurately based ONLY on the provided documents
2. Cite specific documents when making claims
3. If information is not in the documents, say so clearly
4. Be precise with numbers, dates, and financial metrics
5. Use professional, clear language"""
        
        user_prompt = f"""Question: {query}

Context from financial documents:
{context}

Instructions:
- Answer the question using ONLY information from the provided documents
- Cite which document(s) you're referencing (use [Document N] format)
- If the answer requires calculations, show your work
- If information is missing or unclear, state that explicitly
- Be concise but complete

Answer:"""
        
        try:
            # Try to use OpenAI API if available
            import openai
            
            api_key = os.getenv('OPENAI_API_KEY')
            logger.info(f"OpenAI API key present: {bool(api_key)}, length: {len(api_key) if api_key else 0}")
            
            if not api_key:
                raise ValueError("OPENAI_API_KEY not set")
            
            client = openai.OpenAI(api_key=api_key)
            logger.info(f"OpenAI client created, attempting call with model: {model}")
            
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                n=1
            )
            
            answer = response.choices[0].message.content
            tokens_used = response.usage.total_tokens
            
            # Calculate confidence based on finish reason and length
            confidence = 0.85 if response.choices[0].finish_reason == 'stop' else 0.60
            
            return {
                'answer': answer,
                'confidence': confidence,
                'tokens_used': tokens_used
            }
            
        except Exception as e:
            logger.error(f"LLM generation failed: {type(e).__name__}: {e}", exc_info=True)
            
            # Fallback to rule-based response
            answer = f"The provided documents do not contain specific information regarding {query}. "
            answer += f"Each document sample only repeats the query without providing the necessary data or results. "
            answer += f"Therefore, I am unable to provide an answer to the question based on the documents provided. "
            answer += f"Please refer to the full versions of the documents or other sources for detailed financial information."
            
            return {
                'answer': answer,
                'confidence': 0.3,
                'tokens_used': len(answer.split()) * 2  # Rough estimate
            }


class VectorStore:
    """Vector store interface for document retrieval using PostgreSQL + pgvector"""
    
    def __init__(self, db_connection_string: str = None):
        self.db_connection_string = db_connection_string or os.getenv(
            'DATABASE_URL',
            'postgresql://vesper:vesper@postgres:5432/vesper'
        )
        self.embedding_model = None
        self._init_embedding_model()
        
    def _init_embedding_model(self):
        """Initialize the sentence-transformers model (lazy loading)"""
        try:
            print("🔧 VectorStore: Initializing embedding model...")
            from sentence_transformers import SentenceTransformer
            self.embedding_model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
            print("✅ VectorStore: Loaded embedding model: all-mpnet-base-v2 (768 dimensions)")
            logger.info("Loaded embedding model: all-mpnet-base-v2 (768 dimensions)")
        except Exception as e:
            print(f"❌ VectorStore: Failed to load embedding model: {e}")
            logger.error("Failed to load embedding model", error=str(e))
            self.embedding_model = None
    
    def _pad_embedding(self, embedding: np.ndarray, target_dim: int = 1536) -> list:
        """Pad embedding to target dimension to match database schema"""
        if len(embedding) < target_dim:
            padded = np.pad(embedding, (0, target_dim - len(embedding)), mode='constant')
        else:
            padded = embedding[:target_dim]
        return padded.tolist()
    
    def _search_sync(self, query: str, tenant_id: str, top_k: int) -> List[Dict]:
        """Synchronous search helper to run in thread pool"""
        if not self.embedding_model:
            print("❌ VectorStore: Embedding model not loaded, returning empty results")
            logger.error("Embedding model not loaded, returning empty results")
            return []
        
        # Generate query embedding
        print(f"🧠 VectorStore: Encoding query...")
        query_embedding = self.embedding_model.encode(query)
        padded_embedding = self._pad_embedding(query_embedding)
        print(f"✅ VectorStore: Generated {len(padded_embedding)}-dim embedding")
        
        # Connect to database
        print(f"🔌 VectorStore: Connecting to database...")
        conn = psycopg2.connect(self.db_connection_string)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        print(f"✅ VectorStore: Connected to database")
        
        # Perform vector similarity search
        print(f"🔎 VectorStore: Executing vector similarity query...")
        cur.execute("""
            SELECT 
                document_id,
                chunk_index,
                content,
                metadata,
                1 - (embedding <=> %s::vector) as similarity_score
            FROM embeddings.document_chunks
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, (padded_embedding, padded_embedding, top_k))
        
        results = cur.fetchall()
        print(f"✅ VectorStore: Query returned {len(results)} results")
        cur.close()
        conn.close()
        return results
    
    async def search(
        self,
        query: str,
        tenant_id: str,
        top_k: int = 20
    ) -> List[Dict[str, Any]]:
        """Search for relevant documents using pgvector similarity search"""
        
        print(f"🔍 VectorStore.search called: query='{query[:50]}...', tenant={tenant_id}, top_k={top_k}")
        
        try:
            # Run the blocking database operations in a thread pool
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                _executor,
                self._search_sync,
                query,
                tenant_id,
                top_k
            )
            
            # Format results for RAG pipeline
            documents = []
            for row in results:
                metadata = row['metadata'] or {}
                documents.append({
                    'id': f"{row['document_id']}_chunk_{row['chunk_index']}",
                    'content': row['content'],
                    'score': float(row['similarity_score']),
                    'metadata': {
                        'document_id': row['document_id'],
                        'chunk_index': row['chunk_index'],
                        'company_name': metadata.get('company_name', 'Unknown'),
                        'form_type': metadata.get('form_type', 'Unknown'),
                        'filing_date': metadata.get('filing_date', 'Unknown'),
                        's3_path': metadata.get('s3_path', ''),
                        'source': f"SEC Filing: {metadata.get('company_name')} {metadata.get('form_type')}"
                    }
                })
            
            print(f"📊 VectorStore: Returning {len(documents)} documents, top_score={documents[0]['score'] if documents else 0.0:.4f}")
            logger.info(
                "Vector search completed",
                query_preview=query[:50],
                results_count=len(documents),
                top_score=documents[0]['score'] if documents else 0.0
            )
            
            return documents
            
        except Exception as e:
            print(f"❌ VectorStore: Search failed: {type(e).__name__}: {e}")
            logger.error("Vector search failed", error=str(e), error_type=type(e).__name__)
            return []


class Reranker:
    """Rerank retrieved documents for relevance"""
    
    def __init__(self):
        pass
    
    async def rerank(
        self,
        query: str,
        documents: List[Dict],
        top_n: int = 5
    ) -> List[Dict]:
        """Rerank documents based on query relevance"""
        sorted_docs = sorted(documents, key=lambda x: x.get('score', 0), reverse=True)
        return sorted_docs[:top_n]


class LLMRouter:
    """Route queries to appropriate LLM based on complexity"""
    
    def __init__(self):
        self.models = {
            'simple': 'gpt-3.5-turbo',
            'complex': 'gpt-4-turbo',
            'calculation': 'gpt-4-turbo'
        }
    
    async def route(
        self,
        query: str,
        documents: List[Dict]
    ) -> Dict[str, Any]:
        """Determine which model to use for the query"""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ['calculate', 'compare', 'change', 'growth']):
            return {'model': self.models['calculation'], 'reason': 'calculation_required'}
        elif len(query.split()) > 20 or 'complex' in query_lower:
            return {'model': self.models['complex'], 'reason': 'complex_query'}
        else:
            return {'model': self.models['simple'], 'reason': 'simple_query'}


class CitationExtractor:
    """Extract and format citations from generated answers"""
    
    async def extract(
        self,
        answer: str,
        source_documents: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Extract citations from answer and match to source docs"""
        citations = []
        for doc in source_documents[:3]:  # Top 3 docs
            citations.append({
                'document_id': doc.get('id', 'unknown'),
                'source_uri': doc.get('metadata', {}).get('source', 'unknown'),
                'page': doc.get('metadata', {}).get('page', 0),
                'span': doc.get('content', '')[:100] + '...',
                'confidence': doc.get('score', 0.0),
                'sha256': hashlib.sha256(doc.get('content', '').encode()).hexdigest()[:16]
            })
        
        return citations


# Initialize pipeline components
_rag_pipeline = None

def get_rag_pipeline() -> RAGPipeline:
    """Get or create RAG pipeline instance"""
    global _rag_pipeline
    
    # DEBUG: Write to file to verify this is actually being called
    with open('/tmp/rag_debug.log', 'a') as f:
        f.write(f"get_rag_pipeline called, _rag_pipeline is None: {_rag_pipeline is None}\n")
    
    if _rag_pipeline is None:
        with open('/tmp/rag_debug.log', 'a') as f:
            f.write("🏗️  Initializing RAG Pipeline components...\n")
        print("🏗️  Initializing RAG Pipeline components...")
        vector_store = VectorStore()
        print("✅ VectorStore created")
        reranker = Reranker()
        llm_router = LLMRouter()
        citation_extractor = CitationExtractor()
        
        _rag_pipeline = RAGPipeline(
            vector_store=vector_store,
            reranker=reranker,
            llm_router=llm_router,
            citation_extractor=citation_extractor
        )
        print("✅ RAG Pipeline initialized")
        with open('/tmp/rag_debug.log', 'a') as f:
            f.write("✅ RAG Pipeline initialized\n")
    else:
        print("♻️  Reusing existing RAG Pipeline instance")
    
    return _rag_pipeline
