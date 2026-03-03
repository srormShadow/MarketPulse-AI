import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { ResponsiveContainer, LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip } from 'recharts';
import { apiClient } from '../../api/client';
import NoDataCard from './NoDataCard';

const DEFAULT_STOCKS = ['Snacks', 'Staples', 'Edible Oil'];

function toDateLabel(dateStr) {
  return new Date(`${dateStr}T00:00:00`).toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });
}

function normalizeHistoricalEntries(data) {
  if (!data || typeof data !== 'object') return [];
  return Object.entries(data)
    .map(([year, payload]) => ({ year, payload }))
    .sort((a, b) => Number(b.year) - Number(a.year));
}

export default function PredictionSidebar({
  isOpen,
  selectedDate,
  isFestival,
  selectedFestivalName,
  stocks = DEFAULT_STOCKS,
  onClose,
}) {
  const [selectedStock, setSelectedStock] = useState(stocks[0] || '');
  const [predictionData, setPredictionData] = useState(null);
  const [isPredictionLoading, setIsPredictionLoading] = useState(false);
  const [predictionError, setPredictionError] = useState(null);
  const [historicalData, setHistoricalData] = useState(null);
  const [isHistoricalLoading, setIsHistoricalLoading] = useState(false);
  const [historicalError, setHistoricalError] = useState(null);

  useEffect(() => {
    if (!isOpen) return;
    const onKeyDown = (event) => {
      if (event.key === 'Escape') onClose?.();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isOpen, onClose]);

  useEffect(() => {
    if (!isOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen || !selectedDate || !selectedStock) return;

    let cancelled = false;
    setPredictionError(null);
    setHistoricalError(null);
    setIsPredictionLoading(true);
    setIsHistoricalLoading(true);

    apiClient
      .get('/predictions', { params: { date: selectedDate, stock: selectedStock } })
      .then((res) => {
        if (!cancelled) setPredictionData(res.data || null);
      })
      .catch(() => {
        if (!cancelled) {
          setPredictionData(null);
          setPredictionError('Failed to load prediction data.');
        }
      })
      .finally(() => {
        if (!cancelled) setIsPredictionLoading(false);
      });

    apiClient
      .get('/historical', { params: { date: selectedDate, stock: selectedStock } })
      .then((res) => {
        if (!cancelled) setHistoricalData(res.data || null);
      })
      .catch(() => {
        if (!cancelled) {
          setHistoricalData(null);
          setHistoricalError('Failed to load historical comparison.');
        }
      })
      .finally(() => {
        if (!cancelled) setIsHistoricalLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [isOpen, selectedDate, selectedStock]);

  const borderClass = isFestival ? 'border-amber-400/70' : 'border-blue-500/70';
  const dayLabel = isFestival ? selectedFestivalName || 'Festival Day' : 'Regular Trading Day';

  const historicalEntries = useMemo(() => normalizeHistoricalEntries(historicalData), [historicalData]);
  const chartPoints = useMemo(() => {
    return historicalEntries
      .filter((entry) => entry.payload && typeof entry.payload === 'object')
      .map((entry) => {
        const volume = Number(entry.payload.sales_volume ?? entry.payload.volume ?? NaN);
        return Number.isFinite(volume) ? { year: entry.year, sales_volume: volume } : null;
      })
      .filter(Boolean);
  }, [historicalEntries]);

  const hasHistoricalChart = chartPoints.length > 0;

  if (!isOpen) return null;

  return createPortal(
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm transition-opacity duration-300 ease-in-out opacity-100"
      />

      {/* Centered Modal */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
        <div
          onClick={(e) => e.stopPropagation()}
          className={`relative w-full max-w-lg max-h-[85vh] rounded-2xl border ${borderClass} bg-[#0F172A] shadow-2xl shadow-black/40 animate-fade-in-up overflow-hidden`}
        >
          {/* Header */}
          <div className="flex items-start justify-between border-b border-white/10 px-5 py-4">
            <div>
              <p className="text-xs uppercase tracking-wider text-[#64748B]">Selected Date</p>
              <h3 className="mt-1 text-sm font-semibold text-[#F1F5F9]">
                {selectedDate ? toDateLabel(selectedDate) : 'Choose a date'}
              </h3>
              <p className={`mt-1 text-xs ${isFestival ? 'text-amber-300' : 'text-blue-300'}`}>{dayLabel}</p>
            </div>
            <button
              onClick={onClose}
              className="rounded-lg border border-white/10 bg-white/5 p-1.5 text-[#CBD5E1] hover:bg-white/10 transition-colors"
              aria-label="Close popup"
            >
              <X size={16} />
            </button>
          </div>

          {/* Scrollable content */}
          <div className="space-y-4 overflow-y-auto px-5 py-4" style={{ maxHeight: 'calc(85vh - 90px)' }}>
            <section className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
              <label htmlFor="stock-select" className="block text-xs text-[#94A3B8]">
                Stock
              </label>
              <select
                id="stock-select"
                value={selectedStock}
                onChange={(event) => setSelectedStock(event.target.value)}
                className="mt-2 w-full rounded-lg border border-white/10 bg-[#0F172A] px-3 py-2 text-sm text-[#E2E8F0] outline-none focus:border-blue-500"
              >
                {stocks.map((stock) => (
                  <option key={stock} value={stock}>
                    {stock}
                  </option>
                ))}
              </select>
              {!selectedStock && <p className="mt-2 text-xs text-[#94A3B8]">Select a stock to load analytics.</p>}
            </section>

            <section className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
              <p className="text-xs uppercase tracking-wider text-[#64748B]">Prediction</p>
              {isPredictionLoading && <p className="mt-2 text-sm text-[#94A3B8]">Loading prediction...</p>}
              {!isPredictionLoading && predictionError && (
                <p className="mt-2 text-sm text-red-300">{predictionError}</p>
              )}
              {!isPredictionLoading && !predictionError && predictionData && (
                <div className="mt-2 space-y-2 text-sm text-[#CBD5E1]">
                  <p>Predicted demand: <span className="text-[#F1F5F9]">{predictionData.predicted_demand ?? 'N/A'}</span></p>
                  <p>Risk score: <span className="text-[#F1F5F9]">{predictionData.risk_score != null ? `${Math.round(Number(predictionData.risk_score) * 100)}%` : 'N/A'}</span></p>
                  <p>Confidence level: <span className="text-[#F1F5F9]">{predictionData.confidence_level ?? 'N/A'}</span></p>
                  <p>Suggested action: <span className="text-[#F1F5F9]">{predictionData.suggested_action ?? 'N/A'}</span></p>
                </div>
              )}
              {!isPredictionLoading && !predictionError && !predictionData && (
                <p className="mt-2 text-sm text-[#94A3B8]">No prediction returned for this date/stock.</p>
              )}
            </section>

            <section className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
              <p className="text-xs uppercase tracking-wider text-[#64748B]">Historical Comparison (Last 2 Years)</p>

              {isHistoricalLoading && <p className="mt-2 text-sm text-[#94A3B8]">Loading historical data...</p>}
              {!isHistoricalLoading && historicalError && (
                <p className="mt-2 text-sm text-red-300">{historicalError}</p>
              )}

              {!isHistoricalLoading && !historicalError && (
                <div className="mt-3 space-y-2">
                  {historicalEntries.length === 0 && (
                    <p className="text-sm text-[#94A3B8]">No historical records available for comparison.</p>
                  )}

                  {historicalEntries.map(({ year, payload }) => {
                    if (!payload || (typeof payload === 'object' && Object.keys(payload).length === 0)) {
                      return <NoDataCard key={year} year={year} subtext="Stock not active during this period" />;
                    }
                    return (
                      <div key={year} className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
                        <p className="text-sm font-semibold text-[#E2E8F0]">{year}</p>
                        <p className="mt-1 text-sm text-[#CBD5E1]">Sales volume: {payload.sales_volume ?? payload.volume ?? 'N/A'}</p>
                        <p className="text-sm text-[#CBD5E1]">Demand trend: {payload.demand_trend ?? 'N/A'}</p>
                        <p className="text-sm text-[#CBD5E1]">% change: {payload.percent_change ?? payload.change_pct ?? 'N/A'}</p>
                      </div>
                    );
                  })}

                  {hasHistoricalChart ? (
                    <div className="mt-3 h-40 rounded-lg border border-white/10 bg-[#0F172A]/60 p-2">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartPoints}>
                          <CartesianGrid stroke="#1E293B" strokeDasharray="3 3" />
                          <XAxis dataKey="year" stroke="#64748B" />
                          <YAxis stroke="#64748B" />
                          <Tooltip
                            contentStyle={{ backgroundColor: '#1E293B', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, color: '#E2E8F0', fontSize: 12 }}
                            itemStyle={{ color: '#F1F5F9' }}
                            labelStyle={{ color: '#F1F5F9' }}
                          />
                          <Line type="monotone" dataKey="sales_volume" stroke="#38BDF8" strokeWidth={2} dot />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    historicalEntries.length > 0 && (
                      <p className="pt-1 text-sm text-[#94A3B8]">No historical records available for comparison.</p>
                    )
                  )}
                </div>
              )}
            </section>
          </div>
        </div>
      </div>
    </>,
    document.body
  );
}
