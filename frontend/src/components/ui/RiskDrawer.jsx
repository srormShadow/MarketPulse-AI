import { useEffect } from 'react';
import {
  X, AlertTriangle, PackageX, TrendingUp, Shield,
  Clock, Target, ArrowRight, ShieldAlert, BarChart3,
} from 'lucide-react';

// ── Helpers ──────────────────────────────────────────────────

const riskColor = (score) =>
  score >= 70 ? '#EF4444' : score >= 50 ? '#F59E0B' : '#10B981';

const riskLabel = (score) =>
  score >= 70 ? 'Critical' : score >= 50 ? 'Warning' : 'Healthy';

const pct = (value, max) => max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;

function buildReasons(data) {
  const reasons = [];
  if (data.currentStock < data.reorderPoint) {
    const pctBelow = data.reorderPoint > 0
      ? ((data.reorderPoint - data.currentStock) / data.reorderPoint * 100).toFixed(1)
      : 0;
    reasons.push(`Current stock (${data.currentStock.toLocaleString()}) is ${pctBelow}% below reorder point (${data.reorderPoint.toLocaleString()})`);
  } else {
    const pctAbove = data.reorderPoint > 0
      ? ((data.currentStock - data.reorderPoint) / data.reorderPoint * 100).toFixed(1)
      : 0;
    reasons.push(`Stock is comfortably above reorder point (${data.currentStock.toLocaleString()} vs ${data.reorderPoint.toLocaleString()}, +${pctAbove}%)`);
  }
  if (data.uncertaintyRisk >= 0.5) {
    reasons.push(`Demand variability is high — coefficient of variation is ${data.uncertaintyRisk.toFixed(2)}`);
  } else if (data.uncertaintyRisk >= 0.3) {
    reasons.push(`Demand variability is medium — coefficient of variation is ${data.uncertaintyRisk.toFixed(2)}`);
  } else {
    reasons.push(`Demand variability is low — coefficient of variation is ${data.uncertaintyRisk.toFixed(2)}`);
  }
  if (data.leadTime >= 10) {
    reasons.push(`Long lead time (${data.leadTime} days) amplifies stockout risk`);
  }
  if (data.daysUntilStockout <= 14) {
    reasons.push(`Only ${data.daysUntilStockout} days of stock remaining at current burn rate`);
  }
  return reasons;
}

function buildReorderBreach(data) {
  const breached = data.currentStock < data.reorderPoint;
  const deficit = breached ? data.reorderPoint - data.currentStock : 0;
  let explanation;
  if (breached) {
    explanation = `Stock is ${deficit.toLocaleString()} units below the reorder point. ${data.leadTime > 0 ? `Given the ${data.leadTime}-day lead time, reorder soon to avoid stockout.` : 'Consider reordering now.'}`;
  } else {
    const abovePct = data.reorderPoint > 0
      ? ((data.currentStock - data.reorderPoint) / data.reorderPoint * 100).toFixed(1)
      : 0;
    explanation = `Current inventory is ${abovePct}% above the reorder point. No action required at this time.`;
  }
  return { breached, deficit, explanation };
}

// ── Component ────────────────────────────────────────────────

const RiskDrawer = ({ category, rowData, onClose }) => {
  // Build display data from live rowData
  const riskScore = rowData?.riskScore ?? 0;
  const compositeRisk = Math.round(riskScore * 100);

  // Derive inventory vs uncertainty risk from composite
  // composite = 0.6 * inventory + 0.4 * uncertainty
  // We approximate: if stock < reorder, inventory risk is high
  const currentStock = rowData?.currentStock ?? 0;
  const requiredStock = rowData?.requiredStock ?? 0;
  const reorderPoint = rowData?.reorderPoint ?? 0;
  const safetyStock = rowData?.safetyStock ?? 0;
  const leadTime = rowData?.leadTime ?? 0;
  const orderQuantity = rowData?.orderQuantity ?? 0;
  const action = rowData?.action ?? 'MAINTAIN';

  // Estimate sub-risks from available data
  const inventoryRisk = reorderPoint > 0
    ? Math.min(1, Math.max(0, (reorderPoint - currentStock) / reorderPoint))
    : 0;
  const uncertaintyRisk = inventoryRisk >= 0
    ? Math.min(1, Math.max(0, (compositeRisk / 100 - 0.6 * inventoryRisk) / 0.4))
    : riskScore;

  const forecast = rowData?.forecast ?? [];
  const forecast30d = forecast.slice(0, 30).reduce((sum, p) => sum + Number(p?.predicted_mean || 0), 0);
  const dailyAvgDemand = forecast.length > 0
    ? forecast.reduce((sum, p) => sum + Number(p?.predicted_mean || 0), 0) / forecast.length
    : 0;
  const daysUntilStockout = dailyAvgDemand > 0 ? Math.round(currentStock / dailyAvgDemand) : 999;

  // Compute demand std dev from forecast points
  const demands = forecast.map((p) => Number(p?.predicted_mean || 0));
  const mean = demands.length > 0 ? demands.reduce((a, b) => a + b, 0) / demands.length : 0;
  const demandStdDev = demands.length > 1
    ? Math.round(Math.sqrt(demands.reduce((sum, v) => sum + (v - mean) ** 2, 0) / (demands.length - 1)))
    : 0;

  const data = {
    inventoryRisk,
    uncertaintyRisk,
    compositeRisk,
    currentStock,
    requiredStock,
    safetyStock,
    reorderPoint,
    leadTime,
    forecast30d: Math.round(forecast30d),
    dailyAvgDemand: Math.round(dailyAvgDemand),
    demandStdDev,
    daysUntilStockout,
    recommendedAction: action.replace(/_/g, ' '),
    orderQty: orderQuantity,
  };

  data.reasons = buildReasons(data);
  data.reorderBreach = buildReorderBreach(data);

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
        className="fixed top-0 right-0 h-full w-full max-w-[480px] bg-[var(--bg)] border-l border-[var(--border)] z-50 overflow-y-auto shadow-2xl shadow-black/50"
        style={{ animation: 'slideInRight 0.3s ease-out both' }}
      >
        {/* Header */}
        <div className="sticky top-0 bg-[var(--bg)]/95 backdrop-blur-md border-b border-[var(--border-soft)] px-6 py-4 flex items-center justify-between z-10">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-red-500/10 rounded-lg">
              <ShieldAlert size={20} className="text-red-400" />
            </div>
            <div>
              <h2 className="font-bold text-[var(--text-1)] text-lg">{category}</h2>
              <p className="text-xs text-[var(--text-3)]">Risk Analysis & Breakdown</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-white/5 text-[var(--text-3)] hover:text-[var(--text-1)] transition-colors cursor-pointer"
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
                {data.compositeRisk}%
              </span>
            </div>
            <p className="text-sm font-bold uppercase tracking-wider" style={{ color: riskColor(data.compositeRisk) }}>
              {riskLabel(data.compositeRisk)} Risk
            </p>
            <p className="text-xs text-[var(--text-3)] mt-1">
              Composite score = 0.6 x Inventory + 0.4 x Uncertainty
            </p>
          </div>

          {/* ── Risk Factor Breakdown ────────────────────────── */}
          <Section title="Risk Factor Breakdown" icon={<AlertTriangle size={16} />}>
            <RiskBar label="Inventory Risk" value={riskPctInv} weight="60%" color={riskColor(riskPctInv)} />
            <RiskBar label="Uncertainty Risk" value={riskPctUnc} weight="40%" color={riskColor(riskPctUnc)} />
            <p className="text-[10px] text-[var(--text-3)] mt-2 leading-relaxed">
              Inventory risk measures how far below the reorder point current stock sits.
              Uncertainty risk measures demand volatility (coefficient of variation).
            </p>
          </Section>

          {/* ── Why Risk Is High ──────────────────────────────── */}
          <Section title="Why Risk Is Elevated" icon={<ShieldAlert size={16} />}>
            <ul className="space-y-2">
              {data.reasons.map((reason, i) => (
                <li key={i} className="flex items-start gap-2.5 text-sm text-[var(--text-2)]">
                  <span className="mt-1.5 w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: riskColor(data.compositeRisk) }} />
                  {reason}
                </li>
              ))}
            </ul>
          </Section>

          {/* ── Inventory Gap ─────────────────────────────────── */}
          <Section title="Inventory Gap" icon={<PackageX size={16} />}>
            <div className="space-y-3">
              <div className="flex justify-between text-xs text-[var(--text-3)]">
                <span>Current: <span className="text-[var(--text-1)] font-bold">{data.currentStock.toLocaleString()}</span></span>
                <span>Required: <span className="text-[var(--text-1)] font-bold">{data.requiredStock.toLocaleString()}</span></span>
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
                {data.requiredStock > 0 && (
                  <div
                    className="absolute top-0 h-full w-0.5 bg-purple-400"
                    style={{ left: `${pct(data.reorderPoint, data.requiredStock)}%` }}
                    title={`Reorder Point: ${data.reorderPoint}`}
                  />
                )}
              </div>
              <div className="flex justify-between text-[10px] text-[var(--text-3)]">
                <span>{stockPct}% filled</span>
                <span className="text-purple-400">Reorder Pt: {data.reorderPoint.toLocaleString()}</span>
              </div>
              {gap > 0 && (
                <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/5 border border-red-500/15 text-sm">
                  <PackageX size={14} className="text-red-400 shrink-0" />
                  <span className="text-[var(--badge-danger-text)]">
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
                <p className={`text-sm font-bold ${data.reorderBreach.breached ? 'text-[var(--badge-danger-text)]' : 'text-[var(--badge-success-text)]'}`}>
                  {data.reorderBreach.breached ? 'Below Reorder Point' : 'No Breach'}
                </p>
                {data.reorderBreach.breached && data.reorderBreach.deficit > 0 && (
                  <p className="text-xs text-[var(--text-3)] mt-0.5">
                    {data.reorderBreach.deficit.toLocaleString()} units below reorder point
                  </p>
                )}
              </div>
            </div>
            <p className="text-sm text-[var(--text-3)] leading-relaxed">{data.reorderBreach.explanation}</p>
            <div className="flex items-center gap-2 mt-3 text-xs text-[var(--text-3)]">
              <Clock size={12} />
              <span>Days until stockout: <span className="text-[var(--text-1)] font-bold">{data.daysUntilStockout > 900 ? 'N/A' : data.daysUntilStockout}</span></span>
              <span className="mx-1">|</span>
              <Shield size={12} />
              <span>Safety stock: <span className="text-[var(--text-1)] font-bold">{data.safetyStock.toLocaleString()}</span></span>
            </div>
          </Section>

          {/* ── Recommended Action ─────────────────────────────── */}
          <div className="p-4 rounded-xl bg-gradient-to-r from-blue-500/10 to-purple-500/10 border border-blue-500/20">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-blue-500/15 rounded-xl shrink-0">
                <BarChart3 size={20} className="text-blue-400" />
              </div>
              <div className="flex-1">
                <p className="text-[10px] text-[var(--text-3)] uppercase font-bold tracking-wider">Recommended Action</p>
                <p className="text-base font-bold text-[var(--text-1)]">{data.recommendedAction}</p>
              </div>
              <ArrowRight size={18} className="text-[var(--text-3)]" />
            </div>
            {data.orderQty > 0 && (
              <div className="mt-3 pt-3 border-t border-[var(--border-soft)] flex items-center justify-between text-sm">
                <span className="text-[var(--text-3)]">Order quantity</span>
                <span className="font-bold font-mono text-[var(--text-1)]">{data.orderQty.toLocaleString()} units</span>
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
    <div className="flex items-center gap-2 text-[var(--text-3)]">
      {icon}
      <h3 className="text-xs font-bold uppercase tracking-wider">{title}</h3>
    </div>
    <div className="pl-0.5">{children}</div>
  </div>
);

const RiskBar = ({ label, value, weight, color }) => (
  <div className="mb-2.5">
    <div className="flex items-center justify-between text-xs mb-1.5">
      <span className="text-[var(--text-3)]">{label} <span className="text-[var(--text-3)]">({weight})</span></span>
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
  <div className="bg-[color-mix(in_srgb,var(--bg-elevated)_76%,transparent)] border border-[var(--border-soft)] rounded-lg p-2.5 text-center">
    <p className="text-[10px] text-[var(--text-3)] uppercase tracking-wider font-semibold">{label}</p>
    <p className="text-sm font-bold text-[var(--text-1)] mt-0.5 font-mono">{value}</p>
  </div>
);

export default RiskDrawer;



