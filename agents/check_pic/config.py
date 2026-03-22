"""
Check-Pic Configuration

Default thresholds, settings, and constants for image quality control.
These values are calibrated for professional e-commerce product photography.
"""

from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class BackgroundConfig:
    """Background analysis thresholds"""
    # Pure white tolerance (RGB distance from 255,255,255)
    pure_white_tolerance: int = 5           # Within this = pure white
    acceptable_tolerance: int = 15          # Within this = acceptable

    # Uniformity analysis
    uniformity_grid_size: int = 8           # Grid divisions for uniformity check
    min_uniformity_score: float = 0.85      # Below this triggers warning

    # Color cast detection
    max_channel_imbalance: int = 8          # Max difference between R/G/B medians

    # Shadow detection
    shadow_gradient_threshold: float = 0.1  # Gradient strength indicating shadow

    # Impurity thresholds
    max_impure_percentage: float = 0.5      # Max % of non-white background pixels


@dataclass
class CompositionConfig:
    """Composition analysis thresholds"""
    # Fill ratio (product size vs canvas)
    target_fill_ratio: float = 0.84         # Ideal product-to-canvas ratio
    min_fill_ratio: float = 0.50            # Below this = underfill warning
    max_fill_ratio: float = 0.95            # Above this = overflow risk

    # Centering tolerance
    max_center_offset: float = 0.10         # Max offset from center (% of dimension)

    # Margins
    min_margin_pct: float = 0.015           # Minimum margin as % of canvas
    critical_margin_pct: float = 0.005      # Below this = critical

    # Padding
    min_top_pad_px: int = 80                # Minimum top padding in pixels

    # Edge detection
    edge_touch_threshold_px: int = 2        # Pixels from edge = "touching"


@dataclass
class ProductConfig:
    """Product detection thresholds"""
    # Edge detection sensitivity
    edge_sensitivity: float = 0.5           # 0.0-1.0, higher = more sensitive
    min_edge_confidence: float = 0.7        # Minimum confidence for valid edge

    # White-on-white detection
    white_tolerance: int = 12               # RGB distance for "white" classification
    texture_variance_threshold: float = 0.02    # Local variance for texture detection
    micro_gradient_threshold: float = 0.008     # Gradient for micro-edge detection
    variance_window_size: int = 5           # Window size for variance calculation

    # Product area
    min_product_area_pct: float = 0.01      # Minimum product area as % of image

    # Halo detection
    halo_brightness_threshold: int = 240    # Brightness indicating potential halo
    halo_width_threshold_px: int = 3        # Width of bright ring = halo


@dataclass
class IntegrityConfig:
    """Image integrity thresholds"""
    # Color preservation (Delta E)
    max_delta_e: float = 3.0                # Maximum acceptable color difference
    warning_delta_e: float = 2.0            # Warning threshold

    # Histogram similarity
    min_histogram_correlation: float = 0.90 # Minimum correlation with reference

    # Compression artifacts
    max_artifact_score: float = 0.3         # Above this = too many artifacts
    max_jpeg_generations: int = 2           # Estimated save cycles


@dataclass
class QualityConfig:
    """General quality thresholds"""
    # Resolution
    min_dimension: int = 500                # Minimum width/height
    recommended_dimension: int = 1500       # Recommended size

    # Sharpness
    min_sharpness_score: float = 0.3        # Below this = blurry

    # Noise
    max_noise_level: float = 0.05           # Above this = noisy


@dataclass
class CheckPicConfig:
    """Master configuration for Check-Pic agent"""
    background: BackgroundConfig = field(default_factory=BackgroundConfig)
    composition: CompositionConfig = field(default_factory=CompositionConfig)
    product: ProductConfig = field(default_factory=ProductConfig)
    integrity: IntegrityConfig = field(default_factory=IntegrityConfig)
    quality: QualityConfig = field(default_factory=QualityConfig)

    # Scoring weights for overall quality score
    weights: Dict[str, float] = field(default_factory=lambda: {
        "background": 0.25,
        "composition": 0.25,
        "product": 0.20,
        "integrity": 0.15,
        "quality": 0.15
    })

    # Overall pass thresholds
    pass_score: float = 85.0                # Minimum score to pass
    warning_score: float = 70.0             # Below this = warning

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary"""
        return {
            "background": self.background.__dict__,
            "composition": self.composition.__dict__,
            "product": self.product.__dict__,
            "integrity": self.integrity.__dict__,
            "quality": self.quality.__dict__,
            "weights": self.weights,
            "pass_score": self.pass_score,
            "warning_score": self.warning_score
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CheckPicConfig':
        """Create config from dictionary"""
        config = cls()

        if "background" in data:
            for k, v in data["background"].items():
                if hasattr(config.background, k):
                    setattr(config.background, k, v)

        if "composition" in data:
            for k, v in data["composition"].items():
                if hasattr(config.composition, k):
                    setattr(config.composition, k, v)

        if "product" in data:
            for k, v in data["product"].items():
                if hasattr(config.product, k):
                    setattr(config.product, k, v)

        if "integrity" in data:
            for k, v in data["integrity"].items():
                if hasattr(config.integrity, k):
                    setattr(config.integrity, k, v)

        if "quality" in data:
            for k, v in data["quality"].items():
                if hasattr(config.quality, k):
                    setattr(config.quality, k, v)

        if "weights" in data:
            config.weights.update(data["weights"])

        if "pass_score" in data:
            config.pass_score = data["pass_score"]

        if "warning_score" in data:
            config.warning_score = data["warning_score"]

        return config


# Default configuration instance
DEFAULT_CONFIG = CheckPicConfig()


# Issue codes for reference
ISSUE_CODES = {
    # Background issues
    "BG_IMPURE": "Background contains non-white pixels",
    "BG_NOT_UNIFORM": "Background color is not uniform",
    "BG_COLOR_CAST": "Background has color cast",
    "BG_SHADOW_SPILL": "Shadow bleeding into background",
    "BG_ALREADY_CLEAN": "Background already clean (info)",

    # Composition issues
    "COMP_OFF_CENTER_H": "Product off-center horizontally",
    "COMP_OFF_CENTER_V": "Product off-center vertically",
    "COMP_UNDERFILL": "Product too small in frame",
    "COMP_OVERFILL": "Product too large, risk of clipping",
    "COMP_OVERFLOW": "Product extends beyond canvas",
    "COMP_TOP_CLIPPED": "Insufficient top margin",
    "COMP_EDGE_TOUCH": "Product touching canvas edge",
    "COMP_TRUNCATED": "Product appears cut off",
    "COMP_NO_PRODUCT": "No product detected",
    "COMP_NOT_SQUARE": "Output canvas is not square",

    # Product issues
    "PROD_EDGE_AMBIGUOUS": "Product edges unclear",
    "PROD_WHITE_ON_WHITE": "White product on white background (ambiguous)",
    "PROD_HALO_DETECTED": "Halo artifact around product",
    "PROD_MULTIPLE": "Multiple products detected",
    "PROD_LOW_CONFIDENCE": "Low confidence in product detection",

    # Integrity issues
    "INT_COLOR_SHIFT": "Product color has shifted",
    "INT_HISTOGRAM_MISMATCH": "Color histogram differs from original",
    "INT_COMPRESSION_ARTIFACTS": "Excessive compression artifacts",
    "INT_RESAMPLED": "Image appears resampled/resized",

    # Quality issues
    "QUAL_LOW_RES": "Image resolution too low",
    "QUAL_BLURRY": "Image appears blurry",
    "QUAL_NOISY": "Image has excessive noise"
}
