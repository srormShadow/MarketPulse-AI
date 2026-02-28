import { useState } from 'react';
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

// ── Mock Data ────────────────────────────────────────────────

const kpiData = [
  { label: 'Network Risk',      value: 'High',    trend: 'up',      trendValue: '+8%',  accentColor: 'red',     icon: <ShieldAlert /> },
  { label: 'Inventory Gap',     value: '-1,240',  trend: 'down',    trendValue: '-340',  accentColor: 'red',     icon: <PackageX /> },
  { label: '30D Forecast',      value: '14,250',  trend: 'up',      trendValue: '+5.2%', accentColor: 'blue',    icon: <TrendingUp /> },
  { label: 'Active Categories', value: '3',       trend: 'neutral', trendValue: '',      accentColor: 'emerald', icon: <Layers /> },
];

const healthTableData = [
  { category: 'Snacks',     currentStock: 2800, requiredStock: 4200, safetyStock: 600,  riskScore: 78, status: 'critical',  reorderPoint: 3200, leadTime: 5 },
  { category: 'Staples',    currentStock: 5100, requiredStock: 5500, safetyStock: 800,  riskScore: 32, status: 'healthy',   reorderPoint: 4400, leadTime: 7 },
  { category: 'Edible Oil', currentStock: 1900, requiredStock: 3100, safetyStock: 450,  riskScore: 65, status: 'warning',   reorderPoint: 2500, leadTime: 10 },
];

const riskDistributionData = [
  { category: 'Snacks',     riskScore: 78, fill: '#EF4444' },
  { category: 'Edible Oil', riskScore: 65, fill: '#F59E0B' },
  { category: 'Staples',    riskScore: 32, fill: '#10B981' },
];

const inventoryGapData = [
  { category: 'Snacks',     current: 2800, required: 4200 },
  { category: 'Staples',    current: 5100, required: 5500 },
  { category: 'Edible Oil', current: 1900, required: 3100 },
];

// ── Helpers ──────────────────────────────────────────────────

const riskColor = (score) =>
  score >= 70 ? '#EF4444' : score >= 50 ? '#F59E0B' : '#10B981';

const isHighRisk = (row) => row.status === 'critical' || row.riskScore > 60;

const statusStyles = {
  healthy:  'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  warning:  'bg-amber-500/10 text-amber-400 border-amber-500/20',
  critical: 'bg-red-500/10 text-red-400 border-red-500/20',
};

const StatusBadge = ({ status }) => (
  <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold border uppercase tracking-wider ${statusStyles[status]}`}>
    {status}
  </span>
);

const tooltipStyle = {
  backgroundColor: '#1E293B',
  border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: 8,
  color: '#E2E8F0',
  fontSize: 12,
};

// ── Component ────────────────────────────────────────────────

const PortfolioOverview = () => {
  const [drawerCategory, setDrawerCategory] = useState(null);

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {kpiData.map((kpi, i) => (
          <StatCard key={i} {...kpi} />
        ))}
      </div>

      {/* Health Table */}
      <GlassCard
        title="Inventory Health Portfolio"
        subtitle="Real-time category health monitoring — click high-risk rows for details"
        icon={<Activity size={18} />}
      >
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[#64748B] text-xs uppercase tracking-wider border-b border-white/5">
                <th className="pb-3 pr-6 font-semibold">Category</th>
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
              {healthTableData.map((row) => {
                const clickable = isHighRisk(row);
                return (
                  <tr
                    key={row.category}
                    onClick={clickable ? () => setDrawerCategory(row.category) : undefined}
                    className={`
                      border-b border-white/5 transition-colors
                      ${clickable
                        ? 'cursor-pointer hover:bg-white/[0.04] group'
                        : 'hover:bg-white/[0.02]'
                      }
                    `}
                  >
                    <td className="py-4 pr-6 font-semibold text-[#F1F5F9]">
                      <div className="flex items-center gap-2">
                        {clickable && (
                          <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: riskColor(row.riskScore) }} />
                        )}
                        {row.category}
                      </div>
                    </td>
                    <td className="py-4 pr-6"><StatusBadge status={row.status} /></td>
                    <td className="py-4 pr-6 text-right font-mono text-[#E2E8F0]">{row.currentStock.toLocaleString()}</td>
                    <td className="py-4 pr-6 text-right font-mono text-[#94A3B8]">{row.requiredStock.toLocaleString()}</td>
                    <td className="py-4 pr-6 text-right font-mono text-[#94A3B8]">{row.safetyStock.toLocaleString()}</td>
                    <td className="py-4 pr-6 text-right font-mono text-[#94A3B8]">{row.reorderPoint.toLocaleString()}</td>
                    <td className="py-4 pr-6 text-right font-mono text-[#94A3B8]">{row.leadTime}d</td>
                    <td className="py-4 text-right">
                      <div className="flex items-center gap-2 justify-end">
                        <div className="w-16 h-1.5 rounded-full bg-white/5 overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all duration-700"
                            style={{ width: `${row.riskScore}%`, backgroundColor: riskColor(row.riskScore) }}
                          />
                        </div>
                        <span className="font-mono text-xs font-bold w-6 text-right" style={{ color: riskColor(row.riskScore) }}>
                          {row.riskScore}
                        </span>
                      </div>
                    </td>
                    <td className="py-4 pl-2 w-8">
                      {clickable && (
                        <ChevronRight size={14} className="text-[#475569] group-hover:text-[#94A3B8] transition-colors" />
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </GlassCard>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Risk Distribution */}
        <GlassCard
          title="Risk Distribution"
          subtitle="Category risk scores (0-100)"
          icon={<AlertTriangle size={18} />}
        >
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={riskDistributionData}
                layout="vertical"
                margin={{ top: 5, right: 30, left: 70, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" horizontal={false} />
                <XAxis
                  type="number"
                  domain={[0, 100]}
                  tick={{ fill: '#94A3B8', fontSize: 12 }}
                  axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                  tickLine={false}
                />
                <YAxis
                  dataKey="category"
                  type="category"
                  tick={{ fill: '#E2E8F0', fontSize: 13, fontWeight: 500 }}
                  axisLine={false}
                  tickLine={false}
                  width={65}
                />
                <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(255,255,255,0.02)' }} />
                <Bar dataKey="riskScore" name="Risk Score" radius={[0, 6, 6, 0]} barSize={22}>
                  {riskDistributionData.map((entry, index) => (
                    <Cell key={index} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </GlassCard>

        {/* Inventory Gaps */}
        <GlassCard
          title="Inventory Gaps"
          subtitle="Current vs required stock levels"
          icon={<BarChart3 size={18} />}
        >
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={inventoryGapData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis
                  dataKey="category"
                  tick={{ fill: '#E2E8F0', fontSize: 12 }}
                  axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: '#94A3B8', fontSize: 12 }}
                  axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                  tickLine={false}
                />
                <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(255,255,255,0.02)' }} />
                <Legend wrapperStyle={{ fontSize: 12, color: '#94A3B8' }} iconType="circle" iconSize={8} />
                <Bar dataKey="current" name="Current Stock" fill="#3B82F6" radius={[4, 4, 0, 0]} barSize={28} />
                <Bar dataKey="required" name="Required Stock" fill="rgba(139,92,246,0.5)" radius={[4, 4, 0, 0]} barSize={28} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </GlassCard>
      </div>

      {/* Risk Drawer — conditionally rendered */}
      {drawerCategory && (
        <RiskDrawer
          category={drawerCategory}
          onClose={() => setDrawerCategory(null)}
        />
      )}
    </div>
  );
};

export default PortfolioOverview;
