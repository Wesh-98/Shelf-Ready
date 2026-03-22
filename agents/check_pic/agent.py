"""
Check-Pic Agent

Main orchestrator for image quality control analysis.
Coordinates all analyzers and aggregates results.
"""

import os
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from PIL import Image

from .config import CheckPicConfig, DEFAULT_CONFIG
from .models.qc_result import QCResult, QCIssue, ProcessingRecommendation, Severity
from .analyzers import (
    BackgroundAnalyzer,
    CompositionAnalyzer,
    ProductAnalyzer,
    IntegrityAnalyzer
)


class CheckPicAgent:
    """
    Professional Image Quality Control Agent.

    Orchestrates multiple analyzers to provide comprehensive QC analysis
    for product images. Supports both "image" and "canvas" work modes.

    Usage:
        agent = CheckPicAgent()
        result = agent.analyze_file("product.jpg", work_on="image")
        print(result.to_text())
    """

    VERSION = "1.0.0"

    def __init__(self, config: Optional[CheckPicConfig] = None):
        """
        Initialize Check-Pic agent.

        Args:
            config: Custom configuration. Uses defaults if None.
        """
        self.config = config or DEFAULT_CONFIG

        # Initialize analyzers
        self.analyzers = [
            BackgroundAnalyzer(self.config),
            CompositionAnalyzer(self.config),
            ProductAnalyzer(self.config),
            IntegrityAnalyzer(self.config),
        ]

    def analyze_file(
        self,
        image_path: str,
        work_on: str = "image",
        reference_path: Optional[str] = None,
        **context
    ) -> QCResult:
        """
        Analyze a single image file.

        Args:
            image_path: Path to image file
            work_on: "image" (raw product) or "canvas" (on white canvas)
            reference_path: Optional original for comparison
            **context: Additional context (intended_size, fit_mode, etc.)

        Returns:
            QCResult with analysis findings
        """
        if not os.path.exists(image_path):
            result = QCResult(
                source_path=image_path,
                work_mode=work_on,
                passed=False
            )
            result.add_issue(QCIssue(
                category=Severity.CRITICAL,
                severity=Severity.CRITICAL,
                code="FILE_NOT_FOUND",
                message=f"Image file not found: {image_path}"
            ))
            return result

        try:
            image = Image.open(image_path)
            return self.analyze_pre(image, work_on, source_path=image_path, **context)
        except Exception as e:
            result = QCResult(
                source_path=image_path,
                work_mode=work_on,
                passed=False
            )
            result.add_issue(QCIssue(
                category=Severity.CRITICAL,
                severity=Severity.CRITICAL,
                code="FILE_ERROR",
                message=f"Error opening image: {str(e)}"
            ))
            return result

    def analyze_pre(
        self,
        image: Image.Image,
        work_on: str = "image",
        source_path: str = "",
        **context
    ) -> QCResult:
        """
        Analyze image BEFORE processing.

        Runs all analyzers and aggregates findings.

        Args:
            image: PIL Image to analyze
            work_on: "image" or "canvas" mode
            source_path: Path for reporting
            **context: Processing context (intended_size, fit_mode, etc.)

        Returns:
            QCResult with issues and recommendations
        """
        result = QCResult(
            source_path=source_path,
            work_mode=work_on,
            timestamp=datetime.now().isoformat(),
            analysis_phase="pre"
        )

        # Set defaults in context
        context.setdefault("intended_size", 1500)
        context.setdefault("fit_mode", "pad")
        context.setdefault("target_fill", 0.84)
        context.setdefault("margin_pct", 0.015)

        # Run each analyzer
        for analyzer in self.analyzers:
            try:
                issues, metrics, recommendations = analyzer.analyze_pre(
                    image, work_on, context
                )

                for issue in issues:
                    result.add_issue(issue)

                result.metrics.update(metrics)

                for rec in recommendations:
                    result.add_recommendation(rec)

            except Exception as e:
                result.add_issue(QCIssue(
                    category=Severity.WARNING,
                    severity=Severity.WARNING,
                    code=f"ANALYZER_ERROR_{analyzer.name.upper()}",
                    message=f"Analyzer {analyzer.name} failed: {str(e)}"
                ))

        # Calculate overall score
        result.metrics["overall_score"] = self._calculate_score(result)
        result.metrics["analyzer_version"] = self.VERSION

        return result

    def analyze_post(
        self,
        processed_image: Image.Image,
        pre_result: Optional[QCResult] = None
    ) -> QCResult:
        """
        Validate image AFTER processing.

        Args:
            processed_image: PIL Image after processing
            pre_result: QCResult from pre-analysis (for comparison)

        Returns:
            QCResult with validation findings
        """
        result = QCResult(
            source_path=pre_result.source_path if pre_result else "",
            work_mode=pre_result.work_mode if pre_result else "image",
            timestamp=datetime.now().isoformat(),
            analysis_phase="post"
        )

        # Run each analyzer's post-validation
        for analyzer in self.analyzers:
            try:
                issues, metrics = analyzer.validate_post(processed_image, pre_result)

                for issue in issues:
                    result.add_issue(issue)

                result.metrics.update(metrics)

            except Exception as e:
                result.add_issue(QCIssue(
                    category=Severity.WARNING,
                    severity=Severity.WARNING,
                    code=f"VALIDATOR_ERROR_{analyzer.name.upper()}",
                    message=f"Validator {analyzer.name} failed: {str(e)}"
                ))

        # Calculate overall score
        result.metrics["overall_score"] = self._calculate_score(result)
        result.metrics["analyzer_version"] = self.VERSION

        return result

    def analyze_directory(
        self,
        directory: str,
        work_on: str = "image",
        recursive: bool = True,
        extensions: Tuple[str, ...] = (".jpg", ".jpeg", ".png", ".webp"),
        **context
    ) -> List[QCResult]:
        """
        Analyze all images in a directory.

        Args:
            directory: Path to directory
            work_on: Work mode for all images
            recursive: Search subdirectories
            extensions: File extensions to include
            **context: Processing context

        Returns:
            List of QCResult for each image
        """
        results = []

        if recursive:
            for root, dirs, files in os.walk(directory):
                for filename in files:
                    if filename.lower().endswith(extensions):
                        filepath = os.path.join(root, filename)
                        result = self.analyze_file(filepath, work_on, **context)
                        results.append(result)
        else:
            for filename in os.listdir(directory):
                if filename.lower().endswith(extensions):
                    filepath = os.path.join(directory, filename)
                    result = self.analyze_file(filepath, work_on, **context)
                    results.append(result)

        return results

    def _calculate_score(self, result: QCResult) -> float:
        """
        Calculate overall quality score 0-100.
        """
        score = 100.0

        # Deduct based on issue severity
        for issue in result.issues:
            if issue.severity == Severity.CRITICAL:
                score -= 30
            elif issue.severity == Severity.ERROR:
                score -= 15
            elif issue.severity == Severity.WARNING:
                score -= 5
            elif issue.severity == Severity.INFO:
                score -= 1

        return max(0.0, min(100.0, score))

    def get_summary(self, results: List[QCResult]) -> Dict[str, Any]:
        """
        Generate summary statistics for batch results.

        Args:
            results: List of QCResult from batch analysis

        Returns:
            Summary dictionary with statistics
        """
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed

        all_issues = []
        for r in results:
            all_issues.extend(r.issues)

        issue_counts = {}
        for issue in all_issues:
            code = issue.code
            issue_counts[code] = issue_counts.get(code, 0) + 1

        # Top issues by frequency
        top_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        avg_score = sum(r.metrics.get("overall_score", 0) for r in results) / total if total > 0 else 0

        return {
            "total_images": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": round(passed / total * 100, 1) if total > 0 else 0,
            "average_score": round(avg_score, 1),
            "total_issues": len(all_issues),
            "critical_issues": sum(1 for i in all_issues if i.severity == Severity.CRITICAL),
            "error_issues": sum(1 for i in all_issues if i.severity == Severity.ERROR),
            "warning_issues": sum(1 for i in all_issues if i.severity == Severity.WARNING),
            "top_issues": top_issues
        }
