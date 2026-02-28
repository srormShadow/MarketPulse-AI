import React from 'react';

const PortfolioOverview = () => {
    return (
        <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {[
                    { label: 'Network Risk', value: 'High', color: 'text-red-400' },
                    { label: 'Inventory Gap', value: '-1,240', color: 'text-red-400' },
                    { label: '30D Forecast', value: '14,250', color: 'text-blue-400' },
                    { label: 'Active Categories', value: '3', color: 'text-emerald-400' },
                ].map((kpi, i) => (
                    <div key={i} className="bg-[#0F172A] border border-white/5 p-4 rounded-lg shadow-sm">
                        <p className="text-xs uppercase tracking-wider text-[#94A3B8] font-semibold">{kpi.label}</p>
                        <p className={`text-2xl font-bold mt-1 ${kpi.color}`}>{kpi.value}</p>
                    </div>
                ))}
            </div>

            <div className="bg-[#0F172A] border border-white/5 rounded-xl overflow-hidden shadow-xl">
                <div className="px-6 py-4 border-b border-white/5 bg-[#1E293B]/30">
                    <h3 className="font-semibold text-[#F1F5F9]">Inventory Health Portfolio</h3>
                </div>
                <div className="p-6 h-64 flex items-center justify-center text-[#94A3B8] italic border-b border-white/5">
                    Health Table Placeholder (Data Grid or Shadcn Table)
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-[#0F172A] border border-white/5 p-6 rounded-xl h-80 flex flex-col shadow-xl">
                    <h3 className="font-semibold text-[#F1F5F9] mb-4">Risk Distribution</h3>
                    <div className="flex-1 flex items-center justify-center text-[#94A3B8] italic">
                        Lollipop Chart Placeholder
                    </div>
                </div>
                <div className="bg-[#0F172A] border border-white/5 p-6 rounded-xl h-80 flex flex-col shadow-xl">
                    <h3 className="font-semibold text-[#F1F5F9] mb-4">Inventory Gaps</h3>
                    <div className="flex-1 flex items-center justify-center text-[#94A3B8] italic">
                        Gap Chart Placeholder
                    </div>
                </div>
            </div>
        </div>
    );
};

export default PortfolioOverview;
