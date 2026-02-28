const GlassCard = ({ title, subtitle, icon, className, headerRight, children, noPadding }) => {
  return (
    <div className={`glass-card shadow-xl shadow-black/20 ${className || ''}`}>
      {title && (
        <div className="px-6 py-4 border-b border-white/5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {icon && <span className="text-blue-400">{icon}</span>}
            <div>
              <h3 className="font-semibold text-[#F1F5F9] text-sm">{title}</h3>
              {subtitle && <p className="text-xs text-[#64748B] mt-0.5">{subtitle}</p>}
            </div>
          </div>
          {headerRight && <div>{headerRight}</div>}
        </div>
      )}
      <div className={noPadding ? '' : 'p-6'}>
        {children}
      </div>
    </div>
  );
};

export default GlassCard;
