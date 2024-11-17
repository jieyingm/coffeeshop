import streamlit as st
import pandas as pd
import random
import io
from datetime import datetime
import sqlite3
import hashlib

# Database connection and setup
conn = sqlite3.connect('coffee_shop.db')
c = conn.cursor()

# Create tables for customers and admins if they don't exist
c.execute('''CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE,
                password TEXT,
                favorite_order TEXT
                loyalty_points INTEGER DEFAULT 0
            )''')
c.execute('''CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE,
                password TEXT
            )''')
c.execute('''CREATE TABLE IF NOT EXISTS loyalty_points_history (
                 id INTEGER PRIMARY KEY,
                 username TEXT,
                 points INTEGER,
                 description TEXT,
                 timestamp TEXT
             )''')
conn.commit()

# Function to hash passwords for security
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Sign-up function for new users
def signup(username, password, is_admin=False):
    password_hashed = hash_password(password)
    table = 'admins' if is_admin else 'customers'
    try:
        c.execute(f"INSERT INTO {table} (username, password) VALUES (?, ?)", (username, password_hashed))
        conn.commit()
        st.success(f"Account created successfully for {'admin' if is_admin else 'customer'}!")
    except sqlite3.IntegrityError:
        st.error("Username already exists.")

# Login function for existing users
def login(username, password, is_admin=False):
    password_hashed = hash_password(password)
    table = 'admins' if is_admin else 'customers'
    c.execute(f"SELECT * FROM {table} WHERE username=? AND password=?", (username, password_hashed))
    user = c.fetchone()
    return user

# Session management (added logout functionality)
def logout():
    # Clear session state to logout
    if 'user' in st.session_state:
        del st.session_state['user']
        del st.session_state['is_admin']
        st.success("You have been logged out.")
        st.rerun()  # Refresh to go back to the login page

# Streamlit UI for user authentication
# Authentication and user login/signup logic
def authenticate_user():
    if 'user' in st.session_state:
        st.write(f"Welcome back, {st.session_state['user']}!")
        # Display logout button if user is logged in
        if st.button('Logout'):
            logout()
    else:
        choice = st.sidebar.selectbox("Login/Signup", ["Login", "Sign up"])
        is_admin = st.sidebar.checkbox("Admin")

        username = st.sidebar.text_input("Username")
        password = st.sidebar.text_input("Password", type="password")

        if choice == "Sign up":
            if st.sidebar.button("Create Account"):
                signup(username, password, is_admin)
        elif choice == "Login":
            if st.sidebar.button("Login"):
                user = login(username, password, is_admin)
                if user:
                    st.session_state['user'] = username
                    st.session_state['is_admin'] = is_admin
                    st.success(f"Welcome {'Admin' if is_admin else 'Customer'} {username}!")
                    if is_admin:
                        st.rerun()  # Refresh to unlock admin features
                else:
                    st.error("Incorrect username or password.")

def get_daily_offer():
    current_day = datetime.now().strftime("%A")
    return daily_offers.get(current_day, None)

def record_loyalty_points(username, points, description):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO loyalty_points_history (username, points, description, timestamp) VALUES (?, ?, ?, ?)",
              (username, points, description, timestamp))
    conn.commit()

def add_loyalty_points(username, points):
    # Fetch current points
    c.execute("SELECT loyalty_points FROM customers WHERE username=?", (username,))
    current_points = c.fetchone()
    if current_points is None:
        current_points = 0
    else:
        current_points = current_points[0]

    # Calculate new points
    new_points = current_points + points

    # Update the loyalty points in the database
    c.execute("UPDATE customers SET loyalty_points=? WHERE username=?", (new_points, username))
    conn.commit()

    # Debugging statement to verify points are added
    # st.write(f"Debug: {points} points added for {username}. Total points: {new_points}")

    # Add an entry to the Loyalty Points History table
    description = f"Points earned from a purchase"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO loyalty_points_history (username, points, description, timestamp) VALUES (?, ?, ?, ?)",
            (username, points, description, timestamp))
    conn.commit()  # Commit the transaction

def redeem_loyalty_points(username, points_needed):
    c.execute("SELECT loyalty_points FROM customers WHERE username=?", (username,))
    current_points = c.fetchone()[0] or 0
    if current_points >= points_needed:
        new_points = current_points - points_needed
        c.execute("UPDATE customers SET loyalty_points=? WHERE username=?", (new_points, username))
        conn.commit()
        # Record the history
        record_loyalty_points(username, -points_needed, "Points redeemed for a discount")
        return True
    else:
        return False

def display_loyalty_points():
    st.markdown("<h3 style='color: #3D3D3D;'>🎁 Loyalty Points</h3>", unsafe_allow_html=True)
    username = st.session_state['user']

    # Fetch current loyalty points
    c.execute("SELECT loyalty_points FROM customers WHERE username=?", (username,))
    points = c.fetchone()[0] or 0
    st.write(f"**Current Loyalty Points:** {points}")

    # Fetch loyalty points history
    c.execute("SELECT points, description, timestamp FROM loyalty_points_history WHERE username=? ORDER BY timestamp DESC", (username,))
    history = c.fetchall()

    if history:
        st.markdown("### Loyalty Points History")
        for record in history:
            points, description, timestamp = record
            st.write(f"- **{description}**: {points} points on {timestamp}")
    else:
        st.write("No loyalty points history available.")


# Initialize Streamlit Session State to retain data across app interactions
if 'inventory' not in st.session_state:
    st.session_state.inventory = {
        "coffee_beans": 1000,  # in grams
        "milk": 1000,          # in ml
        "sugar": 1000,          # in grams
        "cups": 500
    }

if 'sales_data' not in st.session_state:
    st.session_state.sales_data = pd.DataFrame(columns=['Order Number', 'Customer Name', 'Coffee Type', 'Qantity', 'Size', 'Add-ons', 'Price', 'Time', 'Status'])

if 'order_history' not in st.session_state:
    st.session_state.order_history = {}

# Initialize order_numbers set in session state
if 'order_numbers' not in st.session_state:
    st.session_state.order_numbers = set()

# Initialize restock_history in session state
if 'restock_history' not in st.session_state:
    st.session_state.restock_history = []

# Initialize session state for coupons if not already initialized
if 'coupons' not in st.session_state:
    st.session_state.coupons = []

if 'feedback' not in st.session_state:
    st.session_state.feedback = []

# Function to generate unique 4-digit order number
def generate_unique_order_number():
    existing_numbers = st.session_state.get('order_numbers', set())  # Get existing order numbers from session state

    # Generate a unique order number
    while True:
        new_number = random.randint(1000, 9999)
        if new_number not in existing_numbers:
            st.session_state.order_numbers.add(new_number)
            return new_number

# JavaScript function to refresh the page
def js_refresh():
    st.markdown("""<script>window.location.reload()</script>""", unsafe_allow_html=True)

# Kitchen Orders Interface with box-styled layout
def display_kitchen_orders():
    st.markdown("<h3 style='color: #3D3D3D;'>👨‍🍳 Kitchen Orders</h3>", unsafe_allow_html=True)
    
    # Filter orders that are being processed (not ready yet)
    kitchen_orders = st.session_state.sales_data[st.session_state.sales_data['Status'] == 'Being Processed']
    
    if not kitchen_orders.empty:
        for idx, order in kitchen_orders.iterrows():
            st.markdown(
                f"""
                <div style='border: 1px solid #d9d9d9; border-radius: 10px; padding: 15px; margin-bottom: 10px; background-color: #f5f5f5;'>
                    <strong>Order #{order['Order Number']}</strong><br>
                    <strong>Customer:</strong> {order['Customer Name']}<br>
                    <strong>Coffee:</strong> {order['Coffee Type']} ({order['Size']})<br>
                    <strong>Add-ons:</strong> {order['Add-ons']}<br>
                    <strong>Order Time:</strong> {order['Time']}<br>
                </div>
                """, unsafe_allow_html=True
            )
            if st.button(f"Mark Order #{order['Order Number']} as Ready", key=f"ready_{order['Order Number']}"):
                # Update the order status to "Ready"
                st.session_state.sales_data.at[idx, 'Status'] = 'Ready'
            
    else:
        st.write("No active orders in the kitchen.")


# Ingredient usage per coffee type and size
ingredient_usage = {
    'Americano': {
        'small': {'coffee_beans': 9, 'milk': 10, 'sugar': 5},
        'medium': {'coffee_beans': 12, 'milk': 10, 'sugar': 5},
        'large': {'coffee_beans': 15, 'milk': 10, 'sugar': 5}
    },
    'Cappuccino': {
        'small': {'coffee_beans': 9, 'milk': 60, 'sugar': 5},
        'medium': {'coffee_beans': 12, 'milk': 80, 'sugar': 5},
        'large': {'coffee_beans': 15, 'milk': 100, 'sugar': 5}
    },
    'Latte': {
        'small': {'coffee_beans': 9, 'milk': 100, 'sugar': 5},
        'medium': {'coffee_beans': 12, 'milk': 150, 'sugar': 5},
        'large': {'coffee_beans': 15, 'milk': 200, 'sugar': 5}
    },
    'Caramel Macchiato': {
        'small': {'coffee_beans': 9, 'milk': 90, 'sugar': 5},
        'medium': {'coffee_beans': 12, 'milk': 130, 'sugar': 5},
        'large': {'coffee_beans': 15, 'milk': 180, 'sugar': 5}
    }
}

# Extra usage for additional sugar and milk
extra_usage = {
    'milk': 30,   # Extra 30ml of milk for "Extra milk"
    'sugar': 5    # Extra 5g of sugar for "Extra sugar"
}

# Coffee Menu Prices
coffee_menu = {
    'Americano': {'small': 3.75, 'medium': 5.00, 'large': 7.50},
    'Cappuccino': {'small': 5.00, 'medium': 6.50, 'large': 8.00},
    'Latte': {'small': 5.25, 'medium': 6.75, 'large': 8.25},
    'Caramel Macchiato': {'small': 4.50, 'medium': 7.00, 'large': 9.50}
}

# Prices for add-ons
add_on_prices = {
    'Extra sugar': 0.70,  # Extra 5g of sugar
    'Extra milk': 0.90,   # Extra 30ml of milk
}

# Define daily offers for each day of the week
daily_offers = {
    "Monday": {"description": "10% off on all lattes", "coffee_type": "Latte", "discount": 0.1},
    "Tuesday": {"description": "10% off on all cappuccinos", "coffee_type": "Cappuccino", "discount": 0.1},
    "Wednesday": {"description": "Buy 1 Get 1 Free on all Americanos", "coffee_type": "Americano", "discount": "bogo"},
    "Thursday": {"description": "10% off on all americano", "coffee_type": "Americano", "discount": 0.1},
    "Friday": {"description": "10% off on all Caramel Macchiatos", "coffee_type": "Caramel Macchiato", "discount": 0.1},
    "Sunday": {"description": "Double loyalty points on all purchases", "coffee_type": "all", "discount": "double_points"},
    "Saturday": {"description": "Relax and enjoy - no special offers today!", "coffee_type": "any", "discount": None}
}

# Front Page Coffee Menu Display with clean, professional formatting
# Front Page Coffee Menu Display with clean, professional, and bright formatting
def display_menu():
    st.markdown("""
        <style>
            .menu-container {
                background-color: #ffffff;
                padding: 20px;
                border-radius: 15px;
                box-shadow: 0px 4px 8px rgba(0, 0, 0, 0.1);
                margin-bottom: 40px;
            }
            .menu-title {
                color: #2C3E50;
                font-size: 28px;
                font-weight: bold;
                margin-bottom: 25px;
                text-align: center;
            }
            .menu-item-box {
                background-color: #f9f9f9;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0px 2px 5px rgba(0, 0, 0, 0.05);
                margin-bottom: 20px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .item-title {
                font-size: 22px;
                font-weight: bold;
                color: #34495E;
            }
            .item-prices {
                font-size: 18px;
                color: #3498DB;
                text-align: right;
            }
            .addon-section {
                margin-top: 30px;
                background-color: #f9f9f9;
                padding: 15px;
                border-radius: 10px;
                box-shadow: 0px 2px 5px rgba(0, 0, 0, 0.05);
            }
            .addon-title {
                font-size: 20px;
                font-weight: bold;
                color: #27AE60;
                margin-bottom: 10px;
            }
            .addon-item {
                font-size: 16px;
                color: #2C3E50;
                margin-top: 5px;
            }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("<div class='menu-title'>📋 Our Coffee Menu</div>", unsafe_allow_html=True)

    # Main menu container
    st.markdown("<div class='menu-container'>", unsafe_allow_html=True)

    # Styling each coffee item with box-style layout
    for coffee, sizes in coffee_menu.items():
        st.markdown(
            f"""
            <div class="menu-item-box">
                <div class="item-title">{coffee}</div>
                <div class="item-prices">
                    Small: RM{sizes['small']:.2f} <br>
                    Medium: RM{sizes['medium']:.2f} <br>
                    Large: RM{sizes['large']:.2f}
                </div>
            </div>
            """, unsafe_allow_html=True
        )

    st.markdown("</div>", unsafe_allow_html=True)

    # Clean Add-ons section in a box
    st.markdown(
        f"""
        <div class="addon-section">
            <div class="addon-title">Add-ons</div>
            <div class="addon-item">Extra sugar: RM{add_on_prices['Extra sugar']:.2f}</div>
            <div class="addon-item">Extra milk: RM{add_on_prices['Extra milk']:.2f}</div>
        </div>
        """, unsafe_allow_html=True
    )

    # Divider line to keep the layout neat and clean
    st.markdown("<hr style='margin-top: 30px; border: none; border-top: 2px solid #3498DB;'>", unsafe_allow_html=True)

# Define prices for restock items
restock_prices = {
    'coffee_beans': 1.20,  # RM per 100g
    'milk': 0.70,          # RM per 100ml
    'sugar': 0.20,         # RM per 100g
    'cups': 0.02           # RM per cup
}

def display_inventory():
    st.markdown("<h3 style='color: #3D3D3D;'>📦 Inventory Management</h3>", unsafe_allow_html=True)
    st.write("Here's a summary of the current inventory levels for essential items:")

    # Display current inventory in a clean, modern, and professional table
    st.markdown("### Current Stock Levels:")
    st.markdown(
        f"""
        <style>
            .inventory-table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
                font-size: 18px;
                text-align: left;
            }}
            .inventory-table th, .inventory-table td {{
                padding: 12px 15px;
                border: 1px solid #ddd;
            }}
            .inventory-table th {{
                background-color: #f4f4f4;
                font-weight: bold;
                color: #333;
            }}
            .inventory-table td {{
                background-color: #ffffff;
                color: #555;
            }}
            .inventory-table tbody tr:nth-child(even) td {{
                background-color: #f9f9f9;
            }}
        </style>

        <table class="inventory-table">
            <thead>
                <tr>
                    <th>Item</th>
                    <th>Current Quantity</th>
                    <th>Unit</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Coffee Beans</td>
                    <td>{st.session_state.inventory['coffee_beans']}</td>
                    <td>grams</td>
                </tr>
                <tr>
                    <td>Milk</td>
                    <td>{st.session_state.inventory['milk']}</td>
                    <td>milliliters</td>
                </tr>
                <tr>
                    <td>Sugar</td>
                    <td>{st.session_state.inventory['sugar']}</td>
                    <td>grams</td>
                </tr>
                <tr>
                    <td>Cups</td>
                    <td>{st.session_state.inventory['cups']}</td>
                    <td>units</td>
                </tr>
            </tbody>
        </table>
        """,
        unsafe_allow_html=True
    )


    # Display restock prices under current stock levels in a modern and clean style
    st.markdown("### 🛒 Restock Price Menu:")
    st.markdown(
        f"""
        <style>
            .restock-table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
                font-size: 18px;
                text-align: left;
            }}
            .restock-table th, .restock-table td {{
                padding: 12px 15px;
                border: 1px solid #ddd;
            }}
            .restock-table th {{
                background-color: #f4f4f4;
                font-weight: bold;
            }}
            .restock-table td {{
                background-color: #ffffff;
            }}
            .restock-table tbody tr:nth-child(even) td {{
                background-color: #f9f9f9;
            }}
        </style>

        <table class="restock-table">
            <thead>
                <tr>
                    <th>Item</th>
                    <th>Price</th>
                    <th>Unit</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Coffee Beans</td>
                    <td>RM{restock_prices['coffee_beans']:.2f}</td>
                    <td>per 100g</td>
                </tr>
                <tr>
                    <td>Milk</td>
                    <td>RM{restock_prices['milk']:.2f}</td>
                    <td>per 100ml</td>
                </tr>
                <tr>
                    <td>Sugar</td>
                    <td>RM{restock_prices['sugar']:.2f}</td>
                    <td>per 100g</td>
                </tr>
                <tr>
                    <td>Cups</td>
                    <td>RM{restock_prices['cups']:.2f}</td>
                    <td>per cup</td>
                </tr>
            </tbody>
        </table>
        """, 
        unsafe_allow_html=True
    )

    # Manual Restock Section
    st.markdown("### 🔄 Manual Restock:")
    item_to_restock = st.selectbox("Select item to restock", list(st.session_state.inventory.keys()))
    restock_amount = st.number_input("Enter restock amount", min_value=0, step=10)

    # Calculate restock cost
    cost = 0
    if item_to_restock == "coffee_beans":
        cost = (restock_amount / 100) * restock_prices['coffee_beans']
    elif item_to_restock == "milk":
        cost = (restock_amount / 100) * restock_prices['milk']
    elif item_to_restock == "sugar":
        cost = (restock_amount / 100) * restock_prices['sugar']
    elif item_to_restock == "cups":
        cost = restock_amount * restock_prices['cups']

    # Display restock cost
    if restock_amount > 0:
        st.write(f"💵 **Restock Cost:** RM{cost:.2f}")

    # Restock and update history
    if st.button("Restock", key="restock"):
        if restock_amount > 0:
            st.session_state.inventory[item_to_restock] += restock_amount
            st.success(f"Restocked **{item_to_restock}** by **{restock_amount}**. New total: **{st.session_state.inventory[item_to_restock]}**")
            st.write(f"💵 Total Restock Cost: RM{cost:.2f}")
            # Save restock history
            st.session_state.restock_history.append({
                'Item': item_to_restock,
                'Amount': restock_amount,
                'Cost': cost,
                'Time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        else:
            st.warning("Please enter a valid restock amount.")

    # Display restock history
    display_restock_history()

def display_restock_history():
    st.markdown("<h3 style='color: #3D3D3D;'>📦 Restock History</h3>", unsafe_allow_html=True)

    # Ensure there is restock history to display
    if 'restock_history' in st.session_state and st.session_state.restock_history:
        # Convert restock history to a DataFrame for table display
        df = pd.DataFrame(st.session_state.restock_history)

        # Display restock history in a table format using Streamlit's data frame display
        st.markdown("<h4 style='color: #2C3E50;'>Restock History Table</h4>", unsafe_allow_html=True)

        # Display the table with headers and professional formatting
        st.dataframe(df.style.format({"Amount": "{:.0f}", "Cost": "RM{:.2f}", "Time": "{:%Y-%m-%d %H:%M:%S}"}))
    else:
        st.write("No restock history available.")



# Function to display and download restock history in text file format (invoice)
def display_restock_history():
    st.markdown("<h3 style='color: #3D3D3D;'>📦 Restock History</h3>", unsafe_allow_html=True)

    # Ensure there is restock history to display
    if 'restock_history' in st.session_state and st.session_state.restock_history:
        # Convert restock history to a DataFrame for table display
        df = pd.DataFrame(st.session_state.restock_history)

        # Display restock history in a table format using Streamlit's data frame display
        st.write(df)

        # Generate invoice button
        if st.button("Generate Invoice"):
            generate_invoice()
    else:
        st.write("No restock history available.")




# Function to generate and download invoice as a text file
def generate_invoice():
    if 'restock_history' in st.session_state and st.session_state.restock_history:
        # Create invoice text
        invoice_text = "Coffee Shop Restock Invoice\n"
        invoice_text += f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        invoice_text += "-------------------------------------------------\n"
        invoice_text += "| Item              | Amount    | Cost (RM) | Time           |\n"
        invoice_text += "-------------------------------------------------\n"
        
        total_cost = 0
        for restock in st.session_state.restock_history:
            total_cost += restock['Cost']
            invoice_text += f"| {restock['Item']:<17} | {restock['Amount']:<8} | RM{restock['Cost']:<9.2f} | {restock['Time']:<15} |\n"

        invoice_text += "-------------------------------------------------\n"
        invoice_text += f"Total Cost: RM{total_cost:.2f}\n"

        # Create a downloadable text file
        invoice_bytes = io.BytesIO(invoice_text.encode('utf-8'))

        # Add download button
        st.download_button(
            label="Download Invoice",
            data=invoice_bytes,
            file_name=f"restock_invoice_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain"
        )
    else:
        st.write("No restock history available to generate an invoice.")

import matplotlib.pyplot as plt

# Update the sales report to include the actual final price after discount (which is the price customer pays)
def sales_report():
    st.markdown("<h3 style='color: #3D3D3D; text-align: center;'>📊 Sales Report</h3>", unsafe_allow_html=True)

    # Choose report period
    report_period = st.radio("Select Report Period:", ["Daily", "Weekly", "Monthly"], index=0, key="report_period")

    # Filter sales data based on the selected period
    if report_period == "Daily":
        filtered_data = st.session_state.sales_data[
            st.session_state.sales_data['Time'].str.contains(datetime.now().strftime("%Y-%m-%d"))]
    elif report_period == "Weekly":
        filtered_data = st.session_state.sales_data[
            pd.to_datetime(st.session_state.sales_data['Time']) >= pd.Timestamp(datetime.now()) - pd.Timedelta(days=7)]
    else:  # Monthly report
        filtered_data = st.session_state.sales_data[
            pd.to_datetime(st.session_state.sales_data['Time']).dt.to_period('M') == pd.Timestamp(datetime.now()).to_period('M')]

    # **Exclude orders with RM0.00 from revenue calculations**
    filtered_data = filtered_data[filtered_data['Price'] > 0]  # Filter out RM0.00 orders

    if not filtered_data.empty:
        # Calculate **total revenue** as the sum of **final price**, excluding coupon-discounted RM0.00 orders
        total_revenue = filtered_data['Price'].sum()  # 'Price' field should already include the discount
        st.markdown(f"<strong style='font-size:18px;'>Total Revenue:</strong> RM{total_revenue:.2f}", unsafe_allow_html=True)

        # Coffee sales breakdown
        coffee_sales = filtered_data.groupby('Coffee Type')['Quantity'].sum().reset_index()
        st.markdown("### Coffee Sales by Type")
        st.bar_chart(coffee_sales.set_index('Coffee Type'))

        # Best-selling and least popular coffee types
        best_selling = coffee_sales.loc[coffee_sales['Quantity'].idxmax()]['Coffee Type']
        least_popular = coffee_sales.loc[coffee_sales['Quantity'].idxmin()]['Coffee Type']
        st.write(f"**Best-selling Coffee Type:** {best_selling}", unsafe_allow_html=False)
        st.write(f"**Least Popular Coffee Type:** {least_popular}", unsafe_allow_html=False)

        # Coffee sales distribution pie chart
        st.markdown("<h4 style='text-align: center;'>Coffee Sales Distribution</h4>", unsafe_allow_html=True)
        fig1, ax1 = plt.subplots()
        ax1.pie(coffee_sales['Quantity'], labels=coffee_sales['Coffee Type'], autopct='%1.1f%%', startangle=90, colors=['#FF9999', '#66B3FF', '#99FF99', '#FFD700'])
        ax1.axis('equal')
        st.pyplot(fig1)

        # Ingredient usage calculation based on sales
        total_beans_used = 0
        total_milk_used = 0
        total_sugar_used = 0
        total_cups_used = filtered_data['Quantity'].sum()

        for idx, order in filtered_data.iterrows():
            size = order['Size']
            coffee_type = order['Coffee Type']

            # Calculate base ingredient usage for each order
            beans_used = ingredient_usage[coffee_type][size]['coffee_beans'] * order['Quantity']
            milk_used = ingredient_usage[coffee_type][size]['milk'] * order['Quantity']
            sugar_used = ingredient_usage[coffee_type][size]['sugar'] * order['Quantity']

            total_beans_used += beans_used
            total_milk_used += milk_used
            total_sugar_used += sugar_used

            # Add extra ingredient usage for add-ons
            if 'Extra sugar' in order['Add-ons']:
                total_sugar_used += extra_usage['sugar'] * order['Quantity']
            if 'Extra milk' in order['Add-ons']:
                total_milk_used += extra_usage['milk'] * order['Quantity']

        # **Calculate inventory costs based on initial inventory and restocking costs**
        initial_inventory_value = (
            (st.session_state.inventory['coffee_beans'] / 100) * restock_prices['coffee_beans'] +
            (st.session_state.inventory['milk'] / 100) * restock_prices['milk'] +
            (st.session_state.inventory['sugar'] / 100) * restock_prices['sugar'] +
            st.session_state.inventory['cups'] * restock_prices['cups']
        )

        # **Calculate the restocking cost**
        total_restock_cost = 0
        if 'restock_history' in st.session_state and st.session_state.restock_history:
            total_restock_cost = sum(restock['Cost'] for restock in st.session_state.restock_history)

        # The total inventory cost is the sum of the initial inventory value and restocking cost
        total_inventory_cost = initial_inventory_value + total_restock_cost

        # Calculate **total profit** by subtracting inventory cost from actual final revenue
        total_profit = total_revenue - total_inventory_cost

        # Ingredient usage summary
        ingredient_usage_summary = {
            'Ingredient': ['Coffee Beans (g)', 'Milk (ml)', 'Sugar (g)', 'Cups'],
            'Amount Used': [total_beans_used, total_milk_used, total_sugar_used, total_cups_used],
            '% Used': [
                (total_beans_used / (total_beans_used + st.session_state.inventory['coffee_beans'])) * 100 if st.session_state.inventory['coffee_beans'] > 0 else 0,
                (total_milk_used / (total_milk_used + st.session_state.inventory['milk'])) * 100 if st.session_state.inventory['milk'] > 0 else 0,
                (total_sugar_used / (total_sugar_used + st.session_state.inventory['sugar'])) * 100 if st.session_state.inventory['sugar'] > 0 else 0,
                (total_cups_used / (total_cups_used + st.session_state.inventory['cups'])) * 100 if st.session_state.inventory['cups'] > 0 else 0
            ]
        }
        ingredient_df = pd.DataFrame(ingredient_usage_summary)
        st.markdown("<h4 style='text-align: center;'>Ingredient Usage Summary</h4>", unsafe_allow_html=True)
        st.write(ingredient_df)

        # Stacked bar chart for Total Revenue, Inventory Cost, and Profit
        st.markdown("<h4 style='text-align: center;'>Revenue, Inventory Cost, and Profit Breakdown</h4>", unsafe_allow_html=True)
        fig, ax = plt.subplots()
        categories = ['Total Revenue', 'Inventory Cost', 'Profit']
        values = [total_revenue, total_inventory_cost, total_profit]

        ax.bar(categories, [total_revenue, 0, 0], label='Total Revenue', color='#66B3FF')
        ax.bar(categories, [0, total_inventory_cost, 0], label='Inventory Cost', color='#FF9999')
        ax.bar(categories, [0, 0, total_profit], label='Profit', color='#99FF99')

        ax.set_ylabel('Amount (RM)')
        ax.set_title('Financial Overview')
        ax.legend()
        st.pyplot(fig)

        # **Display total inventory cost and profit at the end**
        st.markdown(f"<strong style='font-size:18px;'>Total Inventory Cost (Including Restocking):</strong> RM{total_inventory_cost:.2f}", unsafe_allow_html=True)
        st.markdown(f"<strong style='font-size:18px;'>Total Profit:</strong> RM{total_profit:.2f}", unsafe_allow_html=True)

    else:
        st.write("No sales data available for the selected period.")




# Order History Section
def display_order_history():
    st.markdown("<h3 style='color: #3D3D3D;'>📜 Order History</h3>", unsafe_allow_html=True)

    if not st.session_state.sales_data.empty:
        # Display order history
        st.dataframe(st.session_state.sales_data[['Order Number', 'Customer Name', 'Coffee Type', 'Size', 'Add-ons', 'Price', 'Time']])

        # Show total price for all orders in the history
        total_price = st.session_state.sales_data['Price'].sum()
        st.markdown(f"<strong style='font-size:18px;'>Total Price of All Orders:</strong> RM{total_price:.2f}", unsafe_allow_html=True)
    else:
        st.write("No orders have been placed yet.")


# Customer Feedback Form
def feedback_form():
    st.markdown("<h3 style='color: #3D3D3D;'>💬 Submit Your Feedback</h3>", unsafe_allow_html=True)

    name = st.text_input("Name")
    coffee_purchased = st.selectbox("Select Coffee Purchased", list(coffee_menu.keys()))
    coffee_rating = st.slider("Rate the Coffee (1-5)", 1, 5, 3)
    service_rating = st.slider("Rate the Service (1-5)", 1, 5, 3)
    additional_feedback = st.text_area("Any additional comments?")

    if st.button("Submit Feedback"):
        # Add feedback to session state
        if 'feedback' not in st.session_state:
            st.session_state.feedback = []

        # Get the current time of submission
        feedback_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Save the feedback as a dictionary
        new_feedback = {
            'Name': name,
            'Coffee Purchased': coffee_purchased,
            'Coffee Rating': coffee_rating,
            'Service Rating': service_rating,
            'Additional Feedback': additional_feedback,
            'Time': feedback_time
        }

        # Append to feedback list in session state
        st.session_state.feedback.append(new_feedback)
        st.success("Thank you for your feedback!")



# Analytics Dashboard with Restocking Warning and Inventory Level Display
def analytics_dashboard():
    st.markdown("<h3 style='color: #3D3D3D;'>📈 Analytics Dashboard</h3>", unsafe_allow_html=True)
    st.write("Real-time stats on orders, inventory, and sales.")

    # Display the order count and total revenue with proper spacing
    st.metric(label="Total Orders", value=len(st.session_state.sales_data))
    total_revenue = st.session_state.sales_data['Price'].sum()
    st.metric(label="Total Revenue", value=f"RM{total_revenue:.2f}")

    # Add spacing before displaying inventory levels
    st.markdown("<h4 style='color: #333; margin-top: 20px;'>📦 Current Inventory Levels</h4>", unsafe_allow_html=True)

    # Show current inventory levels in box format with proper spacing
    st.markdown(
        """
        <div style='display: flex; flex-wrap: wrap; gap: 20px; margin-bottom: 20px;'>
            <div style='flex: 1; border: 1px solid #d9d9d9; border-radius: 10px; padding: 20px; background-color: #f9f9f9;'>
                <strong>Coffee Beans:</strong> {0} g
            </div>
            <div style='flex: 1; border: 1px solid #d9d9d9; border-radius: 10px; padding: 20px; background-color: #f9f9f9;'>
                <strong>Milk:</strong> {1} ml
            </div>
            <div style='flex: 1; border: 1px solid #d9d9d9; border-radius: 10px; padding: 20px; background-color: #f9f9f9;'>
                <strong>Sugar:</strong> {2} g
            </div>
            <div style='flex: 1; border: 1px solid #d9d9d9; border-radius: 10px; padding: 20px; background-color: #f9f9f9;'>
                <strong>Cups:</strong> {3} units
            </div>
        </div>
        """.format(
            st.session_state.inventory['coffee_beans'],
            st.session_state.inventory['milk'],
            st.session_state.inventory['sugar'],
            st.session_state.inventory['cups']
        ), 
        unsafe_allow_html=True
    )

    # Estimate how many cups can be made with the current inventory
    average_beans_per_cup = 12  # g
    average_milk_per_cup = 80   # ml
    average_sugar_per_cup = 5   # g

    max_cups_beans = st.session_state.inventory['coffee_beans'] // average_beans_per_cup
    max_cups_milk = st.session_state.inventory['milk'] // average_milk_per_cup
    max_cups_sugar = st.session_state.inventory['sugar'] // average_sugar_per_cup
    max_cups = min(max_cups_beans, max_cups_milk, max_cups_sugar, st.session_state.inventory['cups'])

    st.markdown(f"<h4 style='margin-top: 20px;'>☕ Estimated Cups You Can Make: {max_cups} cups</h4>", unsafe_allow_html=True)
    st.write(f"- Based on current inventory, you can make approximately **{max_cups}** more cups of coffee.")

    # Inventory Health with restocking warnings with proper spacing
    st.markdown("<h4 style='color: #FF4136; margin-top: 30px;'>⚠️ Inventory Health Alerts</h4>", unsafe_allow_html=True)

    low_stock_items = []

    # Check specific thresholds for coffee_beans, milk, sugar, and cups
    if st.session_state.inventory['coffee_beans'] < 200:
        low_stock_items.append(("Coffee Beans", st.session_state.inventory['coffee_beans'], 'g'))
    if st.session_state.inventory['milk'] < 200:
        low_stock_items.append(("Milk", st.session_state.inventory['milk'], 'ml'))
    if st.session_state.inventory['sugar'] < 200:
        low_stock_items.append(("Sugar", st.session_state.inventory['sugar'], 'g'))
    if st.session_state.inventory['cups'] < 20:
        low_stock_items.append(("Cups", st.session_state.inventory['cups'], 'units'))

    # Show warnings for low stock items with units displayed and spaced out
    if low_stock_items:
        for item, quantity, unit in low_stock_items:
            st.markdown(
                f"""
                <div style='border: 1px solid #FF4136; border-radius: 10px; padding: 20px; margin-bottom: 20px; background-color: #ffe6e6;'>
                    <strong style="color: #FF4136;">{item} is low on stock!</strong><br>
                    <span>Current Quantity: <strong>{quantity} {unit}</strong></span>
                </div>
                """, unsafe_allow_html=True
            )
    else:
        st.success("✔️ All inventory levels are sufficient.")


# Customer-facing section (Coffee Menu, Order Coffee, and Feedback)
def customer_interface():
    st.sidebar.title("Customer Menu")
    selection = st.sidebar.radio("Choose a page:", ["Coffee Menu", "Order Coffee", "Order Status Dashboard", "Feedback", "Loyalty Points"])

    if selection == "Coffee Menu":
        display_menu()
    elif selection == "Order Coffee":
        take_order()
    elif selection == "Order Status Dashboard":
        display_order_status()
    elif selection == "Feedback":
        feedback_form()
    elif selection == "Loyalty Points":
        display_loyalty_points()


# Display order status for customers with a box-styled layout for each order and the pickup button
def display_order_status():
    st.markdown("<h3 style='color: #3D3D3D;'>📊 Order Status Dashboard</h3>", unsafe_allow_html=True)
    
    # Display orders that are being processed
    processing_orders = st.session_state.sales_data[st.session_state.sales_data['Status'] == 'Being Processed']
    ready_orders = st.session_state.sales_data[st.session_state.sales_data['Status'] == 'Ready']

    # Orders being processed
    st.subheader("Orders Being Processed")
    if not processing_orders.empty:
        st.write(processing_orders[['Order Number', 'Customer Name', 'Time']])
    else:
        st.write("No orders are being processed.")

    # Orders ready for pickup with formatted boxes
    st.subheader("Orders Ready for Pickup")
    if not ready_orders.empty:
        for idx, order in ready_orders.iterrows():
            st.markdown(
                f"""
                <div style='border: 1px solid #d9d9d9; border-radius: 10px; padding: 15px; margin-bottom: 10px; background-color: #f9f9f9;'>
                    <strong>Order #{order['Order Number']}</strong><br>
                    <strong>Customer:</strong> {order['Customer Name']}<br>
                    <strong>Coffee:</strong> {order['Coffee Type']} ({order['Size']})<br>
                    <strong>Add-ons:</strong> {order['Add-ons']}<br>
                    <strong>Order Time:</strong> {order['Time']}<br>
                </div>
                """, unsafe_allow_html=True
            )
            if st.button(f"Picked Up #{order['Order Number']}", key=f"pickup_{order['Order Number']}"):
                # Remove the order from the sales data by updating the status
                st.session_state.sales_data.drop(idx, inplace=True)
                st.success(f"Order #{order['Order Number']} has been picked up!")
    else:
        st.write("No orders are ready for pickup.")

# Function to manage coupon codes in the admin interface
def manage_coupons():
    st.markdown("<h3 style='color: #3D3D3D;'>💳 Manage Coupon Codes</h3>", unsafe_allow_html=True)

    # Create a new coupon
    coupon_code = st.text_input("Enter Coupon Code")
    discount_amount = st.number_input("Discount Amount (in RM)", min_value=0.0, format="%.2f")
    expiration_date = st.date_input("Expiration Date")

    if st.button("Create Coupon"):
        if coupon_code and discount_amount > 0:
            new_coupon = {
                'Code': coupon_code,
                'Discount': discount_amount,
                'Expiration Date': expiration_date
            }
            st.session_state.coupons.append(new_coupon)
            st.success(f"Coupon '{coupon_code}' created successfully!")
        else:
            st.error("Please enter a valid coupon code and discount amount.")

    # Display existing coupons
    if st.session_state.coupons:
        st.markdown("<h4>Existing Coupons</h4>", unsafe_allow_html=True)
        for coupon in st.session_state.coupons:
            st.markdown(f"- **{coupon['Code']}**: RM{coupon['Discount']} (Expires on {coupon['Expiration Date']})")
    else:
        st.write("No coupons available.")
        
# Taking Order
def take_order():
    st.markdown("<h3 style='color: #3D3D3D;'>📋 Place Your Coffee Order</h3>", unsafe_allow_html=True)

    customer_name = st.text_input("Enter your name:")

    if customer_name:
        # Initialize order list in session state if not already done
        if 'order_list' not in st.session_state:
            st.session_state.order_list = []

        # Get the daily offer
        daily_offer = get_daily_offer()
        if daily_offer and daily_offer["discount"] is not None:
            st.markdown("<h4 style='color: #3D3D3D;'>🌟 Today's Offer</h4>", unsafe_allow_html=True)
            st.write(f"**{daily_offer['description']}**")

        # Coffee selection
        coffee_type = st.selectbox("Select Coffee", list(coffee_menu.keys()), key="coffee_select")

        if coffee_type:
            # Show sizes with the price difference in a radio button
            size_options = {
                'small': f"Small (RM{coffee_menu[coffee_type]['small']:.2f})",
                'medium': f"Medium (+RM{coffee_menu[coffee_type]['medium'] - coffee_menu[coffee_type]['small']:.2f})",
                'large': f"Large (+RM{coffee_menu[coffee_type]['large'] - coffee_menu[coffee_type]['small']:.2f})"
            }
            size = st.radio(f"Select size for {coffee_type}", list(size_options.keys()), format_func=lambda x: size_options[x])

            # Add-ons selection with displayed prices
            add_ons = st.multiselect(
                f"Add-ons for {coffee_type} (Extra sugar RM{add_on_prices['Extra sugar']}, Extra milk RM{add_on_prices['Extra milk']})",
                ['Extra sugar', 'Extra milk'], key=f"addons_{coffee_type}"
            )

            # Quantity selection
            quantity = st.number_input("Select quantity", min_value=1, max_value=10, value=1, step=1)

            # Calculate the base price
            base_price = coffee_menu[coffee_type][size]
            add_on_price = sum(add_on_prices[add_on] for add_on in add_ons)
            total_item_price = (base_price + add_on_price) * quantity

            # Apply the daily offer
            double_points = False  # Initialize double points flag
            if daily_offer:
                if daily_offer["discount"] == "bogo" and coffee_type == daily_offer["coffee_type"]:
                    # Apply "Buy 1 Get 1 Free" (BOGO)
                    total_item_price /= 2
                elif isinstance(daily_offer["discount"], float) and coffee_type == daily_offer["coffee_type"]:
                    # Apply percentage discount
                    total_item_price *= (1 - daily_offer["discount"])
                elif daily_offer["discount"] == "double_points":
                    double_points = True

            # Add item to the order list
            if st.button("Add to Order"):
                
                # Add the item to the order list
                order_item = {
                    'coffee_type': coffee_type,
                    'size': size,
                    'add_ons': add_ons,
                    'quantity': quantity,
                    'price': total_item_price
                }
                st.session_state.order_list.append(order_item)
                st.success(f"Added {quantity} x {coffee_type} to your order.")

        # Display the current order summary
        if st.session_state.order_list:
            st.markdown("<h4 style='color: #3D3D3D;'>🛒 Order Summary</h4>", unsafe_allow_html=True)
            total_order_price = 0

            for item in st.session_state.order_list:
                st.write(f"{item['quantity']} x {item['coffee_type']} ({item['size']}): RM{item['price']:.2f}")
                if item['add_ons']:
                    st.write(f" - Add-ons: {', '.join(item['add_ons'])}")
                total_order_price += item['price']

            st.write(f"**Total Order Price:** RM{total_order_price:.2f}")

            # Coupon code input
            coupon_code = st.text_input("Enter Coupon Code (optional):")
            discount = 0  # Default discount value

            # Check if the customer wants to redeem points
            c.execute("SELECT loyalty_points FROM customers WHERE username=?", (customer_name,))
            result = c.fetchone()
            points = result[0] if result else 0

            # Input field for redeeming points
            redeem_points = st.number_input(
                f"You have {points} points. Enter how many points to redeem (10 points = RM1):", 
                min_value=0, max_value=points, step=10
            )

            # Calculate the discount based on the redeem_points input (10 points = RM1)
            discount = (redeem_points // 10) * 1  # Integer division to calculate RM1 for every 10 points


            # Automatically apply coupon when entered
            if coupon_code:
                coupon_found = False
                for coupon in st.session_state.coupons:
                    if coupon['Code'] == coupon_code:
                        if datetime.strptime(coupon['Expiration Date'].strftime('%Y-%m-%d'), '%Y-%m-%d') >= datetime.now():
                            discount = coupon['Discount']
                            st.success(f"RM{discount:.2f} discount applied!")  # Show success message for coupon application
                            coupon_found = True
                            break

                if not coupon_found:
                    st.error("Invalid coupon or coupon has expired.")

            # Calculate final price after applying coupon
            final_price = total_order_price - discount
            if final_price < 0:
                final_price = 0.00  # Ensure total price does not go below RM0.00

            # Live total display
            st.markdown("<h4 style='color: #3D3D3D;'>Live Total:</h4>", unsafe_allow_html=True)
            st.write(f"**Total Price:** RM{final_price:.2f}")

            # Calculate preparation time based on size and add-ons
            base_prep_time = 0
            if size == 'small':
                base_prep_time = 2 * 60  # 2 minutes in seconds
            elif size == 'medium':
                base_prep_time = 3 * 60  # 3 minutes in seconds
            elif size == 'large':
                base_prep_time = 5 * 60  # 5 minutes in seconds

            # Add time for each add-on (30 seconds per add-on)
            total_prep_time = base_prep_time + (len(add_ons) * 30)  # in seconds

            # Calculate waiting time based on orders ahead
            orders_ahead = len(st.session_state.sales_data[st.session_state.sales_data['Status'] == 'Being Processed'])
            total_waiting_time = 0

            # Sum the preparation time for each order ahead in the queue
            for idx, order in st.session_state.sales_data[st.session_state.sales_data['Status'] == 'Being Processed'].iterrows():
                order_size = order['Size']
                order_add_ons = order['Add-ons'].split(", ")

                # Calculate preparation time for each order ahead
                if order_size == 'small':
                    prep_time = 2 * 60
                elif order_size == 'medium':
                    prep_time = 3 * 60
                elif order_size == 'large':
                    prep_time = 5 * 60

                prep_time += len(order_add_ons) * 30  # Add time for add-ons
                total_waiting_time += prep_time

            # Calculate estimated waiting time (in minutes and seconds)
            estimated_total_waiting_time = total_waiting_time + total_prep_time
            minutes, seconds = divmod(estimated_total_waiting_time, 60)

            # Payment Method Section
            st.markdown("<h4 style='color: #3D3D3D;'>Secure Payment</h4>", unsafe_allow_html=True)
            payment_method = st.radio("Select Payment Method", ["Credit Card", "Debit Card", "Cash"])

            # Payment form (for simulation purpose)
            valid_payment = False  # Flag to check if payment is valid

            # Inside the payment section
            if payment_method in ["Credit Card", "Debit Card"]:
                card_number = st.text_input("Card Number", max_chars=16, type="password")
                cardholder_name = st.text_input("Cardholder Name")
                expiry_date = st.text_input("Expiry Date (MM/YY)", max_chars=5)
                cvv = st.text_input("CVV", max_chars=3, type="password")

                # Split the expiry date into month and year
                if expiry_date:
                    try:
                        exp_month, exp_year = expiry_date.split("/")
                        exp_month = int(exp_month)
                        exp_year = int("20" + exp_year)  # Assuming YY is 20YY format

                        # Get current month and year
                        current_month = datetime.now().month
                        current_year = datetime.now().year

                        # Check if the expiry date is valid (i.e., not in the past)
                        if (exp_year < current_year) or (exp_year == current_year and exp_month < current_month):
                            st.error("Card expiry date is invalid or expired!")
                            valid_payment = False
                        elif len(card_number) == 16 and len(cvv) == 3:
                            valid_payment = True
                        else:
                            st.error("Invalid card details! Please check your card number and CVV.")
                            valid_payment = False
                    except ValueError:
                        st.error("Invalid expiry date format! Please enter in MM/YY format.")
                        valid_payment = False
                else:
                    st.error("Please enter the expiry date.")
                    valid_payment = False

            else:
                st.write("Pay with cash upon pickup.")
                valid_payment = True  # No validation needed for cash


            # Confirm order button and inventory check
            if st.button("Confirm Order and Pay", key="confirm_order"):
                if valid_payment:
                    if check_inventory(coffee_type, size, 1, add_ons):
                        order_number = generate_unique_order_number()
                        order_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                        # Deduct points only if the user chose to redeem them and payment is successful
                        if redeem_points > 0:
                            redeem_success = redeem_loyalty_points(customer_name, redeem_points)
                            if redeem_success:
                                st.success(f"{redeem_points} loyalty points redeemed successfully!")
                            else:
                                st.warning("Failed to redeem points. Please check your balance.")

                        # Award points based on the final price (1 point for every RM10 spent)
                        points_earned = int(final_price)  # Integer division to award 1 point for every RM1
                        if double_points == True:
                            points_earned = points_earned*2
                            
                        if points_earned > 0:
                            add_loyalty_points(customer_name, points_earned)
                            st.success(f"You earned {points_earned} loyalty points for this order!")

                        # Save each item in the order to the database
                        for item in st.session_state.order_list:
                            new_order = {
                                'Order Number': order_number,
                                'Customer Name': customer_name,
                                'Coffee Type': item['coffee_type'],
                                'Quantity': item['quantity'],
                                'Size': item['size'],
                                'Add-ons': ', '.join(item['add_ons']),
                                'Price': item['price'],
                                'Time': order_time,
                                'Status': 'Being Processed'
                            }
                            st.session_state.sales_data = pd.concat([st.session_state.sales_data, pd.DataFrame([new_order])], ignore_index=True)

                        # Update inventory based on the order
                        update_inventory(coffee_type, size, 1, add_ons)

                        # Show success message with the order number
                        st.success(f"Order placed successfully with Order Number: {order_number}!")

                        # Display the estimated waiting time after confirming the order
                        st.markdown(f"**Your estimated waiting time is:** {minutes} minutes and {seconds} seconds.")
                        
                        # Simulate payment processing
                        st.success(f"Payment of RM{final_price:.2f} received successfully.")
                        # Generate and download invoice
                        generate_invoice(order_number, customer_name, coffee_type, size, add_ons, final_price, order_time)

                        # Clear the order list after successful order placement
                        st.session_state.order_list = []
                    else:
                        st.error("Sorry, your order cannot be placed due to insufficient inventory!")
                else:
                    st.error("Payment could not be processed due to invalid payment details. Please try again.")

                # Clear the order list after successful order placement
                st.session_state.order_list = []
    else:
        st.warning("Please enter your name to proceed.")


# Function to generate and download an invoice as a text file
def generate_invoice(order_number, customer_name, coffee_type, size, add_ons, final_price, order_time):
    invoice_text = f"""
    ==========================
    ☕ Coffee Shop Invoice ☕
    ==========================
    Order Number: {order_number}
    Customer Name: {customer_name}
    Coffee Type: {coffee_type}
    Size: {size.capitalize()}
    Add-ons: {', '.join(add_ons) if add_ons else 'None'}
    Total Price: RM{final_price:.2f}
    Order Time: {order_time}
    ==========================
    Thank you for your purchase!
    """

    # Create a downloadable text file
    invoice_bytes = io.BytesIO(invoice_text.encode('utf-8'))

    # Add download button
    st.download_button(
        label="Download Invoice",
        data=invoice_bytes,
        file_name=f"invoice_{order_number}.txt",
        mime="text/plain"
    )





# Check Inventory Based on Coffee Type, Size, and Quantity
def check_inventory(coffee_type, size, quantity, add_ons):
    ingredients = ingredient_usage[coffee_type][size]

    if st.session_state.inventory['coffee_beans'] < ingredients['coffee_beans'] * quantity:
        st.error(f"Sorry, {coffee_type} ({size}) is currently out of stock due to insufficient coffee beans.")
        return False
    if st.session_state.inventory['milk'] < (ingredients['milk'] * quantity + (extra_usage['milk'] * quantity if 'Extra milk' in add_ons else 0)):
        st.error(f"Sorry, {coffee_type} ({size}) is currently out of stock due to insufficient milk.")
        return False
    if st.session_state.inventory['sugar'] < (ingredients['sugar'] * quantity + (extra_usage['sugar'] * quantity if 'Extra sugar' in add_ons else 0)):
        st.error(f"Sorry, {coffee_type} ({size}) is currently out of stock due to insufficient sugar.")
        return False
    if st.session_state.inventory['cups'] < quantity:
        st.error(f"Sorry, we are out of cups to serve {coffee_type} ({size}).")
        return False
    return True

# Update Inventory After Successful Order
def update_inventory(coffee_type, size, quantity, add_ons):
    ingredients = ingredient_usage[coffee_type][size]
    
    st.session_state.inventory['coffee_beans'] -= ingredients['coffee_beans'] * quantity
    st.session_state.inventory['milk'] -= ingredients['milk'] * quantity
    if 'Extra milk' in add_ons:
        st.session_state.inventory['milk'] -= extra_usage['milk'] * quantity  # Deduct extra milk
    if 'Extra sugar' in add_ons:
        st.session_state.inventory['sugar'] -= (ingredients['sugar'] * quantity + extra_usage['sugar'] * quantity)  # Deduct extra sugar
    else:
        st.session_state.inventory['sugar'] -= ingredients['sugar'] * quantity  # Deduct regular sugar
    st.session_state.inventory['cups'] -= quantity
    st.write("📊 Inventory updated.")

if 'feedback' not in st.session_state:
    st.session_state.feedback = []

# Function to display customer feedback in the admin section
def display_feedback():
    st.markdown("<h3 style='color: #3D3D3D;'>📋 Customer Feedback</h3>", unsafe_allow_html=True)

    feedback_list = st.session_state.feedback

    if feedback_list:
        for fb in feedback_list:
            # Safeguard by checking if the 'Coffee Purchased' key exists
            coffee_purchased = fb.get('Coffee Purchased', 'Not Specified')
            coffee_rating = fb.get('Coffee Rating', 0)
            service_rating = fb.get('Service Rating', 0)
            additional_feedback = fb.get('Additional Feedback', 'No additional feedback')
            
            st.markdown(
                f"""
                <div style='border: 1px solid #d9d9d9; border-radius: 10px; padding: 15px; margin-bottom: 15px; background-color: #f9f9f9;'>
                    <h4 style='color: #333;'>Customer Name: {fb['Name']}</h4>
                    <p><strong>Coffee Purchased:</strong> {coffee_purchased}</p>
                    <p><strong>Coffee Rating:</strong> {'⭐' * coffee_rating} ({coffee_rating}/5)</p>
                    <p><strong>Service Rating:</strong> {'⭐' * service_rating} ({service_rating}/5)</p>
                    <p><strong>Comments:</strong> <span style='color: #666;'>{additional_feedback}</span></p>
                    <p style='color: #999; font-size: 0.85em;'>Submitted on {fb['Time']}</p>
                </div>
                """, unsafe_allow_html=True
            )
    else:
        st.write("No feedback available.")



# Admin Section
def admin_interface():
    st.sidebar.title("Administration")
    # Adding 'Order History' to the admin page selection
    selection = st.sidebar.radio("Choose a page:", ["Inventory Management", "Sales Report", "Analytics Dashboard", "Feedback", "Kitchen Orders", "Manage Coupons", "Order History"])

    if selection == "Inventory Management":
        display_inventory()
    elif selection == "Sales Report":
        sales_report()
    elif selection == "Analytics Dashboard":
        analytics_dashboard()
    elif selection == "Feedback":
        display_feedback()  # Admin can view feedback here
    elif selection == "Kitchen Orders":
        display_kitchen_orders()
    elif selection == "Manage Coupons":
        manage_coupons()
    elif selection == "Order History":  # New section for Order History
        display_order_history()


# Main content function
def main_content():
    if 'user' in st.session_state:
        if st.session_state.get('is_admin'):
            st.subheader("Admin Dashboard")
            admin_interface()  # Show admin features
        else:
            st.subheader("Customer Dashboard")
            customer_interface()  # Show customer features
    else:
        st.write("Please log in or sign up to access the app.")

# Call the authentication and main content functions
if __name__ == "__main__":
    authenticate_user()
    main_content()


