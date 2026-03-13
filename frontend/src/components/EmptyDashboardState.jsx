const EmptyDashboardState = ({ onboarding, title = 'Connect a data source to get started.' }) => {
  const steps = onboarding?.steps || [];
  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--panel)] p-6">
      <p className="text-lg font-semibold text-[var(--text-1)]">{title}</p>
      <p className="mt-2 text-sm text-[var(--text-3)]">
        MarketPulse only shows your own store data. Connect Shopify or upload CSV files to populate forecasts and inventory insights.
      </p>
      <div className="mt-5 grid gap-3 md:grid-cols-3">
        {steps.map((step) => (
          <div key={step.id} className="rounded-xl border border-[var(--border)] bg-[var(--panel-soft)] px-4 py-3">
            <p className="text-xs uppercase tracking-wider text-[var(--text-3)]">
              {step.completed ? 'Completed' : 'Next step'}
            </p>
            <p className="mt-1 text-sm font-semibold text-[var(--text-1)]">{step.label}</p>
          </div>
        ))}
      </div>
    </div>
  );
};

export default EmptyDashboardState;
