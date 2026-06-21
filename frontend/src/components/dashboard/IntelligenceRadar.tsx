import { Radar, RadarChart, PolarGrid, PolarAngleAxis, ResponsiveContainer } from 'recharts';
import { Cpu } from 'lucide-react';

export default function IntelligenceRadar({ report }: { report: any }) {
  const { radar_completeness, label_intelligence } = report.elite;
  const radarData = Object.entries(radar_completeness).map(([key, val]) => ({ subject: key.replace('_', ' ').toUpperCase(), A: val }));

  return (
    <div className="glass-panel p-8 rounded-3xl bg-white/70 h-full">
      <h3 className="text-xl font-black text-scanix-slate flex items-center gap-3 mb-6"><Cpu className="text-scanix-emerald"/> AI Vision Radar</h3>
      <div className="h-[250px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart cx="50%" cy="50%" outerRadius="75%" data={radarData}>
            <PolarGrid stroke="#E2E8F0" />
            <PolarAngleAxis dataKey="subject" tick={{ fill: '#64748B', fontSize: 10, fontWeight: 'bold' }} />
            <Radar name="Completeness" dataKey="A" stroke="#0A8F6A" strokeWidth={3} fill="#10B981" fillOpacity={0.4} />
          </RadarChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-4 grid grid-cols-3 gap-2">
         {Object.entries(label_intelligence.metrics).slice(0,3).map(([k, v]) => (
            <div key={k} className="bg-scanix-ivory p-2 rounded-lg text-center border border-scanix-border">
              <div className="text-lg font-black text-scanix-slate">{Number(v)}</div>
              <div className="text-[9px] uppercase font-bold text-scanix-ash">{k}</div>
            </div>
         ))}
      </div>
    </div>
  );
}