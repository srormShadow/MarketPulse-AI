import datetime
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import requests
import streamlit as st

API_BASE = "http://127.0.0.1:8000"
CATEGORIES = ["Snacks", "Staples", "Edible Oil"]
DEFAULT_INVENTORY = {
    "Snacks": 1200,
    "Staples": 3500,
    "Edible Oil": 800
}

st.set_page_config(
    page_title="MarketPulse AI | Executive Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Global CSS: high-contrast dark design system ─────────────────────────
st.markdown("""
<style>
    /* Base */
    .stApp { background-color: #0B1220; }
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }

    /* Typography */
    h1, h2, h3, h4 {
        color: #F1F5F9 !important;
        font-family: 'Inter', sans-serif;
    }
    p, div, span, label {
        color: #94A3B8;
    }

    /* Metrics: make the big number pop */
    [data-testid="stMetricValue"] {
        color: #E2E8F0 !important;
        font-size: 1.6rem !important;
        font-weight: 700 !important;
    }
    [data-testid="stMetricLabel"] {
        color: #94A3B8 !important;
        font-size: 0.75rem !important;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }

    /* DataFrames */
    [data-testid="stDataFrame"] {
        background-color: #0F172A;
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 8px;
    }
    [data-testid="stDataFrame"] th {
        background-color: #1E293B !important;
        color: #F1F5F9 !important;
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    [data-testid="stDataFrame"] td {
        color: #E2E8F0 !important;
        background-color: #0F172A !important;
    }

    /* File uploader drop zone */
    [data-testid="stFileUploader"] {
        background-color: #0F172A;
        border: 1px dashed rgba(255,255,255,0.15);
        border-radius: 8px;
    }

    /* Section divider */
    hr { border-color: rgba(255,255,255,0.08) !important; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)
def fetch_all_forecasts():
    """Simulate parallel fetching of all categories for the executive view."""
    results = []
    
    # We use fixed parameters for the executive overview
    payload = {
        "n_days": 30,
        "current_inventory": 0,  # overridden below per category
        "lead_time_days": 7
    }

    for cat in CATEGORIES:
        category_payload = payload.copy()
        category_payload["current_inventory"] = DEFAULT_INVENTORY[cat]
        
        try:
            resp = requests.post(f"{API_BASE}/forecast/{cat}", json=category_payload, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                # Sum mean prediction for 30 day demand
                forecast_df = pd.DataFrame(data["forecast"])
                demand_30d = float(forecast_df["predicted_mean"].sum())
                
                decision = data["decision"]
                
                results.append({
                    "Category": cat,
                    "30D Forecast": round(demand_30d),
                    "Current Inventory": DEFAULT_INVENTORY[cat],
                    "Reorder Point": round(decision["reorder_point"]),
                    "Safety Stock": round(decision["safety_stock"]),
                    "Gap": DEFAULT_INVENTORY[cat] - decision["reorder_point"],
                    "Risk Score": decision["risk_score"],
                    "Recommended Action": decision["recommended_action"],
                    "_raw_forecast": forecast_df
                })
        except Exception as e:
            st.error(f"Failed to fetch {cat}: {str(e)}")
            
    return results

def render_header():
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown("<h1 style='margin-bottom:0; color:#F1F5F9;'>MarketPulse AI</h1>", unsafe_allow_html=True)
        st.markdown("<p style='font-size:1.05rem; color:#94A3B8; margin-top:2px;'>Retail Forecasting &amp; Inventory Intelligence</p>", unsafe_allow_html=True)
    with col2:
        st.markdown(
            f"<p style='text-align:right; margin-top:28px; color:#64748B; font-size:0.8rem;'>"
            f"Updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}</p>",
            unsafe_allow_html=True
        )
    st.markdown("<hr style='margin-top:4px;'>", unsafe_allow_html=True)

def render_kpi_strip(data):
    if not data:
        return
        
    total_categories = len(data)
    total_demand = sum(row["30D Forecast"] for row in data)
    total_inventory = sum(row["Current Inventory"] for row in data)
    
    high_risk_count = sum(1 for row in data if row["Risk Score"] >= 0.7)
    urgent_actions = sum(1 for row in data if row["Recommended Action"] == "URGENT_ORDER")
    
    total_gap = sum(row["Gap"] for row in data)

    cols = st.columns(6)
    
    with cols[0]:
        st.metric("Categories Monitored", total_categories)
    with cols[1]:
        st.metric("30D Projected Demand", f"{total_demand:,.0f}")
    with cols[2]:
        st.metric("Current Units on Hand", f"{total_inventory:,.0f}")
    with cols[3]:
        st.metric("Net Inventory Gap", f"{total_gap:,.0f}", delta="Deficit" if total_gap < 0 else "Surplus", delta_color="inverse")
    with cols[4]:
        st.metric("High Risk Categories", high_risk_count, delta="Critical" if high_risk_count > 0 else "Optimal", delta_color="inverse")
    with cols[5]:
        st.metric("Urgent Actions Pending", urgent_actions)

def render_inventory_health_table(data):
    st.markdown("<h3 style='color:#F1F5F9; margin-bottom:12px;'>Inventory Health Across Categories</h3>", unsafe_allow_html=True)

    if not data:
        st.warning("No data available from API.")
        return

    df = pd.DataFrame(data)
    display_df = df.drop(columns=["_raw_forecast"])
    display_df = display_df.sort_values(by="Risk Score", ascending=False).reset_index(drop=True)

    def highlight_risk(val):
        if isinstance(val, float):
            if val >= 0.7:
                return 'color: #EF4444; font-weight: 700;'
            elif val >= 0.4:
                return 'color: #F59E0B; font-weight: 700;'
            return 'color: #22C55E; font-weight: 700;'
        return ''

    def highlight_action(val):
        if val == "URGENT_ORDER":
            return 'color: #EF4444; font-weight: 700;'
        elif val == "ORDER":
            return 'color: #F59E0B; font-weight: 700;'
        elif val == "MONITOR":
            return 'color: #3B82F6; font-weight: 700;'
        return 'color: #22C55E; font-weight: 700;'

    def highlight_gap(val):
        if isinstance(val, (int, float)):
            return 'color: #F87171;' if val < 0 else 'color: #4ADE80;'
        return ''

    styled_df = (
        display_df.style
        .map(highlight_risk, subset=['Risk Score'])
        .map(highlight_action, subset=['Recommended Action'])
        .map(highlight_gap, subset=['Gap'])
        .format({"Risk Score": "{:.2f}", "Gap": "{:+.0f}"})
    )

    st.dataframe(styled_df, use_container_width=True, hide_index=True)


def render_risk_chart(data):
    """Full-width lollipop chart — Risk Score by Category."""
    if not data:
        return

    df = pd.DataFrame(data)
    risk_df = df.sort_values(by="Risk Score", ascending=True).reset_index(drop=True)

    def risk_color(score):
        if score > 0.7:
            return "#EF4444"
        if score > 0.4:
            return "#F59E0B"
        return "#22C55E"

    risk_df["Risk Color"] = risk_df["Risk Score"].apply(risk_color)

    action_labels = {
        "URGENT_ORDER": "🚨 Urgent",
        "ORDER": "⚠️ Order",
        "MONITOR": "👁 Monitor",
        "MAINTAIN": "✅ Healthy",
    }

    cats   = risk_df["Category"].tolist()
    scores = risk_df["Risk Score"].tolist()
    colors = risk_df["Risk Color"].tolist()

    fig = go.Figure()

    # Stem lines
    for cat, score, color in zip(cats, scores, colors):
        fig.add_trace(go.Scatter(
            x=[0, score], y=[cat, cat],
            mode="lines",
            line=dict(color=color, width=4),
            showlegend=False,
            hoverinfo="skip",
        ))

    # Dot heads with score label inside
    fig.add_trace(go.Scatter(
        x=scores, y=cats,
        mode="markers+text",
        marker=dict(color=colors, size=28, line=dict(width=2, color="#0E1117")),
        text=[f"{s:.2f}" for s in scores],
        textposition="middle center",
        textfont=dict(size=11, color="#0E1117", family="monospace"),
        customdata=[action_labels.get(a, a) for a in risk_df["Recommended Action"]],
        hovertemplate="<b>%{y}</b><br>Risk: %{x:.2f}<br>Action: %{customdata}<extra></extra>",
        showlegend=False,
    ))

    # Action badge annotations to the right of the dot
    for cat, score, action, color in zip(cats, scores, risk_df["Recommended Action"], colors):
        fig.add_annotation(
            x=score + 0.04, y=cat,
            text=action_labels.get(action, action),
            showarrow=False,
            font=dict(size=12, color=color),
            xanchor="left",
        )

    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=420,
        margin=dict(l=40, r=120, t=50, b=40),
        title=dict(text="Risk Score by Category", font=dict(size=15, color="#F1F5F9")),
        xaxis=dict(
            title="Risk Score (0 – 1)",
            title_font=dict(color="#94A3B8"),
            tickfont=dict(color="#94A3B8"),
            range=[0, 1.3],
            gridcolor="rgba(255,255,255,0.06)",
            zeroline=False,
        ),
        yaxis=dict(showgrid=False, tickfont=dict(color="#E2E8F0", size=13)),
    )
    fig.update_yaxes(automargin=True)

    st.plotly_chart(fig, use_container_width=True)


def render_gap_chart(data):
    """Full-width diverging lollipop — Inventory Gap by Category."""
    if not data:
        return

    df = pd.DataFrame(data)
    gap_df = df.sort_values(by="Gap", ascending=True).reset_index(drop=True)
    max_abs = max(abs(gap_df["Gap"].min()), abs(gap_df["Gap"].max()), 1)

    gap_colors = ["#F87171" if g < 0 else "#4ADE80" for g in gap_df["Gap"]]

    fig = go.Figure()

    # Arms from zero to gap value
    for i, row_data in gap_df.iterrows():
        fig.add_trace(go.Scatter(
            x=[0, row_data["Gap"]], y=[row_data["Category"], row_data["Category"]],
            mode="lines",
            line=dict(color=gap_colors[i], width=5),
            showlegend=False,
            hoverinfo="skip",
        ))

    # Endpoint dot + label
    gap_labels = [
        f"Deficit {abs(g):,.0f} units" if g < 0 else f"Surplus {g:,.0f} units"
        for g in gap_df["Gap"]
    ]
    fig.add_trace(go.Scatter(
        x=gap_df["Gap"].tolist(),
        y=gap_df["Category"].tolist(),
        mode="markers+text",
        marker=dict(color=gap_colors, size=24, line=dict(width=2, color="#0E1117")),
        text=[f"{g:+,.0f}" for g in gap_df["Gap"]],
        textposition=["middle right" if g >= 0 else "middle left" for g in gap_df["Gap"]],
        textfont=dict(size=12, color="#E2E8F0"),
        customdata=gap_labels,
        hovertemplate="<b>%{y}</b><br>%{customdata}<extra></extra>",
        showlegend=False,
    ))

    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=420,
        margin=dict(l=40, r=100, t=50, b=40),
        title=dict(text="Inventory Gap by Category  (red = deficit · green = surplus)", font=dict(size=15, color="#F1F5F9")),
        xaxis=dict(
            title="Units",
            title_font=dict(color="#94A3B8"),
            tickfont=dict(color="#94A3B8"),
            range=[-max_abs * 1.35, max_abs * 1.35],
            gridcolor="rgba(255,255,255,0.06)",
            zeroline=True,
            zerolinecolor="rgba(255,255,255,0.25)",
            zerolinewidth=2,
        ),
        yaxis=dict(showgrid=False, tickfont=dict(color="#E2E8F0", size=13)),
    )
    fig.update_yaxes(automargin=True)

    st.plotly_chart(fig, use_container_width=True)





def render_category_drilldown(data):
    st.markdown("### Category Deep Dive")
    
    if not data:
        return
        
    cat_names = [row["Category"] for row in data]
    selected_cat = st.selectbox("Select Category for Detailed Analysis", cat_names, label_visibility="collapsed")
    
    row = next(r for r in data if r["Category"] == selected_cat)
    forecast_df = row["_raw_forecast"]
    forecast_df["date"] = pd.to_datetime(forecast_df["date"])
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        fig = go.Figure()

        # Confidence Interval
        fig.add_trace(go.Scatter(
            x=forecast_df["date"],
            y=forecast_df["upper_95"],
            mode="lines",
            line=dict(width=0),
            showlegend=False,
            hoverinfo='skip'
        ))
        fig.add_trace(go.Scatter(
            x=forecast_df["date"],
            y=forecast_df["lower_95"],
            mode="lines",
            fill='tonexty',
            fillcolor='rgba(59, 130, 246, 0.18)',  # Modern, softer blue
            line=dict(width=0),
            name="95% Confidence"
        ))
        
        # Subtle Glow Layer (helps line stand out on dark background)
        fig.add_trace(go.Scatter(
            x=forecast_df["date"],
            y=forecast_df["predicted_mean"],
            mode="lines",
            line=dict(color="rgba(59, 130, 246, 0.4)", width=8),
            showlegend=False,
            hoverinfo='skip'
        ))

        # Mean Forecast (Solid Line)
        fig.add_trace(go.Scatter(
            x=forecast_df["date"],
            y=forecast_df["predicted_mean"],
            mode="lines",
            line=dict(color="#3B82F6", width=4),
            name="Expected Demand"
        ))
        
        # Reorder Point Line
        fig.add_hline(
            y=row["Reorder Point"] / 30, # Approximating daily reorder representation
            line_dash="dash",
            line_width=3,
            line_color="#F59E0B",  # Crisp orange
            opacity=1,
            annotation_text=f"Reorder Threshold ({row['Reorder Point']})",
            annotation_position="top right",
            annotation_font=dict(color="#F59E0B", size=12, weight="bold")
        )

        fig.update_layout(
            template="plotly_dark",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            hovermode="x unified",
            margin=dict(l=0, r=0, t=20, b=0),
            xaxis=dict(
                showgrid=False,
                zeroline=False,
                tickfont=dict(color="#CBD5E1")
            ),
            yaxis=dict(
                gridcolor="rgba(255,255,255,0.06)", 
                zeroline=False,
                title="Units / Day",
                title_font=dict(color="#94A3B8"),
                tickfont=dict(color="#CBD5E1")
            ),
            legend=dict(
                orientation="h", 
                yanchor="bottom", y=1.02, 
                xanchor="right", x=1,
                font=dict(color="#E2E8F0")
            )
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown(f"**Action Required:**")
        
        action = row["Recommended Action"]
        if action == "URGENT_ORDER":
            st.error("🚨 URGENT ORDER Placed")
        elif action == "ORDER":
            st.warning("⚠️ ORDER Required")
        else:
            st.success("✅ MAINTAIN")
            
        st.markdown("---")
        st.metric("30D Demand", f"{row['30D Forecast']:,.0f}")
        st.metric("Current Stock", f"{row['Current Inventory']:,.0f}")
        
        # Refactored Net Gap
        gap = row["Gap"]
        if gap < 0:
            st.metric("Net Gap", f"Inventory Deficit: {abs(gap):,.0f}")
        elif gap > 0:
            st.metric("Net Gap", f"Inventory Surplus: {gap:,.0f}")
        else:
            st.metric("Net Gap", "Balanced: 0")


def render_data_management():
    """Data Management tab: demo mode or CSV upload with validation."""

    st.markdown("### Dataset Source")
    st.markdown("<p>Choose how to supply data to the forecasting engine.</p>", unsafe_allow_html=True)

    mode = st.radio(
        "",
        ["📦  Use Demo Dataset", "📂  Upload My Data"],
        horizontal=True,
        label_visibility="collapsed",
    )

    st.markdown("<hr style='border-color:#2D333B;'>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # DEMO MODE
    # ------------------------------------------------------------------
    if mode == "📦  Use Demo Dataset":
        st.markdown("#### Demo Dataset")
        st.markdown(
            "The demo dataset contains **12 months of synthetic sales history** "
            "across 3 retail categories, pre-loaded into the system."
        )

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Records", "3,285")
        col2.metric("Categories", "3")
        col3.metric("Date Range", "365 days")
        col4.metric("SKUs", "9")

        st.markdown("<br>", unsafe_allow_html=True)

        with st.expander("📋  Category Breakdown", expanded=True):
            st.markdown("""
| Category | SKUs | Avg Daily Units | Festivals Modeled |
|---|---|---|---|
| Snacks | 3 | ~198 | Diwali, Navratri, Christmas |
| Staples | 3 | ~246 | Diwali, Pongal, Eid |
| Edible Oil | 3 | ~223 | Diwali, Pongal, Eid |
            """)

        st.success("✅  Demo data is active. Navigate to Portfolio Overview to view forecasts.")

    # ------------------------------------------------------------------
    # UPLOAD MODE
    # ------------------------------------------------------------------
    else:
        st.markdown("#### Upload Sales Data (CSV)")
        st.markdown(
            "Upload a CSV with columns: `date`, `sku_id`, `units_sold`. "
            "The system will validate and ingest it automatically."
        )

        uploaded = st.file_uploader(
            "",
            type=["csv"],
            label_visibility="collapsed",
            key="sales_upload",
        )

        if uploaded is not None:
            import io

            try:
                df = pd.read_csv(io.BytesIO(uploaded.read()))
            except Exception as exc:
                st.error(f"Could not parse file: {exc}")
                return

            # ── Preview ───────────────────────────────────────────────
            st.markdown("#### Preview (first 10 rows)")
            st.dataframe(df.head(10), use_container_width=True, hide_index=True)

            # ── Validation ────────────────────────────────────────────
            st.markdown("#### Validation Report")

            required_cols = {"date", "sku_id", "units_sold"}
            missing_cols  = required_cols - set(c.lower().strip() for c in df.columns)

            checks = []

            if missing_cols:
                checks.append((False, f"Missing required columns: {', '.join(missing_cols)}"))
            else:
                df.columns = [c.lower().strip() for c in df.columns]

                # Missing values
                nulls = int(df[["date", "sku_id", "units_sold"]].isnull().sum().sum())
                checks.append((
                    nulls == 0,
                    f"Missing values: {nulls}" if nulls else "No missing values"
                ))

                # Negative units
                neg = int((pd.to_numeric(df["units_sold"], errors="coerce") < 0).sum())
                checks.append((
                    neg == 0,
                    f"Negative unit values: {neg} rows" if neg else "No negative values"
                ))

                # Duplicates
                dups = int(df.duplicated(subset=["date", "sku_id"]).sum())
                checks.append((
                    dups == 0,
                    f"Duplicate (date, sku_id) rows: {dups}" if dups else "No duplicate rows"
                ))

                # Date range
                try:
                    dates    = pd.to_datetime(df["date"], errors="coerce")
                    valid_dt = dates.notna().sum()
                    date_range = f"{dates.min().date()} → {dates.max().date()}  ({(dates.max()-dates.min()).days + 1} days)"
                    checks.append((True, f"Date range: {date_range}"))
                except Exception:
                    checks.append((False, "Could not parse date column"))

            for ok, msg in checks:
                if ok:
                    st.success(f"✅  {msg}")
                else:
                    st.error(f"❌  {msg}")

            all_ok = all(ok for ok, _ in checks)

            st.markdown("<br>", unsafe_allow_html=True)

            if all_ok:
                if st.button("🚀  Run Forecast & Update Dashboard", type="primary"):
                    with st.spinner("Uploading and generating forecasts..."):
                        try:
                            import io as _io
                            uploaded.seek(0)
                            resp = requests.post(
                                f"{API_BASE}/upload/sales",
                                files={"file": (uploaded.name, uploaded, "text/csv")},
                                timeout=30,
                            )
                            if resp.status_code == 200:
                                st.success("✅  Data uploaded successfully. Switch to Portfolio Overview to view updated forecasts.")
                                st.cache_data.clear()
                            else:
                                st.error(f"Upload failed: {resp.json().get('detail', resp.text)}")
                        except Exception as exc:
                            st.error(f"Upload error: {exc}")
            else:
                st.warning("Fix the validation errors above before uploading.")



def main():
    render_header()

    with st.spinner("Compiling executive intelligence..."):
        data = fetch_all_forecasts()

    if not data:
        st.warning("Ensure backend API is running at http://127.0.0.1:8000")
        return

    # ── Session-state-controlled navigation ───────────────────────────────────
    # st.tabs() resets to tab 0 on every rerun — we use session_state instead
    # so that file uploads (or any other rerun trigger) keep the user on the
    # tab they selected.
    TABS = ["📊  Portfolio Overview", "🔎  Category Intelligence", "🗂  Data Management"]

    if "active_tab" not in st.session_state:
        st.session_state.active_tab = TABS[0]

    # Horizontal radio styled to look like a native modern tab bar
    st.markdown("""
    <style>
        div[role="radiogroup"] { 
            gap: 12px; 
            padding-bottom: 8px;
        }
        div[role="radiogroup"] label {
            padding: 8px 24px;
            border: 1px solid rgba(255,255,255,0.05);
            border-radius: 8px !important;
            cursor: pointer;
            background: #111827;
            color: #94A3B8;
            font-size: 0.95rem;
            font-weight: 500;
            transition: all 0.2s ease-in-out;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        }
        div[role="radiogroup"] label:hover {
            background: #1F2937;
            color: #E2E8F0;
        }
        div[role="radiogroup"] label:has(input:checked) {
            background: #2563EB !important;
            color: #FFFFFF !important;
            font-weight: 600 !important;
            border-color: #2563EB !important;
            box-shadow: 0 4px 10px rgba(37, 99, 235, 0.3);
        }
    </style>
    """, unsafe_allow_html=True)

    selected = st.radio(
        "nav",
        TABS,
        index=TABS.index(st.session_state.active_tab),
        horizontal=True,
        label_visibility="collapsed",
        key="nav_radio",
    )
    st.session_state.active_tab = selected

    st.markdown("<hr style='border-color:#2D333B; margin-top:4px;'>", unsafe_allow_html=True)

    # ── Tab content ───────────────────────────────────────────────────────────
    if selected == TABS[0]:   # Portfolio Overview
        render_kpi_strip(data)
        st.markdown("<br>", unsafe_allow_html=True)
        render_inventory_health_table(data)
        st.markdown("<br>", unsafe_allow_html=True)
        render_risk_chart(data)
        render_gap_chart(data)

    elif selected == TABS[1]:  # Category Intelligence
        render_category_drilldown(data)

    else:                      # Data Management
        render_data_management()


if __name__ == "__main__":
    main()
