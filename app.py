import streamlit as st
import pandas as pd
import subprocess
import sys
import altair as alt
import datetime
from lankarfr.store.duckdb_store import CurveStore
from lankarfr.curve.curve import YieldCurve

st.set_page_config(page_title="LankaRFR Dashboard", layout="wide")

st.title("📈 LankaRFR - Zero Coupon Yield Curve")
st.markdown("Sri Lanka Risk-Free Rate Curve Builder for IFRS 17 / IRCSL")

# --- Initialize Store ---
def get_store():
    return CurveStore()

store = get_store()

# --- Sidebar Controls ---
st.sidebar.header("Controls")

# Ingest Button
if st.sidebar.button("Run Data Pipeline (Ingest)"):
    with st.spinner("Scraping CBSL and PDMO... Bootstrapping... Please wait."):
        # Run the CLI tool transparently using the current python executable
        result = subprocess.run([sys.executable, "-m", "lankarfr.cli", "ingest"], capture_output=True, text=True)
        if result.returncode == 0:
            st.sidebar.success("Ingestion successful!")
        else:
            st.sidebar.error("Ingestion failed. Check logs.")
            st.sidebar.text(result.stderr)
            
# Date selection
dates = store.get_all_dates()
if not dates:
    st.warning("No curve data found! Please run the Ingestion pipeline from the sidebar.")
    st.stop()

selected_date = st.sidebar.selectbox("Select Curve Date", sorted(dates, reverse=True))

available_methods = store.get_methods_for_date(selected_date)
default_selection = available_methods

selected_methods = st.sidebar.multiselect("Active Curve Layers", available_methods, default=default_selection)

if not selected_methods:
    st.warning("Please select at least one method to visualize.")
    st.stop()

# Build dictionaries for easy access
method_points = {}
for m in selected_methods:
    pts = store.get_curve(selected_date, method=m)
    if pts: method_points[m] = pts

if not method_points:
    st.error("No points found for the selected methods.")
    st.stop()
    
# Colors for distinct lines
COLORS = {
    'linear_exact': '#D81B60',
    'nelson_siegel': '#43A047',
    'nss': '#8E24AA',
    'cubic_spline': '#FDD835',
    'monotone_convex': '#1E88E5',
    'smith_wilson': '#00ACC1'
}

col1, col2 = st.columns([3, 1])

with col1:
    st.subheader(f"Zero Rate Target Horizon Comparison ({selected_date})")
    
    chart_layers = []
    global_max_t = 0
    
    # Calculate global max tenor bounds to align lines
    for m, pts in method_points.items():
        if pts:
            m_max = int(pts[-1][0]) + 1
            if m_max > global_max_t: global_max_t = m_max
            
    if global_max_t == 0: global_max_t = 20

    for m, pts in method_points.items():
        curve_obj = YieldCurve(pts)
        
        # Raw nodes for exact-fit dots
        if m == 'linear_exact':
            node_t = [p[0] for p in pts]
            node_r = [p[1]*100 for p in pts]
            df_points = pd.DataFrame({'Tenor (Years)': node_t, 'Zero Rate (%)': node_r, 'Model': 'linear_exact'})
            
            dots = alt.Chart(df_points).mark_circle(size=70).encode(
                x=alt.X('Tenor (Years):Q', scale=alt.Scale(domain=[0, global_max_t])),
                y=alt.Y('Zero Rate (%):Q', scale=alt.Scale(zero=False)),
                color=alt.Color('Model:N', scale=alt.Scale(domain=list(COLORS.keys()), range=list(COLORS.values()))),
                tooltip=['Tenor (Years)', 'Zero Rate (%)']
            )
            chart_layers.append(dots)
        
        # Generate dense continuous evaluation nodes to draw smooth lines
        eval_t = [t/10.0 for t in range(0, global_max_t * 10)]
        eval_r = [curve_obj.get_zero_rate(t) * 100 for t in eval_t]
        
        df_line = pd.DataFrame({'Tenor (Years)': eval_t, 'Zero Rate (%)': eval_r, 'Model': m})
        
        # Format Smith-Wilson specifically to highlight extrapolation tail
        stroke_dash = [5, 5] if m != 'linear_exact' else []
        c_color = COLORS.get(m, '#ffffff')
        
        # Use a nominal color encoding mapped strictly to the dictionary so the legend renders properly
        line = alt.Chart(df_line).mark_line(size=3, strokeDash=stroke_dash).encode(
            x=alt.X('Tenor (Years):Q'),
            y=alt.Y('Zero Rate (%):Q'),
            color=alt.Color('Model:N', scale=alt.Scale(domain=list(COLORS.keys()), range=list(COLORS.values())), legend=alt.Legend(title="Curves")),
            tooltip=['Tenor (Years)', 'Zero Rate (%)', 'Model']
        )
        chart_layers.append(line)

    if chart_layers:
        final_chart = alt.layer(*chart_layers).resolve_scale(color='independent').interactive()
        st.altair_chart(final_chart, use_container_width=True)

with col2:
    st.subheader("Point Evaluation")
    st.info("Evaluate model-specific rates.")
    
    query_tenor = st.number_input("Tenor (Years)", min_value=0.0, max_value=float(global_max_t), value=1.0, step=0.1)
    
    for m, pts in method_points.items():
        curve_obj = YieldCurve(pts)
        z_rate = curve_obj.get_zero_rate(query_tenor)
        dfactor = curve_obj.get_discount_factor(query_tenor)
        
        # Render stylized metrics
        st.markdown(f"**{m.replace('_', ' ').title()}**")
        scol1, scol2 = st.columns(2)
        scol1.metric(label="Zero Rate", value=f"{z_rate*100:.3f}%")
        scol2.metric(label="Disc Factor", value=f"{dfactor:.5f}")
        st.markdown("---")

st.divider()
st.subheader("Raw Grid Point Extractions")
cols = st.columns(len(method_points))

for idx, (m, pts) in enumerate(method_points.items()):
    with cols[idx]:
        st.markdown(f"**{m}**")
        df_nodes = pd.DataFrame({'Tenor': [p[0] for p in pts], 'Rate (%)': [p[1]*100 for p in pts]})
        st.dataframe(df_nodes.style.format({"Tenor": "{:.3f}", "Rate (%)": "{:.3f}%"}), use_container_width=True)
