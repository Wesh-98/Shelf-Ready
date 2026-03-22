"""
Integrity Analyzer

Analyzes color preservation, image alterations, and ensures product colors
remain unchanged while only the background is modified.
"""

import numpy as np
from typing import Tuple, List, Dict, Any, Optional
from PIL import Image

from .base import BaseAnalyzer
from ..models.qc_result import (
    QCIssue, ProcessingRecommendation, QCResult,
    Severity, IssueCategory, BoundingBox
)
from ..config import CheckPicConfig


class IntegrityAnalyzer(BaseAnalyzer):
    """
    Analyzes image integrity and color preservation.

    Checks:
    - Color preservation (product colors unchanged)
    - Delta E color difference measurement
    - Histogram similarity
    - Compression artifact detection
    """

    @property
    def name(self) -> str:
        return "IntegrityAnalyzer"

    def analyze_pre(
        self,
        image: Image.Image,
        work_on: str,
        context: Dict[str, Any]
    ) -> Tuple[List[QCIssue], Dict[str, Any], List[ProcessingRecommendation]]:
        """
        Analyze image integrity before processing.

        Stores baseline metrics for post-processing comparison.
        """
        issues = []
        metrics = {}
        recommendations = []

        arr = np.array(image.convert("RGB"))

        # Store baseline color histogram for product region
        product_mask = self._get_product_mask(arr)

        if np.sum(product_mask) > 0:
            product_pixels = arr[product_mask]

            # Store color statistics
            metrics["baseline_color_mean_r"] = float(np.mean(product_pixels[:, 0]))
            metrics["baseline_color_mean_g"] = float(np.mean(product_pixels[:, 1]))
            metrics["baseline_color_mean_b"] = float(np.mean(product_pixels[:, 2]))

            # Store histogram
            hist_r = np.histogram(product_pixels[:, 0], bins=32, range=(0, 256))[0]
            hist_g = np.histogram(product_pixels[:, 1], bins=32, range=(0, 256))[0]
            hist_b = np.histogram(product_pixels[:, 2], bins=32, range=(0, 256))[0]

            # Normalize histograms
            hist_r = hist_r / (np.sum(hist_r) + 1e-10)
            hist_g = hist_g / (np.sum(hist_g) + 1e-10)
            hist_b = hist_b / (np.sum(hist_b) + 1e-10)

            metrics["baseline_histogram_r"] = hist_r.tolist()
            metrics["baseline_histogram_g"] = hist_g.tolist()
            metrics["baseline_histogram_b"] = hist_b.tolist()

        # Check for existing compression artifacts
        artifact_score = self._analyze_compression_artifacts(arr)
        metrics["initial_artifact_score"] = round(artifact_score, 3)

        if artifact_score > self.config.integrity.max_artifact_score:
            issues.append(QCIssue(
                category=IssueCategory.INTEGRITY,
                severity=Severity.INFO,
                code="INT_COMPRESSION_ARTIFACTS",
                message=f"Image has existing compression artifacts (score: {artifact_score:.2f})",
                details={"artifact_score": artifact_score}
            ))

        return issues, metrics, recommendations

    def validate_post(
        self,
        processed_image: Image.Image,
        pre_result: Optional[QCResult]
    ) -> Tuple[List[QCIssue], Dict[str, Any]]:
        """
        Validate color integrity after processing.

        Compares processed product colors to baseline.
        """
        issues = []
        metrics = {}

        if pre_result is None:
            return issues, metrics

        arr = np.array(processed_image.convert("RGB"))

        # Get product mask
        product_mask = self._get_product_mask(arr)

        if np.sum(product_mask) == 0:
            return issues, metrics

        product_pixels = arr[product_mask]

        # 1. Compare color means
        if "baseline_color_mean_r" in pre_result.metrics:
            baseline_r = pre_result.metrics["baseline_color_mean_r"]
            baseline_g = pre_result.metrics["baseline_color_mean_g"]
            baseline_b = pre_result.metrics["baseline_color_mean_b"]

            current_r = float(np.mean(product_pixels[:, 0]))
            current_g = float(np.mean(product_pixels[:, 1]))
            current_b = float(np.mean(product_pixels[:, 2]))

            # Calculate color shift
            color_shift = np.sqrt(
                (current_r - baseline_r) ** 2 +
                (current_g - baseline_g) ** 2 +
                (current_b - baseline_b) ** 2
            )

            metrics["color_shift_rgb"] = round(color_shift, 2)
            metrics["post_color_mean_r"] = round(current_r, 2)
            metrics["post_color_mean_g"] = round(current_g, 2)
            metrics["post_color_mean_b"] = round(current_b, 2)

            # Check against threshold
            if color_shift > 10:  # Noticeable color shift
                severity = Severity.ERROR if color_shift > 20 else Severity.WARNING
                issues.append(QCIssue(
                    category=IssueCategory.INTEGRITY,
                    severity=severity,
                    code="INT_COLOR_SHIFT",
                    message=f"Product color shifted by {color_shift:.1f} RGB units",
                    details={
                        "shift": color_shift,
                        "baseline": [baseline_r, baseline_g, baseline_b],
                        "current": [current_r, current_g, current_b]
                    }
                ))

        # 2. Compare histograms
        if "baseline_histogram_r" in pre_result.metrics:
            baseline_hist_r = np.array(pre_result.metrics["baseline_histogram_r"])
            baseline_hist_g = np.array(pre_result.metrics["baseline_histogram_g"])
            baseline_hist_b = np.array(pre_result.metrics["baseline_histogram_b"])

            # Current histograms
            hist_r = np.histogram(product_pixels[:, 0], bins=32, range=(0, 256))[0]
            hist_g = np.histogram(product_pixels[:, 1], bins=32, range=(0, 256))[0]
            hist_b = np.histogram(product_pixels[:, 2], bins=32, range=(0, 256))[0]

            hist_r = hist_r / (np.sum(hist_r) + 1e-10)
            hist_g = hist_g / (np.sum(hist_g) + 1e-10)
            hist_b = hist_b / (np.sum(hist_b) + 1e-10)

            # Compute correlation
            corr_r = float(np.corrcoef(baseline_hist_r, hist_r)[0, 1])
            corr_g = float(np.corrcoef(baseline_hist_g, hist_g)[0, 1])
            corr_b = float(np.corrcoef(baseline_hist_b, hist_b)[0, 1])

            avg_correlation = (corr_r + corr_g + corr_b) / 3
            metrics["histogram_correlation"] = round(avg_correlation, 3)

            if avg_correlation < self.config.integrity.min_histogram_correlation:
                issues.append(QCIssue(
                    category=IssueCategory.INTEGRITY,
                    severity=Severity.WARNING,
                    code="INT_HISTOGRAM_MISMATCH",
                    message=f"Color distribution changed (correlation: {avg_correlation:.2f})",
                    details={
                        "correlation_r": round(corr_r, 3),
                        "correlation_g": round(corr_g, 3),
                        "correlation_b": round(corr_b, 3)
                    }
                ))

        # 3. Estimate Delta E (simplified LAB comparison)
        delta_e = self._estimate_delta_e(arr, product_mask, pre_result)
        if delta_e is not None:
            metrics["estimated_delta_e"] = round(delta_e, 2)

            if delta_e > self.config.integrity.max_delta_e:
                issues.append(QCIssue(
                    category=IssueCategory.INTEGRITY,
                    severity=Severity.WARNING,
                    code="INT_COLOR_SHIFT",
                    message=f"Estimated Delta E of {delta_e:.1f} exceeds threshold",
                    details={"delta_e": delta_e}
                ))

        return issues, metrics

    def _get_product_mask(self, arr: np.ndarray) -> np.ndarray:
        """
        Get product mask (non-background pixels).
        """
        luminance = 0.299 * arr[:,:,0] + 0.587 * arr[:,:,1] + 0.114 * arr[:,:,2]
        return luminance < 250

    def _analyze_compression_artifacts(self, arr: np.ndarray) -> float:
        """
        Analyze JPEG compression artifacts.

        Detects 8x8 DCT block boundaries characteristic of JPEG.
        """
        from scipy import ndimage

        # Convert to grayscale
        gray = 0.299 * arr[:,:,0] + 0.587 * arr[:,:,1] + 0.114 * arr[:,:,2]

        h, w = gray.shape

        # Analyze horizontal and vertical 8-pixel boundaries
        artifact_score = 0.0
        count = 0

        # Check every 8th row/column for discontinuities
        for i in range(8, h - 8, 8):
            row_diff = np.abs(gray[i, :] - gray[i-1, :])
            artifact_score += np.mean(row_diff)
            count += 1

        for j in range(8, w - 8, 8):
            col_diff = np.abs(gray[:, j] - gray[:, j-1])
            artifact_score += np.mean(col_diff)
            count += 1

        if count == 0:
            return 0.0

        avg_artifact = artifact_score / count

        # Compare to random positions
        random_score = 0.0
        random_count = 0

        for i in range(10, h - 10, 7):  # Offset positions
            row_diff = np.abs(gray[i, :] - gray[i-1, :])
            random_score += np.mean(row_diff)
            random_count += 1

        avg_random = random_score / random_count if random_count > 0 else avg_artifact

        # Artifact score is ratio of 8-boundary discontinuity to random
        if avg_random > 0:
            normalized_score = (avg_artifact - avg_random) / avg_random
        else:
            normalized_score = 0.0

        return max(0.0, normalized_score)

    def _estimate_delta_e(
        self,
        arr: np.ndarray,
        product_mask: np.ndarray,
        pre_result: QCResult
    ) -> Optional[float]:
        """
        Estimate Delta E color difference (simplified).

        Uses RGB to LAB approximation for Delta E calculation.
        """
        if "baseline_color_mean_r" not in pre_result.metrics:
            return None

        # Baseline LAB (approximate)
        baseline_rgb = np.array([
            pre_result.metrics["baseline_color_mean_r"],
            pre_result.metrics["baseline_color_mean_g"],
            pre_result.metrics["baseline_color_mean_b"]
        ])
        baseline_lab = self._rgb_to_lab(baseline_rgb)

        # Current LAB
        product_pixels = arr[product_mask]
        if len(product_pixels) == 0:
            return None

        current_rgb = np.array([
            np.mean(product_pixels[:, 0]),
            np.mean(product_pixels[:, 1]),
            np.mean(product_pixels[:, 2])
        ])
        current_lab = self._rgb_to_lab(current_rgb)

        # Delta E (CIE76 simplified)
        delta_e = np.sqrt(np.sum((baseline_lab - current_lab) ** 2))

        return float(delta_e)

    def _rgb_to_lab(self, rgb: np.ndarray) -> np.ndarray:
        """
        Convert RGB to LAB color space (simplified approximation).
        """
        # Normalize RGB to 0-1
        rgb = rgb / 255.0

        # Linearize (simplified gamma correction)
        rgb = np.where(rgb > 0.04045, ((rgb + 0.055) / 1.055) ** 2.4, rgb / 12.92)

        # RGB to XYZ
        matrix = np.array([
            [0.4124564, 0.3575761, 0.1804375],
            [0.2126729, 0.7151522, 0.0721750],
            [0.0193339, 0.1191920, 0.9503041]
        ])
        xyz = np.dot(matrix, rgb)

        # Normalize by D65 white point
        xyz[0] /= 0.95047
        xyz[1] /= 1.00000
        xyz[2] /= 1.08883

        # XYZ to LAB
        epsilon = 0.008856
        kappa = 903.3

        fx = np.where(xyz[0] > epsilon, xyz[0] ** (1/3), (kappa * xyz[0] + 16) / 116)
        fy = np.where(xyz[1] > epsilon, xyz[1] ** (1/3), (kappa * xyz[1] + 16) / 116)
        fz = np.where(xyz[2] > epsilon, xyz[2] ** (1/3), (kappa * xyz[2] + 16) / 116)

        L = 116 * fy - 16
        a = 500 * (fx - fy)
        b = 200 * (fy - fz)

        return np.array([L, a, b])
