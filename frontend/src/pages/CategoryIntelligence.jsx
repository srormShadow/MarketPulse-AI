import { useEffect, useMemo, useState } from 'react';
import {
  ShoppingCart, TrendingUp, Shield, Target, ChevronDown, Bot,
  Sparkles, AlertTriangle, Clock3,
} from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, BarChart, Bar, Cell,
} from 'recharts';
import GlassCard from '../components/ui/GlassCard';
import { apiClient } from '../api/client';
import { useInventory } from '../context/InventoryContext';

const chartTheme = {
  grid: 'color-mix(in srgb, var(--text-3) 24%, transparent)',
  axis: 'color-mix(in srgb, var(--text-3) 42%, transparent)',
  tick: 'var(--text-3)',
  label: 'var(--text-1)',
  cursor: 'color-mix(in srgb, var(--brand-2) 12%, transparent)',
};

const ACTION_STYLES = {
  URGENT_ORDER: 'bg-red-500/16 text-[var(--badge-danger-text)] border-red-500/30',
  ORDER: 'bg-amber-500/16 text-[var(--badge-warning-text)] border-amber-500/30',
  MONITOR: 'bg-blue-500/16 text-[var(--badge-info-text)] border-blue-500/30',
  MAINTAIN: 'bg-emerald-500/16 text-[var(--badge-success-text)] border-emerald-500/30',
  INSUFFICIENT_DATA: 'bg-slate-500/16 text-[var(--badge-neutral-text)] border-slate-500/30',
};

const FEATURE_LABELS = {
  lag_1: 'Yesterday\u2019s Sales',
  lag_7: 'Same Day Last Week',
  festival_score: 'Festival Impact',
  rolling_mean_7: '7-Day Avg Demand',
  weekday: 'Day of Week',
};

const DEFAULT_FEATURES = [
  { key: 'lag_1', value: 0.32 },
  { key: 'lag_7', value: 0.21 },
  { key: 'festival_score', value: 0.19 },
  { key: 'rolling_mean_7', value: 0.18 },
  { key: 'weekday', value: 0.10 },
];

const riskColor = (score01) => {
  const pct = Math.round((score01 || 0) * 100);
  if (pct >= 70) return '#EF4444';
  if (pct >= 50) return '#F59E0B';
  return '#10B981';
};

const formatDate = (value) => {
  try {
    return new Date(value).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });
  } catch {
    return value;
  }
};

const toSafeIso = (v) => {
  try {
    return new Date(v).toISOString().slice(0, 10);
  } catch {
    return '';
  }
};

const CategoryIntelligence = () => {
  const { categories: CATEGORIES, inventory: INVENTORY, leadTimes: LEAD_TIMES } = useInventory();
  const [selectedCategory, setSelectedCategory] = useState('Snacks');
  const [forecastResponse, setForecastResponse] = useState(null);
  const [festivals, setFestivals] = useState([]);
  const [insight, setInsight] = useState('');
  const [insightTimestamp, setInsightTimestamp] = useState('');
  const [insightLoading, setInsightLoading] = useState(false);
  const [forecastLoading, setForecastLoading] = useState(true);
  const [featureInfluence, setFeatureInfluence] = useState(DEFAULT_FEATURES);
  const [featureFallback, setFeatureFallback] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const loadCategoryData = async () => {
      setForecastLoading(true);
      setInsightLoading(true);
      setFeatureFallback(false);

      try {
        const [forecastRes, festivalRes] = await Promise.all([
          apiClient.post(`/forecast/${encodeURIComponent(selectedCategory)}`, {
            n_days: 30,
            current_inventory: INVENTORY[selectedCategory] || 0,
            lead_time_days: LEAD_TIMES[selectedCategory] || 7,
          }),
          apiClient.get('/festivals'),
        ]);

        if (cancelled) return;

        const forecastData = forecastRes?.data || null;
        setForecastResponse(forecastData);
        setFestivals(Array.isArray(festivalRes?.data?.items) ? festivalRes.data.items : []);

        try {
          const insightRes = await apiClient.post(`/insights/${encodeURIComponent(selectedCategory)}`, {
            forecast_data: forecastData?.forecast || [],
            decision_data: forecastData?.decision || {},
            festival_context: festivalRes?.data?.items || [],
          });
          if (!cancelled) {
            setInsight(String(insightRes?.data?.insight || 'No insight returned by Bedrock.'));
            setInsightTimestamp(String(insightRes?.data?.generated_at || ''));
          }
        } catch {
          if (!cancelled) {
            setInsight('AI insight is temporarily unavailable. Continue with forecast and decision metrics below.');
            setInsightTimestamp(new Date().toISOString());
          }
        }

        try {
          const diagnosticsRes = await apiClient.get(`/diagnostics/${encodeURIComponent(selectedCategory)}`);
          const coeffs = diagnosticsRes?.data?.coefficients || diagnosticsRes?.data?.feature_influence || {};
          const rows = ['lag_1', 'lag_7', 'festival_score', 'rolling_mean_7', 'weekday'].map((k) => ({
            key: k,
            value: Number(coeffs[k] ?? 0),
          }));
          if (!cancelled) {
            setFeatureInfluence(rows);
          }
        } catch {
          if (!cancelled) {
            setFeatureFallback(true);
            setFeatureInfluence(DEFAULT_FEATURES);
          }
        }
      } finally {
        if (!cancelled) {
          setForecastLoading(false);
          setInsightLoading(false);
        }
      }
    };

    loadCategoryData();

    return () => {
      cancelled = true;
    };
  }, [selectedCategory]);

  const chartData = useMemo(() => {
    const forecast = Array.isArray(forecastResponse?.forecast) ? forecastResponse.forecast : [];
    return forecast.map((point, idx) => {
      const day = idx + 1;
      const predicted = Number(point?.predicted_mean || 0);
      return {
        date: point?.date,
        label: formatDate(point?.date),
        predicted_mean: predicted,
        lower_95: Number(point?.lower_95 || 0),
        upper_95: Number(point?.upper_95 || 0),
        high_conf: day <= 7 ? predicted : null,
        medium_conf: day > 7 && day <= 14 ? predicted : null,
        low_conf: day > 14 ? predicted : null,
      };
    });
  }, [forecastResponse]);

  const festivalMarkers = useMemo(() => {
    if (!chartData.length) return [];
    const chartDates = new Set(chartData.map((d) => toSafeIso(d.date)));
    return festivals
      .map((f) => {
        const uplift = Number(f?.historical_uplift || 0);
        const inferredScore = Math.min(1, uplift * 2);
        return {
          name: f?.festival_name || 'Festival',
          date: toSafeIso(f?.date),
          category: f?.category || 'general',
          uplift,
          inferredScore,
        };
      })
      .filter((f) => f.inferredScore > 0.5 && chartDates.has(f.date));
  }, [chartData, festivals]);

  const festivalByDate = useMemo(() => {
    const map = {};
    festivalMarkers.forEach((f) => {
      map[f.date] = f;
    });
    return map;
  }, [festivalMarkers]);

  const decision = forecastResponse?.decision || {};
  const leadTime = LEAD_TIMES[selectedCategory] || 7;
  const expectedLeadDemand = useMemo(() => {
    return chartData.slice(0, leadTime).reduce((sum, r) => sum + Number(r.predicted_mean || 0), 0);
  }, [chartData, leadTime]);
  const currentStock = INVENTORY[selectedCategory] || 0;
  const stockGap = Math.max(0, Math.round(expectedLeadDemand - currentStock));

  const featureChartData = useMemo(() => {
    return featureInfluence.map((f) => ({
      feature: FEATURE_LABELS[f.key] || f.key,
      influence: Math.abs(Number(f.value || 0)),
      raw: Number(f.value || 0),
    }));
  }, [featureInfluence]);

  if (forecastLoading) {
    return <div className="text-sm text-[var(--text-3)]">Loading category intelligence...</div>;
  }

  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    const dayFestival = festivalByDate[toSafeIso(label)];
    return (
      <div className="glass-card px-4 py-3 shadow-xl border border-[var(--border)] text-xs">
        <p className="text-[var(--text-3)] font-semibold mb-1.5">{formatDate(label)}</p>
        {payload.map((entry, i) => (
          entry.value != null && (
            <div key={i} className="flex items-center gap-2 py-0.5">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.stroke || entry.color }} />
              <span className="text-[var(--text-3)]">{entry.name}:</span>
              <span className="text-[var(--text-1)] font-bold">{Math.round(entry.value).toLocaleString()}</span>
            </div>
          )
        ))}
        {dayFestival && (
          <p className="mt-2 text-[var(--badge-warning-text)]">
            Festival: {dayFestival.name} - expect +{Math.round(dayFestival.uplift * 100)}% demand spike
          </p>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="relative">
          <ShoppingCart size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-blue-400 pointer-events-none z-10" />
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="appearance-none bg-[var(--bg-soft)] text-[var(--text-1)] border border-[var(--border)] rounded-xl pl-10 pr-10 py-2.5 outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500/30 text-sm font-semibold transition-all cursor-pointer w-56"
          >
            {CATEGORIES.map((cat) => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
          <ChevronDown size={16} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-[var(--text-3)] pointer-events-none" />
        </div>
        <span className={`px-3 py-1 rounded-full text-[10px] font-bold border uppercase tracking-wider ${ACTION_STYLES[decision?.recommended_action] || ACTION_STYLES.INSUFFICIENT_DATA}`}>
          {decision?.recommended_action || 'INSUFFICIENT_DATA'}
        </span>
      </div>

      <GlassCard
        title="Bedrock AI Insight"
        subtitle="Actionable recommendation for this category"
        icon={<Bot size={18} />}
      >
        <div className="rounded-xl border border-sky-500/30 bg-sky-500/12 p-4">
          <div className="flex items-center justify-between gap-3 mb-2">
            <p className="text-[10px] uppercase tracking-wider font-bold text-[var(--badge-info-text)] flex items-center gap-1.5">
              <Sparkles size={12} />
              AI Generated Insight • Amazon Bedrock
            </p>
            {insightTimestamp && (
              <p className="text-[11px] text-[var(--text-3)] flex items-center gap-1">
                <Clock3 size={12} />
                {new Date(insightTimestamp).toLocaleString('en-IN')}
              </p>
            )}
          </div>
          <p className="text-sm text-[var(--text-1)] leading-relaxed">
            {insightLoading ? 'Generating Bedrock insight...' : insight}
          </p>
        </div>
      </GlassCard>

      <GlassCard
        title="Demand Forecast Visualization"
        subtitle={`${selectedCategory} — horizon confidence, uncertainty and festival events`}
        icon={<TrendingUp size={18} />}
      >
        <div className="h-[390px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 10, right: 18, left: 6, bottom: 4 }}>
              <defs>
                <linearGradient id="confidenceBand" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#f472b6" stopOpacity={0.28} />
                  <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.02} />
                </linearGradient>
                <linearGradient id="forecastGlow" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#f472b6" />
                  <stop offset="55%" stopColor="#a78bfa" />
                  <stop offset="100%" stopColor="#22d3ee" />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="4 8" stroke={chartTheme.grid} />
              <XAxis
                dataKey="date"
                tickFormatter={formatDate}
                tick={{ fill: chartTheme.tick, fontSize: 11 }}
                axisLine={{ stroke: chartTheme.axis }}
                tickLine={false}
                interval={4}
              />
              <YAxis
                tick={{ fill: chartTheme.tick, fontSize: 11 }}
                axisLine={{ stroke: chartTheme.axis }}
                tickLine={false}
                width={45}
              />
              <Tooltip content={<CustomTooltip />} cursor={{ stroke: chartTheme.axis, fill: 'none' }} />

              <Area type="monotone" dataKey="upper_95" stroke="none" fill="url(#confidenceBand)" fillOpacity={1} name="Upper 95%" dot={false} />
              <Area type="monotone" dataKey="lower_95" stroke="color-mix(in srgb, var(--brand-2) 38%, transparent)" strokeWidth={1} strokeDasharray="4 4" fill="transparent" fillOpacity={1} name="Lower 95%" dot={false} />

              <Area type="monotone" dataKey="high_conf" stroke="url(#forecastGlow)" strokeWidth={3.4} fill="none" name="Forecast (Days 1-7)" dot={{ r: 2.5, fill: '#f472b6', strokeWidth: 0 }} activeDot={{ r: 5, fill: '#f472b6' }} connectNulls={false} />
              <Area type="monotone" dataKey="medium_conf" stroke="url(#forecastGlow)" strokeOpacity={0.7} strokeWidth={2.7} fill="none" name="Forecast (Days 8-14)" dot={false} connectNulls={false} />
              <Area type="monotone" dataKey="low_conf" stroke="url(#forecastGlow)" strokeOpacity={0.38} strokeWidth={2.2} fill="none" name="Forecast (Days 15+)" dot={false} connectNulls={false} />

              {festivalMarkers.map((festival) => (
                <ReferenceLine
                  key={`${festival.name}-${festival.date}`}
                  x={festival.date}
                  stroke="#f59e0b"
                  strokeDasharray="5 5"
                  label={{ value: festival.name, fill: '#fbbf24', fontSize: 10, position: 'top' }}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="flex items-center flex-wrap gap-5 mt-4 px-2 text-xs text-[var(--text-3)]">
          <div className="flex items-center gap-2">
            <div className="w-6 h-0.5 bg-[#A78BFA]" />
            <span>Days 1-7: high confidence</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-6 h-0.5 bg-[#A78BFA]/70" />
            <span>Days 8-14: medium confidence</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-6 h-0.5 bg-[#A78BFA]/40" />
            <span>Days 15+: lower confidence</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-3 w-[2px] bg-amber-400" />
            <span>Festival markers</span>
          </div>
        </div>
      </GlassCard>

      <GlassCard
        title="What's driving this forecast"
        subtitle="Feature influence from model diagnostics"
        icon={<Target size={18} />}
      >
        {featureFallback && (
          <p className="text-xs text-[var(--badge-warning-text)] mb-3">
            Diagnostics endpoint unavailable; showing fallback influence profile.
          </p>
        )}
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={featureChartData} layout="vertical" margin={{ top: 8, right: 20, left: 80, bottom: 8 }}>
              <CartesianGrid strokeDasharray="4 8" stroke={chartTheme.grid} horizontal={false} />
              <XAxis type="number" tick={{ fill: chartTheme.tick, fontSize: 12 }} axisLine={{ stroke: chartTheme.axis }} tickLine={false} />
              <YAxis dataKey="feature" type="category" tick={{ fill: chartTheme.label, fontSize: 12 }} axisLine={false} tickLine={false} width={78} />
              <Tooltip
                formatter={(value) => {
                  const v = Number(value);
                  const strength = v >= 12 ? 'Very high influence' : v >= 5 ? 'Moderate influence' : 'Low influence';
                  return [strength, null];
                }}
                contentStyle={{ backgroundColor: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 10, color: 'var(--text-1)', fontSize: 12, boxShadow: '0 12px 24px rgba(5, 3, 14, 0.2)' }}
                itemStyle={{ color: 'var(--text-1)' }}
                labelStyle={{ color: 'var(--text-1)', fontWeight: 700 }}
                cursor={{ fill: chartTheme.cursor }}
              />
              <Bar dataKey="influence" radius={[0, 9, 9, 0]} barSize={16}>
                {featureChartData.map((entry, idx) => (
                  <Cell key={idx} fill={entry.influence >= 12 ? '#EF4444' : entry.influence >= 5 ? '#F59E0B' : '#10B981'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </GlassCard>

      <GlassCard
        title="Decision Detail"
        subtitle="Inventory recommendation breakdown"
        icon={<Shield size={18} />}
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <div className="rounded-xl border border-[var(--border)] bg-[color-mix(in_srgb,var(--bg-elevated)_82%,transparent)] p-4">
            <p className="text-[10px] uppercase tracking-wider text-[var(--text-3)] font-semibold">Reorder Point</p>
            <p className="text-2xl font-bold text-[#C4B5FD] mt-1">{Math.round(Number(decision?.reorder_point || 0)).toLocaleString()}</p>
          </div>
          <div className="rounded-xl border border-[var(--border)] bg-[color-mix(in_srgb,var(--bg-elevated)_82%,transparent)] p-4">
            <p className="text-[10px] uppercase tracking-wider text-[var(--text-3)] font-semibold">Safety Stock</p>
            <p className="text-2xl font-bold text-[var(--badge-success-text)] mt-1">{Math.round(Number(decision?.safety_stock || 0)).toLocaleString()}</p>
          </div>
          <div className="rounded-xl border border-[var(--border)] bg-[color-mix(in_srgb,var(--bg-elevated)_82%,transparent)] p-4">
            <p className="text-[10px] uppercase tracking-wider text-[var(--text-3)] font-semibold">Order Quantity</p>
            <p className="text-2xl font-bold text-[var(--badge-info-text)] mt-1">{Math.round(Number(decision?.order_quantity || 0)).toLocaleString()}</p>
          </div>
        </div>

        <div className="space-y-2 text-sm text-[var(--text-2)]">
          <p>
            Expected demand ({leadTime} days lead time) = <span className="font-semibold text-[var(--text-1)]">{Math.round(expectedLeadDemand).toLocaleString()} units</span>
          </p>
          <p>
            Current stock = <span className="font-semibold text-[var(--text-1)]">{currentStock.toLocaleString()} units</span>. Gap = <span className="font-semibold text-[var(--text-1)]">{stockGap.toLocaleString()} units</span>
          </p>
        </div>

        {decision?.festival_buffer_applied && (
          <div className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-[var(--badge-warning-text)] flex items-center gap-2">
            <AlertTriangle size={14} />
            Festival buffer applied to safety stock due to elevated festival score in lead-time window.
          </div>
        )}
        {decision?.data_stale_warning && (
          <div className="mt-3 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-[var(--badge-danger-text)] flex items-center gap-2">
            <AlertTriangle size={14} />
            Data stale warning: upload fresh sales data (older than 7 days).
          </div>
        )}

        <div className="mt-4">
          <span className={`px-3 py-1 rounded-full text-[10px] font-bold border uppercase tracking-wider ${ACTION_STYLES[decision?.recommended_action] || ACTION_STYLES.INSUFFICIENT_DATA}`}>
            {decision?.recommended_action || 'INSUFFICIENT_DATA'}
          </span>
          <span className="ml-3 text-xs" style={{ color: riskColor(Number(decision?.risk_score || 0)) }}>
            Risk score: {Math.round(Number(decision?.risk_score || 0) * 100)}%
          </span>
        </div>
      </GlassCard>
    </div>
  );
};

export default CategoryIntelligence;



