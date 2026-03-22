"""
Base Analyzer Abstract Class

Defines the interface for all Check-Pic analyzers.
"""

from abc import ABC, abstractmethod
from typing import Tuple, List, Dict, Any, Optional
from PIL import Image

from ..models.qc_result import QCIssue, ProcessingRecommendation, QCResult
from ..config import CheckPicConfig, DEFAULT_CONFIG


class BaseAnalyzer(ABC):
    """
    Abstract base class for all image analyzers.

    Each analyzer focuses on a specific aspect of image quality:
    - BackgroundAnalyzer: Background purity and uniformity
    - CompositionAnalyzer: Product placement and margins
    - ProductAnalyzer: Edge detection and product isolation
    - IntegrityAnalyzer: Color preservation and alterations
    """

    def __init__(self, config: Optional[CheckPicConfig] = None):
        """
        Initialize analyzer with configuration.

        Args:
            config: CheckPicConfig instance. Uses DEFAULT_CONFIG if None.
        """
        self.config = config or DEFAULT_CONFIG

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the analyzer name for logging/reporting"""
        pass

    @abstractmethod
    def analyze_pre(
        self,
        image: Image.Image,
        work_on: str,
        context: Dict[str, Any]
    ) -> Tuple[List[QCIssue], Dict[str, Any], List[ProcessingRecommendation]]:
        """
        Analyze image BEFORE processing.

        Args:
            image: PIL Image to analyze
            work_on: "image" or "canvas" mode
            context: Additional context (intended_size, fit_mode, etc.)

        Returns:
            Tuple of:
            - List of QCIssue found
            - Dict of metrics calculated
            - List of ProcessingRecommendation
        """
        pass

    @abstractmethod
    def validate_post(
        self,
        processed_image: Image.Image,
        pre_result: Optional[QCResult]
    ) -> Tuple[List[QCIssue], Dict[str, Any]]:
        """
        Validate image AFTER processing.

        Args:
            processed_image: PIL Image after processing
            pre_result: QCResult from pre-analysis (for comparison)

        Returns:
            Tuple of:
            - List of QCIssue found
            - Dict of metrics calculated
        """
        pass

    def _mode_applies(self, work_on: str, required_modes: List[str]) -> bool:
        """
        Check if analysis applies to the current work mode.

        Args:
            work_on: Current work mode ("image" or "canvas")
            required_modes: List of modes this check applies to

        Returns:
            True if the check should run
        """
        return work_on in required_modes or "all" in required_modes
