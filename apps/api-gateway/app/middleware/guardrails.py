"""
Guardrails middleware for API Gateway.

Integrates pre-processing and post-processing guardrails:
- Pre: Input validation, jailbreak detection, policy checks
- Post: PII redaction, output moderation, citation verification, policy checks
"""

import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

# TODO: Once guardrails service is integrated, uncomment these imports
# from vesper_guardrails.input_validator import InputValidator
# from vesper_guardrails.jailbreak_detector import JailbreakDetector
# from vesper_guardrails.output_moderator import OutputModerator
# from vesper_guardrails.pii_redactor import PIIRedactor
# from vesper_guardrails.citation_verifier import CitationVerifier
# from vesper_guardrails.policy_engine import PolicyEngine


@dataclass
class GuardrailsResult:
    """Result from guardrails check."""
    
    passed: bool
    reason: Optional[str] = None
    blocked_by: Optional[str] = None
    modified_content: Optional[str] = None
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class GuardrailsMiddleware:
    """
    Middleware for pre and post-processing guardrails.
    
    Flow:
        Request → pre_process() → Agent Execution → post_process() → Response
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize guardrails middleware.
        
        Args:
            config: Configuration dict with guardrails settings
        """
        self.config = config or {}
        
        # TODO: Initialize actual guardrails components
        # self.input_validator = InputValidator()
        # self.jailbreak_detector = JailbreakDetector()
        # self.output_moderator = OutputModerator()
        # self.pii_redactor = PIIRedactor()
        # self.citation_verifier = CitationVerifier()
        # self.policy_engine = PolicyEngine()
        
        # Mock initialization for now
        self.enabled = self.config.get("enabled", True)
        self.pre_checks = self.config.get("pre_checks", ["input_validation", "jailbreak", "policy"])
        self.post_checks = self.config.get("post_checks", ["pii", "moderation", "citation", "policy"])
        
        print(f"🛡️  Guardrails Middleware initialized (enabled={self.enabled})")
        print(f"   Pre-checks: {', '.join(self.pre_checks)}")
        print(f"   Post-checks: {', '.join(self.post_checks)}")
    
    async def pre_process(
        self,
        query: str,
        tenant_id: str,
        trace_id: str
    ) -> GuardrailsResult:
        """
        Pre-processing guardrails: Run before agent execution.
        
        Checks:
        1. Input validation (length, format, language)
        2. Jailbreak detection (prompt injection, DAN attacks)
        3. Policy check (rate limits, permissions, content restrictions)
        
        Args:
            query: User's input query
            tenant_id: Tenant identifier
            trace_id: Trace ID for logging
        
        Returns:
            GuardrailsResult with passed=True if all checks pass
        """
        if not self.enabled:
            return GuardrailsResult(passed=True, reason="Guardrails disabled")
        
        start_time = time.time()
        
        # Mock implementation - replace with actual guardrails
        # In production, these would call the actual guardrails service
        
        # 1. Input Validation
        if "input_validation" in self.pre_checks:
            if len(query) > 500:
                latency_ms = (time.time() - start_time) * 1000
                return GuardrailsResult(
                    passed=False,
                    reason="Query exceeds maximum length (500 characters)",
                    blocked_by="input_validation",
                    latency_ms=latency_ms
                )
        
        # 2. Jailbreak Detection
        if "jailbreak" in self.pre_checks:
            # Mock: Check for common jailbreak patterns
            jailbreak_patterns = [
                "ignore previous instructions",
                "forget all previous",
                "you are now",
                "disregard all prior",
                "act as if",
                "pretend you are"
            ]
            
            query_lower = query.lower()
            for pattern in jailbreak_patterns:
                if pattern in query_lower:
                    latency_ms = (time.time() - start_time) * 1000
                    return GuardrailsResult(
                        passed=False,
                        reason=f"Potential jailbreak attempt detected: {pattern}",
                        blocked_by="jailbreak_detector",
                        latency_ms=latency_ms,
                        metadata={"pattern": pattern}
                    )
        
        # 3. Policy Check
        if "policy" in self.pre_checks:
            # Mock: Simple policy checks
            # In production: check rate limits, tenant permissions, content restrictions
            pass
        
        latency_ms = (time.time() - start_time) * 1000
        
        return GuardrailsResult(
            passed=True,
            reason="All pre-processing checks passed",
            latency_ms=latency_ms,
            metadata={
                "checks_run": self.pre_checks,
                "query_length": len(query)
            }
        )
    
    async def post_process(
        self,
        response_text: str,
        citations: List[Dict[str, Any]],
        tenant_id: str,
        trace_id: str
    ) -> GuardrailsResult:
        """
        Post-processing guardrails: Run after agent execution.
        
        Checks:
        1. PII redaction (SSN, credit cards, emails, phone numbers)
        2. Output moderation (toxicity, hallucination detection)
        3. Citation verification (hash validation, coverage)
        4. Policy check (content restrictions, compliance)
        
        Args:
            response_text: Generated response text
            citations: List of citation objects
            tenant_id: Tenant identifier
            trace_id: Trace ID for logging
        
        Returns:
            GuardrailsResult with passed=True and potentially modified_content
        """
        if not self.enabled:
            return GuardrailsResult(passed=True, reason="Guardrails disabled")
        
        start_time = time.time()
        modified_text = response_text
        redactions_made = []
        
        # 1. PII Redaction
        if "pii" in self.post_checks:
            # Mock: Simple PII detection patterns
            import re
            
            # Email redaction
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            if re.search(email_pattern, modified_text):
                modified_text = re.sub(email_pattern, "[EMAIL_REDACTED]", modified_text)
                redactions_made.append("email")
            
            # Phone redaction (simple US format)
            phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
            if re.search(phone_pattern, modified_text):
                modified_text = re.sub(phone_pattern, "[PHONE_REDACTED]", modified_text)
                redactions_made.append("phone")
            
            # SSN redaction
            ssn_pattern = r'\b\d{3}-\d{2}-\d{4}\b'
            if re.search(ssn_pattern, modified_text):
                modified_text = re.sub(ssn_pattern, "[SSN_REDACTED]", modified_text)
                redactions_made.append("ssn")
        
        # 2. Output Moderation
        if "moderation" in self.post_checks:
            # Mock: Check for toxic content
            toxic_words = ["hate", "violence", "offensive"]  # Simplified
            response_lower = modified_text.lower()
            
            for word in toxic_words:
                if word in response_lower:
                    latency_ms = (time.time() - start_time) * 1000
                    return GuardrailsResult(
                        passed=False,
                        reason=f"Output moderation failed: inappropriate content detected",
                        blocked_by="output_moderator",
                        latency_ms=latency_ms,
                        metadata={"flagged_word": word}
                    )
        
        # 3. Citation Verification
        if "citation" in self.post_checks:
            # Mock: Simple citation validation
            if len(citations) == 0:
                # Warning but not blocking
                pass
            
            # In production: verify hashes, check citation coverage
            # For now, just validate that citations have required fields
            for citation in citations:
                # Accept any non-empty sha256 hash (may be truncated IDs)
                if "sha256" not in citation or len(citation.get("sha256", "")) == 0:
                    latency_ms = (time.time() - start_time) * 1000
                    return GuardrailsResult(
                        passed=False,
                        reason="Citation verification failed: missing hash",
                        blocked_by="citation_verifier",
                        latency_ms=latency_ms
                    )
        
        # 4. Policy Check
        if "policy" in self.post_checks:
            # Mock: Post-generation policy checks
            pass
        
        latency_ms = (time.time() - start_time) * 1000
        
        return GuardrailsResult(
            passed=True,
            reason="All post-processing checks passed",
            modified_content=modified_text if redactions_made else None,
            latency_ms=latency_ms,
            metadata={
                "checks_run": self.post_checks,
                "redactions_made": redactions_made,
                "response_length": len(response_text),
                "citations_verified": len(citations)
            }
        )
    
    async def create_fallback_response(
        self,
        reason: str,
        blocked_by: str
    ) -> str:
        """
        Create a safe fallback response when guardrails block the request.
        
        Args:
            reason: Reason for blocking
            blocked_by: Which guardrail blocked the request
        
        Returns:
            Safe fallback message
        """
        fallback_messages = {
            "input_validation": "I'm sorry, but I couldn't process your request. Please rephrase your question.",
            "jailbreak_detector": "I'm sorry, but I can only help with financial document questions. Please ask about SEC filings or financial data.",
            "output_moderator": "I'm sorry, but I couldn't generate an appropriate response. Please try a different question.",
            "citation_verifier": "I'm sorry, but I couldn't verify the sources for this response. Please try again.",
            "policy_engine": "I'm sorry, but this request violates our usage policy. Please review our terms of service."
        }
        
        base_message = fallback_messages.get(blocked_by, "I'm sorry, but I couldn't complete your request.")
        
        # Add a safe citation to documentation or help resources
        safe_citation = {
            "source_uri": "https://docs.vesper.ai/help",
            "text": "For more information, please see our documentation."
        }
        
        return f"{base_message}\n\nFor assistance, visit our help documentation."


# Global instance (will be initialized in main.py lifespan)
guardrails_middleware: Optional[GuardrailsMiddleware] = None


def get_guardrails_middleware() -> GuardrailsMiddleware:
    """Get the global guardrails middleware instance."""
    global guardrails_middleware
    
    if guardrails_middleware is None:
        # Initialize with default config
        guardrails_middleware = GuardrailsMiddleware()
    
    return guardrails_middleware
