# MarketPulse AI — Frontend

React dashboard for the MarketPulse AI inventory forecasting platform.

## Setup

```bash
npm install
npm run dev        # Development server at http://localhost:5173
npm run build      # Production build
npm run preview    # Preview production build
```

## Stack

- React 19 + Vite 7
- Tailwind CSS v4 (via `@tailwindcss/vite` plugin)
- Recharts for data visualization
- Lucide React for icons
- Axios for API calls

## Pages

- **Portfolio Overview** — KPI cards, inventory health table, risk distribution and inventory gap charts, interactive risk drawer for high-risk categories
- **Category Intelligence** — Per-category demand forecast with historical/predicted lines, confidence bands, decision summary with recommended actions
- **Data Management** — CSV upload (drag-and-drop), inventory config, demo dataset loader

## Structure

```
src/
├── components/
│   └── ui/            # GlassCard, StatCard, RiskDrawer
├── pages/             # PortfolioOverview, CategoryIntelligence, DataManagement
├── App.jsx            # Tab navigation shell
├── main.jsx           # Entry point
└── index.css          # Global styles, animations, glass-morphism
```
