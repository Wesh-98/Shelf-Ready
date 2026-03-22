"""
Product Analyzer

Analyzes product edge detection, white-on-white detection, halos, and product isolation.
Specialized for accurate product boundary detection in various scenarios.
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


class ProductAnalyzer(BaseAnalyzer):
    """
    Analyzes product detection quality.

    Checks:
    - Edge detection quality and confidence
    - White-on-white product detection
    - Halo artifacts around product
    - Multiple product detection
    - Product mask quality
    """

    @property
    def name(self) -> str:
        return "ProductAnalyzer"

    def analyze_pre(
        self,
        image: Image.Image,
        work_on: str,
        context: Dict[str, Any]
    ) -> Tuple[List[QCIssue], Dict[str, Any], List[ProcessingRecommendation]]:
        """
        Analyze product detection before processing.
        """
        issues = []
        metrics = {}
        recommendations = []

        arr = np.array(image.convert("RGB"))
        h, w = arr.shape[:2]

        # 1. Generate product mask
        product_mask, confidence_map = self._detect_product_mask(arr)
        metrics["product_pixel_count"] = int(np.sum(product_mask))
        metrics["product_coverage"] = round(np.sum(product_mask) / (h * w) * 100, 2)

        if np.sum(product_mask) == 0:
            issues.append(QCIssue(
                category=IssueCategory.PRODUCT,
                severity=Severity.CRITICAL,
                code="PROD_NOT_DETECTED",
                message="No product detected in image"
            ))
            return issues, metrics, recommendations

        # 2. Analyze edge confidence
        edge_confidence = self._analyze_edge_confidence(confidence_map, product_mask)
        metrics["edge_confidence_mean"] = round(edge_confidence["mean"], 3)
        metrics["edge_confidence_min"] = round(edge_confidence["min"], 3)

        if edge_confidence["mean"] < self.config.product.min_edge_confidence:
            issues.append(QCIssue(
                category=IssueCategory.PRODUCT,
                severity=Severity.WARNING,
                code="PROD_EDGE_AMBIGUOUS",
                message=f"Product edge confidence {edge_confidence['mean']:.1%} below threshold",
                details=edge_confidence
            ))

        # 3. Detect white-on-white scenario
        white_on_white = self._detect_white_on_white(arr, product_mask)
        metrics["white_on_white_detected"] = white_on_white["detected"]
        metrics["product_whiteness"] = round(white_on_white["product_whiteness"], 3)

        if white_on_white["detected"]:
            issues.append(QCIssue(
                category=IssueCategory.PRODUCT,
                severity=Severity.WARNING,
                code="PROD_WHITE_ON_WHITE",
                message="White product on white background - edge detection may be ambiguous",
                details=white_on_white
            ))

            # Recommend more aggressive edge detection
            recommendations.append(ProcessingRecommendation(
                param_name="edge_sensitivity",
                current_value=context.get("edge_sensitivity", 0.5),
                suggested_value=0.7,
                reason="PROD_WHITE_ON_WHITE",
                confidence=0.75
            ))

        # 4. Detect halos (bright rings around product)
        halo_detected = self._detect_halo(arr, product_mask)
        metrics["halo_detected"] = halo_detected["detected"]

        if halo_detected["detected"]:
            issues.append(QCIssue(
                category=IssueCategory.PRODUCT,
                severity=Severity.WARNING,
                code="PROD_HALO_DETECTED",
                message="Halo artifact detected around product",
                details=halo_detected
            ))

            recommendations.append(ProcessingRecommendation(
                param_name="dehalo_px",
                current_value=context.get("dehalo_px", 2),
                suggested_value=min(context.get("dehalo_px", 2) + 2, 6),
                reason="PROD_HALO_DETECTED",
                confidence=halo_detected.get("severity", 0.7)
            ))

        # 5. Check for multiple products
        multi_product = self._detect_multiple_products(product_mask)
        metrics["product_components"] = multi_product["count"]

        if multi_product["detected"]:
            issues.append(QCIssue(
                category=IssueCategory.PRODUCT,
                severity=Severity.INFO,
                code="PROD_MULTIPLE",
                message=f"Multiple product regions detected ({multi_product['count']} components)",
                details=multi_product
            ))

        # 6. Detect overlays/badges in corners
        overlay_result = self._detect_overlays(arr, product_mask)
        metrics["overlay_detected"] = overlay_result["detected"]
        metrics["overlay_count"] = overlay_result["count"]

        if overlay_result["detected"]:
            overlay_info = overlay_result["overlays"][0] if overlay_result["overlays"] else {}
            issues.append(QCIssue(
                category=IssueCategory.PRODUCT,
                severity=Severity.WARNING,
                code="PROD_OVERLAY_DETECTED",
                message=f"Detected {overlay_result['count']} corner overlay(s)/badge(s) that should be removed",
                details=overlay_result
            ))

            recommendations.append(ProcessingRecommendation(
                param_name="remove_overlays",
                current_value=False,
                suggested_value=True,
                reason="PROD_OVERLAY_DETECTED",
                confidence=0.85
            ))

        return issues, metrics, recommendations

    def validate_post(
        self,
        processed_image: Image.Image,
        pre_result: Optional[QCResult]
    ) -> Tuple[List[QCIssue], Dict[str, Any]]:
        """
        Validate product after processing.
        """
        issues = []
        metrics = {}

        arr = np.array(processed_image.convert("RGB"))

        # Generate product mask
        product_mask, confidence_map = self._detect_product_mask(arr)
        metrics["post_product_coverage"] = round(np.sum(product_mask) / product_mask.size * 100, 2)

        if np.sum(product_mask) == 0:
            issues.append(QCIssue(
                category=IssueCategory.PRODUCT,
                severity=Severity.CRITICAL,
                code="PROD_NOT_DETECTED",
                message="Product not visible in processed output"
            ))
            return issues, metrics

        # Check for remaining halos
        halo_detected = self._detect_halo(arr, product_mask)
        metrics["post_halo_detected"] = halo_detected["detected"]

        if halo_detected["detected"] and halo_detected.get("severity", 0) > 0.5:
            issues.append(QCIssue(
                category=IssueCategory.PRODUCT,
                severity=Severity.WARNING,
                code="PROD_HALO_DETECTED",
                message="Halo artifact still visible after processing"
            ))

        # Compare product coverage if we have pre-result
        if pre_result and "product_coverage" in pre_result.metrics:
            pre_coverage = pre_result.metrics["product_coverage"]
            post_coverage = metrics["post_product_coverage"]

            coverage_change = abs(post_coverage - pre_coverage) / pre_coverage if pre_coverage > 0 else 0
            metrics["product_coverage_change"] = round(coverage_change * 100, 2)

            if coverage_change > 0.3:  # More than 30% change
                issues.append(QCIssue(
                    category=IssueCategory.PRODUCT,
                    severity=Severity.WARNING,
                    code="PROD_SIZE_CHANGED",
                    message=f"Product coverage changed significantly ({coverage_change:.0%})"
                ))

        return issues, metrics

    def _detect_product_mask(self, arr: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Detect product mask using multi-pass approach.

        Returns:
            Tuple of (binary mask, confidence map)
        """
        h, w = arr.shape[:2]

        # Pass 1: Basic luminance threshold
        luminance = 0.299 * arr[:,:,0] + 0.587 * arr[:,:,1] + 0.114 * arr[:,:,2]
        base_mask = luminance < 250

        # Pass 2: Color saturation (products often have some color)
        r, g, b = arr[:,:,0].astype(float), arr[:,:,1].astype(float), arr[:,:,2].astype(float)
        max_c = np.maximum(np.maximum(r, g), b)
        min_c = np.minimum(np.minimum(r, g), b)
        saturation = (max_c - min_c) / (max_c + 1e-10)

        color_mask = saturation > 0.05

        # Pass 3: Texture variance (products have texture)
        variance_mask = self._compute_local_variance(arr) > self.config.product.texture_variance_threshold

        # Pass 4: Gradient magnitude (edges)
        gradient_mask = self._compute_gradient_magnitude(arr) > self.config.product.micro_gradient_threshold

        # Combine passes with weights
        confidence = np.zeros((h, w), dtype=float)
        confidence += base_mask.astype(float) * 0.4
        confidence += color_mask.astype(float) * 0.2
        confidence += variance_mask.astype(float) * 0.2
        confidence += gradient_mask.astype(float) * 0.2

        # Threshold for final mask
        product_mask = confidence > 0.3

        return product_mask, confidence

    def _compute_local_variance(self, arr: np.ndarray, window: int = 5) -> np.ndarray:
        """
        Compute local variance in sliding windows.

        Higher variance indicates texture/product surface.
        """
        from scipy import ndimage

        gray = 0.299 * arr[:,:,0] + 0.587 * arr[:,:,1] + 0.114 * arr[:,:,2]
        gray = gray.astype(float)

        # Compute local mean
        kernel = np.ones((window, window)) / (window * window)
        local_mean = ndimage.convolve(gray, kernel, mode='reflect')

        # Compute local variance
        local_sq_mean = ndimage.convolve(gray ** 2, kernel, mode='reflect')
        variance = local_sq_mean - local_mean ** 2

        # Normalize
        variance = variance / (np.max(variance) + 1e-10)

        return variance

    def _compute_gradient_magnitude(self, arr: np.ndarray) -> np.ndarray:
        """
        Compute gradient magnitude using Sobel operator.
        """
        from scipy import ndimage

        gray = 0.299 * arr[:,:,0] + 0.587 * arr[:,:,1] + 0.114 * arr[:,:,2]
        gray = gray.astype(float)

        sobel_x = ndimage.sobel(gray, axis=1)
        sobel_y = ndimage.sobel(gray, axis=0)

        magnitude = np.sqrt(sobel_x ** 2 + sobel_y ** 2)

        # Normalize
        magnitude = magnitude / (np.max(magnitude) + 1e-10)

        return magnitude

    def _analyze_edge_confidence(
        self,
        confidence_map: np.ndarray,
        product_mask: np.ndarray
    ) -> Dict[str, float]:
        """
        Analyze confidence at product edges.
        """
        from scipy import ndimage

        # Find edge pixels
        dilated = ndimage.binary_dilation(product_mask)
        eroded = ndimage.binary_erosion(product_mask)
        edge_mask = dilated & ~eroded

        if np.sum(edge_mask) == 0:
            return {"mean": 1.0, "min": 1.0, "max": 1.0}

        edge_confidence = confidence_map[edge_mask]

        return {
            "mean": float(np.mean(edge_confidence)),
            "min": float(np.min(edge_confidence)),
            "max": float(np.max(edge_confidence)),
            "std": float(np.std(edge_confidence))
        }

    def _detect_white_on_white(
        self,
        arr: np.ndarray,
        product_mask: np.ndarray
    ) -> Dict[str, Any]:
        """
        Detect white product on white background scenario.
        """
        if np.sum(product_mask) == 0:
            return {"detected": False, "product_whiteness": 0}

        # Get product pixels
        product_pixels = arr[product_mask]

        # Calculate product whiteness (mean distance from white)
        white = np.array([255, 255, 255])
        distances = np.sqrt(np.sum((product_pixels.astype(float) - white) ** 2, axis=1))
        mean_distance = float(np.mean(distances))

        # Product is "white" if mean distance is small
        white_tolerance = self.config.product.white_tolerance
        product_whiteness = 1.0 - (mean_distance / 441.67)  # 441.67 = max RGB distance

        detected = mean_distance < (white_tolerance * 3)

        return {
            "detected": detected,
            "product_whiteness": product_whiteness,
            "mean_distance_from_white": mean_distance
        }

    def _detect_halo(
        self,
        arr: np.ndarray,
        product_mask: np.ndarray
    ) -> Dict[str, Any]:
        """
        Detect halo artifacts around product.

        Halos appear as bright rings just outside the product edge.
        """
        from scipy import ndimage

        if np.sum(product_mask) == 0:
            return {"detected": False}

        # Create ring around product (potential halo zone)
        dilated = ndimage.binary_dilation(product_mask, iterations=5)
        halo_zone = dilated & ~product_mask

        if np.sum(halo_zone) == 0:
            return {"detected": False}

        # Get luminance in halo zone
        luminance = 0.299 * arr[:,:,0] + 0.587 * arr[:,:,1] + 0.114 * arr[:,:,2]
        halo_luminance = luminance[halo_zone]

        # Halos are characterized by high brightness (close to white)
        brightness_threshold = self.config.product.halo_brightness_threshold
        bright_pixels = np.sum(halo_luminance > brightness_threshold)
        bright_ratio = bright_pixels / len(halo_luminance)

        # Also check for luminance gradient (halo fades outward)
        inner_ring = ndimage.binary_dilation(product_mask, iterations=2) & ~product_mask
        outer_ring = dilated & ~ndimage.binary_dilation(product_mask, iterations=3)

        if np.sum(inner_ring) > 0 and np.sum(outer_ring) > 0:
            inner_brightness = float(np.mean(luminance[inner_ring]))
            outer_brightness = float(np.mean(luminance[outer_ring]))

            # Halo: inner ring brighter than outer
            gradient_indicates_halo = inner_brightness > outer_brightness + 5
        else:
            gradient_indicates_halo = False

        detected = bright_ratio > 0.5 and gradient_indicates_halo
        severity = min(1.0, bright_ratio) if detected else 0.0

        return {
            "detected": detected,
            "bright_ratio": round(bright_ratio, 3),
            "gradient_indicates_halo": gradient_indicates_halo,
            "severity": severity
        }

    def _detect_multiple_products(self, product_mask: np.ndarray) -> Dict[str, Any]:
        """
        Detect if multiple separate products exist.
        """
        from scipy import ndimage

        # Label connected components
        labeled, num_features = ndimage.label(product_mask)

        if num_features <= 1:
            return {"detected": False, "count": num_features}

        # Get sizes of each component
        component_sizes = []
        for i in range(1, num_features + 1):
            size = np.sum(labeled == i)
            component_sizes.append(size)

        # Sort by size
        component_sizes.sort(reverse=True)

        # Check if secondary components are significant
        if len(component_sizes) > 1:
            largest = component_sizes[0]
            second = component_sizes[1]

            # If second component is more than 10% of largest, it's significant
            if second > largest * 0.1:
                return {
                    "detected": True,
                    "count": num_features,
                    "component_sizes": component_sizes[:5]  # Top 5
                }

        return {"detected": False, "count": 1, "note": "Secondary components too small"}

    def _detect_overlays(self, arr: np.ndarray, product_mask: np.ndarray) -> Dict[str, Any]:
        """
        Detect rectangular overlays/badges in corners/edges that should be removed.

        Overlay characteristics:
        - Located at image corners or edges (within 25% of edge)
        - Separate from main product (not connected)
        - Rectangular shape (fill_ratio > 0.50)
        - Smaller than main product (< 25% of largest component)
        - Different mean color from main product
        """
        from scipy import ndimage

        h, w = arr.shape[:2]
        labeled, num_features = ndimage.label(product_mask)

        if num_features <= 1:
            return {"detected": False, "overlays": []}

        # Get component info
        components = []
        for i in range(1, num_features + 1):
            mask = (labeled == i)
            ys, xs = np.where(mask)
            if len(xs) == 0:
                continue
            bbox = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
            area = int(np.sum(mask))
            bbox_area = (bbox[2] - bbox[0] + 1) * (bbox[3] - bbox[1] + 1)
            fill_ratio = area / bbox_area if bbox_area > 0 else 0
            mean_color = arr[mask].mean(axis=0)
            components.append({
                "label": i, "mask": mask, "bbox": bbox,
                "area": area, "fill_ratio": float(fill_ratio), "mean_color": mean_color
            })

        if not components:
            return {"detected": False, "overlays": []}

        # Sort by area - largest is main product
        components.sort(key=lambda c: c["area"], reverse=True)
        main_product = components[0]
        main_bbox = main_product["bbox"]

        overlays = []
        for comp in components[1:]:
            # Check if in corner or at edge
            x0, y0, x1, y1 = comp["bbox"]
            near_left = x0 < w * 0.25
            near_right = x1 > w * 0.75
            near_top = y0 < h * 0.25
            near_bottom = y1 > h * 0.75

            # Corner = near two perpendicular edges
            is_corner = (near_left or near_right) and (near_top or near_bottom)

            # Side badge = near left/right edge and not overlapping main product
            main_x0, main_y0, main_x1, main_y1 = main_bbox
            is_side_badge = False
            if near_left and x1 < main_x0:
                is_side_badge = True
            elif near_right and x0 > main_x1:
                is_side_badge = True

            is_at_edge = is_corner or is_side_badge

            # Check rectangularity (lowered for badges with curves)
            is_rectangular = comp["fill_ratio"] > 0.50

            # Check relative size
            is_small = comp["area"] < main_product["area"] * 0.25

            # Check color difference from main product
            color_diff = float(np.linalg.norm(comp["mean_color"] - main_product["mean_color"]))
            is_different_color = color_diff > 50

            if is_at_edge and is_rectangular and is_small and is_different_color:
                location = "corner" if is_corner else "side"
                overlays.append({
                    "bbox": comp["bbox"],
                    "area": comp["area"],
                    "fill_ratio": comp["fill_ratio"],
                    "color_diff": round(color_diff, 2),
                    "location": location
                })

        return {
            "detected": len(overlays) > 0,
            "overlays": overlays,
            "count": len(overlays)
        }
