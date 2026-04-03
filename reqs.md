💻 Cashier & Inventory System – Full Requirements (MVC, Python + MSSQL)
🧱 TECHNOLOGY STACK
Backend: Python (Flask, MVC structure)
Frontend: HTML/CSS/JS (Bootstrap optional)
Database: Microsoft SQL Server through SQLAlchemy
ORM: SQLAlchemy
Templating: Jinja2
PDF generation: reportlab or equivalent
📂 PROJECT STRUCTURE (MVC)
project/
│
├─ app.py                   # Main entry point
├─ config.py                # Configs (DB connection, admin password, etc.)
│
├─ models/                  # Database models
│   ├─ supplier.py
│   ├─ retail_transaction.py
│   ├─ special_retailer.py
│   ├─ payment.py
│   ├─ expense.py
│   └─ settings.py
│
├─ routes/                  # Controllers
│   ├─ supplier_routes.py
│   ├─ retail_routes.py
│   ├─ special_retailer_routes.py
│   ├─ payment_routes.py
│   ├─ expense_routes.py
│   └─ admin_routes.py
│
├─ templates/               # HTML pages (views)
│   ├─ base.html
│   ├─ dashboard.html
│   ├─ suppliers.html
│   ├─ retail.html
│   ├─ special_retailers.html
│   ├─ payments.html
│   ├─ expenses.html
│   └─ admin.html
│
├─ static/
│   ├─ css/
│   └─ js/
│
└─ utils/
    ├─ report_generator.py
    └─ helpers.py
🗄️ DATABASE MODELS
1️⃣ Suppliers
id (PK)
date
supplier_name
fruit_name
units_count
remaining_units
class_number
price_per_unit
total_price
notes
is_cleared (boolean)

Business logic:

Decrease remaining_units after each sale
Auto mark is_cleared = True when remaining_units = 0
2️⃣ Retail Transactions
id (PK)
date
fruit_name
units_count
class_number
price_per_unit
commission_per_unit
admin_expense
total_price
final_price = total_price + (commission * units) + admin_expense
notes
3️⃣ Special Retailers (Debt + Installments)
id (PK)
date
retailer_name
fruit_name
units_count
class_number
price_per_unit
total_price
total_paid (default 0)
remaining_balance = total_price - total_paid
status = unpaid / partial / paid
notes
4️⃣ Payments
id (PK)
retailer_id (FK → special_retailers.id)
payment_date
amount_paid
notes

Logic:

total_paid += amount_paid
remaining_balance = total_price - total_paid
Update status based on remaining_balance
5️⃣ Expenses
id (PK)
date
expense_name
amount

Logic:

Deduct all expenses from revenue
6️⃣ Settings
id
company_name
phone_number
commission_per_unit
admin_expense
admin_password (hashed)
🔹 CORE FEATURES
Supplier Management
Add/update/view suppliers
Track remaining units
Auto-clear when units = 0
Retail Sales
Add/view transactions
Auto-update supplier inventory (FIFO)
Calculate final_price including commission + admin expense
Generate PDF receipt including company name, phone, admin expense, commission
Special Retailers (Debt)
Add/view debt transactions
Allow multiple payments (installments)
Track total_paid, remaining_balance, status
Generate updated receipts after each payment
KPI: total outstanding debt
Expenses
Add/view expenses (breakfast, drinks, etc.)
Deduct from revenue
Discounts
Apply discounts per unit manually
Log original and discounted price
📊 DASHBOARD / KPIs

Top bar shows:

Number of active suppliers (remaining_units > 0)
Current inventory (dropdown filter by fruit)
Today revenue
Today expenses
Total outstanding debt
📈 REPORTS

Generate Report Button:

Inventory summary (fruit, class, units, price, total)
Sold units summary (fruit, class, units, revenue)
Total revenue = sum(sales) - expenses
🔐 ADMIN PANEL
Password protected (gear icon)
Admin can:
Edit/delete any transaction (updates revenue & inventory)
Edit company name & phone number
Change/remove commission per unit
Change/remove admin expense
Manage password
⚙️ BUSINESS LOGIC RULES
Inventory cannot go negative
Supplier paid only when stock = 0
Special retailers can have negative balance until paid
All edits must recalc totals instantly
Payment cannot exceed remaining_balance
💡 TECHNICAL NOTES
Use Flask MVC structure for maintainability
Keep SQL Server settings in a dedicated config file for easier setup and maintenance
Keep route registration and navigation centralized so new tabs/features are added in one place
Use SQLAlchemy ORM for DB access
Use Jinja2 for templates
Optional: AJAX for smoother UI
PDF receipts generated using reportlab

System runs locally with:

python app.py
Minimal dependencies, easy install via pip


this should be arabic system
