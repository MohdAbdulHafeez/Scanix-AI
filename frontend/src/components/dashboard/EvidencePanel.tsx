import { ShieldAlert, ShieldCheck } from "lucide-react";

export default function EvidencePanel({ report }: { report: any }) {
  const { elite, verification } = report;
  const { scanix_intelligence_score, health_dashboard } = elite;

  return (
    <div className="glass-panel p-8 rounded-3xl bg-gradient-to-b from-scanix-slate to-[#1e293b] text-white h-full flex flex-col justify-between shadow-2xl">
      <div>
        <div className="flex items-center gap-3 mb-8">
          <ShieldCheck className="w-8 h-8 text-scanix-mint" />
          <h3 className="text-2xl font-black tracking-tight">Trust Auditor</h3>
        </div>

        <div className="flex items-end gap-2 mb-8">
          <span className="text-7xl font-black leading-none text-transparent bg-clip-text bg-gradient-to-br from-scanix-emerald to-scanix-mint">
            {scanix_intelligence_score.score}
          </span>
          <span className="text-scanix-ash font-bold uppercase tracking-widest mb-2">/ 100</span>
        </div>

        <div className="space-y-4">
          <div className="flex justify-between items-center bg-white/5 p-4 rounded-xl border border-white/10">
            <span className="font-bold text-white/80">Reliability Meter</span>
            <span className="font-black text-scanix-mint">{health_dashboard.reliability_score.score}%</span>
          </div>
          <div className="flex justify-between items-center bg-white/5 p-4 rounded-xl border border-white/10">
            <span className="font-bold text-white/80">Data Verification</span>
            <span className="font-black text-scanix-mint">{health_dashboard.verification_score.score}%</span>
          </div>
          <div className="flex justify-between items-center bg-white/5 p-4 rounded-xl border border-white/10">
            <span className="font-bold text-white/80">Source Match</span>
            <span className="font-black text-white capitalize">{verification.matched_by || "None"}</span>
          </div>
        </div>
      </div>
    </div>
  );
}