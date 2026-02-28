import { useState, useMemo } from 'react';
import {
  ShoppingCart, TrendingUp, Shield, Clock, Target,
  AlertCircle, PackageCheck, ArrowRight, ChevronDown,
  Gauge, Activity,
} from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts';
import GlassCard from '../components/ui/GlassCard';
import StatCard from '../components/ui/StatCard';

// ── Category-specific chart parameters ───────────────────────

const categoryChartConfig = {
  Snacks: {
    baseValue: 450, amplitude: 55, trend: 1.8, bandGrowth: 3.5, baseBand: 25,
    noise: [12,-18,25,-8,30,-22,5,18,-15,28,-10,35,-5,20,-25,15,8,-20,32,-12,22,-28,10,26,-16,38,-6,14,-24,19,
            -11,27,-9,33,-17,21,7,-23,29,-14,24,-30,13,31,-7,36,-19,16,9,-21],
  },
  Staples: {
    baseValue: 580, amplitude: 30, trend: 1.2, bandGrowth: 2.0, baseBand: 18,
    noise: [8,-10,15,-5,12,-8,20,-14,6,16,-12,22,-3,10,-18,7,14,-9,18,-6,11,-15,9,13,-7,24,-4,17,-11,8,
            -5,19,-7,14,-10,16,3,-12,20,-8,15,-20,6,22,-9,25,-13,10,4,-16],
  },
  'Edible Oil': {
    baseValue: 320, amplitude: 40, trend: 2.2, bandGrowth: 4.0, baseBand: 30,
    noise: [18,-25,8,-15,35,-10,22,-30,14,40,-20,28,-8,32,-22,10,25,-35,15,-12,30,-18,5,38,-28,12,-5,20,-32,24,
            -15,34,-12,26,-20,18,10,-28,36,-16,22,-38,8,30,-10,42,-24,14,6,-26],
  },
};

// ── Category Profiles ────────────────────────────────────────

const categoryProfiles = {
  Snacks: {
    forecast30d: 5240, safetyStock: 450, orderLeadTime: '5 Days',
    reorderPoint: 3200, riskScore: 78, recommendedAction: 'Urgent Reorder',
    orderQty: 1400, status: 'critical', forecastAccuracy: 92, demandVolatility: 'High',
  },
  Staples: {
    forecast30d: 6100, safetyStock: 800, orderLeadTime: '7 Days',
    reorderPoint: 4400, riskScore: 32, recommendedAction: 'Monitor',
    orderQty: 0, status: 'healthy', forecastAccuracy: 96, demandVolatility: 'Low',
  },
  'Edible Oil': {
    forecast30d: 3050, safetyStock: 450, orderLeadTime: '10 Days',
    reorderPoint: 2500, riskScore: 65, recommendedAction: 'Schedule Reorder',
    orderQty: 850, status: 'warning', forecastAccuracy: 89, demandVolatility: 'Medium',
  },
};

// ── Time Series Generator (category-aware) ───────────────────

const generateTimeSeriesData = (category) => {
  const config = categoryChartConfig[category] || categoryChartConfig.Snacks;
  const { baseValue, amplitude, trend, bandGrowth, baseBand, noise } = config;
  const data = [];
  const startDate = new Date('2025-08-01');

  for (let i = 0; i < 60; i++) {
    const date = new Date(startDate);
    date.setDate(date.getDate() + i);
    const dateStr = `${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;

    const isHistorical = i < 30;
    const seasonal = Math.sin((i / 7) * Math.PI) * amplitude;
    const trendVal = i * trend;
    const n = noise[i % noise.length];
    const value = Math.max(50, Math.round(baseValue + seasonal + trendVal + n));

    const bandWidth = isHistorical ? 0 : (i - 29) * bandGrowth + baseBand;

    data.push({
      date: dateStr,
      historical: isHistorical ? value : null,
      forecast: !isHistorical ? value : (i === 29 ? value : null),
      upperBound: !isHistorical ? value + bandWidth : null,
      lowerBound: !isHistorical ? Math.max(0, value - bandWidth) : null,
    });
  }
  return data;
};

// ── Helpers ──────────────────────────────────────────────────

const statusStyles = {
  healthy:  'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  warning:  'bg-amber-500/10 text-amber-400 border-amber-500/20',
  critical: 'bg-red-500/10 text-red-400 border-red-500/20',
};

const riskColor = (score) =>
  score >= 70 ? '#EF4444' : score >= 50 ? '#F59E0B' : '#10B981';

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="glass-card px-4 py-3 shadow-xl border border-white/10 text-xs">
      <p className="text-[#94A3B8] font-semibold mb-1.5">{label}</p>
      {payload.map((entry, i) => (
        entry.value != null && (
          <div key={i} className="flex items-center gap-2 py-0.5">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.stroke || entry.color }} />
            <span className="text-[#94A3B8]">{entry.name}:</span>
            <span className="text-[#F1F5F9] font-bold">{Math.round(entry.value).toLocaleString()}</span>
          </div>
        )
      ))}
    </div>
  );
};

// ── Component ────────────────────────────────────────────────

const CategoryIntelligence = () => {
  const [selectedCategory, setSelectedCategory] = useState('Snacks');
  const profile = categoryProfiles[selectedCategory];

  // Recompute chart data whenever selectedCategory changes
  const timeSeriesData = useMemo(
    () => generateTimeSeriesData(selectedCategory),
    [selectedCategory]
  );
  const todayLabel = timeSeriesData[29]?.date || '08-31';

  return (
    <div className="space-y-6">
      {/* Category Selector + Status */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="relative">
          <ShoppingCart size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-blue-400 pointer-events-none z-10" />
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="appearance-none bg-[#1E293B] text-[#E2E8F0] border border-white/10 rounded-xl pl-10 pr-10 py-2.5 outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500/30 text-sm font-semibold transition-all cursor-pointer w-56"
          >
            {Object.keys(categoryProfiles).map((cat) => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
          <ChevronDown size={16} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-[#64748B] pointer-events-none" />
        </div>
        <span className={`px-3 py-1 rounded-full text-[10px] font-bold border uppercase tracking-wider ${statusStyles[profile.status]}`}>
          {profile.status}
        </span>
      </div>

      {/* Demand Forecast Area Chart */}
      <GlassCard
        title="Demand Forecast Visualization"
        subtitle={`${selectedCategory} — Historical demand vs predicted units (95% confidence interval)`}
        icon={<TrendingUp size={18} />}
      >
        <div className="h-[380px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={timeSeriesData} margin={{ top: 10, right: 20, left: 10, bottom: 0 }}>
              <defs>
                <linearGradient id="historicalGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3B82F6" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#3B82F6" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="confidenceGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#8B5CF6" stopOpacity={0.2} />
                  <stop offset="100%" stopColor="#8B5CF6" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis
                dataKey="date"
                tick={{ fill: '#64748B', fontSize: 11 }}
                axisLine={{ stroke: 'rgba(255,255,255,0.08)' }}
                tickLine={false}
                interval={5}
              />
              <YAxis
                tick={{ fill: '#64748B', fontSize: 11 }}
                axisLine={{ stroke: 'rgba(255,255,255,0.08)' }}
                tickLine={false}
                width={45}
              />
              <Tooltip content={<CustomTooltip />} />
              {/* Confidence band — upper */}
              <Area
                type="monotone"
                dataKey="upperBound"
                stroke="none"
                fill="url(#confidenceGradient)"
                fillOpacity={1}
                name="Upper 95%"
                dot={false}
                activeDot={false}
                connectNulls={false}
              />
              {/* Confidence band — lower */}
              <Area
                type="monotone"
                dataKey="lowerBound"
                stroke="rgba(139,92,246,0.25)"
                strokeWidth={1}
                strokeDasharray="4 4"
                fill="#0B1220"
                fillOpacity={1}
                name="Lower 95%"
                dot={false}
                activeDot={false}
                connectNulls={false}
              />
              {/* Historical line */}
              <Area
                type="monotone"
                dataKey="historical"
                stroke="#3B82F6"
                strokeWidth={2.5}
                fill="url(#historicalGradient)"
                fillOpacity={1}
                name="Historical"
                dot={false}
                activeDot={{ r: 4, fill: '#3B82F6', stroke: '#1E293B', strokeWidth: 2 }}
                connectNulls={false}
              />
              {/* Forecast line */}
              <Area
                type="monotone"
                dataKey="forecast"
                stroke="#8B5CF6"
                strokeWidth={2.5}
                strokeDasharray="8 4"
                fill="none"
                name="Forecast"
                dot={false}
                activeDot={{ r: 4, fill: '#8B5CF6', stroke: '#1E293B', strokeWidth: 2 }}
                connectNulls={false}
              />
              {/* Today divider */}
              <ReferenceLine
                x={todayLabel}
                stroke="rgba(255,255,255,0.2)"
                strokeDasharray="4 4"
                label={{ value: 'Today', fill: '#64748B', fontSize: 11, position: 'top' }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        {/* Legend */}
        <div className="flex items-center gap-6 mt-4 px-2 text-xs text-[#94A3B8]">
          <div className="flex items-center gap-2">
            <div className="w-5 h-0.5 bg-blue-500 rounded-full" />
            <span>Historical</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-5 h-0.5 bg-purple-500 rounded-full" style={{ backgroundImage: 'repeating-linear-gradient(90deg, #8B5CF6 0, #8B5CF6 4px, transparent 4px, transparent 8px)' }} />
            <span>Forecast</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-5 h-3 rounded-sm bg-purple-500/15 border border-purple-500/30" />
            <span>95% Confidence</span>
          </div>
        </div>
      </GlassCard>

      {/* Decision Summary */}
      <GlassCard
        title="Decision Summary"
        subtitle="AI-recommended inventory actions based on forecast analysis"
        icon={<Target size={18} />}
      >
        {/* Recommended Action Banner */}
        <div className="flex items-center gap-4 p-4 rounded-xl bg-gradient-to-r from-blue-500/10 to-purple-500/10 border border-blue-500/20 mb-5">
          <div className="p-3 bg-blue-500/20 rounded-xl shrink-0">
            <PackageCheck size={24} className="text-blue-400" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-[10px] text-[#64748B] uppercase font-bold tracking-wider">Recommended Action</p>
            <p className="text-lg font-bold text-[#F1F5F9]">{profile.recommendedAction}</p>
          </div>
          <ArrowRight size={20} className="text-[#475569] shrink-0" />
        </div>

        {/* Metrics Grid */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {[
            { label: 'Order Qty',       value: profile.orderQty.toLocaleString(), icon: <PackageCheck size={15} />, color: 'text-blue-400' },
            { label: 'Reorder Point',   value: profile.reorderPoint.toLocaleString(), icon: <Target size={15} />, color: 'text-purple-400' },
            { label: 'Safety Stock',    value: profile.safetyStock.toLocaleString(), icon: <Shield size={15} />, color: 'text-emerald-400' },
            { label: 'Risk Score',      value: profile.riskScore, icon: <AlertCircle size={15} />, color: '', customColor: riskColor(profile.riskScore) },
            { label: 'Accuracy',        value: `${profile.forecastAccuracy}%`, icon: <Gauge size={15} />, color: 'text-cyan-400' },
            { label: 'Volatility',      value: profile.demandVolatility, icon: <Activity size={15} />, color: 'text-amber-400' },
          ].map((metric, i) => (
            <div key={i} className="bg-white/[0.02] border border-white/5 rounded-xl p-3.5 hover:bg-white/[0.04] transition-colors">
              <div className="flex items-center gap-2 mb-2">
                <span className={metric.color || ''} style={metric.customColor ? { color: metric.customColor } : {}}>
                  {metric.icon}
                </span>
                <span className="text-[10px] uppercase tracking-wider text-[#64748B] font-semibold">{metric.label}</span>
              </div>
              <p
                className="text-xl font-bold text-[#F1F5F9]"
                style={metric.customColor ? { color: metric.customColor } : {}}
              >
                {metric.value}
              </p>
            </div>
          ))}
        </div>
      </GlassCard>

      {/* Bottom Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard label="30D Forecast" value={profile.forecast30d.toLocaleString()} icon={<TrendingUp />} trend="up" trendValue="+5.2%" accentColor="blue" />
        <StatCard label="Safety Stock" value={profile.safetyStock.toLocaleString()} icon={<Shield />} trend="neutral" accentColor="emerald" />
        <StatCard label="Order Lead Time" value={profile.orderLeadTime} icon={<Clock />} trend="neutral" accentColor="amber" />
      </div>
    </div>
  );
};

export default CategoryIntelligence;
