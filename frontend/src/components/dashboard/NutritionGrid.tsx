import { Activity, AlertCircle } from "lucide-react";

export default function NutritionGrid({ report }: { report: any }) {
  const { nutrition, elite } = report;

  const getTrafficColor = (s?: string) => {
    if (s === "green") return "bg-scanix-mint/10 text-scanix-forest border-scanix-mint/30 shadow-[inset_0_0_20px_rgba(16,185,129,0.05)]";
    if (s === "yellow") return "bg-amber-50 text-amber-700 border-amber-200 shadow-[inset_0_0_20px_rgba(251,191,36,0.05)]";
    if (s === "red") return "bg-rose-50 text-rose-700 border-rose-200 shadow-[inset_0_0_20px_rgba(244,63,94,0.05)]";
    return "bg-scanix-ivory text-scanix-slate border-scanix-border";
  };

  const stats = [
    { label: "Fat", value: nutrition.fat, color: nutrition.fat_traffic_light, unit: "g" },
    { label: "Sat Fat", value: nutrition.saturated_fat, color: nutrition.saturated_fat_traffic_light, unit: "g" },
    { label: "Sugar", value: nutrition.sugar, color: nutrition.sugar_traffic_light, unit: "g" },
    { label: "Sodium", value: nutrition.sodium, color: nutrition.sodium_traffic_light, unit: "mg" },
  ];

  return (
    <div className="glass-panel p-8 rounded-3xl bg-white/70 h-full flex flex-col justify-between">
      <div>
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-2xl font-black text-scanix-slate flex items-center gap-3"><Activity className="text-scanix-emerald" /> Nutrition Matrix</h3>
          <span className="px-3 py-1 bg-scanix-slate text-white text-[10px] font-black tracking-widest uppercase rounded-lg">Per 100g</span>
        </div>
        
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {stats.map((stat, i) => (
            <div key={i} className={`p-5 rounded-2xl border-2 flex flex-col items-center justify-center transition-all ${getTrafficColor(stat.color)}`}>
              <span className="text-3xl font-black">{stat.value || 0}<span className="text-lg">{stat.unit}</span></span>
              <span className="text-[10px] font-black uppercase tracking-widest mt-1 opacity-80">{stat.label}</span>
            </div>
          ))}
        </div>
      </div>

      {elite.missing_data_detector.has_missing_data && (
        <div className="bg-rose-50 border border-rose-200 p-4 rounded-2xl flex gap-3 items-start">
          <AlertCircle className="w-5 h-5 text-rose-500 shrink-0 mt-0.5" />
          <div>
            <div className="text-sm font-bold text-rose-800">Missing Critical Data Fields</div>
            <div className="text-xs text-rose-600 font-medium mt-1">Unable to extract: {elite.missing_data_detector.missing_fields.join(", ")}</div>
          </div>
        </div>
      )}
    </div>
  );
}