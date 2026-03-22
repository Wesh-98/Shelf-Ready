"""
Check-Pic - Professional Image Quality Control Agent

A comprehensive image QC agent for e-commerce product photography.
Ensures images meet quality standards for background purity,
composition, product detection, and color integrity.

Usage:
    from agents.CheckPic import CheckPicAgent

    agent = CheckPicAgent()
    result = agent.analyze_file("product.jpg", work_on="image")

    if result.passed:
        print("Image passed QC")
    else:
        print("Issues found:")
        for issue in result.issues:
            print(f"  [{issue.severity.value}] {issue.message}")
"""

from .agent import CheckPicAgent
from .config import CheckPicConfig, DEFAULT_CONFIG
from .models import (
    QCResult,
    QCIssue,
    ProcessingRecommendation,
    Severity,
    IssueCategory,
    BoundingBox
)

__version__ = "1.0.0"
__all__ = [
    'CheckPicAgent',
    'CheckPicConfig',
    'DEFAULT_CONFIG',
    'QCResult',
    'QCIssue',
    'ProcessingRecommendation',
    'Severity',
    'IssueCategory',
    'BoundingBox'
]
