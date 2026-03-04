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
  const chartTheme = {
    grid: 'color-mix(in srgb, var(--text-3) 24%, transparent)',
    axis: 'color-mix(in srgb, var(--text-3) 42%, transparent)',
    tick: 'var(--text-3)',
  };

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
          className={`relative w-full max-w-lg max-h-[85vh] rounded-2xl border ${borderClass} bg-[var(--bg-elevated)] shadow-2xl shadow-black/40 animate-fade-in-up overflow-hidden`}
        >
          {/* Header */}
          <div className="flex items-start justify-between border-b border-[var(--border)] px-5 py-4">
            <div>
              <p className="text-xs uppercase tracking-wider text-[var(--text-3)]">Selected Date</p>
              <h3 className="mt-1 text-sm font-semibold text-[var(--text-1)]">
                {selectedDate ? toDateLabel(selectedDate) : 'Choose a date'}
              </h3>
              <p className={`mt-1 text-xs ${isFestival ? 'text-[var(--badge-warning-text)]' : 'text-[var(--badge-info-text)]'}`}>{dayLabel}</p>
            </div>
            <button
              onClick={onClose}
              className="rounded-lg border border-[var(--border)] bg-white/5 p-1.5 text-[var(--text-2)] hover:bg-white/10 transition-colors"
              aria-label="Close popup"
            >
              <X size={16} />
            </button>
          </div>

          {/* Scrollable content */}
          <div className="space-y-4 overflow-y-auto px-5 py-4" style={{ maxHeight: 'calc(85vh - 90px)' }}>
            <section className="rounded-xl border border-[var(--border)] bg-[color-mix(in_srgb,var(--bg-elevated)_82%,transparent)] p-3">
              <label htmlFor="stock-select" className="block text-xs text-[var(--text-3)]">
                Stock
              </label>
              <select
                id="stock-select"
                value={selectedStock}
                onChange={(event) => setSelectedStock(event.target.value)}
                className="mt-2 w-full rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] px-3 py-2 text-sm text-[var(--text-1)] outline-none focus:border-blue-500"
              >
                {stocks.map((stock) => (
                  <option key={stock} value={stock}>
                    {stock}
                  </option>
                ))}
              </select>
              {!selectedStock && <p className="mt-2 text-xs text-[var(--text-3)]">Select a stock to load analytics.</p>}
            </section>

            <section className="rounded-xl border border-[var(--border)] bg-[color-mix(in_srgb,var(--bg-elevated)_82%,transparent)] p-3">
              <p className="text-xs uppercase tracking-wider text-[var(--text-3)]">Prediction</p>
              {isPredictionLoading && <p className="mt-2 text-sm text-[var(--text-3)]">Loading prediction...</p>}
              {!isPredictionLoading && predictionError && (
                <p className="mt-2 text-sm text-[var(--badge-danger-text)]">{predictionError}</p>
              )}
              {!isPredictionLoading && !predictionError && predictionData && (
                <div className="mt-2 space-y-2 text-sm text-[var(--text-2)]">
                  <p>Predicted demand: <span className="text-[var(--text-1)]">{predictionData.predicted_demand ?? 'N/A'}</span></p>
                  <p>Risk score: <span className="text-[var(--text-1)]">{predictionData.risk_score != null ? `${Math.round(Number(predictionData.risk_score) * 100)}%` : 'N/A'}</span></p>
                  <p>Confidence level: <span className="text-[var(--text-1)]">{predictionData.confidence_level ?? 'N/A'}</span></p>
                  <p>Suggested action: <span className="text-[var(--text-1)]">{predictionData.suggested_action ?? 'N/A'}</span></p>
                </div>
              )}
              {!isPredictionLoading && !predictionError && !predictionData && (
                <p className="mt-2 text-sm text-[var(--text-3)]">No prediction returned for this date/stock.</p>
              )}
            </section>

            <section className="rounded-xl border border-[var(--border)] bg-[color-mix(in_srgb,var(--bg-elevated)_82%,transparent)] p-3">
              <p className="text-xs uppercase tracking-wider text-[var(--text-3)]">Historical Comparison (Last 2 Years)</p>

              {isHistoricalLoading && <p className="mt-2 text-sm text-[var(--text-3)]">Loading historical data...</p>}
              {!isHistoricalLoading && historicalError && (
                <p className="mt-2 text-sm text-[var(--badge-danger-text)]">{historicalError}</p>
              )}

              {!isHistoricalLoading && !historicalError && (
                <div className="mt-3 space-y-2">
                  {historicalEntries.length === 0 && (
                    <p className="text-sm text-[var(--text-3)]">No historical records available for comparison.</p>
                  )}

                  {historicalEntries.map(({ year, payload }) => {
                    if (!payload || (typeof payload === 'object' && Object.keys(payload).length === 0)) {
                      return <NoDataCard key={year} year={year} subtext="Stock not active during this period" />;
                    }
                    return (
                      <div key={year} className="rounded-xl border border-[var(--border)] bg-[color-mix(in_srgb,var(--bg-elevated)_82%,transparent)] p-3">
                        <p className="text-sm font-semibold text-[var(--text-1)]">{year}</p>
                        <p className="mt-1 text-sm text-[var(--text-2)]">Sales volume: {payload.sales_volume ?? payload.volume ?? 'N/A'}</p>
                        <p className="text-sm text-[var(--text-2)]">Demand trend: {payload.demand_trend ?? 'N/A'}</p>
                        <p className="text-sm text-[var(--text-2)]">% change: {payload.percent_change ?? payload.change_pct ?? 'N/A'}</p>
                      </div>
                    );
                  })}

                  {hasHistoricalChart ? (
                    <div className="mt-3 h-40 rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)]/60 p-2">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartPoints}>
                          <defs>
                            <linearGradient id="miniLine" x1="0" y1="0" x2="1" y2="0">
                              <stop offset="0%" stopColor="#22d3ee" />
                              <stop offset="55%" stopColor="#a78bfa" />
                              <stop offset="100%" stopColor="#f472b6" />
                            </linearGradient>
                          </defs>
                          <CartesianGrid stroke={chartTheme.grid} strokeDasharray="4 8" />
                          <XAxis dataKey="year" stroke={chartTheme.axis} tick={{ fill: chartTheme.tick, fontSize: 11 }} />
                          <YAxis stroke={chartTheme.axis} tick={{ fill: chartTheme.tick, fontSize: 11 }} />
                          <Tooltip
                            contentStyle={{ backgroundColor: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 10, color: 'var(--text-1)', fontSize: 12, boxShadow: '0 12px 24px rgba(5, 3, 14, 0.2)' }}
                            itemStyle={{ color: 'var(--text-1)' }}
                            labelStyle={{ color: 'var(--text-1)', fontWeight: 700 }}
                          />
                          <Line type="monotone" dataKey="sales_volume" stroke="url(#miniLine)" strokeWidth={3} dot={{ r: 2.5, fill: '#f472b6', strokeWidth: 0 }} activeDot={{ r: 5, fill: '#f472b6' }} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    historicalEntries.length > 0 && (
                      <p className="pt-1 text-sm text-[var(--text-3)]">No historical records available for comparison.</p>
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



