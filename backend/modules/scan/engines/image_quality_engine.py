# ==========================================================
# SCANIX AI
# SYSTEM 1 - IMAGE QUALITY ENGINE
# Analyzes image quality for label intelligence
# Features: Zero-disk processing, Threadpool offloading, Advanced CV2 metrics
# ==========================================================


import asyncio
import math
from typing import Any
from typing import Dict
from typing import Optional

import cv2
import numpy as np

from core.config import settings
from core.logging import get_logger
from modules.scan.schemas import ImageQualityResult


logger = get_logger(__name__)


# ==========================================================
# CONSTANTS (Moved to settings for production tuning)
# ==========================================================


# These can be overridden in config.py for different camera types
BLUR_CALIBRATION_FACTOR = getattr(settings, "BLUR_CALIBRATION_FACTOR", 500)
EDGE_DENSITY_CALIBRATION_FACTOR = getattr(settings, "EDGE_DENSITY_CALIBRATION_FACTOR", 200)
NOISE_VARIANCE_THRESHOLD = getattr(settings, "NOISE_VARIANCE_THRESHOLD", 25)
GLARE_THRESHOLD = getattr(settings, "GLARE_THRESHOLD", 240)
GLARE_SCALE_FACTOR = getattr(settings, "GLARE_SCALE_FACTOR", 1000)
MIN_EDGE_PIXELS = getattr(settings, "MIN_EDGE_PIXELS", 500)


# Weight configuration for quality scoring (tunable from settings)
QUALITY_WEIGHTS = {
    "blur": getattr(settings, "QUALITY_WEIGHT_BLUR", 0.10),
    "edge_density": getattr(settings, "QUALITY_WEIGHT_EDGE_DENSITY", 0.10),
    "brightness": getattr(settings, "QUALITY_WEIGHT_BRIGHTNESS", 0.05),
    "contrast": getattr(settings, "QUALITY_WEIGHT_CONTRAST", 0.05),
    "glare": getattr(settings, "QUALITY_WEIGHT_GLARE", 0.05),
    "lighting": getattr(settings, "QUALITY_WEIGHT_LIGHTING", 0.10),
    "resolution": getattr(settings, "QUALITY_WEIGHT_RESOLUTION", 0.10),
    "noise": getattr(settings, "QUALITY_WEIGHT_NOISE", 0.05),
    "perspective": getattr(settings, "QUALITY_WEIGHT_PERSPECTIVE", 0.10),
    "coverage": getattr(settings, "QUALITY_WEIGHT_COVERAGE", 0.20),
}


class ImageQualityEngine:
    
    def _resize_if_needed(self, image: np.ndarray) -> np.ndarray:
        
        height, width = image.shape[:2]
        
        max_dim = settings.SCAN_MAX_IMAGE_DIMENSION
        
        if height > max_dim or width > max_dim:
            
            scale = max_dim / max(height, width)
            
            new_width = int(width * scale)
            
            new_height = int(height * scale)
            
            resized = cv2.resize(image, (new_width, new_height))
            
            return resized
        
        return image
    
    
    def _compute_laplacian_variance(self, gray: np.ndarray) -> float:
        
        return cv2.Laplacian(gray, cv2.CV_64F).var()
    
    
    def _compute_edge_density(self, gray: np.ndarray) -> float:
        """
        Compute edge density as percentage of pixels that are edges.
        More reliable than Laplacian variance alone for sharpness assessment.
        """
        edges = cv2.Canny(gray, 50, 150)
        
        edge_pixels = np.count_nonzero(edges)
        
        total_pixels = edges.size
        
        if total_pixels == 0:
            return 0.0
        
        edge_density = edge_pixels / total_pixels
        
        return edge_density
    
    
    def calculate_blur_score(self, variance: float) -> int:
        
        normalized = min(100, int((variance / BLUR_CALIBRATION_FACTOR) * 100))
        
        return max(0, normalized)
    
    
    def calculate_edge_density_score(self, edge_density: float) -> int:
        """
        Calculate sharpness score based on edge density.
        Higher edge density = sharper image.
        Replaces the duplicate sharpness score.
        """
        normalized = min(100, int((edge_density * EDGE_DENSITY_CALIBRATION_FACTOR)))
        
        return max(0, normalized)
    
    
    def calculate_brightness_score(self, gray: np.ndarray) -> int:
        
        mean_val = cv2.mean(gray)[0]
        
        diff = abs(127 - mean_val)
        
        score = max(0, 100 - int(diff * 0.78))
        
        return score
    
    
    def calculate_contrast_score(self, gray: np.ndarray) -> int:
        
        std_val = gray.std()
        
        normalized = min(100, int(std_val * 2))
        
        return normalized
    
    
    def calculate_glare_score(self, gray: np.ndarray) -> int:
        
        mask = gray > GLARE_THRESHOLD
        
        glare_ratio = mask.sum() / mask.size if mask.size > 0 else 0
        
        score = max(0, 100 - int(glare_ratio * GLARE_SCALE_FACTOR))
        
        return score
    
    
    def calculate_lighting_score(self, brightness: int, glare: int) -> int:
        
        score = int((brightness * 0.6) + (glare * 0.4))
        
        return max(0, min(100, score))
    
    
    def calculate_resolution_score(self, image: np.ndarray) -> int:
        """
        Resolution score now heavily penalizes images that are too large.
        Optimal range: 800-1920 pixels on short side.
        """
        height, width = image.shape[:2]
        
        min_width = 800
        min_height = 600
        optimal_width = 1280
        optimal_height = 720
        max_penalty_width = 4000
        
        # Base score for meeting minimum requirements
        if width >= min_width and height >= min_height:
            base_score = 80
        else:
            area_ratio = (width * height) / (min_width * min_height)
            base_score = int(area_ratio * 80)
            base_score = max(30, min(80, base_score))
        
        # Penalize images that are excessively large (blurry upscaled images)
        if width > optimal_width or height > optimal_height:
            oversize_factor = min(1.0, (max(width, height) - optimal_width) / (max_penalty_width - optimal_width))
            penalty = int(oversize_factor * 30)
            score = max(30, base_score - penalty)
        else:
            score = base_score
        
        return min(100, max(0, score))
    
    
    def calculate_noise_score(self, gray: np.ndarray) -> int:
        
        denoised = cv2.medianBlur(gray, 5)
        
        noise = cv2.absdiff(gray.astype(np.float32), denoised.astype(np.float32))
        
        noise_variance = np.var(noise)
        
        if noise_variance <= NOISE_VARIANCE_THRESHOLD:
            
            score = 100
        
        elif noise_variance >= 100:
            
            score = 0
        
        else:
            
            score = int(100 - ((noise_variance - NOISE_VARIANCE_THRESHOLD) / 75) * 100)
        
        return max(0, min(100, score))
    
    
    def calculate_perspective_score(self, image: np.ndarray) -> int:
        """
        Calculate perspective distortion score.
        Returns higher score for minimal distortion (parallel lines).
        Note: This is heuristic and works best for rectangular labels.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        edges = cv2.Canny(gray, 50, 150)
        
        # Count edge pixels to detect if image has structure
        edge_pixel_count = np.count_nonzero(edges)
        
        if edge_pixel_count < MIN_EDGE_PIXELS:
            # Not enough edges to determine perspective, assume acceptable
            return 70
        
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, 100, minLineLength=100, maxLineGap=10)
        
        if lines is None or len(lines) < 2:
            
            return 65  # Slightly lower when lines can't be detected
        
        angles = []
        
        for line in lines[:20]:  # Limit to first 20 lines for performance
            
            x1, y1, x2, y2 = line[0]
            
            if x2 - x1 == 0:
                
                angle = 90.0
            
            else:
                
                angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
            
            # Normalize to 0-90 range
            normalized_angle = abs(angle % 90)
            angles.append(min(normalized_angle, 90 - normalized_angle))
        
        if not angles:
            
            return 65
        
        # Average deviation from perfect horizontal/vertical
        avg_deviation = sum(angles) / len(angles)
        
        # Score decreases as deviation increases
        score = max(0, 100 - int(avg_deviation * 1.5))
        
        return min(100, score)
    
    
    def _estimate_text_coverage(
        self,
        image: np.ndarray,
        text_blocks_count: int,
        text_blocks_area_ratio: Optional[float] = None,
    ) -> int:
        """
        Estimate text coverage without relying on OCR results.
        Uses edge density and morphological operations to estimate text regions.
        """
        if text_blocks_count > 0:
            # If we have OCR blocks, use them primarily
            if text_blocks_count >= 20:
                block_score = 100
            elif text_blocks_count >= 10:
                block_score = 85
            elif text_blocks_count >= 5:
                block_score = 65
            elif text_blocks_count >= 2:
                block_score = 45
            else:
                block_score = 25
            
            if text_blocks_area_ratio and text_blocks_area_ratio > 0:
                area_score = min(100, int(text_blocks_area_ratio * 100))
                return int((block_score * 0.6) + (area_score * 0.4))
            
            return block_score
        
        # Fallback: Estimate text regions using edge detection
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        
        # Use morphological operations to find text-like regions
        edges = cv2.Canny(gray, 30, 100)
        
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        dilated = cv2.dilate(edges, kernel, iterations=2)
        
        # Count potential text regions
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        text_like_contours = 0
        for contour in contours:
            area = cv2.contourArea(contour)
            if 50 < area < 10000:  # Text region typical size range
                text_like_contours += 1
        
        # Score based on number of text-like regions
        if text_like_contours >= 15:
            return 80
        elif text_like_contours >= 8:
            return 60
        elif text_like_contours >= 3:
            return 40
        elif text_like_contours >= 1:
            return 25
        else:
            return 15
    
    
    def _get_recommendation(self, metrics: dict) -> str:
        
        low_metrics = []
        
        if metrics.get("lighting", 100) < 50:
            
            low_metrics.append("Improve lighting")
        
        if metrics.get("edge_density", 100) < 40:
            
            low_metrics.append("Hold camera steady")
        
        if metrics.get("glare", 100) < 50:
            
            low_metrics.append("Avoid flash glare")
        
        if metrics.get("resolution", 100) < 40:
            
            low_metrics.append("Adjust camera distance")
        
        if metrics.get("perspective", 100) < 50:
            
            low_metrics.append("Hold camera parallel to label")
        
        if metrics.get("blur", 100) < 40:
            
            low_metrics.append("Focus camera on label")
        
        if low_metrics:
            
            return " | ".join(low_metrics[:2]) + " for better results"
        
        if metrics.get("overall", 0) >= 85:
            
            return "Excellent quality. Perfect for accurate OCR."
        
        if metrics.get("overall", 0) >= 65:
            
            return "Good quality. OCR should work well."
        
        if metrics.get("overall", 0) >= 45:
            
            return "Fair quality. Some text may be missed."
        
        return "Poor quality. Please retake with better lighting and focus."
    
    
    def _analyze_sync(
        self,
        image_bytes: bytes,
        text_blocks_count: int = 0,
        text_blocks_area_ratio: Optional[float] = None,
    ) -> ImageQualityResult:
        
        try:
            
            if not image_bytes:
                
                raise ValueError("No image bytes provided")
            
            nparr = np.frombuffer(image_bytes, np.uint8)
            
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if image is None:
                
                raise ValueError("Failed to decode image bytes")
            
            image = self._resize_if_needed(image)
            
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Core quality metrics
            laplacian_variance = self._compute_laplacian_variance(gray)
            edge_density = self._compute_edge_density(gray)
            
            blur = self.calculate_blur_score(laplacian_variance)
            edge_density_score = self.calculate_edge_density_score(edge_density)
            
            brightness = self.calculate_brightness_score(gray)
            contrast = self.calculate_contrast_score(gray)
            glare = self.calculate_glare_score(gray)
            lighting = self.calculate_lighting_score(brightness, glare)
            resolution = self.calculate_resolution_score(image)
            noise = self.calculate_noise_score(gray)
            perspective = self.calculate_perspective_score(image)
            
            # Coverage using fallback estimation if OCR blocks unavailable
            coverage = self._estimate_text_coverage(image, text_blocks_count, text_blocks_area_ratio)
            
            # Calculate overall score with configurable weights
            overall = int(
                blur * QUALITY_WEIGHTS["blur"] +
                edge_density_score * QUALITY_WEIGHTS["edge_density"] +
                brightness * QUALITY_WEIGHTS["brightness"] +
                contrast * QUALITY_WEIGHTS["contrast"] +
                glare * QUALITY_WEIGHTS["glare"] +
                lighting * QUALITY_WEIGHTS["lighting"] +
                resolution * QUALITY_WEIGHTS["resolution"] +
                noise * QUALITY_WEIGHTS["noise"] +
                perspective * QUALITY_WEIGHTS["perspective"] +
                coverage * QUALITY_WEIGHTS["coverage"]
            )
            
            overall = max(0, min(100, overall))
            
            metrics = {
                "overall": overall,
                "lighting": lighting,
                "edge_density": edge_density_score,
                "glare": glare,
                "resolution": resolution,
                "perspective": perspective,
                "blur": blur,
            }
            
            recommendation = self._get_recommendation(metrics)
            
            return ImageQualityResult(
                overall_score=overall,
                blur_score=blur,
                brightness_score=brightness,
                contrast_score=contrast,
                glare_score=glare,
                lighting_score=lighting,
                sharpness_score=edge_density_score,
                recommendation=recommendation,
            )
        
        except Exception as e:
            
            logger.error(f"Image quality sync analysis failed: {e}")
            
            return ImageQualityResult(
                overall_score=50,
                blur_score=50,
                brightness_score=50,
                contrast_score=50,
                glare_score=50,
                lighting_score=50,
                sharpness_score=50,
                recommendation="Quality analysis failed. Please ensure image is clear.",
            )
    
    
    async def analyze(
        self,
        image_bytes: bytes,
        text_blocks_count: int = 0,
        text_blocks_area_ratio: Optional[float] = None,
    ) -> ImageQualityResult:
        
        # Offload heavy CPU bound CV2 tasks to background thread
        return await asyncio.to_thread(
            self._analyze_sync,
            image_bytes,
            text_blocks_count,
            text_blocks_area_ratio,
        )
    
    
    def _get_image_metadata_sync(self, image_bytes: bytes) -> Dict[str, Any]:
        
        try:
            
            if not image_bytes:
                
                raise ValueError("No image bytes provided")
            
            file_size_bytes = len(image_bytes)
            
            nparr = np.frombuffer(image_bytes, np.uint8)
            
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if image is None:
                
                raise ValueError("Failed to decode image")
            
            height, width = image.shape[:2]
            
            channels = image.shape[2] if len(image.shape) > 2 else 1
            
            return {
                "width": width,
                "height": height,
                "channels": channels,
                "file_size_bytes": file_size_bytes,
                "aspect_ratio": round(width / height, 2) if height > 0 else 0.0,
            }
        
        except Exception as e:
            
            logger.error(f"Failed to get image metadata: {e}")
            
            return {
                "width": 0,
                "height": 0,
                "channels": 0,
                "file_size_bytes": 0,
                "aspect_ratio": 0.0,
            }
    
    
    async def get_image_metadata(self, image_bytes: bytes) -> Dict[str, Any]:
        
        return await asyncio.to_thread(self._get_image_metadata_sync, image_bytes)
    
    
    def _calculate_perspective_sync(self, image_bytes: bytes) -> int:
        
        try:
            
            nparr = np.frombuffer(image_bytes, np.uint8)
            
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if image is None:
                return 50
                
            image = self._resize_if_needed(image)
            
            return self.calculate_perspective_score(image)
            
        except Exception:
            
            return 50
    
    
    async def get_label_intelligence_metrics(
        self,
        image_bytes: bytes,
        quality: ImageQualityResult,
        ocr_readability: int,
        ocr_coverage: int,
    ) -> Dict[str, int]:
        
        # Calculate perspective efficiently in a background thread without re-running full analysis
        perspective = await asyncio.to_thread(self._calculate_perspective_sync, image_bytes)
        
        return {
            "lighting": quality.lighting_score,
            "sharpness": quality.sharpness_score,
            "readability": ocr_readability,
            "coverage": ocr_coverage,
            "contrast": quality.contrast_score,
            "perspective": perspective,
        }


# ==========================================================
# SINGLETON
# ==========================================================


image_quality_engine = ImageQualityEngine()


# ==========================================================
# END OF FILE
# ==========================================================