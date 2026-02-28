import React, { useState } from 'react';
import PortfolioOverview from './pages/PortfolioOverview';
import CategoryIntelligence from './pages/CategoryIntelligence';
import DataManagement from './pages/DataManagement';

const App = () => {
  const [activeTab, setActiveTab] = useState('portfolio');

  const tabs = [
    { id: 'portfolio', label: '📊 Portfolio Overview' },
    { id: 'intelligence', label: '🔎 Category Intelligence' },
    { id: 'data', label: '🗂 Data Management' },
  ];

  return (
    <div className="min-h-screen bg-[#0B1220] text-[#E2E8F0] font-sans selection:bg-blue-500/30">
      {/* Header */}
      <header className="max-w-[1400px] mx-auto px-6 py-8">
        <div className="flex justify-between items-end">
          <div>
            <h1 className="text-4xl font-extrabold text-[#F1F5F9] tracking-tight">
              MarketPulse <span className="text-blue-500">AI</span>
            </h1>
            <p className="text-[#94A3B8] mt-2 font-medium text-lg">Retail Forecasting & Inventory Intelligence</p>
          </div>
          <div className="hidden md:block text-right">
            <p className="text-[10px] uppercase font-bold tracking-[0.2em] text-[#64748B]">System Status: Operational</p>
            <p className="text-xs text-[#475569] mt-1 font-mono">Last Ingest: {new Date().toISOString().slice(0, 16).replace('T', ' ')}</p>
          </div>
        </div>
        <div className="h-px bg-gradient-to-r from-blue-500/50 via-white/5 to-transparent mt-6"></div>
      </header>

      {/* Main Container */}
      <main className="max-w-[1400px] mx-auto px-6 pb-20">

        {/* Navigation Tabs */}
        <nav className="flex gap-4 mb-10 overflow-x-auto pb-2 scrollbar-none">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`
                whitespace-nowrap px-6 py-3 rounded-xl text-sm font-semibold transition-all duration-300
                ${activeTab === tab.id
                  ? 'bg-[#2563EB] text-white shadow-[0_4px_20px_rgba(37,99,235,0.3)]'
                  : 'bg-[#111827] text-[#94A3B8] hover:bg-[#1F2937] hover:text-[#E2E8F0] border border-white/5 shadow-lg shadow-black/20'
                }
              `}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        {/* Dynamic Content */}
        <div className="animate-in fade-in slide-in-from-bottom-2 duration-700 fill-mode-both">
          {activeTab === 'portfolio' && <PortfolioOverview />}
          {activeTab === 'intelligence' && <CategoryIntelligence />}
          {activeTab === 'data' && <DataManagement />}
        </div>
      </main>
    </div>
  );
};

export default App;
