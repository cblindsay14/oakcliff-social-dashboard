"""
Oakcliff Social Analytics Dashboard
Streamlit dashboard for Instagram Professional + Facebook Page using Meta Graph API.

Run:
  pip install -r requirements.txt
  streamlit run oakcliff_social_dashboard.py

Use a Meta User Access Token with the appropriate approved permissions.
Do not commit or share your token. Paste it into the sidebar only for your local session.
"""
import os
import requests
import pandas as pd
import streamlit as st
import plotly.express as px
from datetime import date, timedelta

GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v26.0")
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"
TIMEOUT = 30

st.set_page_config(page_title="Oakcliff Social Analytics", page_icon="⛵", layout="wide")
st.title("⛵ Oakcliff Sailing | Social Analytics")
st.caption("Instagram Professional + Facebook Page • Data supplied by Meta Graph API")

# ---- API helpers ----
def graph_get(path, token, params=None):
    params = dict(params or {})
    params["access_token"] = token
    response = requests.get(f"{GRAPH_BASE}/{path.lstrip('/')}", params=params, timeout=TIMEOUT)
    try:
        payload = response.json()
    except ValueError:
        response.raise_for_status()
        raise RuntimeError("Meta returned a non-JSON response.")
    if response.status_code >= 400 or "error" in payload:
        error = payload.get("error", {})
        message = error.get("message", response.text)
        raise RuntimeError(f"Meta API error: {message}")
    return payload

def fetch_all(path, token, params=None, max_pages=20):
    """Read a paginated Graph API edge."""
    params = dict(params or {})
    payload = graph_get(path, token, params)
    items = payload.get("data", [])
    pages = 1
    while payload.get("paging", {}).get("next") and pages < max_pages:
        # Use cursor parameters rather than following a URL containing token.
        cursors = payload.get("paging", {}).get("cursors", {})
        after = cursors.get("after")
        if not after:
            break
        params["after"] = after
        payload = graph_get(path, token, params)
        items.extend(payload.get("data", []))
        pages += 1
    return items

def insight_value(data, metric_name):
    for item in data or []:
        if item.get("name") == metric_name:
            values = item.get("values") or []
            if values:
                return values[-1].get("value")
            if item.get("total_value"):
                return item["total_value"].get("value")
    return None

def try_insights(object_id, token, metrics, params=None):
    """Attempt a metrics request; return data and an error string without stopping the app."""
    try:
        result = graph_get(f"{object_id}/insights", token, {"metric": ",".join(metrics), **(params or {})})
        return result.get("data", []), None
    except Exception as exc:
        return [], str(exc)

# ---- Sidebar/auth ----
with st.sidebar:
    st.header("Meta connection")
    token = st.text_input("Meta User Access Token (Instagram)", type="password",
                          help="Paste the User Access Token generated for your Meta app. It is not saved by this script.")
    page_token_input = st.text_input("Facebook Page Access Token (Facebook)", type="password",
                                     help="Paste the Page Access Token for Oakcliff Sailing. It is not saved by this script.")
    st.caption("Keep both tokens private. Paste them only into this local dashboard; never share them in chat or screenshots.")
    if st.button("Connect and load data", type="primary", disabled=not token):
        st.session_state["load_data"] = True
    st.divider()
    days = st.selectbox("Reporting window", [7, 28, 30, 90], index=1)
    st.caption("API access and available metrics depend on the app's approved permissions and the account.")

if not token:
    st.info("Paste your Meta User Access Token and Facebook Page Access Token in the sidebar, then click **Connect and load data**.")
    st.markdown("""
    **Before running:** Meta app access must include the relevant Instagram Insights permissions
    (for Facebook Login, commonly `instagram_basic`, `instagram_manage_insights`,
    `pages_show_list`, and `pages_read_engagement`) and Facebook Page Insights access
    (typically `read_insights` plus `pages_read_engagement`). The Facebook Page Access Token
    is used for Facebook Page details, posts, and Page Insights; the User Access Token is used
    for Instagram. Permission availability and review requirements vary by app and use case.
    """)
    st.stop()

if not st.session_state.get("load_data"):
    st.info("Click **Connect and load data** in the sidebar to query Meta.")
    st.stop()

# ---- Connect directly to Oakcliff Sailing Page + connected IG account ----
# Use the known Oakcliff Sailing Page ID rather than /me/accounts Page discovery.
page_id = "197493546964972"
page_token = page_token_input.strip()
if not page_token:
    st.error("Please enter the Facebook Page Access Token for Oakcliff Sailing in the sidebar.")
    st.stop()

try:
    page_details = graph_get(page_id, page_token, {"fields": "id,name,fan_count,followers_count,instagram_business_account"})
except Exception as exc:
    st.error(f"Could not retrieve Oakcliff Sailing Page details using the Facebook Page Access Token. {exc}")
    st.stop()

ig_id = (page_details.get("instagram_business_account") or {}).get("id")
if not ig_id:
    st.warning("Meta did not return an Instagram professional account connected to this Page. Verify the Page/Instagram connection in Meta Business Suite.")
    st.stop()

# ---- Pull data ----
since_date = date.today() - timedelta(days=days)
until_date = date.today()
since_ts = int(pd.Timestamp(since_date).timestamp())
until_ts = int(pd.Timestamp(until_date + timedelta(days=1)).timestamp())

with st.spinner("Fetching Instagram and Facebook data from Meta..."):
    # IG profile and recent media
    try:
        ig_profile = graph_get(ig_id, token, {"fields": "id,username,name,profile_picture_url,followers_count,follows_count,media_count"})
    except Exception as exc:
        st.error(f"Could not retrieve Instagram profile. {exc}")
        st.stop()

    try:
        ig_media = fetch_all(f"{ig_id}/media", token, {
            "fields": "id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count",
            "limit": 50
        })
    except Exception as exc:
        ig_media = []
        st.warning(f"Instagram media could not be loaded: {exc}")

    # IG account insights - metrics vary by API version and account. Try a modern metric set.
    ig_account_metrics = ["reach", "views", "accounts_engaged", "total_interactions", "profile_views", "follows_and_unfollows"]
    ig_account_insights, ig_insights_error = try_insights(
        ig_id, token, ig_account_metrics,
        {"metric_type": "total_value", "period": "day", "since": since_ts, "until": until_ts}
    )

    # Facebook Page Insights: try supported metric names; Meta may reject metrics not available for this Page/version.
    fb_metrics = ["page_media_view", "page_post_engagements", "page_daily_follows_unique"]
    fb_page_insights, fb_insights_error = try_insights(
        page_id, page_token, fb_metrics,
        {"period": "day", "since": since_ts, "until": until_ts}
    )

    # Recent Facebook posts
    try:
        fb_posts = fetch_all(f"{page_id}/posts", page_token, {
            "fields": "id,message,created_time,permalink_url,shares,likes.summary(true),comments.summary(true)",
            "limit": 50
        })
    except Exception as exc:
        fb_posts = []
        st.warning(f"Facebook posts could not be loaded: {exc}")

# ---- Overview ----
st.subheader("Overview")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Instagram followers", ig_profile.get("followers_count", "—"))
c2.metric("Instagram media count", ig_profile.get("media_count", "—"))
c3.metric("Facebook followers", page_details.get("followers_count", page_details.get("fan_count", "—")))
c4.metric("Reporting window", f"{days} days")

if ig_insights_error:
    st.warning(f"Instagram account insights unavailable: {ig_insights_error}")
if fb_insights_error:
    st.warning(f"Facebook Page insights unavailable: {fb_insights_error}")

# KPI cards where the returned API metric data can be read
ig_kpis = {name: insight_value(ig_account_insights, name) for name in ig_account_metrics}
kpi_cols = st.columns(5)
for col, (name, value) in zip(kpi_cols, [
    ("Instagram reach", ig_kpis.get("reach")),
    ("Instagram views", ig_kpis.get("views")),
    ("Accounts engaged", ig_kpis.get("accounts_engaged")),
    ("Interactions", ig_kpis.get("total_interactions")),
    ("Profile views", ig_kpis.get("profile_views")),
]):
    col.metric(name, value if value is not None else "Unavailable")

# ---- Instagram content table and chart ----
st.subheader("Instagram content performance")
ig_rows = []
for m in ig_media:
    ig_rows.append({
        "Date": m.get("timestamp", "")[:10],
        "Type": m.get("media_product_type") or m.get("media_type"),
        "Caption": (m.get("caption") or "").replace("\n", " ")[:180],
        "Likes": m.get("like_count"),
        "Comments": m.get("comments_count"),
        "Permalink": m.get("permalink"),
        "Media ID": m.get("id"),
    })
ig_df = pd.DataFrame(ig_rows)
if not ig_df.empty:
    ig_df["Date"] = pd.to_datetime(ig_df["Date"], errors="coerce")
    ig_df["Engagements (likes + comments)"] = ig_df[["Likes", "Comments"]].fillna(0).sum(axis=1)
    recent_ig = ig_df[ig_df["Date"] >= pd.Timestamp(since_date)]
    st.dataframe(recent_ig.sort_values("Date", ascending=False), use_container_width=True, hide_index=True)
    chart_df = recent_ig.groupby("Date", as_index=False)["Engagements (likes + comments)"].sum()
    if not chart_df.empty:
        st.plotly_chart(px.line(chart_df, x="Date", y="Engagements (likes + comments)",
                                title="Instagram likes + comments over time"), use_container_width=True)
else:
    st.info("No Instagram media rows returned.")

# Per-media insights calls; results may be limited by metric availability/content age
with st.expander("Instagram per-post Insights (API-supported metrics)"):
    post_metrics = ["reach", "views", "shares", "saved", "total_interactions"]
    post_rows = []
    for m in ig_media[:30]:
        data, err = try_insights(m["id"], token, post_metrics, {"metric_type": "total_value"})
        row = {"Date": m.get("timestamp", "")[:10], "Media ID": m["id"],
               "Type": m.get("media_product_type") or m.get("media_type"),
               "Permalink": m.get("permalink")}
        for metric in post_metrics:
            row[metric] = insight_value(data, metric)
        if err:
            row["API note"] = err[:180]
        post_rows.append(row)
    if post_rows:
        st.dataframe(pd.DataFrame(post_rows), use_container_width=True, hide_index=True)

# ---- Facebook content ----
st.subheader("Facebook Page content")
fb_rows = []
for post in fb_posts:
    likes = ((post.get("likes") or {}).get("summary") or {}).get("total_count")
    comments = ((post.get("comments") or {}).get("summary") or {}).get("total_count")
    shares = (post.get("shares") or {}).get("count")
    fb_rows.append({
        "Date": post.get("created_time", "")[:10],
        "Message": (post.get("message") or "").replace("\n", " ")[:180],
        "Likes": likes, "Comments": comments, "Shares": shares,
        "Permalink": post.get("permalink_url"), "Post ID": post.get("id")
    })
fb_df = pd.DataFrame(fb_rows)
if not fb_df.empty:
    fb_df["Date"] = pd.to_datetime(fb_df["Date"], errors="coerce")
    fb_df["Engagements (likes + comments + shares)"] = fb_df[["Likes", "Comments", "Shares"]].fillna(0).sum(axis=1)
    recent_fb = fb_df[fb_df["Date"] >= pd.Timestamp(since_date)]
    st.dataframe(recent_fb.sort_values("Date", ascending=False), use_container_width=True, hide_index=True)
    fb_chart = recent_fb.groupby("Date", as_index=False)["Engagements (likes + comments + shares)"].sum()
    if not fb_chart.empty:
        st.plotly_chart(px.line(fb_chart, x="Date", y="Engagements (likes + comments + shares)",
                                title="Facebook likes + comments + shares over time"), use_container_width=True)
else:
    st.info("No Facebook posts returned.")

with st.expander("Facebook Page Insights data returned by Meta"):
    if fb_page_insights:
        st.json(fb_page_insights)
    else:
        st.write("No Page insights were returned for the requested metrics/window.")

# ---- Export ----
st.subheader("Export")
col_a, col_b = st.columns(2)
with col_a:
    if not ig_df.empty:
        st.download_button("Download Instagram content CSV", ig_df.to_csv(index=False).encode("utf-8"),
                           "oakcliff_instagram_content.csv", "text/csv")
with col_b:
    if not fb_df.empty:
        st.download_button("Download Facebook content CSV", fb_df.to_csv(index=False).encode("utf-8"),
                           "oakcliff_facebook_content.csv", "text/csv")

st.caption("This is an API-powered starter dashboard, not a guarantee that every Meta metric is accessible. Meta changes metric names, scopes, and availability; unavailable metrics are displayed as unavailable with API notes.")
