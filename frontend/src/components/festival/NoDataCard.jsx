export default function NoDataCard({ year, subtext = 'No records found' }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
      <p className="text-sm font-semibold text-[#E2E8F0]">{year}</p>
      <p className="mt-1 text-sm text-[#94A3B8]">Data Not Available</p>
      <p className="mt-0.5 text-xs text-[#64748B]">{subtext}</p>
    </div>
  );
}
