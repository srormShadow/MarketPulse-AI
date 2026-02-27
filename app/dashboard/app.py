import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go

API_BASE = "http://127.0.0.1:8000"

st.set_page_config(page_title="MarketPulse AI", layout="wide")

st.title("📊 MarketPulse AI — Retail Forecast & Inventory Intelligence")

st.markdown("Forecast demand and optimize inventory using Bayesian recursive forecasting.")

# Sidebar controls
st.sidebar.header("Forecast Parameters")

category = st.sidebar.selectbox(
    "Category",
    ["Snacks", "Staples", "Edible Oil"]
)

n_days = st.sidebar.slider("Forecast Horizon (days)", 7, 60, 30)
current_inventory = st.sidebar.number_input("Current Inventory", min_value=0, value=200)
lead_time_days = st.sidebar.slider("Lead Time (days)", 1, 30, 7)

if st.sidebar.button("Generate Forecast"):

    with st.spinner("Calling Forecast Engine..."):

        payload = {
            "n_days": n_days,
            "current_inventory": current_inventory,
            "lead_time_days": lead_time_days
        }

        response = requests.post(
            f"{API_BASE}/forecast/{category}",
            json=payload
        )

    if response.status_code != 200:
        st.error("API Error")
        st.stop()

    data = response.json()

    forecast_df = pd.DataFrame(data["forecast"])
    forecast_df["date"] = pd.to_datetime(forecast_df["date"])

    decision = data["decision"]

    # =========================
    # Layout
    # =========================

    col1, col2 = st.columns([3, 1])

    # -------- Forecast Graph --------
    with col1:

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=forecast_df["date"],
            y=forecast_df["predicted_mean"],
            mode="lines",
            name="Predicted Demand"
        ))

        fig.add_trace(go.Scatter(
            x=forecast_df["date"],
            y=forecast_df["upper_95"],
            mode="lines",
            line=dict(width=0),
            showlegend=False
        ))

        fig.add_trace(go.Scatter(
            x=forecast_df["date"],
            y=forecast_df["lower_95"],
            mode="lines",
            fill='tonexty',
            name="95% Confidence Interval"
        ))

        fig.update_layout(
            title=f"{category} Demand Forecast",
            xaxis_title="Date",
            yaxis_title="Units",
            template="plotly_white"
        )

        st.plotly_chart(fig, use_container_width=True)

    # -------- Decision Panel --------
    with col2:

        st.subheader("📦 Inventory Decision")

        st.metric(
            "Recommended Action",
            decision["recommended_action"]
        )

        st.metric(
            "Order Quantity",
            f"{decision['order_quantity']}"
        )

        st.metric(
            "Reorder Point",
            f"{round(decision['reorder_point'], 2)}"
        )

        st.metric(
            "Safety Stock",
            f"{round(decision['safety_stock'], 2)}"
        )

        risk = decision["risk_score"]

        st.progress(risk)

        if risk > 0.7:
            st.error("High Risk of Stockout")
        elif risk > 0.4:
            st.warning("Moderate Risk")
        else:
            st.success("Low Risk")
