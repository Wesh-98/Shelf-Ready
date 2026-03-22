"""
Composition Analyzer

Analyzes product placement, centering, margins, fill ratio, and canvas overflow.
Ensures proper composition for e-commerce standards.
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


class CompositionAnalyzer(BaseAnalyzer):
    """
    Analyzes image composition metrics.

    Checks:
    - Product bounding box detection
    - Fill ratio (product size vs canvas)
    - Centering (horizontal and vertical)
    - Margins (all sides)
    - Canvas overflow/truncation detection
    """

    @property
    def name(self) -> str:
        return "CompositionAnalyzer"

    def analyze_pre(
        self,
        image: Image.Image,
        work_on: str,
        context: Dict[str, Any]
    ) -> Tuple[List[QCIssue], Dict[str, Any], List[ProcessingRecommendation]]:
        """
        Analyze composition before processing.
        """
        issues = []
        metrics = {}
        recommendations = []

        arr = np.array(image.convert("RGB"))
        h, w = arr.shape[:2]

        metrics["input_width"] = w
        metrics["input_height"] = h
        metrics["input_aspect"] = round(w / h, 3) if h > 0 else 0

        # Detect product region
        product_bbox = self._detect_product_bbox(arr)

        if product_bbox is None:
            issues.append(QCIssue(
                category=IssueCategory.COMPOSITION,
                severity=Severity.CRITICAL,
                code="COMP_NO_PRODUCT",
                message="No product detected in image (entirely white/near-white)"
            ))
            return issues, metrics, recommendations

        # Store product metrics
        metrics["product_bbox"] = product_bbox.to_dict()
        metrics["product_width"] = product_bbox.width
        metrics["product_height"] = product_bbox.height
        metrics["product_area"] = product_bbox.area
        metrics["product_area_pct"] = round(product_bbox.area / (w * h) * 100, 2)

        # Get intended canvas size
        intended_size = context.get("intended_size", context.get("size", 1500))

        # 1. Analyze fill ratio
        fill_issues, fill_metrics, fill_recs = self._analyze_fill_ratio(
            product_bbox, intended_size, context
        )
        issues.extend(fill_issues)
        metrics.update(fill_metrics)
        recommendations.extend(fill_recs)

        # 2. Analyze centering
        center_issues, center_metrics = self._analyze_centering(
            product_bbox, w, h
        )
        issues.extend(center_issues)
        metrics.update(center_metrics)

        # 3. Analyze margins
        margin_issues, margin_metrics, margin_recs = self._analyze_margins(
            product_bbox, w, h, context
        )
        issues.extend(margin_issues)
        metrics.update(margin_metrics)
        recommendations.extend(margin_recs)

        # 4. Check for edge touching (canvas mode important)
        if work_on == "canvas":
            edge_issues = self._check_edge_touching(product_bbox, w, h)
            issues.extend(edge_issues)

        # 5. Check for truncation
        truncation_issues = self._check_truncation(arr, product_bbox)
        issues.extend(truncation_issues)

        return issues, metrics, recommendations

    def validate_post(
        self,
        processed_image: Image.Image,
        pre_result: Optional[QCResult]
    ) -> Tuple[List[QCIssue], Dict[str, Any]]:
        """
        Validate composition after processing.
        """
        issues = []
        metrics = {}

        arr = np.array(processed_image.convert("RGB"))
        h, w = arr.shape[:2]

        metrics["output_width"] = w
        metrics["output_height"] = h

        # 1. Check for square canvas
        if h != w:
            issues.append(QCIssue(
                category=IssueCategory.COMPOSITION,
                severity=Severity.ERROR,
                code="COMP_NOT_SQUARE",
                message=f"Output is not square: {w}x{h}",
                details={"width": w, "height": h}
            ))

        # 2. Check product still visible and not clipped
        product_bbox = self._detect_product_bbox(arr)

        if product_bbox is None:
            issues.append(QCIssue(
                category=IssueCategory.COMPOSITION,
                severity=Severity.CRITICAL,
                code="COMP_NO_PRODUCT",
                message="Product not visible in output"
            ))
            return issues, metrics

        metrics["output_product_bbox"] = product_bbox.to_dict()

        # 3. Check product not touching edges
        edge_touch_issues = self._check_edge_touching(product_bbox, w, h)
        issues.extend(edge_touch_issues)

        # 4. Check fill ratio in output
        max_dim = max(product_bbox.width, product_bbox.height)
        fill_ratio = max_dim / w
        metrics["output_fill_ratio"] = round(fill_ratio, 3)

        if fill_ratio > 0.98:
            issues.append(QCIssue(
                category=IssueCategory.COMPOSITION,
                severity=Severity.ERROR,
                code="COMP_OVERFLOW",
                message=f"Product overflows canvas (fill ratio {fill_ratio:.1%})"
            ))

        # 5. Check centering in output
        center_x, center_y = product_bbox.center
        expected_center = w / 2

        h_offset = abs(center_x - expected_center) / w
        v_offset = abs(center_y - expected_center) / h

        metrics["output_center_offset_h"] = round(h_offset, 3)
        metrics["output_center_offset_v"] = round(v_offset, 3)

        if h_offset > 0.15:
            issues.append(QCIssue(
                category=IssueCategory.COMPOSITION,
                severity=Severity.WARNING,
                code="COMP_OFF_CENTER_H",
                message=f"Product off-center horizontally ({h_offset:.1%})"
            ))

        return issues, metrics

    def _detect_product_bbox(self, arr: np.ndarray) -> Optional[BoundingBox]:
        """
        Detect product bounding box from image.

        Returns BoundingBox of detected product, or None if no product found.
        """
        # Find non-white pixels (product pixels)
        white_threshold = 250
        non_white = np.any(arr < white_threshold, axis=-1)

        ys, xs = np.where(non_white)

        if len(xs) == 0:
            return None

        # Check minimum area
        min_area = arr.shape[0] * arr.shape[1] * self.config.product.min_product_area_pct
        if len(xs) < min_area:
            return None

        return BoundingBox(
            x0=int(xs.min()),
            y0=int(ys.min()),
            x1=int(xs.max()),
            y1=int(ys.max())
        )

    def _analyze_fill_ratio(
        self,
        bbox: BoundingBox,
        intended_size: int,
        context: Dict[str, Any]
    ) -> Tuple[List[QCIssue], Dict[str, Any], List[ProcessingRecommendation]]:
        """
        Analyze product fill ratio vs intended canvas.
        """
        issues = []
        metrics = {}
        recommendations = []

        max_dim = max(bbox.width, bbox.height)
        fill_ratio = max_dim / intended_size
        metrics["fill_ratio"] = round(fill_ratio, 3)

        target_fill = context.get("target_fill", self.config.composition.target_fill_ratio)
        min_fill = self.config.composition.min_fill_ratio
        max_fill = self.config.composition.max_fill_ratio

        if fill_ratio < min_fill:
            issues.append(QCIssue(
                category=IssueCategory.COMPOSITION,
                severity=Severity.WARNING,
                code="COMP_UNDERFILL",
                message=f"Product fill ratio {fill_ratio:.1%} is below minimum {min_fill:.0%}",
                details={"current": fill_ratio, "minimum": min_fill, "target": target_fill}
            ))
            recommendations.append(ProcessingRecommendation(
                param_name="target_fill",
                current_value=target_fill,
                suggested_value=max(0.5, fill_ratio * 1.1),
                reason="COMP_UNDERFILL",
                confidence=0.7
            ))

        elif fill_ratio > max_fill:
            issues.append(QCIssue(
                category=IssueCategory.COMPOSITION,
                severity=Severity.WARNING,
                code="COMP_OVERFILL",
                message=f"Product fill ratio {fill_ratio:.1%} exceeds safe limit {max_fill:.0%}",
                details={"current": fill_ratio, "maximum": max_fill}
            ))
            recommendations.append(ProcessingRecommendation(
                param_name="margin_pct",
                current_value=context.get("margin_pct", 0.015),
                suggested_value=0.03,
                reason="COMP_OVERFILL",
                confidence=0.8
            ))

        return issues, metrics, recommendations

    def _analyze_centering(
        self,
        bbox: BoundingBox,
        img_w: int,
        img_h: int
    ) -> Tuple[List[QCIssue], Dict[str, Any]]:
        """
        Analyze product centering within image.
        """
        issues = []
        metrics = {}

        # Calculate centers
        img_center_x = img_w / 2
        img_center_y = img_h / 2
        prod_center_x, prod_center_y = bbox.center

        # Calculate offsets as percentage of image dimension
        h_offset = abs(prod_center_x - img_center_x) / img_w
        v_offset = abs(prod_center_y - img_center_y) / img_h

        metrics["center_offset_h"] = round(h_offset, 3)
        metrics["center_offset_v"] = round(v_offset, 3)

        max_offset = self.config.composition.max_center_offset

        if h_offset > max_offset:
            direction = "right" if prod_center_x > img_center_x else "left"
            issues.append(QCIssue(
                category=IssueCategory.COMPOSITION,
                severity=Severity.WARNING,
                code="COMP_OFF_CENTER_H",
                message=f"Product {h_offset:.1%} off-center to the {direction}",
                details={"offset": h_offset, "direction": direction}
            ))

        if v_offset > max_offset:
            direction = "bottom" if prod_center_y > img_center_y else "top"
            issues.append(QCIssue(
                category=IssueCategory.COMPOSITION,
                severity=Severity.WARNING,
                code="COMP_OFF_CENTER_V",
                message=f"Product {v_offset:.1%} off-center towards {direction}",
                details={"offset": v_offset, "direction": direction}
            ))

        return issues, metrics

    def _analyze_margins(
        self,
        bbox: BoundingBox,
        img_w: int,
        img_h: int,
        context: Dict[str, Any]
    ) -> Tuple[List[QCIssue], Dict[str, Any], List[ProcessingRecommendation]]:
        """
        Analyze margins on all sides.
        """
        issues = []
        metrics = {}
        recommendations = []

        # Calculate margins as percentage of dimension
        margin_left = bbox.x0 / img_w
        margin_right = (img_w - bbox.x1) / img_w
        margin_top = bbox.y0 / img_h
        margin_bottom = (img_h - bbox.y1) / img_h

        metrics["margins"] = {
            "left": round(margin_left, 3),
            "right": round(margin_right, 3),
            "top": round(margin_top, 3),
            "bottom": round(margin_bottom, 3)
        }

        min_margin = self.config.composition.min_margin_pct
        critical_margin = self.config.composition.critical_margin_pct

        # Check each margin
        margin_checks = [
            ("left", margin_left),
            ("right", margin_right),
            ("top", margin_top),
            ("bottom", margin_bottom)
        ]

        for side, margin in margin_checks:
            if margin < critical_margin:
                issues.append(QCIssue(
                    category=IssueCategory.COMPOSITION,
                    severity=Severity.ERROR,
                    code=f"COMP_{side.upper()}_CLIPPED",
                    message=f"Critical: {side} margin only {margin:.1%}",
                    details={"margin": margin, "minimum": min_margin}
                ))
            elif margin < min_margin:
                issues.append(QCIssue(
                    category=IssueCategory.COMPOSITION,
                    severity=Severity.WARNING,
                    code=f"COMP_{side.upper()}_TIGHT",
                    message=f"Tight {side} margin: {margin:.1%}",
                    details={"margin": margin, "minimum": min_margin}
                ))

        # Special check for top padding
        min_top_pad = self.config.composition.min_top_pad_px
        actual_top_pad = bbox.y0

        if actual_top_pad < min_top_pad:
            issues.append(QCIssue(
                category=IssueCategory.COMPOSITION,
                severity=Severity.WARNING,
                code="COMP_TOP_CLIPPED",
                message=f"Top padding {actual_top_pad}px below recommended {min_top_pad}px",
                details={"actual": actual_top_pad, "minimum": min_top_pad}
            ))
            recommendations.append(ProcessingRecommendation(
                param_name="min_top_pad_px",
                current_value=context.get("min_top_pad_px", 120),
                suggested_value=max(80, actual_top_pad - 20),
                reason="COMP_TOP_CLIPPED",
                confidence=0.7
            ))

        return issues, metrics, recommendations

    def _check_edge_touching(
        self,
        bbox: BoundingBox,
        img_w: int,
        img_h: int
    ) -> List[QCIssue]:
        """
        Check if product touches canvas edges.
        """
        issues = []
        threshold = self.config.composition.edge_touch_threshold_px

        touching_edges = []

        if bbox.x0 <= threshold:
            touching_edges.append("left")
        if bbox.x1 >= img_w - threshold:
            touching_edges.append("right")
        if bbox.y0 <= threshold:
            touching_edges.append("top")
        if bbox.y1 >= img_h - threshold:
            touching_edges.append("bottom")

        if touching_edges:
            issues.append(QCIssue(
                category=IssueCategory.COMPOSITION,
                severity=Severity.ERROR,
                code="COMP_EDGE_TOUCH",
                message=f"Product touches canvas edge(s): {', '.join(touching_edges)}",
                details={"edges": touching_edges}
            ))

        return issues

    def _check_truncation(
        self,
        arr: np.ndarray,
        bbox: BoundingBox
    ) -> List[QCIssue]:
        """
        Check if product appears truncated at edges.

        Looks for strong gradients at edges indicating product continues beyond.
        """
        issues = []
        h, w = arr.shape[:2]

        # Check each edge where product is close
        edge_checks = []

        if bbox.x0 < 5:
            edge_checks.append(("left", arr[:, :3, :]))
        if bbox.x1 > w - 5:
            edge_checks.append(("right", arr[:, -3:, :]))
        if bbox.y0 < 5:
            edge_checks.append(("top", arr[:3, :, :]))
        if bbox.y1 > h - 5:
            edge_checks.append(("bottom", arr[-3:, :, :]))

        truncated_edges = []

        for edge_name, edge_slice in edge_checks:
            # Check for non-white pixels at edge
            non_white_ratio = np.mean(np.any(edge_slice < 240, axis=-1))

            if non_white_ratio > 0.3:
                # Check gradient pointing into edge
                if edge_name in ("left", "right"):
                    grad = np.gradient(edge_slice.astype(float), axis=1)
                else:
                    grad = np.gradient(edge_slice.astype(float), axis=0)

                mean_grad = np.mean(np.abs(grad))

                if mean_grad > 10:  # Strong gradient = truncation likely
                    truncated_edges.append(edge_name)

        if truncated_edges:
            issues.append(QCIssue(
                category=IssueCategory.COMPOSITION,
                severity=Severity.ERROR,
                code="COMP_TRUNCATED",
                message=f"Product appears cut off at: {', '.join(truncated_edges)}",
                details={"edges": truncated_edges}
            ))

        return issues
