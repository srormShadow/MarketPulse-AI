import { useEffect } from 'react';
import {
  X, AlertTriangle, PackageX, TrendingUp, Shield,
  Clock, Target, ArrowRight, ShieldAlert, BarChart3,
} from 'lucide-react';

// ── Detailed risk data per category ──────────────────────────

const riskDetails = {
  Snacks: {
    inventoryRisk: 0.83,
    uncertaintyRisk: 0.71,
    compositeRisk: 78,
    currentStock: 2800,
    requiredStock: 4200,
    safetyStock: 600,
    reorderPoint: 3200,
    leadTime: 5,
    forecast30d: 5240,
    dailyAvgDemand: 175,
    demandStdDev: 42,
    daysUntilStockout: 16,
    recommendedAction: 'Urgent Reorder',
    orderQty: 1400,
    reasons: [
      'Current stock (2,800) is 12.5% below reorder point (3,200)',
      'Demand coefficient of variation is 0.71 — high unpredictability',
      'Diwali seasonal surge expected within forecast window',
      'Only 16 days of stock remaining at current burn rate',
    ],
    forecastImpact: [
      'Projected demand spike of +35% during festival period',
      'Confidence interval widens significantly after day 15',
      'Historical pattern shows 2.1x demand during Diwali week',
    ],
    reorderBreach: {
      breached: true,
      deficit: 400,
      daysBelow: 8,
      explanation: 'Stock fell below reorder point 8 days ago and has not recovered. Without immediate action, stockout is projected within 16 days.',
    },
  },
  Staples: {
    inventoryRisk: 0.16,
    uncertaintyRisk: 0.22,
    compositeRisk: 32,
    currentStock: 5100,
    requiredStock: 5500,
    safetyStock: 800,
    reorderPoint: 4400,
    leadTime: 7,
    forecast30d: 6100,
    dailyAvgDemand: 203,
    demandStdDev: 28,
    daysUntilStockout: 25,
    recommendedAction: 'Monitor',
    orderQty: 0,
    reasons: [
      'Stock is comfortably above reorder point (5,100 vs 4,400)',
      'Demand variability is low — coefficient of variation is 0.22',
      'No major seasonal events in the near forecast window',
    ],
    forecastImpact: [
      'Steady demand expected with minimal seasonal variation',
      'Narrow confidence bands indicate high forecast reliability',
    ],
    reorderBreach: {
      breached: false,
      deficit: 0,
      daysBelow: 0,
      explanation: 'Current inventory is 15.9% above the reorder point. No action required at this time.',
    },
  },
  'Edible Oil': {
    inventoryRisk: 0.62,
    uncertaintyRisk: 0.54,
    compositeRisk: 65,
    currentStock: 1900,
    requiredStock: 3100,
    safetyStock: 450,
    reorderPoint: 2500,
    leadTime: 10,
    forecast30d: 3050,
    dailyAvgDemand: 102,
    demandStdDev: 38,
    daysUntilStockout: 19,
    recommendedAction: 'Schedule Reorder',
    orderQty: 850,
    reasons: [
      'Current stock (1,900) is 24% below reorder point (2,500)',
      'Long lead time (10 days) amplifies stockout risk',
      'Demand variability is medium — coefficient of variation is 0.54',
      'Pongal season historically drives +25% demand increase',
    ],
    forecastImpact: [
      'Lead time covers 33% of the forecast window — delays are costly',
      'Festival-driven demand increase of ~25% expected in 3 weeks',
      'Confidence interval suggests possible peak demand of 4,100 units',
    ],
    reorderBreach: {
      breached: true,
      deficit: 600,
      daysBelow: 3,
      explanation: 'Stock dropped below reorder point 3 days ago. Given the 10-day lead time, an order placed today would arrive when stock is critically low.',
    },
  },
};

// ── Helpers ──────────────────────────────────────────────────

const riskColor = (score) =>
  score >= 70 ? '#EF4444' : score >= 50 ? '#F59E0B' : '#10B981';

const riskLabel = (score) =>
  score >= 70 ? 'Critical' : score >= 50 ? 'Warning' : 'Healthy';

const pct = (value, max) => Math.min(100, Math.round((value / max) * 100));

// ── Component ────────────────────────────────────────────────

const RiskDrawer = ({ category, onClose }) => {
  const data = riskDetails[category];
  if (!data) return null;

  // Lock body scroll while drawer is open
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = ''; };
  }, []);

  // Close on Escape key
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const gap = data.requiredStock - data.currentStock;
  const stockPct = pct(data.currentStock, data.requiredStock);
  const riskPctInv = Math.round(data.inventoryRisk * 100);
  const riskPctUnc = Math.round(data.uncertaintyRisk * 100);

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40 animate-fade-in-up"
        style={{ animationDuration: '0.2s' }}
        onClick={onClose}
      />

      {/* Drawer Panel */}
      <div
        className="fixed top-0 right-0 h-full w-full max-w-[480px] bg-[#0B1220] border-l border-white/10 z-50 overflow-y-auto shadow-2xl shadow-black/50"
        style={{ animation: 'slideInRight 0.3s ease-out both' }}
      >
        {/* Header */}
        <div className="sticky top-0 bg-[#0B1220]/95 backdrop-blur-md border-b border-white/5 px-6 py-4 flex items-center justify-between z-10">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-red-500/10 rounded-lg">
              <ShieldAlert size={20} className="text-red-400" />
            </div>
            <div>
              <h2 className="font-bold text-[#F1F5F9] text-lg">{category}</h2>
              <p className="text-xs text-[#64748B]">Risk Analysis & Breakdown</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-white/5 text-[#64748B] hover:text-[#E2E8F0] transition-colors cursor-pointer"
          >
            <X size={20} />
          </button>
        </div>

        <div className="px-6 py-6 space-y-6">

          {/* ── Composite Risk Score ─────────────────────────── */}
          <div className="text-center py-5">
            <div className="inline-flex items-center justify-center w-24 h-24 rounded-full border-4 mb-3"
              style={{ borderColor: riskColor(data.compositeRisk) }}
            >
              <span className="text-3xl font-black" style={{ color: riskColor(data.compositeRisk) }}>
                {data.compositeRisk}
              </span>
            </div>
            <p className="text-sm font-bold uppercase tracking-wider" style={{ color: riskColor(data.compositeRisk) }}>
              {riskLabel(data.compositeRisk)} Risk
            </p>
            <p className="text-xs text-[#64748B] mt-1">
              Composite score = 0.6 x Inventory + 0.4 x Uncertainty
            </p>
          </div>

          {/* ── Risk Factor Breakdown ────────────────────────── */}
          <Section title="Risk Factor Breakdown" icon={<AlertTriangle size={16} />}>
            <RiskBar label="Inventory Risk" value={riskPctInv} weight="60%" color={riskColor(riskPctInv)} />
            <RiskBar label="Uncertainty Risk" value={riskPctUnc} weight="40%" color={riskColor(riskPctUnc)} />
            <p className="text-[10px] text-[#475569] mt-2 leading-relaxed">
              Inventory risk measures how far below the reorder point current stock sits.
              Uncertainty risk measures demand volatility (coefficient of variation).
            </p>
          </Section>

          {/* ── Why Risk Is High ──────────────────────────────── */}
          <Section title="Why Risk Is Elevated" icon={<ShieldAlert size={16} />}>
            <ul className="space-y-2">
              {data.reasons.map((reason, i) => (
                <li key={i} className="flex items-start gap-2.5 text-sm text-[#CBD5E1]">
                  <span className="mt-1.5 w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: riskColor(data.compositeRisk) }} />
                  {reason}
                </li>
              ))}
            </ul>
          </Section>

          {/* ── Inventory Gap ─────────────────────────────────── */}
          <Section title="Inventory Gap" icon={<PackageX size={16} />}>
            <div className="space-y-3">
              <div className="flex justify-between text-xs text-[#94A3B8]">
                <span>Current: <span className="text-[#E2E8F0] font-bold">{data.currentStock.toLocaleString()}</span></span>
                <span>Required: <span className="text-[#E2E8F0] font-bold">{data.requiredStock.toLocaleString()}</span></span>
              </div>
              <div className="relative h-3 bg-white/5 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{
                    width: `${stockPct}%`,
                    backgroundColor: stockPct >= 90 ? '#10B981' : stockPct >= 60 ? '#F59E0B' : '#EF4444',
                  }}
                />
                {/* Reorder point marker */}
                <div
                  className="absolute top-0 h-full w-0.5 bg-purple-400"
                  style={{ left: `${pct(data.reorderPoint, data.requiredStock)}%` }}
                  title={`Reorder Point: ${data.reorderPoint}`}
                />
              </div>
              <div className="flex justify-between text-[10px] text-[#475569]">
                <span>{stockPct}% filled</span>
                <span className="text-purple-400">Reorder Pt: {data.reorderPoint.toLocaleString()}</span>
              </div>
              {gap > 0 && (
                <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/5 border border-red-500/15 text-sm">
                  <PackageX size={14} className="text-red-400 shrink-0" />
                  <span className="text-red-300">
                    Deficit of <span className="font-bold">{gap.toLocaleString()}</span> units to reach required level
                  </span>
                </div>
              )}
            </div>
          </Section>

          {/* ── Forecast Impact ────────────────────────────────── */}
          <Section title="Forecast Impact" icon={<TrendingUp size={16} />}>
            <div className="grid grid-cols-3 gap-3 mb-3">
              <MiniStat label="30D Demand" value={data.forecast30d.toLocaleString()} />
              <MiniStat label="Daily Avg" value={data.dailyAvgDemand.toLocaleString()} />
              <MiniStat label="Std Dev" value={`\u00B1${data.demandStdDev}`} />
            </div>
            <ul className="space-y-2">
              {data.forecastImpact.map((impact, i) => (
                <li key={i} className="flex items-start gap-2.5 text-sm text-[#CBD5E1]">
                  <TrendingUp size={12} className="text-blue-400 mt-1 shrink-0" />
                  {impact}
                </li>
              ))}
            </ul>
          </Section>

          {/* ── Reorder Breach ─────────────────────────────────── */}
          <Section title="Reorder Breach Status" icon={<Target size={16} />}>
            <div className={`flex items-center gap-3 p-3.5 rounded-xl border mb-3 ${
              data.reorderBreach.breached
                ? 'bg-red-500/5 border-red-500/20'
                : 'bg-emerald-500/5 border-emerald-500/20'
            }`}>
              <div className={`p-2 rounded-lg ${data.reorderBreach.breached ? 'bg-red-500/15' : 'bg-emerald-500/15'}`}>
                <Target size={16} className={data.reorderBreach.breached ? 'text-red-400' : 'text-emerald-400'} />
              </div>
              <div>
                <p className={`text-sm font-bold ${data.reorderBreach.breached ? 'text-red-300' : 'text-emerald-300'}`}>
                  {data.reorderBreach.breached ? `Breached ${data.reorderBreach.daysBelow} days ago` : 'No Breach'}
                </p>
                {data.reorderBreach.breached && data.reorderBreach.deficit > 0 && (
                  <p className="text-xs text-[#94A3B8] mt-0.5">
                    {data.reorderBreach.deficit.toLocaleString()} units below reorder point
                  </p>
                )}
              </div>
            </div>
            <p className="text-sm text-[#94A3B8] leading-relaxed">{data.reorderBreach.explanation}</p>
            <div className="flex items-center gap-2 mt-3 text-xs text-[#64748B]">
              <Clock size={12} />
              <span>Days until stockout: <span className="text-[#E2E8F0] font-bold">{data.daysUntilStockout}</span></span>
              <span className="mx-1">|</span>
              <Shield size={12} />
              <span>Safety stock: <span className="text-[#E2E8F0] font-bold">{data.safetyStock.toLocaleString()}</span></span>
            </div>
          </Section>

          {/* ── Recommended Action ─────────────────────────────── */}
          <div className="p-4 rounded-xl bg-gradient-to-r from-blue-500/10 to-purple-500/10 border border-blue-500/20">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-blue-500/15 rounded-xl shrink-0">
                <BarChart3 size={20} className="text-blue-400" />
              </div>
              <div className="flex-1">
                <p className="text-[10px] text-[#64748B] uppercase font-bold tracking-wider">Recommended Action</p>
                <p className="text-base font-bold text-[#F1F5F9]">{data.recommendedAction}</p>
              </div>
              <ArrowRight size={18} className="text-[#475569]" />
            </div>
            {data.orderQty > 0 && (
              <div className="mt-3 pt-3 border-t border-white/5 flex items-center justify-between text-sm">
                <span className="text-[#94A3B8]">Order quantity</span>
                <span className="font-bold font-mono text-[#F1F5F9]">{data.orderQty.toLocaleString()} units</span>
              </div>
            )}
          </div>

        </div>
      </div>
    </>
  );
};

// ── Sub-components ───────────────────────────────────────────

const Section = ({ title, icon, children }) => (
  <div className="space-y-3">
    <div className="flex items-center gap-2 text-[#94A3B8]">
      {icon}
      <h3 className="text-xs font-bold uppercase tracking-wider">{title}</h3>
    </div>
    <div className="pl-0.5">{children}</div>
  </div>
);

const RiskBar = ({ label, value, weight, color }) => (
  <div className="mb-2.5">
    <div className="flex items-center justify-between text-xs mb-1.5">
      <span className="text-[#94A3B8]">{label} <span className="text-[#475569]">({weight})</span></span>
      <span className="font-mono font-bold" style={{ color }}>{value}%</span>
    </div>
    <div className="h-2 bg-white/5 rounded-full overflow-hidden">
      <div
        className="h-full rounded-full transition-all duration-700"
        style={{ width: `${value}%`, backgroundColor: color }}
      />
    </div>
  </div>
);

const MiniStat = ({ label, value }) => (
  <div className="bg-white/[0.03] border border-white/5 rounded-lg p-2.5 text-center">
    <p className="text-[10px] text-[#64748B] uppercase tracking-wider font-semibold">{label}</p>
    <p className="text-sm font-bold text-[#E2E8F0] mt-0.5 font-mono">{value}</p>
  </div>
);

export default RiskDrawer;
