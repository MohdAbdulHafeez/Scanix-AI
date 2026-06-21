# ==========================================================
# SCANIX AI - SYSTEM 1 SCHEMAS
# ==========================================================
# Production-grade Pydantic models for all scanning operations.
# Strict typing, validation, and OpenAPI schema generation.
# Aligned with all frozen engines and scan service.
# ==========================================================

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Union
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


# ==========================================================
# ENUMS
# ==========================================================

class VerificationLevel(str, Enum):
    VERIFIED = "verified"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    FAILED = "failed"


class Grade(str, Enum):
    A_PLUS = "A+"
    A = "A"
    A_MINUS = "A-"
    B_PLUS = "B+"
    B = "B"
    B_MINUS = "B-"
    C_PLUS = "C+"
    C = "C"
    D = "D"
    F = "F"


class TrafficLight(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class ProductSource(str, Enum):
    OPENFOODFACTS = "openfoodfacts"
    OCR = "ocr"
    BARCODE = "barcode"
    FUSION = "fusion"
    UNKNOWN = "unknown"


class DetectionSource(str, Enum):
    IMAGE = "image"
    TEXT = "text"
    MANUAL = "manual"
    NONE = "none"


class PackageType(str, Enum):
    BOTTLE = "bottle"
    CAN = "can"
    JAR = "jar"
    BOX = "box"
    POUCH = "pouch"
    PACKET = "packet"
    TUB = "tub"
    BAG = "bag"
    TRAY = "tray"
    CUP = "cup"
    UNKNOWN = "unknown"


class RecommendationType(str, Enum):
    RECOMMENDED = "recommended"
    OCCASIONAL = "occasional"
    LIMITED = "limited"
    AVOID = "avoid"
    UNKNOWN = "unknown"


class ScanSource(str, Enum):
    IMAGE_CAPTURE = "image_capture"
    MANUAL_BARCODE = "manual_barcode"
    BULK_UPLOAD = "bulk_upload"
    API = "api"


class APIVersion(str, Enum):
    V1 = "v1"


# ==========================================================
# CORE MODELS
# ==========================================================

class OCRBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    text: str
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: List[List[float]] = Field(default_factory=list)


class OCRResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    extracted_text: str = ""
    raw_text: str = ""
    blocks: List[OCRBlock] = Field(default_factory=list)
    average_confidence: float = 0.0
    text_density_score: int = 0
    readability_score: int = 0
    ocr_quality_score: int = 0
    ocr_provider: str = "none"
    processing_time_ms: int = 0
    detected_sections: Dict[str, Any] = Field(default_factory=dict)
    nutrition_data: Dict[str, Any] = Field(default_factory=dict)
    orientation_corrected: Optional[int] = None
    images_processed: Optional[int] = None


class BarcodeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    barcode: Optional[str] = None
    barcode_type: Optional[str] = None
    is_valid: bool = False
    confidence: int = 0
    market: Optional[str] = None
    market_flag: Optional[str] = None
    detected_from: DetectionSource = DetectionSource.NONE
    prefix_country: Optional[str] = None


class ImageQualityResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    overall_score: int = 0
    blur_score: int = 0
    brightness_score: int = 0
    contrast_score: int = 0
    glare_score: int = 0
    lighting_score: int = 0
    sharpness_score: int = 0
    recommendation: str = ""


class OpenFoodFactsMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    barcode: str
    found: bool = True
    score: int = 0
    source_url: Optional[str] = None
    product_name: Optional[str] = None
    brand: Optional[str] = None
    image_url: Optional[str] = None
    ingredients_text: Optional[str] = None
    nutriscore: Optional[str] = None
    nova_group: Optional[int] = None
    categories: Optional[str] = None
    countries: Optional[str] = None
    manufacturer: Optional[str] = None


# ==========================================================
# INGREDIENT MODELS
# ==========================================================

class IngredientItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    name: str
    confidence: float = 1.0
    source: str = "ocr"


class IngredientSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    ingredients: List[IngredientItem] = Field(default_factory=list)
    ingredient_count: int = 0
    e_numbers: List[Dict[str, Any]] = Field(default_factory=list)
    basic_allergens: List[str] = Field(default_factory=list)
    has_ingredients_section: bool = False
    ingredient_visibility_score: int = 0


# ==========================================================
# NUTRITION MODELS
# ==========================================================

class NutritionData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    nutrition_detected: bool = False
    nutrition_completeness: int = 0
    nutrition_confidence: int = 0
    
    protein: float = 0.0
    fat: float = 0.0
    saturated_fat: float = 0.0
    sugar: float = 0.0
    sodium: float = 0.0
    carbohydrates: float = 0.0
    fiber: float = 0.0
    calories: float = 0.0
    
    serving_size_g: float = 100.0
    is_per_serving: bool = False
    missing_fields: List[str] = Field(default_factory=list)
    
    sugar_traffic_light: TrafficLight = TrafficLight.GREEN
    fat_traffic_light: TrafficLight = TrafficLight.GREEN
    saturated_fat_traffic_light: TrafficLight = TrafficLight.GREEN
    sodium_traffic_light: TrafficLight = TrafficLight.GREEN
    added_sugar_traffic_light: Optional[TrafficLight] = None


# ==========================================================
# PRODUCT IDENTITY MODELS
# ==========================================================

class ProductFusionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    barcode_confidence: int = 0
    ocr_confidence: int = 0
    off_confidence: int = 0
    final_confidence: int = 0
    selected_source: ProductSource = ProductSource.UNKNOWN
    identity_consistency: int = 0


class ProductIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    product_name: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    barcode: Optional[str] = None
    image_url: Optional[str] = None
    manufacturer: Optional[str] = None
    country: Optional[str] = None
    identity_confidence: int = 0
    matched_by: List[str] = Field(default_factory=list)
    source: ProductSource = ProductSource.UNKNOWN
    fusion: Optional[ProductFusionResult] = None


class ProductPassport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    brand: Optional[str] = None
    country: Optional[str] = None
    market_flag: Optional[str] = None
    barcode: Optional[str] = None
    category: Optional[str] = None
    package_type: PackageType = PackageType.UNKNOWN
    manufacturer: Optional[str] = None
    verification_status: VerificationLevel = VerificationLevel.LOW


# ==========================================================
# TRUST & VERIFICATION MODELS
# ==========================================================

class ConfidenceBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    barcode_match: int = 0
    ocr_match: int = 0
    brand_match: int = 0
    database_match: int = 0


class ScanixScoreBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    ocr_confidence: int = 0
    barcode_confidence: int = 0
    off_match: int = 0
    data_completeness: int = 0
    verification_level: int = 0


class ScanixScore(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    score: int = 0
    grade: Grade = Grade.F
    breakdown: ScanixScoreBreakdown = Field(default_factory=ScanixScoreBreakdown)


class EvidenceSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    name: str
    confidence: int
    data_found: List[str] = Field(default_factory=list)


class EvidencePanel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    sources: List[EvidenceSource] = Field(default_factory=list)
    total_sources: int = 0
    verified_count: int = 0


class VerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    barcode_verified: bool = False
    ocr_verified: bool = False
    source_verified: bool = False
    verification_level: VerificationLevel = VerificationLevel.LOW
    trust_score: int = 0
    reliability_score: int = 0
    source_reliability: int = 0
    evidence_strength: int = 0
    data_confidence: int = 0


# ==========================================================
# ELITE FEATURES MODELS
# ==========================================================

class RadarCompleteness(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    product_name: int = 0
    brand: int = 0
    ingredients: int = 0
    nutrition: int = 0
    barcode: int = 0
    images: int = 0


class LabelIntelligenceMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    lighting: int = 0
    sharpness: int = 0
    readability: int = 0
    coverage: int = 0
    contrast: int = 0
    perspective: int = 0


class LabelIntelligence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    overall: str = "Unknown"
    metrics: LabelIntelligenceMetrics = Field(default_factory=LabelIntelligenceMetrics)


class HealthDashboardCard(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    name: str
    score: int
    grade: Grade = Grade.F


class HealthDashboard(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    health_score: HealthDashboardCard
    trust_score: HealthDashboardCard
    reliability_score: HealthDashboardCard
    verification_score: HealthDashboardCard


class IngredientVisibilityScore(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    score: int = 0
    ingredients_found: bool = False
    ingredients_readable: bool = False
    nutrition_complete: bool = False


class MissingDataDetector(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    missing_fields: List[str] = Field(default_factory=list)
    has_missing_data: bool = False
    completeness_percentage: int = 0


class OCRHeatmapBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    text: str
    confidence: float
    bbox: List[List[float]]


class EliteFeatures(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    scanix_intelligence_score: ScanixScore
    product_reliability_meter: int
    radar_completeness: RadarCompleteness
    label_intelligence: LabelIntelligence
    multi_source_verification: EvidencePanel
    confidence_breakdown: ConfidenceBreakdown
    product_passport: ProductPassport
    evidence_panel: EvidencePanel
    health_dashboard: HealthDashboard
    ingredient_visibility_score: IngredientVisibilityScore
    missing_data_detector: MissingDataDetector
    packaging_type: PackageType
    ocr_heatmap: List[OCRHeatmapBlock] = Field(default_factory=list)


# ==========================================================
# SCAN REPORT MODELS
# ==========================================================

class AuditTrail(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    ocr_raw: str = ""
    ocr_corrected: str = ""


class ScanMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    scan_id: str
    source: ScanSource
    processing_time_ms: int = 0
    fallback_used: Optional[str] = None
    api_version: APIVersion = APIVersion.V1
    audit_trail: AuditTrail = Field(default_factory=AuditTrail)


class ScanQuality(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    coverage_score: int = 0
    completeness_score: int = 0
    image_quality_score: int = 0
    scan_quality_score: int = 0
    scan_reliability_score: int = 0


class RecommendationInsight(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    recommendation: RecommendationType = RecommendationType.UNKNOWN
    reason: str = ""
    best_for: List[str] = Field(default_factory=list)


class ScanReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    success: bool = True
    metadata: ScanMetadata
    product: ProductIdentity
    ocr: OCRResult
    barcode: BarcodeResult
    image_quality: ImageQualityResult
    nutrition: NutritionData
    ingredients: IngredientSummary
    verification: VerificationResult
    recommendation: RecommendationInsight
    scan_quality: ScanQuality
    off_match: Optional[OpenFoodFactsMatch] = None
    elite: EliteFeatures
    warnings: List[str] = Field(default_factory=list)
    hash: str = ""


# ==========================================================
# HEALTH CHECK MODELS
# ==========================================================

class HealthCheckResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    status: str
    version: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    services: Dict[str, bool] = Field(default_factory=dict)


# ==========================================================
# END OF FILE
# ==========================================================