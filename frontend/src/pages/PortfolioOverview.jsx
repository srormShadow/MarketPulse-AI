import { useEffect, useMemo, useState } from 'react';
import {
  ShieldAlert, PackageX, TrendingUp, Layers,
  Activity, AlertTriangle, BarChart3, ChevronRight,
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, Legend,
} from 'recharts';
import GlassCard from '../components/ui/GlassCard';
import StatCard from '../components/ui/StatCard';
import RiskDrawer from '../components/ui/RiskDrawer';
import FestivalCalendar from '../components/festival/FestivalCalendar';
import EmptyDashboardState from '../components/EmptyDashboardState';
import { apiClient } from '../api/client';
import { useInventory } from '../context/inventoryStore';

const chartTheme = {
  grid: 'color-mix(in srgb, var(--text-3) 24%, transparent)',
  axis: 'color-mix(in srgb, var(--text-3) 40%, transparent)',
  tick: 'var(--text-3)',
  label: 'var(--text-1)',
  cursor: 'color-mix(in srgb, var(--brand-2) 10%, transparent)',
};

const tooltipStyle = {
  backgroundColor: 'var(--panel)',
  border: '1px solid var(--border)',
  borderRadius: 10,
  color: 'var(--text-1)',
  fontSize: 12,
  boxShadow: '0 12px 24px rgba(5, 3, 14, 0.2)',
};

const riskColor = (score01) => {
  const score = Math.max(0, Math.min(100, (score01 || 0) * 100));
  return score >= 60 ? '#EF4444' : score >= 25 ? '#F59E0B' : '#10B981';
};

const actionStyleMap = {
  URGENT_ORDER: 'bg-red-500/16 text-[var(--badge-danger-text)] border-red-500/40',
  ORDER: 'bg-amber-500/16 text-[var(--badge-warning-text)] border-amber-500/40',
  MONITOR: 'bg-blue-500/16 text-[var(--badge-info-text)] border-blue-500/40',
  MAINTAIN: 'bg-emerald-500/16 text-[var(--badge-success-text)] border-emerald-500/40',
  INSUFFICIENT_DATA: 'bg-slate-500/16 text-[var(--badge-neutral-text)] border-slate-500/40',
};

const inventoryStatus = (gap, action) => {
  if (action === 'URGENT_ORDER' || gap > 0.4) return 'critical';
  if (action === 'ORDER' || gap > 0.1) return 'warning';
  return 'healthy';
};

const statusStyles = {
  healthy: 'bg-emerald-500/10 text-[var(--badge-success-text)] border-emerald-500/20',
  warning: 'bg-amber-500/10 text-[var(--badge-warning-text)] border-amber-500/20',
  critical: 'bg-red-500/10 text-[var(--badge-danger-text)] border-red-500/20',
};

const StatusBadge = ({ status }) => (
  <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold border uppercase tracking-wider ${statusStyles[status]}`}>
    {status}
  </span>
);

const ActionBadge = ({ action }) => (
  <span className={`px-3 py-1 rounded-full text-[10px] font-bold border uppercase tracking-wider ${actionStyleMap[action] || actionStyleMap.INSUFFICIENT_DATA}`}>
    {action}
  </span>
);

const PortfolioOverview = () => {
  const { categories, inventory, leadTimes, onboarding, loading: inventoryLoading } = useInventory();
  const [drawerRow, setDrawerRow] = useState(null);
  const [forecastRows, setForecastRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!categories.length) {
      setForecastRows([]);
      setLoading(false);
      return undefined;
    }
    let cancelled = false;

    const loadPortfolio = async () => {
      setLoading(true);
      setError('');
      try {
        const batchRes = await apiClient.post('/forecast/batch', {
          categories,
          n_days: 60,
          inventory,
          lead_times: leadTimes,
        });

        if (cancelled) return;

        setForecastRows(Array.isArray(batchRes.data) ? batchRes.data : []);
      } catch (err) {
        if (cancelled) return;
        setError(err?.response?.data?.message || 'Unable to load portfolio data from backend.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    loadPortfolio();
    return () => {
      cancelled = true;
    };
  }, [categories, inventory, leadTimes]);

  const derived = useMemo(() => {
    const rows = forecastRows.map((row) => {
      const category = row?.category || 'Unknown';
      const forecast = Array.isArray(row?.forecast) ? row.forecast : [];
      const decision = row?.decision || {};
      const riskScore = Number(decision?.risk_score || 0);
      const action = decision?.recommended_action || 'INSUFFICIENT_DATA';
      const forecast30 = forecast.slice(30, 60).reduce((sum, p) => sum + Number(p?.predicted_mean || 0), 0);
      const previous30 = forecast.slice(0, 30).reduce((sum, p) => sum + Number(p?.predicted_mean || 0), 0);
      const pctChange = previous30 > 0 ? ((forecast30 - previous30) / previous30) * 100 : 0;
      const reorderPoint = Number(decision?.reorder_point || 0);
      const safetyStock = Number(decision?.safety_stock || 0);
      const currentStock = Number(inventory[category] || 0);
      const leadTime = Number(leadTimes[category] || 0);
      const requiredStock = Math.max(reorderPoint, safetyStock);
      const gapRatio = requiredStock > 0 ? Math.max(0, (requiredStock - currentStock) / requiredStock) : 0;

      return {
        category,
        forecast,
        action,
        riskScore,
        reorderPoint,
        safetyStock,
        currentStock,
        requiredStock,
        leadTime,
        orderQuantity: Number(decision?.order_quantity || 0),
        status: inventoryStatus(gapRatio, action),
        pctChange,
      };
    });

    const urgentRows = rows.filter((r) => r.action === 'URGENT_ORDER');
    const orderRows = rows.filter((r) => r.action === 'ORDER');
    const requiresOrdering = rows.filter((r) => r.action === 'URGENT_ORDER' || r.action === 'ORDER');

    const highestRisk = [...rows].sort((a, b) => b.riskScore - a.riskScore)[0];
    const totalForecast30 = rows.reduce((sum, r) => {
      return sum + r.forecast.slice(30, 60).reduce((s, p) => s + Number(p?.predicted_mean || 0), 0);
    }, 0);
    const totalPrevious30 = rows.reduce((sum, r) => {
      return sum + r.forecast.slice(0, 30).reduce((s, p) => s + Number(p?.predicted_mean || 0), 0);
    }, 0);
    const networkForecastDeltaPct = totalPrevious30 > 0 ? ((totalForecast30 - totalPrevious30) / totalPrevious30) * 100 : 0;
    const totalInventoryGap = rows.reduce((sum, r) => sum + Math.max(0, r.requiredStock - r.currentStock), 0);

    return {
      rows,
      kpis: {
        forecast30: Math.round(totalForecast30),
        forecastDeltaPct: networkForecastDeltaPct,
        highestRiskCategory: highestRisk?.category || 'n/a',
        highestRiskScore: highestRisk?.riskScore || 0,
        inventoryGap: Math.round(totalInventoryGap),
        activeCategories: rows.length,
      },
      action: {
        urgentCount: urgentRows.length,
        orderCount: orderRows.length,
        requiresOrderingCount: requiresOrdering.length,
        criticalCategory: urgentRows[0]?.category || orderRows[0]?.category || null,
        severity: urgentRows.length > 0 ? 'urgent' : (orderRows.length > 0 ? 'order' : 'ok'),
      },
    };
  }, [forecastRows, inventory, leadTimes]);

  const riskDistributionData = useMemo(() => {
    return derived.rows.map((r) => ({
      category: r.category,
      riskScore: Math.round(r.riskScore * 100),
      fill: riskColor(r.riskScore),
    }));
  }, [derived.rows]);

  const inventoryGapData = useMemo(() => {
    return derived.rows.map((r) => ({
      category: r.category,
      current: r.currentStock,
      required: Math.round(r.requiredStock),
    }));
  }, [derived.rows]);

  const actionBanner = useMemo(() => {
    const orderingCount = derived.action.requiresOrderingCount;
    const criticalCount = derived.action.urgentCount;
    if (derived.action.severity === 'urgent') {
      return {
        style: 'border-red-500/35 bg-red-500/10 text-[var(--badge-danger-text)]',
        message: `Warning: ${orderingCount} categories need ordering, ${criticalCount} critical - ${derived.action.criticalCategory} is critical`,
      };
    }
    if (derived.action.severity === 'order') {
      return {
        style: 'border-amber-500/35 bg-amber-500/10 text-[var(--badge-warning-text)]',
        message: `${orderingCount} categories need ordering, ${criticalCount} critical - prioritize ${derived.action.criticalCategory}`,
      };
    }
    return {
      style: 'border-emerald-500/35 bg-emerald-500/10 text-[var(--badge-success-text)]',
      message: '0 categories need ordering, 0 critical - all categories are MONITOR/MAINTAIN',
    };
  }, [derived.action]);

  if (inventoryLoading) {
    return <div className="text-sm text-[var(--text-3)]">Loading workspace...</div>;
  }

  if (!categories.length) {
    return <EmptyDashboardState onboarding={onboarding} />;
  }

  if (loading) {
    return <div className="text-sm text-[var(--text-3)]">Loading portfolio data...</div>;
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-[var(--badge-danger-text)]">
          {error}
        </div>
      )}

      <div className={`rounded-xl border px-4 py-3 text-sm font-semibold ${actionBanner.style}`}>
        {actionBanner.message}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="30D Forecast"
          value={derived.kpis.forecast30.toLocaleString()}
          trend={derived.kpis.forecastDeltaPct >= 0 ? 'up' : 'down'}
          trendValue={`${derived.kpis.forecastDeltaPct >= 0 ? '+' : ''}${derived.kpis.forecastDeltaPct.toFixed(1)}%`}
          context="vs prior 30-day forecast window"
          accentColor="blue"
          icon={<TrendingUp />}
        />
        <StatCard
          label="Network Risk"
          value={`${Math.round(derived.kpis.highestRiskScore * 100)}`}
          trend={derived.kpis.highestRiskScore >= 0.6 ? 'up' : 'neutral'}
          trendValue={derived.kpis.highestRiskScore >= 0.6 ? 'elevated' : 'stable'}
          context={`driven by ${derived.kpis.highestRiskCategory}`}
          accentColor={derived.kpis.highestRiskScore >= 0.6 ? 'red' : 'amber'}
          icon={<ShieldAlert />}
        />
        <StatCard
          label="Inventory Gap"
          value={derived.kpis.inventoryGap.toLocaleString()}
          trend={derived.kpis.inventoryGap > 0 ? 'up' : 'neutral'}
          trendValue={derived.kpis.inventoryGap > 0 ? 'needs action' : 'balanced'}
          context={`across ${derived.kpis.activeCategories} categories`}
          accentColor={derived.kpis.inventoryGap > 0 ? 'red' : 'emerald'}
          icon={<PackageX />}
        />
        <StatCard
          label="Active Categories"
          value={String(derived.kpis.activeCategories)}
          trend="neutral"
          context="models trained"
          accentColor="emerald"
          icon={<Layers />}
        />
      </div>

      <GlassCard
        title="Inventory Health Portfolio"
        subtitle="Category-level view with recommended actions from batch forecast"
        icon={<Activity size={18} />}
      >
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[var(--text-3)] text-xs uppercase tracking-wider border-b border-[var(--border-soft)]">
                <th className="pb-3 pr-6 font-semibold">Category</th>
                <th className="pb-3 pr-6 font-semibold">Recommended Action</th>
                <th className="pb-3 pr-6 font-semibold">Status</th>
                <th className="pb-3 pr-6 font-semibold text-right">Current</th>
                <th className="pb-3 pr-6 font-semibold text-right">Required</th>
                <th className="pb-3 pr-6 font-semibold text-right">Safety Stock</th>
                <th className="pb-3 pr-6 font-semibold text-right">Reorder Pt</th>
                <th className="pb-3 pr-6 font-semibold text-right">Lead Time</th>
                <th className="pb-3 font-semibold text-right">Risk</th>
                <th className="pb-3 w-8"></th>
              </tr>
            </thead>
            <tbody>
              {derived.rows.map((row) => {
                return (
                  <tr
                    key={row.category}
                    onClick={() => setDrawerRow(row)}
                    className="border-b border-[var(--border-soft)] transition-colors cursor-pointer hover:bg-white/[0.04] group"
                  >
                    <td className="py-4 pr-6 font-semibold text-[var(--text-1)]">{row.category}</td>
                    <td className="py-4 pr-6">
                      <ActionBadge action={row.action} />
                    </td>
                    <td className="py-4 pr-6"><StatusBadge status={row.status} /></td>
                    <td className="py-4 pr-6 text-right font-mono text-[var(--text-1)]">{row.currentStock.toLocaleString()}</td>
                    <td className="py-4 pr-6 text-right font-mono text-[var(--text-3)]">{Math.round(row.requiredStock).toLocaleString()}</td>
                    <td className="py-4 pr-6 text-right font-mono text-[var(--text-3)]">{Math.round(row.safetyStock).toLocaleString()}</td>
                    <td className="py-4 pr-6 text-right font-mono text-[var(--text-3)]">{Math.round(row.reorderPoint).toLocaleString()}</td>
                    <td className="py-4 pr-6 text-right font-mono text-[var(--text-3)]">{row.leadTime}d</td>
                    <td className="py-4 text-right">
                      <div className="flex items-center gap-2 justify-end">
                        <div className="w-16 h-1.5 rounded-full bg-white/5 overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all duration-700"
                            style={{ width: `${Math.round(row.riskScore * 100)}%`, backgroundColor: riskColor(row.riskScore) }}
                          />
                        </div>
                        <span className="font-mono text-xs font-bold w-8 text-right" style={{ color: riskColor(row.riskScore) }}>
                          {Math.round(row.riskScore * 100)}%
                        </span>
                      </div>
                    </td>
                    <td className="py-4 pl-2 w-8">
                      <ChevronRight size={14} className="text-[var(--text-3)] group-hover:text-[var(--text-3)] transition-colors" />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </GlassCard>

      <FestivalCalendar variant="compact" />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <GlassCard
          title="Risk Distribution"
          subtitle="Category risk scores"
          icon={<AlertTriangle size={18} />}
        >
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={riskDistributionData}
                layout="vertical"
                margin={{ top: 10, right: 26, left: 64, bottom: 10 }}
              >
                <CartesianGrid strokeDasharray="4 8" stroke={chartTheme.grid} horizontal={false} />
                <XAxis
                  type="number"
                  domain={[0, 100]}
                  tick={{ fill: chartTheme.tick, fontSize: 12 }}
                  axisLine={{ stroke: chartTheme.axis }}
                  tickLine={false}
                  tickFormatter={(v) => `${v}%`}
                />
                <YAxis
                  dataKey="category"
                  type="category"
                  tick={{ fill: chartTheme.label, fontSize: 12, fontWeight: 600 }}
                  axisLine={false}
                  tickLine={false}
                  width={72}
                />
                <Tooltip contentStyle={tooltipStyle} itemStyle={{ color: 'var(--text-1)' }} labelStyle={{ color: 'var(--text-1)', fontWeight: 700 }} cursor={{ fill: chartTheme.cursor }} formatter={(v) => [`${v}%`, 'Risk Score']} />
                <Bar dataKey="riskScore" name="Risk Score" radius={[0, 10, 10, 0]} barSize={20}>
                  {riskDistributionData.map((entry, index) => (
                    <Cell key={index} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </GlassCard>

        <GlassCard
          title="Inventory Gaps"
          subtitle="Current vs required stock levels"
          icon={<BarChart3 size={18} />}
        >
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={inventoryGapData} margin={{ top: 10, right: 22, left: 10, bottom: 10 }}>
                <CartesianGrid strokeDasharray="4 8" stroke={chartTheme.grid} />
                <XAxis
                  dataKey="category"
                  tick={{ fill: chartTheme.label, fontSize: 12 }}
                  axisLine={{ stroke: chartTheme.axis }}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: chartTheme.tick, fontSize: 12 }}
                  axisLine={{ stroke: chartTheme.axis }}
                  tickLine={false}
                />
                <Tooltip contentStyle={tooltipStyle} itemStyle={{ color: 'var(--text-1)' }} labelStyle={{ color: 'var(--text-1)', fontWeight: 700 }} cursor={{ fill: chartTheme.cursor }} />
                <Legend wrapperStyle={{ fontSize: 12, color: 'var(--text-3)' }} iconType="circle" iconSize={8} />
                <Bar dataKey="current" name="Current Stock" fill="url(#gapBarPrimary)" radius={[8, 8, 0, 0]} barSize={24} />
                <Bar dataKey="required" name="Required Stock" fill="url(#gapBarSecondary)" radius={[8, 8, 0, 0]} barSize={24} />
                <defs>
                  <linearGradient id="gapBarPrimary" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.95} />
                    <stop offset="100%" stopColor="#1d4ed8" stopOpacity={0.6} />
                  </linearGradient>
                  <linearGradient id="gapBarSecondary" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#f472b6" stopOpacity={0.9} />
                    <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.45} />
                  </linearGradient>
                </defs>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </GlassCard>
      </div>

      {drawerRow && (
        <RiskDrawer
          category={drawerRow.category}
          rowData={drawerRow}
          onClose={() => setDrawerRow(null)}
        />
      )}
    </div>
  );
};

export default PortfolioOverview;




