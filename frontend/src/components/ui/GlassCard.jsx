const GlassCard = ({ title, subtitle, icon, className, headerRight, children, noPadding }) => {
  return (
    <div className={`glass-card overflow-hidden ${className || ''}`}>
      {title && (
        <div className="flex items-center justify-between border-b border-[var(--border-soft)] px-6 py-4">
          <div className="flex items-center gap-3">
            {icon && (
              <span className="rounded-xl bg-gradient-to-br from-sky-500/18 to-indigo-500/18 p-2 text-[var(--brand-3)] shadow-[0_6px_18px_rgba(14,116,144,0.22)]">
                {icon}
              </span>
            )}
            <div>
              <h3 className="text-primary font-[var(--font-display)] text-[15px] font-semibold tracking-tight">{title}</h3>
              {subtitle && <p className="text-muted mt-0.5 text-xs">{subtitle}</p>}
            </div>
          </div>
          {headerRight && <div>{headerRight}</div>}
        </div>
      )}
      <div className={noPadding ? '' : 'p-6'}>{children}</div>
    </div>
  );
};

export default GlassCard;


