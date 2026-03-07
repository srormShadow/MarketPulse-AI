import { useEffect, useMemo, useState } from 'react';
import {
  Package, FileSpreadsheet, CloudUpload, CheckCircle2, AlertCircle, Info, Clock,
  ChevronDown, ChevronUp, RefreshCw, Database, ShieldAlert,
} from 'lucide-react';
import GlassCard from '../components/ui/GlassCard';
import { apiClient } from '../api/client';
import { useInventory } from '../context/inventoryStore';

const freshnessTone = (stale) => (stale ? 'text-[var(--badge-danger-text)]' : 'text-[var(--badge-success-text)]');

const parseCsvSummary = async (file) => {
  const text = await file.text();
  const lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
  if (!lines.length) {
    return {
      totalRows: 0,
      acceptedRows: 0,
      rejectedRows: 0,
      rejectedReason: 'Empty CSV',
      dateRange: 'n/a',
      categoriesDetected: [],
      modelsWillRetrain: false,
    };
  }

  const header = lines[0].split(',').map((h) => h.trim().toLowerCase());
  const dateIdx = header.indexOf('date');
  const categoryIdx = header.indexOf('category');
  const unitsIdx = header.indexOf('units_sold');

  const missing = [];
  if (dateIdx < 0) missing.push('date');
  if (unitsIdx < 0) missing.push('units_sold');

  let acceptedRows = 0;
  let rejectedRows = 0;
  const categories = new Set();
  const dates = [];

  for (let i = 1; i < lines.length; i += 1) {
    const cols = lines[i].split(',').map((c) => c.trim());
    const dateVal = dateIdx >= 0 ? cols[dateIdx] : '';
    const unitsVal = unitsIdx >= 0 ? cols[unitsIdx] : '';
    if (!dateVal || Number.isNaN(Number(unitsVal))) {
      rejectedRows += 1;
      continue;
    }
    acceptedRows += 1;
    dates.push(dateVal);
    if (categoryIdx >= 0 && cols[categoryIdx]) categories.add(cols[categoryIdx]);
  }

  const sortedDates = dates
    .map((d) => new Date(d))
    .filter((d) => !Number.isNaN(d.getTime()))
    .sort((a, b) => a - b);

  const dateRange = sortedDates.length
    ? `${sortedDates[0].toISOString().slice(0, 10)} to ${sortedDates[sortedDates.length - 1].toISOString().slice(0, 10)}`
    : 'n/a';

  return {
    totalRows: Math.max(0, lines.length - 1),
    acceptedRows,
    rejectedRows,
    rejectedReason: missing.length ? `Missing required columns: ${missing.join(', ')}` : 'Invalid date or units_sold value',
    dateRange,
    categoriesDetected: [...categories],
    modelsWillRetrain: acceptedRows > 0,
  };
};

const DataManagement = () => {
  const { categories: CATEGORIES, inventory, setInventory, leadTimes: DEFAULT_LEAD_TIMES } = useInventory();
  const [isDragOver, setIsDragOver] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [inventoryValues, setInventoryValues] = useState(inventory);
  const [inventoryDraft, setInventoryDraft] = useState(inventory);
  const [isApplying, setIsApplying] = useState(false);
  const [applyMessage, setApplyMessage] = useState('');
  const [applyError, setApplyError] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadStatus, setUploadStatus] = useState(null);
  const [uploadError, setUploadError] = useState('');
  const [uploadSummary, setUploadSummary] = useState(null);
  const [freshnessRows, setFreshnessRows] = useState([]);
  const [modelRows, setModelRows] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [recommendationFallback, setRecommendationFallback] = useState(false);
  const [retrainingCategory, setRetrainingCategory] = useState('');
  const [seeding, setSeeding] = useState(false);
  const [seedStatus, setSeedStatus] = useState(null);

  const loadOperationalData = async (inventorySnapshot = inventoryValues) => {
    const batchPayload = {
      categories: CATEGORIES,
      n_days: 30,
      inventory: inventorySnapshot,
      lead_times: DEFAULT_LEAD_TIMES,
    };

    const [batchResult, recommendationsResult] = await Promise.allSettled([
      apiClient.post('/forecast/batch', batchPayload),
      apiClient.get('/recommendations/recent?limit=10'),
    ]);

    if (batchResult.status === 'fulfilled') {
      const rows = Array.isArray(batchResult.value?.data) ? batchResult.value.data : [];
      const freshness = rows.map((row) => {
        const localTs = localStorage.getItem(`last_upload_${row.category}`);
        return {
          category: row.category,
          lastUpload: row.last_upload_date || localTs || 'Unknown',
          stale: Boolean(row.data_stale || row?.decision?.data_stale_warning),
        };
      });
      setFreshnessRows(freshness);

      const models = rows.map((row) => {
        const decision = row?.decision || {};
        const risk = Number(decision?.risk_score || 0);
        const trainingPoints = Array.isArray(row?.forecast) ? row.forecast.length : 0;
        const status = risk >= 0.7 ? 'degraded' : (risk >= 0.4 ? 'watch' : 'healthy');
        const diagnosticsHealth = localStorage.getItem(`diag_health_${row.category}`);
        return {
          category: row.category,
          lastTrained: localStorage.getItem(`model_trained_${row.category}`) || 'Unknown',
          trainingPoints,
          health: diagnosticsHealth || status,
        };
      });
      setModelRows(models);

      const fallbackRecommendations = rows.map((row, idx) => ({
        id: `${row.category}-${idx}`,
        date: new Date().toISOString(),
        category: row.category,
        action: row?.decision?.recommended_action || 'MAINTAIN',
        order_quantity: Number(row?.decision?.order_quantity || 0),
        risk_score: Number(row?.decision?.risk_score || 0),
      }));

      if (recommendationsResult.status !== 'fulfilled') {
        setRecommendationFallback(true);
        setRecommendations(fallbackRecommendations.slice(0, 10));
      }
    }

    if (recommendationsResult.status === 'fulfilled') {
      const items = recommendationsResult.value?.data?.items || recommendationsResult.value?.data?.recommendations || [];
      setRecommendationFallback(false);
      setRecommendations(Array.isArray(items) ? items.slice(0, 10) : []);
    }
  };

  useEffect(() => {
    loadOperationalData(inventoryValues);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const anyStaleData = useMemo(() => freshnessRows.some((row) => row.stale), [freshnessRows]);

  const onFileSelected = async (file) => {
    if (!file) return;
    setSelectedFile(file);
    setUploadStatus(null);
    setUploadError('');
    const summary = await parseCsvSummary(file);
    setUploadSummary(summary);
  };

  const hasInventoryChanges = useMemo(() => {
    return CATEGORIES.some(
      (category) => Number(inventoryDraft[category] || 0) !== Number(inventoryValues[category] || 0),
    );
  }, [CATEGORIES, inventoryDraft, inventoryValues]);

  const handleApplyInventoryChanges = async () => {
    const normalized = {};
    for (const category of CATEGORIES) {
      const raw = Number(inventoryDraft[category]);
      if (!Number.isFinite(raw) || raw < 0) {
        setApplyError(`Invalid stock value for ${category}. Enter a non-negative number.`);
        setApplyMessage('');
        return;
      }
      normalized[category] = Math.round(raw);
    }

    setIsApplying(true);
    setApplyError('');
    setApplyMessage('');
    try {
      setInventoryValues(normalized);
      setInventory(normalized);
      await loadOperationalData(normalized);
      setApplyMessage('Changes applied successfully.');
    } catch {
      setApplyError('Failed to apply inventory changes. Try again.');
    } finally {
      setIsApplying(false);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;
    setUploading(true);
    setUploadProgress(0);
    setUploadStatus(null);
    setUploadError('');

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      const response = await apiClient.post('/upload_csv', formData, {
        onUploadProgress: (evt) => {
          if (evt.total) {
            const pct = Math.round((evt.loaded / evt.total) * 100);
            setUploadProgress(Math.max(1, pct));
          }
        },
      });
      setUploadStatus('success');
      setUploadProgress(100);
      const nowIso = new Date().toISOString();
      CATEGORIES.forEach((c) => localStorage.setItem(`last_upload_${c}`, nowIso));
      if (uploadSummary) {
        setUploadSummary({
          ...uploadSummary,
          acceptedRows: Number(response?.data?.records_inserted || uploadSummary.acceptedRows),
          modelsWillRetrain: true,
        });
      }
      await loadOperationalData(inventoryValues);
    } catch (err) {
      setUploadStatus('error');
      const details = err?.response?.data?.errors?.[0]?.issue;
      setUploadError(details || err?.response?.data?.message || 'CSV upload failed.');
    } finally {
      setUploading(false);
    }
  };

  const handleSeedDemo = async () => {
    setSeeding(true);
    setSeedStatus(null);
    try {
      const res = await apiClient.post('/seed_demo');
      const data = res?.data || {};
      setSeedStatus({ ok: true, skus: data.skus_inserted, sales: data.sales_inserted });
      const nowIso = new Date().toISOString();
      CATEGORIES.forEach((c) => localStorage.setItem(`last_upload_${c}`, nowIso));
      await loadOperationalData(inventoryValues);
    } catch (err) {
      const msg = err?.response?.data?.message || 'Demo seed failed.';
      setSeedStatus({ ok: false, message: msg });
    } finally {
      setSeeding(false);
    }
  };

  const handleRetrain = async (category) => {
    setRetrainingCategory(category);
    try {
      await apiClient.post(`/retrain/${encodeURIComponent(category)}`);
      const now = new Date().toISOString();
      localStorage.setItem(`model_trained_${category}`, now);
      await loadOperationalData(inventoryValues);
    } catch {
      setUploadError(`Retrain endpoint unavailable for ${category}.`);
    } finally {
      setRetrainingCategory('');
    }
  };

  return (
    <div className="max-w-6xl space-y-7">
      {anyStaleData && (
        <div className="rounded-xl border border-red-500/35 bg-red-500/10 px-4 py-3 text-sm text-[var(--badge-danger-text)]">
          Models are training on stale data. One or more categories have data older than 7 days.
        </div>
      )}

      <GlassCard
        title="Data Freshness"
        subtitle="Last upload status by category"
        icon={<Clock size={18} />}
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {CATEGORIES.map((category) => {
            const row = freshnessRows.find((r) => r.category === category) || { lastUpload: 'Unknown', stale: false };
            return (
              <div key={category} className="rounded-xl border border-[var(--border)] bg-[color-mix(in_srgb,var(--bg-elevated)_82%,transparent)] p-4">
                <p className="text-xs uppercase tracking-wider text-[var(--text-3)]">{category}</p>
                <p className="text-sm text-[var(--text-1)] mt-1">{row.lastUpload === 'Unknown' ? 'Last upload unknown' : new Date(row.lastUpload).toLocaleString('en-IN')}</p>
                <p className={`text-xs mt-2 ${freshnessTone(row.stale)}`}>
                  {row.stale ? 'Stale (7+ days)' : 'Fresh'}
                </p>
              </div>
            );
          })}
        </div>
      </GlassCard>

      <GlassCard
        title="Dataset Upload"
        subtitle="Upload CSV and validate before retraining"
        icon={<FileSpreadsheet size={18} />}
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <button
            onClick={handleSeedDemo}
            disabled={seeding}
            className="group relative overflow-hidden p-6 rounded-xl bg-gradient-to-br from-blue-600/20 to-blue-700/10 border border-blue-500/20 hover:border-blue-500/40 transition-all duration-300 cursor-pointer flex flex-col items-center justify-center gap-3 text-center min-h-[180px] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <div className="p-3.5 bg-blue-500/15 rounded-xl group-hover:scale-110 transition-transform duration-300">
              {seeding ? <RefreshCw size={26} className="text-blue-400 animate-spin" /> : <Database size={26} className="text-blue-400" />}
            </div>
            <div>
              <p className="font-bold text-[var(--text-1)] text-base">{seeding ? 'Seeding...' : 'Use Demo Dataset'}</p>
              <p className="text-xs text-[var(--text-3)] mt-1">
                {seedStatus?.ok ? `Loaded ${seedStatus.skus} SKUs + ${seedStatus.sales} sales rows` : seedStatus?.message || 'Load seeded sample data for quick testing'}
              </p>
            </div>
          </button>

          <div
            onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
            onDragLeave={() => setIsDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setIsDragOver(false);
              const file = e.dataTransfer?.files?.[0];
              onFileSelected(file);
            }}
            className={`relative p-6 rounded-xl border-2 border-dashed transition-all duration-300 flex flex-col items-center justify-center gap-3 text-center min-h-[180px] ${isDragOver ? 'border-blue-500 bg-blue-500/10 shadow-[0_0_40px_rgba(59,130,246,0.15)] scale-[1.01]' : 'border-[var(--border)] hover:border-white/20 bg-white/[0.015] hover:bg-[color-mix(in_srgb,var(--bg-elevated)_76%,transparent)]'}`}
          >
            <input
              type="file"
              className="absolute inset-0 opacity-0 cursor-pointer z-10"
              accept=".csv"
              onChange={(e) => onFileSelected(e.target.files?.[0])}
            />
            <div className={`p-3.5 rounded-xl transition-all duration-300 ${isDragOver ? 'bg-blue-500/15 scale-110' : 'bg-white/5'}`}>
              <CloudUpload size={28} className={`transition-colors duration-300 ${isDragOver ? 'text-blue-400' : 'text-[var(--text-3)]'}`} />
            </div>
            <div>
              <p className="font-semibold text-[var(--text-1)]">{selectedFile ? selectedFile.name : 'Drag & drop CSV file'}</p>
              <p className="text-xs text-[var(--text-3)] mt-1">or click to browse</p>
            </div>
          </div>
        </div>

        <div className="mt-5 flex items-center gap-3">
          <button
            onClick={handleUpload}
            disabled={!selectedFile || uploading}
            className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {uploading ? 'Uploading...' : 'Upload CSV'}
          </button>
          {uploadStatus === 'success' && <span className="text-[var(--badge-success-text)] text-sm flex items-center gap-1"><CheckCircle2 size={14} />Upload successful</span>}
          {uploadStatus === 'error' && <span className="text-[var(--badge-danger-text)] text-sm flex items-center gap-1"><AlertCircle size={14} />{uploadError}</span>}
        </div>

        {(uploading || uploadProgress > 0) && (
          <div className="mt-3">
            <div className="h-2 w-full bg-white/10 rounded-full overflow-hidden">
              <div className="h-full bg-blue-500 transition-all" style={{ width: `${uploadProgress}%` }} />
            </div>
            <p className="text-xs text-[var(--text-3)] mt-1">{uploadProgress}%</p>
          </div>
        )}

        {uploadSummary && (
          <div className="mt-5 rounded-xl border border-[var(--border)] bg-[color-mix(in_srgb,var(--bg-elevated)_82%,transparent)] p-4">
            <p className="text-xs uppercase tracking-wider text-[var(--text-3)] mb-3">Validation Summary</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 text-sm">
              <p>Rows accepted: <span className="font-semibold text-[var(--badge-success-text)]">{uploadSummary.acceptedRows}</span></p>
              <p>Rows rejected: <span className="font-semibold text-[var(--badge-danger-text)]">{uploadSummary.rejectedRows}</span></p>
              <p>Date range: <span className="font-semibold text-[var(--text-1)]">{uploadSummary.dateRange}</span></p>
              <p>Categories: <span className="font-semibold text-[var(--text-1)]">{uploadSummary.categoriesDetected.join(', ') || 'n/a'}</span></p>
              <p>Retrain: <span className="font-semibold text-[var(--text-1)]">{uploadSummary.modelsWillRetrain ? 'Yes' : 'No'}</span></p>
              <p>Reject reason: <span className="font-semibold text-[var(--text-1)]">{uploadSummary.rejectedRows > 0 ? uploadSummary.rejectedReason : 'None'}</span></p>
            </div>
          </div>
        )}
      </GlassCard>

      <GlassCard
        title="Model Status"
        subtitle="Category-level training and health status"
        icon={<ShieldAlert size={18} />}
      >
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[var(--text-3)] text-xs uppercase tracking-wider border-b border-[var(--border-soft)]">
                <th className="pb-3 pr-6 font-semibold">Category</th>
                <th className="pb-3 pr-6 font-semibold">Last Trained</th>
                <th className="pb-3 pr-6 font-semibold text-right">Training Points</th>
                <th className="pb-3 pr-6 font-semibold">Model Health</th>
                <th className="pb-3 font-semibold">Action</th>
              </tr>
            </thead>
            <tbody>
              {modelRows.map((row) => (
                <tr key={row.category} className="border-b border-[var(--border-soft)]">
                  <td className="py-3 pr-6 text-[var(--text-1)] font-semibold">{row.category}</td>
                  <td className="py-3 pr-6 text-[var(--text-2)]">{row.lastTrained === 'Unknown' ? 'Unknown' : new Date(row.lastTrained).toLocaleString('en-IN')}</td>
                  <td className="py-3 pr-6 text-right font-mono text-[var(--text-2)]">{row.trainingPoints}</td>
                  <td className="py-3 pr-6">
                    <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold border uppercase tracking-wider ${row.health === 'healthy' ? 'bg-emerald-500/10 text-[var(--badge-success-text)] border-emerald-500/30' : row.health === 'watch' ? 'bg-amber-500/10 text-[var(--badge-warning-text)] border-amber-500/30' : 'bg-red-500/10 text-[var(--badge-danger-text)] border-red-500/30'}`}>
                      {row.health}
                    </span>
                  </td>
                  <td className="py-3">
                    <button
                      onClick={() => handleRetrain(row.category)}
                      disabled={retrainingCategory === row.category}
                      className="px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-xs font-semibold text-slate-100 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                    >
                      <RefreshCw size={12} className={retrainingCategory === row.category ? 'animate-spin' : ''} />
                      Retrain
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </GlassCard>

      <GlassCard
        title="Recent AI Recommendations"
        subtitle="Audit trail from recommendation logs"
        icon={<Info size={18} />}
      >
        {recommendationFallback && (
          <p className="text-xs text-[var(--badge-warning-text)] mb-2">Recommendation log endpoint unavailable; showing fallback from latest forecast decisions.</p>
        )}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[var(--text-3)] text-xs uppercase tracking-wider border-b border-[var(--border-soft)]">
                <th className="pb-3 pr-6 font-semibold">Date</th>
                <th className="pb-3 pr-6 font-semibold">Category</th>
                <th className="pb-3 pr-6 font-semibold">Action</th>
                <th className="pb-3 pr-6 font-semibold text-right">Order Qty</th>
                <th className="pb-3 font-semibold text-right">Risk Score</th>
              </tr>
            </thead>
            <tbody>
              {recommendations.map((row, idx) => (
                <tr key={`${row.category}-${row.date}-${idx}`} className="border-b border-[var(--border-soft)]">
                  <td className="py-3 pr-6 text-[var(--text-2)]">{new Date(row.date || row.generated_at || Date.now()).toLocaleString('en-IN')}</td>
                  <td className="py-3 pr-6 text-[var(--text-1)]">{row.category}</td>
                  <td className="py-3 pr-6 text-[var(--text-2)]">{(row.action && row.action !== 'n/a' ? row.action : null) || (row.recommended_action && row.recommended_action !== 'n/a' ? row.recommended_action : null) || 'MAINTAIN'}</td>
                  <td className="py-3 pr-6 text-right font-mono text-[var(--text-2)]">{Number(row.order_quantity || 0).toLocaleString()}</td>
                  <td className="py-3 text-right font-mono text-[var(--text-2)]">{Math.round(Number(row.risk_score || 0) * 100)}%</td>
                </tr>
              ))}
              {!recommendations.length && (
                <tr>
                  <td colSpan={5} className="py-4 text-center text-[var(--text-3)]">No recommendation history available.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </GlassCard>

      <GlassCard
        title="Advanced Settings"
        subtitle="Inventory configuration for optimization inputs"
        icon={<Package size={18} />}
      >
        <button
          onClick={() => setAdvancedOpen((v) => !v)}
          className="w-full flex items-center justify-between rounded-xl border border-[var(--border)] bg-[color-mix(in_srgb,var(--bg-elevated)_82%,transparent)] px-4 py-3 text-sm font-semibold text-[var(--text-1)]"
        >
          <span>Inventory Configuration</span>
          {advancedOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
        {advancedOpen && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-4">
            {CATEGORIES.map((category) => (
              <div key={category} className="space-y-2.5">
                <label className="text-xs font-semibold text-[var(--text-3)] uppercase tracking-wider">{category} Stock</label>
                <div className="relative group">
                  <input
                    type="number"
                    min={0}
                    value={inventoryDraft[category]}
                    onChange={(e) => {
                      const nextValue = e.target.value;
                      setInventoryDraft((prev) => ({
                        ...prev,
                        [category]: nextValue === '' ? '' : Number(nextValue),
                      }));
                      setApplyMessage('');
                      setApplyError('');
                    }}
                    className="w-full bg-[var(--bg)] border border-[var(--border)] rounded-xl px-4 py-3 text-[var(--text-1)] focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500/30 outline-none transition-all font-mono"
                  />
                  <span className="absolute right-4 top-1/2 -translate-y-1/2 text-xs text-[var(--text-3)] font-medium">units</span>
                </div>
              </div>
            ))}
            <div className="md:col-span-3 flex items-center gap-3">
              <button
                onClick={handleApplyInventoryChanges}
                disabled={isApplying || !hasInventoryChanges}
                className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {isApplying && <RefreshCw size={14} className="animate-spin" />}
                {isApplying ? 'Applying...' : 'Apply Changes'}
              </button>
              {applyMessage && <span className="text-[var(--badge-success-text)] text-sm">{applyMessage}</span>}
              {applyError && <span className="text-[var(--badge-danger-text)] text-sm">{applyError}</span>}
            </div>
          </div>
        )}
      </GlassCard>
    </div>
  );
};

export default DataManagement;



