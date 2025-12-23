import io
import datetime as dt
import pandas as pd
import requests
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="Spotify Pakistan Charts Dashboard", layout="wide")

# Spotify charts URL pattern (Pakistan country code = pk)
BASE = "https://spotifycharts.com/regional/pk/daily/{date}/download"

@st.cache_data(ttl=3600)
def fetch_day(date_str: str) -> pd.DataFrame:
    """
    Download one day of Spotify Pakistan Top 200 CSV and return a dataframe.
    Expected columns in CSV: Position, Track Name, Artist, Streams, URL
    """
    url = BASE.format(date=date_str)
    r = requests.get(url, timeout=30)
    if r.status_code != 200:
        return pd.DataFrame()  # some dates may be missing
    # Spotify CSV has a few header lines sometimes; pandas handles it well with read_csv
    raw = io.StringIO(r.text)
    df = pd.read_csv(raw)

    # Normalize column names (just in case)
    df.columns = [c.strip() for c in df.columns]

    # Common columns:
    # Position, Track Name, Artist, Streams, URL
    # Sometimes "Track Name" could appear slightly differently; handle safely:
    rename_map = {}
    for c in df.columns:
        if c.lower() == "track name":
            rename_map[c] = "Track"
        if c.lower() == "artist":
            rename_map[c] = "Artist"
        if c.lower() == "streams":
            rename_map[c] = "Streams"
        if c.lower() == "position":
            rename_map[c] = "Position"
        if c.lower() == "url":
            rename_map[c] = "URL"
    df = df.rename(columns=rename_map)

    if "Track" not in df.columns and "Track Name" in df.columns:
        df = df.rename(columns={"Track Name": "Track"})

    # Cast types
    for col in ["Position", "Streams"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["Date"] = pd.to_datetime(date_str)
    return df.dropna(subset=["Position", "Streams"], how="any")

@st.cache_data(ttl=3600)
def fetch_range(start: dt.date, end: dt.date) -> pd.DataFrame:
    all_days = []
    cur = start
    while cur <= end:
        ds = cur.strftime("%Y-%m-%d")
        day_df = fetch_day(ds)
        if not day_df.empty:
            all_days.append(day_df)
        cur += dt.timedelta(days=1)

    if not all_days:
        return pd.DataFrame()

    df = pd.concat(all_days, ignore_index=True)

    # Keep only expected columns if present
    keep = [c for c in ["Date", "Position", "Track", "Artist", "Streams", "URL"] if c in df.columns]
    df = df[keep]
    return df

st.title("🇵🇰 Spotify Pakistan Charts Dashboard (Top 200)")
st.caption("Explore daily Pakistan chart data with filters + temporal visualizations.")

# Sidebar controls
st.sidebar.header("Controls")

today = dt.date.today()
default_end = today - dt.timedelta(days=2)  # charts can lag by a day
default_start = default_end - dt.timedelta(days=14)

date_range = st.sidebar.date_input(
    "Date range",
    value=(default_start, default_end),
    min_value=today - dt.timedelta(days=365),
    max_value=default_end
)

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = default_start, default_end

rank_max = st.sidebar.slider("Include ranks up to (Top N)", 10, 200, 50)

df = fetch_range(start_date, end_date)

if df.empty:
    st.error("No data fetched for that range. Try another date range (some days may be missing).")
    st.stop()

df = df[df["Position"] <= rank_max].copy()

# Additional filters
artist_options = ["(All)"] + sorted(df["Artist"].dropna().unique().tolist())
artist_choice = st.sidebar.selectbox("Artist filter", artist_options)

if artist_choice != "(All)":
    df = df[df["Artist"] == artist_choice]

keyword = st.sidebar.text_input("Track keyword (optional)", value="")
if keyword.strip():
    df = df[df["Track"].fillna("").str.contains(keyword.strip(), case=False, na=False)]

# KPIs
k1, k2, k3, k4 = st.columns(4)
k1.metric("Rows (song-days)", f"{len(df):,}")
k2.metric("Unique tracks", f"{df['Track'].nunique():,}")
k3.metric("Unique artists", f"{df['Artist'].nunique():,}")
k4.metric("Avg streams (in selection)", f"{df['Streams'].mean():,.0f}")

st.divider()

left, right = st.columns([1.2, 0.8])

with left:
    st.subheader("📈 Temporal Trends")

    daily = df.groupby("Date", as_index=False).agg(
        total_streams=("Streams", "sum"),
        avg_streams=("Streams", "mean"),
        tracks_count=("Track", "nunique")
    ).sort_values("Date")

    fig_total = px.line(daily, x="Date", y="total_streams", markers=True, title="Total Streams per Day (selected ranks)")
    st.plotly_chart(fig_total, use_container_width=True)

    fig_tracks = px.line(daily, x="Date", y="tracks_count", markers=True, title="Unique Tracks per Day (in selection)")
    st.plotly_chart(fig_tracks, use_container_width=True)

with right:
    st.subheader("🏆 Top Entities (within selection)")

    top_tracks = df.groupby("Track", as_index=False).agg(total_streams=("Streams", "sum")).sort_values("total_streams", ascending=False).head(10)
    fig_tt = px.bar(top_tracks, x="total_streams", y="Track", orientation="h", title="Top 10 Tracks by Total Streams")
    st.plotly_chart(fig_tt, use_container_width=True)

    top_artists = df.groupby("Artist", as_index=False).agg(total_streams=("Streams", "sum")).sort_values("total_streams", ascending=False).head(10)
    fig_ta = px.bar(top_artists, x="total_streams", y="Artist", orientation="h", title="Top 10 Artists by Total Streams")
    st.plotly_chart(fig_ta, use_container_width=True)

st.divider()

st.subheader("🎛️ Interactive Track Drilldown (Rank over time)")

track_options = sorted(df["Track"].dropna().unique().tolist())
chosen_track = st.selectbox("Pick a track", track_options)

track_df = df[df["Track"] == chosen_track].copy()
track_df = track_df.sort_values("Date")

if not track_df.empty:
    fig_rank = px.line(track_df, x="Date", y="Position", markers=True, title=f"Rank over Time — {chosen_track}")
    fig_rank.update_yaxes(autorange="reversed")  # rank 1 at top
    st.plotly_chart(fig_rank, use_container_width=True)

    fig_streams = px.line(track_df, x="Date", y="Streams", markers=True, title=f"Streams over Time — {chosen_track}")
    st.plotly_chart(fig_streams, use_container_width=True)

st.divider()
st.subheader("📋 Data Table (Filtered)")
st.dataframe(df.sort_values(["Date", "Position"]), use_container_width=True, hide_index=True)
