"use client";

import CameraView from "../components/scanner/CameraView";
import MasterDashboard from "../components/dashboard/MasterDashboard";
import { useScanStore } from "../store/useScanStore";

export default function Home() {
  const { currentReport, clearCurrentScan } = useScanStore();

  return (
    <main className="min-h-screen bg-[#FDFCF8] bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-scanix-mint/5 via-[#FDFCF8] to-[#FDFCF8] pb-20">
      
      {/* Navigation Layer */}
      <nav className="w-full border-b border-scanix-border/50 bg-white/70 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-[1400px] mx-auto px-6 h-20 flex items-center justify-between">
          <div className="flex items-center gap-3 cursor-pointer" onClick={clearCurrentScan}>
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-scanix-emerald to-scanix-mint flex items-center justify-center shadow-lg shadow-scanix-mint/20">
              <span className="text-white font-black text-2xl tracking-tighter">S</span>
            </div>
            <span className="font-extrabold text-2xl text-scanix-slate tracking-tight">
              Scanix<span className="text-scanix-emerald">AI</span>
            </span>
          </div>
          
          {currentReport && (
            <button 
              onClick={clearCurrentScan}
              className="text-sm font-bold text-white bg-scanix-slate hover:bg-scanix-emerald px-6 py-2.5 rounded-full transition-all shadow-md"
            >
              Scan New Product
            </button>
          )}
        </div>
      </nav>

      {/* Main Workspace */}
      <div className="max-w-[1400px] mx-auto px-6 py-12 md:py-16">
        
        {!currentReport && (
          <div className="space-y-6 text-center mb-12 animate-in fade-in slide-in-from-bottom-8 duration-1000">
            <h1 className="text-5xl md:text-7xl font-black text-scanix-slate tracking-tighter leading-tight">
              Decode your food <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-scanix-emerald to-scanix-mint">
                at the molecular level.
              </span>
            </h1>
            <p className="text-xl text-scanix-ash max-w-2xl mx-auto font-medium">
              Enterprise-grade label intelligence.
            </p>
          </div>
        )}

        {/* Dynamic View Swapper */}
        {!currentReport ? (
          <CameraView />
        ) : currentReport && 'ocr' in currentReport ? (
          <div className="w-full animate-in zoom-in-95 duration-700 fade-in">
            <MasterDashboard report={currentReport as any} />
          </div>
        ) : null}

      </div>
    </main>
  );
}