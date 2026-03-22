"""
Check-Pic Quality Control Result Models

Data structures for QC analysis results, issues, and recommendations.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime


class Severity(Enum):
    """Issue severity levels"""
    INFO = "info"           # Informational only
    WARNING = "warning"     # Minor issue, processing can continue
    ERROR = "error"         # Significant issue, may affect output
    CRITICAL = "critical"   # Must be addressed before proceeding


class IssueCategory(Enum):
    """Categories of QC issues"""
    BACKGROUND = "background"       # Background purity, color, uniformity
    COMPOSITION = "composition"     # Centering, margins, fill ratio
    QUALITY = "quality"             # Resolution, sharpness, artifacts
    PRODUCT = "product"             # Edge detection, halos, masking
    METADATA = "metadata"           # EXIF, DPI, color profile
    INTEGRITY = "integrity"         # Color preservation, alterations


@dataclass
class BoundingBox:
    """Pixel-level bounding box for region identification"""
    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def width(self) -> int:
        return self.x1 - self.x0

    @property
    def height(self) -> int:
        return self.y1 - self.y0

    @property
    def area(self) -> int:
        return self.width * self.height

    @property
    def center(self) -> Tuple[float, float]:
        return (self.x0 + self.width / 2, self.y0 + self.height / 2)

    def to_tuple(self) -> Tuple[int, int, int, int]:
        return (self.x0, self.y0, self.x1, self.y1)

    def to_dict(self) -> Dict[str, int]:
        return {"x0": self.x0, "y0": self.y0, "x1": self.x1, "y1": self.y1}


@dataclass
class QCIssue:
    """Individual quality control issue"""
    category: IssueCategory
    severity: Severity
    code: str                           # e.g., "BG_IMPURE", "COMP_OFF_CENTER"
    message: str                        # Human-readable description
    details: Dict[str, Any] = field(default_factory=dict)
    location: Optional[BoundingBox] = None  # Region if applicable
    confidence: float = 1.0             # 0.0-1.0 confidence in detection

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "severity": self.severity.value,
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "location": self.location.to_dict() if self.location else None,
            "confidence": self.confidence
        }


@dataclass
class ProcessingRecommendation:
    """Recommended parameter adjustment based on QC analysis"""
    param_name: str                     # e.g., "dehalo_px", "mode"
    current_value: Any
    suggested_value: Any
    reason: str                         # Issue code that triggered this
    confidence: float = 0.8             # 0.0-1.0 confidence in recommendation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "param_name": self.param_name,
            "current_value": self.current_value,
            "suggested_value": self.suggested_value,
            "reason": self.reason,
            "confidence": self.confidence
        }


@dataclass
class QCResult:
    """Complete QC analysis result"""
    source_path: str
    work_mode: str                      # "image" or "canvas"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    issues: List[QCIssue] = field(default_factory=list)
    recommendations: List[ProcessingRecommendation] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    passed: bool = True
    analysis_phase: str = "pre"         # "pre" or "post"

    def has_critical_issues(self) -> bool:
        """Check if any critical issues exist"""
        return any(i.severity == Severity.CRITICAL for i in self.issues)

    def has_errors(self) -> bool:
        """Check if any error-level issues exist"""
        return any(i.severity in (Severity.ERROR, Severity.CRITICAL) for i in self.issues)

    def get_issues_by_severity(self, severity: Severity) -> List[QCIssue]:
        """Filter issues by severity level"""
        return [i for i in self.issues if i.severity == severity]

    def get_issues_by_category(self, category: IssueCategory) -> List[QCIssue]:
        """Filter issues by category"""
        return [i for i in self.issues if i.category == category]

    @property
    def critical_count(self) -> int:
        return len(self.get_issues_by_severity(Severity.CRITICAL))

    @property
    def error_count(self) -> int:
        return len(self.get_issues_by_severity(Severity.ERROR))

    @property
    def warning_count(self) -> int:
        return len(self.get_issues_by_severity(Severity.WARNING))

    @property
    def info_count(self) -> int:
        return len(self.get_issues_by_severity(Severity.INFO))

    def add_issue(self, issue: QCIssue) -> None:
        """Add an issue and update passed status"""
        self.issues.append(issue)
        if issue.severity in (Severity.CRITICAL, Severity.ERROR):
            self.passed = False

    def add_recommendation(self, rec: ProcessingRecommendation) -> None:
        """Add a processing recommendation"""
        self.recommendations.append(rec)

    def merge(self, other: 'QCResult') -> None:
        """Merge another QCResult into this one"""
        self.issues.extend(other.issues)
        self.recommendations.extend(other.recommendations)
        self.metrics.update(other.metrics)
        if other.has_critical_issues() or other.has_errors():
            self.passed = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "source_path": self.source_path,
            "work_mode": self.work_mode,
            "timestamp": self.timestamp,
            "passed": self.passed,
            "analysis_phase": self.analysis_phase,
            "summary": {
                "critical": self.critical_count,
                "errors": self.error_count,
                "warnings": self.warning_count,
                "info": self.info_count
            },
            "issues": [i.to_dict() for i in self.issues],
            "recommendations": [r.to_dict() for r in self.recommendations],
            "metrics": self.metrics
        }

    def to_text(self, verbose: bool = False) -> str:
        """Format as human-readable text"""
        lines = []
        status = "PASSED" if self.passed else "FAILED"
        lines.append(f"QC Result: {status}")
        lines.append(f"File: {self.source_path}")
        lines.append(f"Mode: {self.work_mode}")
        lines.append(f"Phase: {self.analysis_phase}")
        lines.append("")

        if self.issues:
            lines.append(f"Issues ({len(self.issues)}):")
            for issue in self.issues:
                prefix = {
                    Severity.CRITICAL: "[!!]",
                    Severity.ERROR: "[!]",
                    Severity.WARNING: "[~]",
                    Severity.INFO: "[i]"
                }.get(issue.severity, "[?]")
                lines.append(f"  {prefix} {issue.code}: {issue.message}")
                if verbose and issue.details:
                    for k, v in issue.details.items():
                        lines.append(f"      {k}: {v}")
        else:
            lines.append("No issues found.")

        if self.recommendations:
            lines.append("")
            lines.append(f"Recommendations ({len(self.recommendations)}):")
            for rec in self.recommendations:
                lines.append(f"  - {rec.param_name}: {rec.current_value} -> {rec.suggested_value}")
                lines.append(f"    Reason: {rec.reason} (confidence: {rec.confidence:.0%})")

        if verbose and self.metrics:
            lines.append("")
            lines.append("Metrics:")
            for k, v in self.metrics.items():
                lines.append(f"  {k}: {v}")

        return "\n".join(lines)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QCResult':
        """Create QCResult from dictionary"""
        result = cls(
            source_path=data.get("source_path", ""),
            work_mode=data.get("work_mode", "image"),
            timestamp=data.get("timestamp", ""),
            passed=data.get("passed", True),
            analysis_phase=data.get("analysis_phase", "pre"),
            metrics=data.get("metrics", {})
        )

        for issue_data in data.get("issues", []):
            location = None
            if issue_data.get("location"):
                loc = issue_data["location"]
                location = BoundingBox(loc["x0"], loc["y0"], loc["x1"], loc["y1"])

            result.issues.append(QCIssue(
                category=IssueCategory(issue_data["category"]),
                severity=Severity(issue_data["severity"]),
                code=issue_data["code"],
                message=issue_data["message"],
                details=issue_data.get("details", {}),
                location=location,
                confidence=issue_data.get("confidence", 1.0)
            ))

        for rec_data in data.get("recommendations", []):
            result.recommendations.append(ProcessingRecommendation(
                param_name=rec_data["param_name"],
                current_value=rec_data["current_value"],
                suggested_value=rec_data["suggested_value"],
                reason=rec_data["reason"],
                confidence=rec_data.get("confidence", 0.8)
            ))

        return result
