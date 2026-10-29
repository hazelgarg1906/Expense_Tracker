import uuid
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

# ---------- Config ----------
st.set_page_config(page_title="Expense Tracker", page_icon="💸", layout="wide")

COLUMNS = ["id", "date", "category", "amount", "note"]
CATEGORIES = ["Food", "Transport", "Shopping", "Bills", "Entertainment",
              "Health", "Education", "Other"]
CURRENCY = "₹"

st.markdown(
    """
    <style>
    .block-container {padding-top: 2rem;}
    div[data-testid="stMetric"] {
        background: rgba(128,128,128,0.08);
        border: 1px solid rgba(128,128,128,0.2);
        padding: 14px 18px; border-radius: 14px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------- Data helpers ----------
def load_data() -> pd.DataFrame:
    # Each visitor gets their own private data, stored in their browser session
    if "expenses" not in st.session_state:
        st.session_state.expenses = pd.DataFrame(columns=COLUMNS).astype({"amount": float})
    return st.session_state.expenses.copy()


def save_data(df: pd.DataFrame) -> None:
    st.session_state.expenses = df[COLUMNS].reset_index(drop=True)


def money(x: float) -> str:
    return f"{CURRENCY}{x:,.0f}"


df = load_data()
df["month"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m") if not df.empty else ""

# ---------- Sidebar: add expense + budget ----------
with st.sidebar:
    st.header("➕ Add expense")
    with st.form("add_expense", clear_on_submit=True):
        d = st.date_input("Date", date.today())
        category = st.selectbox("Category", CATEGORIES)
        amount = st.number_input(f"Amount ({CURRENCY})", min_value=0.0, step=10.0)
        note = st.text_input("Note (optional)")
        submitted = st.form_submit_button("Add expense", use_container_width=True)

    if submitted:
        if amount <= 0:
            st.error("Enter an amount greater than 0.")
        else:
            new = pd.DataFrame([{
                "id": uuid.uuid4().hex[:8],
                "date": pd.to_datetime(d),
                "category": category,
                "amount": amount,
                "note": note,
            }])
            save_data(pd.concat([df[COLUMNS], new], ignore_index=True))
            st.toast("Expense added!", icon="✅")
            st.rerun()

    st.divider()
    st.header("📂 Your data")
    st.caption("Your expenses are private to you and live only in this session. "
               "Export a CSV before you leave and re-import it next time.")
    up = st.file_uploader("Import CSV", type="csv")
    if up is not None and st.session_state.get("last_upload") != up.file_id:
        try:
            imp = pd.read_csv(up)
            if not set(COLUMNS).issubset(imp.columns):
                st.error("That CSV doesn't look like an export from this app.")
            else:
                imp["date"] = pd.to_datetime(imp["date"])
                imp["amount"] = imp["amount"].astype(float)
                imp["note"] = imp["note"].fillna("")
                save_data(imp)
                st.session_state["last_upload"] = up.file_id
                st.toast("Data imported!", icon="📂")
                st.rerun()
        except Exception:
            st.error("Couldn't read that file.")

    st.divider()
    st.header("🎯 Monthly budget")
    budget = st.number_input(f"Budget ({CURRENCY})", min_value=0.0,
                             value=10000.0, step=500.0)

# ---------- Header + month filter ----------
st.title("💸 Personal Expense Tracker")

current_month = date.today().strftime("%Y-%m")
months = sorted(set(df["month"].tolist()) | {current_month}, reverse=True)
months = [m for m in months if m]
selected = st.selectbox("Month", months, index=months.index(current_month))

month_df = df[df["month"] == selected].copy()
total = month_df["amount"].sum()

# ---------- Metrics ----------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total spent", money(total))
c2.metric("Transactions", len(month_df))
days = month_df["date"].dt.date.nunique() if not month_df.empty else 0
c3.metric("Avg per active day", money(total / days) if days else money(0))
top_cat = (month_df.groupby("category")["amount"].sum().idxmax()
           if not month_df.empty else "—")
c4.metric("Top category", top_cat)

# ---------- Budget progress ----------
if budget > 0:
    used = total / budget
    st.progress(min(used, 1.0), text=f"{used:.0%} of budget used "
                                      f"({money(total)} / {money(budget)})")
    if used > 1:
        st.error(f"Over budget by {money(total - budget)}")
    elif used > 0.8:
        st.warning("You've used over 80% of your budget.")

# ---------- Tabs ----------
tab1, tab2 = st.tabs(["📊 Overview", "🧾 Transactions"])

with tab1:
    if month_df.empty:
        st.info("No expenses this month yet. Add one from the sidebar.")
    else:
        left, right = st.columns(2)
        by_cat = month_df.groupby("category", as_index=False)["amount"].sum()
        fig_pie = px.pie(by_cat, names="category", values="amount", hole=0.55,
                         title="Spending by category")
        left.plotly_chart(fig_pie, use_container_width=True)

        daily = (month_df.groupby(month_df["date"].dt.date)["amount"]
                 .sum().reset_index())
        daily.columns = ["date", "amount"]
        fig_bar = px.bar(daily, x="date", y="amount", title="Daily spending")
        right.plotly_chart(fig_bar, use_container_width=True)

with tab2:
    cats = st.multiselect("Filter by category", CATEGORIES)
    view = month_df if not cats else month_df[month_df["category"].isin(cats)]
    view = view.sort_values("date", ascending=False).copy()
    view["Delete"] = False

    edited = st.data_editor(
        view,
        hide_index=True,
        use_container_width=True,
        column_order=["Delete", "date", "category", "amount", "note"],
        disabled=["id", "date", "category", "amount", "note"],
        column_config={
            "date": st.column_config.DateColumn("Date", format="DD MMM YYYY"),
            "amount": st.column_config.NumberColumn("Amount", format=f"{CURRENCY}%.0f"),
        },
        key="editor",
    )

    b1, b2, _ = st.columns([1, 1, 3])
    if b1.button("🗑️ Delete selected"):
        ids = edited.loc[edited["Delete"], "id"]
        if len(ids):
            save_data(df[~df["id"].isin(ids)])
            st.rerun()
        else:
            st.info("Tick the rows you want to delete first.")
    b2.download_button("⬇️ Export CSV", df[COLUMNS].to_csv(index=False),
                       file_name="expenses.csv", mime="text/csv")
