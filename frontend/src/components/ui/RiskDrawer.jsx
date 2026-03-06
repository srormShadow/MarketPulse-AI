import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import {
  X, AlertTriangle, PackageX, TrendingUp, Shield,
  Clock, Target, ArrowRight, ShieldAlert, BarChart3,
} from 'lucide-react';

const riskColor = (score) => (
  score >= 70 ? '#EF4444' : score >= 50 ? '#F59E0B' : '#10B981'
);

const riskLabel = (score) => (
  score >= 70 ? 'Critical' : score >= 50 ? 'Warning' : 'Healthy'
);

const pct = (value, max) => (
  max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0
);

function buildReasons(data) {
  const reasons = [];

  if (data.currentStock < data.reorderPoint) {
    const pctBelow = data.reorderPoint > 0
      ? ((data.reorderPoint - data.currentStock) / data.reorderPoint * 100).toFixed(1)
      : 0;
    reasons.push(
      `Current stock (${data.currentStock.toLocaleString()}) is ${pctBelow}% below reorder point (${data.reorderPoint.toLocaleString()})`
    );
  } else {
    const pctAbove = data.reorderPoint > 0
      ? ((data.currentStock - data.reorderPoint) / data.reorderPoint * 100).toFixed(1)
      : 0;
    reasons.push(
      `Stock is comfortably above reorder point (${data.currentStock.toLocaleString()} vs ${data.reorderPoint.toLocaleString()}, +${pctAbove}%)`
    );
  }

  if (data.uncertaintyRisk >= 0.5) {
    reasons.push(`Demand variability is high - coefficient of variation is ${data.uncertaintyRisk.toFixed(2)}`);
  } else if (data.uncertaintyRisk >= 0.3) {
    reasons.push(`Demand variability is medium - coefficient of variation is ${data.uncertaintyRisk.toFixed(2)}`);
  } else {
    reasons.push(`Demand variability is low - coefficient of variation is ${data.uncertaintyRisk.toFixed(2)}`);
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
    explanation = `Stock is ${deficit.toLocaleString()} units below the reorder point. ${
      data.leadTime > 0
        ? `Given the ${data.leadTime}-day lead time, reorder soon to avoid stockout.`
        : 'Consider reordering now.'
    }`;
  } else {
    const abovePct = data.reorderPoint > 0
      ? ((data.currentStock - data.reorderPoint) / data.reorderPoint * 100).toFixed(1)
      : 0;
    explanation = `Current inventory is ${abovePct}% above the reorder point. No action required at this time.`;
  }

  return { breached, deficit, explanation };
}

const RiskDrawer = ({ category, rowData, onClose }) => {
  const riskScore = rowData?.riskScore ?? 0;
  const compositeRisk = Math.round(riskScore * 100);

  const currentStock = rowData?.currentStock ?? 0;
  const requiredStock = rowData?.requiredStock ?? 0;
  const reorderPoint = rowData?.reorderPoint ?? 0;
  const safetyStock = rowData?.safetyStock ?? 0;
  const leadTime = rowData?.leadTime ?? 0;
  const orderQuantity = rowData?.orderQuantity ?? 0;
  const action = rowData?.action ?? 'MAINTAIN';

  const inventoryRisk = reorderPoint > 0
    ? Math.min(1, Math.max(0, (reorderPoint - currentStock) / reorderPoint))
    : 0;
  const uncertaintyRisk = inventoryRisk >= 0
    ? Math.min(1, Math.max(0, (compositeRisk / 100 - 0.6 * inventoryRisk) / 0.4))
    : riskScore;

  const forecast = rowData?.forecast ?? [];
  const forecast30d = forecast
    .slice(0, 30)
    .reduce((sum, point) => sum + Number(point?.predicted_mean || 0), 0);
  const dailyAvgDemand = forecast.length > 0
    ? forecast.reduce((sum, point) => sum + Number(point?.predicted_mean || 0), 0) / forecast.length
    : 0;
  const daysUntilStockout = dailyAvgDemand > 0 ? Math.round(currentStock / dailyAvgDemand) : 999;

  const demands = forecast.map((point) => Number(point?.predicted_mean || 0));
  const mean = demands.length > 0 ? demands.reduce((a, b) => a + b, 0) / demands.length : 0;
  const demandStdDev = demands.length > 1
    ? Math.round(Math.sqrt(demands.reduce((sum, value) => sum + (value - mean) ** 2, 0) / (demands.length - 1)))
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

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, []);

  useEffect(() => {
    const handler = (event) => {
      if (event.key === 'Escape') onClose();
    };

    window.addEventListener('keydown', handler);
    return () => {
      window.removeEventListener('keydown', handler);
    };
  }, [onClose]);

  const gap = data.requiredStock - data.currentStock;
  const stockPct = pct(data.currentStock, data.requiredStock);
  const riskPctInv = Math.round(data.inventoryRisk * 100);
  const riskPctUnc = Math.round(data.uncertaintyRisk * 100);
  const ringColor = riskColor(data.compositeRisk);

  return createPortal(
    <>
      <div
        className="fixed inset-0 z-40 bg-black/55 backdrop-blur-sm transition-opacity duration-200"
        onClick={onClose}
      />

      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6" onClick={onClose}>
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`${category} risk analysis`}
          onClick={(event) => event.stopPropagation()}
          className="w-full max-w-4xl max-h-[88vh] overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--bg)] shadow-2xl shadow-black/50 animate-fade-in-up"
        >
          <div className="sticky top-0 z-10 flex items-center justify-between border-b border-[var(--border-soft)] bg-[var(--bg)]/95 px-5 py-4 backdrop-blur-md sm:px-6">
            <div className="flex min-w-0 items-center gap-3">
              <div className="rounded-lg bg-red-500/10 p-2">
                <ShieldAlert size={20} className="text-red-400" />
              </div>
              <div className="min-w-0">
                <h2 className="truncate text-lg font-bold text-[var(--text-1)]">{category}</h2>
                <p className="text-xs text-[var(--text-3)]">Risk Analysis and Breakdown</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="rounded-lg p-2 text-[var(--text-3)] transition-colors hover:bg-white/5 hover:text-[var(--text-1)]"
              aria-label="Close popup"
            >
              <X size={20} />
            </button>
          </div>

          <div className="max-h-[calc(88vh-74px)] space-y-6 overflow-y-auto px-5 py-5 sm:px-6 sm:py-6">
            <div className="py-2 text-center">
              <div
                className="mb-3 inline-flex h-24 w-24 items-center justify-center rounded-full border-4"
                style={{ borderColor: ringColor }}
              >
                <span className="text-3xl font-black" style={{ color: ringColor }}>
                  {data.compositeRisk}%
                </span>
              </div>
              <p className="text-sm font-bold uppercase tracking-wider" style={{ color: ringColor }}>
                {riskLabel(data.compositeRisk)} Risk
              </p>
              <p className="mt-1 text-xs text-[var(--text-3)]">
                Composite score = 0.6 x Inventory + 0.4 x Uncertainty
              </p>
            </div>

            <Section title="Risk Factor Breakdown" icon={<AlertTriangle size={16} />}>
              <RiskBar label="Inventory Risk" value={riskPctInv} weight="60%" color={riskColor(riskPctInv)} />
              <RiskBar label="Uncertainty Risk" value={riskPctUnc} weight="40%" color={riskColor(riskPctUnc)} />
              <p className="mt-2 text-[10px] leading-relaxed text-[var(--text-3)]">
                Inventory risk measures how far below the reorder point current stock sits.
                Uncertainty risk measures demand volatility (coefficient of variation).
              </p>
            </Section>

            <Section title="Why Risk Is Elevated" icon={<ShieldAlert size={16} />}>
              <ul className="space-y-2">
                {data.reasons.map((reason, index) => (
                  <li key={index} className="flex items-start gap-2.5 text-sm text-[var(--text-2)]">
                    <span
                      className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full"
                      style={{ backgroundColor: ringColor }}
                    />
                    {reason}
                  </li>
                ))}
              </ul>
            </Section>

            <Section title="Inventory Gap" icon={<PackageX size={16} />}>
              <div className="space-y-3">
                <div className="flex justify-between text-xs text-[var(--text-3)]">
                  <span>
                    Current: <span className="font-bold text-[var(--text-1)]">{data.currentStock.toLocaleString()}</span>
                  </span>
                  <span>
                    Required: <span className="font-bold text-[var(--text-1)]">{data.requiredStock.toLocaleString()}</span>
                  </span>
                </div>
                <div className="relative h-3 overflow-hidden rounded-full bg-white/5">
                  <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{
                      width: `${stockPct}%`,
                      backgroundColor: stockPct >= 90 ? '#10B981' : stockPct >= 60 ? '#F59E0B' : '#EF4444',
                    }}
                  />
                  {data.requiredStock > 0 && (
                    <div
                      className="absolute top-0 h-full w-0.5 bg-cyan-300"
                      style={{ left: `${pct(data.reorderPoint, data.requiredStock)}%` }}
                      title={`Reorder Point: ${data.reorderPoint}`}
                    />
                  )}
                </div>
                <div className="flex justify-between text-[10px] text-[var(--text-3)]">
                  <span>{stockPct}% filled</span>
                  <span className="text-cyan-300">Reorder Pt: {data.reorderPoint.toLocaleString()}</span>
                </div>
                {gap > 0 && (
                  <div className="flex items-center gap-2 rounded-lg border border-red-500/15 bg-red-500/5 p-3 text-sm">
                    <PackageX size={14} className="shrink-0 text-red-400" />
                    <span className="text-[var(--badge-danger-text)]">
                      Deficit of <span className="font-bold">{gap.toLocaleString()}</span> units to reach required level
                    </span>
                  </div>
                )}
              </div>
            </Section>

            <Section title="Forecast Impact" icon={<TrendingUp size={16} />}>
              <div className="mb-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
                <MiniStat label="30D Demand" value={data.forecast30d.toLocaleString()} />
                <MiniStat label="Daily Avg" value={data.dailyAvgDemand.toLocaleString()} />
                <MiniStat label="Std Dev" value={`+/-${data.demandStdDev}`} />
              </div>
            </Section>

            <Section title="Reorder Breach Status" icon={<Target size={16} />}>
              <div
                className={`mb-3 flex items-center gap-3 rounded-xl border p-3.5 ${
                  data.reorderBreach.breached
                    ? 'border-red-500/20 bg-red-500/5'
                    : 'border-emerald-500/20 bg-emerald-500/5'
                }`}
              >
                <div className={`rounded-lg p-2 ${data.reorderBreach.breached ? 'bg-red-500/15' : 'bg-emerald-500/15'}`}>
                  <Target size={16} className={data.reorderBreach.breached ? 'text-red-400' : 'text-emerald-400'} />
                </div>
                <div>
                  <p
                    className={`text-sm font-bold ${
                      data.reorderBreach.breached ? 'text-[var(--badge-danger-text)]' : 'text-[var(--badge-success-text)]'
                    }`}
                  >
                    {data.reorderBreach.breached ? 'Below Reorder Point' : 'No Breach'}
                  </p>
                  {data.reorderBreach.breached && data.reorderBreach.deficit > 0 && (
                    <p className="mt-0.5 text-xs text-[var(--text-3)]">
                      {data.reorderBreach.deficit.toLocaleString()} units below reorder point
                    </p>
                  )}
                </div>
              </div>
              <p className="text-sm leading-relaxed text-[var(--text-3)]">{data.reorderBreach.explanation}</p>
              <div className="mt-3 flex items-center gap-2 text-xs text-[var(--text-3)]">
                <Clock size={12} />
                <span>
                  Days until stockout:{' '}
                  <span className="font-bold text-[var(--text-1)]">
                    {data.daysUntilStockout > 900 ? 'N/A' : data.daysUntilStockout}
                  </span>
                </span>
                <span className="mx-1">|</span>
                <Shield size={12} />
                <span>
                  Safety stock:{' '}
                  <span className="font-bold text-[var(--text-1)]">{data.safetyStock.toLocaleString()}</span>
                </span>
              </div>
            </Section>

            <div className="rounded-xl border border-blue-500/20 bg-gradient-to-r from-blue-500/10 to-cyan-500/10 p-4">
              <div className="flex items-center gap-3">
                <div className="shrink-0 rounded-xl bg-blue-500/15 p-2.5">
                  <BarChart3 size={20} className="text-blue-400" />
                </div>
                <div className="flex-1">
                  <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-3)]">Recommended Action</p>
                  <p className="text-base font-bold text-[var(--text-1)]">{data.recommendedAction}</p>
                </div>
                <ArrowRight size={18} className="text-[var(--text-3)]" />
              </div>
              {data.orderQty > 0 && (
                <div className="mt-3 flex items-center justify-between border-t border-[var(--border-soft)] pt-3 text-sm">
                  <span className="text-[var(--text-3)]">Order quantity</span>
                  <span className="font-mono font-bold text-[var(--text-1)]">{data.orderQty.toLocaleString()} units</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </>,
    document.body
  );
};

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
    <div className="mb-1.5 flex items-center justify-between text-xs">
      <span className="text-[var(--text-3)]">
        {label} <span className="text-[var(--text-3)]">({weight})</span>
      </span>
      <span className="font-mono font-bold" style={{ color }}>
        {value}%
      </span>
    </div>
    <div className="h-2 overflow-hidden rounded-full bg-white/5">
      <div
        className="h-full rounded-full transition-all duration-700"
        style={{ width: `${value}%`, backgroundColor: color }}
      />
    </div>
  </div>
);

const MiniStat = ({ label, value }) => (
  <div className="rounded-lg border border-[var(--border-soft)] bg-[color-mix(in_srgb,var(--bg-elevated)_76%,transparent)] p-2.5 text-center">
    <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-3)]">{label}</p>
    <p className="mt-0.5 font-mono text-sm font-bold text-[var(--text-1)]">{value}</p>
  </div>
);

export default RiskDrawer;
