import { Target, Box, Leaf } from "lucide-react";

export default function ProductPassport({ report }: { report: any }) {
  const { product, elite, ingredients } = report;
  
  return (
    <div className="glass-panel p-8 rounded-3xl bg-white/70 h-full flex flex-col justify-between">
      <div>
        <div className="flex justify-between items-start mb-6">
          <div>
            <h1 className="text-4xl md:text-5xl font-black text-scanix-slate leading-tight">{product.product_name || "Unknown Product"}</h1>
            <p className="text-xl text-scanix-ash font-bold mt-2">{product.brand || "Brand Not Detected"} • {product.category || "General"}</p>
          </div>
          <div className="bg-scanix-emerald/10 border border-scanix-emerald text-scanix-emerald px-4 py-2 rounded-xl font-black text-sm uppercase tracking-widest shadow-sm">
            Verified Identity
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 mb-8">
          <div className="p-4 bg-scanix-ivory rounded-2xl border border-scanix-border flex items-center gap-4">
            <Box className="w-8 h-8 text-scanix-ash" />
            <div>
              <div className="text-[10px] font-black uppercase text-scanix-ash tracking-widest">Packaging</div>
              <div className="font-bold text-scanix-slate capitalize">{elite.packaging_type || "Unknown"}</div>
            </div>
          </div>
          <div className="p-4 bg-scanix-ivory rounded-2xl border border-scanix-border flex items-center gap-4">
            <Target className="w-8 h-8 text-scanix-ash" />
            <div>
              <div className="text-[10px] font-black uppercase text-scanix-ash tracking-widest">Barcode Match</div>
              <div className="font-bold text-scanix-slate">{report.barcode.barcode || "N/A"}</div>
            </div>
          </div>
        </div>
      </div>

      <div>
        <h3 className="font-bold text-scanix-slate flex items-center gap-2 mb-3"><Leaf className="w-5 h-5 text-scanix-emerald"/> Ingredients Visibility: {elite.ingredient_visibility_score.score}/100</h3>
        <div className="flex flex-wrap gap-2">
          {ingredients.ingredients?.length > 0 ? ingredients.ingredients.map((ing: string, i: number) => (
            <span key={i} className="px-3 py-1 bg-scanix-slate text-white text-xs font-bold rounded-lg">{ing}</span>
          )) : <span className="text-sm font-semibold text-scanix-ash">No ingredients extracted.</span>}
        </div>
      </div>
    </div>
  );
}