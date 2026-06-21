// ==========================================================
// SCANIX AI
// CLIENT STATE CORE (ZUSTAND)
// Central data architecture managing multi-system context variables
// ==========================================================

import { create } from "zustand";
import { scanixApi, ScanReport } from "../services/scanixApi";

interface ScanState {
  currentReport: ScanReport | null;
  history: ScanReport[];
  isProcessing: boolean;
  pipelineStage: "idle" | "uploading" | "vision_ocr" | "database_fusion" | "complete";
  error: string | null;
  scanImage: (file: File | Blob) => Promise<void>;
  scanBarcode: (barcode: string) => Promise<void>;
  clearCurrentScan: () => void;
}

export const useScanStore = create<ScanState>((set, get) => ({
  currentReport: null,
  history: [],
  isProcessing: false,
  pipelineStage: "idle",
  error: null,

  scanImage: async (file: File | Blob) => {
    set({ isProcessing: true, pipelineStage: "uploading", error: null });
    
    try {
      const timer1 = setTimeout(() => {
        if (get().isProcessing) set({ pipelineStage: "vision_ocr" });
      }, 1000);

      const timer2 = setTimeout(() => {
        if (get().pipelineStage === "vision_ocr") set({ pipelineStage: "database_fusion" });
      }, 4000);

      const report = await scanixApi.processImageScan(file);
      
      clearTimeout(timer1);
      clearTimeout(timer2);
      
      set((state) => ({
        currentReport: report,
        history: [report, ...state.history],
        pipelineStage: "complete",
        isProcessing: false
      }));
    } catch (err: any) {
      set({ 
        error: err.response?.data?.message || err.message || "An image processing pipeline crash occurred.",
        isProcessing: false,
        pipelineStage: "idle"
      });
      throw err;
    }
  },

  scanBarcode: async (barcode: string) => {
    set({ isProcessing: true, pipelineStage: "database_fusion", error: null });
    
    try {
      const report = await scanixApi.processBarcodeScan(barcode);
      
      set((state) => ({
        currentReport: report,
        history: [report, ...state.history],
        pipelineStage: "complete",
        isProcessing: false
      }));
    } catch (err: any) {
      set({ 
        error: err.response?.data?.message || err.message || "A manual barcode processing failure occurred.",
        isProcessing: false,
        pipelineStage: "idle"
      });
      throw err;
    }
  },

  clearCurrentScan: () => set({ currentReport: null, pipelineStage: "idle", error: null })
}));