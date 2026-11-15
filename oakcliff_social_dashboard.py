"""
Oakcliff Sailing | Monthly Social Analytics
Export-based dashboard: no Meta API tokens or live account connections required.

Run locally:
    python3 -m pip install -r requirements.txt
    python3 -m streamlit run oakcliff_social_dashboard.py

Upload monthly CSV exports from Meta Business Suite and Neon CRM.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Oakcliff Sailing | Social Analytics",
    page_icon="⛵",
    layout="wide",
)

st.title("⛵ Oakcliff Sailing | Social Analytics")
st.caption("Monthly reporting • Facebook • Instagram • Neon CRM")

st.info(
    "This version uses CSV exports only. No Meta access tokens or live account connections "
    "are required. Monthly aggregate reports are stored in the app's private GitHub repository."
)

# ---------- Helpers ----------
def clean_col(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).strip().lower()).strip()

def find_col(df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
    normalized = {clean_col(c): c for c in df.columns}
    for candidate in candidates:
        key = clean_col(candidate)
        if key in normalized:
            return normalized[key]
    # allow partial matches for common export header variations
    for candidate in candidates:
        key = clean_col(candidate)
        for norm, original in normalized.items():
            if key and (key in norm or norm in key):
                return original
    return None

def numeric_series(df: pd.DataFrame, col: Optional[str]) -> pd.Series:
    if not col:
        return pd.Series([pd.NA] * len(df), index=df.index, dtype="Float64")
    return pd.to_numeric(
        df[col].astype(str).str.replace(",", "", regex=False).str.replace("%", "", regex=False),
        errors="coerce",
    )

def read_csv(upload) -> pd.DataFrame:
    if hasattr(upload, "_path"):
        try:
            return pd.read_csv(upload._path)
        except UnicodeDecodeError:
            return pd.read_csv(upload._path, encoding="latin-1")
    upload.seek(0)
    try:
        return pd.read_csv(upload)
    except UnicodeDecodeError:
        upload.seek(0)
        return pd.read_csv(upload, encoding="latin-1")

def format_num(value) -> str:
    if pd.isna(value):
        return "—"
    return f"{value:,.0f}"

def format_pct(value) -> str:
    if pd.isna(value):
        return "—"
    return f"{value:.1f}%"

def detect_platform(filename: str, df: pd.DataFrame) -> str:
    name = filename.lower()
    cols = " ".join(clean_col(c) for c in df.columns)
    if "instagram" in name or "instagram" in cols:
        return "Instagram"
    if "facebook" in name or "facebook" in cols:
        return "Facebook"
    return "Meta / Unclassified"

def normalize_meta(upload) -> tuple[pd.DataFrame, str]:
    raw = read_csv(upload)
    platform = detect_platform(upload.name, raw)
    date_col = find_col(raw, [
        "Date", "Day", "Published", "Published date", "Post date", "Start date",
        "Reporting starts", "Date created", "Creation date"
    ])
    metric_map = {
        "Reach": ["Reach", "Accounts reached", "People reached", "Page reach"],
        "Views": ["Views", "Video views", "Content views", "Impressions"],
        "Interactions": ["Interactions", "Content interactions", "Engagement", "Engagements", "Post engagements"],
        "Link clicks": ["Link clicks", "Website clicks", "Outbound clicks", "Clicks"],
        "Shares": ["Shares", "Post shares"],
        "Likes": ["Likes", "Reactions"],
        "Comments": ["Comments"],
        "Saves": ["Saves", "Saved"],
        "Followers": ["Followers", "Follows", "Total followers", "Lifetime followers"],
        "Posts": ["Posts", "Published posts", "Post count"],
        "Stories": ["Stories", "Published stories", "Story count"],
    }
    out = pd.DataFrame(index=raw.index)
    if date_col:
        out["Date"] = pd.to_datetime(raw[date_col], errors="coerce")
    else:
        out["Date"] = pd.NaT
    out["Platform"] = platform
    out["Source file"] = upload.name
    out["Content"] = (
        raw[find_col(raw, ["Post title", "Title", "Caption", "Description", "Content"])].astype(str)
        if find_col(raw, ["Post title", "Title", "Caption", "Description", "Content"])
        else ""
    )
    for metric, candidates in metric_map.items():
        col = find_col(raw, candidates)
        out[metric] = numeric_series(raw, col) if col else pd.NA

    # If a Meta export is a metric/value table, pivot it into the standard layout.
    metric_name_col = find_col(raw, ["Metric", "Metric name", "Measure"])
    metric_value_col = find_col(raw, ["Value", "Results", "Total"])
    if metric_name_col and metric_value_col and out[list(metric_map)].isna().all().all():
        long = raw[[metric_name_col, metric_value_col]].copy()
        long["Metric"] = long[metric_name_col].astype(str).str.lower()
        long["Value"] = pd.to_numeric(long[metric_value_col], errors="coerce")
        for metric, candidates in metric_map.items():
            keys = [clean_col(x) for x in candidates]
            match = long["Metric"].map(clean_col).isin(keys)
            if match.any():
                out[metric] = long.loc[match, "Value"].sum()

    # Discard fully blank records, but retain source file and platform.
    metric_cols = list(metric_map)
    if out[metric_cols].notna().any().any():
        out = out[out[metric_cols].notna().any(axis=1)].copy()
    return out, platform

def normalize_neon(upload) -> pd.DataFrame:
    raw = read_csv(upload)
    sent_col = find_col(raw, ["Sent", "Emails sent", "Delivered"])
    opens_col = find_col(raw, ["Opens", "Unique opens", "Total opens"])
    clicks_col = find_col(raw, ["Clicks", "Unique clicks", "Total clicks"])
    unsub_col = find_col(raw, ["Unsubscribed", "Unsubscribes", "Unsubscribe"])
    bounced_col = find_col(raw, ["Bounced", "Bounces"])
    attempted_col = find_col(raw, ["Attempted", "Emails attempted"])
    date_col = find_col(raw, ["Delivery Started", "Delivery Completed", "Date", "Send date", "Sent date"])
    name_col = find_col(raw, ["Email Name", "Campaign", "Campaign name", "Email"])
    out = pd.DataFrame()
    out["Date"] = pd.to_datetime(raw[date_col], errors="coerce") if date_col else pd.NaT
    out["Email"] = raw[name_col].astype(str) if name_col else "Email campaign"
    out["Sent"] = numeric_series(raw, sent_col)
    out["Opens"] = numeric_series(raw, opens_col)
    out["Clicks"] = numeric_series(raw, clicks_col)
    out["Unsubscribes"] = numeric_series(raw, unsub_col)
    out["Bounced"] = numeric_series(raw, bounced_col)
    out["Attempted"] = numeric_series(raw, attempted_col)
    out["Open rate"] = (out["Opens"] / out["Sent"] * 100).where(out["Sent"] > 0)
    out["Click rate"] = (out["Clicks"] / out["Sent"] * 100).where(out["Sent"] > 0)
    out["Source file"] = upload.name
    return out

# ---------- Load monthly exports stored with the app ----------
# Keep the GitHub repository private. Place public-facing aggregate exports here:
# data/meta/facebook_YYYY-MM.csv
# data/meta/instagram_YYYY-MM.csv
# data/neon/neon_email_YYYY-MM.csv
from glob import glob

META_PATHS = sorted(glob("data/meta/*.csv"))
NEON_PATHS = sorted(glob("data/neon/*.csv"))

meta_frames = []
meta_warnings = []
for path in META_PATHS:
    try:
        class LocalUpload:
            def __init__(self, file_path):
                self.name = Path(file_path).name
                self._path = file_path
            def seek(self, position):
                pass
            def read(self):
                return Path(self._path).read_bytes()
        frame, platform = normalize_meta(LocalUpload(path))
        if frame.empty:
            meta_warnings.append(f"{Path(path).name}: no recognizable social metrics were found.")
        else:
            meta_frames.append(frame)
    except Exception as exc:
        meta_warnings.append(f"{Path(path).name}: {exc}")

if meta_frames:
    meta_df = pd.concat(meta_frames, ignore_index=True)
else:
    meta_df = pd.DataFrame(columns=[
        "Date", "Platform", "Source file", "Content", "Reach", "Views",
        "Interactions", "Link clicks", "Shares", "Likes", "Comments", "Saves",
        "Followers", "Posts", "Stories"
    ])

neon_frames = []
for path in NEON_PATHS:
    try:
        class LocalUpload:
            def __init__(self, file_path):
                self.name = Path(file_path).name
                self._path = file_path
            def seek(self, position):
                pass
            def read(self):
                return Path(self._path).read_bytes()
        neon_frames.append(normalize_neon(LocalUpload(path)))
    except Exception as exc:
        meta_warnings.append(f"{Path(path).name}: {exc}")

neon_df = pd.concat(neon_frames, ignore_index=True) if neon_frames else pd.DataFrame()

for warning in meta_warnings:
    st.warning(warning)

if not META_PATHS and not NEON_PATHS:
    st.warning(
        "No monthly exports have been added yet. Add CSV files to the data/meta and "
        "data/neon folders in the GitHub repository, then the dashboard will load them."
    )
    st.stop()

# ---------- Date filters ----------
date_candidates = []
if not meta_df.empty and meta_df["Date"].notna().any():
    date_candidates.extend(meta_df["Date"].dropna().tolist())
if not neon_df.empty and neon_df["Date"].notna().any():
    date_candidates.extend(neon_df["Date"].dropna().tolist())

if date_candidates:
    min_date = min(pd.Timestamp(x).date() for x in date_candidates)
    max_date = max(pd.Timestamp(x).date() for x in date_candidates)
    date_range = st.date_input("Reporting period", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = min_date, max_date
else:
    start_date, end_date = None, None
    st.caption("Upload reports to populate the dashboard. Date filters will appear when dates are detected.")

if start_date and end_date:
    if not meta_df.empty:
        meta_view = meta_df[
            meta_df["Date"].isna() |
            meta_df["Date"].dt.date.between(start_date, end_date)
        ].copy()
    else:
        meta_view = meta_df
    if not neon_df.empty:
        neon_view = neon_df[
            neon_df["Date"].isna() |
            neon_df["Date"].dt.date.between(start_date, end_date)
        ].copy()
    else:
        neon_view = neon_df
else:
    meta_view, neon_view = meta_df.copy(), neon_df.copy()

# ---------- Summary ----------
st.subheader("Monthly overview")
if meta_view.empty and neon_view.empty:
    st.markdown(
        "Start by uploading your monthly CSV exports in the left sidebar. "
        "The dashboard will combine the files and calculate the reporting metrics."
    )
    st.stop()

def total_metric(df: pd.DataFrame, metric: str):
    if df.empty or metric not in df:
        return pd.NA
    values = pd.to_numeric(df[metric], errors="coerce").dropna()
    return values.sum() if len(values) else pd.NA

if not meta_view.empty:
    for platform in ["Facebook", "Instagram"]:
        subset = meta_view[meta_view["Platform"] == platform]
        if subset.empty:
            continue
        st.markdown(f"#### {platform}")
        cols = st.columns(5)
        for col, metric in zip(cols, ["Reach", "Views", "Interactions", "Link clicks", "Shares"]):
            val = total_metric(subset, metric)
            col.metric(metric, format_num(val))
        # Follower counts and post/story totals are commonly snapshots or content-level fields;
        # show latest available value rather than summing repeated snapshots.
        snapshot_cols = st.columns(3)
        for col, metric in zip(snapshot_cols, ["Followers", "Posts", "Stories"]):
            vals = pd.to_numeric(subset[metric], errors="coerce").dropna() if metric in subset else pd.Series(dtype=float)
            col.metric(f"Latest {metric.lower()}", format_num(vals.iloc[-1]) if len(vals) else "—")

if not neon_view.empty:
    st.markdown("#### Neon CRM email")
    sent = total_metric(neon_view, "Sent")
    opens = total_metric(neon_view, "Opens")
    clicks = total_metric(neon_view, "Clicks")
    unsub = total_metric(neon_view, "Unsubscribes")
    bounced = total_metric(neon_view, "Bounced")
    open_rate = (opens / sent * 100) if pd.notna(sent) and sent > 0 and pd.notna(opens) else pd.NA
    click_rate = (clicks / sent * 100) if pd.notna(sent) and sent > 0 and pd.notna(clicks) else pd.NA
    cols = st.columns(6)
    for col, label, value, is_pct in [
        (cols[0], "Emails sent", sent, False),
        (cols[1], "Opens", opens, False),
        (cols[2], "Open rate", open_rate, True),
        (cols[3], "Clicks", clicks, False),
        (cols[4], "Click rate", click_rate, True),
        (cols[5], "Unsubscribes", unsub, False),
    ]:
        col.metric(label, format_pct(value) if is_pct else format_num(value))
    if pd.notna(bounced):
        st.caption(f"Bounced emails: {format_num(bounced)}")

# ---------- Trends ----------
st.subheader("Trends")
if not meta_view.empty and meta_view["Date"].notna().any():
    trend_metric = st.selectbox(
        "Social metric",
        ["Reach", "Views", "Interactions", "Link clicks", "Shares", "Followers"],
        key="social_trend_metric",
    )
    trend = meta_view.dropna(subset=["Date"]).copy()
    trend[trend_metric] = pd.to_numeric(trend[trend_metric], errors="coerce")
    trend = trend.dropna(subset=[trend_metric])
    if not trend.empty:
        if trend_metric == "Followers":
            trend = trend.sort_values("Date").drop_duplicates(["Platform", "Date"], keep="last")
        else:
            trend = trend.groupby(["Platform", pd.Grouper(key="Date", freq="MS")], as_index=False)[trend_metric].sum()
        if trend_metric == "Followers":
            chart = px.line(trend, x="Date", y=trend_metric, color="Platform", markers=True,
                            title=f"{trend_metric} over time")
        else:
            chart = px.bar(trend, x="Date", y=trend_metric, color="Platform", barmode="group",
                           title=f"Monthly {trend_metric}")
        st.plotly_chart(chart, use_container_width=True)
    else:
        st.caption(f"No {trend_metric.lower()} values were found in the uploaded Meta exports.")

if not neon_view.empty and neon_view["Date"].notna().any():
    email_trend = neon_view.dropna(subset=["Date"]).copy()
    email_trend["Month"] = email_trend["Date"].dt.to_period("M").astype(str)
    email_monthly = email_trend.groupby("Month", as_index=False)[["Sent", "Opens", "Clicks", "Unsubscribes"]].sum()
    if not email_monthly.empty:
        st.plotly_chart(
            px.bar(email_monthly, x="Month", y=["Sent", "Opens", "Clicks"],
                   barmode="group", title="Neon CRM email activity by month"),
            use_container_width=True,
        )

# ---------- Detail tables ----------
with st.expander("View uploaded Meta data"):
    if meta_view.empty:
        st.write("No Meta CSV data loaded.")
    else:
        st.dataframe(meta_view, use_container_width=True, hide_index=True)
with st.expander("View Neon CRM email data"):
    if neon_view.empty:
        st.write("No Neon CRM CSV data loaded.")
    else:
        st.dataframe(neon_view, use_container_width=True, hide_index=True)

# ---------- Downloads ----------
st.subheader("Download filtered reporting data")
if not meta_view.empty:
    st.download_button(
        "Download combined Meta data (CSV)",
        meta_view.to_csv(index=False).encode("utf-8"),
        file_name="oakcliff_meta_monthly_data.csv",
        mime="text/csv",
    )
if not neon_view.empty:
    st.download_button(
        "Download cleaned Neon email data (CSV)",
        neon_view.to_csv(index=False).encode("utf-8"),
        file_name="oakcliff_neon_email_monthly_data.csv",
        mime="text/csv",
    )

st.caption(
    "Reporting note: reach/views/interactions in content-level exports are summed across the selected rows. "
    "Follower counts are shown as the latest available snapshot, not added together. "
    "Use the same export type and date-range convention each month for consistent comparisons."
)
