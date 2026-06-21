# ==========================================================
# SCANIX AI
# SYSTEM 1 - OCR ENGINE
# EasyOCR with Tesseract fallback
# Features: Orientation detection, multi-image merging, section extraction
# Zero-disk memory processing, non-blocking CV2, schema alignment
# ==========================================================


import asyncio
import gc
import re
import subprocess
import time
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

import cv2
import easyocr
import numpy as np
from fastapi import UploadFile

from core.config import settings
from core.exceptions import OCRError
from core.exceptions import OCRNoTextError
from core.exceptions import OCRTimeoutError
from core.logging import get_logger
from modules.scan.constants import MIN_OCR_CONFIDENCE
from modules.scan.constants import OCR_CORRECTIONS
from modules.scan.constants import SECTION_KEYWORDS
from modules.scan.schemas import OCRBlock


logger = get_logger(__name__)


# ==========================================================
# CONSTANTS
# ==========================================================


OCR_TIMEOUT_SECONDS = getattr(settings, "OCR_TIMEOUT_SECONDS", 30)
OCR_ORIENTATION_ANGLES = [0, 90, 180, 270]
OCR_MIN_SECTION_CONFIDENCE = 0.5
OCR_MIN_NUTRITION_TABLE_DENSITY = 0.3


# ==========================================================
# ENHANCED NUTRITION PATTERNS
# ==========================================================


NUTRITION_PATTERNS = {
    "energy": [
        r'(?:energy|calories|kcal|kj)[:\s]*(\d+(?:\.\d+)?)\s*(?:kcal|kj|cal)',
        r'energy\s+(\d+(?:\.\d+)?)\s*(?:kcal|kj)',
        r'calories?\s+(\d+(?:\.\d+)?)',
        r'(\d+(?:\.\d+)?)\s*(?:kcal|calories)',
    ],
    "protein": [
        r'protein[:\s]*(\d+(?:\.\d+)?)\s*g',
        r'proteins?[:\s]*(\d+(?:\.\d+)?)\s*g',
        r'protein\s+\(g\)[:\s]*(\d+(?:\.\d+)?)',
        r'protein\s+per\s+100g[:\s]*(\d+(?:\.\d+)?)',
    ],
    "carbohydrates": [
        r'(?:carbohydrates|carbohydrate|carb)[:\s]*(\d+(?:\.\d+)?)\s*g',
        r'total\s+carbohydrates?[:\s]*(\d+(?:\.\d+)?)\s*g',
        r'carbohydrate\s+\(g\)[:\s]*(\d+(?:\.\d+)?)',
    ],
    "sugar": [
        r'sugar[:\s]*(\d+(?:\.\d+)?)\s*g',
        r'sugars[:\s]*(\d+(?:\.\d+)?)\s*g',
        r'total\s+sugars?[:\s]*(\d+(?:\.\d+)?)\s*g',
        r'added\s+sugars?[:\s]*(\d+(?:\.\d+)?)\s*g',
    ],
    "fat": [
        r'(?:fat|total fat)[:\s]*(\d+(?:\.\d+)?)\s*g',
        r'fats?[:\s]*(\d+(?:\.\d+)?)\s*g',
        r'total\s+fats?[:\s]*(\d+(?:\.\d+)?)\s*g',
    ],
    "saturated_fat": [
        r'(?:saturated fat|saturates)[:\s]*(\d+(?:\.\d+)?)\s*g',
        r'saturated\s+fats?[:\s]*(\d+(?:\.\d+)?)\s*g',
        r'(?:saturated|satd?)\s+fat[:\s]*(\d+(?:\.\d+)?)\s*g',
    ],
    "fiber": [
        r'(?:fiber|fibre|dietary fiber)[:\s]*(\d+(?:\.\d+)?)\s*g',
        r'(?:fibre|dietary\s+fibre)[:\s]*(\d+(?:\.\d+)?)\s*g',
    ],
    "sodium": [
        r'(?:sodium|salt)[:\s]*(\d+(?:\.\d+)?)\s*(?:mg|g)',
        r'sodium\s+\(mg\)[:\s]*(\d+(?:\.\d+)?)',
        r'salt\s+equivalent[:\s]*(\d+(?:\.\d+)?)\s*g',
    ],
    "cholesterol": [
        r'cholesterol[:\s]*(\d+(?:\.\d+)?)\s*mg',
        r'cholest[:\s]*(\d+(?:\.\d+)?)\s*mg',
    ],
    "trans_fat": [
        r'trans\s+fat[:\s]*(\d+(?:\.\d+)?)\s*g',
        r'trans\s+fats?[:\s]*(\d+(?:\.\d+)?)\s*g',
    ],
    "vitamin_d": [
        r'vitamin\s+d[:\s]*(\d+(?:\.\d+)?)\s*(?:mcg|µg)',
    ],
    "calcium": [
        r'calcium[:\s]*(\d+(?:\.\d+)?)\s*mg',
    ],
    "iron": [
        r'iron[:\s]*(\d+(?:\.\d+)?)\s*mg',
    ],
    "potassium": [
        r'potassium[:\s]*(\d+(?:\.\d+)?)\s*mg',
    ],
}


class OrientationDetector:
    
    def __init__(self):
        self._ocr_instance = None
        self._min_confidence = MIN_OCR_CONFIDENCE
    
    def _set_ocr_instance(self, ocr_instance):
        """Set reference to main OCR engine for reusing reader"""
        self._ocr_instance = ocr_instance
    
    def detect_orientation_by_ocr(
        self,
        image: np.ndarray,
        reader,
    ) -> int:
        """
        Detect orientation by running OCR on multiple angles and choosing best.
        This is more reliable than MSER for food packaging.
        """
        best_angle = 0
        best_score = 0
        best_text_length = 0
        best_confidence = 0
        
        for angle in OCR_ORIENTATION_ANGLES:
            rotated = self._rotate_image(image, angle)
            
            try:
                # Run OCR on rotated image
                results = reader.readtext(rotated)
                
                if not results:
                    continue
                
                # Calculate score based on multiple factors
                total_confidence = 0
                detected_words = 0
                nutrition_keywords_found = 0
                ingredient_keywords_found = 0
                extracted_texts = []
                
                for result in results:
                    bbox, text, confidence = result
                    
                    if confidence >= self._min_confidence:
                        total_confidence += confidence
                        detected_words += 1
                        extracted_texts.append(text.lower())
                
                if detected_words == 0:
                    continue
                
                avg_confidence = total_confidence / detected_words
                
                # Check for nutrition and ingredient keywords
                combined_text = " ".join(extracted_texts)
                
                nutrition_keywords = ["protein", "fat", "carbohydrate", "sugar", "sodium", "calories", "energy"]
                ingredient_keywords = ["ingredients", "contains", "allergen", "may contain"]
                
                for kw in nutrition_keywords:
                    if kw in combined_text:
                        nutrition_keywords_found += 1
                
                for kw in ingredient_keywords:
                    if kw in combined_text:
                        ingredient_keywords_found += 1
                
                # Total score: confidence + word count bonus + keyword bonuses
                word_bonus = min(detected_words * 2, 20)
                nutrition_bonus = nutrition_keywords_found * 5
                ingredient_bonus = ingredient_keywords_found * 3
                
                total_score = (avg_confidence * 100) + word_bonus + nutrition_bonus + ingredient_bonus
                total_text_length = sum(len(t) for t in extracted_texts)
                
                if total_score > best_score:
                    best_score = total_score
                    best_angle = angle
                    best_text_length = total_text_length
                    best_confidence = avg_confidence
            
            except Exception as e:
                logger.debug(f"OCR orientation test failed for angle {angle}: {e}")
                continue
        
        if best_angle != 0:
            logger.info(f"Orientation detected: {best_angle}° (score={best_score:.1f}, words={best_text_length}, conf={best_confidence:.2f})")
        
        return best_angle
    
    def _rotate_image(self, image: np.ndarray, angle: int) -> np.ndarray:
        """Rotate image by specified angle (0, 90, 180, 270 degrees)"""
        if angle == 0:
            return image
        
        if angle == 90:
            return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
        
        if angle == 180:
            return cv2.rotate(image, cv2.ROTATE_180)
        
        if angle == 270:
            return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
        
        return image


# ==========================================================
# SECTION EXTRACTOR
# ==========================================================


class SectionExtractor:
    
    def __init__(self):
        self.section_keywords = SECTION_KEYWORDS
    
    def detect_sections(self, text: str, blocks: List[Dict]) -> Dict[str, Any]:
        """
        Detect and extract specific sections from OCR text.
        Returns dictionary with ingredients, nutrition, allergens, etc.
        """
        sections = {
            "ingredients": None,
            "nutrition_facts": None,
            "allergens": None,
            "product_name": None,
            "brand": None,
            "claims": [],
            "storage": None,
            "manufacturer": None,
        }
        
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            
            # Detect ingredients section
            if any(kw in line_lower for kw in self.section_keywords.get("ingredients", [])):
                # Extract subsequent lines until next section
                ingredients_text = []
                for j in range(i + 1, min(i + 20, len(lines))):
                    if self._is_section_boundary(lines[j]):
                        break
                    ingredients_text.append(lines[j])
                
                if ingredients_text:
                    sections["ingredients"] = " ".join(ingredients_text)
            
            # Detect nutrition facts
            if any(kw in line_lower for kw in self.section_keywords.get("nutrition", [])):
                nutrition_text = []
                for j in range(i + 1, min(i + 30, len(lines))):
                    if self._is_section_boundary(lines[j]):
                        break
                    nutrition_text.append(lines[j])
                
                if nutrition_text:
                    sections["nutrition_facts"] = " ".join(nutrition_text)
            
            # Detect allergens
            if any(kw in line_lower for kw in self.section_keywords.get("allergens", [])):
                allergen_text = []
                for j in range(i + 1, min(i + 10, len(lines))):
                    allergen_text.append(lines[j])
                
                if allergen_text:
                    sections["allergens"] = " ".join(allergen_text)
            
            # Detect product name (usually near top, not in a section)
            if i < 5 and not sections["product_name"]:
                if len(line) > 10 and len(line) < 100:
                    sections["product_name"] = line.strip()
            
            # Detect brand
            if "brand" in line_lower or "manufactured by" in line_lower:
                brand_match = re.search(r'(?:brand|manufactured by)[:\s]+([A-Z][A-Za-z\s]+)', line, re.IGNORECASE)
                if brand_match:
                    sections["brand"] = brand_match.group(1).strip()
            
            # Detect claims (organic, natural, etc.)
            claims_keywords = ["organic", "natural", "gluten-free", "sugar-free", "low fat", "high protein"]
            for claim in claims_keywords:
                if claim in line_lower:
                    sections["claims"].append(claim)
        
        return sections
    
    def _is_section_boundary(self, line: str) -> bool:
        """Check if a line indicates a new section boundary"""
        line_lower = line.lower()
        
        boundary_keywords = ["ingredients", "nutrition", "allergens", "storage", "manufactured"]
        
        return any(kw in line_lower for kw in boundary_keywords) and len(line) < 50


# ==========================================================
# ENHANCED NUTRITION TABLE PARSER
# ==========================================================


class NutritionTableParser:
    
    def parse_nutrition_table(self, text: str, blocks: List[Dict]) -> Dict[str, Any]:
        """
        Extract structured nutrition data from OCR text.
        Handles table layouts with per-serving and per-100g values.
        Uses enhanced regex patterns for better coverage.
        """
        nutrition_data = {
            "energy": None,
            "protein": None,
            "carbohydrates": None,
            "sugar": None,
            "fat": None,
            "saturated_fat": None,
            "fiber": None,
            "sodium": None,
            "cholesterol": None,
            "trans_fat": None,
            "vitamin_d": None,
            "calcium": None,
            "iron": None,
            "potassium": None,
            "serving_size": None,
            "per_serving": {},
            "per_100g": {},
        }
        
        lines = text.split('\n')
        text_lower = text.lower()
        
        # Check for per-serving vs per-100g context throughout the document
        has_per_serving = "per serving" in text_lower
        has_per_100g = "per 100g" in text_lower or "per 100ml" in text_lower
        
        # First pass: extract values using enhanced patterns
        for line in lines:
            # Determine context for this line
            if "per serving" in line.lower():
                current_context = "per_serving"
            elif "per 100g" in line.lower() or "per 100ml" in line.lower():
                current_context = "per_100g"
            elif has_per_serving and not has_per_100g:
                current_context = "per_serving"
            elif has_per_100g and not has_per_serving:
                current_context = "per_100g"
            else:
                current_context = None
            
            # Extract values for each nutrient using multiple patterns
            for nutrient, patterns in NUTRITION_PATTERNS.items():
                for pattern in patterns:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        try:
                            value = float(match.group(1))
                            
                            if current_context == "per_serving":
                                nutrition_data["per_serving"][nutrient] = value
                            elif current_context == "per_100g":
                                nutrition_data["per_100g"][nutrient] = value
                            else:
                                # If no specific context, store directly and also in both
                                nutrition_data[nutrient] = value
                                
                                # Also populate per_100g as default if not specified elsewhere
                                if nutrient not in nutrition_data["per_100g"]:
                                    nutrition_data["per_100g"][nutrient] = value
                            
                            break  # Found match for this nutrient in this line
                        except (ValueError, TypeError):
                            continue
            
            # Extract serving size
            serving_match = re.search(r'(?:serving size|servings|serving)[:\s]*(\d+(?:\.\d+)?)\s*(g|ml|oz|cup|piece|slice|tbsp|tsp)', line, re.IGNORECASE)
            if serving_match and not nutrition_data["serving_size"]:
                nutrition_data["serving_size"] = f"{serving_match.group(1)}{serving_match.group(2)}"
        
        # Second pass: fill in missing data from per_100g if direct values exist
        for nutrient in NUTRITION_PATTERNS.keys():
            if nutrition_data.get(nutrient) is None and nutrition_data["per_100g"].get(nutrient):
                nutrition_data[nutrient] = nutrition_data["per_100g"][nutrient]
        
        return nutrition_data


# ==========================================================
# OCR ENGINE (Main Class)
# ==========================================================


class OCREngine:
    
    def __init__(self):
        
        self._reader = None
        
        self._last_used = None
        
        self._languages = settings.OCR_LANGUAGES_LIST
        
        self._min_confidence = MIN_OCR_CONFIDENCE
        
        self._max_text_length = settings.OCR_MAX_TEXT_LENGTH
        
        self._tesseract_available = self._check_tesseract()
        
        self._orientation_detector = OrientationDetector()
        
        self._section_extractor = SectionExtractor()
        
        self._nutrition_parser = NutritionTableParser()
        
        self._image_results_cache: Dict[str, List[Tuple]] = {}
    
    
    def _check_tesseract(self) -> bool:
        
        try:
            
            result = subprocess.run(
                ["tesseract", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            return result.returncode == 0
        
        except Exception:
            
            logger.warning("Tesseract OCR not found on system. Fallback disabled.")
            
            return False
    
    
    def _preprocess_image_in_memory(self, image_bytes: bytes) -> Tuple[np.ndarray, int]:
        """
        Preprocess image and detect orientation using OCR-based method.
        Returns (processed_image, orientation_angle)
        """
        # Zero-disk processing: Convert bytes directly to numpy array
        nparr = np.frombuffer(image_bytes, np.uint8)
        
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            
            raise ValueError("Could not decode image bytes into numpy array")
        
        if len(image.shape) == 3:
            
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        else:
            
            gray = image
        
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        
        enhanced = clahe.apply(gray)
        
        denoised = cv2.fastNlMeansDenoising(enhanced, h=10)
        
        # Detect orientation using OCR-based method (requires reader)
        angle = 0
        if self._reader is not None:
            angle = self._orientation_detector.detect_orientation_by_ocr(image, self._reader)
        
        if angle != 0:
            denoised = self._orientation_detector._rotate_image(denoised, angle)
            logger.debug(f"Applied orientation correction: {angle} degrees")
        
        return denoised, angle
    
    
    def _sort_blocks_by_reading_order(self, blocks: List[Tuple]) -> List[Tuple]:
        
        if not blocks:
            
            return blocks
        
        sorted_by_y = sorted(blocks, key=lambda x: x[0][0][1])
        
        lines = []
        
        current_line = []
        
        current_y = None
        
        y_threshold = 20
        
        for block in sorted_by_y:
            
            bbox = block[0]
            
            y_center = (bbox[0][1] + bbox[2][1]) / 2
            
            if current_y is None or abs(y_center - current_y) <= y_threshold:
                
                current_line.append(block)
                
                current_y = y_center
            
            else:
                
                if current_line:
                    
                    current_line.sort(key=lambda x: x[0][0][0])
                    
                    lines.extend(current_line)
                
                current_line = [block]
                
                current_y = y_center
        
        if current_line:
            
            current_line.sort(key=lambda x: x[0][0][0])
            
            lines.extend(current_line)
        
        return lines
    
    
    def _apply_corrections(self, text: str) -> str:
        
        if not text:
            
            return ""
        
        corrected = text
        
        for wrong, right in OCR_CORRECTIONS.items():
            
            pattern = re.compile(rf"\b{re.escape(wrong)}\b", re.IGNORECASE)
            
            corrected = pattern.sub(right, corrected)
        
        corrected = re.sub(r"\s+", " ", corrected)
        
        return corrected.strip()
    
    
    def _calculate_density_score(self, text: str) -> int:
        
        if not text:
            
            return 0
        
        words = len(text.split())
        
        return min(words * 2, 100)
    
    
    def _calculate_readability_score(self, text: str) -> int:
        
        if not text:
            
            return 0
        
        alpha_chars = sum(1 for c in text if c.isalpha())
        
        return min(alpha_chars // 3, 100)
    
    
    def _calculate_ocr_quality_score(
        self,
        text: str,
        avg_confidence: float,
        sections: Dict[str, Any],
    ) -> int:
        """
        Calculate comprehensive OCR quality score.
        Factors: confidence, text coverage, section detection, nutrition presence.
        """
        score = int(avg_confidence * 100)
        
        # Boost for detected sections
        section_boost = 0
        
        if sections.get("ingredients"):
            section_boost += 10
        
        if sections.get("nutrition_facts"):
            section_boost += 15
        
        if sections.get("product_name"):
            section_boost += 5
        
        if sections.get("brand"):
            section_boost += 5
        
        # Boost for text length (coverage)
        text_length_boost = min(len(text) // 200, 20)
        
        total_score = score + section_boost + text_length_boost
        
        return min(total_score, 100)
    
    
    def _process_ocr_results(self, results: List[Tuple], image_index: int = 0) -> Dict[str, Any]:
        
        if not results:
            
            raise OCRNoTextError()
        
        sorted_results = self._sort_blocks_by_reading_order(results)
        
        blocks = []
        
        confidence_values = []
        
        extracted_text = []
        
        for result in sorted_results:
            
            bbox = result[0]
            
            text_block = result[1]
            
            confidence = float(result[2])
            
            if confidence >= self._min_confidence:
                
                # Convert numpy float coordinates to standard python floats for JSON serialization
                clean_bbox = [[float(point[0]), float(point[1])] for point in bbox]
                
                blocks.append({
                    "text": text_block,
                    "confidence": confidence,
                    "bbox": clean_bbox,
                })
                
                confidence_values.append(confidence)
                
                extracted_text.append(text_block)
        
        if not blocks:
            
            raise OCRNoTextError()
        
        raw_merged_text = "\n".join(extracted_text)
        
        corrected_text = self._apply_corrections(raw_merged_text)
        
        if len(corrected_text) > self._max_text_length:
            
            corrected_text = corrected_text[:self._max_text_length]
        
        avg_confidence = sum(confidence_values) / len(confidence_values) if confidence_values else 0.0
        
        # Detect sections and nutrition data
        sections = self._section_extractor.detect_sections(corrected_text, blocks)
        
        nutrition_data = self._nutrition_parser.parse_nutrition_table(corrected_text, blocks)
        
        ocr_quality_score = self._calculate_ocr_quality_score(corrected_text, avg_confidence, sections)
        
        # Strict mapping to OCRResult Pydantic schema
        return {
            "extracted_text": corrected_text,
            "raw_text": raw_merged_text[:self._max_text_length],
            "blocks": blocks,
            "average_confidence": avg_confidence,
            "text_density_score": self._calculate_density_score(corrected_text),
            "readability_score": self._calculate_readability_score(corrected_text),
            "ocr_quality_score": ocr_quality_score,
            "ocr_provider": "easyocr",
            "processing_time_ms": 0,  # Computed in outer wrapper
            "detected_sections": sections,
            "nutrition_data": nutrition_data,
            "image_index": image_index,
        }
    
    
    def _run_tesseract_ocr(self, processed_image: np.ndarray) -> Optional[Dict[str, Any]]:
        
        if not self._tesseract_available:
            
            return None
        
        try:
            
            import pytesseract
            
            custom_config = r'--oem 3 --psm 6'
            
            text = pytesseract.image_to_string(processed_image, config=custom_config)
            
            if not text or len(text.strip()) < 10:
                
                return None
            
            corrected_text = self._apply_corrections(text.strip())
            
            # Detect sections for Tesseract results as well
            sections = self._section_extractor.detect_sections(corrected_text, [])
            
            nutrition_data = self._nutrition_parser.parse_nutrition_table(corrected_text, [])
            
            ocr_quality_score = self._calculate_ocr_quality_score(corrected_text, 0.75, sections)
            
            return {
                "extracted_text": corrected_text,
                "raw_text": text[:self._max_text_length],
                "blocks": [{"text": text.strip(), "confidence": 0.75, "bbox": []}],
                "average_confidence": 0.75,
                "text_density_score": self._calculate_density_score(corrected_text),
                "readability_score": self._calculate_readability_score(corrected_text),
                "ocr_quality_score": ocr_quality_score,
                "ocr_provider": "tesseract",
                "processing_time_ms": 0,
                "detected_sections": sections,
                "nutrition_data": nutrition_data,
                "image_index": 0,
            }
        
        except Exception as e:
            
            logger.warning(f"Tesseract OCR failed: {e}")
            
            return None
    
    
    def _merge_multi_image_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge OCR results from multiple images of the same product.
        Combines text, prioritizes higher confidence blocks, deduplicates.
        """
        if not results:
            raise OCRNoTextError()
        
        if len(results) == 1:
            return results[0]
        
        # Combine all text
        all_text = []
        all_blocks = []
        all_confidence = []
        
        # Priority: nutrition facts > ingredients > other
        best_sections = {}
        best_nutrition = {}
        
        for result in results:
            all_text.append(result["extracted_text"])
            all_blocks.extend(result["blocks"])
            all_confidence.append(result["average_confidence"])
            
            # Take best sections (prefer results with nutrition data)
            sections = result.get("detected_sections", {})
            nutrition = result.get("nutrition_data", {})
            
            if nutrition.get("per_100g") and not best_nutrition:
                best_nutrition = nutrition
                best_sections = sections
            elif not best_nutrition and sections.get("ingredients"):
                best_sections = sections
                best_nutrition = nutrition
        
        # Deduplicate blocks by text content
        seen_texts = set()
        unique_blocks = []
        
        for block in all_blocks:
            text_key = block.get("text", "").lower().strip()
            if text_key and text_key not in seen_texts:
                seen_texts.add(text_key)
                unique_blocks.append(block)
        
        merged_text = "\n\n".join(all_text)
        
        # Apply corrections to merged text
        merged_text = self._apply_corrections(merged_text)
        
        if len(merged_text) > self._max_text_length:
            merged_text = merged_text[:self._max_text_length]
        
        avg_confidence = sum(all_confidence) / len(all_confidence) if all_confidence else 0.0
        
        ocr_quality_score = self._calculate_ocr_quality_score(
            merged_text, avg_confidence, best_sections
        )
        
        return {
            "extracted_text": merged_text,
            "raw_text": merged_text[:self._max_text_length],
            "blocks": unique_blocks,
            "average_confidence": avg_confidence,
            "text_density_score": self._calculate_density_score(merged_text),
            "readability_score": self._calculate_readability_score(merged_text),
            "ocr_quality_score": ocr_quality_score,
            "ocr_provider": "multi_easyocr",
            "processing_time_ms": sum(r.get("processing_time_ms", 0) for r in results),
            "detected_sections": best_sections,
            "nutrition_data": best_nutrition,
            "images_processed": len(results),
        }
    
    
    @property
    def reader(self):
        
        if self._reader is None:
            
            gc.collect()
            
            logger.info("Initializing EasyOCR reader...")
            
            self._reader = easyocr.Reader(
                self._languages,
                gpu=False,
                verbose=False,
            )
            
            self._last_used = time.time()
            
            # Set reference in orientation detector
            self._orientation_detector._set_ocr_instance(self)
            
            logger.info("EasyOCR reader initialized successfully")
        
        return self._reader
    
    
    def cleanup_if_idle(self) -> None:
        
        if self._reader and self._last_used:
            
            if time.time() - self._last_used > 300:
                
                self._reader = None
                
                self._last_used = None
                
                gc.collect()
                
                logger.info("OCR reader cleaned up due to idle timeout")
    
    
    async def warmup(self) -> None:
        """Pre-initialize OCR reader during application startup"""
        await asyncio.to_thread(lambda: self.reader)
        logger.info("OCR engine warmed up successfully")
    
    
    async def extract_text(self, file: UploadFile) -> Dict[str, Any]:
        
        content = await file.read()
        
        await file.seek(0)
        
        return await self.extract_text_from_bytes(content)
    
    
    async def extract_text_from_bytes(self, image_bytes: bytes) -> Dict[str, Any]:
        
        start_time = time.time()
        
        try:
            
            # Offload heavy OpenCV operations to background thread
            processed_image, orientation_angle = await asyncio.to_thread(
                self._preprocess_image_in_memory, image_bytes
            )
            
            try:
                
                # Run EasyOCR natively on the numpy array in a thread
                results = await asyncio.wait_for(
                    asyncio.to_thread(self.reader.readtext, processed_image),
                    timeout=OCR_TIMEOUT_SECONDS
                )
                
                ocr_result = self._process_ocr_results(results)
                
                ocr_result["processing_time_ms"] = int((time.time() - start_time) * 1000)
                
                if orientation_angle != 0:
                    ocr_result["orientation_corrected"] = orientation_angle
                
                return ocr_result
            
            except (OCRNoTextError, asyncio.TimeoutError) as e:
                
                logger.warning(f"EasyOCR failed or timed out: {e}. Falling back to Tesseract.")
                
                # Offload Tesseract execution to background thread
                tesseract_result = await asyncio.to_thread(self._run_tesseract_ocr, processed_image)
                
                if tesseract_result:
                    
                    tesseract_result["processing_time_ms"] = int((time.time() - start_time) * 1000)
                    
                    if orientation_angle != 0:
                        tesseract_result["orientation_corrected"] = orientation_angle
                    
                    return tesseract_result
                
                raise
        
        except asyncio.TimeoutError:
            
            logger.error(f"OCR timeout after {OCR_TIMEOUT_SECONDS} seconds")
            
            raise OCRTimeoutError(OCR_TIMEOUT_SECONDS)
        
        except OCRNoTextError:
            
            raise
        
        except Exception as e:
            
            logger.exception(f"OCR processing failed: {e}")
            
            raise OCRError(str(e))
    
    
    async def extract_text_from_multiple_images(
        self,
        image_bytes_list: List[bytes],
    ) -> Dict[str, Any]:
        """
        Process multiple images of the same product and merge results.
        Use for products with front/back/side labels.
        """
        results = []
        
        for i, image_bytes in enumerate(image_bytes_list):
            try:
                result = await self.extract_text_from_bytes(image_bytes)
                result["image_index"] = i
                results.append(result)
            except OCRNoTextError:
                logger.warning(f"No text found in image {i}")
                continue
            except Exception as e:
                logger.warning(f"Failed to process image {i}: {e}")
                continue
        
        if not results:
            raise OCRNoTextError()
        
        merged_result = self._merge_multi_image_results(results)
        
        return merged_result
    
    
    def get_ocr_heatmap_data(self, blocks: List[OCRBlock], image_shape: Tuple[int, int]) -> List[Dict]:
        
        height, width = image_shape
        
        heatmap_data = []
        
        for block in blocks:
            
            bbox = block.bbox
            
            if bbox and len(bbox) >= 4:
                
                normalized_bbox = []
                
                for point in bbox:
                    
                    x = point[0] / width if width > 0 else 0.0
                    
                    y = point[1] / height if height > 0 else 0.0
                    
                    normalized_bbox.append([x, y])
                
                heatmap_data.append({
                    "text": block.text,
                    "confidence": block.confidence,
                    "bbox": normalized_bbox,
                })
        
        return heatmap_data


# ==========================================================
# SINGLETON
# ==========================================================


ocr_engine = OCREngine()


# ==========================================================
# END OF FILE
# ==========================================================