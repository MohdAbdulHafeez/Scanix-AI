// ==========================================================
// SCANIX AI
// SYSTEM 1 - API TRANSPORT SERVICE
// Orchestrates zero-disk binary streams to the vision core
// ==========================================================

import axios from "axios";

// Self-contained strict types to bypass external module checks
export interface ScanReport {
  success: boolean;
  metadata: {
    scan_id: string;
    timestamp: string;
    source: string;
    processing_time_ms: number;
    api_version: string;
  };
  product: {
    product_name: string | null;
    brand: string | null;
    category: string | null;
    barcode: string | null;
  };
  image_quality: {
    overall_score: number;
    recommendation: string;
  };
  nutrition: {
    nutrition_detected: boolean;
    nutrition_completeness: number;
    protein: number;
    fat: number;
    saturated_fat: number;
    sugar: number;
    sodium: number;
    carbohydrates: number;
    fiber: number;
    calories: number;
    sugar_traffic_light: string;
    fat_traffic_light: string;
    saturated_fat_traffic_light: string;
    sodium_traffic_light: string;
  };
  ingredients: {
    ingredients: string[];
    ingredient_count: number;
    basic_allergens: string[];
  };
  elite: {
    radar_completeness: {
      product_name: number;
      brand: number;
      ingredients: number;
      nutrition: number;
      barcode: number;
      images: number;
    };
    label_intelligence: {
      overall: string;
      metrics: {
        lighting: number;
        sharpness: number;
        readability: number;
        coverage: number;
        contrast: number;
        perspective: number;
      };
    };
  };
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Accept": "application/json",
  },
  timeout: 60000,
});

export const scanixApi = {
  
  async processImageScan(file: File | Blob): Promise<ScanReport> {
    const formData = new FormData();
    formData.append("file", file, file instanceof File ? file.name : "camera_scan.jpg");

    const response = await apiClient.post<ScanReport>("/scan/image", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
    
    return response.data;
  },

  async processBarcodeScan(barcode: string): Promise<ScanReport> {
    const response = await apiClient.post<ScanReport>("/scan/barcode", {
      barcode: barcode.trim(),
    }, {
      headers: {
        "Content-Type": "application/json",
      },
    });
    
    return response.data;
  }
};