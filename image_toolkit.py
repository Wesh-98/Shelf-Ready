import os, argparse, zipfile, sys, tempfile, concurrent.futures
from collections import deque
import numpy as np
from scipy.ndimage import label as _ndlabel
try:
    import pillow_avif
except Exception:
    try:
        import pillow_avif_plugin
    except Exception:
        pass
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pass
from PIL import Image, ImageOps, ImageFilter, ImageEnhance, ImageDraw, ImageFont
import json

# Check-Pic QC integration
try:
    from agents.check_pic import CheckPicAgent
    from agents.check_pic.models import QCResult
    CHECKPIC_AVAILABLE = True
except ImportError:
    CHECKPIC_AVAILABLE = False

def add_bottom_shadow(canvas_rgb, alpha_pct=70):
    # alpha_pct 0–100 → convert to 0–255
    a = max(0, min(100, int(alpha_pct)))
    A = int(255 * (a/100.0))
    w, h = canvas_rgb.size
    shadow = Image.new("RGBA", (w, h), (0,0,0,0))
    draw = ImageDraw.Draw(shadow)

    # ellipse sized to 65% width, very short height
    ew, eh = int(w*0.65), max(8, int(h*0.06))
    ex0 = (w - ew)//2
    ex1 = ex0 + ew
    ey1 = h - int(h*0.07)
    ey0 = ey1 - eh

    draw.ellipse([ex0, ey0, ex1, ey1], fill=(0,0,0,A))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=int(min(w,h)*0.03)))

    out = canvas_rgb.convert("RGBA")
    out.alpha_composite(shadow)
    return out.convert("RGB")


def add_quantity_badge(canvas_rgb, badge_text, overlap_px=6):
    """
    Add a quantity badge (full pill shape) to the left side of the product.
    - White fill with teal outline
    - Bold black text: number larger, unit smaller (both bold)
    - Text centered in the pill
    - Positioned on left side, in the bottom half of the product
    """
    import re

    if not badge_text or not badge_text.strip():
        return canvas_rgb

    badge_text = badge_text.strip().upper()
    w, h = canvas_rgb.size

    # Find product bounding box by detecting non-white pixels
    arr = np.array(canvas_rgb)
    non_white = np.any(arr < 250, axis=-1)
    ys, xs = np.where(non_white)

    if len(xs) == 0:
        return canvas_rgb  # No product found

    prod_left_overall = xs.min()
    prod_top = ys.min()
    prod_bottom = ys.max()
    prod_height = prod_bottom - prod_top
    prod_center_y = prod_top + prod_height // 2

    # Calculate badge Y position first (72% down the product height)
    badge_center_y = prod_top + int(prod_height * 0.72)

    # Find product's left edge AT THE BADGE'S Y POSITION (not overall min)
    # Look at a vertical band around the badge position
    badge_y_range = int(prod_height * 0.15)  # Check 15% of height around badge position
    y_min_check = max(prod_top, badge_center_y - badge_y_range)
    y_max_check = min(prod_bottom, badge_center_y + badge_y_range)

    # Get the leftmost X for pixels in that Y range
    mask_at_badge_height = (ys >= y_min_check) & (ys <= y_max_check)
    if np.any(mask_at_badge_height):
        prod_left = xs[mask_at_badge_height].min()
    else:
        prod_left = prod_left_overall

    # Calculate font size based on canvas size (larger for better visibility)
    font_size = max(32, int(w * 0.048))

    # Helper to load bold font
    def load_bold_font(size):
        for fname in ["arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf"]:
            try:
                return ImageFont.truetype(fname, size)
            except:
                pass
        return ImageFont.load_default()

    # Split text into number and unit parts (e.g., "16 OZ" -> "16" and "Oz")
    match = re.match(r'^([\d.]+)\s*(.*)$', badge_text)
    if match:
        number_part = match.group(1)
        unit_part = match.group(2).capitalize()  # Capitalize first letter (e.g., "OZ" -> "Oz", "PIECES" -> "Pieces")
    else:
        number_part = badge_text
        unit_part = ""

    # Number uses base font (bold), unit uses smaller bold font (85% of number)
    num_font = load_bold_font(font_size)
    unit_font_size = int(font_size * 0.85)
    unit_font = load_bold_font(unit_font_size)

    # Create a temporary image to measure text
    temp_img = Image.new("RGBA", (1, 1))
    temp_draw = ImageDraw.Draw(temp_img)

    # Measure number part with base font
    num_bbox = temp_draw.textbbox((0, 0), number_part, font=num_font)
    num_w = num_bbox[2] - num_bbox[0]
    num_h = num_bbox[3] - num_bbox[1]

    # Measure unit part with smaller font
    if unit_part:
        unit_bbox = temp_draw.textbbox((0, 0), unit_part, font=unit_font)
        unit_w = unit_bbox[2] - unit_bbox[0]
        unit_h = unit_bbox[3] - unit_bbox[1]
        space_w = int(font_size * 0.12)  # Reduced gap between number and unit
    else:
        unit_w = 0
        unit_h = 0
        space_w = 0

    # Total text dimensions
    text_w = num_w + space_w + unit_w
    text_h = max(num_h, unit_h)

    # Badge dimensions (pill shape with padding)
    pad_x = int(font_size * 0.6)
    pad_y = int(font_size * 0.4)
    badge_w = text_w + pad_x * 2
    badge_h = text_h + pad_y * 2
    radius = badge_h // 2  # Fully rounded ends for pill shape

    # Position: badge to the left of product, with right edge tucking behind product
    # Right edge of badge should overlap into product by overlap_px
    # Use the local left edge at badge height (already calculated above)
    badge_x = prod_left - badge_w + overlap_px
    badge_y = badge_center_y - badge_h // 2

    # Ensure badge doesn't go off canvas left edge
    if badge_x < 5:
        badge_x = 5
    badge_y = max(prod_center_y, min(badge_y, h - badge_h - 5))

    # Create badge on RGBA layer
    badge_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(badge_layer)

    # Colors
    outline_color = (0, 128, 128)  # Teal
    fill_color = (255, 255, 255, 255)  # White
    outline_width = max(4, int(font_size * 0.12))  # Thicker solid outline

    # Draw C-shape (curved left, flat right edge)
    # Fill the interior with white
    # Left semicircle fill
    draw.pieslice(
        [badge_x, badge_y, badge_x + badge_h, badge_y + badge_h],
        start=90, end=270, fill=fill_color
    )
    # Rectangle fill (extends to right edge)
    draw.rectangle(
        [badge_x + radius, badge_y, badge_x + badge_w, badge_y + badge_h],
        fill=fill_color
    )

    # Draw teal outline (C-shape - no right curve)
    # Left arc
    draw.arc(
        [badge_x, badge_y, badge_x + badge_h, badge_y + badge_h],
        start=90, end=270, fill=outline_color, width=outline_width
    )
    # Top line (extends to right edge)
    draw.line(
        [badge_x + radius, badge_y + outline_width // 2,
         badge_x + badge_w, badge_y + outline_width // 2],
        fill=outline_color, width=outline_width
    )
    # Bottom line (extends to right edge)
    draw.line(
        [badge_x + radius, badge_y + badge_h - outline_width // 2,
         badge_x + badge_w, badge_y + badge_h - outline_width // 2],
        fill=outline_color, width=outline_width
    )

    # Calculate centered text position (horizontally centered in full badge)
    total_text_w = num_w + space_w + unit_w
    badge_center_x = badge_x + badge_w // 2
    badge_center_y = badge_y + badge_h // 2

    # Calculate text start position to center the combined text
    text_start_x = badge_center_x - total_text_w // 2

    # Draw number part (larger bold font) - vertically centered using anchor
    draw.text((text_start_x, badge_center_y), number_part, font=num_font, fill=(0, 0, 0, 255), anchor="lm")

    # Draw unit part (smaller bold font, vertically centered same as number)
    if unit_part:
        unit_x = text_start_x + num_w + space_w
        # Use same vertical center anchor for both - keeps them on same line
        draw.text((unit_x, badge_center_y), unit_part, font=unit_font, fill=(0, 0, 0, 255), anchor="lm")

    # Composite onto original image
    result = canvas_rgb.convert("RGBA")
    result = Image.alpha_composite(result, badge_layer)
    return result.convert("RGB")


def load_rgb(path):
    im = Image.open(path)
    try: im.load()
    except Exception: pass
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "LA"):
        bg = Image.new("RGB", im.size, (255,255,255))
        alpha = im.split()[-1] if im.mode == "RGBA" else im.convert("RGBA").split()[-1]
        bg.paste(im, mask=alpha); im = bg
    elif im.mode != "RGB":
        im = im.convert("RGB")
    return im

def save_jpg(im, out_path, quality=95, progressive=True, optimize=True, dpi=None):
    kw = dict(quality=int(quality), progressive=bool(progressive), optimize=bool(optimize))
    if dpi:
        kw["dpi"] = (int(dpi), int(dpi))
    im.save(out_path, "JPEG", **kw)

def rgb_to_hsv01(arr):
    f = arr.astype(np.float32) / 255.0
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    cmax = np.maximum(np.maximum(r,g), b)
    cmin = np.minimum(np.minimum(r,g), b)
    d = cmax - cmin
    with np.errstate(divide='ignore', invalid='ignore'):
        s = np.where(cmax==0, 0, d/cmax)
    v = cmax
    return s, v
def border_median_color(rgb, frac=0.02):
    h,w,_ = rgb.shape
    bw, bh = max(1,int(w*frac)), max(1,int(h*frac))
    border = np.concatenate([
        rgb[:, :bw, :].reshape(-1,3),
        rgb[:, -bw:, :].reshape(-1,3),
        rgb[:bh, :, :].reshape(-1,3),
        rgb[-bh:, :, :].reshape(-1,3),
    ], axis=0)
    return np.median(border, axis=0)

def auto_detect_work_mode(im):
    """
    Auto-detect whether image needs background cleaning or is already on white.
    Returns: "image" if needs cleaning, "canvas" if already clean white background.
    """
    arr = np.array(im.convert("RGB"))
    bg_med = border_median_color(arr)

    # Check if border is near-white
    is_white_bg = np.all(bg_med > 245)

    # Also check what percentage of border pixels are white
    h, w = arr.shape[:2]
    bw, bh = max(1, int(w * 0.03)), max(1, int(h * 0.03))
    border_pixels = np.concatenate([
        arr[:bh, :, :].reshape(-1, 3),
        arr[-bh:, :, :].reshape(-1, 3),
        arr[:, :bw, :].reshape(-1, 3),
        arr[:, -bw:, :].reshape(-1, 3),
    ], axis=0)

    # Count near-white pixels in border
    white_dist = np.sqrt(np.sum((border_pixels.astype(float) - 255) ** 2, axis=1))
    white_ratio = np.sum(white_dist < 20) / len(white_dist)

    # If >90% of border is white, it's already a clean canvas
    if is_white_bg and white_ratio > 0.90:
        return "canvas"
    return "image"

def analyze_image_quality(im):
    """
    Analyze image quality and return metrics + enhancement recommendations.

    Returns dict with:
    - blur_score: 0-1 (1 = sharp, 0 = very blurry)
    - color_score: 0-1 (1 = vibrant, 0 = dull/desaturated)
    - brightness_score: 0-1 (0.5 = ideal, 0 = dark, 1 = overexposed)
    - noise_score: 0-1 (1 = clean, 0 = noisy)
    - overall_quality: 0-100
    - fixable: bool (can be enhanced)
    - recommendations: dict of suggested parameter adjustments
    """
    arr = np.array(im.convert("RGB")).astype(np.float32)
    h, w = arr.shape[:2]

    # 1. BLUR DETECTION using Laplacian variance
    gray = 0.299 * arr[:,:,0] + 0.587 * arr[:,:,1] + 0.114 * arr[:,:,2]
    # Compute Laplacian manually (edge detection)
    laplacian = (
        np.roll(gray, 1, axis=0) + np.roll(gray, -1, axis=0) +
        np.roll(gray, 1, axis=1) + np.roll(gray, -1, axis=1) - 4 * gray
    )
    blur_variance = np.var(laplacian)
    # Normalize: <100 = very blurry, >500 = sharp
    blur_score = min(1.0, blur_variance / 500)

    # 2. COLOR/SATURATION analysis
    r, g, b = arr[:,:,0]/255, arr[:,:,1]/255, arr[:,:,2]/255
    cmax = np.maximum(np.maximum(r, g), b)
    cmin = np.minimum(np.minimum(r, g), b)
    saturation = np.where(cmax > 0, (cmax - cmin) / (cmax + 1e-10), 0)

    # Exclude near-white pixels (background) from saturation calculation
    non_white_mask = cmax < 0.95
    if np.sum(non_white_mask) > 100:
        mean_saturation = np.mean(saturation[non_white_mask])
    else:
        mean_saturation = np.mean(saturation)

    # Normalize: <0.15 = dull, >0.4 = vibrant
    color_score = min(1.0, mean_saturation / 0.4)

    # 3. BRIGHTNESS analysis
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    if np.sum(non_white_mask) > 100:
        mean_brightness = np.mean(luminance[non_white_mask])
    else:
        mean_brightness = np.mean(luminance)
    # Score: 0.5 is ideal, 0 or 1 are bad
    brightness_score = 1 - abs(mean_brightness - 0.5) * 2

    # 4. NOISE estimation (using local variance in smooth regions)
    # Compute local variance in 3x3 windows
    from PIL import ImageFilter
    gray_img = im.convert("L")
    smooth = gray_img.filter(ImageFilter.GaussianBlur(2))
    diff = np.abs(np.array(gray_img).astype(float) - np.array(smooth).astype(float))
    noise_level = np.mean(diff)
    # Normalize: <3 = clean, >10 = noisy
    noise_score = max(0, 1 - noise_level / 10)

    # 5. OVERALL QUALITY
    overall_quality = (
        blur_score * 35 +       # Blur is most important
        color_score * 25 +
        brightness_score * 20 +
        noise_score * 20
    )

    # 6. RECOMMENDATIONS
    recommendations = {}

    # Sharpening recommendation
    if blur_score < 0.6:
        if blur_score < 0.3:
            # Too blurry to fix well
            recommendations["sharpen_percent"] = 200
            recommendations["sharpen_radius"] = 2.0
            recommendations["warning"] = "Image is very blurry - consider using a higher quality source"
        else:
            # Moderately soft - can enhance
            recommendations["sharpen_percent"] = int(140 + (0.6 - blur_score) * 150)
            recommendations["sharpen_radius"] = 1.3 + (0.6 - blur_score)

    # Color/saturation recommendation
    if color_score < 0.5:
        # Dull colors - boost contrast and saturation
        boost = 1 + (0.5 - color_score) * 0.3
        recommendations["product_contrast"] = round(min(1.25, 1.05 * boost), 2)
        recommendations["color_boost"] = round(boost, 2)

    # Brightness recommendation
    if brightness_score < 0.6:
        if mean_brightness < 0.4:
            recommendations["brightness_adjust"] = "Image is dark - may need exposure correction"
        elif mean_brightness > 0.7:
            recommendations["brightness_adjust"] = "Image is overexposed"

    # Determine if fixable
    fixable = blur_score >= 0.2 and overall_quality >= 30

    return {
        "blur_score": round(blur_score, 3),
        "color_score": round(color_score, 3),
        "brightness_score": round(brightness_score, 3),
        "noise_score": round(noise_score, 3),
        "overall_quality": round(overall_quality, 1),
        "fixable": fixable,
        "recommendations": recommendations,
        "metrics": {
            "laplacian_variance": round(blur_variance, 1),
            "mean_saturation": round(mean_saturation, 3),
            "mean_brightness": round(mean_brightness, 3),
            "noise_level": round(noise_level, 2)
        }
    }
def flood_from_edges(allowed):
    labeled, _ = _ndlabel(allowed)
    border = np.concatenate([labeled[0, :], labeled[-1, :],
                              labeled[:, 0], labeled[:, -1]])
    ids = set(border.tolist())
    ids.discard(0)
    if not ids:
        return np.zeros(allowed.shape, dtype=bool)
    return np.isin(labeled, list(ids))
def build_bg_mask(rgb_u8, mode="auto", top_clean_pct=0.0):
    s, v = rgb_to_hsv01(rgb_u8)
    bg_med = border_median_color(rgb_u8)
    dist = np.sqrt(((rgb_u8.astype(np.float32) - bg_med.astype(np.float32))**2).sum(axis=-1))

    # Check if background is already near-white (clean product image)
    # Use both median AND corner samples to handle shadows at edges
    bg_is_white = np.all(bg_med > 240)

    # Also check corners - less likely to have shadows
    h, w = rgb_u8.shape[:2]
    corner_size = max(5, min(20, h//20, w//20))
    corners = [
        rgb_u8[:corner_size, :corner_size],           # top-left
        rgb_u8[:corner_size, -corner_size:],          # top-right
        rgb_u8[-corner_size:, :corner_size],          # bottom-left
        rgb_u8[-corner_size:, -corner_size:],         # bottom-right
    ]
    corner_pixels = np.concatenate([c.reshape(-1, 3) for c in corners], axis=0)
    corner_median = np.median(corner_pixels, axis=0)
    corners_are_white = np.all(corner_median > 235)

    # If corners are white but border median isn't (shadow at edge), treat as white
    if corners_are_white and not bg_is_white:
        bg_is_white = True
        bg_med = corner_median  # Use corner color as reference instead

    # Calculate background saturation to distinguish saturated (blue/pink) from desaturated (beige/cream)
    bg_r, bg_g, bg_b = bg_med[0]/255.0, bg_med[1]/255.0, bg_med[2]/255.0
    bg_max, bg_min = max(bg_r, bg_g, bg_b), min(bg_r, bg_g, bg_b)
    bg_sat = (bg_max - bg_min) / bg_max if bg_max > 0 else 0

    if bg_is_white:
        # For white backgrounds, ONLY use color distance - no brightness/saturation criteria
        # This prevents white product areas (labels, caps) from being detected as background
        cand_bright_low_sat = dist < 12  # Only very close to white bg
        cand_shadow_low_sat = dist < 12  # Same - only color distance
        cand_bg_close = dist < 15.0
        cand_bg_loose = dist < 20.0
    elif bg_sat > 0.2:
        # Saturated colored background (blue, pink, green, etc.)
        # Use color distance as primary criteria - products typically won't match saturated colors
        cand_bright_low_sat = (v > 0.88) & (s < 0.33)  # Original thresholds OK for saturated BG
        cand_shadow_low_sat = (v > 0.60) & (s < 0.18)
        cand_bg_close = dist < 40.0   # Color distance works well for saturated backgrounds
        cand_bg_loose = dist < 58.0
    else:
        # Desaturated colored background (beige, cream, tan)
        # Use TIGHT thresholds to avoid eating into light-colored products
        cand_bright_low_sat = (v > 0.92) & (s < 0.15)  # Very strict
        cand_shadow_low_sat = (v > 0.75) & (s < 0.10)  # More conservative
        cand_bg_close = dist < 25.0   # Tighter color distance
        cand_bg_loose = dist < 35.0   # Tighter loose threshold

    allowed = cand_bg_close | cand_bright_low_sat | (cand_shadow_low_sat & cand_bg_loose)

    # Detect shadows (darker, low saturation areas) for ALL backgrounds
    # Shadows are grayish areas - low saturation, medium-to-low brightness
    if bg_is_white:
        # For white backgrounds, use tight distance-only shadow detection.
        # The brightness + saturation criteria used for colored backgrounds are too broad
        # here — they catch white/grey product surfaces (wrapper ends, labels, caps) because
        # those areas are also bright, low-saturation, and close to white.
        # Keeping dist < 25 only catches near-pure-white areas (true dead-space / soft shadow),
        # not the product packaging itself.
        shadow_mask = (s < 0.07) & (dist < 25)
    else:
        # For colored backgrounds, shadows are darker with some color similarity
        shadow_mask = (v < 0.7) & (s < 0.2) & (dist < 60)
    allowed = allowed | shadow_mask

    bg_flood = flood_from_edges(allowed)
    lum = (0.299*rgb_u8[...,0] + 0.587*rgb_u8[...,1] + 0.114*rgb_u8[...,2]) / 255.0
    gy = np.abs(np.roll(lum, -1, axis=0) - lum)
    gx = np.abs(np.roll(lum, -1, axis=1) - lum)
    grad = np.maximum(gx, gy)
    # For white backgrounds use a lower edge threshold so the flood stops at the softer
    # product–background boundary (e.g. rounded wrapper ends that fade gradually into white).
    if bg_is_white:
        edge_thresh = 0.08 if mode != "aggressive" else 0.12
    elif bg_sat > 0.2:
        edge_thresh = 0.12 if mode != "aggressive" else 0.16
    else:
        edge_thresh = 0.08  # Desaturated backgrounds need tighter edge protection
    edge_strong = grad > edge_thresh
    bg_mask = bg_flood & (~edge_strong)
    m = Image.fromarray((bg_mask*255).astype(np.uint8))
    if mode == "safe":
        m = m.filter(ImageFilter.MinFilter(3))
    elif mode == "aggressive":
        m = m.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(3))
    bg_mask = np.array(m) > 127
    if top_clean_pct and top_clean_pct > 0:
        h = rgb_u8.shape[0]
        top = int(h * float(top_clean_pct))
        # Only force top pixels to background if they actually look like background
        # This prevents clipping product that extends to the top edge
        top_region = rgb_u8[:max(1, top), :]
        top_dist = np.sqrt(((top_region - bg_med)**2).sum(axis=-1))
        # Only mark as background if close to background color (dist < 50)
        bg_mask[:max(1, top), :] = bg_mask[:max(1, top), :] | (top_dist < 50)
    return bg_mask
def largest_component_only(nonwhite_mask):
    labeled, n = _ndlabel(nonwhite_mask)
    if n == 0:
        return nonwhite_mask
    counts = np.bincount(labeled.ravel())
    counts[0] = 0
    return labeled == counts.argmax()

def label_components(mask):
    return _ndlabel(mask)

def detect_and_remove_overlays(rgb, product_mask):
    """
    Detect and mask out corner/edge overlays/badges.
    Returns updated product mask with overlays removed.

    Detects badges that are:
    - Separate from the main product (not connected)
    - Located at edges or corners of the image
    - Relatively small compared to main product
    - Reasonably rectangular in shape
    """
    h, w = rgb.shape[:2]
    labeled, num_features = label_components(product_mask)

    if num_features <= 1:
        return product_mask

    # Find component sizes and bboxes
    components = []
    for i in range(1, num_features + 1):
        mask = (labeled == i)
        ys, xs = np.where(mask)
        if len(xs) == 0:
            continue
        bbox = (xs.min(), ys.min(), xs.max(), ys.max())
        area = np.sum(mask)
        bbox_area = (bbox[2] - bbox[0] + 1) * (bbox[3] - bbox[1] + 1)
        fill_ratio = area / bbox_area if bbox_area > 0 else 0
        components.append({"label": i, "area": area, "bbox": bbox, "fill_ratio": fill_ratio})

    if not components:
        return product_mask

    # Largest component is the product
    components.sort(key=lambda c: c["area"], reverse=True)
    main_label = components[0]["label"]
    main_area = components[0]["area"]
    main_bbox = components[0]["bbox"]

    # Remove edge/corner overlays
    clean_mask = product_mask.copy()
    for comp in components[1:]:
        x0, y0, x1, y1 = comp["bbox"]

        # Is it near any edge? (within 25% of edge)
        near_left = x0 < w * 0.25
        near_right = x1 > w * 0.75
        near_top = y0 < h * 0.25
        near_bottom = y1 > h * 0.75

        # Corner = near two perpendicular edges
        is_corner = (near_left or near_right) and (near_top or near_bottom)

        # Edge = near any single edge but NOT overlapping main product horizontally
        # This catches left/right side badges like "7 oz"
        main_x0, main_y0, main_x1, main_y1 = main_bbox
        is_side_badge = False
        if near_left and x1 < main_x0:  # Badge is to the left of main product
            is_side_badge = True
        elif near_right and x0 > main_x1:  # Badge is to the right of main product
            is_side_badge = True

        is_at_edge = is_corner or is_side_badge

        # Is it rectangular-ish and small?
        is_rectangular = comp["fill_ratio"] > 0.50  # Lowered threshold for badges with curves
        is_small = comp["area"] < main_area * 0.30

        if is_at_edge and is_rectangular and is_small:
            # Remove this component
            clean_mask[labeled == comp["label"]] = False

    return clean_mask
def clamp_white_background(im, white_floor=245, neutrality_tol=18):
    arr = np.asarray(im).astype(np.int16)
    r,g,b = arr[...,0], arr[...,1], arr[...,2]
    maxc = np.maximum.reduce([r,g,b])
    minc = np.minimum.reduce([r,g,b])
    near_white = maxc >= white_floor
    neutral = (maxc - minc) <= neutrality_tol
    mask = near_white & neutral
    arr[mask] = [255,255,255]
    return Image.fromarray(arr.astype(np.uint8), "RGB")

def square_canvas(im_rgb, size=1500, fit_mode="pad", target_fill=0.84,
                  min_top_pad_px=120, vertical_bias=0.58, allow_upscale=True, no_downscale=False):
    W, H = im_rgb.size

    if fit_mode == "fit":
        # Scale to fill target_fill of the canvas (based on the larger dimension)
        # target_fill=0.95 means product should fill 95% of canvas height or width
        target_dim = int(size * target_fill)
        ratio = min(target_dim/W, target_dim/H)

        # Determine if we should scale
        should_scale = False
        if ratio > 1 and allow_upscale:  # Image smaller than target, upscale allowed
            should_scale = True
        elif ratio < 1 and not no_downscale:  # Image larger than target, downscale allowed
            should_scale = True

        if should_scale:
            im = im_rgb.resize((int(W*ratio), int(H*ratio)), Image.Resampling.LANCZOS)
        else:
            im = im_rgb.copy()

        # If image is larger than canvas and no_downscale, expand canvas to fit
        if no_downscale and (im.width > size or im.height > size):
            canvas_size = max(size, im.width, im.height)
            canvas = Image.new("RGB", (canvas_size, canvas_size), (255,255,255))
        else:
            canvas = Image.new("RGB", (size,size), (255,255,255))

        x = (canvas.width - im.width)//2
        y = (canvas.height - im.height)//2
        # Apply min_top_pad constraint but don't push off bottom
        if y < min_top_pad_px:
            max_y = canvas.height - im.height - 10
            y = min(min_top_pad_px, max(0, max_y))
        canvas.paste(im, (x,y))
        return canvas

    if fit_mode == "crop_fill":
        scale = max(size/W, size/H)
        if scale < 1 or allow_upscale:
            new_w, new_h = int(W*scale), int(H*scale)
            im = im_rgb.resize((new_w, new_h), Image.Resampling.LANCZOS)
        else:
            im = im_rgb.copy(); new_w, new_h = im.size
        x0 = (new_w - size)//2
        y0 = int((new_h - size) * (1 - vertical_bias))
        x0 = max(0, min(x0, new_w - size)); y0 = max(0, min(y0, new_h - size))
        return im.crop((x0, y0, x0+size, y0+size))

    def _apply_scale(src, ratio, allow_up, no_dn):
        if (ratio > 1 and allow_up) or (ratio < 1 and not no_dn):
            return src.resize((int(src.width * ratio), int(src.height * ratio)),
                               Image.Resampling.LANCZOS)
        return src.copy()

    if fit_mode == "fill_height":
        # Scale so product HEIGHT fills target_fill of canvas; width follows aspect ratio.
        # If the scaled width would overflow the canvas, fall back to width constraint.
        target_h = int(size * target_fill)
        im = _apply_scale(im_rgb, target_h / H, allow_upscale, no_downscale)
        if im.width > size:
            im = _apply_scale(im, size / im.width, allow_upscale, no_downscale)

        canvas = Image.new("RGB", (size, size), (255, 255, 255))
        x = (size - im.width) // 2
        top_pad = max(20, min_top_pad_px // 3)
        y = max(top_pad, (size - im.height) // 2)
        y = min(y, max(0, size - im.height - top_pad))
        canvas.paste(im, (x, y))
        return canvas

    if fit_mode == "fill_width":
        # Scale so product WIDTH fills target_fill of canvas; height follows aspect ratio.
        # Designed for wide/landscape products (protein bars, flat-packs) so the left and
        # right ends reach the canvas edges with no white side-space.
        # target_fill=0.99 → bar nearly edge-to-edge; =1.0 → truly edge-to-edge.
        # If the scaled height overflows, fall back to height constraint instead.
        target_w = int(size * target_fill)
        im = _apply_scale(im_rgb, target_w / W, allow_upscale, no_downscale)
        if im.height > size:
            im = _apply_scale(im, size / im.height, allow_upscale, no_downscale)

        canvas = Image.new("RGB", (size, size), (255, 255, 255))
        # Centre horizontally — for target_fill≥1 this will be 0 (flush to edges)
        x = max(0, (size - im.width) // 2)
        # Always dead-centre vertically; do NOT apply min_top_pad for landscape products
        y = max(0, (size - im.height) // 2)
        canvas.paste(im, (x, y))
        return canvas

    # PAD mode - Scale product to fill target_fill of canvas, then center on white
    im = im_rgb.copy()

    # Calculate target dimension based on target_fill
    target_dim = int(size * target_fill)

    # Scale to fit within target dimension (preserving aspect ratio)
    ratio = min(target_dim / im.width, target_dim / im.height)

    # Determine if we should scale
    should_scale = False
    if ratio > 1 and allow_upscale:  # Image smaller than target, upscale allowed
        should_scale = True
    elif ratio < 1 and not no_downscale:  # Image larger than target, downscale allowed
        should_scale = True

    if should_scale:
        new_w = int(im.width * ratio)
        new_h = int(im.height * ratio)
        im = im.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # If image is larger than canvas and no_downscale, expand canvas to fit
    if no_downscale and (im.width > size or im.height > size):
        canvas_size = max(size, im.width, im.height)
        canvas = Image.new("RGB", (canvas_size, canvas_size), (255, 255, 255))
    else:
        canvas = Image.new("RGB", (size, size), (255, 255, 255))

    x = (canvas.width - im.width) // 2
    y = (canvas.height - im.height) // 2

    # Apply min_top_pad constraint (shift down if too close to top)
    # But don't push the image off the bottom
    if y < min_top_pad_px:
        max_y = canvas.height - im.height - 10  # Leave at least 10px at bottom
        y = min(min_top_pad_px, max(0, max_y))

    canvas.paste(im, (x, y))
    return canvas

def clean_product_image(im, size=1500, allow_upscale=False, mode="auto", dehalo_px=2,
                        edge_feather=1.0, sharpen_radius=1.3, sharpen_percent=140,
                        sharpen_threshold=2, product_contrast=1.05, largest_scrub=True,
                        top_clean_pct=0.08, margin_pct=0.015, white_floor=245, neutrality_tol=18,
                        fit_mode="pad", work_on="image", target_fill=0.84, min_top_pad_px=120, vertical_bias=0.58,
                        no_bg_clean=False, no_downscale=False, remove_overlays=True):
    if work_on == "image" and not no_bg_clean:
        arr = np.array(im.convert("RGB")).astype(np.uint8)
        rgb = arr[...,:3]
        bg_mask = build_bg_mask(rgb, mode=mode, top_clean_pct=top_clean_pct)
        if dehalo_px > 0:
            m = Image.fromarray((bg_mask*255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2*int(dehalo_px)+1))
            bg_mask = np.array(m) > 127
        prod_mask = (~bg_mask).astype(np.uint8)
        if largest_scrub:
            # Simply find largest connected component - no diff>8 filtering
            # diff>8 was causing white labels/caps to break connectivity
            keep = largest_component_only(prod_mask.astype(bool))
            prod_mask = (keep.astype(np.uint8))
        # Remove corner overlays/badges
        if remove_overlays:
            prod_mask_bool = detect_and_remove_overlays(rgb, prod_mask.astype(bool))
            prod_mask = prod_mask_bool.astype(np.uint8)
        ys, xs = np.where(prod_mask > 0)
        if len(xs) > 0:
            y0, y1 = ys.min(), ys.max(); x0, x1 = xs.min(), xs.max()
            margin = int(float(margin_pct) * max(im.size))
            x0 = max(0, x0 - margin); y0 = max(0, y0 - margin)
            x1 = min(im.width-1, x1 + margin); y1 = min(im.height-1, y1 + margin)
            im = im.crop((x0, y0, x1+1, y1+1))
    im_white = clamp_white_background(Image.new("RGB", im.size, (255,255,255)), white_floor, neutrality_tol)
    enhanced = ImageEnhance.Contrast(im).enhance(product_contrast)
    enhanced = enhanced.filter(ImageFilter.UnsharpMask(radius=sharpen_radius, percent=sharpen_percent, threshold=sharpen_threshold))
    if work_on == "image" and not no_bg_clean:
        mask = Image.new("L", im.size, 255)
        if edge_feather > 0: mask = mask.filter(ImageFilter.GaussianBlur(edge_feather))
        im_white.paste(enhanced, (0,0), mask)
    else:
        im_white = enhanced
    placed = square_canvas(im_white, size=size, fit_mode=fit_mode,
                       target_fill=target_fill, min_top_pad_px=min_top_pad_px,
                       vertical_bias=vertical_bias, allow_upscale=allow_upscale, no_downscale=no_downscale) 
    placed = clamp_white_background(placed, white_floor, neutrality_tol)
    return placed
SUPPORTED_EXTS = (".jpg",".jpeg",".png",".webp",".bmp",".tif",".tiff",".gif",".heic",".heif",".jfif",".avif")
def process_file(in_path, out_path=None, op="convert", size=1500, allow_upscale=False, mode="auto",
                 dehalo_px=2, edge_feather=1.0, sharpen_radius=1.3, sharpen_percent=140, sharpen_threshold=2,
                 product_contrast=1.05, largest_scrub=True, top_clean_pct=0.08, margin_pct=0.015, quality=95,
                 progressive=True, optimize=True, set_dpi=None, add_shadow=False, shadow_alpha=70,
                 work_on="image", fit_mode="pad", target_fill=0.84, min_top_pad_px=120,
                 vertical_bias=0.58, white_floor=245, neutrality_tol=18, no_bg_clean=False,
                 no_downscale=False, qty_badge=None, qc_enabled=False, qc_mode="validate", qc_agent=None,
                 auto_work_on=False, auto_enhance=False, **_):

    qc_results = {"pre": None, "post": None, "adjustments": []}

    im = load_rgb(in_path)

    # Auto-detect work mode if enabled
    if auto_work_on:
        detected_mode = auto_detect_work_mode(im)
        if detected_mode != work_on:
            print(f"AUTO_DETECT: work_on changed from '{work_on}' to '{detected_mode}'")
            work_on = detected_mode

    # Auto-enhance: analyze quality and adjust parameters
    quality_report = None
    if auto_enhance:
        quality_report = analyze_image_quality(im)
        print(f"QUALITY_REPORT: blur={quality_report['blur_score']:.2f}, color={quality_report['color_score']:.2f}, overall={quality_report['overall_quality']:.0f}/100")

        if not quality_report["fixable"]:
            print("WARNING: Image quality is too poor to fix reliably. Consider using a better source image.")

        # Apply recommendations
        recs = quality_report.get("recommendations", {})
        if "sharpen_percent" in recs:
            old_val = sharpen_percent
            sharpen_percent = recs["sharpen_percent"]
            print(f"  -> sharpen_percent: {old_val} -> {sharpen_percent}")
        if "sharpen_radius" in recs:
            old_val = sharpen_radius
            sharpen_radius = recs["sharpen_radius"]
            print(f"  -> sharpen_radius: {old_val:.1f} -> {sharpen_radius:.1f}")
        if "product_contrast" in recs:
            old_val = product_contrast
            product_contrast = recs["product_contrast"]
            print(f"  -> product_contrast: {old_val:.2f} -> {product_contrast:.2f}")
        if "warning" in recs:
            print(f"  -> WARNING: {recs['warning']}")

    # QC Pre-analysis
    if qc_enabled and CHECKPIC_AVAILABLE:
        if qc_agent is None:
            qc_agent = CheckPicAgent()

        context = {
            "source_path": in_path,
            "intended_size": size,
            "fit_mode": fit_mode,
            "target_fill": target_fill,
            "margin_pct": margin_pct,
            "mode": mode,
            "dehalo_px": dehalo_px,
            "min_top_pad_px": min_top_pad_px
        }

        qc_pre = qc_agent.analyze_pre(im, work_on=work_on, **context)
        qc_results["pre"] = qc_pre

        # Adaptive mode: apply recommendations
        if qc_mode == "adaptive" and qc_pre.recommendations:
            for rec in qc_pre.recommendations:
                if rec.confidence >= 0.6:
                    if rec.param_name == "mode":
                        mode = rec.suggested_value
                    elif rec.param_name == "dehalo_px":
                        dehalo_px = rec.suggested_value
                    elif rec.param_name == "no_bg_clean":
                        no_bg_clean = rec.suggested_value
                    elif rec.param_name == "margin_pct":
                        margin_pct = rec.suggested_value
                    elif rec.param_name == "target_fill":
                        target_fill = rec.suggested_value
                    elif rec.param_name == "edge_sensitivity":
                        # Higher sensitivity → lower white_floor so near-white
                        # product edges aren't eaten by background cleaning
                        delta = rec.suggested_value - rec.current_value
                        white_floor = max(230, white_floor - int(delta * 20))
                    elif rec.param_name == "remove_overlays" and rec.suggested_value:
                        # White-out detected corner badges/overlays before processing
                        from PIL import ImageDraw as _ID
                        _draw = _ID.Draw(im)
                        for _issue in qc_pre.issues:
                            if _issue.code == "PROD_OVERLAY_DETECTED":
                                for _ov in _issue.details.get("overlays", []):
                                    x0, y0, x1, y1 = _ov["bbox"]
                                    _draw.rectangle([x0, y0, x1, y1],
                                                    fill=(255, 255, 255))
                        del _draw
                    qc_results["adjustments"].append({
                        "param": rec.param_name,
                        "from": rec.current_value,
                        "to": rec.suggested_value
                    })

    if op in ("clean","both"):
        im = clean_product_image(
            im,
            size=size, allow_upscale=allow_upscale, mode=mode,
            dehalo_px=dehalo_px, edge_feather=edge_feather,
            sharpen_radius=sharpen_radius, sharpen_percent=sharpen_percent,
            sharpen_threshold=sharpen_threshold, product_contrast=product_contrast,
            largest_scrub=largest_scrub, top_clean_pct=top_clean_pct, margin_pct=margin_pct,
            work_on=work_on, fit_mode=fit_mode, target_fill=target_fill,           # ADD THESE
            min_top_pad_px=min_top_pad_px, vertical_bias=vertical_bias,            # ADD THESE
            white_floor=white_floor, neutrality_tol=neutrality_tol,                # ADD THESE
            no_bg_clean=no_bg_clean, no_downscale=no_downscale                     # ADD THESE
        )
    
    # optional post: soft shadow on the final square canvas
    if add_shadow:
        im = add_bottom_shadow(im, alpha_pct=shadow_alpha)

    # optional post: quantity badge on left side of product
    if qty_badge:
        im = add_quantity_badge(im, qty_badge)

    if out_path is None:
        base, _ = os.path.splitext(in_path)
        out_path = base + ".jpg"

    save_jpg(im, out_path, quality=quality, progressive=progressive, optimize=optimize, dpi=set_dpi)

    # QC Post-validation
    if qc_enabled and CHECKPIC_AVAILABLE:
        qc_post = qc_agent.analyze_post(im, qc_results["pre"])
        qc_results["post"] = qc_post

        # Print QC results for GUI parsing
        print("QC_RESULT:" + json.dumps({
            "passed": qc_post.passed,
            "pre_issues": len(qc_results["pre"].issues) if qc_results["pre"] else 0,
            "post_issues": len(qc_post.issues),
            "score": qc_post.metrics.get("overall_score", 0),
            "adjustments": qc_results["adjustments"],
            "issues": [{"severity": i.severity.value, "code": i.code, "message": i.message}
                       for i in qc_post.issues]
        }) + ":END_QC_RESULT")

        # Strict mode: raise error if QC fails
        if qc_mode == "strict" and not qc_post.passed:
            raise Exception(f"QC validation failed: {qc_post.critical_count} critical, {qc_post.error_count} errors")

    return out_path

def process_folder(in_dir, out_dir=None, out_prefix="", out_suffix="", **kw):
    if out_dir is None:
        out_dir = os.path.join(in_dir, "_out")
    os.makedirs(out_dir, exist_ok=True)

    tasks = []
    for root, dirs, files in os.walk(in_dir):
        rel = os.path.relpath(root, in_dir)
        rel = "" if rel == "." else rel
        dst_root = os.path.join(out_dir, rel)
        os.makedirs(dst_root, exist_ok=True)
        for f in files:
            if f.lower().endswith(SUPPORTED_EXTS):
                src = os.path.join(root, f)
                stem = os.path.splitext(f)[0]
                dst = os.path.join(dst_root, f"{out_prefix}{stem}{out_suffix}.jpg")
                tasks.append((src, dst))

    count = 0
    workers = min(os.cpu_count() or 1, max(len(tasks), 1), 4)

    def _do(args):
        src, dst = args
        try:
            process_file(src, dst, **kw)
            return None
        except Exception as e:
            return f"[X] Failed: {src} | {e}"

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        for msg in ex.map(_do, tasks):
            if msg:
                print(msg)
            else:
                count += 1

    return out_dir, count
def process_zip(in_zip, out_zip="converted_cleaned.zip", **kw):
    with tempfile.TemporaryDirectory() as din, tempfile.TemporaryDirectory() as dout:
        with zipfile.ZipFile(in_zip, 'r') as z: z.extractall(din)
        out_dir, count = process_folder(din, dout, **kw)
        with zipfile.ZipFile(out_zip, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
            for root, _, files in os.walk(out_dir):
                for f in files:
                    fp = os.path.join(root, f); arc = os.path.relpath(fp, out_dir); zout.write(fp, arc)
    return out_zip, count
def main():
    p = argparse.ArgumentParser(description="ShelfReady Image Toolkit")
    p.add_argument("--in", dest="in_path"); p.add_argument("--out", dest="out_path", default=None)
    p.add_argument("--in_dir", dest="in_dir"); p.add_argument("--out_dir", dest="out_dir", default=None)
    p.add_argument("--in_zip", dest="in_zip"); p.add_argument("--out_zip", dest="out_zip", default="converted_cleaned.zip")
    p.add_argument("--out_prefix", default=""); p.add_argument("--out_suffix", default="")
    p.add_argument("--op", choices=["convert","clean","both"], default="convert")
    p.add_argument("--work_on", choices=["image","canvas"], default="image")
    p.add_argument("--fit_mode", choices=["pad","fit","crop_fill","fill_height","fill_width"], default="pad")
    p.add_argument("--size", type=int, default=1500)
    p.add_argument("--allow_upscale", action="store_true"); p.add_argument("--no_downscale", action="store_true")
    p.add_argument("--mode", choices=["safe","auto","aggressive"], default="auto")
    p.add_argument("--dehalo_px", type=float, default=2.0); p.add_argument("--edge_feather", type=float, default=1.0)
    p.add_argument("--sharpen_radius", type=float, default=1.3); p.add_argument("--sharpen_percent", type=int, default=140)
    p.add_argument("--sharpen_threshold", type=int, default=2); p.add_argument("--product_contrast", type=float, default=1.05)
    p.add_argument("--no_largest_scrub", action="store_true"); p.add_argument("--top_clean_pct", type=float, default=0.08)
    p.add_argument("--margin_pct", type=float, default=0.015); p.add_argument("--white_floor", type=int, default=245)
    p.add_argument("--neutrality_tol", type=int, default=18)
    p.add_argument("--target_fill", type=float, default=0.84); p.add_argument("--min_top_pad_px", type=int, default=120)
    p.add_argument("--vertical_bias", type=float, default=0.58)
    p.add_argument("--quality", type=int, default=95); p.add_argument("--no_progressive", action="store_true")
    p.add_argument("--no_optimize", action="store_true"); p.add_argument("--no_bg_clean", action="store_true")
    p.add_argument("--set_dpi", type=int, default=None, help="Embed DPI in output (e.g., 300).")
    p.add_argument("--add_shadow", action="store_true", help="Add a soft bottom shadow on white.")
    p.add_argument("--shadow_alpha", type=int, default=70, help="Shadow opacity 0–100.")
    p.add_argument("--qty_badge", type=str, default=None, help="Add quantity badge with text (e.g., '20 OZ').")

    # Check-Pic QC arguments
    p.add_argument("--qc", action="store_true", help="Enable Check-Pic QC analysis")
    p.add_argument("--qc_mode", choices=["validate", "adaptive", "strict"], default="validate",
                   help="QC mode: validate (report), adaptive (auto-adjust), strict (fail on errors)")
    p.add_argument("--qc_report", type=str, default=None, help="Output QC report to file (JSON)")

    # Auto-detection and enhancement
    p.add_argument("--auto_work_on", action="store_true",
                   help="Auto-detect work mode based on background (white bg = canvas, else image)")
    p.add_argument("--auto_enhance", action="store_true",
                   help="Auto-adjust sharpening/contrast based on image quality analysis")

    args = p.parse_args()
    progressive = not args.no_progressive; optimize = not args.no_optimize; largest_scrub = not args.no_largest_scrub
    kw = dict(
        op=args.op, size=args.size, allow_upscale=args.allow_upscale, mode=args.mode,
        dehalo_px=args.dehalo_px, edge_feather=args.edge_feather, sharpen_radius=args.sharpen_radius,
        sharpen_percent=args.sharpen_percent, sharpen_threshold=args.sharpen_threshold,
        product_contrast=args.product_contrast, largest_scrub=largest_scrub, top_clean_pct=args.top_clean_pct,
        margin_pct=args.margin_pct, quality=args.quality, progressive=progressive, optimize=optimize,
        set_dpi=args.set_dpi, add_shadow=args.add_shadow, shadow_alpha=args.shadow_alpha, work_on=args.work_on,
        fit_mode=args.fit_mode, target_fill=args.target_fill, min_top_pad_px=args.min_top_pad_px, vertical_bias=args.vertical_bias,
        white_floor=args.white_floor, neutrality_tol=args.neutrality_tol, no_bg_clean=args.no_bg_clean, no_downscale=args.no_downscale,
        qty_badge=args.qty_badge, qc_enabled=args.qc, qc_mode=args.qc_mode,
        auto_work_on=args.auto_work_on, auto_enhance=args.auto_enhance,
        out_prefix=args.out_prefix, out_suffix=args.out_suffix
    )

    performed = False
    if args.in_path:
        out = process_file(args.in_path, args.out_path, **kw); print("Saved ->", out); performed = True
    if args.in_dir:
        out_dir, n = process_folder(args.in_dir, args.out_dir, **kw); print(f"Folder -> {out_dir} | {n} files"); performed = True
    if args.in_zip:
        out_zip, n = process_zip(args.in_zip, args.out_zip, **kw); print(f"ZIP -> {out_zip} | {n} files"); performed = True
    if not performed: p.error("Provide one of: --in <file> | --in_dir <folder> | --in_zip <zip>")
if __name__ == "__main__":
    main()
