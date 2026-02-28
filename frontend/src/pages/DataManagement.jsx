import { useState } from 'react';
import {
  Package, FileSpreadsheet, CloudUpload, CheckCircle2,
  AlertCircle, Info, Clock, HardDrive, Rows3, Trash2,
} from 'lucide-react';
import GlassCard from '../components/ui/GlassCard';

// ── Mock Data ────────────────────────────────────────────────

const recentActivity = [
  { id: 1, filename: 'sales_q4_2025.csv',        date: '2025-12-15', rows: 12450, status: 'success', size: '2.4 MB' },
  { id: 2, filename: 'sku_master_dec.csv',        date: '2025-12-10', rows: 3200,  status: 'success', size: '890 KB' },
  { id: 3, filename: 'demand_forecast_input.csv', date: '2025-12-01', rows: 8900,  status: 'warning', size: '1.8 MB' },
  { id: 4, filename: 'sales_q3_2025.csv',        date: '2025-09-30', rows: 11200, status: 'success', size: '2.1 MB' },
];

const categoryDefaults = [
  { name: 'Snacks',     stock: 2800, icon: '🍿' },
  { name: 'Staples',    stock: 5100, icon: '🌾' },
  { name: 'Edible Oil', stock: 1900, icon: '🫒' },
];

// ── Component ────────────────────────────────────────────────

const DataManagement = () => {
  const [isDragOver, setIsDragOver] = useState(false);
  const [inventoryValues, setInventoryValues] = useState(
    Object.fromEntries(categoryDefaults.map((c) => [c.name, c.stock]))
  );

  const handleInventoryChange = (category, value) => {
    setInventoryValues((prev) => ({ ...prev, [category]: value }));
  };

  return (
    <div className="max-w-5xl space-y-8">
      {/* Inventory Configuration */}
      <GlassCard
        title="Inventory Configuration"
        subtitle="Current stock on hand used for reorder optimization"
        icon={<Package size={18} />}
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {categoryDefaults.map((cat) => (
            <div key={cat.name} className="space-y-2.5">
              <label className="flex items-center gap-2 text-xs font-semibold text-[#94A3B8] uppercase tracking-wider">
                <span className="text-base">{cat.icon}</span>
                {cat.name} Stock
              </label>
              <div className="relative group">
                <input
                  type="number"
                  value={inventoryValues[cat.name]}
                  onChange={(e) => handleInventoryChange(cat.name, Number(e.target.value))}
                  className="w-full bg-[#0B1220] border border-white/10 rounded-xl px-4 py-3.5 text-[#E2E8F0]
                    focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500/30 outline-none transition-all
                    font-mono text-lg group-hover:border-white/20"
                />
                <span className="absolute right-4 top-1/2 -translate-y-1/2 text-xs text-[#475569] font-medium">
                  units
                </span>
              </div>
              <div className="flex items-center justify-between text-[10px] text-[#475569] px-1">
                <span>Min: 0</span>
                <span>Default: {cat.stock.toLocaleString()}</span>
              </div>
            </div>
          ))}
        </div>
      </GlassCard>

      {/* Dataset Source */}
      <GlassCard
        title="Dataset Source"
        subtitle="Upload custom data or use the built-in demo dataset"
        icon={<FileSpreadsheet size={18} />}
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Demo Dataset */}
          <button className="group relative overflow-hidden p-6 rounded-xl
            bg-gradient-to-br from-blue-600/20 to-blue-700/10
            border border-blue-500/20 hover:border-blue-500/40
            transition-all duration-300 cursor-pointer
            flex flex-col items-center justify-center gap-3 text-center min-h-[180px]
            hover:shadow-[0_0_30px_rgba(59,130,246,0.1)]"
          >
            <div className="p-3.5 bg-blue-500/15 rounded-xl group-hover:scale-110 transition-transform duration-300">
              <FileSpreadsheet size={28} className="text-blue-400" />
            </div>
            <div>
              <p className="font-bold text-[#F1F5F9] text-base">Use Demo Dataset</p>
              <p className="text-xs text-[#64748B] mt-1 leading-relaxed">
                Pre-loaded with 12 months of synthetic<br />sales data across 3 categories
              </p>
            </div>
            <div className="absolute inset-0 bg-gradient-to-t from-blue-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
          </button>

          {/* Drag-and-Drop Upload Zone */}
          <div
            onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
            onDragLeave={() => setIsDragOver(false)}
            onDrop={(e) => { e.preventDefault(); setIsDragOver(false); }}
            className={`
              relative p-6 rounded-xl border-2 border-dashed transition-all duration-300
              flex flex-col items-center justify-center gap-3 text-center min-h-[180px] cursor-pointer
              ${isDragOver
                ? 'border-blue-500 bg-blue-500/10 shadow-[0_0_40px_rgba(59,130,246,0.15)] scale-[1.01]'
                : 'border-white/10 hover:border-white/20 bg-white/[0.015] hover:bg-white/[0.03]'
              }
            `}
          >
            <input type="file" className="absolute inset-0 opacity-0 cursor-pointer z-10" accept=".csv" />
            <div className={`p-3.5 rounded-xl transition-all duration-300 ${isDragOver ? 'bg-blue-500/15 scale-110' : 'bg-white/5'}`}>
              <CloudUpload size={28} className={`transition-colors duration-300 ${isDragOver ? 'text-blue-400' : 'text-[#64748B]'}`} />
            </div>
            <div>
              <p className="font-semibold text-[#E2E8F0]">
                {isDragOver ? 'Drop your file here' : 'Drag & drop CSV file'}
              </p>
              <p className="text-xs text-[#64748B] mt-1">or click to browse &middot; .csv files only</p>
            </div>
            {isDragOver && (
              <div className="absolute inset-0 bg-blue-500/5 rounded-xl pointer-events-none animate-pulse" />
            )}
          </div>
        </div>
      </GlassCard>

      {/* Recent Activity */}
      <GlassCard
        title="Recent Activity"
        subtitle="Upload and processing history"
        icon={<Clock size={18} />}
        noPadding
      >
        <div className="divide-y divide-white/5">
          {recentActivity.map((item) => (
            <div key={item.id} className="flex items-center gap-4 px-6 py-4 hover:bg-white/[0.02] transition-colors group">
              <div className={`p-2 rounded-lg shrink-0 ${item.status === 'success' ? 'bg-emerald-500/10' : 'bg-amber-500/10'}`}>
                {item.status === 'success'
                  ? <CheckCircle2 size={18} className="text-emerald-400" />
                  : <AlertCircle size={18} className="text-amber-400" />
                }
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-[#E2E8F0] text-sm truncate">{item.filename}</p>
                <p className="text-xs text-[#475569] mt-0.5">{item.date}</p>
              </div>
              <div className="hidden sm:flex items-center gap-4 text-xs text-[#64748B]">
                <span className="flex items-center gap-1.5">
                  <Rows3 size={12} className="text-[#475569]" />
                  {item.rows.toLocaleString()} rows
                </span>
                <span className="flex items-center gap-1.5">
                  <HardDrive size={12} className="text-[#475569]" />
                  {item.size}
                </span>
              </div>
              <button className="opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded-lg hover:bg-red-500/10 text-[#475569] hover:text-red-400">
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      </GlassCard>

      {/* Info Box */}
      <div className="p-6 rounded-xl bg-gradient-to-r from-blue-500/5 to-transparent border border-blue-500/15 flex items-start gap-4">
        <div className="p-2.5 bg-blue-500/10 rounded-xl shrink-0">
          <Info size={20} className="text-blue-400" />
        </div>
        <div>
          <h4 className="font-semibold text-blue-100 text-sm">Validation Ready</h4>
          <p className="text-sm text-blue-300/70 mt-1 leading-relaxed">
            System is ready for forecasting. Upload a valid sales history CSV to generate
            customized network intelligence. Required columns: <code className="text-blue-300/90 bg-blue-500/10 px-1.5 py-0.5 rounded text-xs">date</code>,{' '}
            <code className="text-blue-300/90 bg-blue-500/10 px-1.5 py-0.5 rounded text-xs">sku_id</code>,{' '}
            <code className="text-blue-300/90 bg-blue-500/10 px-1.5 py-0.5 rounded text-xs">units_sold</code>
          </p>
        </div>
      </div>
    </div>
  );
};

export default DataManagement;
