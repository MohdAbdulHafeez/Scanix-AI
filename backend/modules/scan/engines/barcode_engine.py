# ==========================================================
# SCANIX AI
# SYSTEM 1 - BARCODE ENGINE
# Barcode detection from image and text
# Supports: EAN-8, EAN-13, UPC, GTIN-14
# Features: Zero-disk processing, Rotation detection, Cropped region search
# Threadpool offloading, Strict schema mapping
# ==========================================================


import asyncio
import re
from datetime import datetime
from datetime import timezone
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Set
from typing import Tuple

import cv2
import numpy as np
from pyzbar.pyzbar import decode

from core.config import settings
from core.logging import get_logger
from modules.scan.constants import BARCODE_REGION_PREFIXES
from modules.scan.schemas import BarcodeResult
from modules.scan.schemas import DetectionSource


logger = get_logger(__name__)


# ==========================================================
# CONSTANTS & MAPS
# ==========================================================


FLAG_MAP = {
    "India": "🇮🇳",
    "United States": "🇺🇸",
    "USA/Canada": "🇺🇸/🇨🇦",
    "China": "🇨🇳",
    "France": "🇫🇷",
    "Germany": "🇩🇪",
    "United Kingdom": "🇬🇧",
    "Switzerland": "🇨🇭",
    "Italy": "🇮🇹",
    "Spain": "🇪🇸",
    "Turkey": "🇹🇷",
    "Netherlands": "🇳🇱",
    "South Korea": "🇰🇷",
    "Japan": "🇯🇵",
    "Australia": "🇦🇺",
    "New Zealand": "🇳🇿",
    "Malaysia": "🇲🇾",
    "Macau": "🇲🇴",
    "Russia": "🇷🇺",
    "Bulgaria": "🇧🇬",
}

BARCODE_TYPES = {
    8: "EAN-8",
    12: "UPC",
    13: "EAN-13",
    14: "GTIN-14",
}

# Valid retail barcode types (filter out QR, CODE128, etc.)
VALID_RETAIL_BARCODE_TYPES: Set[str] = {
    "EAN13", "EAN-13",
    "EAN8", "EAN-8",
    "UPC", "UPC-A",
    "GTIN", "GTIN-12", "GTIN-13", "GTIN-14",
}

# Rotation angles to try for barcode detection (0, 90, 180, 270 degrees)
ROTATION_ANGLES = [0, 90, 180, 270]

# Search regions as (y_start_percent, y_end_percent, x_start_percent, x_end_percent, priority, name)
# Priority: 1 = highest, 6 = lowest
SEARCH_REGIONS = [
    (0.6, 1.0, 0.2, 0.8, 1, "bottom_center"),      # Bottom center (most common)
    (0.5, 1.0, 0.0, 1.0, 2, "bottom_half"),         # Bottom half
    (0.0, 1.0, 0.0, 1.0, 3, "full_image"),          # Full image
    (0.7, 0.95, 0.1, 0.9, 4, "bottom_strip"),       # Bottom strip (just above edge)
    (0.0, 0.5, 0.0, 1.0, 5, "top_half"),            # Top half
    (0.0, 1.0, 0.3, 0.7, 6, "center_strip"),        # Center vertical strip
]

# Preprocessing modes with priority (higher priority = try first)
PREPROCESSING_MODES = [
    ("original", 1, 95.0),      # No preprocessing (highest confidence)
    ("threshold", 2, 85.0),     # Binary threshold
    ("adaptive", 3, 75.0),      # Adaptive threshold
]

# Maximum decode attempts per scan (early termination)
MAX_DECODE_ATTEMPTS = 30

# Early termination confidence threshold (stop if found barcode above this)
EARLY_TERMINATION_CONFIDENCE = 80


class BarcodeEngine:
    
    def __init__(self):
        
        self.detection_attempts = 0
        
        self.last_scan_timestamp: Optional[datetime] = None
    
    
    def _rotate_image(self, image: np.ndarray, angle: int) -> np.ndarray:
        """Rotate image by 0, 90, 180, or 270 degrees"""
        if angle == 0:
            return image
        
        if angle == 90:
            return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
        
        if angle == 180:
            return cv2.rotate(image, cv2.ROTATE_180)
        
        if angle == 270:
            return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
        
        return image
    
    
    def _crop_region(
        self,
        image: np.ndarray,
        y_start_pct: float,
        y_end_pct: float,
        x_start_pct: float,
        x_end_pct: float,
    ) -> Optional[np.ndarray]:
        """Extract a cropped region from the image using percentage coordinates"""
        height, width = image.shape[:2]
        
        y_start = int(height * y_start_pct)
        y_end = int(height * y_end_pct)
        x_start = int(width * x_start_pct)
        x_end = int(width * x_end_pct)
        
        # Validate bounds
        y_start = max(0, min(y_start, height - 1))
        y_end = max(y_start + 1, min(y_end, height))
        x_start = max(0, min(x_start, width - 1))
        x_end = max(x_start + 1, min(x_end, width))
        
        if y_end <= y_start or x_end <= x_start:
            return None
        
        return image[y_start:y_end, x_start:x_end]
    
    
    def _is_valid_retail_barcode_type(self, barcode_type: str) -> bool:
        """Check if the detected barcode type is a valid retail barcode (not QR, CODE128, etc.)"""
        barcode_type_upper = barcode_type.upper()
        
        for valid_type in VALID_RETAIL_BARCODE_TYPES:
            if valid_type.upper() in barcode_type_upper or barcode_type_upper in valid_type.upper():
                return True
        
        return False
    
    
    def _decode_single_image(
        self,
        image: np.ndarray,
        preprocess: bool = True,
    ) -> List[Tuple[str, str, float]]:
        """Decode barcodes from a single image (no rotation or cropping)"""
        results = []
        
        try:
            if preprocess:
                # Convert to grayscale
                if len(image.shape) == 3:
                    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                else:
                    gray = image
                
                # Contrast enhancement
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                processed = clahe.apply(gray)
            else:
                processed = image
            
            # Sort preprocessing modes by priority
            sorted_modes = sorted(PREPROCESSING_MODES, key=lambda x: x[1])
            
            for method_name, _, confidence_base in sorted_modes:
                if method_name == "original":
                    img = processed
                elif method_name == "threshold":
                    img = cv2.threshold(processed, 127, 255, cv2.THRESH_BINARY)[1]
                elif method_name == "adaptive":
                    img = cv2.adaptiveThreshold(
                        processed, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                        cv2.THRESH_BINARY, 11, 2
                    )
                else:
                    continue
                
                decoded = decode(img)
                
                for barcode in decoded:
                    barcode_data = barcode.data.decode()
                    barcode_type = barcode.type
                    
                    # Filter out non-retail barcode types (QR, CODE128, etc.)
                    if not self._is_valid_retail_barcode_type(barcode_type):
                        logger.debug(f"Skipping non-retail barcode type: {barcode_type}")
                        continue
                    
                    results.append((barcode_data, barcode_type, confidence_base))
        
        except Exception as e:
            logger.debug(f"Single image decode failed: {e}")
        
        return results
    
    
    def _decode_with_rotation_and_cropping(
        self,
        image: np.ndarray,
    ) -> List[Tuple[str, str, float, int, str]]:
        """
        Decode barcodes with rotation and region search.
        Returns: (barcode, barcode_type, confidence, rotation_angle, region_name)
        Uses priority-based search with early termination.
        """
        all_results = []
        attempt_count = 0
        
        # Sort regions by priority (lower priority number = higher priority)
        sorted_regions = sorted(SEARCH_REGIONS, key=lambda x: x[4])
        
        for angle in ROTATION_ANGLES:
            rotated = self._rotate_image(image, angle)
            
            for y_start, y_end, x_start, x_end, priority, region_name in sorted_regions:
                cropped = self._crop_region(rotated, y_start, y_end, x_start, x_end)
                
                if cropped is None or cropped.size == 0:
                    continue
                
                # Resize if too large (improves performance)
                height, width = cropped.shape[:2]
                max_dimension = 1024
                
                if height > max_dimension or width > max_dimension:
                    scale = max_dimension / max(height, width)
                    new_width = int(width * scale)
                    new_height = int(height * scale)
                    cropped = cv2.resize(cropped, (new_width, new_height))
                
                results = self._decode_single_image(cropped, preprocess=True)
                
                for barcode, barcode_type, confidence in results:
                    all_results.append((barcode, barcode_type, confidence, angle, region_name))
                    attempt_count += 1
                    
                    # Early termination if we found a high-confidence barcode in high-priority region
                    if (confidence >= EARLY_TERMINATION_CONFIDENCE and 
                        priority <= 2 and  # Only for top priority regions
                        angle == 0):       # Only for non-rotated images
                        logger.debug(f"Early termination: found high-confidence barcode in {region_name}")
                        return all_results
                    
                    # Hard limit on decode attempts
                    if attempt_count >= MAX_DECODE_ATTEMPTS:
                        logger.debug(f"Reached max decode attempts ({MAX_DECODE_ATTEMPTS})")
                        return all_results
        
        return all_results
    
    
    def _decode_from_image_sync(self, image_bytes: bytes) -> List[Tuple[str, str, float]]:
        
        results = []
        
        try:
            # Zero-disk processing
            nparr = np.frombuffer(image_bytes, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if image is None:
                return results
            
            # Try rotation and cropping-based detection with early termination
            enhanced_results = self._decode_with_rotation_and_cropping(image)
            
            for barcode, barcode_type, confidence, angle, region_name in enhanced_results:
                # Adjust confidence based on detection quality
                final_confidence = confidence
                
                # Bonus for 0-degree detection (no rotation needed)
                if angle == 0:
                    final_confidence += 5
                
                # Bonus for bottom region detection (most common location)
                if "bottom" in region_name:
                    final_confidence += 5
                
                # Penalty for extreme rotations
                if angle in [90, 270]:
                    final_confidence -= 10
                
                final_confidence = max(0, min(100, final_confidence))
                
                results.append((barcode, barcode_type, final_confidence))
            
            # Fallback: Try simple decode if rotation/cropping found nothing
            if not results:
                results = self._decode_single_image(image, preprocess=True)
            
            # Remove duplicates (keep highest confidence)
            unique_results = {}
            
            for barcode, b_type, confidence in results:
                if barcode not in unique_results or confidence > unique_results[barcode][2]:
                    unique_results[barcode] = (barcode, b_type, confidence)
            
            # Filter out any non-retail barcodes that might have slipped through
            filtered_results = [
                (b, t, c) for b, t, c in unique_results.values()
                if self._is_valid_retail_barcode_type(t)
            ]
            
            return filtered_results
        
        except Exception as e:
            
            logger.debug(f"Barcode decode failed: {e}")
            
            return results
    
    
    def _score_barcode(self, barcode: str, barcode_type: str, confidence: float) -> int:
        
        score = 0
        
        # Valid checksum (40 points)
        if self.validate_barcode(barcode):
            
            score += 40
        
        # Barcode length valid (20 points)
        if len(barcode) in [8, 12, 13, 14]:
            
            score += 20
        
        # Detection confidence (20 points)
        score += min(20, int(confidence / 5))
        
        # Preference for EAN-13 and UPC (20 points)
        if barcode_type in ["EAN13", "UPC", "EAN-13", "UPC-A"]:
            
            score += 20
        
        elif barcode_type in ["EAN8", "EAN-8"]:
            
            score += 10
        
        return min(100, score)
    
    
    def _select_best_barcode(self, barcodes: List[Tuple[str, str, float]]) -> Optional[Tuple[str, str, int]]:
        
        if not barcodes:
            
            return None
        
        scored_barcodes = []
        
        for barcode, barcode_type, confidence in barcodes:
            
            score = self._score_barcode(barcode, barcode_type, confidence)
            
            scored_barcodes.append((barcode, barcode_type, score, confidence))
        
        # Sort by score descending
        scored_barcodes.sort(key=lambda x: x[2], reverse=True)
        
        best = scored_barcodes[0]
        
        return (best[0], best[1], best[2])
    
    
    def extract_from_text(self, text: str) -> Optional[str]:
        
        if not text:
            
            return None
        
        candidates = re.findall(r"\b\d{8,14}\b", text)
        
        ignore_prefixes = ["lic", "license", "fssai", "tel", "phone", "mobile", "contact"]
        
        normalized = text.lower()
        
        lines = normalized.split("\n")
        
        scored_candidates = []
        
        for candidate in candidates:
            
            if not self.validate_barcode(candidate):
                
                continue
            
            score = 0
            
            for line in lines:
                
                if candidate in line:
                    
                    line_lower = line.lower()
                    
                    if any(prefix in line_lower for prefix in ignore_prefixes):
                        
                        score -= 50
                    
                    if any(keyword in line_lower for keyword in ["barcode", "ean", "upc", "scan", "gtin"]):
                        
                        score += 50
                    
                    break
            
            scored_candidates.append((candidate, score))
        
        if not scored_candidates:
            
            return None
        
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        
        return scored_candidates[0][0]
    
    
    def validate_ean8(self, barcode: str) -> bool:
        
        return len(barcode) == 8 and self._mod10_checksum(barcode)
    
    
    def validate_ean13(self, barcode: str) -> bool:
        
        return len(barcode) == 13 and self._mod10_checksum(barcode)
    
    
    def validate_upc(self, barcode: str) -> bool:
        
        return len(barcode) == 12 and self._mod10_checksum(barcode)
    
    
    def validate_gtin14(self, barcode: str) -> bool:
        
        return len(barcode) == 14 and self._mod10_checksum(barcode)
    
    
    def _mod10_checksum(self, barcode: str) -> bool:
        
        digits = [int(x) for x in barcode]
        
        checksum = digits.pop()
        
        digits.reverse()
        
        total = sum(d * 3 if i % 2 == 0 else d for i, d in enumerate(digits))
        
        expected = (10 - (total % 10)) % 10
        
        return expected == checksum
    
    
    def validate_barcode(self, barcode: Optional[str]) -> bool:
        
        if not barcode or not barcode.isdigit():
            
            return False
        
        length = len(barcode)
        
        if length == 8:
            
            return self.validate_ean8(barcode)
        
        if length == 12:
            
            return self.validate_upc(barcode)
        
        if length == 13:
            
            return self.validate_ean13(barcode)
        
        if length == 14:
            
            return self.validate_gtin14(barcode)
        
        return False
    
    
    def detect_market(self, barcode: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        
        if not barcode or len(barcode) < 3:
            
            return None, None
        
        prefix = barcode[:3]
        
        market = BARCODE_REGION_PREFIXES.get(prefix)
        
        # Extended market detection for common prefixes without exact matches
        if not market:
            if prefix.startswith('69'):
                market = "China"
            elif prefix.startswith('89'):
                market = "Japan"
            elif prefix.startswith('88'):
                market = "South Korea"
            elif prefix.startswith('93'):
                market = "Australia"
        
        flag = FLAG_MAP.get(market) if market else None
        
        return market, flag
    
    
    def get_barcode_type(self, barcode: Optional[str]) -> Optional[str]:
        
        if not barcode:
            
            return None
        
        return BARCODE_TYPES.get(len(barcode))
    
    
    def calculate_confidence(self, barcode: Optional[str], detection_confidence: int = 50) -> int:
        
        if not barcode:
            
            return 0
        
        score = 0
        
        # Image decode success (0-40 points)
        score += min(40, detection_confidence)
        
        # Checksum valid (0-30 points)
        if self.validate_barcode(barcode):
            
            score += 30
        
        # Barcode length valid (0-15 points)
        if len(barcode) in [8, 12, 13, 14]:
            
            score += 15
        
        # Additional points for EAN-13 (most common) (0-15 points)
        if len(barcode) == 13:
            
            score += 15
        
        elif len(barcode) == 12:
            
            score += 10
        
        return min(100, score)
    
    
    async def scan(self, image_bytes: Optional[bytes] = None, text: Optional[str] = None) -> BarcodeResult:
        
        self.detection_attempts += 1
        
        self.last_scan_timestamp = datetime.now(timezone.utc)
        
        barcode = None
        
        barcode_type = None
        
        detection_confidence = 0
        
        detected_from = DetectionSource.NONE
        
        if image_bytes and settings.ENABLE_BARCODE_SCAN:
            
            # Offload heavy OpenCV & pyzbar operations to background thread
            results = await asyncio.to_thread(self._decode_from_image_sync, image_bytes)
            
            if results:
                
                best = self._select_best_barcode(results)
                
                if best:
                    
                    barcode, barcode_type, detection_confidence = best
                    
                    detected_from = DetectionSource.IMAGE
        
        if not barcode and text and settings.ENABLE_BARCODE_SCAN:
            
            extracted = self.extract_from_text(text)
            
            if extracted:
                
                barcode = extracted
                
                barcode_type = self.get_barcode_type(barcode)
                
                detection_confidence = 70
                
                detected_from = DetectionSource.TEXT
        
        is_valid = self.validate_barcode(barcode) if barcode else False
        
        confidence = self.calculate_confidence(barcode, detection_confidence) if barcode else 0
        
        market, market_flag = self.detect_market(barcode)
        
        # Fallback to general market detection if specific country logic isn't split
        prefix_country = market
        
        if is_valid and not barcode_type:
            
            barcode_type = self.get_barcode_type(barcode)
        
        return BarcodeResult(
            barcode=barcode,
            barcode_type=barcode_type,
            is_valid=is_valid,
            confidence=confidence,
            market=market,
            market_flag=market_flag,
            detected_from=detected_from,
            prefix_country=prefix_country,
        )
    
    
    async def scan_manual(self, barcode_input: str) -> BarcodeResult:
        
        self.detection_attempts += 1
        
        self.last_scan_timestamp = datetime.now(timezone.utc)
        
        barcode = barcode_input.strip()
        
        is_valid = self.validate_barcode(barcode)
        
        barcode_type = self.get_barcode_type(barcode) if is_valid else None
        
        confidence = 95 if is_valid else 25
        
        market, market_flag = self.detect_market(barcode) if is_valid else (None, None)
        
        prefix_country = market if is_valid else None
        
        return BarcodeResult(
            barcode=barcode,
            barcode_type=barcode_type,
            is_valid=is_valid,
            confidence=confidence,
            market=market,
            market_flag=market_flag,
            detected_from=DetectionSource.MANUAL,
            prefix_country=prefix_country,
        )


# ==========================================================
# SINGLETON
# ==========================================================


barcode_engine = BarcodeEngine()


# ==========================================================
# END OF FILE
# ==========================================================