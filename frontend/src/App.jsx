import React, { useState } from 'react';
import { LayoutDashboard, BrainCircuit, Database, Zap } from 'lucide-react';
import PortfolioOverview from './pages/PortfolioOverview';
import CategoryIntelligence from './pages/CategoryIntelligence';
import DataManagement from './pages/DataManagement';

const tabs = [
  { id: 'portfolio',    label: 'Portfolio Overview',    icon: LayoutDashboard },
  { id: 'intelligence', label: 'Category Intelligence', icon: BrainCircuit },
  { id: 'data',         label: 'Data Management',       icon: Database },
];

const App = () => {
  const [activeTab, setActiveTab] = useState('portfolio');

  const renderPage = () => {
    switch (activeTab) {
      case 'portfolio':    return <PortfolioOverview />;
      case 'intelligence': return <CategoryIntelligence />;
      case 'data':         return <DataManagement />;
      default:             return null;
    }
  };

  return (
    <div className="min-h-screen bg-[#0B1220] text-[#E2E8F0] font-sans selection:bg-blue-500/30">
      {/* Header */}
      <header className="max-w-[1400px] mx-auto px-6 pt-8 pb-6">
        <div className="flex justify-between items-end">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-blue-500/10 rounded-xl border border-blue-500/20">
              <Zap size={26} className="text-blue-400" />
            </div>
            <div>
              <h1 className="text-3xl font-extrabold text-[#F1F5F9] tracking-tight">
                MarketPulse <span className="text-blue-500">AI</span>
              </h1>
              <p className="text-[#94A3B8] mt-0.5 font-medium text-sm">
                Retail Forecasting & Inventory Intelligence
              </p>
            </div>
          </div>
          <div className="hidden md:flex items-center gap-3">
            <div className="flex items-center gap-2">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              <p className="text-[10px] uppercase font-bold tracking-[0.15em] text-emerald-400/80">
                Operational
              </p>
            </div>
            <div className="h-4 w-px bg-white/10 mx-1"></div>
            <p className="text-xs text-[#475569] font-mono">
              {new Date().toISOString().slice(0, 16).replace('T', ' ')}
            </p>
          </div>
        </div>
        <div className="h-[2px] animate-gradient-line mt-6 rounded-full"></div>
      </header>

      {/* Main */}
      <main className="max-w-[1400px] mx-auto px-6 pb-20">
        {/* Navigation */}
        <nav className="flex gap-2 mb-10 overflow-x-auto pb-2">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`
                  flex items-center gap-2 whitespace-nowrap px-5 py-2.5
                  rounded-xl text-sm font-semibold transition-all duration-300 cursor-pointer
                  ${isActive
                    ? 'bg-blue-600 text-white shadow-[0_4px_20px_rgba(37,99,235,0.35)]'
                    : 'bg-[#111827] text-[#94A3B8] hover:bg-[#1F2937] hover:text-[#E2E8F0] border border-white/5'
                  }
                `}
              >
                <Icon size={16} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Page Content */}
        <div key={activeTab} className="animate-fade-in-up">
          {renderPage()}
        </div>
      </main>
    </div>
  );
};

export default App;
