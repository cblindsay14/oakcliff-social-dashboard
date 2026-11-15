from pathlib import Path
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(
    page_title="Oakcliff Sailing | Social Analytics",
    page_icon="⛵",
    layout="wide",
)

ROOT = Path(__file__).parent
DATA = ROOT / "data"

st.title("Oakcliff Sailing | Social Analytics")
st.caption("Monthly performance across Facebook, Instagram and Neon CRM")

def read_csv(path):
    try:
        if path.exists():
            return pd.read_csv(path)
    except Exception as exc:
        st.warning(f"Could not read {path.name}: {exc}")
    return pd.DataFrame()

def metric_value(df, metric, value_col="value"):
    if df.empty or "metric" not in df.columns:
        return None
    rows = df[df["metric"].astype(str).str.lower() == metric.lower()]
    if rows.empty:
        return None
    return rows.iloc[0][value_col]

def display_number(value):
    if value is None or pd.isna(value):
        return "—"
    try:
        return f"{int(float(value)):,}"
    except (ValueError, TypeError):
        return str(value)

def kpi(label, value, help_text=None):
    st.metric(label, display_number(value) if value is not None else "—", help=help_text)

# Load the exact files stored in the private GitHub repository.
fb = read_csv(DATA / "meta" / "facebook" / "facebook_monthly_summary.csv")
fb_formats = read_csv(DATA / "meta" / "facebook" / "facebook_content_formats.csv")
fb_audience = read_csv(DATA / "meta" / "facebook" / "facebook_audience_demographics.csv")
fb_posts = read_csv(DATA / "meta" / "facebook" / "facebook_post_performance.csv")

ig_summary = read_csv(DATA / "meta" / "instagram" / "instagram_monthly_summary.csv")
ig_daily = read_csv(DATA / "meta" / "instagram" / "instagram_daily_metrics.csv")
ig_posts = read_csv(DATA / "meta" / "instagram" / "instagram_content_performance.csv")
ig_stories = read_csv(DATA / "meta" / "instagram" / "instagram_story_performance.csv")
ig_audience = read_csv(DATA / "meta" / "instagram" / "instagram_audience_demographics.csv")

neon = read_csv(DATA / "neon" / "neon_campaign_summary.csv")

# Reporting period
report_month = "October 2026"
if not fb.empty and "reporting_month" in fb.columns:
    report_month = str(fb.iloc[0]["reporting_month"])
    try:
        report_month = pd.to_datetime(report_month).strftime("%B %Y")
    except Exception:
        pass
st.subheader(report_month)

tabs = st.tabs(["Overview", "Facebook", "Instagram", "Email"])

with tabs[0]:
    st.markdown("### Cross-platform snapshot")
    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("**Facebook**")
        if not fb.empty:
            r = fb.iloc[0]
            kpi("Daily viewers summed", r.get("unique_viewers_daily_sum"),
                "Sum of daily viewers; not unique people across the month.")
            kpi("Content interactions", r.get("content_interactions_daily_sum"))
            kpi("Link clicks", r.get("link_clicks_daily_sum"))
            kpi("New follows", r.get("new_follows_daily_sum"))
        else:
            st.info("Facebook monthly summary not found.")

    with c2:
        st.markdown("**Instagram**")
        kpi("Views", metric_value(ig_summary, "views"))
        kpi("Content interactions", metric_value(ig_summary, "content_interactions"))
        kpi("Profile visits", metric_value(ig_summary, "profile_visits"))
        kpi("New follows", metric_value(ig_summary, "follows"))

    with c3:
        st.markdown("**Neon CRM email**")
        if not neon.empty:
            n = neon.iloc[0]
            kpi("Recipients attempted", n.get("recipients_attempted"))
            kpi("Open rate", f'{n.get("open_rate_pct", "—")}%' if pd.notna(n.get("open_rate_pct")) else None)
            kpi("Click rate", f'{n.get("click_rate_pct", "—")}%' if pd.notna(n.get("click_rate_pct")) else None)
            kpi("Unsubscribes", n.get("unsubscribed"))
        else:
            st.info("Neon campaign summary not found.")

    st.caption("Metrics are platform-defined and may use different counting methods. See each platform tab for definitions and reporting notes.")

with tabs[1]:
    st.markdown("### Facebook performance")
    if fb.empty:
        st.warning("No Facebook summary found. Check data/meta/facebook/")
    else:
        r = fb.iloc[0]
        a, b, c, d = st.columns(4)
        with a: kpi("Daily viewers summed", r.get("unique_viewers_daily_sum"))
        with b: kpi("Content interactions", r.get("content_interactions_daily_sum"))
        with c: kpi("Link clicks", r.get("link_clicks_daily_sum"))
        with d: kpi("Page visits", r.get("page_visits_daily_sum"))

        e, f, g = st.columns(3)
        with e: kpi("New follows", r.get("new_follows_daily_sum"))
        with f: kpi("Views (partial export)", r.get("views_partial_period_oct17_oct31"),
                    "The export starts October 17, so this is not a full-month total.")
        with g:
            st.metric("Shares metric", "Not available" if not bool(r.get("shares_metric_available", False)) else "Available")

        st.info("Daily viewers are summed across days and should not be interpreted as unique monthly people. The Views export covers October 17–November 13, 2026; the displayed October value is only October 17–31.")

    if not fb_formats.empty and {"metric", "content_format", "value"}.issubset(fb_formats.columns):
        st.markdown("### Performance by content format")
        metric_options = sorted(fb_formats["metric"].dropna().astype(str).unique().tolist())
        selected_metric = st.selectbox("Choose a metric", metric_options, key="fb_format_metric")
        plot_data = fb_formats[fb_formats["metric"].astype(str) == selected_metric].copy()
        plot_data["value"] = pd.to_numeric(plot_data["value"], errors="coerce")
        fig = px.bar(plot_data.sort_values("value", ascending=False), x="content_format", y="value",
                     title=f"Facebook {selected_metric.replace('_', ' ').title()} by format")
        st.plotly_chart(fig, use_container_width=True)

    if not fb_audience.empty:
        st.markdown("### Audience demographics")
        sections = fb_audience["section"].dropna().unique().tolist() if "section" in fb_audience.columns else []
        for section in sections:
            section_df = fb_audience[fb_audience["section"] == section].copy()
            st.markdown(f"**{str(section).replace('_', ' ').title()}**")
            st.dataframe(section_df, use_container_width=True, hide_index=True)

    if not fb_posts.empty:
        st.markdown("### Individual Facebook posts")
        st.caption("Post-level export supplied by Meta. Sortable table; blank metrics remain blank where Meta did not provide a value.")
        preferred = [c for c in ["post_title", "publish_time", "post_type", "Reactions, Comments and Shares",
                                 "Reactions", "Comments", "Shares", "3-second video views",
                                 "1-minute video views", "Seconds viewed"] if c in fb_posts.columns]
        st.dataframe(fb_posts[preferred] if preferred else fb_posts, use_container_width=True, hide_index=True)

with tabs[2]:
    st.markdown("### Instagram performance")
    if ig_summary.empty:
        st.warning("No Instagram summary found. Check data/meta/instagram/")
    else:
        vals = {str(row["metric"]): row["value"] for _, row in ig_summary.iterrows()}
        a, b, c = st.columns(3)
        with a: kpi("Views", vals.get("views"))
        with b: kpi("Daily reach summed", vals.get("reach"),
                    "Sum of daily reach; not unique monthly reach.")
        with c: kpi("Content interactions", vals.get("content_interactions"))
        d, e, f = st.columns(3)
        with d: kpi("Profile visits", vals.get("profile_visits"))
        with e: kpi("Link clicks", vals.get("link_clicks"))
        with f: kpi("New follows", vals.get("follows"))
        g, h = st.columns(2)
        with g: kpi("Stories published", vals.get("published_stories"))
        with h: kpi("Posts and Reels published", vals.get("published_posts_and_reels"))

        st.info("Reach is the sum of daily reach values. It is not a deduplicated count of unique people reached during October.")

    if not ig_daily.empty and "date" in ig_daily.columns:
        st.markdown("### Daily Instagram trends")
        ig_daily["date"] = pd.to_datetime(ig_daily["date"], errors="coerce")
        metric_choices = [c for c in ["views", "reach", "content_interactions", "profile_visits", "link_clicks", "follows"] if c in ig_daily.columns]
        selected = st.multiselect("Metrics to display", metric_choices, default=[m for m in ["views", "reach"] if m in metric_choices])
        if selected:
            long_df = ig_daily.melt(id_vars="date", value_vars=selected, var_name="Metric", value_name="Value")
            fig = px.line(long_df, x="date", y="Value", color="Metric", markers=True)
            st.plotly_chart(fig, use_container_width=True)
        with st.expander("View daily data"):
            st.dataframe(ig_daily, use_container_width=True, hide_index=True)

    if not ig_posts.empty:
        st.markdown("### Instagram posts and Reels")
        cols = [c for c in ["Publish time", "Description", "Post type", "Views", "Reach", "Likes", "Comments", "Shares", "Saves", "Follows", "Permalink"] if c in ig_posts.columns]
        st.dataframe(ig_posts[cols] if cols else ig_posts, use_container_width=True, hide_index=True)

    if not ig_stories.empty:
        st.markdown("### Instagram Stories")
        cols = [c for c in ["Publish time", "Description", "Views", "Reach", "Replies", "Navigation", "Profile visits", "Link clicks", "Sticker taps", "Permalink"] if c in ig_stories.columns]
        st.dataframe(ig_stories[cols] if cols else ig_stories, use_container_width=True, hide_index=True)

    if not ig_audience.empty:
        st.markdown("### Instagram audience demographics")
        if {"dimension", "category", "percentage"}.issubset(ig_audience.columns):
            for dimension in ig_audience["dimension"].dropna().unique():
                part = ig_audience[ig_audience["dimension"] == dimension].copy()
                part["percentage"] = pd.to_numeric(part["percentage"], errors="coerce")
                st.markdown(f"**{str(dimension).replace('_', ' ').title()}**")
                fig = px.bar(part.sort_values("percentage", ascending=False), x="category", y="percentage")
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.dataframe(ig_audience, use_container_width=True, hide_index=True)

with tabs[3]:
    st.markdown("### Neon CRM email performance")
    if neon.empty:
        st.warning("No Neon CRM summary found. Check data/neon/")
    else:
        n = neon.iloc[0]
        st.markdown(f"**{n.get('campaign_name', 'Email campaign')}** · Sent {n.get('send_date', '')}")
        a, b, c, d = st.columns(4)
        with a: kpi("Recipients attempted", n.get("recipients_attempted"))
        with b: st.metric("Successful deliveries", display_number(n.get("successful_deliveries")), f'{n.get("delivery_rate_pct", "—")}% delivery')
        with c: st.metric("Unique opens", display_number(n.get("unique_opens")), f'{n.get("open_rate_pct", "—")}% open rate')
        with d: st.metric("Unique clickers", display_number(n.get("unique_clickers")), f'{n.get("click_rate_pct", "—")}% click rate')
        e, f, g, h = st.columns(4)
        with e: kpi("Total opens", n.get("total_opens"))
        with f: kpi("Total clicks", n.get("total_clicks"))
        with g: st.metric("Bounced", display_number(n.get("bounced")), f'{n.get("bounce_rate_pct", "—")}%')
        with h: st.metric("Unsubscribed", display_number(n.get("unsubscribed")), f'{n.get("unsubscribe_rate_pct", "—")}%')
        st.caption(f"Clicks per unique open: {n.get('clicks_per_unique_open_pct', '—')}%. This is one campaign report, not a monthly aggregate across all email campaigns.")

st.divider()
st.caption("Oakcliff Sailing · Performance analytics. Data is refreshed when updated CSV files are committed to the private GitHub repository.")
