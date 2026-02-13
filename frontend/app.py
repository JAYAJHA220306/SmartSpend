import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime

BASE_URL = "http://localhost:8000"

# -------------------------------
# Session State Initialization
# -------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = ""
if "current_page" not in st.session_state:
    st.session_state.current_page = "Register"

# -------------------------------
# Sidebar
# -------------------------------
def show_sidebar():
    st.sidebar.title("SmartSpend")

    if not st.session_state.logged_in:
        st.sidebar.button("Register", on_click=lambda: set_page("Register"))
        st.sidebar.button("Login", on_click=lambda: set_page("Login"))

    if st.session_state.logged_in:
        profile = get_profile(st.session_state.user)

        if not profile:
            st.sidebar.button("Create Profile", on_click=lambda: set_page("Create Profile"))
        else:
            st.sidebar.button("Dashboard", on_click=lambda: set_page("Dashboard"))
            st.sidebar.button("Update Profile", on_click=lambda: set_page("Update Profile"))
            st.sidebar.button("Add Expense", on_click=lambda: set_page("Add Expense"))
            st.sidebar.button("View Expense History", on_click=lambda: set_page("View Expense History"))

        st.sidebar.button("Logout", on_click=logout)

def set_page(page):
    st.session_state.current_page = page

def logout():
    st.session_state.logged_in = False
    st.session_state.user = ""
    st.session_state.current_page = "Login"

# -------------------------------
# API Helpers
# -------------------------------
def get_profile(user):
    r = requests.get(f"{BASE_URL}/profile/{user}")
    return r.json() if r.status_code == 200 else None

def get_expenses(user):
    r = requests.get(f"{BASE_URL}/expense/{user}")
    return r.json().get("expenses", []) if r.status_code == 200 else []

# -------------------------------
# Register
# -------------------------------
def register_page():
    st.title("Register")
    u = st.text_input("Username")
    e = st.text_input("Email")
    p = st.text_input("Password", type="password")

    if st.button("Register"):
        r = requests.post(f"{BASE_URL}/register", json={"username": u, "email": e, "password": p})
        if r.status_code == 200:
            st.success("Registered! Please login.")
            set_page("Login")
        else:
            st.error(r.text)

# -------------------------------
# Create Profile
# -------------------------------
def create_profile_page():
    st.title("Create Profile")
    first = st.text_input("First Name")
    last = st.text_input("Last Name")
    status = st.selectbox("Working Status", ["student", "working_professional"])

    if status == "student":
        income = {"allowance": st.number_input("Monthly Allowance", min_value=0.0)}
    else:
        income = {"monthly_salary": st.number_input("Monthly Salary", min_value=0.0)}

    st.subheader("Fixed Expenses")
    fixed = []
    for i in range(3):
        with st.expander(f"Expense {i+1}", expanded=True):
            n = st.text_input("Name", key=f"cname{i}")
            a = st.number_input("Amount", min_value=0.0, key=f"camt{i}")
            c = st.text_input("Category", key=f"ccat{i}")
            if n and c:
                fixed.append({"name": n, "amount": a, "category": c})

    if st.button("Create Profile"):
        r = requests.post(f"{BASE_URL}/profile/create", json={
            "username": st.session_state.user,
            "first_name": first,
            "last_name": last,
            "working_status": status,
            "income": income,
            "fixed_expenses": fixed
        })
        if r.status_code == 200:
            st.success("Profile created!")
            set_page("Dashboard")
            st.rerun()
        else:
            st.error(r.text)

# -------------------------------
# Login
# -------------------------------
def login_page():
    st.title("Login")
    i = st.text_input("Username or Email")
    p = st.text_input("Password", type="password")

    if st.button("Login"):
        r = requests.post(f"{BASE_URL}/login", json={"identifier": i, "password": p})
        if r.status_code == 200:
            st.success("Logged in!")
            st.session_state.logged_in = True
            st.session_state.user = r.json()["username"]
            set_page("Dashboard")
            st.rerun()
        else:
            st.error(r.text)

# -------------------------------
# Dashboard
# -------------------------------
def dashboard_page():
    st.title("📊 SmartSpend Dashboard")

    profile = get_profile(st.session_state.user)
    expenses = get_expenses(st.session_state.user)

    if not profile:
        st.warning("Please create your profile first.")
        set_page("Create Profile")
        st.rerun()

    months = sorted({e["month"] for e in expenses}, reverse=True)
    cur = datetime.now().strftime("%Y-%m")
    if cur not in months:
        months.insert(0, cur)

    month = st.selectbox("Select Month", months)

    salary = profile["income"].get("monthly_salary") or profile["income"].get("allowance") or 0
    monthly = [e for e in expenses if e["month"] == month]
    spent = sum(e["amount"] for e in monthly)
    remaining = salary - spent

    col1, col2 = st.columns(2)

    with col1:
        pie = pd.DataFrame({"Status": ["Spent", "Remaining"], "Amount": [spent, max(0, remaining)]})
        st.plotly_chart(px.pie(pie, names="Status", values="Amount"), use_container_width=True)

    with col2:
        if monthly:
            df = pd.DataFrame(monthly)
            df["created_at"] = pd.to_datetime(df["created_at"])
            df["date"] = df["created_at"].dt.date
            trend = df.groupby("date")["amount"].sum().reset_index()
            st.line_chart(trend.set_index("date"))
        else:
            st.info("No expenses yet")

    c1, c2, c3 = st.columns(3)
    c1.metric("Income", f"₹{salary}")
    c2.metric("Spent", f"₹{spent}")
    c3.metric("Remaining", f"₹{remaining}")

# -------------------------------
# Update Profile
# -------------------------------
def update_profile_page():
    st.title("Update Profile")
    p = get_profile(st.session_state.user)

    first = st.text_input("First Name", p["first_name"])
    last = st.text_input("Last Name", p["last_name"])

    status = st.selectbox("Working Status", ["student", "working_professional"],
                          index=0 if p["working_status"] == "student" else 1)

    if status == "student":
        income = {"allowance": st.number_input("Monthly Allowance", p["income"].get("allowance", 0.0))}
    else:
        income = {"monthly_salary": st.number_input("Monthly Salary", p["income"].get("monthly_salary", 0.0))}

    st.subheader("Fixed Expenses")
    fixed = []
    existing = p.get("fixed_expenses", [])
    for i in range(max(3, len(existing))):
        d = existing[i] if i < len(existing) else {"name": "", "amount": 0, "category": ""}
        with st.expander(f"Expense {i+1}", expanded=True):
            n = st.text_input("Name", d["name"], key=f"upn{i}")
            a = st.number_input("Amount", value=float(d["amount"]), min_value=0.0, key=f"upa{i}")

            c = st.text_input("Category", d["category"], key=f"upc{i}")
            if n and c:
                fixed.append({"name": n, "amount": a, "category": c})

    if st.button("Update"):
        r = requests.put(f"{BASE_URL}/profile/update/{st.session_state.user}", json={
            "username": st.session_state.user,
            "first_name": first,
            "last_name": last,
            "working_status": status,
            "income": income,
            "fixed_expenses": fixed
        })
        if r.status_code == 200:
            st.success("Updated!")
            st.rerun()
        else:
            st.error(r.text)

# -------------------------------
# Add Expense
# -------------------------------
def add_expense_page():
    st.title("Add Expense")
    t = st.text_input("Title")
    a = st.number_input("Amount", min_value=0.0)
    c = st.text_input("Category")

    if st.button("Add"):
        r = requests.post(f"{BASE_URL}/add-expense", json={
            "username": st.session_state.user,
            "title": t,
            "amount": a,
            "category": c
        })
        if r.status_code == 200:
            st.success("Added!")
            st.rerun()
        else:
            st.error(r.text)

# -------------------------------
# View History
# -------------------------------
def view_expense_history_page():
    st.title("Expense History")
    data = get_expenses(st.session_state.user)
    if not data:
        st.info("No expenses yet")
        return
    st.dataframe(pd.DataFrame(data), use_container_width=True)

# -------------------------------
# Router
# -------------------------------
show_sidebar()

if st.session_state.current_page == "Register":
    register_page()
elif st.session_state.current_page == "Create Profile":
    create_profile_page()
elif st.session_state.current_page == "Login":
    login_page()
elif st.session_state.current_page == "Dashboard":
    dashboard_page()
elif st.session_state.current_page == "Update Profile":
    update_profile_page()
elif st.session_state.current_page == "Add Expense":
    add_expense_page()
elif st.session_state.current_page == "View Expense History":
    view_expense_history_page()

