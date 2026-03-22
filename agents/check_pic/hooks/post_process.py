"""
Post-Processing Hook

Hook for running Check-Pic validation after image processing.
Ensures output meets quality standards.
"""

from typing import Optional, Tuple
from PIL import Image

from ..agent import CheckPicAgent
from ..models import QCResult
from ..config import CheckPicConfig


class QCValidationError(Exception):
    """Raised when QC validation fails in strict mode."""

    def __init__(self, result: QCResult, message: str = "QC validation failed"):
        self.result = result
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        issues = [f"  [{i.severity.value}] {i.code}: {i.message}"
                  for i in self.result.issues if i.severity.value in ("critical", "error")]
        return f"{self.message}\n" + "\n".join(issues)


def post_process_hook(
    processed_image: Image.Image,
    pre_result: Optional[QCResult] = None,
    agent: Optional[CheckPicAgent] = None,
    config: Optional[CheckPicConfig] = None,
    strict: bool = False
) -> QCResult:
    """
    Post-processing validation hook.

    Runs QC validation after processing to ensure output quality.
    Can compare against pre-processing results for integrity checks.

    Args:
        processed_image: PIL Image after processing
        pre_result: QCResult from pre-analysis (for comparison)
        agent: Existing agent instance (creates new if None)
        config: Custom configuration
        strict: If True, raises QCValidationError on failure

    Returns:
        QCResult with validation findings

    Raises:
        QCValidationError: If strict=True and validation fails

    Example:
        from agents.CheckPic.hooks import pre_process_hook, post_process_hook

        # Pre-analysis
        pre_result, adjustments = pre_process_hook(image, work_on="image")

        # Process image
        processed = clean_product_image(image, **adjustments)

        # Post-validation
        post_result = post_process_hook(processed, pre_result, strict=True)
    """
    # Create agent if not provided
    if agent is None:
        agent = CheckPicAgent(config)

    # Run post-validation
    qc_result = agent.analyze_post(processed_image, pre_result)

    # Strict mode: raise on failure
    if strict and not qc_result.passed:
        raise QCValidationError(
            qc_result,
            f"QC validation failed with {qc_result.critical_count} critical and "
            f"{qc_result.error_count} error issues"
        )

    return qc_result


def validate_output(
    processed_image: Image.Image,
    pre_result: Optional[QCResult] = None,
    agent: Optional[CheckPicAgent] = None,
    config: Optional[CheckPicConfig] = None
) -> Tuple[bool, QCResult]:
    """
    Simple validation function returning pass/fail status.

    Args:
        processed_image: PIL Image after processing
        pre_result: QCResult from pre-analysis
        agent: Existing agent instance
        config: Custom configuration

    Returns:
        Tuple of (passed: bool, result: QCResult)

    Example:
        passed, result = validate_output(processed_image)
        if not passed:
            print("Output failed QC:", result.to_text())
    """
    result = post_process_hook(
        processed_image,
        pre_result=pre_result,
        agent=agent,
        config=config,
        strict=False
    )

    return result.passed, result
