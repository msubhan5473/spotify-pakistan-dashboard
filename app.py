import glob
import os
import re
import datetime as dt

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.io as pio

# ----------------------------
# Page config + theme defaults
# ----------------------------
st.set_page_config(
    page_title="Spotify Pakistan Charts Dashboard",
    layout="wide",
    page_icon="🇵🇰",
)

pio.templates.default = "plotly_dark"

DATA_DIR = "data"


# ----------------------------
# Helpers
# ----------------------------
def extract_date_from_filename(path: str):
    name = os.path.basename(path)
    m = re.search(r"(\d{4}-\d{2}-\d{2})", name)
    if not m:
        return None
    return pd.to_datetime(m.group(1), errors="coerce")


def normalize_col(c: str) -> str:
    c = str(c).strip().lower()
    c = re.sub(r"[_\s]+", " ", c)
    return c


def uri_to_url(uri: str) -> str:
    if not isinstance(uri, str):
        return ""
    uri = uri.strip()
    m = re.match(r"spotify:track:([A-Za-z0-9]+)", uri)
    if m:
        return f"https://open.spotify.com/track/{m.group(1)}"
    return ""


@st.cache_data(ttl=3600)
def load_local_data() -> pd.DataFrame:
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.csv")))
    if not files:
        return pd.DataFrame()

    all_days = []

    for f in files:
        d = extract_date_from_filename(f)
        if d is None or pd.isna(d):
            continue

        try:
            df = pd.read_csv(f)
        except Exception:
            continue

        df.columns = [str(c).strip() for c in df.columns]

        rename_map = {}
        for c in df.columns:
            cl = normalize_col(c)

            if cl in ["position", "rank", "chart position"]:
                rename_map[c] = "Position"
            elif cl in ["track name", "track", "trackname", "song", "title"]:
                rename_map[c] = "Track"
            elif cl in ["artist", "artist name", "artist names", "artistname", "artistnames"]:
                rename_map[c] = "Artist"
            elif cl in ["streams", "stream"]:
                rename_map[c] = "Streams"
            elif cl in ["url", "track url", "spotify url"]:
                rename_map[c] = "URL"
            elif cl in ["uri"]:
                rename_map[c] = "URI"

        df = df.rename(columns=rename_map)

        # Create URL from URI if URL missing
        if "URL" not in df.columns:
            if "URI" in df.columns:
                df["URL"] = df["URI"].map(uri_to_url)
            else:
                df["URL"] = ""

        # Must have these
        if "Position" not in df.columns or "Streams" not in df.columns:
            continue

        if "Track" not in df.columns:
            df["Track"] = "Unknown"
        if "Artist" not in df.columns:
            df["Artist"] = "Unknown"

        df["Position"] = pd.to_numeric(df["Position"], errors="coerce")
        df["Streams"] = pd.to_numeric(df["Streams"], errors="coerce")
        df["Date"] = d

        df = df.dropna(subset=["Position", "Streams"])
        all_days.append(df)

    if not all_days:
        return pd.DataFrame()

    out = pd.concat(all_days, ignore_index=True)

    keep = [c for c in ["Date", "Position", "Track", "Artist", "Streams", "URL"] if c in out.columns]
    out = out[keep].copy()
    out["Track"] = out["Track"].astype(str)
    out["Artist"] = out["Artist"].astype(str)
    return out


# ----------------------------
# UI polish (CSS)
# ----------------------------
st.markdown(
    """
<style>
.block-container { padding-top: 2.0rem; padding-bottom: 2.2rem; max-width: 1400px; }

.section {
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 18px;
  padding: 18px 18px;
  margin-top: 14px;
}

.kpi div[data-testid="stMetric"]{
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
  padding: 14px 16px;
  border-radius: 16px;
}

.badge {
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.10);
  font-size: 12px;
  display: inline-block;
  margin-left: 6px;
}

section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01));
  border-right: 1px solid rgba(255,255,255,0.08);
}

hr { opacity: 0.25; }
</style>
""",
    unsafe_allow_html=True,
)

# ----------------------------
# Load data
# ----------------------------
df = load_local_data()

# Hero header
st.markdown(
    """
<div style="display:flex; align-items:flex-end; gap:14px; flex-wrap:wrap;">
  <div>
    <div style="font-size:44px; font-weight:800; line-height:1.05;">🇵🇰 PK Spotify Charts Dashboard</div>
    <div style="opacity:0.8; font-size:16px; margin-top:6px;">
      Local CSV mode • Daily charts • Explore tracks, artists & trends
    </div>
  </div>
  <div style="margin-left:auto;">
    <span class="badge">Pakistan</span>
    <span class="badge">Top 200</span>
    <span class="badge">Interactive</span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

if df.empty:
    st.error("No local CSVs found.")
    st.write("Fix:")
    st.write("1) Create a folder named `data` in your project (same level as app.py).")
    st.write("2) Put downloaded CSVs inside `data/`.")
    st.write("3) Filenames must contain a date like YYYY-MM-DD (example: regional-pk-daily-2025-12-22.csv).")
    st.stop()

min_date = df["Date"].min().date()
max_date = df["Date"].max().date()

# ----------------------------
# Sidebar controls
# ----------------------------
st.sidebar.header("Controls")

st.sidebar.subheader("Quick ranges")
preset = st.sidebar.radio(" ", ["Custom", "Last 7 days", "Last 14 days", "Last 30 days"], index=0)

if preset != "Custom":
    end_date = max_date
    days = {"Last 7 days": 7, "Last 14 days": 14, "Last 30 days": 30}[preset]
    start_date = max(min_date, (max_date - dt.timedelta(days=days - 1)))
else:
    date_range = st.sidebar.date_input(
        "Date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = min_date, max_date

rank_max = st.sidebar.slider("Include ranks up to (Top N)", 10, 200, 50)

st.sidebar.subheader("Filters")
artist_options = ["(All)"] + sorted(df["Artist"].dropna().unique().tolist())
artist_choice = st.sidebar.selectbox("Artist", artist_options)
keyword = st.sidebar.text_input("Track keyword", value="")

# ----------------------------
# Apply filters
# ----------------------------
df_f = df[(df["Date"].dt.date >= start_date) & (df["Date"].dt.date <= end_date)].copy()
df_f = df_f[df_f["Position"] <= rank_max].copy()

if artist_choice != "(All)":
    df_f = df_f[df_f["Artist"] == artist_choice]

if keyword.strip():
    df_f = df_f[df_f["Track"].fillna("").str.contains(keyword.strip(), case=False, na=False)]

if df_f.empty:
    st.warning("No rows match your filters. Try widening date range or Top N.")
    st.stop()

# ----------------------------
# KPI row
# ----------------------------
k1, k2, k3, k4, k5 = st.columns([1, 1, 1, 1, 1.2])
with st.container():
    st.markdown('<div class="kpi">', unsafe_allow_html=True)
    k1.metric("Rows (song-days)", f"{len(df_f):,}")
    k2.metric("Unique tracks", f"{df_f['Track'].nunique():,}")
    k3.metric("Unique artists", f"{df_f['Artist'].nunique():,}")
    k4.metric("Avg streams", f"{df_f['Streams'].mean():,.0f}")
    k5.metric("Date span", f"{start_date} → {end_date}")
    st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------
# Section: Trends + Top entities
# ----------------------------
st.markdown('<div class="section">', unsafe_allow_html=True)
left, right = st.columns([1.25, 0.75], gap="large")

with left:
    st.subheader("📈 Temporal Trends")


    daily = (
        df_f.groupby("Date", as_index=False)
        .agg(
            total_streams=("Streams", "sum"),
            avg_streams=("Streams", "mean"),
            tracks_count=("Track", "nunique"),
        )
        .sort_values("Date")
    )

    fig_total = px.line(
        daily,
        x="Date",
        y="total_streams",
        markers=True,
        title="Total Streams per Day",
        hover_data={"Date": True, "total_streams": ":,"},
    )
    fig_total.update_layout(margin=dict(l=10, r=10, t=60, b=10), title_font_size=18)
    st.plotly_chart(fig_total, use_container_width=True)

    fig_tracks = px.line(
        daily,
        x="Date",
        y="tracks_count",
        markers=True,
        title="Unique Tracks per Day",
        hover_data={"Date": True, "tracks_count": True},
    )
    fig_tracks.update_layout(margin=dict(l=10, r=10, t=60, b=10), title_font_size=18)
    st.plotly_chart(fig_tracks, use_container_width=True)

with right:
    st.subheader("🏆 Top Entities")

    top_tracks = (
        df_f.groupby("Track", as_index=False)
        .agg(total_streams=("Streams", "sum"))
        .sort_values("total_streams", ascending=False)
        .head(10)
    )
    fig_tt = px.bar(top_tracks, x="total_streams", y="Track", orientation="h", title="Top 10 Tracks")
    fig_tt.update_layout(margin=dict(l=10, r=10, t=60, b=10), title_font_size=18)
    st.plotly_chart(fig_tt, use_container_width=True)

    top_artists = (
        df_f.groupby("Artist", as_index=False)
        .agg(total_streams=("Streams", "sum"))
        .sort_values("total_streams", ascending=False)
        .head(10)
    )
    fig_ta = px.bar(top_artists, x="total_streams", y="Artist", orientation="h", title="Top 10 Artists")
    fig_ta.update_layout(margin=dict(l=10, r=10, t=60, b=10), title_font_size=18)
    st.plotly_chart(fig_ta, use_container_width=True)

st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------
# Section: Movers + Highlights
# ----------------------------
st.markdown('<div class="section">', unsafe_allow_html=True)
st.subheader("🚀 Movers & Highlights")

c1, c2 = st.columns([1, 1], gap="large")

with c1:
    tmp = df_f.sort_values("Date").copy()
    tmp["prev_rank"] = tmp.groupby("Track")["Position"].shift(1)
    tmp["rank_change"] = tmp["prev_rank"] - tmp["Position"]  # + means improved

    movers = (
        tmp.dropna(subset=["rank_change"])
        .groupby(["Track", "Artist"], as_index=False)
        .agg(best_improvement=("rank_change", "max"), worst_drop=("rank_change", "min"))
        .sort_values("best_improvement", ascending=False)
        .head(10)
    )
    movers["best_improvement"] = movers["best_improvement"].round(0).astype(int)
    movers["worst_drop"] = movers["worst_drop"].round(0).astype(int)

    st.caption("Biggest rank improvements (higher = better).")
    st.dataframe(movers, use_container_width=True, hide_index=True)

with c2:
    # Most streamed tracks overall in current selection
    highlights = (
        df_f.groupby(["Track", "Artist"], as_index=False)
        .agg(total_streams=("Streams", "sum"), best_rank=("Position", "min"))
        .sort_values(["total_streams", "best_rank"], ascending=[False, True])
        .head(10)
    )
    highlights["total_streams"] = highlights["total_streams"].round(0).astype(int)

    st.caption("Most total streams in the selected window.")
    st.dataframe(highlights, use_container_width=True, hide_index=True)

st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------
# Section: Track drilldown
# ----------------------------
st.markdown('<div class="section">', unsafe_allow_html=True)
st.subheader("🎛️ Track Drilldown")

track_options = sorted(df_f["Track"].dropna().unique().tolist())
chosen_track = st.selectbox("Pick a track", track_options)

track_df = df_f[df_f["Track"] == chosen_track].sort_values("Date").copy()

colA, colB = st.columns([1, 1], gap="large")

with colA:
    fig_rank = px.line(track_df, x="Date", y="Position", markers=True, title="Rank over Time")
    fig_rank.update_yaxes(autorange="reversed")
    fig_rank.update_layout(margin=dict(l=10, r=10, t=60, b=10), title_font_size=18)
    st.plotly_chart(fig_rank, use_container_width=True)

with colB:
    fig_streams = px.line(track_df, x="Date", y="Streams", markers=True, title="Streams over Time")
    fig_streams.update_layout(margin=dict(l=10, r=10, t=60, b=10), title_font_size=18)
    st.plotly_chart(fig_streams, use_container_width=True)

st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------
# Section: Data table + search + export
# ----------------------------
st.markdown('<div class="section">', unsafe_allow_html=True)
st.subheader("📋 Data Table")

q = st.text_input("Search in table (track or artist)", "")
table_df = df_f.copy()
if q.strip():
    table_df = table_df[
        table_df["Track"].str.contains(q, case=False, na=False)
        | table_df["Artist"].str.contains(q, case=False, na=False)
    ]

table_df = table_df.sort_values(["Date", "Position"])

st.dataframe(table_df, use_container_width=True, hide_index=True)

csv_bytes = table_df.to_csv(index=False).encode("utf-8")
st.download_button(
    "⬇️ Download filtered CSV",
    data=csv_bytes,
    file_name="spotify_pk_filtered.csv",
    mime="text/csv",
)

st.markdown("</div>", unsafe_allow_html=True)