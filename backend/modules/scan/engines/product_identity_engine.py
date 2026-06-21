# ==========================================================
# SCANIX AI
# SYSTEM 1 - PRODUCT IDENTITY ENGINE
# Product detection from OCR and OpenFoodFacts
# Features: Strict Pydantic typing, Async HTTPX, Tenacity backoff, Rapidfuzz
# OCR-OFF consistency verification, OFF search fallback with full product fetch
# ==========================================================


import re
from types import MappingProxyType
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

import httpx
from cachetools import TTLCache
from rapidfuzz import fuzz
from tenacity import retry, stop_after_attempt, wait_exponential

from core.config import settings
from core.logging import get_logger

from modules.scan.constants import PACKAGE_TYPE_KEYWORDS
from modules.scan.schemas import BarcodeResult
from modules.scan.schemas import OCRBlock
from modules.scan.schemas import OpenFoodFactsMatch
from modules.scan.schemas import PackageType
from modules.scan.schemas import ProductFusionResult
from modules.scan.schemas import ProductIdentity
from modules.scan.schemas import ProductPassport
from modules.scan.schemas import ProductSource
from modules.scan.schemas import VerificationLevel


logger = get_logger(__name__)


# ==========================================================
# HEURISTIC MAPPINGS (Immutable)
# ==========================================================


CATEGORY_KEYWORDS = MappingProxyType({
    "chips": {"keywords": ("chips", "crisps", "potato", "namkeen", "bhujia", "wafers"), "weight": 10},
    "biscuits": {"keywords": ("biscuit", "cookie", "cracker", "cream biscuit", "digestive"), "weight": 10},
    "chocolate": {"keywords": ("chocolate", "candy", "cocoa", "milk chocolate", "dark chocolate"), "weight": 10},
    "soft_drink": {"keywords": ("soda", "cola", "soft drink", "carbonated", "beverage", "soda pop"), "weight": 10},
    "noodles": {"keywords": ("noodle", "instant noodle", "ramen", "pasta", "macaroni"), "weight": 10},
    "protein_bar": {"keywords": ("protein bar", "energy bar", "nutrition bar", "snack bar"), "weight": 10},
    "ice_cream": {"keywords": ("ice cream", "frozen dessert", "gelato", "sorbet", "frozen yogurt"), "weight": 10},
    "energy_drink": {"keywords": ("energy drink", "caffeine", "taurine", "sports drink", "electrolyte"), "weight": 10},
    "breakfast_cereal": {"keywords": ("cereal", "flakes", "muesli", "granola", "oats", "porridge"), "weight": 10},
    "dairy": {"keywords": ("milk", "yogurt", "curd", "cheese", "paneer", "butter", "ghee"), "weight": 8},
    "juice": {"keywords": ("juice", "nectar", "fruit drink", "smoothie", "fruit juice"), "weight": 10},
    "sauce": {"keywords": ("sauce", "ketchup", "chutney", "mayonnaise", "dip", "paste"), "weight": 10},
    "bread": {"keywords": ("bread", "loaf", "bun", "pav", "croissant", "baguette"), "weight": 10},
    "sweets": {"keywords": ("sweet", "mithai", "laddu", "barfi", "halwa", "gulab jamun"), "weight": 10},
})


# Confidence thresholds
OFF_VERIFIED_CONFIDENCE = 85
HIGH_CONFIDENCE_THRESHOLD = 70
MEDIUM_CONFIDENCE_THRESHOLD = 50
OCR_OFF_CONSISTENCY_BONUS = 15
OCR_OFF_MISMATCH_PENALTY = 20

# Keywords that should never be detected as brand
BRAND_EXCLUSION_KEYWORDS = (
    "nutrition", "ingredients", "fssai", "manufactured", "marketed",
    "customer care", "email", "phone", "barcode", "mrp", "batch",
    "net wt", "net qty", "serving", "per 100g", "calories", "protein",
    "allergen", "storage", "refrigerate", "keep cool", "best before",
    "expiry", "imported", "distributed", "product of", "made in",
    "vegetarian", "non vegetarian", "nutrition facts",
)


class ProductIdentityEngine:
    
    def __init__(self):
        
        self._off_cache = TTLCache(maxsize=2000, ttl=settings.OPENFOODFACTS_CACHE_TTL)
        
        self._search_cache = TTLCache(maxsize=500, ttl=3600)
        
        self._off_url = settings.OPENFOODFACTS_URL
        
        self._user_agent = settings.OPENFOODFACTS_USER_AGENT
        
        self._client: Optional[httpx.AsyncClient] = None
    
    
    async def _get_client(self) -> httpx.AsyncClient:
        
        if self._client is None or self._client.is_closed:
            
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.OPENFOODFACTS_TIMEOUT),
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            )
        
        return self._client
    
    
    async def close(self):
        
        if self._client and not self._client.is_closed:
            
            await self._client.aclose()
            
            self._client = None
    
    
    def _is_excluded_brand_term(self, text: str) -> bool:
        """Check if text contains brand exclusion keywords"""
        text_lower = text.lower()
        for keyword in BRAND_EXCLUSION_KEYWORDS:
            if keyword in text_lower:
                return True
        return False
    
    
    def _get_largest_text_blocks(self, blocks: Optional[List[OCRBlock]], max_blocks: int = 10) -> List[OCRBlock]:
        """Extract largest text blocks by bounding box area for better product name detection"""
        if not blocks:
            return []
        
        blocks_with_area = []
        for block in blocks:
            if block.bbox and len(block.bbox) >= 4:
                bbox = block.bbox
                width = bbox[2][0] - bbox[0][0] if len(bbox) > 2 else 0
                height = bbox[2][1] - bbox[0][1] if len(bbox) > 2 else 0
                area = width * height
                blocks_with_area.append((area, block))
        
        blocks_with_area.sort(key=lambda x: x[0], reverse=True)
        
        return [block for _, block in blocks_with_area[:max_blocks]]
    
    
    def _detect_brand_from_ocr(self, text: str, off_brand: Optional[str] = None) -> Optional[str]:
        """Enhanced brand detection with OFF brand priority and exclusion filters"""
        
        # Prefer OFF brand if available (it's more reliable)
        if off_brand:
            return off_brand
        
        if not text:
            return None
        
        normalized = text.lower()
        
        brand_patterns = [
            r"brand[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
            r"by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
            r"®\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
            r"tm\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
            r"manufactured by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
            r"manufacturer\s*[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
        ]
        
        for pattern in brand_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                candidate = match.group(1).strip()
                if not self._is_excluded_brand_term(candidate):
                    return candidate
        
        # Capitalized phrase detection from top lines
        lines = text.split("\n")[:20]
        best_match = None
        best_score = 0
        
        for line in lines:
            line_clean = line.strip()
            line_lower = line_clean.lower()
            
            if len(line_lower) < 3 or len(line_lower) > 30:
                continue
            
            # Skip if contains exclusion keywords
            if self._is_excluded_brand_term(line_clean):
                continue
            
            # Check for common brand patterns (all caps or title case)
            if line_clean.isupper() and len(line_clean) > 3:
                result = line_clean.title()
                if not self._is_excluded_brand_term(result):
                    return result
            
            if line_clean.istitle() and len(line_clean) > 3:
                if not self._is_excluded_brand_term(line_clean):
                    return line_clean
        
        return best_match
    
    
    def _detect_category_weighted(self, text: str, off_categories: Optional[str] = None) -> Tuple[Optional[str], int]:
        """Enhanced category detection with OFF category priority"""
        
        # Prefer OFF category if available
        if off_categories:
            off_categories_lower = off_categories.lower()
            for category, data in CATEGORY_KEYWORDS.items():
                keywords = data.get("keywords", ())
                for keyword in keywords:
                    if keyword in off_categories_lower:
                        return category, 80
        
        if not text:
            return None, 0
        
        normalized = text.lower()
        scores = {}
        
        for category, data in CATEGORY_KEYWORDS.items():
            score = 0
            keywords = data.get("keywords", ())
            weight = data.get("weight", 10)
            
            for keyword in keywords:
                if keyword in normalized:
                    score += weight
            
            scores[category] = score
        
        if not scores:
            return None, 0
        
        best_category = max(scores, key=scores.get)
        best_score = scores[best_category]
        
        if best_score == 0:
            return None, 0
        
        return best_category, best_score
    
    
    def _detect_product_name_from_blocks(self, blocks: Optional[List[OCRBlock]], brand: Optional[str] = None) -> Optional[str]:
        """Enhanced product name detection using largest text blocks"""
        if not blocks:
            return None
        
        largest_blocks = self._get_largest_text_blocks(blocks, max_blocks=8)
        
        candidates = []
        
        for block in largest_blocks:
            text = block.text.strip()
            if not text:
                continue
            
            # Skip if too short or too long
            if len(text) < 4 or len(text) > 60:
                continue
            
            # Skip if contains typical non-product keywords
            skip_keywords = [
                "ingredient", "nutrition", "fssai", "manufactured",
                "marketed", "customer care", "email", "phone",
                "barcode", "mrp", "batch", "net wt", "net qty",
                "serving", "per 100g", "calories", "protein"
            ]
            
            text_lower = text.lower()
            if any(keyword in text_lower for keyword in skip_keywords):
                continue
            
            # Skip brand exclusion terms
            if self._is_excluded_brand_term(text):
                continue
            
            score = 0
            
            # Bonus if contains brand
            if brand and brand.lower() in text_lower:
                score += 100
            
            # Bonus for flavor indicators
            flavor_words = [
                "cream", "onion", "masala", "cheese", "chocolate", "vanilla",
                "strawberry", "mango", "orange", "lemon", "bbq", "salt", "spicy",
                "salted", "original", "classic", "magic", "sweet"
            ]
            if any(word in text_lower for word in flavor_words):
                score += 40
            
            # Bonus for reasonable length
            if 10 <= len(text) <= 40:
                score += 20
            
            # Bonus for title case (but not all caps)
            if text.istitle() and not text.isupper():
                score += 15
            
            # Higher confidence for larger blocks (likely product name)
            if hasattr(block, 'bbox') and block.bbox and len(block.bbox) >= 4:
                bbox = block.bbox
                width = bbox[2][0] - bbox[0][0] if len(bbox) > 2 else 0
                height = bbox[2][1] - bbox[0][1] if len(bbox) > 2 else 0
                area = width * height
                score += min(30, area // 5000)
            
            candidates.append((score, text))
        
        if not candidates:
            return None
        
        candidates.sort(key=lambda x: x[0], reverse=True)
        
        return candidates[0][1]
    
    
    def _detect_product_name_fallback(self, text: str, brand: Optional[str] = None) -> Optional[str]:
        """Fallback product name detection from raw text"""
        if not text:
            return None
        
        lines = [x.strip() for x in text.splitlines() if x.strip()]
        top_lines = lines[:15]
        
        candidates = []
        
        for line in top_lines:
            l = line.lower()
            
            skip_keywords = [
                "ingredient", "nutrition", "fssai", "manufactured",
                "marketed", "customer care", "email", "phone",
                "barcode", "mrp", "batch", "net wt", "net qty",
                "serving", "per 100g", "calories", "protein"
            ]
            
            if any(keyword in l for keyword in skip_keywords):
                continue
            
            if len(line) < 4 or len(line) > 60:
                continue
            
            if self._is_excluded_brand_term(line):
                continue
            
            score = 0
            
            if brand and brand.lower() in l:
                score += 100
            
            flavor_words = [
                "cream", "onion", "masala", "cheese", "chocolate", "vanilla",
                "strawberry", "mango", "orange", "lemon", "bbq", "salt", "spicy"
            ]
            if any(word in l for word in flavor_words):
                score += 40
            
            if 10 <= len(line) <= 40:
                score += 20
            
            if line.istitle() and not line.isupper():
                score += 15
            
            candidates.append((score, line))
        
        if not candidates:
            return None
        
        candidates.sort(reverse=True)
        
        return candidates[0][1]
    
    
    def _verify_ocr_off_consistency(
        self,
        ocr_text: str,
        off_product_name: Optional[str],
        off_brand: Optional[str],
    ) -> Tuple[int, float]:
        """
        Verify consistency between OCR and OpenFoodFacts data.
        Returns (consistency_score, agreement_percentage)
        """
        if not off_product_name:
            return 0, 0.0
        
        ocr_lower = ocr_text.lower() if ocr_text else ""
        
        # Check if OFF product name appears in OCR
        off_product_lower = off_product_name.lower()
        product_match_score = fuzz.partial_ratio(off_product_lower, ocr_lower) if ocr_lower else 0
        
        # Check if OFF brand appears in OCR
        brand_match_score = 0
        if off_brand:
            off_brand_lower = off_brand.lower()
            brand_match_score = fuzz.partial_ratio(off_brand_lower, ocr_lower) if ocr_lower else 0
        
        # Combined consistency score
        consistency_score = (product_match_score * 0.7) + (brand_match_score * 0.3)
        consistency_score = min(100, consistency_score)
        
        # Calculate agreement percentage
        agreement = consistency_score / 100.0
        
        return int(consistency_score), agreement
    
    
    def _detect_packaging_type(self, text: str, off_packaging: Optional[str] = None) -> PackageType:
        
        if off_packaging:
            
            off_lower = off_packaging.lower()
            
            for pkg_type, keywords in PACKAGE_TYPE_KEYWORDS.items():
                
                for keyword in keywords:
                    
                    if keyword in off_lower:
                        
                        try:
                            return PackageType(pkg_type)
                        except ValueError:
                            continue
        
        if text:
            
            normalized = text.lower()
            
            for pkg_type, keywords in PACKAGE_TYPE_KEYWORDS.items():
                
                for keyword in keywords:
                    
                    if keyword in normalized:
                        
                        try:
                            return PackageType(pkg_type)
                        except ValueError:
                            continue
        
        return PackageType.UNKNOWN
    
    
    def _extract_openfoodfacts_match(self, barcode: str, product: Dict) -> OpenFoodFactsMatch:
        
        return OpenFoodFactsMatch(
            barcode=barcode,
            found=True,
            score=95,
            source_url=f"{self._off_url}/product/{barcode}",
            product_name=product.get("product_name"),
            brand=product.get("brands") or product.get("brand"),
            image_url=product.get("image_url"),
            ingredients_text=product.get("ingredients_text"),
            nutriscore=product.get("nutriscore_grade"),
            nova_group=product.get("nova_group"),
            categories=product.get("categories"),
            countries=product.get("countries"),
            manufacturer=product.get("manufacturer") or product.get("producer"),
        )
    
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        reraise=False
    )
    async def lookup_openfoodfacts(self, barcode: str) -> Optional[OpenFoodFactsMatch]:
        
        if not barcode or not settings.ENABLE_OPENFOODFACTS:
            
            return None
        
        if barcode in self._off_cache:
            
            cached = self._off_cache[barcode]
            
            if cached:
                
                return self._extract_openfoodfacts_match(barcode, cached)
        
        try:
            
            url = f"{self._off_url}/api/v2/product/{barcode}.json"
            
            headers = {"User-Agent": self._user_agent}
            
            client = await self._get_client()
            
            response = await client.get(url, headers=headers)
            
            if response.status_code != 200:
                
                return None
            
            data = response.json()
            
            if data.get("status") != 1:
                
                return None
            
            product = data.get("product", {})
            
            self._off_cache[barcode] = product
            
            return self._extract_openfoodfacts_match(barcode, product)
        
        except Exception as e:
            
            logger.error(f"OpenFoodFacts lookup failed for {barcode}: {e}")
            
            return None
    
    
    async def search_openfoodfacts(self, query: str) -> Optional[List[Dict[str, Any]]]:
        
        if not query or not settings.ENABLE_OPENFOODFACTS:
            
            return None
        
        cache_key = query.lower()
        
        if cache_key in self._search_cache:
            
            return self._search_cache[cache_key]
        
        try:
            
            url = f"{self._off_url}/cgi/search.pl"
            
            params = {
                "search_terms": query,
                "search_simple": 1,
                "action": "process",
                "json": 1,
                "page_size": 5,
            }
            
            headers = {"User-Agent": self._user_agent}
            
            client = await self._get_client()
            
            response = await client.get(url, params=params, headers=headers)
            
            if response.status_code != 200:
                
                return None
            
            data = response.json()
            
            products = data.get("products", [])
            
            results = []
            
            for product in products[:5]:
                
                results.append({
                    "barcode": product.get("code"),
                    "product_name": product.get("product_name"),
                    "brand": product.get("brands"),
                    "image_url": product.get("image_url"),
                    "source": "openfoodfacts_search",
                })
            
            self._search_cache[cache_key] = results
            
            return results
        
        except Exception as e:
            
            logger.error(f"OpenFoodFacts search failed for {query}: {e}")
            
            return None
    
    
    async def search_and_match(self, product_name: str, brand: Optional[str] = None) -> Optional[OpenFoodFactsMatch]:
        """
        Search OpenFoodFacts by product name and find the best matching product.
        Used as fallback when barcode lookup fails.
        Now fetches full product data via barcode lookup for complete metadata.
        """
        if not product_name:
            return None
        
        search_query = product_name
        if brand:
            search_query = f"{brand} {product_name}"
        
        results = await self.search_openfoodfacts(search_query)
        
        if not results:
            return None
        
        # Score each candidate
        scored_candidates = []
        
        for candidate in results:
            candidate_name = candidate.get("product_name", "")
            candidate_brand = candidate.get("brand", "")
            candidate_barcode = candidate.get("barcode", "")
            
            if not candidate_name:
                continue
            
            name_score = fuzz.token_set_ratio(product_name.lower(), candidate_name.lower())
            
            brand_score = 0
            if brand and candidate_brand:
                brand_score = fuzz.partial_ratio(brand.lower(), candidate_brand.lower())
            
            total_score = name_score * 0.7 + brand_score * 0.3
            
            scored_candidates.append((total_score, candidate_barcode, candidate_name, candidate_brand))
        
        if not scored_candidates:
            return None
        
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        
        best_score, best_barcode, best_name, best_brand = scored_candidates[0]
        
        if best_score < 60:  # Threshold for accepting search result
            return None
        
        # Fetch full product data using the barcode
        if best_barcode:
            full_match = await self.lookup_openfoodfacts(best_barcode)
            if full_match and full_match.found:
                logger.info(f"Found full product via search fallback: {product_name} -> {full_match.product_name}")
                return full_match
        
        # Fallback to minimal match if full lookup fails
        logger.info(f"Found minimal match via search fallback: {product_name} -> {best_name}")
        return OpenFoodFactsMatch(
            barcode=best_barcode,
            found=True,
            score=int(best_score),
            source_url=f"{self._off_url}/product/{best_barcode}" if best_barcode else None,
            product_name=best_name,
            brand=best_brand,
            image_url=None,
            ingredients_text=None,
            nutriscore=None,
            nova_group=None,
            categories=None,
            countries=None,
            manufacturer=None,
        )
    
    
    def _calculate_identity_confidence(
        self,
        off_match: Optional[OpenFoodFactsMatch],
        brand: Optional[str],
        category: Optional[str],
        barcode_valid: bool,
        ocr_quality_score: int,
        brand_match_score: int = 0,
        category_match_score: int = 0,
        consistency_score: int = 0,
        agreement_percentage: float = 0.0,
    ) -> int:
        
        score = 0
        
        # Barcode validity (35 points)
        if barcode_valid:
            score += 35
        
        # OpenFoodFacts match (35 points)
        if off_match and off_match.found:
            score += 35
        
        # Brand detection with match score (15 points)
        if brand:
            # Higher match score = more points
            brand_points = min(15, brand_match_score // 7)
            score += brand_points
        
        # Category detection with match score (10 points)
        if category:
            category_points = min(10, category_match_score // 10)
            score += category_points
        
        # OCR quality (5 points)
        score += min(5, ocr_quality_score // 20)
        
        # OCR-OFF consistency bonus or penalty (only if OFF exists)
        if off_match and off_match.found:
            if consistency_score >= 70:
                # High consistency: bonus
                score += OCR_OFF_CONSISTENCY_BONUS
            elif consistency_score <= 30:
                # Low consistency: penalty
                score -= OCR_OFF_MISMATCH_PENALTY
        
        return max(0, min(100, score))
    
    
    def _fuse_product_identity(
        self,
        off_match: Optional[OpenFoodFactsMatch],
        ocr_brand: Optional[str],
        ocr_category: Optional[str],
        ocr_product_name: Optional[str],
        barcode_valid: bool,
        ocr_quality_score: int,
        consistency_score: int = 0,
        brand_match_score: int = 0,
        category_match_score: int = 0,
    ) -> Tuple[ProductFusionResult, List[str]]:
        
        barcode_confidence = 35 if barcode_valid else 0
        
        off_confidence = 35 if off_match and off_match.found else 0
        
        ocr_confidence = 0
        
        matched_by = []
        
        if ocr_brand or ocr_category or ocr_product_name:
            
            ocr_confidence = 20 + (ocr_quality_score // 10)
            
            ocr_confidence = min(30, ocr_confidence)
        
        # Determine selected source based on consistency
        if off_match and off_match.found:
            if consistency_score >= 70:
                # High consistency: trust OFF
                selected_source = ProductSource.OPENFOODFACTS
                matched_by.append("openfoodfacts_verified")
            elif consistency_score >= 40:
                # Medium consistency: use both
                selected_source = ProductSource.OPENFOODFACTS
                matched_by.append("openfoodfacts_with_ocr")
            else:
                # Low consistency: prefer OCR
                selected_source = ProductSource.OCR
                matched_by.append("ocr_over_off")
            matched_by.append("openfoodfacts")
        
        elif barcode_valid:
            
            selected_source = ProductSource.OCR
            
            matched_by.append("barcode")
        
        elif ocr_product_name:
            
            selected_source = ProductSource.OCR
            
            matched_by.append("ocr")
        
        else:
            
            selected_source = ProductSource.UNKNOWN
        
        if barcode_valid:
            
            matched_by.append("barcode_valid")
        
        if ocr_brand:
            
            matched_by.append("ocr_brand")
        
        if ocr_category:
            
            matched_by.append("ocr_category")
        
        if ocr_product_name:
            
            matched_by.append("ocr_product_name")
        
        # Calculate final confidence with all match scores
        final_confidence = self._calculate_identity_confidence(
            off_match=off_match,
            brand=ocr_brand,
            category=ocr_category,
            barcode_valid=barcode_valid,
            ocr_quality_score=ocr_quality_score,
            brand_match_score=brand_match_score,
            category_match_score=category_match_score,
            consistency_score=consistency_score,
            agreement_percentage=0.0,
        )
        
        fusion_result = ProductFusionResult(
            barcode_confidence=barcode_confidence,
            ocr_confidence=ocr_confidence,
            off_confidence=off_confidence,
            final_confidence=final_confidence,
            selected_source=selected_source,
        )
        
        return fusion_result, matched_by
    
    
    async def build_product_identity(
        self,
        barcode_result: BarcodeResult,
        ocr_text: str,
        off_data: Optional[OpenFoodFactsMatch],
        ocr_blocks: Optional[List[OCRBlock]] = None,
        ocr_quality_score: int = 50,
    ) -> Tuple[ProductIdentity, ProductFusionResult, List[str]]:
        
        product_name = None
        brand = None
        category = None
        category_confidence = 0
        consistency_score = 0
        agreement_percentage = 0.0
        image_url = None
        manufacturer = None
        
        # Try OFF search fallback if direct lookup failed but we have OCR product name
        if not off_data or not off_data.found:
            # Try to extract product name first
            temp_product_name = self._detect_product_name_from_blocks(ocr_blocks, None)
            if not temp_product_name:
                temp_product_name = self._detect_product_name_fallback(ocr_text, None)
            
            if temp_product_name:
                off_search_result = await self.search_and_match(temp_product_name, None)
                if off_search_result:
                    off_data = off_search_result
                    logger.info(f"Found product via search fallback: {temp_product_name} -> {off_data.product_name}")
        
        if off_data and off_data.found:
            # Verify OCR-OFF consistency
            consistency_score, agreement_percentage = self._verify_ocr_off_consistency(
                ocr_text,
                off_data.product_name,
                off_data.brand,
            )
            
            product_name = off_data.product_name
            brand = off_data.brand
            category = off_data.categories
            image_url = off_data.image_url
            manufacturer = off_data.manufacturer
            
            if category:
                category = category.split(",")[0].strip()
        
        # Detect from OCR (may override or fill gaps)
        ocr_brand = self._detect_brand_from_ocr(ocr_text, brand if not brand else None)
        detected_category, category_confidence = self._detect_category_weighted(ocr_text, off_data.categories if off_data else None)
        
        # Use OCR brand if no brand from OFF
        if not brand and ocr_brand:
            brand = ocr_brand
        
        # Use OCR category if no category from OFF or low confidence
        if not category and detected_category:
            category = detected_category
        elif category and detected_category and category_confidence > 60:
            # Both available, use OFF but keep OCR for matching
            pass
        
        # Detect product name from OCR blocks (preferred) or fallback
        ocr_product_name = self._detect_product_name_from_blocks(ocr_blocks, brand)
        if not ocr_product_name:
            ocr_product_name = self._detect_product_name_fallback(ocr_text, brand)
        
        # Use OCR product name if no product name from OFF
        if not product_name and ocr_product_name:
            product_name = ocr_product_name
        
        # Calculate match scores
        brand_match_score = 0
        if off_data and off_data.brand and ocr_brand:
            brand_match_score = fuzz.token_set_ratio(
                ocr_brand.lower(),
                off_data.brand.lower(),
            )
        
        category_match_score = category_confidence
        
        barcode_valid = barcode_result.is_valid
        
        # Pass all match scores to fusion
        fusion_result, matched_by = self._fuse_product_identity(
            off_match=off_data,
            ocr_brand=ocr_brand,
            ocr_category=detected_category,
            ocr_product_name=ocr_product_name,
            barcode_valid=barcode_valid,
            ocr_quality_score=ocr_quality_score,
            consistency_score=consistency_score,
            brand_match_score=brand_match_score,
            category_match_score=category_match_score,
        )
        
        # Final brand selection (prefer OFF if high consistency)
        if off_data and off_data.brand and consistency_score >= 60:
            final_brand = off_data.brand
        elif ocr_brand:
            final_brand = ocr_brand
        else:
            final_brand = None
        
        # Final category selection
        if category:
            final_category = category
        elif detected_category:
            final_category = detected_category
        else:
            final_category = None
        
        # Final product name selection
        if off_data and off_data.product_name and consistency_score >= 60:
            final_product_name = off_data.product_name
        elif product_name:
            final_product_name = product_name
        elif ocr_product_name:
            final_product_name = ocr_product_name
        else:
            final_product_name = None
        
        product_identity = ProductIdentity(
            product_name=final_product_name,
            brand=final_brand,
            category=final_category,
            barcode=barcode_result.barcode,
            image_url=image_url,
            manufacturer=manufacturer,
            country=barcode_result.market,
            identity_confidence=fusion_result.final_confidence,
            matched_by=matched_by,
            source=fusion_result.selected_source,
            fusion=fusion_result,
        )
        
        return product_identity, fusion_result, matched_by
    
    def detect_packaging_type(
        self,
        text: str,
        off_categories: Optional[str] = None,
    ) -> PackageType:
        """
        Public wrapper for packaging type detection.
        """
        return self._detect_packaging_type(text, off_categories)
    
    
    async def build_product_passport(
        self,
        product_identity: ProductIdentity,
        barcode_result: BarcodeResult,
        off_data: Optional[OpenFoodFactsMatch],
        packaging_type: PackageType,
    ) -> ProductPassport:
        
        if product_identity.identity_confidence >= OFF_VERIFIED_CONFIDENCE:
            
            verification_status = VerificationLevel.VERIFIED
        
        elif product_identity.identity_confidence >= HIGH_CONFIDENCE_THRESHOLD:
            
            verification_status = VerificationLevel.HIGH
        
        elif product_identity.identity_confidence >= MEDIUM_CONFIDENCE_THRESHOLD:
            
            verification_status = VerificationLevel.MEDIUM
        
        else:
            
            verification_status = VerificationLevel.LOW
        
        return ProductPassport(
            brand=product_identity.brand,
            country=product_identity.country or barcode_result.market,
            market_flag=barcode_result.market_flag,
            barcode=product_identity.barcode,
            category=product_identity.category,
            package_type=packaging_type,
            manufacturer=product_identity.manufacturer,
            verification_status=verification_status,
        )


# ==========================================================
# SINGLETON
# ==========================================================


product_identity_engine = ProductIdentityEngine()


# ==========================================================
# END OF FILE
# ==========================================================