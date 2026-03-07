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
  // Step-1: SKU Master upload state
  const [skuFile, setSkuFile] = useState(null);
  const [skuUploading, setSkuUploading] = useState(false);
  const [skuProgress, setSkuProgress] = useState(0);
  const [skuStatus, setSkuStatus] = useState(null);   // 'success' | 'error' | null
  const [skuError, setSkuError] = useState('');
  const [skuDragOver, setSkuDragOver] = useState(false);
  // Step-2: Sales Data upload state
  const [salesFile, setSalesFile] = useState(null);
  const [salesUploading, setSalesUploading] = useState(false);
  const [salesProgress, setSalesProgress] = useState(0);
  const [salesStatus, setSalesStatus] = useState(null); // 'success' | 'error' | null
  const [salesError, setSalesError] = useState('');
  const [salesDragOver, setSalesDragOver] = useState(false);
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

  // Generic upload helper — used by both steps
  const uploadFile = async (file, {
    setUploading, setProgress, setStatus, setError, onSuccess,
  }) => {
    if (!file) return;
    setUploading(true);
    setProgress(0);
    setStatus(null);
    setError('');
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await apiClient.post('/upload_csv', formData, {
        onUploadProgress: (evt) => {
          if (evt.total) setProgress(Math.max(1, Math.round((evt.loaded / evt.total) * 100)));
        },
      });
      setStatus('success');
      setProgress(100);
      if (onSuccess) await onSuccess(response);
    } catch (err) {
      setStatus('error');
      const details = err?.response?.data?.errors?.[0]?.issue;
      setError(details || err?.response?.data?.message || 'CSV upload failed.');
    } finally {
      setUploading(false);
    }
  };

  const handleSkuUpload = () => uploadFile(skuFile, {
    setUploading: setSkuUploading,
    setProgress: setSkuProgress,
    setStatus: setSkuStatus,
    setError: setSkuError,
    onSuccess: async () => {
      const nowIso = new Date().toISOString();
      CATEGORIES.forEach((c) => localStorage.setItem(`last_upload_${c}`, nowIso));
    },
  });

  const handleSalesUpload = () => uploadFile(salesFile, {
    setUploading: setSalesUploading,
    setProgress: setSalesProgress,
    setStatus: setSalesStatus,
    setError: setSalesError,
    onSuccess: async (response) => {
      const nowIso = new Date().toISOString();
      CATEGORIES.forEach((c) => localStorage.setItem(`last_upload_${c}`, nowIso));
      const summary = salesFile ? await parseCsvSummary(salesFile) : null;
      if (summary) {
        setUploadSummary({
          ...summary,
          acceptedRows: Number(response?.data?.records_inserted || summary.acceptedRows),
          modelsWillRetrain: true,
        });
      }
      await loadOperationalData(inventoryValues);
    },
  });

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
        subtitle="Upload CSV files and validate before retraining"
        icon={<FileSpreadsheet size={18} />}
      >
        {/* Quick-seed row */}
        <div className="mb-6">
          <button
            onClick={handleSeedDemo}
            disabled={seeding}
            className="group w-full relative overflow-hidden p-5 rounded-xl bg-gradient-to-br from-blue-600/20 to-blue-700/10 border border-blue-500/20 hover:border-blue-500/40 transition-all duration-300 cursor-pointer flex items-center justify-center gap-4 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <div className="p-3 bg-blue-500/15 rounded-xl group-hover:scale-110 transition-transform duration-300 shrink-0">
              {seeding ? <RefreshCw size={22} className="text-blue-400 animate-spin" /> : <Database size={22} className="text-blue-400" />}
            </div>
            <div className="text-left">
              <p className="font-bold text-[var(--text-1)] text-sm">{seeding ? 'Seeding demo data...' : 'Use Demo Dataset'}</p>
              <p className="text-xs text-[var(--text-3)] mt-0.5">
                {seedStatus?.ok ? `✓ Loaded ${seedStatus.skus} SKUs + ${seedStatus.sales} sales rows` : seedStatus?.message || 'One-click load of seeded sample data — no files needed'}
              </p>
            </div>
          </button>
        </div>

        {/* Divider */}
        <div className="flex items-center gap-3 mb-6">
          <div className="flex-1 h-px bg-[var(--border)]" />
          <span className="text-xs text-[var(--text-3)] font-semibold uppercase tracking-wider">or upload your own CSVs</span>
          <div className="flex-1 h-px bg-[var(--border)]" />
        </div>

        {/* Two-step upload */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">

          {/* ── Step 1: SKU Master ────────────────────────────── */}
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <span className={`w-6 h-6 rounded-full text-xs font-bold flex items-center justify-center shrink-0 ${skuStatus === 'success' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40' : 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                }`}>
                {skuStatus === 'success' ? '✓' : '1'}
              </span>
              <div>
                <p className="text-sm font-semibold text-[var(--text-1)]">SKU Master</p>
                <p className="text-xs text-[var(--text-3)]">Products, categories, prices &amp; stock</p>
              </div>
            </div>

            {/* Drop zone */}
            <div
              onDragOver={(e) => { e.preventDefault(); setSkuDragOver(true); }}
              onDragLeave={() => setSkuDragOver(false)}
              onDrop={(e) => { e.preventDefault(); setSkuDragOver(false); const f = e.dataTransfer?.files?.[0]; if (f) { setSkuFile(f); setSkuStatus(null); setSkuError(''); } }}
              className={`relative p-5 rounded-xl border-2 border-dashed transition-all duration-300 flex flex-col items-center justify-center gap-2 text-center min-h-[120px] ${skuDragOver ? 'border-blue-500 bg-blue-500/10 scale-[1.01]' :
                  skuStatus === 'success' ? 'border-emerald-500/40 bg-emerald-500/5' :
                    'border-[var(--border)] hover:border-white/20 bg-white/[0.015] hover:bg-[color-mix(in_srgb,var(--bg-elevated)_76%,transparent)]'
                }`}
            >
              <input type="file" accept=".csv" className="absolute inset-0 opacity-0 cursor-pointer z-10"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) { setSkuFile(f); setSkuStatus(null); setSkuError(''); } }} />
              <CloudUpload size={22} className={skuStatus === 'success' ? 'text-emerald-400' : 'text-[var(--text-3)]'} />
              <p className="text-xs font-semibold text-[var(--text-1)] truncate max-w-[180px]">
                {skuFile ? skuFile.name : 'Drag & drop or click to browse'}
              </p>
              <p className="text-[10px] text-[var(--text-3)]">Cols: sku_id · product_name · category · mrp · cost · current_inventory</p>
            </div>

            {/* Upload btn + status */}
            <div className="flex items-center gap-3">
              <button
                onClick={handleSkuUpload}
                disabled={!skuFile || skuUploading}
                className="px-3 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {skuUploading ? 'Uploading...' : 'Upload SKU Master'}
              </button>
              {skuStatus === 'success' && <span className="text-[var(--badge-success-text)] text-xs flex items-center gap-1"><CheckCircle2 size={12} />Done</span>}
              {skuStatus === 'error' && <span className="text-[var(--badge-danger-text)] text-xs flex items-center gap-1"><AlertCircle size={12} />{skuError}</span>}
            </div>
            {(skuUploading || skuProgress > 0) && (
              <div className="h-1.5 w-full bg-white/10 rounded-full overflow-hidden">
                <div className="h-full bg-blue-500 transition-all" style={{ width: `${skuProgress}%` }} />
              </div>
            )}
          </div>

          {/* ── Step 2: Sales Data ────────────────────────────── */}
          <div className={`flex flex-col gap-3 transition-opacity duration-300 ${skuStatus === 'success' ? 'opacity-100' : 'opacity-50 pointer-events-none'}`}>
            <div className="flex items-center gap-2">
              <span className={`w-6 h-6 rounded-full text-xs font-bold flex items-center justify-center shrink-0 ${salesStatus === 'success' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40' :
                  skuStatus === 'success' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' : 'bg-white/10 text-[var(--text-3)] border border-white/10'
                }`}>
                {salesStatus === 'success' ? '✓' : '2'}
              </span>
              <div>
                <p className="text-sm font-semibold text-[var(--text-1)]">Sales Data</p>
                <p className="text-xs text-[var(--text-3)]">Historical sales — triggers model retraining</p>
              </div>
              {skuStatus !== 'success' && (
                <span className="ml-auto text-[10px] text-amber-400 border border-amber-400/30 rounded px-1.5 py-0.5 bg-amber-400/10">Upload SKU first</span>
              )}
            </div>

            {/* Drop zone */}
            <div
              onDragOver={(e) => { e.preventDefault(); setSalesDragOver(true); }}
              onDragLeave={() => setSalesDragOver(false)}
              onDrop={(e) => { e.preventDefault(); setSalesDragOver(false); const f = e.dataTransfer?.files?.[0]; if (f) { setSalesFile(f); setSalesStatus(null); setSalesError(''); } }}
              className={`relative p-5 rounded-xl border-2 border-dashed transition-all duration-300 flex flex-col items-center justify-center gap-2 text-center min-h-[120px] ${salesDragOver ? 'border-blue-500 bg-blue-500/10 scale-[1.01]' :
                  salesStatus === 'success' ? 'border-emerald-500/40 bg-emerald-500/5' :
                    'border-[var(--border)] hover:border-white/20 bg-white/[0.015]'
                }`}
            >
              <input type="file" accept=".csv" className="absolute inset-0 opacity-0 cursor-pointer z-10"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) { setSalesFile(f); setSalesStatus(null); setSalesError(''); } }} />
              <CloudUpload size={22} className={salesStatus === 'success' ? 'text-emerald-400' : 'text-[var(--text-3)]'} />
              <p className="text-xs font-semibold text-[var(--text-1)] truncate max-w-[180px]">
                {salesFile ? salesFile.name : 'Drag & drop or click to browse'}
              </p>
              <p className="text-[10px] text-[var(--text-3)]">Cols: date · sku_id · units_sold</p>
            </div>

            {/* Upload btn + status */}
            <div className="flex items-center gap-3">
              <button
                onClick={handleSalesUpload}
                disabled={!salesFile || salesUploading || skuStatus !== 'success'}
                className="px-3 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {salesUploading ? 'Uploading...' : 'Upload Sales Data'}
              </button>
              {salesStatus === 'success' && <span className="text-[var(--badge-success-text)] text-xs flex items-center gap-1"><CheckCircle2 size={12} />Done — models retraining</span>}
              {salesStatus === 'error' && <span className="text-[var(--badge-danger-text)] text-xs flex items-center gap-1"><AlertCircle size={12} />{salesError}</span>}
            </div>
            {(salesUploading || salesProgress > 0) && (
              <div className="h-1.5 w-full bg-white/10 rounded-full overflow-hidden">
                <div className="h-full bg-blue-500 transition-all" style={{ width: `${salesProgress}%` }} />
              </div>
            )}
          </div>
        </div>

        {/* Validation summary after sales upload */}
        {uploadSummary && (
          <div className="mt-5 rounded-xl border border-[var(--border)] bg-[color-mix(in_srgb,var(--bg-elevated)_82%,transparent)] p-4">
            <p className="text-xs uppercase tracking-wider text-[var(--text-3)] mb-3">Sales Validation Summary</p>
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



