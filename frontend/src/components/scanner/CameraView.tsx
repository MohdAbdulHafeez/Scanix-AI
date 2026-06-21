"use client";

import React, { useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { UploadCloud, Camera, Loader2, Sparkles, ScanLine, Search, Barcode } from "lucide-react";
import { useScanStore } from "../../store/useScanStore";

export default function CameraView() {
  const { scanImage, scanBarcode, isProcessing } = useScanStore();
  const [isDragging, setIsDragging] = useState(false);
  const [barcodeInput, setBarcodeInput] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files?.[0]) scanImage(e.dataTransfer.files[0]);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) scanImage(e.target.files[0]);
  };

  const handleBarcodeSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (barcodeInput.trim().length > 3) scanBarcode(barcodeInput.trim());
  };

  return (
    <div className="w-full max-w-3xl mx-auto mt-8">
      <div 
        className={`relative overflow-hidden rounded-[2.5rem] transition-all duration-500 ease-out 
          ${isDragging ? "border-4 border-scanix-mint bg-scanix-mint/5 scale-[1.02]" : "border border-scanix-border bg-white/60 backdrop-blur-xl shadow-xl hover:shadow-2xl hover:bg-white/80"}
          ${isProcessing ? "border-scanix-mint/50 shadow-[0_0_50px_rgba(16,185,129,0.15)]" : ""}
        `}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        <div className="p-8 md:p-12 flex flex-col items-center justify-center text-center min-h-[450px]">
          <AnimatePresence mode="wait">
            {!isProcessing ? (
              <motion.div key="idle" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex flex-col items-center gap-8 w-full">
                
                <div className="relative h-24 w-24 rounded-full bg-gradient-to-b from-white to-scanix-ivory flex items-center justify-center shadow-lg border border-white/50 cursor-pointer hover:scale-105 transition-transform" onClick={() => fileInputRef.current?.click()}>
                  <ScanLine className="w-10 h-10 text-scanix-emerald" />
                </div>
                
                <div className="space-y-2">
                  <h2 className="text-3xl font-extrabold text-scanix-slate">Scan Product Label</h2>
                  <p className="text-scanix-ash">Drop a photo or manually enter the barcode.</p>
                </div>

                <div className="flex flex-col sm:flex-row gap-4 w-full justify-center">
                  <button onClick={() => fileInputRef.current?.click()} className="flex items-center justify-center gap-2 bg-scanix-emerald hover:bg-scanix-forest text-white px-8 py-3.5 rounded-2xl font-bold transition-all shadow-lg">
                    <UploadCloud className="w-5 h-5" /> Image Gallery
                  </button>
                  <button onClick={() => fileInputRef.current?.click()} className="flex items-center justify-center gap-2 bg-white border-2 border-scanix-border hover:border-scanix-emerald text-scanix-slate px-8 py-3.5 rounded-2xl font-bold transition-all shadow-sm">
                    <Camera className="w-5 h-5 text-scanix-emerald" /> Camera
                  </button>
                </div>

                <div className="w-full max-w-md flex items-center gap-4 mt-2">
                  <div className="h-px bg-scanix-border flex-1"></div>
                  <span className="text-xs font-bold text-scanix-ash uppercase tracking-widest">OR</span>
                  <div className="h-px bg-scanix-border flex-1"></div>
                </div>

                <form onSubmit={handleBarcodeSubmit} className="w-full max-w-md relative flex items-center">
                  <Barcode className="absolute left-4 w-5 h-5 text-scanix-ash" />
                  <input 
                    type="text" 
                    placeholder="Enter Barcode (e.g., 890...)" 
                    value={barcodeInput}
                    onChange={(e) => setBarcodeInput(e.target.value)}
                    className="w-full pl-12 pr-24 py-4 rounded-2xl bg-scanix-ivory border-2 border-scanix-border focus:border-scanix-emerald focus:ring-0 text-scanix-slate font-semibold outline-none"
                  />
                  <button type="submit" disabled={barcodeInput.length < 3} className="absolute right-2 top-2 bottom-2 bg-scanix-slate hover:bg-scanix-emerald text-white px-4 rounded-xl font-bold text-sm transition-colors disabled:opacity-50">
                    Lookup <Search className="w-4 h-4 inline ml-1" />
                  </button>
                </form>

              </motion.div>
            ) : (
              <motion.div key="processing" initial={{ scale: 0.9 }} animate={{ scale: 1 }} className="flex flex-col items-center justify-center space-y-8">
                <div className="relative w-40 h-40 rounded-3xl border border-scanix-mint/20 bg-white shadow-2xl flex items-center justify-center overflow-hidden">
                  <Sparkles className="w-12 h-12 text-scanix-emerald animate-pulse" />
                  <motion.div className="absolute top-0 left-0 w-full h-1 bg-scanix-mint shadow-[0_0_30px_rgba(16,185,129,1)]" animate={{ y: [0, 160, 0] }} transition={{ repeat: Infinity, duration: 2 }} />
                </div>
                <div className="text-center bg-white/80 px-8 py-4 rounded-2xl border border-scanix-border shadow-sm">
                  <div className="flex items-center justify-center gap-3 text-scanix-emerald font-bold text-lg">
                    <Loader2 className="w-6 h-6 animate-spin" /> Processing AI Pipeline...
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
      <input type="file" ref={fileInputRef} onChange={handleFileChange} accept="image/*" className="hidden" />
    </div>
  );
}