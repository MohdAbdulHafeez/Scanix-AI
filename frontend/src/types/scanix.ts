export interface ScanReport {
  success: boolean;
  metadata: any;
  product: any;
  ocr: any;
  barcode: any;
  image_quality: any;
  nutrition: any;
  ingredients: any;
  verification: any;
  recommendation: any;
  scan_quality: any;
  off_match: any;
  elite: {
    scanix_intelligence_score: any;
    product_reliability_meter: number;
    radar_completeness: any;
    label_intelligence: any;
    multi_source_verification: any;
    confidence_breakdown: any;
    product_passport: any;
    evidence_panel: any;
    health_dashboard: any;
    ingredient_visibility_score: any;
    missing_data_detector: any;
    packaging_type: string | null;
    ocr_heatmap: any[];
  };
}