import os
import sqlite3
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from app.config import Config
from app.db import init_db

def seed_database():
    print("[*] Initializing Bharat National Bank database schema...")
    os.makedirs(os.path.dirname(Config.DATABASE_PATH), exist_ok=True)
    
    # Remove existing db file to apply fresh schema
    if os.path.exists(Config.DATABASE_PATH):
        try:
            os.remove(Config.DATABASE_PATH)
        except Exception:
            pass

    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    with open(Config.SCHEMA_PATH, 'r', encoding='utf-8') as f:
        conn.executescript(f.read())

    cur = conn.cursor()

    # Clear existing data for clean re-seeding
    cur.execute("DELETE FROM audit_logs;")
    cur.execute("DELETE FROM transactions;")
    cur.execute("DELETE FROM accounts;")
    cur.execute("DELETE FROM users;")

    print("[*] Creating users with Indian identities...")
    now = datetime.now()

    # 1. Admin User (Head Office New Delhi)
    admin_pwd = generate_password_hash("Admin@123")
    admin_created = (now - timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
        INSERT INTO users (username, email, password_hash, first_name, last_name, phone, address, role, is_active, created_at)
        VALUES ('admin', 'admin@bharatbank.co.in', ?, 'System', 'Administrator', '+91 11 2345 6789', 'Head Office, 7, Barakhamba Road, Connaught Place, New Delhi - 110001', 'admin', 1, ?)
    """, (admin_pwd, admin_created))
    admin_id = cur.lastrowid

    # 2. Customers with Indian names, +91 phone numbers, and addresses
    cust_pwd = generate_password_hash("Customer@123")

    customers_data = [
        ("aaravs", "aarav.sharma@example.com", "Aarav", "Sharma", "+91 98765 43210", "B-42, Sector 62, Noida, Uttar Pradesh - 201301", 45),
        ("priyap", "priya.patel@example.com", "Priya", "Patel", "+91 98123 45678", "12, Navrangpura, Ahmedabad, Gujarat - 380009", 35),
        ("rohanv", "rohan.verma@example.com", "Rohan", "Verma", "+91 97654 32109", "Flat 304, Green Glen Layout, Bellandur, Bengaluru - 560103", 25),
        ("vikrams", "vikram.singh@example.com", "Vikram", "Singh", "+91 99887 76655", "C-18, Malviya Nagar, Jaipur, Rajasthan - 302017", 15)
    ]

    user_ids = {}
    for username, email, fn, ln, phone, addr, days_ago in customers_data:
        dt_str = (now - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("""
            INSERT INTO users (username, email, password_hash, first_name, last_name, phone, address, role, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'customer', 1, ?)
        """, (username, email, cust_pwd, fn, ln, phone, addr, dt_str))
        user_ids[username] = cur.lastrowid

    print("[*] Creating Indian bank accounts with INR balances...")
    accounts_info = [
        (user_ids['aaravs'], "1001202401", "Savings", 145000.00, "ACTIVE", 45),
        (user_ids['priyap'], "1001202402", "Current", 85500.00, "ACTIVE", 35),
        (user_ids['rohanv'], "1001202403", "Salary", 32000.00, "ACTIVE", 25),
        (user_ids['vikrams'], "1001202404", "Savings", 15000.00, "FROZEN", 15)
    ]

    account_ids = {}
    for uid, acc_num, acc_type, bal, status, days_ago in accounts_info:
        dt_str = (now - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("""
            INSERT INTO accounts (user_id, account_number, account_type, balance, currency, status, created_at)
            VALUES (?, ?, ?, ?, 'INR', ?, ?)
        """, (uid, acc_num, acc_type, bal, status, dt_str))
        account_ids[acc_num] = cur.lastrowid

    print("[*] Creating realistic Indian banking transaction history (INR)...")
    a_acc = account_ids["1001202401"]
    p_acc = account_ids["1001202402"]
    r_acc = account_ids["1001202403"]
    v_acc = account_ids["1001202404"]

    transactions_data = [
        # Aarav Initial Cash Deposit
        ("TXN-20261001-A9E1B2", None, a_acc, "DEPOSIT", 100000.00, None, 100000.00, "SUCCESS", "Initial Account Opening Cash Deposit (CDM)", now - timedelta(days=44)),
        # Priya Initial Deposit
        ("TXN-20261010-B2C3D4", None, p_acc, "DEPOSIT", 75000.00, None, 75000.00, "SUCCESS", "Account Activation Cheque Clearing Deposit", now - timedelta(days=34)),
        # Rohan Initial Salary Account Deposit
        ("TXN-20261020-C4D5E6", None, r_acc, "DEPOSIT", 25000.00, None, 25000.00, "SUCCESS", "Opening Cash Deposit Counter", now - timedelta(days=24)),
        # Vikram Wire Transfer
        ("TXN-20261101-D5E6F7", None, v_acc, "DEPOSIT", 15000.00, None, 15000.00, "SUCCESS", "NEFT Inward Inception Credit", now - timedelta(days=14)),
        
        # Monthly Salary for Aarav (Infosys Corporate Payroll NEFT)
        ("TXN-20261015-E7F8A1", None, a_acc, "DEPOSIT", 65000.00, None, 165000.00, "SUCCESS", "Monthly Corporate Payroll NEFT Credit", now - timedelta(days=30)),
        # Aarav ATM Withdrawal (SBI / HDFC ATM Counter)
        ("TXN-20261022-F9A1B2", a_acc, None, "WITHDRAWAL", 5000.00, 160000.00, None, "SUCCESS", "Metro Station ATM Cash Withdrawal", now - timedelta(days=26)),
        # Aarav Transfers to Priya (Apartment Rent via IMPS)
        ("TXN-20261028-A2B3C4", a_acc, p_acc, "TRANSFER", 20000.00, 140000.00, 95000.00, "SUCCESS", "Monthly Apartment Rent Share via IMPS", now - timedelta(days=20)),
        # Priya Consulting Income (TCS Tech Project NEFT)
        ("TXN-20261102-B3C4D5", None, p_acc, "DEPOSIT", 30000.00, None, 125000.00, "SUCCESS", "Tech Consulting Fee via RTGS Inward", now - timedelta(days=15)),
        # Priya Transfers to Rohan (UI/UX Design Payment)
        ("TXN-20261105-C5D6E7", p_acc, r_acc, "TRANSFER", 15000.00, 110000.00, 40000.00, "SUCCESS", "UI/UX Mobile App Milestone Payment", now - timedelta(days=12)),
        # Rohan ATM Withdrawal
        ("TXN-20261108-D6E7F8", r_acc, None, "WITHDRAWAL", 3000.00, 37000.00, None, "SUCCESS", "Bank ATM Counter Cash Withdrawal", now - timedelta(days=9)),
        # Aarav Diwali Festive Bonus
        ("TXN-20261110-E8F9A1", None, a_acc, "DEPOSIT", 15000.00, None, 155000.00, "SUCCESS", "Annual Festive Bonus Credit", now - timedelta(days=7)),
        # Aarav Transfers to Priya (Dinner Reimbursement)
        ("TXN-20261112-F1A2B3", a_acc, p_acc, "TRANSFER", 2000.00, 153000.00, 112000.00, "SUCCESS", "Weekend Family Dinner Reimbursement", now - timedelta(days=5)),
        # Priya Shopping / Expenses
        ("TXN-20261114-A3B4C5", p_acc, None, "WITHDRAWAL", 6500.00, 105500.00, None, "SUCCESS", "Point-of-Sale POS Terminal Withdrawal", now - timedelta(days=3)),
        # Aarav transfers to Rohan (Mentorship & Code Review Fee)
        ("TXN-20261116-B5C6D7", a_acc, r_acc, "TRANSFER", 8000.00, 145000.00, 45000.00, "SUCCESS", "Full-Stack Mentorship & Code Review Fee", now - timedelta(days=2)),
        # Rohan Electricity & Broadband Bills
        ("TXN-20261117-C7D8E9", r_acc, None, "WITHDRAWAL", 5000.00, 40000.00, None, "SUCCESS", "BESCOM Electricity & Broadband Bill Settlement", now - timedelta(days=1)),
        # Rohan ATM Cash
        ("TXN-20261118-D8E9F1", r_acc, None, "WITHDRAWAL", 8000.00, 32000.00, None, "SUCCESS", "Cash Withdrawal at Branch Teller", now - timedelta(hours=6)),
        # Priya Business Payment
        ("TXN-20261118-E9F1A2", p_acc, None, "WITHDRAWAL", 20000.00, 85500.00, None, "SUCCESS", "Vendor Advance Payment Disbursement", now - timedelta(hours=3))
    ]

    for ref, s_id, r_id, t_type, amt, s_bal, r_bal, st, desc, dt in transactions_data:
        dt_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("""
            INSERT INTO transactions (
                transaction_ref, sender_account_id, receiver_account_id,
                transaction_type, amount, sender_balance_after, receiver_balance_after,
                status, description, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (ref, s_id, r_id, t_type, amt, s_bal, r_bal, st, desc, dt_str))

    print("[*] Creating administrative audit logs...")
    audit_data = [
        (admin_id, "SYSTEM_INIT", "SYSTEM", "0", "Bharat National Bank CBS Core Banking System Ledger initialized.", "127.0.0.1", now - timedelta(days=60)),
        (admin_id, "ACCOUNT_STATUS_CHANGE", "ACCOUNT", str(v_acc), "Admin placed temporary compliance FROZEN hold on Account #1001202404.", "127.0.0.1", now - timedelta(days=5)),
        (user_ids['aaravs'], "SUCCESSFUL_LOGIN", "AUTH", str(user_ids['aaravs']), "Customer Aarav Sharma logged in via NetBanking portal.", "192.168.1.15", now - timedelta(days=1)),
        (user_ids['priyap'], "SUCCESSFUL_LOGIN", "AUTH", str(user_ids['priyap']), "Customer Priya Patel authenticated from Mobile Banking.", "192.168.1.42", now - timedelta(hours=4))
    ]

    for uid, action, target_type, target_id, details, ip, dt in audit_data:
        dt_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("""
            INSERT INTO audit_logs (user_id, action, target_type, target_id, details, ip_address, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (uid, action, target_type, target_id, details, ip, dt_str))

    conn.commit()
    conn.close()
    print("[✔] Bharat National Bank database seeded successfully!")
    print("\n" + "="*65)
    print("DEMO CREDENTIALS (INDIAN BANKING SIMULATOR):")
    print("="*65)
    print("1. Bank Admin Access:")
    print("   Username: admin")
    print("   Password: Admin@123")
    print("   Role: Head Office Administrator (Connaught Place, New Delhi)")
    print("\n2. Customer Demo Access (Indian Rupees ₹):")
    print("   Username: aaravs        (Password: Customer@123, Account: 1001202401, Balance: ₹1,45,000.00)")
    print("   Username: priyap        (Password: Customer@123, Account: 1001202402, Balance: ₹85,500.00)")
    print("   Username: rohanv        (Password: Customer@123, Account: 1001202403, Balance: ₹32,000.00)")
    print("   Username: vikrams       (Password: Customer@123, Account: 1001202404, Balance: ₹15,000.00 - FROZEN)")
    print("="*65 + "\n")

if __name__ == '__main__':
    seed_database()
