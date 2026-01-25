from flask import Flask, request, redirect, url_for, render_template_string, g
import sqlite3
import datetime

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
        total REAL,
        created_at TEXT,
        FOREIGN KEY(customer_id) REFERENCES customers(id)
    );

    CREATE TABLE IF NOT EXISTS shipments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        carrier TEXT,
        tracking TEXT,
        status TEXT,
        expected_date TEXT
    );
    """)
    db.commit()

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
<a href="/shipments">Shipments</a>
</nav>
<div class="container">
"""

# =====================================================
# Routes
# =====================================================

@app.route("/")
def dashboard():
    return render_template_string(BASE + """"
    <h2>Dashboard</h2>
    <p>Repair shop management system</p>
    """) #" , Customers ----------------

@app.route("/customers", methods=["GET", "POST"])
def customers():
    db = get_db()
    if request.method == "POST":
        db.execute("INSERT INTO customers (name, phone, email) VALUES (?,?,?)",
                   (request.form["name"], request.form["phone"], request.form["email"]))
        db.commit()
        return redirect("/customers")

    rows = db.execute("SELECT * FROM customers").fetchall()
    return render_template_string(BASE + """"
    <h2>Customers</h2>
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
    """, rows=rows) #" , Devices ----------------

@app.route("/devices", methods=["GET", "POST"])
def devices():
    db = get_db()
    if request.method == "POST":
        db.execute("""
        INSERT INTO devices (customer_id, type, brand, model, serial, os, storage, ram, status)
        VALUES (?,?,?,?,?,?,?,?,?)
        """, (
            request.form["customer_id"], request.form["type"], request.form["brand"],
            request.form["model"], request.form["serial"], request.form["os"],
            request.form["storage"], request.form["ram"], "Checked In"
        ))
        db.commit()
        return redirect("/devices")

    devices = db.execute("""
    SELECT devices.*, customers.name AS customer
    FROM devices LEFT JOIN customers ON customers.id = devices.customer_id
    """).fetchall()
    customers = db.execute("SELECT * FROM customers").fetchall()

    return render_template_string(BASE + """"
    <h2>Devices</h2>
    <form method="post">
        <select name="customer_id">
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
        <button>Add</button>
    </form>
    <table>
        <tr><th>Customer</th><th>Device</th><th>Specs</th><th>Status</th></tr>
        {% for d in devices %}
        <tr>
            <td>{{d.customer}}</td>
            <td>{{d.brand}} {{d.model}}</td>
            <td>{{d.os}} | {{d.ram}} | {{d.storage}}</td>
            <td>{{d.status}}</td>
        </tr>
        {% endfor %}
    </table>
    """, devices=devices, customers=customers) #" , Parts ----------------

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
    return render_template_string(BASE + """"
    <h2>Parts Inventory</h2>
    <form method="post">
        <input name="name" placeholder="Part name">
        <input name="sku" placeholder="SKU">
        <input name="quantity" placeholder="Qty" type="number">
        <input name="cost" placeholder="Cost">
        <input name="price" placeholder="Price">
        <button>Add</button>
    </form>
    <table>
        <tr><th>Name</th><th>SKU</th><th>Qty</th><th>Price</th></tr>
        {% for p in rows %}
        <tr><td>{{p.name}}</td><td>{{p.sku}}</td><td>{{p.quantity}}</td><td>${{p.price}}</td></tr>
        {% endfor %}
    </table>
    """, rows=rows) #" , Repairs ----------------

@app.route("/repairs", methods=["GET", "POST"])
def repairs():
    db = get_db()
    if request.method == "POST":
        db.execute("INSERT INTO repairs (device_id, issue, status, created_at) VALUES (?,?,?,?)",
                   (request.form["device_id"], request.form["issue"], "Open",
                    datetime.datetime.now().isoformat()))
        db.commit()
        return redirect("/repairs")

    repairs = db.execute("""
    SELECT repairs.*, devices.brand, devices.model
    FROM repairs JOIN devices ON devices.id = repairs.device_id
    """).fetchall()
    devices = db.execute("SELECT * FROM devices").fetchall()

    return render_template_string(BASE + """"
    <h2>Repairs</h2>
    <form method="post">
        <select name="device_id">
            {% for d in devices %}
            <option value="{{d.id}}">{{d.brand}} {{d.model}}</option>
            {% endfor %}
        </select>
        <input name="issue" placeholder="Issue">
        <button>Create</button>
    </form>
    <table>
        <tr><th>Device</th><th>Issue</th><th>Status</th></tr>
        {% for r in repairs %}
        <tr><td>{{r.brand}} {{r.model}}</td><td>{{r.issue}}</td><td>{{r.status}}</td></tr>
        {% endfor %}
    </table>
    """, repairs=repairs, devices=devices) #" , Sales ----------------

@app.route("/sales", methods=["GET", "POST"])
def sales():
    db = get_db()
    if request.method == "POST":
        db.execute("INSERT INTO sales (customer_id, total, created_at) VALUES (?,?,?)",
                   (request.form["customer_id"], request.form["total"],
                    datetime.datetime.now().isoformat()))
        db.commit()
        return redirect("/sales")

    sales = db.execute("""
    SELECT sales.*, customers.name
    FROM sales JOIN customers ON customers.id = sales.customer_id
    """).fetchall()
    customers = db.execute("SELECT * FROM customers").fetchall()

    return render_template_string(BASE + """"
    <h2>Sales</h2>
    <form method="post">
        <select name="customer_id">
            {% for c in customers %}
            <option value="{{c.id}}">{{c.name}}</option>
            {% endfor %}
        </select>
        <input name="total" placeholder="Total">
        <button>Add</button>
    </form>
    <table>
        <tr><th>Customer</th><th>Total</th><th>Date</th></tr>
        {% for s in sales %}
        <tr><td>{{s.name}}</td><td>${{s.total}}</td><td>{{s.created_at}}</td></tr>
        {% endfor %}
    </table>
    """, sales=sales, customers=customers) #" , Shipments ----------------

@app.route("/shipments", methods=["GET", "POST"])
def shipments():
    db = get_db()
    if request.method == "POST":
        db.execute("INSERT INTO shipments (carrier, tracking, status, expected_date) VALUES (?,?,?,?)",
                   (request.form["carrier"], request.form["tracking"],
                    request.form["status"], request.form["expected_date"]))
        db.commit()
        return redirect("/shipments")

    rows = db.execute("SELECT * FROM shipments").fetchall()
    return render_template_string(BASE + """"
    <h2>Shipments</h2>
    <form method="post">
        <input name="carrier" placeholder="Carrier">
        <input name="tracking" placeholder="Tracking #">
        <input name="status" placeholder="Status">
        <input name="expected_date" placeholder="Expected Date">
        <button>Add</button>
    </form>
    <table>
        <tr><th>Carrier</th><th>Tracking</th><th>Status</th><th>ETA</th></tr>
        {% for s in rows %}
        <tr><td>{{s.carrier}}</td><td>{{s.tracking}}</td><td>{{s.status}}</td><td>{{s.expected_date}}</td></tr>
        {% endfor %}
    </table>
    """, rows=rows)

# =====================================================

if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
