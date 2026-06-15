from flask import Flask, request, redirect, url_for, render_template_string, g, Response
import sqlite3
import datetime
import csv
import io

app = Flask(__name__)
DATABASE = "repair_shop.db"

# =====================================================
# Database helpers
# =====================================================

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

# =====================================================
# DB Schema
# =====================================================

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT,
        email TEXT
    );

    CREATE TABLE IF NOT EXISTS devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER,
        type TEXT,
        brand TEXT,
        model TEXT,
        serial TEXT,
        os TEXT,
        storage TEXT,
        ram TEXT,
        status TEXT,
        condition TEXT,
        purchase_source TEXT,
        listed_online INTEGER DEFAULT 0,
        FOREIGN KEY(customer_id) REFERENCES customers(id)
    );

    CREATE TABLE IF NOT EXISTS parts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        sku TEXT,
        quantity INTEGER,
        cost REAL,
        price REAL
    );

    CREATE TABLE IF NOT EXISTS repairs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER,
        issue TEXT,
        status TEXT,
        created_at TEXT,
        FOREIGN KEY(device_id) REFERENCES devices(id)
    );

    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER,
        device_id INTEGER,
        quantity INTEGER DEFAULT 1,
        unit_price REAL,
        total REAL,
        channel TEXT,
        listing_url TEXT,
        bulk_order INTEGER DEFAULT 0,
        created_at TEXT,
        FOREIGN KEY(customer_id) REFERENCES customers(id),
        FOREIGN KEY(device_id) REFERENCES devices(id)
    );

    CREATE TABLE IF NOT EXISTS bulk_purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier TEXT,
        quantity INTEGER,
        unit_cost REAL,
        total_cost REAL,
        received_date TEXT,
        status TEXT
    );

    CREATE TABLE IF NOT EXISTS listings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER,
        platform TEXT,
        listing_price REAL,
        listing_url TEXT,
        status TEXT,
        listed_at TEXT,
        FOREIGN KEY(device_id) REFERENCES devices(id)
    );

    CREATE TABLE IF NOT EXISTS shipments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        carrier TEXT,
        tracking TEXT,
        status TEXT,
        expected_date TEXT
    );

    CREATE TABLE IF NOT EXISTS technicians (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT,
        email TEXT,
        role TEXT
    );

    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER,
        device_id INTEGER,
        scheduled_date TEXT,
        appointment_type TEXT,
        status TEXT,
        notes TEXT,
        FOREIGN KEY(customer_id) REFERENCES customers(id),
        FOREIGN KEY(device_id) REFERENCES devices(id)
    );

    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT,
        amount REAL,
        vendor TEXT,
        date TEXT,
        notes TEXT
    );

    CREATE TABLE IF NOT EXISTS quotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER,
        device_id INTEGER,
        estimate REAL,
        status TEXT,
        created_at TEXT,
        notes TEXT,
        FOREIGN KEY(customer_id) REFERENCES customers(id),
        FOREIGN KEY(device_id) REFERENCES devices(id)
    );
    """)
    db.commit()

# =====================================================
# Helpers

def get_carrier_eta(carrier_name):
    carrier = (carrier_name or "").strip().lower()
    today = datetime.datetime.now()
    if "fedex" in carrier:
        delta = datetime.timedelta(days=2)
        status = "In transit"
    elif "ups" in carrier:
        delta = datetime.timedelta(days=3)
        status = "In transit"
    elif "usps" in carrier or "postal" in carrier:
        delta = datetime.timedelta(days=4)
        status = "In transit"
    elif "dhl" in carrier:
        delta = datetime.timedelta(days=2)
        status = "In transit"
    else:
        delta = datetime.timedelta(days=5)
        status = "Pending pickup"
    return (today + delta).date().isoformat(), status

# =====================================================
# Base layout
# =====================================================

BASE = """
<!doctype html>
<title>Repair Shop</title>
<style>
:root {
  --bg: radial-gradient(circle at top, #1b2140 0%, #0b0f1a 55%);
  --panel: rgba(22,26,34,0.92);
  --panel-2: rgba(28,34,48,0.95);
  --accent: #4da3ff;
  --accent-2: #7cffc4;
  --text: #e6e9ef;
  --muted: #9aa4b2;
  --border: rgba(255,255,255,0.08);
}
body {
  margin: 0;
  min-height: 100vh;
  font-family: system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell;
  background: var(--bg);
  color: var(--text);
}
nav {
  backdrop-filter: blur(10px);
  background: rgba(15,17,30,0.85);
  padding: 14px 18px;
  display: flex;
  gap: 16px;
  border-bottom: 1px solid var(--border);
}
nav a {
  color: var(--muted);
  text-decoration: none;
  font-weight: 600;
}
nav a:hover { color: var(--accent); }
.container { padding: 22px; }
h2 { margin-top: 0; letter-spacing: .3px; }
form {
  background: var(--panel);
  padding: 16px;
  border-radius: 14px;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  box-shadow: 0 10px 30px rgba(0,0,0,.35);
}
input, select, textarea {
  background: var(--panel-2);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 12px;
}
button {
  background: linear-gradient(135deg, var(--accent), var(--accent-2));
  color: #000;
  border: none;
  border-radius: 8px;
  padding: 10px 16px;
  cursor: pointer;
  font-weight: 700;
}
button:hover { filter: brightness(1.05); }
.card {
  background: var(--panel);
  border-radius: 16px;
  padding: 16px;
  box-shadow: 0 10px 30px rgba(0,0,0,.35);
}
table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 16px;
  background: var(--panel);
  border-radius: 16px;
  overflow: hidden;
}
th, td {
  padding: 12px;
  border-bottom: 1px solid var(--border);
}
th {
  background: rgba(255,255,255,0.03);
  text-align: left;
  font-size: .85rem;
  color: var(--muted);
  text-transform: uppercase;
}
tr:hover td { background: rgba(255,255,255,0.03); }
.low-stock { background: rgba(255, 68, 68, 0.1); }
.footer {
  margin-top: 32px;
  padding-top: 16px;
  border-top: 1px solid rgba(255,255,255,0.12);
  color: var(--muted);
  font-size: .9rem;
}
.tools {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 18px;
}
.tools a {
  color: var(--accent);
  text-decoration: none;
}
.status {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: .75rem;
  font-weight: 700;
}
.status-open { background:#3b82f6; color:#000; }
.status-done { background:#22c55e; color:#000; }
</style>
<nav>
<a href="/">Dashboard</a>
<a href="/customers">Customers</a>
<a href="/devices">Devices</a>
<a href="/parts">Parts</a>
<a href="/repairs">Repairs</a>
<a href="/sales">Sales</a>
<a href="/bulk_purchases">Bulk Purchases</a>
<a href="/listings">Listings</a>
<a href="/appointments">Appointments</a>
<a href="/technicians">Technicians</a>
<a href="/quotes">Quotes</a>
<a href="/expenses">Expenses</a>
<a href="/reports">Reports</a>
<a href="/shipments">Shipments</a>
</nav>
<div class="container">
"""

def page_body(content):
    return BASE + content + "<div class='footer'>Repair Shop Manager · Inventory, sales, shipments, quotes, appointments, and reports. · Updated and Maintained by Jacob Saranen</div></div>"

# =====================================================
# Routes
# =====================================================

@app.route("/")
def dashboard():
    db = get_db()
    total_revenue = db.execute("SELECT IFNULL(SUM(total),0) FROM sales").fetchone()[0]
    active_repairs = db.execute("SELECT COUNT(*) FROM repairs WHERE status != 'Done'").fetchone()[0]
    low_stock = db.execute("SELECT COUNT(*) FROM parts WHERE quantity <= 5").fetchone()[0]
    pending_shipments = db.execute("SELECT COUNT(*) FROM shipments WHERE status NOT IN ('Delivered','Complete')").fetchone()[0]
    active_listings = db.execute("SELECT COUNT(*) FROM listings WHERE status = 'Active'").fetchone()[0]
    active_appointments = db.execute("SELECT COUNT(*) FROM appointments WHERE status != 'Completed'").fetchone()[0]
    total_expenses = db.execute("SELECT IFNULL(SUM(amount),0) FROM expenses").fetchone()[0]
    inventory_value = db.execute("SELECT IFNULL(SUM(quantity * price),0) FROM parts").fetchone()[0]
    due_shipments = db.execute("SELECT COUNT(*) FROM shipments WHERE expected_date <= date('now') AND status NOT IN ('Delivered','Complete')").fetchone()[0]
    return render_template_string(page_body("""
    <h2>Dashboard</h2>
    <div class="card">
        <p><strong>Total revenue:</strong> ${{'%.2f'|format(total_revenue)}}</p>
        <p><strong>Open repairs:</strong> {{active_repairs}}</p>
        <p><strong>Low stock parts:</strong> {{low_stock}}</p>
        <p><strong>Inventory value:</strong> ${{'%.2f'|format(inventory_value)}}</p>
        <p><strong>Pending shipments:</strong> {{pending_shipments}}</p>
        <p><strong>Shipments due today or earlier:</strong> {{due_shipments}}</p>
        <p><strong>Active online listings:</strong> {{active_listings}}</p>
        <p><strong>Active appointments:</strong> {{active_appointments}}</p>
        <p><strong>Total expenses:</strong> ${{'%.2f'|format(total_expenses)}}</p>
    </div>
    """), total_revenue=total_revenue, active_repairs=active_repairs,
    low_stock=low_stock, pending_shipments=pending_shipments, active_listings=active_listings,
    active_appointments=active_appointments, total_expenses=total_expenses, inventory_value=inventory_value, due_shipments=due_shipments)

@app.route("/reports")
def reports():
    db = get_db()
    total_sales = db.execute("SELECT IFNULL(SUM(total),0) FROM sales").fetchone()[0]
    online_sales = db.execute("SELECT IFNULL(SUM(total),0) FROM sales WHERE channel = 'Online'").fetchone()[0]
    bulk_sales = db.execute("SELECT IFNULL(SUM(total),0) FROM sales WHERE channel = 'Bulk'").fetchone()[0]
    pending_shipments = db.execute("SELECT COUNT(*) FROM shipments WHERE status NOT IN ('Delivered','Complete')").fetchone()[0]
    low_stock_parts = db.execute("SELECT COUNT(*) FROM parts WHERE quantity <= 5").fetchone()[0]
    upcoming_appointments = db.execute("SELECT COUNT(*) FROM appointments WHERE status = 'Scheduled'").fetchone()[0]
    top_customers = db.execute("SELECT customers.name, IFNULL(SUM(sales.total),0) AS total_spent FROM sales LEFT JOIN customers ON customers.id = sales.customer_id GROUP BY customers.name ORDER BY total_spent DESC LIMIT 5").fetchall()
    return render_template_string(page_body("""
    <h2>Reports</h2>
    <div class="card">
        <p><strong>Total sales revenue:</strong> ${{'%.2f'|format(total_sales)}}</p>
        <p><strong>Online sales revenue:</strong> ${{'%.2f'|format(online_sales)}}</p>
        <p><strong>Bulk sales revenue:</strong> ${{'%.2f'|format(bulk_sales)}}</p>
        <p><strong>Pending shipments:</strong> {{pending_shipments}}</p>
        <p><strong>Low stock parts:</strong> {{low_stock_parts}}</p>
        <p><strong>Upcoming appointments:</strong> {{upcoming_appointments}}</p>
    </div>
    <h3>Top Customers</h3>
    <table>
        <tr><th>Customer</th><th>Total Spent</th></tr>
        {% for c in top_customers %}
        <tr><td>{{c.name or 'Guest'}}</td><td>${{'%.2f'|format(c.total_spent)}}</td></tr>
        {% endfor %}
    </table>
    """), total_sales=total_sales, online_sales=online_sales, bulk_sales=bulk_sales,
    pending_shipments=pending_shipments, low_stock_parts=low_stock_parts,
    upcoming_appointments=upcoming_appointments, top_customers=top_customers)

@app.route("/customers", methods=["GET", "POST"])
def customers():
    db = get_db()
    if request.method == "POST":
        db.execute("INSERT INTO customers (name, phone, email) VALUES (?,?,?)",
                   (request.form["name"], request.form["phone"], request.form["email"]))
        db.commit()
        return redirect("/customers")

    query = request.args.get("q", "").strip()
    if query:
        rows = db.execute("SELECT * FROM customers WHERE name LIKE ? OR email LIKE ?", (f"%{query}%", f"%{query}%")).fetchall()
    else:
        rows = db.execute("SELECT * FROM customers").fetchall()
    return render_template_string(page_body("""
    <h2>Customers</h2>
    <div class="tools">
        <a href="/export/customers">Export CSV</a>
        <form method="get" style="display:flex; gap:10px; flex-wrap:wrap; align-items:center;">
            <input name="q" placeholder="Search customers" value="{{query}}">
            <button type="submit">Search</button>
        </form>
    </div>
    <form method="post">
        <input name="name" placeholder="Name">
        <input name="phone" placeholder="Phone">
        <input name="email" placeholder="Email">
        <button>Add</button>
    </form>
    <table>
        <tr><th>Name</th><th>Phone</th><th>Email</th></tr>
        {% for c in rows %}
        <tr><td>{{c.name}}</td><td>{{c.phone}}</td><td>{{c.email}}</td></tr>
        {% endfor %}
    </table>
    """), rows=rows, query=query)

@app.route("/devices", methods=["GET", "POST"])
def devices():
    db = get_db()
    if request.method == "POST":
        db.execute("""
        INSERT INTO devices (customer_id, type, brand, model, serial, os, storage, ram, status, condition, purchase_source)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            request.form.get("customer_id") or None, request.form["type"], request.form["brand"],
            request.form["model"], request.form["serial"], request.form["os"],
            request.form["storage"], request.form["ram"], "Checked In",
            request.form.get("condition", "Good"), request.form.get("purchase_source", "Walk-in")
        ))
        db.commit()
        return redirect("/devices")

    status_filter = request.args.get("status", "")
    source_filter = request.args.get("source", "")
    status_query = f"%{status_filter}%"
    source_query = f"%{source_filter}%"
    devices = db.execute("""
    SELECT devices.*, customers.name AS customer
    FROM devices LEFT JOIN customers ON customers.id = devices.customer_id
    WHERE devices.status LIKE ? AND devices.purchase_source LIKE ?
    """, (status_query, source_query)).fetchall()
    customers = db.execute("SELECT * FROM customers").fetchall()

    return render_template_string(page_body("""
    <h2>Devices</h2>
    <div class="tools">
        <a href="/export/devices">Export CSV</a>
        <form method="get" style="display:flex; gap:10px; flex-wrap:wrap; align-items:center;">
            <select name="status">
                <option value="">All statuses</option>
                <option{% if status_filter == 'Checked In' %} selected{% endif %}>Checked In</option>
                <option{% if status_filter == 'In Repair' %} selected{% endif %}>In Repair</option>
                <option{% if status_filter == 'Ready' %} selected{% endif %}>Ready</option>
                <option{% if status_filter == 'Sold' %} selected{% endif %}>Sold</option>
            </select>
            <input name="source" placeholder="Source filter" value="{{source_filter}}">
            <button type="submit">Filter</button>
        </form>
    </div>
    <form method="post">
        <select name="customer_id">
            <option value="">Unassigned</option>
            {% for c in customers %}
            <option value="{{c.id}}">{{c.name}}</option>
            {% endfor %}
        </select>
        <input name="type" placeholder="Type (Laptop, Phone)">
        <input name="brand" placeholder="Brand">
        <input name="model" placeholder="Model">
        <input name="serial" placeholder="Serial">
        <input name="os" placeholder="OS">
        <input name="storage" placeholder="Storage">
        <input name="ram" placeholder="RAM">
        <select name="condition">
            <option>Good</option>
            <option>Fair</option>
            <option>Poor</option>
            <option>New</option>
        </select>
        <input name="purchase_source" placeholder="Purchase source (Bulk, Trade-in, Supplier)">
        <button>Add</button>
    </form>
    <table>
        <tr><th>Customer</th><th>Device</th><th>Specs</th><th>Status</th><th>Condition</th><th>Source</th><th>Online</th></tr>
        {% for d in devices %}
        <tr>
            <td>{{d.customer or 'N/A'}}</td>
            <td>{{d.brand}} {{d.model}}</td>
            <td>{{d.os}} | {{d.ram}} | {{d.storage}}</td>
            <td>{{d.status}}</td>
            <td>{{d.condition}}</td>
            <td>{{d.purchase_source}}</td>
            <td>{{ 'Yes' if d.listed_online else 'No' }}</td>
        </tr>
        {% endfor %}
    </table>
    """), devices=devices, customers=customers, status_filter=status_filter, source_filter=source_filter)

@app.route("/parts", methods=["GET", "POST"])
def parts():
    db = get_db()
    if request.method == "POST":
        db.execute("INSERT INTO parts (name, sku, quantity, cost, price) VALUES (?,?,?,?,?)",
                   (request.form["name"], request.form["sku"], request.form["quantity"],
                    request.form["cost"], request.form["price"]))
        db.commit()
        return redirect("/parts")

    rows = db.execute("SELECT * FROM parts").fetchall()
    return render_template_string(page_body("""
    <h2>Parts Inventory</h2>
    <div class="tools"><a href="/export/parts">Export CSV</a></div>
    <form method="post">
        <input name="name" placeholder="Part name">
        <input name="sku" placeholder="SKU">
        <input name="quantity" placeholder="Qty" type="number">
        <input name="cost" placeholder="Cost">
        <input name="price" placeholder="Price">
        <button>Add</button>
    </form>
    <table>
        <tr><th>Name</th><th>SKU</th><th>Qty</th><th>Cost</th><th>Price</th><th>Margin</th></tr>
        {% for p in rows %}
        <tr{% if p.quantity <= 5 %} class="low-stock"{% endif %}>
            <td>{{p.name}}</td>
            <td>{{p.sku}}</td>
            <td>{{p.quantity}}</td>
            <td>${{p.cost}}</td>
            <td>${{p.price}}</td>
            <td>${{'%.2f'|format(p.price - p.cost)}}</td>
        </tr>
        {% endfor %}
    </table>
    """), rows=rows)

@app.route("/repairs", methods=["GET", "POST"])
def repairs():
    db = get_db()
    if request.method == "POST":
        if request.form.get("repair_id"):
            db.execute("UPDATE repairs SET status = ? WHERE id = ?",
                       (request.form["status"], request.form["repair_id"]))
        else:
            db.execute("INSERT INTO repairs (device_id, issue, status, created_at) VALUES (?,?,?,?)",
                       (request.form["device_id"], request.form["issue"], request.form.get("status", "Open"),
                        datetime.datetime.now().isoformat()))
        db.commit()
        return redirect("/repairs")

    repairs = db.execute("""
    SELECT repairs.*, devices.brand, devices.model
    FROM repairs JOIN devices ON devices.id = repairs.device_id
    """).fetchall()
    devices = db.execute("SELECT * FROM devices").fetchall()

    return render_template_string(page_body("""
    <h2>Repairs</h2>
    <form method="post">
        <select name="device_id">
            {% for d in devices %}
            <option value="{{d.id}}">{{d.brand}} {{d.model}}</option>
            {% endfor %}
        </select>
        <input name="issue" placeholder="Issue">
        <select name="status">
            <option>Open</option>
            <option>In Progress</option>
            <option>Awaiting Parts</option>
            <option>Done</option>
        </select>
        <button>Create</button>
    </form>
    <table>
        <tr><th>Device</th><th>Issue</th><th>Status</th><th>Created</th><th>Update</th></tr>
        {% for r in repairs %}
        <tr>
            <td>{{r.brand}} {{r.model}}</td>
            <td>{{r.issue}}</td>
            <td>{{r.status}}</td>
            <td>{{r.created_at}}</td>
            <td>
                <form method="post" style="display:inline-block;">
                    <input type="hidden" name="repair_id" value="{{r.id}}">
                    <select name="status">
                        <option{% if r.status == 'Open' %} selected{% endif %}>Open</option>
                        <option{% if r.status == 'In Progress' %} selected{% endif %}>In Progress</option>
                        <option{% if r.status == 'Awaiting Parts' %} selected{% endif %}>Awaiting Parts</option>
                        <option{% if r.status == 'Done' %} selected{% endif %}>Done</option>
                    </select>
                    <button>Save</button>
                </form>
            </td>
        </tr>
        {% endfor %}
    </table>
    """), repairs=repairs, devices=devices)

@app.route("/sales", methods=["GET", "POST"])
def sales():
    db = get_db()
    if request.method == "POST":
        quantity = int(request.form.get("quantity", 1) or 1)
        unit_price = float(request.form.get("unit_price", 0) or 0)
        total = float(request.form.get("total") or (quantity * unit_price) or 0)
        channel = request.form.get("channel", "Store")
        bulk_order = 1 if channel == "Bulk" else 0
        db.execute("INSERT INTO sales (customer_id, device_id, quantity, unit_price, total, channel, listing_url, bulk_order, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                   (request.form.get("customer_id") or None, request.form.get("device_id") or None,
                    quantity, unit_price, total, channel,
                    request.form.get("listing_url"), bulk_order,
                    datetime.datetime.now().isoformat()))
        db.commit()
        return redirect("/sales")

    query = request.args.get("q", "").strip()
    channel_filter = request.args.get("channel", "")
    query_sql = ""
    params = []
    if query:
        query_sql += " AND (customers.name LIKE ? OR devices.brand LIKE ? OR devices.model LIKE ? OR sales.channel LIKE ? OR sales.listing_url LIKE ?)"
        params += [f"%{query}%"] * 5
    if channel_filter:
        query_sql += " AND sales.channel = ?"
        params.append(channel_filter)
    sales = db.execute("""
    SELECT sales.*, customers.name AS customer, devices.brand, devices.model
    FROM sales
    LEFT JOIN customers ON customers.id = sales.customer_id
    LEFT JOIN devices ON devices.id = sales.device_id
    WHERE 1=1""" + query_sql, params).fetchall()
    customers = db.execute("SELECT * FROM customers").fetchall()
    devices = db.execute("SELECT * FROM devices").fetchall()

    return render_template_string(page_body("""
    <h2>Sales</h2>
    <div class="tools">
        <form method="get" style="display:flex; gap:10px; flex-wrap:wrap; align-items:center;">
            <input name="q" placeholder="Search sales" value="{{query}}">
            <select name="channel">
                <option value="">All channels</option>
                <option{% if channel_filter == 'Store' %} selected{% endif %}>Store</option>
                <option{% if channel_filter == 'Online' %} selected{% endif %}>Online</option>
                <option{% if channel_filter == 'Bulk' %} selected{% endif %}>Bulk</option>
            </select>
            <button type="submit">Filter</button>
        </form>
        <a href="/export/sales">Export CSV</a>
    </div>
    <form method="post">
        <select name="customer_id">
            <option value="">Walk-in / Online buyer</option>
            {% for c in customers %}
            <option value="{{c.id}}">{{c.name}}</option>
            {% endfor %}
        </select>
        <select name="device_id">
            <option value="">No specific device</option>
            {% for d in devices %}
            <option value="{{d.id}}">{{d.brand}} {{d.model}}</option>
            {% endfor %}
        </select>
        <input name="quantity" placeholder="Qty" type="number" value="1">
        <input name="unit_price" placeholder="Unit price">
        <input name="total" placeholder="Total (auto if blank)">
        <input name="listing_url" placeholder="Listing URL">
        <select name="channel">
            <option>Store</option>
            <option>Online</option>
            <option>Bulk</option>
        </select>
        <button>Add</button>
    </form>
    <table>
        <tr><th>Customer</th><th>Device</th><th>Qty</th><th>Channel</th><th>Total</th><th>Listing</th><th>Date</th></tr>
        {% for s in sales %}
        <tr>
            <td>{{s.customer or 'Guest'}}</td>
            <td>{{s.brand or 'N/A'}} {{s.model or ''}}</td>
            <td>{{s.quantity}}</td>
            <td>{{s.channel}}</td>
            <td>${{s.total}}</td>
            <td>{% if s.listing_url %}<a href="{{s.listing_url}}" target="_blank">Link</a>{% else %}—{% endif %}</td>
            <td>{{s.created_at}}</td>
        </tr>
        {% endfor %}
    </table>
    """), sales=sales, customers=customers, devices=devices, query=query, channel_filter=channel_filter)

@app.route("/bulk_purchases", methods=["GET", "POST"])
def bulk_purchases():
    db = get_db()
    if request.method == "POST":
        quantity = int(request.form.get("quantity", 0) or 0)
        unit_cost = float(request.form.get("unit_cost", 0) or 0)
        total_cost = quantity * unit_cost
        db.execute("INSERT INTO bulk_purchases (supplier, quantity, unit_cost, total_cost, received_date, status) VALUES (?,?,?,?,?,?)",
                   (request.form.get("supplier"), quantity, unit_cost, total_cost,
                    request.form.get("received_date", datetime.datetime.now().date().isoformat()),
                    request.form.get("status", "Ordered")))
        db.commit()
        return redirect("/bulk_purchases")

    rows = db.execute("SELECT * FROM bulk_purchases ORDER BY received_date DESC").fetchall()
    return render_template_string(page_body("""
    <h2>Bulk Purchases</h2>
    <div class="tools"><a href="/export/bulk_purchases">Export CSV</a></div>
    <form method="post">
        <input name="supplier" placeholder="Supplier">
        <input name="quantity" placeholder="Qty" type="number">
        <input name="unit_cost" placeholder="Unit cost">
        <input name="received_date" placeholder="Received date">
        <select name="status">
            <option>Ordered</option>
            <option>Received</option>
            <option>Partially received</option>
        </select>
        <button>Add</button>
    </form>
    <table>
        <tr><th>Supplier</th><th>Qty</th><th>Unit cost</th><th>Total</th><th>Received</th><th>Status</th></tr>
        {% for r in rows %}
        <tr>
            <td>{{r.supplier}}</td><td>{{r.quantity}}</td><td>${{r.unit_cost}}</td><td>${{r.total_cost}}</td>
            <td>{{r.received_date}}</td><td>{{r.status}}</td>
        </tr>
        {% endfor %}
    </table>
    """), rows=rows)

@app.route("/listings", methods=["GET", "POST"])
def listings():
    db = get_db()
    if request.method == "POST":
        if request.form.get("listing_id"):
            status = request.form.get("status", "Active")
            db.execute("UPDATE listings SET status = ? WHERE id = ?", (status, request.form["listing_id"]))
            listing = db.execute("SELECT device_id FROM listings WHERE id = ?", (request.form["listing_id"],)).fetchone()
            if status == "Sold" and listing and listing["device_id"]:
                db.execute("UPDATE devices SET status = 'Sold' WHERE id = ?", (listing["device_id"],))
        else:
            db.execute("INSERT INTO listings (device_id, platform, listing_price, listing_url, status, listed_at) VALUES (?,?,?,?,?,?)",
                       (request.form.get("device_id"), request.form.get("platform"),
                        request.form.get("listing_price"), request.form.get("listing_url"),
                        request.form.get("status", "Active"), datetime.datetime.now().isoformat()))
            if request.form.get("device_id"):
                db.execute("UPDATE devices SET listed_online = 1 WHERE id = ?", (request.form.get("device_id"),))
        db.commit()
        return redirect("/listings")

    rows = db.execute("SELECT listings.*, devices.brand, devices.model FROM listings LEFT JOIN devices ON devices.id = listings.device_id ORDER BY listed_at DESC").fetchall()
    devices = db.execute("SELECT * FROM devices").fetchall()
    return render_template_string(page_body("""
    <h2>Online Listings</h2>
    <div class="tools"><a href="/export/listings">Export CSV</a></div>
    <form method="post">
        <select name="device_id">
            <option value="">Select device</option>
            {% for d in devices %}
            <option value="{{d.id}}">{{d.brand}} {{d.model}}</option>
            {% endfor %}
        </select>
        <input name="platform" placeholder="Platform">
        <input name="listing_price" placeholder="Listing price">
        <input name="listing_url" placeholder="Listing URL">
        <select name="status">
            <option>Active</option>
            <option>Sold</option>
            <option>Paused</option>
        </select>
        <button>Add</button>
    </form>
    <table>
        <tr><th>Device</th><th>Platform</th><th>Price</th><th>Status</th><th>Listed</th><th>Link</th><th>Update</th></tr>
        {% for l in rows %}
        <tr>
            <td>{{l.brand or 'N/A'}} {{l.model or ''}}</td><td>{{l.platform}}</td><td>${{l.listing_price}}</td><td>{{l.status}}</td>
            <td>{{l.listed_at}}</td>
            <td>{% if l.listing_url %}<a href="{{l.listing_url}}" target="_blank">Link</a>{% else %}—{% endif %}</td>
            <td>
                <form method="post" style="display:inline-flex; gap:8px;">
                    <input type="hidden" name="listing_id" value="{{l.id}}">
                    <select name="status" style="min-width:120px;">
                        <option{% if l.status == 'Active' %} selected{% endif %}>Active</option>
                        <option{% if l.status == 'Sold' %} selected{% endif %}>Sold</option>
                        <option{% if l.status == 'Paused' %} selected{% endif %}>Paused</option>
                    </select>
                    <button>Save</button>
                </form>
            </td>
        </tr>
        {% endfor %}
    </table>
    """), rows=rows, devices=devices)

@app.route("/technicians", methods=["GET", "POST"])
def technicians():
    db = get_db()
    if request.method == "POST":
        db.execute("INSERT INTO technicians (name, phone, email, role) VALUES (?,?,?,?)",
                   (request.form.get("name"), request.form.get("phone"), request.form.get("email"), request.form.get("role")))
        db.commit()
        return redirect("/technicians")

    rows = db.execute("SELECT * FROM technicians").fetchall()
    return render_template_string(page_body("""
    <h2>Technicians</h2>
    <form method="post">
        <input name="name" placeholder="Name">
        <input name="phone" placeholder="Phone">
        <input name="email" placeholder="Email">
        <input name="role" placeholder="Role">
        <button>Add</button>
    </form>
    <table>
        <tr><th>Name</th><th>Phone</th><th>Email</th><th>Role</th></tr>
        {% for t in rows %}
        <tr><td>{{t.name}}</td><td>{{t.phone}}</td><td>{{t.email}}</td><td>{{t.role}}</td></tr>
        {% endfor %}
    </table>
    """), rows=rows)

@app.route("/appointments", methods=["GET", "POST"])
def appointments():
    db = get_db()
    if request.method == "POST":
        db.execute("INSERT INTO appointments (customer_id, device_id, scheduled_date, appointment_type, status, notes) VALUES (?,?,?,?,?,?)",
                   (request.form.get("customer_id"), request.form.get("device_id"), request.form.get("scheduled_date"),
                    request.form.get("appointment_type"), request.form.get("status", "Scheduled"), request.form.get("notes")))
        db.commit()
        return redirect("/appointments")

    rows = db.execute("SELECT appointments.*, customers.name AS customer, devices.brand, devices.model FROM appointments LEFT JOIN customers ON customers.id = appointments.customer_id LEFT JOIN devices ON devices.id = appointments.device_id ORDER BY scheduled_date DESC").fetchall()
    customers = db.execute("SELECT * FROM customers").fetchall()
    devices = db.execute("SELECT * FROM devices").fetchall()
    return render_template_string(page_body("""
    <h2>Appointments</h2>
    <div class="tools"><a href="/export/appointments">Export CSV</a></div>
    <form method="post">
        <select name="customer_id">
            <option value="">Customer</option>
            {% for c in customers %}
            <option value="{{c.id}}">{{c.name}}</option>
            {% endfor %}
        </select>
        <select name="device_id">
            <option value="">Device</option>
            {% for d in devices %}
            <option value="{{d.id}}">{{d.brand}} {{d.model}}</option>
            {% endfor %}
        </select>
        <input name="scheduled_date" placeholder="Date">
        <input name="appointment_type" placeholder="Type">
        <select name="status">
            <option>Scheduled</option>
            <option>Completed</option>
            <option>Cancelled</option>
        </select>
        <input name="notes" placeholder="Notes">
        <button>Add</button>
    </form>
    <table>
        <tr><th>Date</th><th>Customer</th><th>Device</th><th>Type</th><th>Status</th><th>Notes</th></tr>
        {% for a in rows %}
        <tr><td>{{a.scheduled_date}}</td><td>{{a.customer or 'N/A'}}</td><td>{{a.brand or 'N/A'}} {{a.model or ''}}</td><td>{{a.appointment_type}}</td><td>{{a.status}}</td><td>{{a.notes}}</td></tr>
        {% endfor %}
    </table>
    """), rows=rows, customers=customers, devices=devices)

@app.route("/quotes", methods=["GET", "POST"])
def quotes():
    db = get_db()
    if request.method == "POST":
        if request.form.get("quote_action") == "convert_to_sale":
            quote = db.execute("SELECT * FROM quotes WHERE id = ?", (request.form.get("quote_id"),)).fetchone()
            if quote:
                db.execute("INSERT INTO sales (customer_id, device_id, quantity, unit_price, total, channel, listing_url, bulk_order, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                           (quote["customer_id"], quote["device_id"], 1, quote["estimate"], quote["estimate"], "Store", None, 0, datetime.datetime.now().isoformat()))
                db.execute("UPDATE quotes SET status = 'Accepted' WHERE id = ?", (quote["id"],))
        elif request.form.get("quote_action") == "convert_to_repair":
            quote = db.execute("SELECT * FROM quotes WHERE id = ?", (request.form.get("quote_id"),)).fetchone()
            if quote:
                db.execute("INSERT INTO repairs (device_id, issue, status, created_at) VALUES (?,?,?,?)",
                           (quote["device_id"], "Quote accepted", "Open", datetime.datetime.now().isoformat()))
                db.execute("UPDATE quotes SET status = 'Accepted' WHERE id = ?", (quote["id"],))
        else:
            db.execute("INSERT INTO quotes (customer_id, device_id, estimate, status, created_at, notes) VALUES (?,?,?,?,?,?)",
                       (request.form.get("customer_id"), request.form.get("device_id"), request.form.get("estimate"),
                        request.form.get("status", "Pending"), datetime.datetime.now().isoformat(), request.form.get("notes")))
        db.commit()
        return redirect("/quotes")

    rows = db.execute("SELECT quotes.*, customers.name AS customer, devices.brand, devices.model FROM quotes LEFT JOIN customers ON customers.id = quotes.customer_id LEFT JOIN devices ON devices.id = quotes.device_id ORDER BY created_at DESC").fetchall()
    customers = db.execute("SELECT * FROM customers").fetchall()
    devices = db.execute("SELECT * FROM devices").fetchall()
    return render_template_string(page_body("""
    <h2>Quotes</h2>
    <div class="tools"><a href="/export/quotes">Export CSV</a></div>
    <form method="post">
        <select name="customer_id">
            <option value="">Customer</option>
            {% for c in customers %}
            <option value="{{c.id}}">{{c.name}}</option>
            {% endfor %}
        </select>
        <select name="device_id">
            <option value="">Device</option>
            {% for d in devices %}
            <option value="{{d.id}}">{{d.brand}} {{d.model}}</option>
            {% endfor %}
        </select>
        <input name="estimate" placeholder="Estimate">
        <select name="status">
            <option>Pending</option>
            <option>Accepted</option>
            <option>Rejected</option>
        </select>
        <input name="notes" placeholder="Notes">
        <button>Add</button>
    </form>
    <table>
        <tr><th>Created</th><th>Customer</th><th>Device</th><th>Estimate</th><th>Status</th><th>Notes</th><th>Actions</th></tr>
        {% for q in rows %}
        <tr>
            <td>{{q.created_at}}</td><td>{{q.customer or 'N/A'}}</td><td>{{q.brand or 'N/A'}} {{q.model or ''}}</td><td>${{q.estimate}}</td><td>{{q.status}}</td><td>{{q.notes}}</td>
            <td>
                <form method="post" style="display:inline-flex; gap:8px;">
                    <input type="hidden" name="quote_id" value="{{q.id}}">
                    <input type="hidden" name="quote_action" value="convert_to_sale">
                    <button>Convert to Sale</button>
                </form>
                <form method="post" style="display:inline-flex; gap:8px;">
                    <input type="hidden" name="quote_id" value="{{q.id}}">
                    <input type="hidden" name="quote_action" value="convert_to_repair">
                    <button>Convert to Repair</button>
                </form>
            </td>
        </tr>
        {% endfor %}
    </table>
    """), rows=rows, customers=customers, devices=devices)

@app.route("/expenses", methods=["GET", "POST"])
def expenses():
    db = get_db()
    if request.method == "POST":
        db.execute("INSERT INTO expenses (category, amount, vendor, date, notes) VALUES (?,?,?,?,?)",
                   (request.form.get("category"), request.form.get("amount"), request.form.get("vendor"),
                    request.form.get("date", datetime.datetime.now().date().isoformat()), request.form.get("notes")))
        db.commit()
        return redirect("/expenses")

    rows = db.execute("SELECT * FROM expenses ORDER BY date DESC").fetchall()
    return render_template_string(page_body("""
    <h2>Expenses</h2>
    <div class="tools"><a href="/export/expenses">Export CSV</a></div>
    <form method="post">
        <input name="category" placeholder="Category">
        <input name="amount" placeholder="Amount">
        <input name="vendor" placeholder="Vendor">
        <input name="date" placeholder="Date">
        <input name="notes" placeholder="Notes">
        <button>Add</button>
    </form>
    <table>
        <tr><th>Date</th><th>Category</th><th>Amount</th><th>Vendor</th><th>Notes</th></tr>
        {% for e in rows %}
        <tr><td>{{e.date}}</td><td>{{e.category}}</td><td>${{e.amount}}</td><td>{{e.vendor}}</td><td>{{e.notes}}</td></tr>
        {% endfor %}
    </table>
    """), rows=rows)

@app.route("/shipments", methods=["GET", "POST"])
def shipments():
    db = get_db()
    query = request.args.get("q", "").strip()
    if request.method == "POST":
        if request.form.get("shipment_id"):
            db.execute("UPDATE shipments SET status = ?, expected_date = ?, tracking = ? WHERE id = ?",
                       (request.form.get("status"), request.form.get("expected_date"), request.form.get("tracking"), request.form["shipment_id"]))
        else:
            carrier = request.form.get("carrier")
            expected_date = request.form.get("expected_date")
            status = request.form.get("status")
            if not expected_date or not status:
                suggested_date, suggested_status = get_carrier_eta(carrier)
                expected_date = expected_date or suggested_date
                status = status or suggested_status
            db.execute("INSERT INTO shipments (carrier, tracking, status, expected_date) VALUES (?,?,?,?)",
                       (carrier, request.form.get("tracking"), status, expected_date))
        db.commit()
        return redirect("/shipments")

    if query:
        rows = db.execute("SELECT * FROM shipments WHERE carrier LIKE ? OR tracking LIKE ?", (f"%{query}%", f"%{query}%")).fetchall()
    else:
        rows = db.execute("SELECT * FROM shipments").fetchall()
    return render_template_string(page_body("""
    <h2>Shipments</h2>
    <div class="tools">
        <a href="/export/shipments">Export CSV</a>
        <form method="get" style="display:flex; gap:10px; flex-wrap:wrap; align-items:center;">
            <input name="q" placeholder="Search carrier or tracking" value="{{query}}">
            <button type="submit">Filter</button>
        </form>
    </div>
    <form method="post">
        <input name="carrier" placeholder="Carrier">
        <input name="tracking" placeholder="Tracking #">
        <input name="status" placeholder="Status (optional)">
        <input name="expected_date" placeholder="Expected Date (optional)">
        <button>Add</button>
    </form>
    <table>
        <tr><th>Carrier</th><th>Tracking</th><th>Status</th><th>ETA</th><th>Update</th></tr>
        {% for s in rows %}
        <tr>
            <td>{{s.carrier}}</td><td>{{s.tracking}}</td><td>{{s.status}}</td><td>{{s.expected_date}}</td>
            <td>
                <form method="post" style="display:inline-flex; gap:8px;">
                    <input type="hidden" name="shipment_id" value="{{s.id}}">
                    <input name="tracking" placeholder="Tracking" value="{{s.tracking}}">
                    <input name="status" placeholder="Status" value="{{s.status}}">
                    <input name="expected_date" placeholder="ETA" value="{{s.expected_date}}">
                    <button>Save</button>
                </form>
            </td>
        </tr>
        {% endfor %}
    </table>
    """), rows=rows, query=query)

@app.route("/export/<table_name>")
def export_table(table_name):
    db = get_db()
    allowed = {
        "customers": "SELECT * FROM customers",
        "devices": "SELECT * FROM devices",
        "parts": "SELECT * FROM parts",
        "sales": "SELECT * FROM sales",
        "appointments": "SELECT * FROM appointments",
        "quotes": "SELECT * FROM quotes",
        "expenses": "SELECT * FROM expenses",
        "bulk_purchases": "SELECT * FROM bulk_purchases",
        "listings": "SELECT * FROM listings",
        "shipments": "SELECT * FROM shipments",
        "technicians": "SELECT * FROM technicians"
    }
    if table_name not in allowed:
        return redirect("/")
    rows = db.execute(allowed[table_name]).fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(rows[0].keys() if rows else [])
    for row in rows:
        writer.writerow(list(row))
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f"attachment; filename={table_name}.csv"})

# =====================================================

if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
