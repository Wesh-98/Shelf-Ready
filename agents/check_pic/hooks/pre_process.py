"""
Pre-Processing Hook

Hook for running Check-Pic analysis before image processing.
Can be integrated into image_toolkit.py workflow.
"""

from typing import Dict, Any, Optional, Tuple
from PIL import Image

from ..agent import CheckPicAgent
from ..models import QCResult, ProcessingRecommendation
from ..config import CheckPicConfig


def pre_process_hook(
    image: Image.Image,
    work_on: str = "image",
    source_path: str = "",
    agent: Optional[CheckPicAgent] = None,
    config: Optional[CheckPicConfig] = None,
    **context
) -> Tuple[QCResult, Dict[str, Any]]:
    """
    Pre-processing analysis hook.

    Runs QC analysis before processing and returns recommendations
    that can be applied to processing parameters.

    Args:
        image: PIL Image to analyze
        work_on: "image" or "canvas" mode
        source_path: Path for reporting
        agent: Existing agent instance (creates new if None)
        config: Custom configuration
        **context: Processing context (intended_size, fit_mode, etc.)

    Returns:
        Tuple of:
        - QCResult with analysis findings
        - Dict of suggested parameter adjustments

    Example:
        from agents.CheckPic.hooks import pre_process_hook

        image = Image.open("product.jpg")
        qc_result, adjustments = pre_process_hook(
            image,
            work_on="image",
            intended_size=1500
        )

        if qc_result.passed:
            # Apply adjustments to processing params
            params.update(adjustments)
            process_image(image, **params)
        else:
            print("QC failed:", qc_result.critical_count, "critical issues")
    """
    # Create agent if not provided
    if agent is None:
        agent = CheckPicAgent(config)

    # Run pre-analysis
    qc_result = agent.analyze_pre(
        image,
        work_on=work_on,
        source_path=source_path,
        **context
    )

    # Build parameter adjustments from recommendations
    adjustments = {}
    for rec in qc_result.recommendations:
        if rec.confidence >= 0.6:  # Only apply high-confidence recommendations
            adjustments[rec.param_name] = rec.suggested_value

    return qc_result, adjustments


def apply_recommendations(
    params: Dict[str, Any],
    recommendations: list,
    min_confidence: float = 0.6
) -> Tuple[Dict[str, Any], list]:
    """
    Apply QC recommendations to processing parameters.

    Args:
        params: Current processing parameters
        recommendations: List of ProcessingRecommendation
        min_confidence: Minimum confidence threshold

    Returns:
        Tuple of:
        - Updated parameters dict
        - List of applied recommendations
    """
    adjusted = params.copy()
    applied = []

    for rec in recommendations:
        if rec.confidence >= min_confidence:
            adjusted[rec.param_name] = rec.suggested_value
            applied.append(rec)

    return adjusted, applied
