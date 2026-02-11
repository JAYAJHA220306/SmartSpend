import streamlit as st
import requests
from datetime import datetime

BASE_URL = "http://localhost:8000"

# -------------------------------
# Session State Initialization
# -------------------------------
if "registered" not in st.session_state:
    st.session_state.registered = False
if "profile_created" not in st.session_state:
    st.session_state.profile_created = False
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = ""
if "current_page" not in st.session_state:
    st.session_state.current_page = "Register"

# -------------------------------
# Sidebar Navigation
# -------------------------------
def show_sidebar():
    st.sidebar.title("SmartSpend")

    if not st.session_state.logged_in:
        st.sidebar.button("Register", on_click=lambda: set_page("Register"))
        st.sidebar.button("Login", on_click=lambda: set_page("Login"))

    if st.session_state.registered and not st.session_state.profile_created:
        st.sidebar.button("Create Profile", on_click=lambda: set_page("Create Profile"))

    if st.session_state.logged_in:
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
# Register Page
# -------------------------------
def register_page():
    st.title("Register")
    username = st.text_input("Username")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Register"):
        res = requests.post(f"{BASE_URL}/register", json={
            "username": username,
            "email": email,
            "password": password
        })
        if res.status_code == 200:
            st.success("Registered successfully!")
            st.session_state.registered = True
            st.session_state.user = username
            set_page("Create Profile")
        else:
            st.error(res.json().get("detail", "Registration failed"))

# -------------------------------
# Create Profile Page
# -------------------------------
def create_profile_page():
    st.title("Create Profile")
    first_name = st.text_input("First Name")
    last_name = st.text_input("Last Name")
    status = st.selectbox("Working Status", ["student", "working_professional"])

    if status == "student":
        allowance = st.number_input("Monthly Allowance", min_value=0.0)
        income = {"allowance": allowance}
    else:
        salary = st.number_input("Monthly Salary", min_value=0.0)
        income = {"monthly_salary": salary}

    st.subheader("Fixed Expenses")
    fixed_expenses = []
    for i in range(3):
        name = st.text_input(f"Expense {i+1} Name", key=f"name_{i}")
        amount = st.number_input("Amount", key=f"amount_{i}", min_value=0.0)
        category = st.text_input("Category", key=f"cat_{i}")
        if name and category:
            fixed_expenses.append({"name": name, "amount": amount, "category": category})

    if st.button("Create Profile"):
        res = requests.post(f"{BASE_URL}/profile/create", json={
            "username": st.session_state.user,
            "first_name": first_name,
            "last_name": last_name,
            "working_status": status,
            "income": income,
            "fixed_expenses": fixed_expenses
        })
        if res.status_code == 200:
            st.success("Profile created!")
            st.session_state.profile_created = True
            set_page("Login")
        else:
            st.error(res.json().get("detail", "Profile creation failed"))

# -------------------------------
# Login Page
# -------------------------------
def login_page():
    st.title("Login")
    identifier = st.text_input("Username or Email")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        res = requests.post(f"{BASE_URL}/login", json={
            "identifier": identifier,
            "password": password
        })
        if res.status_code == 200:
            st.success("Login successful!")
            st.session_state.logged_in = True
            st.session_state.user = res.json()["username"]
            set_page("View Expense History")
            st.rerun()
        else:
            st.error(res.json().get("detail", "Login failed"))

# -------------------------------
# Update Profile Page (FIXED)
# -------------------------------
def update_profile_page():
    st.title("Update Profile")

    res = requests.get(f"{BASE_URL}/profile/{st.session_state.user}")
    if res.status_code != 200:
        st.error("Profile not found")
        return

    profile = res.json()

    first_name = st.text_input("First Name", value=profile["first_name"])
    last_name = st.text_input("Last Name", value=profile["last_name"])
    status = st.selectbox(
        "Working Status",
        ["student", "working_professional"],
        index=0 if profile["working_status"] == "student" else 1
    )

    if status == "student":
        allowance = st.number_input("Monthly Allowance", value=profile["income"].get("allowance", 0.0))
        income = {"allowance": allowance}
    else:
        salary = st.number_input("Monthly Salary", value=profile["income"].get("monthly_salary", 0.0))
        income = {"monthly_salary": salary}

    st.subheader("Fixed Expenses")
    fixed_expenses = []
    existing = profile.get("fixed_expenses", [])

    for i in range(3):
        data = existing[i] if i < len(existing) else {"name": "", "amount": 0.0, "category": ""}
        name = st.text_input(f"Expense {i+1} Name", value=data["name"], key=f"up_name_{i}")
        amount = st.number_input("Amount", value=data["amount"], key=f"up_amount_{i}", min_value=0.0)
        category = st.text_input("Category", value=data["category"], key=f"up_cat_{i}")
        if name and category:
            fixed_expenses.append({"name": name, "amount": amount, "category": category})

    if st.button("Update Profile"):
        res = requests.put(
            f"{BASE_URL}/profile/update/{st.session_state.user}",
            json={
                "username": st.session_state.user,
                "first_name": first_name,
                "last_name": last_name,
                "working_status": status,
                "income": income,
                "fixed_expenses": fixed_expenses
            }
        )
        if res.status_code == 200:
            st.success("Profile updated!")
        else:
            st.error(res.json().get("detail", "Update failed"))

# -------------------------------
# Add Expense Page
# -------------------------------
def add_expense_page():
    st.title("Add Expense")
    title = st.text_input("Title")
    amount = st.number_input("Amount", min_value=0.0)
    category = st.text_input("Category")

    if st.button("Add"):
        res = requests.post(
            f"{BASE_URL}/add-expense",
            json={
                "username": st.session_state.user,
                "title": title,
                "amount": amount,
                "category": category
            }
        )
        if res.status_code == 200:
            st.success("Expense added")
        else:
            st.error(res.text)

# -------------------------------
# View Expense History Page
# -------------------------------
def view_expense_history_page():
    st.title("Expense History")

    res = requests.get(f"{BASE_URL}/expense/{st.session_state.user}")
    if res.status_code != 200:
        st.error("Could not load expenses")
        return

    expenses = res.json()["expenses"]

    if not expenses:
        st.info("No expenses found yet.")
        return

    for e in expenses:
        e["type"] = "Fixed" if e["category"] == "fixed" else "Variable"
        e["month_display"] = datetime.strptime(e["month"], "%Y-%m").strftime("%b %Y")

    months = sorted(set(e["month_display"] for e in expenses), reverse=True)
    selected_month = st.selectbox("Select Month", months)

    filtered = [e for e in expenses if e["month_display"] == selected_month]
    filtered.sort(key=lambda x: x["created_at"], reverse=True)

    st.dataframe(filtered, use_container_width=True)

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
elif st.session_state.current_page == "Update Profile":
    update_profile_page()
elif st.session_state.current_page == "Add Expense":
    add_expense_page()
elif st.session_state.current_page == "View Expense History":
    view_expense_history_page()

