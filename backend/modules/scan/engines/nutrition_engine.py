# ==========================================================
# SCANIX AI
# SYSTEM 1 - NUTRITION ENGINE
# Extracts nutrition information from OCR text
# Features: Pre-compiled Regex, 100g Normalization, Immutable Thresholds
# Enhanced pattern matching, serving size detection, calorie extraction
# ==========================================================


import re
from types import MappingProxyType
from typing import Dict
from typing import List
from typing import Tuple

from core.logging import get_logger
from modules.scan.schemas import NutritionData
from modules.scan.schemas import TrafficLight


logger = get_logger(__name__)


# ==========================================================
# PRE-COMPILED NUTRITION PATTERNS (For Maximum Throughput)
# ==========================================================


NUTRITION_PATTERNS = MappingProxyType({
    "protein": (
        re.compile(r"protein\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*g", re.IGNORECASE),
        re.compile(r"prot(e|ei)n\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*g", re.IGNORECASE),
        re.compile(r"proteln\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*g", re.IGNORECASE),
        re.compile(r"pr[o0]tein\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*g", re.IGNORECASE),
    ),
    "fat": (
        re.compile(r"total\s*fat\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*g", re.IGNORECASE),
        re.compile(r"fat\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*g", re.IGNORECASE),
        re.compile(r"f[ae]t\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*g", re.IGNORECASE),
    ),
    "saturated_fat": (
        re.compile(r"saturated\s*fat\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*g", re.IGNORECASE),
        re.compile(r"sat\.?\s*fat\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*g", re.IGNORECASE),
        re.compile(r"satd\s*fat\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*g", re.IGNORECASE),
        re.compile(r"saturates\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*g", re.IGNORECASE),
    ),
    "sugar": (
        re.compile(r"sugars?\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*g", re.IGNORECASE),
        re.compile(r"total\s*sugars?\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*g", re.IGNORECASE),
        re.compile(r"sug[ae]r\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*g", re.IGNORECASE),
    ),
    "added_sugar": (
        re.compile(r"added\s*sugars?\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*g", re.IGNORECASE),
        re.compile(r"includes\s*(\d+(?:\.\d+)?)\s*g\s*added\s*sugars?", re.IGNORECASE),
        re.compile(r"added\s*sugar\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*g", re.IGNORECASE),
    ),
    "sodium": (
        re.compile(r"sodium\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*mg", re.IGNORECASE),
        re.compile(r"salt\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*g", re.IGNORECASE),
        re.compile(r"sod[iu]m\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*mg", re.IGNORECASE),
    ),
    "salt": (
        re.compile(r"salt\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*g", re.IGNORECASE),
        re.compile(r"sodium\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*mg", re.IGNORECASE),
    ),
    "carbohydrates": (
        re.compile(r"carbohydrates?\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*g", re.IGNORECASE),
        re.compile(r"carbs?\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*g", re.IGNORECASE),
        re.compile(r"carbohyd[ae]te\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*g", re.IGNORECASE),
        re.compile(r"total\s*carbohydrates?\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*g", re.IGNORECASE),
    ),
    "fiber": (
        re.compile(r"fiber\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*g", re.IGNORECASE),
        re.compile(r"fibre\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*g", re.IGNORECASE),
        re.compile(r"dietary\s*fiber\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*g", re.IGNORECASE),
        re.compile(r"dietary\s*fibre\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*g", re.IGNORECASE),
        re.compile(r"fib[er]e\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*g", re.IGNORECASE),
    ),
    "calories": (
        re.compile(r"calories?\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*kcal", re.IGNORECASE),
        re.compile(r"energy\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*kcal", re.IGNORECASE),
        re.compile(r"energy\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*kj", re.IGNORECASE),
        re.compile(r"energy\s*value\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*kcal", re.IGNORECASE),
        re.compile(r"energy\s*\(\s*kcal\s*\)\s*[|:.\-]*\s*(\d+(?:\.\d+)?)", re.IGNORECASE),
        re.compile(r"calories?\s*[|:.\-]*\s*(\d+(?:\.\d+)?)", re.IGNORECASE),
        re.compile(r"calorie\s*[|:.\-]*\s*(\d+(?:\.\d+)?)", re.IGNORECASE),
        re.compile(r"kcal\s*[|:.\-]*\s*(\d+(?:\.\d+)?)", re.IGNORECASE),
        re.compile(r"energy\s*\(\s*kj\s*\)\s*[|:.\-]*\s*(\d+(?:\.\d+)?)", re.IGNORECASE),
        re.compile(r"energy:\s*(\d+(?:\.\d+)?)\s*kcal", re.IGNORECASE),
    ),
})

SERVING_SIZE_PATTERNS = (
    re.compile(r"per\s+serving\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(g|ml|gm|gram|grams)", re.IGNORECASE),
    re.compile(r"serving\s+size\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(g|ml|gm|gram|grams)", re.IGNORECASE),
    re.compile(r"each\s+serving\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(g|ml|gm|gram|grams)", re.IGNORECASE),
    re.compile(r"(\d+(?:\.\d+)?)\s*(g|ml|gm|gram|grams)\s+per\s+serving", re.IGNORECASE),
    re.compile(r"serving\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(g|ml|gm|gram|grams)", re.IGNORECASE),
    re.compile(r"1\s*(packet|sachet|piece|slice|cup|tablespoon|tbsp|teaspoon|tsp)", re.IGNORECASE),
    re.compile(r"1\s*(cookie|biscuit|bar|scoop|serving)", re.IGNORECASE),
    re.compile(r"serving\s*size\s*[:\-]?\s*1\s*(cookie|biscuit|bar|slice)", re.IGNORECASE),
)

KJ_PATTERN = re.compile(r"energy\s*[|:.\-]*\s*(\d+(?:\.\d+)?)\s*kj", re.IGNORECASE)


# ==========================================================
# THRESHOLDS & LIMITS (Immutable)
# ==========================================================


TRAFFIC_LIGHT_THRESHOLDS = MappingProxyType({
    "sugar": MappingProxyType({"green": 5.0, "yellow": 12.5, "red": 22.5}),
    "fat": MappingProxyType({"green": 3.0, "yellow": 17.5, "red": 25.0}),
    "saturated_fat": MappingProxyType({"green": 1.5, "yellow": 5.0, "red": 7.5}),
    "sodium": MappingProxyType({"green": 120.0, "yellow": 400.0, "red": 800.0}),
    "calories": MappingProxyType({"green": 100.0, "yellow": 200.0, "red": 400.0}),
    "protein": MappingProxyType({"green": 10.0, "yellow": 5.0, "red": 0.0}),
    "fiber": MappingProxyType({"green": 6.0, "yellow": 3.0, "red": 0.0}),
    "added_sugar": MappingProxyType({"green": 5.0, "yellow": 12.5, "red": 22.5}),
})


VALIDATION_LIMITS = MappingProxyType({
    "protein": (0.0, 100.0),
    "fat": (0.0, 100.0),
    "saturated_fat": (0.0, 50.0),
    "sugar": (0.0, 100.0),
    "added_sugar": (0.0, 100.0),
    "sodium": (0.0, 10000.0),
    "salt": (0.0, 30.0),
    "carbohydrates": (0.0, 100.0),
    "fiber": (0.0, 50.0),
    "calories": (0.0, 1000.0),
})


COMPLETENESS_WEIGHTS = MappingProxyType({
    "calories": 20,
    "protein": 15,
    "fat": 15,
    "carbohydrates": 15,
    "sugar": 15,
    "sodium": 10,
    "fiber": 10,
})


OCR_CORRECTIONS = MappingProxyType({
    "proteln": "protein",
    "protien": "protein",
    "prote in": "protein",
    "pr0tein": "protein",
    "f1ber": "fiber",
    "f1bre": "fiber",
    "sugor": "sugar",
    "suger": "sugar",
    "calaries": "calories",
    "caloires": "calories",
    "soduim": "sodium",
    "sodim": "sodium",
    "carbohydrate": "carbohydrates",
    "carbohydratez": "carbohydrates",
})


class NutritionEngine:
    
    def _normalize_ocr_text(self, text: str) -> str:
        
        if not text:
            
            return ""
        
        normalized = text.lower()
        
        for wrong, right in OCR_CORRECTIONS.items():
            
            if wrong in normalized:
                
                normalized = normalized.replace(wrong, right)
        
        return normalized
    
    
    def _extract_serving_size(self, text: str) -> Tuple[float, bool, str]:
        
        for pattern in SERVING_SIZE_PATTERNS:
            
            match = pattern.search(text)
            
            if match:
                
                # Check for unit-based serving (cookie, biscuit, bar, etc.)
                unit_based_match = re.match(
                    r"^1\s*(packet|sachet|piece|slice|cup|tablespoon|tbsp|teaspoon|tsp|cookie|biscuit|bar|scoop|serving)",
                    match.group(0) if len(match.groups()) == 1 else (match.group(1) if len(match.groups()) > 1 else ""),
                    re.IGNORECASE,
                )
                
                if unit_based_match:
                    
                    unit = unit_based_match.group(1) if unit_based_match.lastindex else "piece"
                    
                    return 100.0, True, unit
                
                # Check for 1 cookie/biscuit/bar in serving size pattern
                if len(match.groups()) >= 1 and match.group(0).lower().find("cookie") >= 0:
                    return 100.0, True, "cookie"
                
                if len(match.groups()) >= 1 and match.group(0).lower().find("biscuit") >= 0:
                    return 100.0, True, "biscuit"
                
                if len(match.groups()) >= 1 and match.group(0).lower().find("bar") >= 0:
                    return 100.0, True, "bar"
                
                # Extract numeric value and unit
                if len(match.groups()) >= 2:
                    
                    try:
                        value = float(match.group(1))
                    except (ValueError, TypeError):
                        continue
                    
                    unit = match.group(2).lower() if len(match.groups()) > 1 else "g"
                    
                    if unit in ("g", "gm", "gram", "grams"):
                        
                        return value, True, unit
        
        return 100.0, False, "g"
    
    
    def _convert_to_per_100g(self, value: float, serving_size_g: float) -> float:
        
        if serving_size_g <= 0 or serving_size_g == 100:
            
            return value
        
        return round((value * 100) / serving_size_g, 2)
    
    
    def _get_traffic_light(self, value: float, thresholds: Dict[str, float]) -> TrafficLight:
        
        if value <= thresholds.get("green", 0.0):
            
            return TrafficLight.GREEN
        
        if value <= thresholds.get("yellow", 0.0):
            
            return TrafficLight.YELLOW
        
        return TrafficLight.RED
    
    
    def _validate_value(self, field: str, value: float) -> float:
        
        if field not in VALIDATION_LIMITS:
            
            return value
        
        min_val, max_val = VALIDATION_LIMITS[field]
        
        if value < min_val or value > max_val:
            
            return 0.0
        
        return value
    
    
    def _fix_ocr_digit_error(self, value: float) -> float:
        
        """
        Fixes OCR digit errors where numbers end with .09, .08
        Example: 3.09 -> 3.0, 5.08 -> 5.0
        
        Only corrects when the value appears to be an obvious OCR error
        where the last digit is 9 or 8 and the value is less than 100.
        This is conservative to avoid incorrect corrections.
        """
        
        # Only correct values that are likely nutrition values (< 100)
        if value >= 100:
            return value
        
        str_val = str(value)
        
        # Check if the value ends with .09, .08, .07, .06, .05, .04, .03, .02, .01
        # And the decimal part is either a single digit 9 or 8, or two digits ending with 9/8
        match = re.search(r"\.(\d)9$", str_val)
        
        if match:
            # Extract the first decimal digit and convert to 0
            first_decimal = match.group(1)
            corrected = float(f"{int(value)}.{first_decimal}0")
            logger.debug(f"OCR digit correction: {value} -> {corrected}")
            return corrected
        
        # Also check for .08, .07, etc. where last digit is 8 (only if value < 20)
        match = re.search(r"\.(\d)8$", str_val)
        
        if match and value < 20:
            first_decimal = match.group(1)
            corrected = float(f"{int(value)}.{first_decimal}0")
            logger.debug(f"OCR digit correction: {value} -> {corrected}")
            return corrected
        
        return value
    
    
    def _extract_best_match(self, patterns: Tuple[re.Pattern, ...], text: str, field: str) -> Tuple[float, int]:
        
        best_value = 0.0
        
        best_confidence = 0
        
        for pattern in patterns:
            
            matches = pattern.finditer(text)
            
            for match in matches:
                
                try:
                    value = float(match.group(1))
                except (ValueError, TypeError, IndexError):
                    continue
                
                confidence = 90 if len(pattern.pattern) > 30 else 80
                
                if field == "sodium" and "salt" in pattern.pattern:
                    
                    value = value * 400.0
                    
                    confidence = 85
                
                if value > best_value and value < 1000:
                    
                    best_value = value
                    
                    best_confidence = confidence
        
        return best_value, best_confidence
    
    
    def _calculate_weighted_completeness(self, nutrition_values: Dict[str, float]) -> int:
        
        total_weight = 0
        
        achieved_weight = 0
        
        for field, weight in COMPLETENESS_WEIGHTS.items():
            
            total_weight += weight
            
            if nutrition_values.get(field, 0.0) > 0.0:
                
                achieved_weight += weight
        
        if total_weight == 0:
            
            return 0
        
        return int((achieved_weight / total_weight) * 100)
    
    
    def _detect_nutrition_table(self, text: str) -> bool:
        
        if not text:
            
            return False
        
        nutrition_indicators = (
            "nutrition facts",
            "nutritional information",
            "nutrition information",
            "per 100g",
            "per 100 ml",
            "per serving",
            "typical values",
            "nutrient",
        )
        
        # Check for explicit indicators
        if any(indicator in text for indicator in nutrition_indicators):
            
            return True
        
        # Secondary heuristic: count how many nutrition fields are present
        nutrition_fields_found = 0
        
        for field, patterns in NUTRITION_PATTERNS.items():
            for pattern in patterns:
                if pattern.search(text):
                    nutrition_fields_found += 1
                    break
        
        # If 3 or more nutrition fields detected, assume nutrition table exists
        if nutrition_fields_found >= 3:
            logger.debug(f"Nutrition table detected by field count: {nutrition_fields_found} fields found")
            return True
        
        return False
    
    
    def extract(self, text: str, has_nutrition_table: bool = False) -> NutritionData:
        
        normalized = self._normalize_ocr_text(text)
        
        if not has_nutrition_table:
            
            has_nutrition_table = self._detect_nutrition_table(normalized)
        
        if not has_nutrition_table or not text:
            
            return NutritionData(
                nutrition_detected=False,
                nutrition_completeness=0,
                nutrition_confidence=0,
                missing_fields=["nutrition_data"],
            )
        
        serving_size_g, is_per_serving, _ = self._extract_serving_size(normalized)
        
        nutrition_values = {}
        
        extraction_confidence = {}
        
        for field, patterns in NUTRITION_PATTERNS.items():
            
            value, confidence = self._extract_best_match(patterns, normalized, field)
            
            if value > 0:
                
                value = self._validate_value(field, value)
                
                if value > 0:
                    
                    # Fix OCR digit errors like 3.09 -> 3.0 (conservatively)
                    value = self._fix_ocr_digit_error(value)
                    
                    nutrition_values[field] = value
                    
                    extraction_confidence[field] = confidence
        
        if nutrition_values.get("calories", 0.0) == 0.0:
            
            kj_match = KJ_PATTERN.search(normalized)
            
            if kj_match:
                
                try:
                    kj = float(kj_match.group(1))
                    calories = round(kj / 4.184, 1)
                    
                    # Fix OCR digit errors on calories
                    calories = self._fix_ocr_digit_error(calories)
                    
                    nutrition_values["calories"] = calories
                    
                    extraction_confidence["calories"] = 85
                except (ValueError, TypeError):
                    pass
        
        for field in NUTRITION_PATTERNS.keys():
            
            if field not in nutrition_values:
                
                nutrition_values[field] = 0.0
        
        if nutrition_values.get("sodium", 0.0) > 0.0 and nutrition_values.get("salt", 0.0) == 0.0:
            
            nutrition_values["salt"] = round(nutrition_values["sodium"] / 400.0, 2)
        
        if is_per_serving and serving_size_g != 100.0:
            
            fields_to_convert = ("protein", "fat", "saturated_fat", "sugar", "added_sugar", "carbohydrates", "fiber", "sodium", "salt", "calories")
            
            for field in fields_to_convert:
                
                if nutrition_values.get(field, 0.0) > 0.0:
                    
                    nutrition_values[field] = self._convert_to_per_100g(nutrition_values[field], serving_size_g)
        
        completeness = self._calculate_weighted_completeness(nutrition_values)
        
        avg_confidence = sum(extraction_confidence.values()) / len(extraction_confidence) if extraction_confidence else 0.0
        
        confidence = int((completeness * 0.6) + (avg_confidence * 0.4))
        
        missing_fields = []
        
        core_fields = ("protein", "fat", "sugar", "sodium", "fiber", "calories")
        
        for field in core_fields:
            
            if nutrition_values.get(field, 0.0) == 0.0:
                
                missing_fields.append(field)
        
        sugar_light = self._get_traffic_light(nutrition_values.get("sugar", 0.0), TRAFFIC_LIGHT_THRESHOLDS["sugar"])
        
        fat_light = self._get_traffic_light(nutrition_values.get("fat", 0.0), TRAFFIC_LIGHT_THRESHOLDS["fat"])
        
        sat_fat_light = self._get_traffic_light(nutrition_values.get("saturated_fat", 0.0), TRAFFIC_LIGHT_THRESHOLDS["saturated_fat"])
        
        sodium_light = self._get_traffic_light(nutrition_values.get("sodium", 0.0), TRAFFIC_LIGHT_THRESHOLDS["sodium"])
        
        added_sugar_light = self._get_traffic_light(nutrition_values.get("added_sugar", 0.0), TRAFFIC_LIGHT_THRESHOLDS["added_sugar"]) if nutrition_values.get("added_sugar", 0.0) > 0 else None
        
        return NutritionData(
            nutrition_detected=True,
            nutrition_completeness=completeness,
            nutrition_confidence=confidence,
            protein=round(nutrition_values.get("protein", 0.0), 1),
            fat=round(nutrition_values.get("fat", 0.0), 1),
            saturated_fat=round(nutrition_values.get("saturated_fat", 0.0), 1),
            sugar=round(nutrition_values.get("sugar", 0.0), 1),
            sodium=round(nutrition_values.get("sodium", 0.0), 0),
            carbohydrates=round(nutrition_values.get("carbohydrates", 0.0), 1),
            fiber=round(nutrition_values.get("fiber", 0.0), 1),
            calories=round(nutrition_values.get("calories", 0.0), 0),
            serving_size_g=serving_size_g,
            is_per_serving=is_per_serving,
            missing_fields=missing_fields,
            sugar_traffic_light=sugar_light,
            fat_traffic_light=fat_light,
            saturated_fat_traffic_light=sat_fat_light,
            sodium_traffic_light=sodium_light,
            added_sugar_traffic_light=added_sugar_light,
        )


# ==========================================================
# SINGLETON
# ==========================================================


nutrition_engine = NutritionEngine()


# ==========================================================
# END OF FILE
# ==========================================================