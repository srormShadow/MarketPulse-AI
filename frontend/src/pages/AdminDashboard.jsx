import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Users,
  Building2,
  Store,
  Package,
  ShoppingCart,
  LogOut,
  Sparkles,
  RefreshCw,
  LayoutDashboard,
  Moon,
  Sun,
} from 'lucide-react';
import { apiClient } from '../api/client';
import { useAuth } from '../context/AuthContext';

const StatCard = ({ icon: Icon, label, value, color }) => (
  <div className="rounded-2xl border border-[var(--border-soft)] bg-[color-mix(in_srgb,var(--panel)_90%,transparent)] p-5 shadow-[var(--shadow-md)] backdrop-blur-xl">
    <div className="flex items-center gap-3">
      <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${color}`}>
        <Icon size={18} className="text-white" />
      </div>
      <div>
        <p className="text-2xl font-bold text-[var(--text-1)]">{value ?? '—'}</p>
        <p className="text-xs text-[var(--text-3)]">{label}</p>
      </div>
    </div>
  </div>
);

const DataTable = ({ title, columns, rows, emptyText }) => (
  <div className="rounded-2xl border border-[var(--border-soft)] bg-[color-mix(in_srgb,var(--panel)_90%,transparent)] p-5 shadow-[var(--shadow-md)] backdrop-blur-xl">
    <h3 className="mb-4 text-sm font-semibold text-[var(--text-1)]">{title}</h3>
    {rows.length === 0 ? (
      <p className="text-sm text-[var(--text-3)]">{emptyText || 'No data'}</p>
    ) : (
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border-soft)]">
              {columns.map((col) => (
                <th key={col.key} className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider text-[var(--text-3)]">
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr
                key={i}
                className="border-b border-[var(--border-soft)] transition-colors hover:bg-[color-mix(in_srgb,var(--panel-soft)_85%,transparent)]"
              >
                {columns.map((col) => (
                  <td key={col.key} className="px-3 py-2.5 text-[var(--text-2)]">
                    {col.render ? col.render(row[col.key], row) : (row[col.key] ?? '—')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )}
  </div>
);

const AdminDashboard = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [orgs, setOrgs] = useState([]);
  const [stores, setStores] = useState([]);
  const [loading, setLoading] = useState(true);
  const [theme, setTheme] = useState(() => localStorage.getItem('marketpulse-theme') || 'dark');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('marketpulse-theme', theme);
  }, [theme]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [statsRes, usersRes, orgsRes, storesRes] = await Promise.all([
        apiClient.get('/admin/stats'),
        apiClient.get('/admin/users'),
        apiClient.get('/admin/organizations'),
        apiClient.get('/admin/stores'),
      ]);
      setStats(statsRes.data);
      setUsers(usersRes.data?.users || []);
      setOrgs(orgsRes.data?.organizations || []);
      setStores(storesRes.data?.stores || []);
    } catch {
      // Silently ignore admin fetch failures for now.
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  const userColumns = [
    { key: 'id', label: 'ID' },
    { key: 'email', label: 'Email' },
    {
      key: 'role',
      label: 'Role',
      render: (val) => (
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
            val === 'admin' ? 'bg-purple-500/20 text-purple-400' : 'bg-sky-500/20 text-sky-400'
          }`}
        >
          {val}
        </span>
      ),
    },
    { key: 'organization_id', label: 'Org ID' },
  ];

  const orgColumns = [
    { key: 'id', label: 'ID' },
    { key: 'name', label: 'Name' },
    {
      key: 'plan',
      label: 'Plan',
      render: (val) => (
        <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-xs font-semibold text-emerald-400">
          {val}
        </span>
      ),
    },
  ];

  const storeColumns = [
    { key: 'id', label: 'ID' },
    { key: 'shop_domain', label: 'Store Domain' },
    {
      key: 'is_active',
      label: 'Status',
      render: (val) => (
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
            val ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
          }`}
        >
          {val ? 'Active' : 'Inactive'}
        </span>
      ),
    },
    {
      key: 'last_synced_at',
      label: 'Last Synced',
      render: (val) => (val ? new Date(val).toLocaleDateString() : '—'),
    },
  ];

  return (
    <div className="theme-transition min-h-screen bg-[radial-gradient(circle_at_8%_0%,color-mix(in_srgb,var(--brand-1)_22%,transparent),transparent_38%),radial-gradient(circle_at_100%_10%,color-mix(in_srgb,var(--brand-3)_20%,transparent),transparent_35%),linear-gradient(180deg,var(--bg),var(--bg-2))]">
      <aside className="fixed left-0 top-0 z-30 flex h-screen w-64 flex-col border-r border-[var(--border-soft)] bg-[color-mix(in_srgb,var(--brand-1)_94%,transparent)] px-5 py-6 backdrop-blur-xl">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-purple-500 to-indigo-600 font-bold text-white">
            MP
          </div>
          <div>
            <p className="text-xs tracking-[0.16em] text-[color-mix(in_srgb,var(--text-1)_78%,transparent)]">MARKETPULSE</p>
            <h1 className="text-lg font-bold leading-tight text-[var(--text-1)]">Admin Panel</h1>
          </div>
        </div>

        <div className="mb-6 h-px bg-[var(--border-soft)]" />

        <nav className="space-y-2">
          <button className="flex w-full items-center gap-3 rounded-xl bg-[color-mix(in_srgb,var(--panel)_75%,transparent)] px-3 py-3 text-left text-sm font-semibold text-[var(--text-1)] ring-1 ring-[var(--border)]">
            <LayoutDashboard size={16} />
            Dashboard
          </button>
        </nav>

        <div className="mt-auto space-y-3">
          <div className="rounded-xl bg-[color-mix(in_srgb,var(--panel)_80%,transparent)] p-3 ring-1 ring-[var(--border-soft)]">
            <p className="text-xs text-[var(--text-3)]">Signed in as</p>
            <p className="truncate text-sm font-semibold text-[var(--text-1)]">{user?.email}</p>
            <p className="text-xs text-purple-400">{user?.role}</p>
          </div>

          <div className="flex gap-2">
            <button
              onClick={() => setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'))}
              className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-[var(--border-soft)] bg-[color-mix(in_srgb,var(--panel)_80%,transparent)] px-3 py-2 text-xs text-[var(--text-3)] transition-colors hover:text-[var(--text-1)]"
            >
              {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
              {theme === 'dark' ? 'Light' : 'Dark'}
            </button>
            <button
              onClick={handleLogout}
              className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-400 transition-colors hover:bg-red-500/20"
            >
              <LogOut size={14} />
              Logout
            </button>
          </div>
        </div>
      </aside>

      <main className="ml-64 min-h-screen p-8">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2 text-[var(--text-3)]">
              <Sparkles size={14} className="text-purple-400" />
              <span className="text-xs font-semibold">Admin Dashboard</span>
            </div>
            <h2 className="mt-1 text-2xl font-bold text-[var(--text-1)]">System Overview</h2>
          </div>
          <button
            onClick={loadData}
            disabled={loading}
            className="flex items-center gap-2 rounded-xl border border-[var(--border-soft)] bg-[color-mix(in_srgb,var(--panel)_82%,transparent)] px-4 py-2 text-sm text-[var(--text-2)] transition-colors hover:bg-[color-mix(in_srgb,var(--panel-soft)_90%,transparent)] disabled:opacity-50"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>

        <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <StatCard icon={Users} label="Total Users" value={stats?.total_users} color="bg-purple-500/20" />
          <StatCard icon={Building2} label="Organizations" value={stats?.total_organizations} color="bg-sky-500/20" />
          <StatCard icon={Store} label="Stores" value={stats?.total_stores} color="bg-emerald-500/20" />
          <StatCard icon={Package} label="SKUs" value={stats?.total_skus} color="bg-amber-500/20" />
          <StatCard icon={ShoppingCart} label="Sales Records" value={stats?.total_sales} color="bg-pink-500/20" />
        </div>

        <div className="space-y-6">
          <DataTable title="Users" columns={userColumns} rows={users} emptyText="No users found" />
          <DataTable title="Organizations" columns={orgColumns} rows={orgs} emptyText="No organizations found" />
          <DataTable title="Connected Stores" columns={storeColumns} rows={stores} emptyText="No stores connected" />
        </div>
      </main>
    </div>
  );
};

export default AdminDashboard;
