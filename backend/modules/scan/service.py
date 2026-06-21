# ==========================================================
# SCANIX AI
# SYSTEM 1 - SCAN SERVICE
# Orchestrates all engines for the master Scan Report
# Features: Async orchestration, strict schema mapping, trace logging
# ==========================================================

import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_scan_logger
from core.exceptions import ScanProcessingError

from modules.scan.constants import SCAN_SYSTEM_NAME, SCAN_SYSTEM_VERSION
from modules.scan.schemas import (
    APIVersion, AuditTrail, BarcodeResult, DetectionSource, EliteFeatures, HealthDashboard,
    HealthDashboardCard, ImageQualityResult, IngredientSummary,
    IngredientVisibilityScore, LabelIntelligence, LabelIntelligenceMetrics,
    MissingDataDetector, NutritionData, OCRResult,
    OpenFoodFactsMatch, RadarCompleteness, RecommendationInsight,
    RecommendationType, ScanMetadata, ScanQuality, ScanReport, ScanSource,
    ScanixScore
)

# Import Engines
from modules.scan.engines.barcode_engine import barcode_engine
from modules.scan.engines.image_quality_engine import image_quality_engine
from modules.scan.engines.ingredient_base_engine import ingredient_base_engine
from modules.scan.engines.nutrition_engine import nutrition_engine
from modules.scan.engines.ocr_engine import ocr_engine
from modules.scan.engines.product_identity_engine import product_identity_engine
from modules.scan.engines.trust_verification_engine import trust_verification_engine


class ScanService:
    
    @staticmethod
    def _generate_report_hash(metadata_id: str, timestamp: str) -> str:
        raw_string = f"{metadata_id}_{timestamp}_{SCAN_SYSTEM_VERSION}"
        return hashlib.sha256(raw_string.encode("utf-8")).hexdigest()
    
    @staticmethod
    def _calculate_health_score(nutrition_data: NutritionData) -> int:
        """
        Calculate actual health score based on nutrition quality, not completeness.
        This is a simplified version - System 3 will have a more sophisticated version.
        """
        score = 70  # Start neutral
        
        # Penalize high sugar
        if nutrition_data.sugar > 22.5:
            score -= 20
        elif nutrition_data.sugar > 12.5:
            score -= 10
        
        # Penalize high saturated fat
        if nutrition_data.saturated_fat > 7.5:
            score -= 15
        elif nutrition_data.saturated_fat > 5.0:
            score -= 8
        
        # Penalize high sodium
        if nutrition_data.sodium > 800:
            score -= 15
        elif nutrition_data.sodium > 400:
            score -= 8
        
        # Reward high protein
        if nutrition_data.protein > 10:
            score += 10
        elif nutrition_data.protein > 5:
            score += 5
        
        # Reward high fiber
        if nutrition_data.fiber > 6:
            score += 10
        elif nutrition_data.fiber > 3:
            score += 5
        
        return max(0, min(100, score))
    
    @staticmethod
    def _determine_recommendation(
        nutrition_data: NutritionData,
        ingredient_data: IngredientSummary,
    ) -> RecommendationInsight:
        """
        Determine recommendation based on actual nutrition and ingredient quality.
        """
        # Calculate recommendation score
        score = 70  # Start neutral
        
        # Sugar impact
        if nutrition_data.sugar > 22.5:
            score -= 25
        elif nutrition_data.sugar > 12.5:
            score -= 15
        
        # Fat impact
        if nutrition_data.saturated_fat > 7.5:
            score -= 20
        elif nutrition_data.saturated_fat > 5.0:
            score -= 10
        
        # Sodium impact
        if nutrition_data.sodium > 800:
            score -= 15
        elif nutrition_data.sodium > 400:
            score -= 8
        
        # Protein benefit
        if nutrition_data.protein > 10:
            score += 15
        elif nutrition_data.protein > 5:
            score += 8
        
        # Fiber benefit
        if nutrition_data.fiber > 6:
            score += 10
        elif nutrition_data.fiber > 3:
            score += 5
        
        # Determine recommendation type
        if score >= 80:
            rec_type = RecommendationType.RECOMMENDED
            reason = "Good nutritional profile with balanced macros."
            best_for = ["Daily consumption", "Regular meals"]
        elif score >= 60:
            rec_type = RecommendationType.OCCASIONAL
            reason = "Moderate nutritional value. Best for occasional consumption."
            best_for = ["Occasional snacking", "Weekly meals"]
        elif score >= 40:
            rec_type = RecommendationType.LIMITED
            reason = "High in sugar, fat, or sodium. Limit consumption."
            best_for = ["Rare treats", "Special occasions"]
        else:
            rec_type = RecommendationType.AVOID
            reason = "Poor nutritional quality. Consider healthier alternatives."
            best_for = ["Avoid for regular consumption"]
        
        # Adjust for ingredient quality
        if ingredient_data.ingredient_visibility_score < 30:
            reason += " Ingredient transparency is limited."
        
        return RecommendationInsight(
            recommendation=rec_type,
            reason=reason,
            best_for=best_for,
        )
    
    async def process_image_scan(
        self,
        image_bytes: bytes,
        user_id: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> ScanReport:
        
        scan_id = str(uuid4())
        logger = get_scan_logger(scan_id)
        start_time = asyncio.get_event_loop().time()
        logger.info("Initiating full image scan pipeline")
        
        try:
            quality_task = asyncio.create_task(image_quality_engine.analyze(image_bytes))
            barcode_task = asyncio.create_task(barcode_engine.scan(image_bytes=image_bytes))
            ocr_task = asyncio.create_task(ocr_engine.extract_text_from_bytes(image_bytes))
            
            quality_res: ImageQualityResult = await quality_task
            barcode_res: BarcodeResult = await barcode_task
            ocr_dict: Dict[str, Any] = await ocr_task
            ocr_res = OCRResult(**ocr_dict)
            
            off_match: Optional[OpenFoodFactsMatch] = None
            if barcode_res.is_valid and barcode_res.barcode:
                off_match = await product_identity_engine.lookup_openfoodfacts(barcode_res.barcode)
            
            nutrition_res: NutritionData = nutrition_engine.extract(
                text=ocr_res.extracted_text,
                has_nutrition_table=False,  # Let engine auto-detect
            )
            
            ingredient_dict = ingredient_base_engine.analyze_basic(
                text=ocr_res.extracted_text,
                has_ingredients_section=ocr_res.detected_sections.get("ingredients") is not None,
                readability_score=ocr_res.readability_score,
            )
            ingredient_res = IngredientSummary(**ingredient_dict)
            
            identity_res, fusion_res, matched_by = await product_identity_engine.build_product_identity(
                barcode_result=barcode_res,
                ocr_text=ocr_res.extracted_text,
                off_data=off_match,
                ocr_blocks=ocr_res.blocks,
                ocr_quality_score=ocr_res.ocr_quality_score,
            )
            
            # Use public wrapper method for packaging detection
            packaging_type = product_identity_engine.detect_packaging_type(
                ocr_res.extracted_text, 
                off_match.categories if off_match else None
            )
            
            passport_res = await product_identity_engine.build_product_passport(
                product_identity=identity_res,
                barcode_result=barcode_res,
                off_data=off_match,
                packaging_type=packaging_type,
            )
            
            # Extract real brand confidence from identity resolution
            brand_confidence = identity_res.identity_confidence if identity_res.brand else 0
            
            # Extract identity consistency from fusion result
            identity_consistency = getattr(fusion_res, 'identity_consistency', 0)
            
            verification_res = trust_verification_engine.build_verification_result(
                barcode_valid=barcode_res.is_valid,
                ocr_confidence=ocr_res.average_confidence,
                off_data_found=(off_match is not None and off_match.found),
                matched_by=matched_by,
                has_nutrition=nutrition_res.nutrition_detected,
                has_ingredients=ingredient_res.has_ingredients_section,
                fusion_used=(fusion_res.final_confidence > 0),
                ocr_threshold=0.70,
                barcode_confidence=barcode_res.confidence,
                off_confidence=off_match.score if off_match else 0,
                identity_consistency=identity_consistency,
            )
            
            evidence_panel = trust_verification_engine.build_evidence_panel(
                barcode_found=barcode_res.is_valid,
                barcode_confidence=barcode_res.confidence,
                off_found=(off_match is not None and off_match.found),
                off_confidence=off_match.score if off_match else 0,
                ocr_confidence=ocr_res.ocr_quality_score,
                fusion_used=(fusion_res.final_confidence > 0),
                fusion_confidence=fusion_res.final_confidence,
                identity_consistency=identity_consistency,
            )
            
            confidence_breakdown = trust_verification_engine.calculate_confidence_breakdown(
                barcode_confidence=barcode_res.confidence,
                ocr_confidence=ocr_res.ocr_quality_score,
                brand_confidence=brand_confidence,
                database_confidence=off_match.score if off_match else 0,
            )
            
            scanix_score = trust_verification_engine.calculate_scanix_score(
                ocr_confidence=ocr_res.average_confidence,
                barcode_confidence=barcode_res.confidence,
                off_match_confidence=off_match.score if off_match else 0,
                data_completeness=nutrition_res.nutrition_completeness,
                verification_level=verification_res.verification_level,
            )
            
            radar = RadarCompleteness(
                product_name=100 if identity_res.product_name else 0,
                brand=100 if identity_res.brand else 0,
                ingredients=ingredient_res.ingredient_visibility_score,
                nutrition=nutrition_res.nutrition_completeness,
                barcode=100 if barcode_res.is_valid else 0,
                images=100 if image_bytes else 0,
            )
            
            missing_detector = MissingDataDetector(
                missing_fields=nutrition_res.missing_fields,
                has_missing_data=len(nutrition_res.missing_fields) > 0,
                completeness_percentage=nutrition_res.nutrition_completeness,
            )
            
            vis_score = IngredientVisibilityScore(
                score=ingredient_res.ingredient_visibility_score,
                ingredients_found=ingredient_res.ingredient_count > 0,
                ingredients_readable=ocr_res.readability_score > 60,
                nutrition_complete=nutrition_res.nutrition_completeness > 80,
            )
            
            # Calculate actual health score (not completeness)
            health_score = self._calculate_health_score(nutrition_res)
            
            health_dash = HealthDashboard(
                health_score=HealthDashboardCard(
                    name="Health", 
                    score=health_score, 
                    grade=trust_verification_engine.get_grade(health_score)
                ),
                trust_score=HealthDashboardCard(
                    name="Trust", 
                    score=verification_res.trust_score, 
                    grade=trust_verification_engine.get_grade(verification_res.trust_score)
                ),
                reliability_score=HealthDashboardCard(
                    name="Reliability", 
                    score=verification_res.reliability_score, 
                    grade=trust_verification_engine.get_grade(verification_res.reliability_score)
                ),
                verification_score=HealthDashboardCard(
                    name="Verification", 
                    score=scanix_score.breakdown.verification_level, 
                    grade=trust_verification_engine.get_grade(scanix_score.breakdown.verification_level)
                ),
            )
            
            # Use OCR engine's heatmap method instead of manual construction
            image_shape = (0, 0)  # Will be populated by caller if needed
            ocr_heatmap_data = ocr_engine.get_ocr_heatmap_data(
                blocks=ocr_res.blocks,
                image_shape=image_shape,
            )
            
            label_intel_dict = await image_quality_engine.get_label_intelligence_metrics(
                image_bytes=image_bytes,
                quality=quality_res,
                ocr_readability=ocr_res.readability_score,
                ocr_coverage=ocr_res.text_density_score,
            )
            
            label_intel = LabelIntelligence(
                overall=quality_res.recommendation.split(".")[0] if quality_res.recommendation else "Unknown",
                metrics=LabelIntelligenceMetrics(**label_intel_dict)
            )
            
            elite_features = EliteFeatures(
                scanix_intelligence_score=scanix_score,
                product_reliability_meter=verification_res.reliability_score,
                radar_completeness=radar,
                label_intelligence=label_intel,
                multi_source_verification=evidence_panel,
                confidence_breakdown=confidence_breakdown,
                product_passport=passport_res,
                evidence_panel=evidence_panel,
                health_dashboard=health_dash,
                ingredient_visibility_score=vis_score,
                missing_data_detector=missing_detector,
                packaging_type=packaging_type,
                ocr_heatmap=ocr_heatmap_data,
            )
            
            processing_time = int((asyncio.get_event_loop().time() - start_time) * 1000)
            
            metadata = ScanMetadata(
                scan_id=scan_id,
                source=ScanSource.IMAGE_CAPTURE,
                processing_time_ms=processing_time,
                fallback_used=ocr_res.ocr_provider if ocr_res.ocr_provider != "easyocr" else None,
                api_version=APIVersion.V1,
                audit_trail=AuditTrail(
                    ocr_raw=ocr_res.raw_text[:1000],
                    ocr_corrected=ocr_res.extracted_text[:1000]
                )
            )
            
            scan_quality = ScanQuality(
                coverage_score=ocr_res.text_density_score,
                completeness_score=nutrition_res.nutrition_completeness,
                image_quality_score=quality_res.overall_score,
                scan_quality_score=scanix_score.score,
                scan_reliability_score=verification_res.reliability_score,
            )
            
            recommendation = self._determine_recommendation(
                nutrition_res,
                ingredient_res,
            )
            
            report = ScanReport(
                success=True,
                metadata=metadata,
                product=identity_res,
                ocr=ocr_res,
                barcode=barcode_res,
                image_quality=quality_res,
                nutrition=nutrition_res,
                ingredients=ingredient_res,
                verification=verification_res,
                recommendation=recommendation,
                scan_quality=scan_quality,
                off_match=off_match,
                elite=elite_features,
                warnings=[],
                hash=self._generate_report_hash(scan_id, datetime.now(timezone.utc).isoformat()),
            )
            
            logger.info(f"Scan pipeline completed successfully in {processing_time}ms")
            return report

        except Exception as e:
            logger.exception(f"Fatal error in scan pipeline: {e}")
            raise ScanProcessingError(message=f"Pipeline execution failed: {str(e)}")

    async def process_barcode_scan(
        self,
        barcode: str,
        user_id: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> ScanReport:
        
        scan_id = str(uuid4())
        logger = get_scan_logger(scan_id)
        start_time = asyncio.get_event_loop().time()
        logger.info(f"Initiating manual barcode pipeline for: {barcode}")
        
        try:
            quality_res = ImageQualityResult(
                overall_score=50, blur_score=50, brightness_score=50, contrast_score=50,
                glare_score=50, lighting_score=50, sharpness_score=50, recommendation="Manual Barcode Scan"
            )
            
            barcode_res = await barcode_engine.scan_manual(barcode)
            
            ocr_res = OCRResult(
                extracted_text="",
                raw_text="",
                blocks=[],
                average_confidence=0.0,
                text_density_score=0.0,
                readability_score=0.0,
                ocr_quality_score=0.0,
                ocr_provider="none",
                processing_time_ms=0,
                detected_sections={},
                nutrition_data={},
            )

            off_match = await product_identity_engine.lookup_openfoodfacts(barcode)
            nutrition_res: NutritionData = nutrition_engine.extract(text="", has_nutrition_table=False)
            ingredient_dict = ingredient_base_engine.analyze_basic(
                text="", 
                has_ingredients_section=False, 
                readability_score=0
            )
            ingredient_res = IngredientSummary(**ingredient_dict)

            identity_res, fusion_res, matched_by = await product_identity_engine.build_product_identity(
                barcode_result=barcode_res,
                ocr_text="",
                off_data=off_match,
                ocr_blocks=[],
                ocr_quality_score=0,
            )
            
            # Use public wrapper method for packaging detection
            packaging_type = product_identity_engine.detect_packaging_type(
                "", 
                off_match.categories if off_match else None
            )
            
            passport_res = await product_identity_engine.build_product_passport(
                product_identity=identity_res,
                barcode_result=barcode_res,
                off_data=off_match,
                packaging_type=packaging_type,
            )
            
            # Extract real brand confidence from identity resolution
            brand_confidence = identity_res.identity_confidence if identity_res.brand else 0
            
            # Extract identity consistency from fusion result
            identity_consistency = getattr(fusion_res, 'identity_consistency', 0)

            verification_res = trust_verification_engine.build_verification_result(
                barcode_valid=barcode_res.is_valid,
                ocr_confidence=0.0,
                off_data_found=(off_match is not None and off_match.found),
                matched_by=matched_by,
                has_nutrition=False,
                has_ingredients=False,
                fusion_used=(fusion_res.final_confidence > 0),
                ocr_threshold=0.70,
                barcode_confidence=barcode_res.confidence,
                off_confidence=off_match.score if off_match else 0,
                identity_consistency=identity_consistency,
            )
            
            evidence_panel = trust_verification_engine.build_evidence_panel(
                barcode_found=barcode_res.is_valid,
                barcode_confidence=barcode_res.confidence,
                off_found=(off_match is not None and off_match.found),
                off_confidence=off_match.score if off_match else 0,
                ocr_confidence=0,
                fusion_used=(fusion_res.final_confidence > 0),
                fusion_confidence=fusion_res.final_confidence,
                identity_consistency=identity_consistency,
            )
            
            confidence_breakdown = trust_verification_engine.calculate_confidence_breakdown(
                barcode_confidence=barcode_res.confidence,
                ocr_confidence=0,
                brand_confidence=brand_confidence,
                database_confidence=off_match.score if off_match else 0,
            )
            
            scanix_score = trust_verification_engine.calculate_scanix_score(
                ocr_confidence=0.0,
                barcode_confidence=barcode_res.confidence,
                off_match_confidence=off_match.score if off_match else 0,
                data_completeness=0,
                verification_level=verification_res.verification_level,
            )

            radar = RadarCompleteness(
                product_name=100 if identity_res.product_name else 0,
                brand=100 if identity_res.brand else 0,
                ingredients=0,
                nutrition=0,
                barcode=100 if barcode_res.is_valid else 0,
                images=0,
            )
            
            missing_detector = MissingDataDetector(
                missing_fields=["nutrition_data", "ingredients", "ocr_data"],
                has_missing_data=True,
                completeness_percentage=0,
            )
            
            vis_score = IngredientVisibilityScore(
                score=0,
                ingredients_found=False,
                ingredients_readable=False,
                nutrition_complete=False,
            )
            
            # Calculate actual health score
            health_score = self._calculate_health_score(nutrition_res)
            
            health_dash = HealthDashboard(
                health_score=HealthDashboardCard(
                    name="Health", 
                    score=health_score, 
                    grade=trust_verification_engine.get_grade(health_score)
                ),
                trust_score=HealthDashboardCard(
                    name="Trust", 
                    score=verification_res.trust_score, 
                    grade=trust_verification_engine.get_grade(verification_res.trust_score)
                ),
                reliability_score=HealthDashboardCard(
                    name="Reliability", 
                    score=verification_res.reliability_score, 
                    grade=trust_verification_engine.get_grade(verification_res.reliability_score)
                ),
                verification_score=HealthDashboardCard(
                    name="Verification", 
                    score=scanix_score.breakdown.verification_level, 
                    grade=trust_verification_engine.get_grade(scanix_score.breakdown.verification_level)
                ),
            )
            
            label_intel = LabelIntelligence(
                overall="Manual Scan",
                metrics=LabelIntelligenceMetrics(
                    lighting=0, sharpness=0, readability=0, coverage=0, contrast=0, perspective=0
                )
            )

            elite_features = EliteFeatures(
                scanix_intelligence_score=scanix_score,
                product_reliability_meter=verification_res.reliability_score,
                radar_completeness=radar,
                label_intelligence=label_intel,
                multi_source_verification=evidence_panel,
                confidence_breakdown=confidence_breakdown,
                product_passport=passport_res,
                evidence_panel=evidence_panel,
                health_dashboard=health_dash,
                ingredient_visibility_score=vis_score,
                missing_data_detector=missing_detector,
                packaging_type=packaging_type,
                ocr_heatmap=[],
            )

            processing_time = int((asyncio.get_event_loop().time() - start_time) * 1000)
            
            metadata = ScanMetadata(
                scan_id=scan_id,
                source=ScanSource.MANUAL_BARCODE,
                processing_time_ms=processing_time,
                fallback_used=None,
                api_version=APIVersion.V1,
                audit_trail=AuditTrail(ocr_raw="", ocr_corrected="")
            )
            
            scan_quality = ScanQuality(
                coverage_score=0,
                completeness_score=0,
                image_quality_score=50,
                scan_quality_score=scanix_score.score,
                scan_reliability_score=verification_res.reliability_score,
            )
            
            recommendation = self._determine_recommendation(
                nutrition_res,
                ingredient_res,
            )

            report = ScanReport(
                success=True,
                metadata=metadata,
                product=identity_res,
                ocr=ocr_res,
                barcode=barcode_res,
                image_quality=quality_res,
                nutrition=nutrition_res,
                ingredients=ingredient_res,
                verification=verification_res,
                recommendation=recommendation,
                scan_quality=scan_quality,
                off_match=off_match,
                elite=elite_features,
                warnings=[],
                hash=self._generate_report_hash(scan_id, datetime.now(timezone.utc).isoformat()),
            )

            logger.info(f"Manual barcode pipeline completed successfully in {processing_time}ms")
            return report

        except Exception as e:
            logger.exception(f"Fatal error in manual barcode pipeline: {e}")
            raise ScanProcessingError(message=f"Pipeline execution failed: {str(e)}")


# ==========================================================
# SINGLETON
# ==========================================================

scan_service = ScanService()