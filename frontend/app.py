import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime

BASE_URL = "http://localhost:8000"

# ── Session State ──────────────────────────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = ""
if "current_page" not in st.session_state:
    st.session_state.current_page = "Register"

# ── Helpers ────────────────────────────────────────────────────────────────────
def set_page(page):
    st.session_state.current_page = page

def logout():
    st.session_state.logged_in = False
    st.session_state.user = ""
    st.session_state.current_page = "Login"

def get_profile(user):
    try:
        r = requests.get(f"{BASE_URL}/profile/{user}", timeout=5)
        return r.json() if r.status_code == 200 else None
    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot connect to backend. Is it running?")
        return None

def get_expenses(user):
    try:
        r = requests.get(f"{BASE_URL}/expense/{user}", timeout=5)
        return r.json().get("expenses", []) if r.status_code == 200 else []
    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot connect to backend.")
        return []

# ── Sidebar ────────────────────────────────────────────────────────────────────
def show_sidebar():
    st.sidebar.title("SmartSpend 💰")

    if not st.session_state.logged_in:
        st.sidebar.button("Register", on_click=lambda: set_page("Register"))
        st.sidebar.button("Login",    on_click=lambda: set_page("Login"))
    else:
        profile = get_profile(st.session_state.user)
        if not profile:
            st.sidebar.button("Create Profile", on_click=lambda: set_page("Create Profile"))
        else:
            st.sidebar.button("Dashboard",           on_click=lambda: set_page("Dashboard"))
            st.sidebar.button("Add Expense",          on_click=lambda: set_page("Add Expense"))
            st.sidebar.button("View Expense History", on_click=lambda: set_page("View Expense History"))
            st.sidebar.button("Update Profile",       on_click=lambda: set_page("Update Profile"))
        st.sidebar.button("Logout", on_click=logout)

# ── Register ───────────────────────────────────────────────────────────────────
def register_page():
    st.title("📝 Register")
    u = st.text_input("Username")
    e = st.text_input("Email")
    p = st.text_input("Password", type="password")

    if st.button("Register"):
        if not u or not e or not p:
            st.warning("Please fill in all fields.")
            return
        try:
            r = requests.post(f"{BASE_URL}/register",
                              json={"username": u, "email": e, "password": p}, timeout=5)
            if r.status_code == 200:
                st.success("Registered! Please login.")
                set_page("Login")
                st.rerun()
            else:
                # FIX: show readable error, not raw JSON
                detail = r.json().get("detail", r.text)
                st.error(f"❌ {detail}")
        except requests.exceptions.ConnectionError:
            st.error("❌ Cannot connect to backend.")

# ── Login ──────────────────────────────────────────────────────────────────────
def login_page():
    st.title("🔐 Login")
    i = st.text_input("Username or Email")
    p = st.text_input("Password", type="password")

    if st.button("Login"):
        if not i or not p:
            st.warning("Please fill in all fields.")
            return
        try:
            r = requests.post(f"{BASE_URL}/login",
                              json={"identifier": i, "password": p}, timeout=5)
            if r.status_code == 200:
                st.success("Logged in!")
                st.session_state.logged_in = True
                st.session_state.user = r.json()["username"]
                set_page("Dashboard")
                st.rerun()
            else:
                detail = r.json().get("detail", r.text)
                st.error(f"❌ {detail}")
        except requests.exceptions.ConnectionError:
            st.error("❌ Cannot connect to backend.")

# ── Create Profile ─────────────────────────────────────────────────────────────
def create_profile_page():
    st.title("👤 Create Profile")
    first  = st.text_input("First Name")
    last   = st.text_input("Last Name")
    status = st.selectbox("Working Status", ["student", "working_professional"])

    if status == "student":
        income = {"allowance": st.number_input("Monthly Allowance", min_value=0.0)}
    else:
        income = {"monthly_salary": st.number_input("Monthly Salary", min_value=0.0)}

    st.subheader("Fixed Expenses (optional)")
    fixed = []
    for i in range(3):
        with st.expander(f"Fixed Expense {i+1}"):
            n = st.text_input("Name",     key=f"cname{i}")
            a = st.number_input("Amount", key=f"camt{i}",  min_value=0.0)
            c = st.text_input("Category", key=f"ccat{i}")
            if n and c:
                fixed.append({"name": n, "amount": a, "category": c})

    if st.button("Create Profile"):
        if not first or not last:
            st.warning("Please enter your name.")
            return
        try:
            r = requests.post(f"{BASE_URL}/profile/create", json={
                "username":       st.session_state.user,
                "first_name":     first,
                "last_name":      last,
                "working_status": status,
                "income":         income,
                "fixed_expenses": fixed,
            }, timeout=5)
            if r.status_code == 200:
                st.success("Profile created!")
                set_page("Dashboard")
                st.rerun()
            else:
                detail = r.json().get("detail", r.text)
                st.error(f"❌ {detail}")
        except requests.exceptions.ConnectionError:
            st.error("❌ Cannot connect to backend.")

# ── Update Profile ─────────────────────────────────────────────────────────────
def update_profile_page():
    st.title("✏️ Update Profile")
    p = get_profile(st.session_state.user)
    if not p:
        st.error("Could not load profile.")
        return

    first  = st.text_input("First Name", p.get("first_name", ""))
    last   = st.text_input("Last Name",  p.get("last_name", ""))
    status = st.selectbox("Working Status", ["student", "working_professional"],
                          index=0 if p.get("working_status") == "student" else 1)

    if status == "student":
        income = {"allowance": st.number_input("Monthly Allowance",
                                                value=float(p["income"].get("allowance", 0.0)))}
    else:
        income = {"monthly_salary": st.number_input("Monthly Salary",
                                                     value=float(p["income"].get("monthly_salary", 0.0)))}

    st.subheader("Fixed Expenses")
    fixed    = []
    existing = p.get("fixed_expenses", [])
    for i in range(max(3, len(existing))):
        d = existing[i] if i < len(existing) else {"name": "", "amount": 0.0, "category": ""}
        with st.expander(f"Fixed Expense {i+1}", expanded=i < len(existing)):
            n = st.text_input("Name",     value=d["name"],            key=f"upn{i}")
            a = st.number_input("Amount", value=float(d["amount"]),   key=f"upa{i}", min_value=0.0)
            c = st.text_input("Category", value=d["category"],        key=f"upc{i}")
            if n and c:
                fixed.append({"name": n, "amount": a, "category": c})

    if st.button("Update"):
        try:
            r = requests.put(f"{BASE_URL}/profile/update/{st.session_state.user}", json={
                "username":       st.session_state.user,
                "first_name":     first,
                "last_name":      last,
                "working_status": status,
                "income":         income,
                "fixed_expenses": fixed,
            }, timeout=5)
            if r.status_code == 200:
                st.success("Profile updated!")
                st.rerun()
            else:
                detail = r.json().get("detail", r.text)
                st.error(f"❌ {detail}")
        except requests.exceptions.ConnectionError:
            st.error("❌ Cannot connect to backend.")

# ── Dashboard ──────────────────────────────────────────────────────────────────
def dashboard_page():
    st.title("📊 SmartSpend Dashboard")

    profile  = get_profile(st.session_state.user)
    expenses = get_expenses(st.session_state.user)

    if not profile:
        st.warning("Please create your profile first.")
        set_page("Create Profile")
        st.rerun()
        return  # FIX: return after rerun to stop further execution

    months = sorted({e["month"] for e in expenses}, reverse=True)
    cur    = datetime.now().strftime("%Y-%m")
    if cur not in months:
        months.insert(0, cur)

    month   = st.selectbox("Select Month", months)
    salary  = (profile["income"].get("monthly_salary")
               or profile["income"].get("allowance") or 0)
    monthly = [e for e in expenses if e["month"] == month]
    spent   = sum(e["amount"] for e in monthly)
    remaining = salary - spent

    # ── Metrics ───────────────────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    c1.metric("💰 Income",    f"₹{salary:,.2f}")
    c2.metric("💸 Spent",     f"₹{spent:,.2f}")
    c3.metric("🏦 Remaining", f"₹{remaining:,.2f}",
              delta=f"{'Over budget!' if remaining < 0 else 'On track'}",
              delta_color="inverse" if remaining < 0 else "normal")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Budget Overview")
        pie = pd.DataFrame({
            "Status": ["Spent", "Remaining"],
            "Amount": [spent, max(0, remaining)]
        })
        st.plotly_chart(
            px.pie(pie, names="Status", values="Amount",
                   color_discrete_map={"Spent": "#ef4444", "Remaining": "#22c55e"}),
            width='stretch'   # FIX: replaces deprecated use_container_width
        )

    with col2:
        st.subheader("Spending Trend")
        if monthly:
            df              = pd.DataFrame(monthly)
            df["created_at"] = pd.to_datetime(df["created_at"])
            df["date"]       = df["created_at"].dt.date
            trend            = df.groupby("date")["amount"].sum().reset_index()
            st.line_chart(trend.set_index("date"))
        else:
            st.info("No expenses this month yet.")

    # ── Category breakdown ────────────────────────────────────────────────────
    if monthly:
        st.subheader("By Category")
        df_cat = pd.DataFrame(monthly).groupby("category")["amount"].sum().reset_index()
        st.plotly_chart(
            px.bar(df_cat, x="category", y="amount",
                   labels={"amount": "₹ Spent", "category": "Category"}),
            width='stretch'
        )

# ── Add Expense ────────────────────────────────────────────────────────────────
def add_expense_page():
    st.title("➕ Add Expense")
    t = st.text_input("Title")
    a = st.number_input("Amount (₹)", min_value=0.0, step=1.0)
    c = st.selectbox("Category", [
        "Food", "Transport", "Shopping", "Entertainment",
        "Health", "Education", "Bills", "Other"
    ])

    if st.button("Add Expense"):
        if not t:
            st.warning("Please enter a title.")
            return
        if a <= 0:
            st.warning("Amount must be greater than 0.")
            return
        try:
            r = requests.post(f"{BASE_URL}/add-expense", json={
                "username": st.session_state.user,
                "title":    t,
                "amount":   float(a),   # FIX: ensure float, not numpy type
                "category": c,
            }, timeout=10)
            if r.status_code == 200:
                st.success(f"✅ ₹{a:.2f} added for '{t}'!")
                st.rerun()
            else:
                # FIX: show actual error detail instead of raw response
                try:
                    detail = r.json().get("detail", r.text)
                except Exception:
                    detail = r.text
                st.error(f"❌ {detail}")
        except requests.exceptions.ConnectionError:
            st.error("❌ Cannot connect to backend.")
        except requests.exceptions.Timeout:
            st.error("⏱️ Request timed out. Backend may be busy.")

# ── Expense History ────────────────────────────────────────────────────────────
def view_expense_history_page():
    st.title("📋 Expense History")
    data = get_expenses(st.session_state.user)

    if not data:
        st.info("No expenses recorded yet.")
        return

    df = pd.DataFrame(data)
    df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%d %b %Y, %I:%M %p")
    df = df.rename(columns={
        "title": "Title", "amount": "Amount (₹)",
        "category": "Category", "created_at": "Date", "month": "Month"
    })
    df = df[["Date", "Title", "Amount (₹)", "Category", "Month"]]
    df = df.sort_values("Date", ascending=False)

    # Summary
    total = sum(e["amount"] for e in data)
    st.metric("Total Spent (All Time)", f"₹{total:,.2f}")

    st.dataframe(df, width='stretch')

# ── Router ─────────────────────────────────────────────────────────────────────
show_sidebar()

page = st.session_state.current_page

if page == "Register":
    register_page()
elif page == "Login":
    login_page()
elif page == "Create Profile":
    create_profile_page()
elif page == "Update Profile":
    update_profile_page()
elif page == "Dashboard":
    dashboard_page()
elif page == "Add Expense":
    add_expense_page()
elif page == "View Expense History":
    view_expense_history_page()