# Repair Management

A lightweight repair shop management web application built with Python Flask and SQLite.

## Features

- Customer, device, part, technician, appointment, and quote management
- Repair tracking with status updates
- Sales tracking for store, online, and bulk channels
- Bulk purchase and vendor order management
- Online listings with platform and status tracking
- Shipment tracking with carrier ETA auto-suggestions
- Expense tracking and exportable reports
- Dashboard metrics for revenue, inventory value, stock alerts, and shipment monitoring
- CSV export support for customers, devices, parts, sales, appointments, quotes, expenses, bulk purchases, listings, shipments, and technicians
- Quote conversion actions for quick sale or repair creation

## Requirements

- Python 3.10+
- Flask

## Setup

1. Create a virtual environment:

   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

2. Install Flask:

   ```bash
   pip install flask
   ```

3. Run the app:

   ```bash
   python main.py
   ```

4. Open your browser at:

   ```text
   http://127.0.0.1:5000
   ```

## Project Structure

- `main.py` — Flask application with routes, templates, and SQLite schema all in one file
- `repair_shop.db` — local SQLite database created at runtime
- `README.md` — project documentation
- `.gitignore` — files to ignore in Git commits

## Notes

- The app initializes the SQLite database automatically on first launch.
- Data is stored locally in `repair_shop.db`.
- Use the export links in the UI to download CSV data for key tables.

## Future enhancements

- Add authentication and role-based access control
- Improve the UI with separate templates and static assets
- Add item-level part usage and inventory reservation
- Add email/SMS notifications for appointments and shipment updates
