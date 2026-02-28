import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

const colorMap = {
  red:     { border: 'border-red-500/30',     bg: 'bg-red-500/10',     text: 'text-red-400',     glow: 'shadow-red-500/10' },
  blue:    { border: 'border-blue-500/30',    bg: 'bg-blue-500/10',    text: 'text-blue-400',    glow: 'shadow-blue-500/10' },
  emerald: { border: 'border-emerald-500/30', bg: 'bg-emerald-500/10', text: 'text-emerald-400', glow: 'shadow-emerald-500/10' },
  amber:   { border: 'border-amber-500/30',   bg: 'bg-amber-500/10',   text: 'text-amber-400',   glow: 'shadow-amber-500/10' },
  purple:  { border: 'border-purple-500/30',  bg: 'bg-purple-500/10',  text: 'text-purple-400',  glow: 'shadow-purple-500/10' },
};

const StatCard = ({ label, value, icon, trend, trendValue, accentColor = 'blue', className }) => {
  const colors = colorMap[accentColor] || colorMap.blue;
  const TrendIcon = trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : Minus;
  const trendColor = trend === 'up' ? 'text-emerald-400' : trend === 'down' ? 'text-red-400' : 'text-[#64748B]';

  return (
    <div className={`
      glass-card p-5 border-l-2 ${colors.border}
      shadow-lg ${colors.glow}
      hover:shadow-xl hover:scale-[1.02] transition-all duration-300
      ${className || ''}
    `}>
      <div className="flex items-start justify-between mb-3">
        <div className={`p-2 rounded-lg ${colors.bg}`}>
          {icon && React.cloneElement(icon, { size: 18, className: colors.text })}
        </div>
        {trend && (
          <div className={`flex items-center gap-1 text-xs ${trendColor}`}>
            <TrendIcon size={14} />
            {trendValue && <span>{trendValue}</span>}
          </div>
        )}
      </div>
      <p className="text-xs uppercase tracking-wider text-[#94A3B8] font-semibold">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${colors.text}`}>{value}</p>
    </div>
  );
};

export default StatCard;
