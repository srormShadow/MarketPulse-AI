export default function NoDataCard({ year, subtext = 'No records found' }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[color-mix(in_srgb,var(--bg-elevated)_82%,transparent)] p-3">
      <p className="text-sm font-semibold text-[var(--text-1)]">{year}</p>
      <p className="mt-1 text-sm text-[var(--text-3)]">Data Not Available</p>
      <p className="mt-0.5 text-xs text-[var(--text-3)]">{subtext}</p>
    </div>
  );
}



