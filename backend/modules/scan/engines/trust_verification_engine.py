# ==========================================================
# SCANIX AI
# SYSTEM 1 - TRUST & VERIFICATION ENGINE
# Calculates trust scores, verification levels, and elite confidence metrics
# Features: Immutable weights, Strict Enum casting, Schema alignment
# Identity consistency integration, confidence ranges
# ==========================================================


from types import MappingProxyType
from typing import List

from core.logging import get_logger

from modules.scan.schemas import ConfidenceBreakdown
from modules.scan.schemas import EvidencePanel
from modules.scan.schemas import EvidenceSource
from modules.scan.schemas import Grade
from modules.scan.schemas import ScanixScore
from modules.scan.schemas import ScanixScoreBreakdown
from modules.scan.schemas import VerificationLevel
from modules.scan.schemas import VerificationResult


logger = get_logger(__name__)


# ==========================================================
# SCORING WEIGHTS (Immutable)
# ==========================================================


SOURCE_RELIABILITY_MAP = MappingProxyType({
    "openfoodfacts": 95,
    "barcode": 80,
    "fusion": 90,
    "ocr": 65,
})


EVIDENCE_WEIGHTS = MappingProxyType({
    "barcode": 30,
    "openfoodfacts": 35,
    "ocr": 15,
    "fusion": 20,
    "nutrition": 10,
    "ingredients": 10,
})


TRUST_BADGE_THRESHOLDS = MappingProxyType({
    "PLATINUM": 95,
    "GOLD": 85,
    "SILVER": 75,
    "BRONZE": 65,
})


# Confidence thresholds for verification levels
VERIFICATION_THRESHOLDS = MappingProxyType({
    "HIGH_OCR": 85,
    "MEDIUM_OCR": 70,
    "HIGH_OFF": 90,
    "MEDIUM_OFF": 70,
})


class TrustVerificationEngine:
    
    def calculate_trust_score(
        self,
        source_reliability: int,
        data_confidence: int,
        evidence_strength: int,
        identity_consistency: int = 0,
    ) -> int:
        
        # New weights: source (15%), data confidence (35%), evidence (20%), consistency (30%)
        score = int(
            source_reliability * 0.15 +
            data_confidence * 0.35 +
            evidence_strength * 0.20 +
            identity_consistency * 0.30
        )
        
        return max(0, min(100, score))
    
    
    def calculate_reliability_score(
        self,
        barcode_valid: bool,
        off_data_found: bool,
        ocr_confidence: float,
        has_nutrition: bool,
        has_ingredients: bool,
    ) -> int:
        
        score = 0
        
        if barcode_valid:
            
            score += 25
        
        if off_data_found:
            
            score += 35
        
        # Use confidence ranges instead of binary
        if ocr_confidence > 0.85:
            
            score += 20
        
        elif ocr_confidence > 0.70:
            
            score += 15
        
        elif ocr_confidence > 0.60:
            
            score += 10
        
        elif ocr_confidence > 0.40:
            
            score += 5
        
        if has_nutrition:
            
            score += 12
        
        if has_ingredients:
            
            score += 8
        
        return min(100, score)
    
    
    def get_grade(self, score: int) -> Grade:
        """
        Grade mapping with proper A+ through F scale.
        A+: 95-100
        A: 90-94
        A-: 85-89
        B+: 80-84
        B: 75-79
        B-: 70-74
        C+: 65-69
        C: 60-64
        D: 50-59
        F: 0-49
        """
        if score >= 95:
            return Grade.A_PLUS
        
        if score >= 90:
            return Grade.A
        
        if score >= 85:
            # Map to A_MINUS if available, otherwise B
            try:
                return Grade.A_MINUS
            except AttributeError:
                return Grade.A
        
        if score >= 80:
            # Map to B_PLUS if available, otherwise B
            try:
                return Grade.B_PLUS
            except AttributeError:
                return Grade.B
        
        if score >= 75:
            return Grade.B
        
        if score >= 70:
            # Map to B_MINUS if available, otherwise C_PLUS
            try:
                return Grade.B_MINUS
            except AttributeError:
                return Grade.C_PLUS
        
        if score >= 65:
            # Map to C_PLUS if available, otherwise C
            try:
                return Grade.C_PLUS
            except AttributeError:
                return Grade.C
        
        if score >= 60:
            return Grade.C
        
        if score >= 50:
            return Grade.D
        
        return Grade.F
    
    
    def get_reliability_status(self, reliability_score: int) -> str:
        
        if reliability_score >= 90:
            
            return "Excellent"
        
        if reliability_score >= 75:
            
            return "Good"
        
        if reliability_score >= 60:
            
            return "Fair"
        
        if reliability_score >= 40:
            
            return "Poor"
        
        return "Very Poor"
    
    
    def get_trust_badge(self, trust_score: int) -> str:
        
        for badge, threshold in TRUST_BADGE_THRESHOLDS.items():
            
            if trust_score >= threshold:
                
                return badge
        
        return "BRONZE"
    
    
    def calculate_verification_score(self, verification_level: VerificationLevel) -> int:
        
        level_scores = {
            VerificationLevel.VERIFIED: 100,
            VerificationLevel.HIGH: 85,
            VerificationLevel.MEDIUM: 60,
            VerificationLevel.LOW: 35,
        }
        
        return level_scores.get(verification_level, 35)
    
    
    def calculate_verification_level(
        self,
        barcode_verified: bool,
        ocr_verified: bool,
        source_verified: bool,
        barcode_confidence: int = 0,
        ocr_confidence: float = 0.0,
        off_confidence: int = 0,
    ) -> VerificationLevel:
        """
        Calculate verification level using confidence ranges instead of binary flags.
        """
        # Calculate weighted confidence score
        confidence_score = 0
        total_weight = 0
        
        if barcode_verified:
            barcode_weight = 40
            barcode_contrib = (barcode_confidence if barcode_confidence > 0 else 80) * (barcode_weight / 100)
            confidence_score += barcode_contrib
            total_weight += barcode_weight
        
        if source_verified:
            off_weight = 35
            off_contrib = (off_confidence if off_confidence > 0 else 85) * (off_weight / 100)
            confidence_score += off_contrib
            total_weight += off_weight
        
        if ocr_verified:
            ocr_weight = 25
            ocr_contrib = int(ocr_confidence * 100) * (ocr_weight / 100)
            confidence_score += ocr_contrib
            total_weight += ocr_weight
        
        if total_weight == 0:
            return VerificationLevel.LOW
        
        final_confidence = confidence_score
        
        if final_confidence >= 85:
            return VerificationLevel.VERIFIED
        
        if final_confidence >= 70:
            return VerificationLevel.HIGH
        
        if final_confidence >= 45:
            return VerificationLevel.MEDIUM
        
        return VerificationLevel.LOW
    
    
    def calculate_confidence_breakdown(
        self,
        barcode_confidence: int,
        ocr_confidence: int,
        brand_confidence: int,
        database_confidence: int,
    ) -> ConfidenceBreakdown:
        
        return ConfidenceBreakdown(
            barcode_match=barcode_confidence,
            ocr_match=ocr_confidence,
            brand_match=brand_confidence,
            database_match=database_confidence,
        )
    
    
    def calculate_overall_confidence(self, breakdown: ConfidenceBreakdown) -> int:
        
        weights = {
            "barcode_match": 0.35,
            "database_match": 0.35,
            "brand_match": 0.15,
            "ocr_match": 0.15,
        }
        
        total = 0
        
        total += breakdown.barcode_match * weights["barcode_match"]
        
        total += breakdown.database_match * weights["database_match"]
        
        total += breakdown.brand_match * weights["brand_match"]
        
        total += breakdown.ocr_match * weights["ocr_match"]
        
        return int(total)
    
    
    def calculate_scanix_score(
        self,
        ocr_confidence: float,
        barcode_confidence: int,
        off_match_confidence: int,
        data_completeness: int,
        verification_level: VerificationLevel,
    ) -> ScanixScore:
        
        ocr_score = int(ocr_confidence * 100)
        
        verification_score = self.calculate_verification_score(verification_level)
        
        weighted_score = int(
            ocr_score * 0.25 +
            barcode_confidence * 0.25 +
            off_match_confidence * 0.25 +
            data_completeness * 0.15 +
            verification_score * 0.10
        )
        
        final_score = max(0, min(100, weighted_score))
        
        grade = self.get_grade(final_score)
        
        breakdown = ScanixScoreBreakdown(
            ocr_confidence=ocr_score,
            barcode_confidence=barcode_confidence,
            off_match=off_match_confidence,
            data_completeness=data_completeness,
            verification_level=verification_score,
        )
        
        return ScanixScore(
            score=final_score,
            grade=grade,
            breakdown=breakdown,
        )
    
    
    def calculate_evidence_strength(self, matched_by: List[str]) -> int:
        """
        Calculate evidence strength with deduplication.
        Prevents multiple matches from the same category inflating score.
        """
        total_weight = 0
        categories_found = set()
        
        for evidence in matched_by:
            evidence_lower = evidence.lower()
            
            # Map evidence to categories
            category = None
            for key, weight in EVIDENCE_WEIGHTS.items():
                if key in evidence_lower:
                    category = key
                    break
            
            if category and category not in categories_found:
                categories_found.add(category)
                total_weight += EVIDENCE_WEIGHTS.get(category, 0)
        
        return min(100, total_weight)
    
    
    def get_source_reliability(self, source: str, confidence: int = 0) -> int:
        """
        Get source reliability with dynamic adjustment based on confidence.
        Higher confidence OCR can override static OCR reliability.
        """
        base_reliability = SOURCE_RELIABILITY_MAP.get(source, 50)
        
        # Dynamic adjustment for OCR based on confidence
        if source == "ocr" and confidence > 0:
            if confidence >= 85:
                return min(95, base_reliability + 20)
            elif confidence >= 70:
                return min(90, base_reliability + 10)
        
        # Dynamic adjustment for OpenFoodFacts based on confidence
        if source == "openfoodfacts" and confidence > 0:
            if confidence >= 90:
                return min(98, base_reliability + 3)
            elif confidence <= 50:
                return max(60, base_reliability - 20)
        
        return base_reliability
    
    
    def get_verification_reasons(
        self,
        barcode_verified: bool,
        ocr_verified: bool,
        source_verified: bool,
        fusion_used: bool,
        identity_consistent: bool = False,
    ) -> List[str]:
        
        reasons = []
        
        if barcode_verified:
            
            reasons.append("Barcode verified")
        
        if source_verified:
            
            reasons.append("OpenFoodFacts matched")
        
        if ocr_verified:
            
            reasons.append("OCR confidence high")
        
        if fusion_used:
            
            reasons.append("Product fusion applied")
        
        if identity_consistent:
            
            reasons.append("OCR-OFF identity consistent")
        
        if not reasons:
            
            reasons.append("Limited verification available")
        
        return reasons
    
    
    def build_evidence_panel(
        self,
        barcode_found: bool,
        barcode_confidence: int,
        off_found: bool,
        off_confidence: int,
        ocr_confidence: int,
        fusion_used: bool,
        fusion_confidence: int = 85,
        identity_consistency: int = 0,
    ) -> EvidencePanel:
        
        sources = []
        
        sources.append(EvidenceSource(
            name="Barcode",
            confidence=barcode_confidence if barcode_found else 0,
            data_found=["barcode"] if barcode_found else [],
        ))
        
        sources.append(EvidenceSource(
            name="OpenFoodFacts",
            confidence=off_confidence if off_found else 0,
            data_found=["product_name", "brand", "nutrition"] if off_found else [],
        ))
        
        sources.append(EvidenceSource(
            name="OCR",
            confidence=ocr_confidence,
            data_found=["text_extraction"] if ocr_confidence > 50 else [],
        ))
        
        if fusion_used:
            
            sources.append(EvidenceSource(
                name="Product Fusion",
                confidence=fusion_confidence,
                data_found=["merged_data", "confidence_scoring"],
            ))
        
        if identity_consistency > 0:
            sources.append(EvidenceSource(
                name="Identity Consistency",
                confidence=identity_consistency,
                data_found=["brand_match", "product_name_match", "category_match"],
            ))
        
        verified_count = sum(1 for s in sources if s.confidence >= 70)
        
        return EvidencePanel(
            sources=sources,
            total_sources=len(sources),
            verified_count=verified_count,
        )
    
    
    def build_verification_result(
        self,
        barcode_valid: bool,
        ocr_confidence: float,
        off_data_found: bool,
        matched_by: List[str],
        has_nutrition: bool,
        has_ingredients: bool,
        fusion_used: bool = False,
        ocr_threshold: float = 0.70,
        barcode_confidence: int = 0,
        off_confidence: int = 0,
        identity_consistency: int = 0,
    ) -> VerificationResult:
        
        barcode_verified = barcode_valid
        
        ocr_verified = ocr_confidence >= ocr_threshold
        
        source_verified = off_data_found
        
        verification_level = self.calculate_verification_level(
            barcode_verified,
            ocr_verified,
            source_verified,
            barcode_confidence,
            ocr_confidence,
            off_confidence,
        )
        
        # Get source reliability with confidence-based adjustment
        source_reliability = self.get_source_reliability(
            "openfoodfacts" if off_data_found else "barcode" if barcode_valid else "ocr",
            off_confidence if off_data_found else (barcode_confidence if barcode_valid else int(ocr_confidence * 100))
        )
        
        data_confidence = int(ocr_confidence * 100) if ocr_confidence > 0 else 50
        
        if barcode_valid:
            
            data_confidence += 10
        
        if off_data_found:
            
            data_confidence += 10
        
        data_confidence = min(100, data_confidence)
        
        evidence_strength = self.calculate_evidence_strength(matched_by)
        
        trust_score = self.calculate_trust_score(
            source_reliability,
            data_confidence,
            evidence_strength,
            identity_consistency,
        )
        
        reliability_score = self.calculate_reliability_score(
            barcode_valid,
            off_data_found,
            ocr_confidence,
            has_nutrition,
            has_ingredients,
        )
        
        return VerificationResult(
            barcode_verified=barcode_verified,
            ocr_verified=ocr_verified,
            source_verified=source_verified,
            verification_level=verification_level,
            trust_score=trust_score,
            reliability_score=reliability_score,
            source_reliability=source_reliability,
            evidence_strength=evidence_strength,
            data_confidence=data_confidence,
        )


# ==========================================================
# SINGLETON
# ==========================================================


trust_verification_engine = TrustVerificationEngine()


# ==========================================================
# END OF FILE
# ==========================================================