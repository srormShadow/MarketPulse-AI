import React from 'react';

const DataManagement = () => {
    return (
        <div className="max-w-4xl space-y-8">
            <section className="space-y-4">
                <h3 className="text-xl font-bold text-[#F1F5F9]">Inventory Configuration</h3>
                <p className="text-sm text-[#94A3B8]">These values represent current stock on hand used for reorder optimization.</p>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-2">
                    {['Snacks', 'Staples', 'Edible Oil'].map((cat) => (
                        <div key={cat} className="space-y-2">
                            <label className="text-xs font-semibold text-[#94A3B8] uppercase">{cat} Stock</label>
                            <input
                                type="number"
                                defaultValue={100}
                                className="w-full bg-[#111827] border border-white/10 rounded-lg px-4 py-3 text-[#E2E8F0] focus:ring-2 focus:ring-blue-500/50 outline-none transition-all"
                            />
                        </div>
                    ))}
                </div>
            </section>

            <hr className="border-white/5" />

            <section className="space-y-4">
                <h3 className="text-xl font-bold text-[#F1F5F9]">Dataset Source</h3>
                <div className="flex gap-4">
                    <button className="flex-1 bg-blue-600 hover:bg-blue-500 text-white font-semibold py-4 rounded-xl transition-all shadow-lg shadow-blue-900/20 active:scale-[0.98]">
                        Use Demo Dataset
                    </button>
                    <div className="flex-1 relative group">
                        <input type="file" className="absolute inset-0 opacity-0 cursor-pointer z-10" />
                        <button className="w-full bg-[#1e293b] group-hover:bg-[#334155] text-[#E2E8F0] font-semibold py-4 rounded-xl transition-all border border-white/10">
                            Upload Custom CSV
                        </button>
                    </div>
                </div>
            </section>

            <div className="bg-[#1e293b]/20 border border-blue-500/20 p-6 rounded-xl flex items-start gap-4">
                <div className="p-2 bg-blue-500/10 rounded-lg text-blue-400">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                </div>
                <div>
                    <h4 className="font-semibold text-blue-100 italic">Validation Ready</h4>
                    <p className="text-sm text-blue-300/70 mt-1 leading-relaxed">System is ready for forecasting. Upload a valid sales history file to generate customized network intelligence.</p>
                </div>
            </div>
        </div>
    );
};

export default DataManagement;
