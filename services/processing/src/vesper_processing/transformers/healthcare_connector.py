"""
Healthcare Operations Domain Connector

Sample connector for healthcare domain demonstrating VESPER's domain portability.
Toggle via ENV: DOMAIN=healthcare

This connector ingests and processes healthcare operations documents:
- Hospital performance reports
- Clinical quality metrics
- Operational dashboards
- Compliance reports
"""

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

# Domain toggle
DOMAIN = os.getenv("DOMAIN", "finance")


class HealthcareDocumentType(Enum):
    """Types of healthcare documents supported."""
    
    QUALITY_REPORT = "quality_report"
    PERFORMANCE_DASHBOARD = "performance_dashboard"
    COMPLIANCE_AUDIT = "compliance_audit"
    CLINICAL_METRICS = "clinical_metrics"
    OPERATIONS_SUMMARY = "operations_summary"


@dataclass
class HealthcareDocument:
    """Represents a healthcare operations document."""
    
    document_id: str
    facility_name: str
    facility_id: str
    document_type: HealthcareDocumentType
    report_date: str
    period_start: str
    period_end: str
    content: str
    sections: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


# Healthcare NER entity types
HEALTHCARE_ENTITIES = {
    "FACILITY": r"\b(?:Hospital|Medical Center|Clinic|Health System|Care Center)\b",
    "METRIC": r"\b(?:readmission rate|mortality rate|patient satisfaction|wait time|bed occupancy|length of stay|infection rate)\b",
    "DEPARTMENT": r"\b(?:Emergency|ICU|Cardiology|Oncology|Pediatrics|Surgery|Radiology|Pharmacy)\b",
    "COMPLIANCE": r"\b(?:HIPAA|CMS|Joint Commission|OSHA|FDA|state regulations)\b",
    "MEASURE": r"\b\d+(?:\.\d+)?(?:\s*%|\s*per\s*\d+|\s*days?|\s*hours?)\b",
}

# Sample healthcare facilities for demo
DEMO_FACILITIES = {
    "METRO_GENERAL": {
        "name": "Metro General Hospital",
        "facility_id": "FAC-001",
        "type": "Acute Care Hospital",
        "beds": 450,
        "region": "Northeast",
    },
    "CITY_MEDICAL": {
        "name": "City Medical Center",
        "facility_id": "FAC-002",
        "type": "Teaching Hospital",
        "beds": 680,
        "region": "Midwest",
    },
    "COMMUNITY_HEALTH": {
        "name": "Community Health System",
        "facility_id": "FAC-003",
        "type": "Community Hospital",
        "beds": 220,
        "region": "Southeast",
    },
}

# Sample healthcare metrics
DEMO_METRICS = {
    "METRO_GENERAL": {
        "readmission_rate": 12.5,
        "mortality_rate": 2.1,
        "patient_satisfaction": 87,
        "avg_wait_time_mins": 28,
        "bed_occupancy": 78,
        "avg_los_days": 4.2,
        "infection_rate_per_1000": 1.8,
        "staff_turnover": 14,
        "er_visits_monthly": 4500,
    },
    "CITY_MEDICAL": {
        "readmission_rate": 10.8,
        "mortality_rate": 1.9,
        "patient_satisfaction": 91,
        "avg_wait_time_mins": 35,
        "bed_occupancy": 85,
        "avg_los_days": 5.1,
        "infection_rate_per_1000": 1.2,
        "staff_turnover": 11,
        "er_visits_monthly": 6200,
    },
    "COMMUNITY_HEALTH": {
        "readmission_rate": 14.2,
        "mortality_rate": 2.4,
        "patient_satisfaction": 82,
        "avg_wait_time_mins": 22,
        "bed_occupancy": 65,
        "avg_los_days": 3.8,
        "infection_rate_per_1000": 2.1,
        "staff_turnover": 18,
        "er_visits_monthly": 2100,
    },
}


class HealthcareConnector:
    """Connector for healthcare operations data sources."""
    
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.facilities = DEMO_FACILITIES
        self.metrics = DEMO_METRICS
    
    def is_enabled(self) -> bool:
        """Check if healthcare domain is enabled."""
        return DOMAIN.lower() == "healthcare"
    
    def list_facilities(self) -> list[dict[str, Any]]:
        """List available healthcare facilities."""
        return [
            {"key": key, **facility}
            for key, facility in self.facilities.items()
        ]
    
    def get_facility_metrics(self, facility_key: str) -> dict[str, Any]:
        """Get metrics for a specific facility."""
        return self.metrics.get(facility_key, {})
    
    def generate_quality_report(
        self,
        facility_key: str,
        report_date: datetime | None = None,
    ) -> HealthcareDocument:
        """Generate a sample quality report for a facility."""
        facility = self.facilities.get(facility_key)
        metrics = self.metrics.get(facility_key, {})
        
        if not facility:
            raise ValueError(f"Unknown facility: {facility_key}")
        
        report_date = report_date or datetime.now()
        
        content, sections = self._generate_quality_content(facility, metrics, report_date)
        
        return HealthcareDocument(
            document_id=f"{facility_key}-QR-{report_date.strftime('%Y%m')}-{uuid4().hex[:8]}",
            facility_name=facility["name"],
            facility_id=facility["facility_id"],
            document_type=HealthcareDocumentType.QUALITY_REPORT,
            report_date=report_date.strftime("%Y-%m-%d"),
            period_start=(report_date.replace(day=1)).strftime("%Y-%m-%d"),
            period_end=report_date.strftime("%Y-%m-%d"),
            content=content,
            sections=sections,
            metrics=metrics,
        )
    
    def generate_performance_dashboard(
        self,
        facility_key: str,
        report_date: datetime | None = None,
    ) -> HealthcareDocument:
        """Generate a sample performance dashboard for a facility."""
        facility = self.facilities.get(facility_key)
        metrics = self.metrics.get(facility_key, {})
        
        if not facility:
            raise ValueError(f"Unknown facility: {facility_key}")
        
        report_date = report_date or datetime.now()
        
        content, sections = self._generate_dashboard_content(facility, metrics, report_date)
        
        return HealthcareDocument(
            document_id=f"{facility_key}-PD-{report_date.strftime('%Y%m')}-{uuid4().hex[:8]}",
            facility_name=facility["name"],
            facility_id=facility["facility_id"],
            document_type=HealthcareDocumentType.PERFORMANCE_DASHBOARD,
            report_date=report_date.strftime("%Y-%m-%d"),
            period_start=(report_date.replace(day=1)).strftime("%Y-%m-%d"),
            period_end=report_date.strftime("%Y-%m-%d"),
            content=content,
            sections=sections,
            metrics=metrics,
        )
    
    def _generate_quality_content(
        self,
        facility: dict[str, Any],
        metrics: dict[str, Any],
        report_date: datetime,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Generate quality report content."""
        sections = []
        full_content = f"# {facility['name']} - Quality Report\n"
        full_content += f"## Report Period: {report_date.strftime('%B %Y')}\n\n"
        
        # Executive Summary
        exec_summary = f"""
{facility['name']} ({facility['type']}) with {facility['beds']} beds in the {facility['region']} region
demonstrates continued commitment to quality care. Key highlights for this reporting period include:

- Patient Satisfaction Score: {metrics.get('patient_satisfaction', 'N/A')}%
- 30-Day Readmission Rate: {metrics.get('readmission_rate', 'N/A')}%
- Hospital-Acquired Infection Rate: {metrics.get('infection_rate_per_1000', 'N/A')} per 1,000 patient days
- Average Length of Stay: {metrics.get('avg_los_days', 'N/A')} days
"""
        sections.append({"title": "Executive Summary", "content": exec_summary})
        full_content += f"## Executive Summary\n{exec_summary}\n\n"
        
        # Clinical Quality Metrics
        quality_content = f"""
### Clinical Quality Indicators

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| 30-Day Readmission Rate | {metrics.get('readmission_rate', 0)}% | <12% | {'✅' if metrics.get('readmission_rate', 100) < 12 else '⚠️'} |
| Mortality Rate | {metrics.get('mortality_rate', 0)}% | <2% | {'✅' if metrics.get('mortality_rate', 100) < 2 else '⚠️'} |
| HAI Rate (per 1000) | {metrics.get('infection_rate_per_1000', 0)} | <1.5 | {'✅' if metrics.get('infection_rate_per_1000', 100) < 1.5 else '⚠️'} |

### Analysis

The facility has {'met' if metrics.get('readmission_rate', 100) < 12 else 'not yet met'} the readmission target.
Infection control measures have been {'effective' if metrics.get('infection_rate_per_1000', 100) < 1.5 else 'requiring attention'}.
Mortality rates are {'within acceptable range' if metrics.get('mortality_rate', 100) < 2 else 'above target'}.
"""
        sections.append({"title": "Clinical Quality Metrics", "content": quality_content})
        full_content += f"## Clinical Quality Metrics\n{quality_content}\n\n"
        
        # Patient Experience
        patient_content = f"""
### Patient Satisfaction

Overall patient satisfaction score: **{metrics.get('patient_satisfaction', 0)}%**

Key drivers of satisfaction:
- Communication with nurses: {'High' if metrics.get('patient_satisfaction', 0) > 85 else 'Moderate'}
- Responsiveness of staff: {'High' if metrics.get('avg_wait_time_mins', 100) < 30 else 'Needs improvement'}
- Cleanliness and quiet: {'High' if metrics.get('patient_satisfaction', 0) > 80 else 'Moderate'}

Average ER wait time: {metrics.get('avg_wait_time_mins', 0)} minutes
Monthly ER visits: {metrics.get('er_visits_monthly', 0):,}
"""
        sections.append({"title": "Patient Experience", "content": patient_content})
        full_content += f"## Patient Experience\n{patient_content}\n\n"
        
        return full_content, sections
    
    def _generate_dashboard_content(
        self,
        facility: dict[str, Any],
        metrics: dict[str, Any],
        report_date: datetime,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Generate performance dashboard content."""
        sections = []
        full_content = f"# {facility['name']} - Performance Dashboard\n"
        full_content += f"## As of: {report_date.strftime('%B %d, %Y')}\n\n"
        
        # Operational Metrics
        ops_content = f"""
### Operational Performance

**Capacity Utilization**
- Bed Occupancy Rate: {metrics.get('bed_occupancy', 0)}%
- Total Licensed Beds: {facility['beds']}
- Average Daily Census: {int(facility['beds'] * metrics.get('bed_occupancy', 0) / 100)}

**Throughput**
- Average Length of Stay: {metrics.get('avg_los_days', 0)} days
- ER Volume (Monthly): {metrics.get('er_visits_monthly', 0):,} visits
- ER Wait Time: {metrics.get('avg_wait_time_mins', 0)} minutes

**Workforce**
- Staff Turnover Rate: {metrics.get('staff_turnover', 0)}%
- Target Turnover: <15%
"""
        sections.append({"title": "Operational Performance", "content": ops_content})
        full_content += f"## Operational Performance\n{ops_content}\n\n"
        
        # Trend Analysis
        trend_content = f"""
### Trend Analysis

**90-Day Trends:**
- Bed occupancy trending {'up' if metrics.get('bed_occupancy', 0) > 75 else 'stable'}
- Patient satisfaction {'improving' if metrics.get('patient_satisfaction', 0) > 85 else 'stable'}
- Staff turnover {'decreasing' if metrics.get('staff_turnover', 0) < 15 else 'requires attention'}

**Risk Indicators:**
- {'🟢' if metrics.get('readmission_rate', 100) < 12 else '🟡'} Readmission Risk
- {'🟢' if metrics.get('infection_rate_per_1000', 100) < 1.5 else '🟡'} Infection Risk
- {'🟢' if metrics.get('staff_turnover', 0) < 15 else '🟡'} Staffing Risk
"""
        sections.append({"title": "Trend Analysis", "content": trend_content})
        full_content += f"## Trend Analysis\n{trend_content}\n\n"
        
        return full_content, sections
    
    def ingest_documents(
        self,
        facility_keys: list[str] | None = None,
    ) -> list[HealthcareDocument]:
        """Ingest documents for specified facilities."""
        facility_keys = facility_keys or list(self.facilities.keys())
        documents = []
        
        for key in facility_keys:
            # Generate both report types for each facility
            documents.append(self.generate_quality_report(key))
            documents.append(self.generate_performance_dashboard(key))
        
        return documents


def extract_healthcare_entities(text: str) -> dict[str, list[str]]:
    """Extract healthcare-specific entities from text."""
    entities = {}
    
    for entity_type, pattern in HEALTHCARE_ENTITIES.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            entities[entity_type] = list(set(matches))
    
    return entities


def get_domain_connector():
    """Factory function to get the appropriate domain connector."""
    domain = os.getenv("DOMAIN", "finance").lower()
    
    if domain == "healthcare":
        return HealthcareConnector()
    else:
        # Return None or finance connector (default)
        return None


# Demo usage
if __name__ == "__main__":
    connector = HealthcareConnector()
    
    print("Healthcare Domain Connector Demo")
    print("=" * 50)
    print(f"Domain enabled: {connector.is_enabled()}")
    print(f"Available facilities: {len(connector.list_facilities())}")
    
    # Generate sample documents
    docs = connector.ingest_documents(["METRO_GENERAL"])
    for doc in docs:
        print(f"\nGenerated: {doc.document_id}")
        print(f"  Type: {doc.document_type.value}")
        print(f"  Sections: {len(doc.sections)}")
