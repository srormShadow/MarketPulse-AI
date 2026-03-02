import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Flame } from 'lucide-react';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell,
} from 'recharts';
import GlassCard from '../components/ui/GlassCard';
import FestivalCalendar from '../components/festival/FestivalCalendar';
import { apiClient } from '../api/client';

const CATEGORIES = ['Snacks', 'Staples', 'Edible Oil'];
const INVENTORY = { Snacks: 2800, Staples: 5100, 'Edible Oil': 1900 };
const LEAD_TIMES = { Snacks: 5, Staples: 7, 'Edible Oil': 10 };

const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
const daysUntil = (dateValue) => {
  const now = startOfDay(new Date());
  const target = startOfDay(new Date(dateValue));
  return Math.floor((target - now) / (1000 * 60 * 60 * 24));
};
const readinessStatus = (gapRatio) => {
  if (gapRatio >= 0.35) return 'CRITICAL';
  if (gapRatio > 0.1) return 'AT RISK';
  return 'READY';
};
const readinessStyle = (status) => {
  if (status === 'CRITICAL') return 'bg-red-500/15 text-red-200 border-red-500/35';
  if (status === 'AT RISK') return 'bg-amber-500/15 text-amber-200 border-amber-500/35';
  return 'bg-emerald-500/15 text-emerald-200 border-emerald-500/35';
};

const FestivalIntelligence = () => {
  const [festivals, setFestivals] = useState([]);
  const [forecastRows, setForecastRows] = useState([]);
  const [diagnosticsAll, setDiagnosticsAll] = useState(null);
  const [diagnosticsFallback, setDiagnosticsFallback] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    const loadData = async () => {
      setLoading(true);
      setError('');
      try {
        const [festivalsRes, batchRes, diagnosticsRes] = await Promise.allSettled([
          apiClient.get('/festivals'),
          apiClient.post('/forecast/batch', {
            categories: CATEGORIES,
            n_days: 60,
            inventory: INVENTORY,
            lead_times: LEAD_TIMES,
          }),
          apiClient.get('/diagnostics/all'),
        ]);

        if (cancelled) return;

        if (festivalsRes.status === 'fulfilled') {
          setFestivals(Array.isArray(festivalsRes.value?.data?.items) ? festivalsRes.value.data.items : []);
        } else {
          setError('Unable to load festival calendar.');
        }

        if (batchRes.status === 'fulfilled') {
          setForecastRows(Array.isArray(batchRes.value?.data) ? batchRes.value.data : []);
        }

        if (diagnosticsRes.status === 'fulfilled') {
          setDiagnosticsAll(diagnosticsRes.value?.data || null);
          setDiagnosticsFallback(false);
        } else {
          setDiagnosticsFallback(true);
          setDiagnosticsAll(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    loadData();
    return () => { cancelled = true; };
  }, []);

  const upcoming60 = useMemo(() => {
    const now = startOfDay(new Date());
    return festivals
      .map((f) => ({
        ...f,
        dateObj: new Date(f.date),
        days_to: daysUntil(f.date),
        affected: (f.categories && f.categories.length > 0)
          ? f.categories
          : String(f.category || '').split(',').map((s) => s.trim()).filter(Boolean),
      }))
      .filter((f) => f.dateObj >= now && f.days_to <= 60)
      .sort((a, b) => a.dateObj - b.dateObj);
  }, [festivals]);

  const readinessRows = useMemo(() => {
    const rows = [];
    const forecastByCategory = {};
    forecastRows.forEach((row) => {
      forecastByCategory[row.category] = row;
    });

    upcoming60.forEach((festival) => {
      festival.affected.forEach((category) => {
        const categoryForecast = forecastByCategory[category];
        const currentStock = Number(INVENTORY[category] || 0);
        const decision = categoryForecast?.decision || {};
        const reorderPoint = Number(decision?.reorder_point || 0);
        const safetyStock = Number(decision?.safety_stock || 0);
        const baseRequired = Math.max(reorderPoint, safetyStock);
        const requiredStock = Math.round(baseRequired * (1 + Number(festival.historical_uplift || 0)));
        const gap = Math.max(0, requiredStock - currentStock);
        const gapRatio = requiredStock > 0 ? gap / requiredStock : 0;
        rows.push({
          festival: festival.festival_name,
          category,
          currentStock,
          requiredStock,
          gap,
          status: readinessStatus(gapRatio),
        });
      });
    });
    return rows;
  }, [upcoming60, forecastRows]);

  const sensitivityData = useMemo(() => {
    if (diagnosticsAll?.categories) {
      return Object.entries(diagnosticsAll.categories).map(([category, payload]) => ({
        category,
        value: Math.abs(Number(payload?.coefficients?.festival_score || 0)),
      }));
    }

    if (diagnosticsAll?.items && Array.isArray(diagnosticsAll.items)) {
      return diagnosticsAll.items.map((item) => ({
        category: item.category,
        value: Math.abs(Number(item?.coefficients?.festival_score || item?.festival_score || 0)),
      }));
    }

    return CATEGORIES.map((category, idx) => ({
      category,
      value: [0.19, 0.11, 0.25][idx],
    }));
  }, [diagnosticsAll]);

  if (loading) {
    return <div className="text-sm text-[#94A3B8]">Loading festival intelligence...</div>;
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-red-200 text-sm">
          {error}
        </div>
      )}

      <FestivalCalendar variant="full" leadTimes={LEAD_TIMES} />

      <GlassCard
        title="Pre-Festival Readiness"
        subtitle="Category-level stock preparedness per upcoming festival"
        icon={<AlertTriangle size={18} />}
      >
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[#64748B] text-xs uppercase tracking-wider border-b border-white/5">
                <th className="pb-3 pr-6 font-semibold">Festival</th>
                <th className="pb-3 pr-6 font-semibold">Category</th>
                <th className="pb-3 pr-6 font-semibold text-right">Current Stock</th>
                <th className="pb-3 pr-6 font-semibold text-right">Required Stock</th>
                <th className="pb-3 pr-6 font-semibold text-right">Gap</th>
                <th className="pb-3 font-semibold">Status</th>
              </tr>
            </thead>
            <tbody>
              {readinessRows.map((row, idx) => (
                <tr key={`${row.festival}-${row.category}-${idx}`} className="border-b border-white/5">
                  <td className="py-3 pr-6 text-[#F1F5F9]">{row.festival}</td>
                  <td className="py-3 pr-6 text-[#CBD5E1]">{row.category}</td>
                  <td className="py-3 pr-6 text-right font-mono text-[#CBD5E1]">{row.currentStock.toLocaleString()}</td>
                  <td className="py-3 pr-6 text-right font-mono text-[#CBD5E1]">{row.requiredStock.toLocaleString()}</td>
                  <td className="py-3 pr-6 text-right font-mono text-[#CBD5E1]">{row.gap.toLocaleString()}</td>
                  <td className="py-3">
                    <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold border uppercase tracking-wider ${readinessStyle(row.status)}`}>
                      {row.status}
                    </span>
                  </td>
                </tr>
              ))}
              {!readinessRows.length && (
                <tr>
                  <td colSpan={6} className="py-4 text-center text-[#94A3B8]">No readiness rows available.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </GlassCard>

      <GlassCard
        title="Festival Sensitivity by Category"
        subtitle="Comparison of festival_score coefficients across categories"
        icon={<Flame size={18} />}
      >
        {diagnosticsFallback && (
          <p className="text-xs text-amber-300 mb-3">`GET /diagnostics/all` unavailable; using fallback sensitivity values.</p>
        )}
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={sensitivityData} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="category" tick={{ fill: '#CBD5E1', fontSize: 12 }} axisLine={{ stroke: 'rgba(255,255,255,0.1)' }} tickLine={false} />
              <YAxis tick={{ fill: '#94A3B8', fontSize: 12 }} axisLine={{ stroke: 'rgba(255,255,255,0.1)' }} tickLine={false} />
              <Tooltip
                formatter={(value) => [Number(value).toFixed(3), 'festival_score coef']}
                contentStyle={{ backgroundColor: '#1E293B', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, color: '#E2E8F0', fontSize: 12 }}
              />
              <Bar dataKey="value" radius={[6, 6, 0, 0]} barSize={36}>
                {sensitivityData.map((row, idx) => (
                  <Cell key={`${row.category}-${idx}`} fill={row.value >= 0.2 ? '#EF4444' : row.value >= 0.14 ? '#F59E0B' : '#10B981'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </GlassCard>
    </div>
  );
};

export default FestivalIntelligence;
