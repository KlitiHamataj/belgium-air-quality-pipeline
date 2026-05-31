"""
Streamlit dashboard for Belgium Air Quality data.

Features:
- Interactive Folium map with station markers colored by BelAQI
- Time series charts per station (Plotly)
- Weather correlation scatter plots
"""

import math

import duckdb
import folium
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

st.set_page_config(
    page_title="Belgium Air Quality",
    page_icon="🇧🇪",
    layout="wide",
)

DB_PATH = "./data/warehouse/air_quality.duckdb"

BELAQI_COLORS = {
    1: "#50C878",
    2: "#7CCD7C",
    3: "#FFD700",
    4: "#FFC125",
    5: "#FF8C00",
    6: "#FF6347",
    7: "#DC143C",
    8: "#B22222",
    9: "#8B0000",
    10: "#4B0000",
}


@st.cache_resource
def get_connection():
    return duckdb.connect(DB_PATH, read_only=True)


def clean_df(df):
    """Replace NaN/Infinity with None."""
    for col in df.select_dtypes(include=["float64"]).columns:
        df[col] = df[col].apply(
            lambda x: None if isinstance(x, float) and (math.isnan(x) or math.isinf(x)) else x
        )
    return df


@st.cache_data(ttl=300)
def load_station_summary():
    con = get_connection()
    df = con.execute("select * from main_marts.mart_station_summary").fetchdf()
    return clean_df(df)


@st.cache_data(ttl=300)
def load_daily_data(station_id=None):
    con = get_connection()
    query = "select * from main_marts.mart_daily_aqi"
    if station_id:
        query += f" where station_id = '{station_id}'"
    query += " order by measurement_date desc"
    df = con.execute(query).fetchdf()
    return clean_df(df)


# ─── Header ──────────────────────────────────────────────────────
st.title("🇧🇪 Belgium Air Quality Monitor")
st.markdown("Real-time pipeline: IRCELINE → dbt → DuckDB → this dashboard")

# ─── Load data ───────────────────────────────────────────────────
stations_df = load_station_summary()

if stations_df.empty:
    st.warning("No data in warehouse yet. Run the ingestion pipeline first.")
    st.code("python -m src.ingestion.run_all\ncd dbt && dbt run")
    st.stop()

# ─── Sidebar Filters ─────────────────────────────────────────────
st.sidebar.header("Filters")

belaqi_range = st.sidebar.slider(
    "Mean BelAQI Range", 1.0, 10.0, (1.0, 10.0), 0.5
)

filtered = stations_df[
    (stations_df["mean_belaqi"] >= belaqi_range[0])
    & (stations_df["mean_belaqi"] <= belaqi_range[1])
]

st.sidebar.metric("Stations shown", len(filtered))

# ─── Map ─────────────────────────────────────────────────────────
st.subheader("Station Map")

m = folium.Map(location=[50.5, 4.5], zoom_start=8, tiles="CartoDB positron")

for _, row in filtered.iterrows():
    belaqi = int(row.get("mean_belaqi") or 1)
    color = BELAQI_COLORS.get(min(max(belaqi, 1), 10), "#808080")

    popup_html = f"""
    <b>{row['station_label']}</b><br>
    Mean BelAQI: {row['mean_belaqi']}<br>
    PM2.5: {row.get('mean_pm25', 'N/A')} µg/m³<br>
    PM10: {row.get('mean_pm10', 'N/A')} µg/m³<br>
    NO₂: {row.get('mean_no2', 'N/A')} µg/m³<br>
    Days monitored: {row.get('days_with_data', 'N/A')}
    """

    folium.CircleMarker(
        location=[row["station_lat"], row["station_lon"]],
        radius=8,
        color=color,
        fill=True,
        fill_opacity=0.8,
        popup=folium.Popup(popup_html, max_width=300),
        tooltip=row["station_label"],
    ).add_to(m)

map_data = st_folium(m, width=None, height=500, returned_objects=["last_object_clicked"])

# ─── BelAQI Legend ───────────────────────────────────────────────
legend_html = (
    '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:1rem;">'
    '<span style="background:#50C878;padding:4px 10px;border-radius:4px">'
    "1-2 Very Good</span>"
    '<span style="background:#FFD700;padding:4px 10px;border-radius:4px">'
    "3-4 Good</span>"
    '<span style="background:#FF8C00;padding:4px 10px;border-radius:4px">'
    "5-6 Moderate</span>"
    '<span style="background:#DC143C;color:white;padding:4px 10px;'
    'border-radius:4px">7-8 Poor</span>'
    '<span style="background:#8B0000;color:white;padding:4px 10px;'
    'border-radius:4px">9-10 Very Poor</span>'
    "</div>"
)
st.markdown(legend_html, unsafe_allow_html=True)

# ─── Station Deep Dive ───────────────────────────────────────────
st.subheader("Station Detail")

# Check if user clicked a marker on the map
clicked_station = None
if map_data and map_data.get("last_object_clicked"):
    click_lat = map_data["last_object_clicked"].get("lat")
    click_lng = map_data["last_object_clicked"].get("lng")
    if click_lat and click_lng:
        filtered_copy = filtered.copy()
        filtered_copy["_dist"] = (
            (filtered_copy["station_lat"] - click_lat) ** 2 +
            (filtered_copy["station_lon"] - click_lng) ** 2
        )
        closest = filtered_copy.loc[filtered_copy["_dist"].idxmin()]
        clicked_station = closest["station_label"]

station_options = filtered[["station_id", "station_label"]].drop_duplicates()
station_list = station_options["station_label"].tolist()

default_index = 0
if clicked_station and clicked_station in station_list:
    default_index = station_list.index(clicked_station)

selected_label = st.selectbox(
    "Select a station",
    options=station_list,
    index=default_index,
)

if selected_label:
    selected_id = station_options[
        station_options["station_label"] == selected_label
    ]["station_id"].iloc[0]

    daily_df = load_daily_data(selected_id)

    if not daily_df.empty:
        col1, col2 = st.columns(2)

        with col1:
            fig = px.line(
                daily_df,
                x="measurement_date",
                y="belaqi_overall",
                title=f"BelAQI — {selected_label}",
                labels={"belaqi_overall": "BelAQI", "measurement_date": "Date"},
            )
            fig.add_hline(y=5, line_dash="dash", line_color="orange",
                          annotation_text="Moderate")
            fig.add_hline(y=7, line_dash="dash", line_color="red",
                          annotation_text="Poor")
            fig.update_yaxes(range=[0, 10])
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            pollutant_cols = {
                "PM2.5": "avg_pm25",
                "PM10": "avg_pm10",
                "NO₂": "avg_no2",
                "O₃": "avg_o3",
            }
            fig2 = go.Figure()
            for label, col in pollutant_cols.items():
                if col in daily_df.columns and daily_df[col].notna().any():
                    fig2.add_trace(go.Scatter(
                        x=daily_df["measurement_date"],
                        y=daily_df[col],
                        name=label,
                        mode="lines",
                    ))
            fig2.update_layout(
                title=f"Pollutant Concentrations — {selected_label}",
                yaxis_title="µg/m³",
            )
            st.plotly_chart(fig2, use_container_width=True)

        # Weather correlation
        st.subheader("Weather vs Air Quality")
        col3, col4 = st.columns(2)

        with col3:
            if "avg_wind_speed" in daily_df.columns and daily_df["avg_wind_speed"].notna().any():
                fig3 = px.scatter(
                    daily_df.dropna(subset=["avg_wind_speed", "belaqi_overall"]),
                    x="avg_wind_speed",
                    y="belaqi_overall",
                    title="Wind Speed vs BelAQI",
                    labels={"avg_wind_speed": "Wind Speed (m/s)", "belaqi_overall": "BelAQI"},
                )
                st.plotly_chart(fig3, use_container_width=True)

        with col4:
            has_bl = (
                "avg_boundary_layer" in daily_df.columns
                and daily_df["avg_boundary_layer"].notna().any()
            )
            if has_bl:
                fig4 = px.scatter(
                    daily_df.dropna(subset=["avg_boundary_layer", "avg_pm25"]),
                    x="avg_boundary_layer",
                    y="avg_pm25",
                    title="Boundary Layer Height vs PM2.5",
                    labels={
                        "avg_boundary_layer": "Boundary Layer (m)",
                        "avg_pm25": "PM2.5 (µg/m³)",
                    },
                )
                st.plotly_chart(fig4, use_container_width=True)
# ─── Summary Table ───────────────────────────────────────────────
st.subheader("All Stations")
display_cols = [
    "station_label", "mean_belaqi", "mean_pm25",
    "mean_pm10", "mean_no2", "days_with_data", "pct_days_poor",
]
available_cols = [c for c in display_cols if c in filtered.columns]
st.dataframe(
    filtered[available_cols].sort_values("mean_belaqi", ascending=False),
    use_container_width=True,
    hide_index=True,
)
