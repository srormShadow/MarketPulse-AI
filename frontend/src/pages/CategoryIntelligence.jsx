import React from 'react';

const CategoryIntelligence = () => {
    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between mb-2">
                <select className="bg-[#1E293B] text-[#E2E8F0] border border-white/10 rounded-md px-4 py-2 outline-none focus:ring-2 focus:ring-blue-500/50 w-64 text-sm">
                    <option>Select Category...</option>
                    <option>Snacks</option>
                    <option>Staples</option>
                    <option>Edible Oil</option>
                </select>
                <div className="flex gap-2">
                    <span className="px-3 py-1 rounded bg-emerald-500/10 text-emerald-400 text-xs font-bold border border-emerald-500/20 uppercase tracking-tight">Status: Healthy</span>
                </div>
            </div>

            <div className="bg-[#0F172A] border border-white/5 rounded-xl p-6 h-[450px] flex flex-col shadow-xl transition-all">
                <h3 className="font-semibold text-[#F1F5F9] mb-1">Demand Forecast Visualization</h3>
                <p className="text-xs text-[#94A3B8] mb-6">Historical demand vs predicted units (95% confidence interval)</p>
                <div className="flex-1 bg-[#090E1A]/50 rounded-lg flex items-center justify-center text-[#94A3B8] italic border border-white/5">
                    Recharts Area Chart with Glow & Bands Placeholder
                </div>
            </div>

            <div className="grid grid-cols-3 gap-6">
                {[
                    { label: '30D Forecast', value: '5,240', desc: 'Predicted units' },
                    { label: 'Safety Stock', value: '450', desc: 'Recommended level' },
                    { label: 'Order Lead Time', value: '7 Days', desc: 'Supply constraint' },
                ].map((stat, i) => (
                    <div key={i} className="bg-[#0F172A] border border-white/5 p-5 rounded-xl shadow-lg">
                        <p className="text-xs font-bold text-[#94A3B8] uppercase tracking-wider mb-1">{stat.label}</p>
                        <div className="text-2xl font-bold text-[#F1F5F9]">{stat.value}</div>
                        <p className="text-[10px] text-[#64748B] mt-1">{stat.desc}</p>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default CategoryIntelligence;
