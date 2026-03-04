import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

const colorMap = {
  red: { border: 'border-red-500/25', bg: 'from-red-500/20 to-rose-500/10', text: 'text-red-400', glow: 'shadow-red-500/20' },
  blue: { border: 'border-cyan-500/25', bg: 'from-cyan-500/20 to-blue-500/10', text: 'text-cyan-400', glow: 'shadow-cyan-500/20' },
  emerald: { border: 'border-emerald-500/25', bg: 'from-emerald-500/20 to-green-500/10', text: 'text-emerald-400', glow: 'shadow-emerald-500/20' },
  amber: { border: 'border-amber-500/25', bg: 'from-amber-500/20 to-orange-500/10', text: 'text-amber-400', glow: 'shadow-amber-500/20' },
  purple: { border: 'border-fuchsia-500/25', bg: 'from-fuchsia-500/20 to-violet-500/10', text: 'text-fuchsia-400', glow: 'shadow-fuchsia-500/20' },
};

const StatCard = ({ label, value, icon, trend, trendValue, accentColor = 'blue', context, className }) => {
  const colors = colorMap[accentColor] || colorMap.blue;
  const TrendIcon = trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : Minus;
  const trendColor = trend === 'up' ? 'text-emerald-400' : trend === 'down' ? 'text-red-400' : 'text-[var(--text-3)]';

  return (
    <div className={`surface-card relative overflow-hidden border ${colors.border} p-5 shadow-lg ${colors.glow} transition-all duration-300 hover:-translate-y-0.5 hover:shadow-xl ${className || ''}`}>
      <div className={`pointer-events-none absolute inset-x-0 top-0 h-16 bg-gradient-to-b ${colors.bg} opacity-80`} />
      <div className="relative">
        <div className="mb-3 flex items-start justify-between">
          <div className={`rounded-xl bg-gradient-to-br ${colors.bg} p-2`}>{icon && React.cloneElement(icon, { size: 18, className: colors.text })}</div>
          {trend && (
            <div className={`flex items-center gap-1 text-xs ${trendColor}`}>
              <TrendIcon size={14} />
              {trendValue && <span>{trendValue}</span>}
            </div>
          )}
        </div>
        <p className="text-muted text-[11px] font-semibold uppercase tracking-[0.16em]">{label}</p>
        <p className={`mt-1 text-3xl font-bold leading-none ${colors.text}`}>{value}</p>
        {context && <p className="text-muted mt-2 text-xs">{context}</p>}
      </div>
    </div>
  );
};

export default StatCard;


