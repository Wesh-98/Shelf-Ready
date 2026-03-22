"""
Background Analyzer

Analyzes background purity, uniformity, color cast, and shadow detection.
Ensures pure white background while identifying contamination.
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


class BackgroundAnalyzer(BaseAnalyzer):
    """
    Analyzes background quality for e-commerce product images.

    Checks:
    - Pure white compliance (RGB distance from 255,255,255)
    - Background uniformity across image regions
    - Color cast detection (yellow, blue, etc.)
    - Shadow spillover from product edges
    """

    @property
    def name(self) -> str:
        return "BackgroundAnalyzer"

    def analyze_pre(
        self,
        image: Image.Image,
        work_on: str,
        context: Dict[str, Any]
    ) -> Tuple[List[QCIssue], Dict[str, Any], List[ProcessingRecommendation]]:
        """
        Analyze background before processing.

        In "image" mode: Full analysis to determine cleaning needs
        In "canvas" mode: Validate existing background quality
        """
        issues = []
        metrics = {}
        recommendations = []

        # Convert to numpy array
        arr = np.array(image.convert("RGB"))
        h, w = arr.shape[:2]

        # Get background mask (non-product pixels)
        bg_mask = self._estimate_background_mask(arr)
        metrics["background_pixel_count"] = int(np.sum(bg_mask))
        metrics["background_percentage"] = float(np.sum(bg_mask) / (h * w))

        if np.sum(bg_mask) == 0:
            # No clear background detected
            issues.append(QCIssue(
                category=IssueCategory.BACKGROUND,
                severity=Severity.WARNING,
                code="BG_NOT_DETECTED",
                message="Could not clearly identify background region"
            ))
            return issues, metrics, recommendations

        # Extract background pixels
        bg_pixels = arr[bg_mask]

        # 1. Check purity (distance from pure white)
        purity_result = self._analyze_purity(bg_pixels)
        metrics.update(purity_result["metrics"])

        if purity_result["impure_percentage"] > self.config.background.max_impure_percentage:
            severity = Severity.ERROR if purity_result["impure_percentage"] > 5.0 else Severity.WARNING
            issues.append(QCIssue(
                category=IssueCategory.BACKGROUND,
                severity=severity,
                code="BG_IMPURE",
                message=f"Background has {purity_result['impure_percentage']:.1f}% non-white pixels",
                details={
                    "impure_percentage": purity_result["impure_percentage"],
                    "mean_distance": purity_result["mean_distance"]
                }
            ))

            if work_on == "image":
                recommendations.append(ProcessingRecommendation(
                    param_name="mode",
                    current_value=context.get("mode", "auto"),
                    suggested_value="aggressive",
                    reason="BG_IMPURE",
                    confidence=min(0.9, purity_result["impure_percentage"] / 10)
                ))

        elif purity_result["mean_distance"] < 3:
            # Background is already very clean
            issues.append(QCIssue(
                category=IssueCategory.BACKGROUND,
                severity=Severity.INFO,
                code="BG_ALREADY_CLEAN",
                message="Background is already clean, minimal processing needed"
            ))

            if work_on == "image":
                recommendations.append(ProcessingRecommendation(
                    param_name="no_bg_clean",
                    current_value=False,
                    suggested_value=True,
                    reason="BG_ALREADY_CLEAN",
                    confidence=0.8
                ))

        # 2. Check uniformity
        uniformity_score = self._analyze_uniformity(arr, bg_mask)
        metrics["background_uniformity"] = uniformity_score

        if uniformity_score < self.config.background.min_uniformity_score:
            issues.append(QCIssue(
                category=IssueCategory.BACKGROUND,
                severity=Severity.WARNING,
                code="BG_NOT_UNIFORM",
                message=f"Background uniformity {uniformity_score:.1%} below threshold",
                details={"uniformity_score": uniformity_score}
            ))

        # 3. Check for color cast
        color_cast = self._detect_color_cast(bg_pixels)
        metrics["color_cast"] = color_cast

        if color_cast["detected"]:
            issues.append(QCIssue(
                category=IssueCategory.BACKGROUND,
                severity=Severity.WARNING,
                code="BG_COLOR_CAST",
                message=f"Background has {color_cast['type']} color cast",
                details=color_cast
            ))

        # 4. Check for shadow spillover (only in canvas mode or post-analysis)
        if work_on == "canvas":
            shadow_detected = self._detect_shadow_spillover(arr, bg_mask)
            metrics["shadow_detected"] = shadow_detected

            if shadow_detected:
                issues.append(QCIssue(
                    category=IssueCategory.BACKGROUND,
                    severity=Severity.INFO,
                    code="BG_SHADOW_SPILL",
                    message="Shadow bleeding into background area"
                ))

        return issues, metrics, recommendations

    def validate_post(
        self,
        processed_image: Image.Image,
        pre_result: Optional[QCResult]
    ) -> Tuple[List[QCIssue], Dict[str, Any]]:
        """
        Validate background after processing.

        Ensures background is now pure white and uniform.
        """
        issues = []
        metrics = {}

        arr = np.array(processed_image.convert("RGB"))
        h, w = arr.shape[:2]

        # Get background mask
        bg_mask = self._estimate_background_mask(arr)

        if np.sum(bg_mask) == 0:
            return issues, metrics

        bg_pixels = arr[bg_mask]

        # Check purity after processing
        purity_result = self._analyze_purity(bg_pixels)
        metrics["post_bg_purity"] = purity_result["purity_score"]
        metrics["post_impure_percentage"] = purity_result["impure_percentage"]

        # Should be much cleaner after processing
        if purity_result["impure_percentage"] > 1.0:
            issues.append(QCIssue(
                category=IssueCategory.BACKGROUND,
                severity=Severity.ERROR,
                code="BG_IMPURE",
                message=f"Background still has {purity_result['impure_percentage']:.1f}% non-white pixels after processing",
                details=purity_result["metrics"]
            ))

        # Check edges specifically (common problem area)
        edge_purity = self._check_edge_purity(arr)
        metrics["edge_purity"] = edge_purity

        if edge_purity < 0.98:
            issues.append(QCIssue(
                category=IssueCategory.BACKGROUND,
                severity=Severity.WARNING,
                code="BG_EDGE_IMPURE",
                message="Canvas edges contain non-white pixels"
            ))

        return issues, metrics

    def _estimate_background_mask(self, arr: np.ndarray) -> np.ndarray:
        """
        Estimate which pixels are background (near-white).

        Uses a simple luminance threshold approach.
        Product detection in ProductAnalyzer is more sophisticated.
        """
        # Calculate luminance
        luminance = 0.299 * arr[:,:,0] + 0.587 * arr[:,:,1] + 0.114 * arr[:,:,2]

        # Background is typically bright
        bright_mask = luminance > 230

        # Also check color neutrality (background should be neutral)
        r, g, b = arr[:,:,0], arr[:,:,1], arr[:,:,2]
        max_channel = np.maximum(np.maximum(r, g), b)
        min_channel = np.minimum(np.minimum(r, g), b)
        color_spread = max_channel - min_channel

        neutral_mask = color_spread < 20

        # Background = bright AND neutral
        bg_mask = bright_mask & neutral_mask

        return bg_mask

    def _analyze_purity(self, bg_pixels: np.ndarray) -> Dict[str, Any]:
        """
        Analyze how pure white the background is.

        Calculates RGB distance from (255, 255, 255).
        """
        if len(bg_pixels) == 0:
            return {
                "purity_score": 1.0,
                "impure_percentage": 0.0,
                "mean_distance": 0.0,
                "metrics": {}
            }

        # Calculate distance from pure white
        white = np.array([255, 255, 255])
        distances = np.sqrt(np.sum((bg_pixels.astype(float) - white) ** 2, axis=1))

        pure_tolerance = self.config.background.pure_white_tolerance
        acceptable_tolerance = self.config.background.acceptable_tolerance

        pure_count = np.sum(distances <= pure_tolerance)
        acceptable_count = np.sum(distances <= acceptable_tolerance)
        impure_count = np.sum(distances > acceptable_tolerance)

        total = len(bg_pixels)

        purity_score = pure_count / total if total > 0 else 1.0
        impure_percentage = (impure_count / total * 100) if total > 0 else 0.0
        mean_distance = float(np.mean(distances))

        return {
            "purity_score": purity_score,
            "impure_percentage": impure_percentage,
            "mean_distance": mean_distance,
            "metrics": {
                "bg_purity_score": round(purity_score, 3),
                "bg_impure_pct": round(impure_percentage, 2),
                "bg_mean_white_distance": round(mean_distance, 2),
                "bg_pure_pixel_count": int(pure_count),
                "bg_acceptable_pixel_count": int(acceptable_count),
                "bg_impure_pixel_count": int(impure_count)
            }
        }

    def _analyze_uniformity(self, arr: np.ndarray, bg_mask: np.ndarray) -> float:
        """
        Check background uniformity across image regions.

        Divides background into grid and compares region means.
        Returns uniformity score 0.0-1.0 (1.0 = perfectly uniform).
        """
        h, w = arr.shape[:2]
        grid_size = self.config.background.uniformity_grid_size

        cell_h = h // grid_size
        cell_w = w // grid_size

        region_means = []

        for i in range(grid_size):
            for j in range(grid_size):
                y0, y1 = i * cell_h, (i + 1) * cell_h
                x0, x1 = j * cell_w, (j + 1) * cell_w

                cell_mask = bg_mask[y0:y1, x0:x1]
                cell_pixels = arr[y0:y1, x0:x1][cell_mask]

                if len(cell_pixels) > 10:  # Need enough pixels
                    mean_val = np.mean(cell_pixels)
                    region_means.append(mean_val)

        if len(region_means) < 4:
            return 1.0  # Not enough data

        # Calculate variance in region means
        variance = np.var(region_means)

        # Convert to uniformity score (lower variance = higher uniformity)
        # Normalized so variance of 100 gives score of ~0.5
        uniformity = 1.0 / (1.0 + variance / 50)

        return float(uniformity)

    def _detect_color_cast(self, bg_pixels: np.ndarray) -> Dict[str, Any]:
        """
        Detect color cast in background.

        Analyzes channel imbalance in background pixels.
        """
        if len(bg_pixels) == 0:
            return {"detected": False}

        # Get median of each channel
        r_med = float(np.median(bg_pixels[:, 0]))
        g_med = float(np.median(bg_pixels[:, 1]))
        b_med = float(np.median(bg_pixels[:, 2]))

        max_imbalance = self.config.background.max_channel_imbalance

        # Check for imbalance
        r_g_diff = r_med - g_med
        r_b_diff = r_med - b_med
        g_b_diff = g_med - b_med

        result = {
            "detected": False,
            "r_median": r_med,
            "g_median": g_med,
            "b_median": b_med
        }

        # Determine cast type
        if abs(r_g_diff) > max_imbalance or abs(r_b_diff) > max_imbalance:
            if r_med > g_med and r_med > b_med:
                result["detected"] = True
                result["type"] = "warm/yellow"
            elif b_med > r_med and b_med > g_med:
                result["detected"] = True
                result["type"] = "cool/blue"
            elif g_med > r_med and g_med > b_med:
                result["detected"] = True
                result["type"] = "green"

        return result

    def _detect_shadow_spillover(self, arr: np.ndarray, bg_mask: np.ndarray) -> bool:
        """
        Detect shadow bleeding into background.

        Looks for gradient patterns near product edges.
        """
        from scipy import ndimage

        # Find edges of background mask
        bg_edges = ndimage.sobel(bg_mask.astype(float))
        edge_regions = np.abs(bg_edges) > 0.1

        # Get pixels near edges
        dilated_edges = ndimage.binary_dilation(edge_regions, iterations=5)
        near_edge_mask = dilated_edges & bg_mask

        if np.sum(near_edge_mask) < 100:
            return False

        # Check for gradient (darker near product)
        edge_pixels = arr[near_edge_mask]
        far_pixels = arr[bg_mask & ~near_edge_mask]

        if len(far_pixels) < 100:
            return False

        edge_brightness = np.mean(edge_pixels)
        far_brightness = np.mean(far_pixels)

        # Shadow would make edge pixels darker
        brightness_diff = far_brightness - edge_brightness

        return brightness_diff > 5  # Threshold for shadow detection

    def _check_edge_purity(self, arr: np.ndarray) -> float:
        """
        Check purity of canvas edges specifically.

        Returns ratio of pure white edge pixels.
        """
        h, w = arr.shape[:2]

        # Get edge pixels (2px border)
        edge_pixels = np.concatenate([
            arr[:2, :, :].reshape(-1, 3),      # Top
            arr[-2:, :, :].reshape(-1, 3),     # Bottom
            arr[:, :2, :].reshape(-1, 3),      # Left
            arr[:, -2:, :].reshape(-1, 3)      # Right
        ])

        # Check for pure white
        white = np.array([255, 255, 255])
        distances = np.sqrt(np.sum((edge_pixels.astype(float) - white) ** 2, axis=1))

        pure_count = np.sum(distances <= self.config.background.pure_white_tolerance)

        return pure_count / len(edge_pixels)
