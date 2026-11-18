import os
import unittest
from app import create_app
from app.config import Config
from app.db import init_db, get_db
from app.models.user import UserModel
from app.models.account import AccountModel
from app.models.transaction import TransactionModel
from app.models.audit import AuditModel
from seed_data import seed_database

class BankingSystemTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()
        seed_database()

    def setUp(self):
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_01_user_authentication(self):
        """Test Indian customer & admin login with valid and invalid credentials."""
        user = UserModel.get_by_username('aaravs')
        self.assertIsNotNone(user)
        self.assertFalse(UserModel.verify_password(user['password_hash'], 'WrongPassword'))
        self.assertTrue(UserModel.verify_password(user['password_hash'], 'Customer@123'))

        admin = UserModel.get_by_username('admin')
        self.assertIsNotNone(admin)
        self.assertEqual(admin['role'], 'admin')
        self.assertTrue(UserModel.verify_password(admin['password_hash'], 'Admin@123'))

    def test_02_account_generation_and_balance(self):
        """Verify unique account number generation and INR balance lookup."""
        user = UserModel.get_by_username('aaravs')
        accounts = AccountModel.get_by_user_id(user['id'])
        self.assertGreaterEqual(len(accounts), 1)
        primary = accounts[0]
        self.assertEqual(primary['account_number'], '1001202401')
        self.assertGreater(float(primary['balance']), 0.0)
        self.assertEqual(primary['currency'], 'INR')

    def test_03_deposit_atomic_transaction(self):
        """Test depositing INR money increases account balance atomically."""
        user = UserModel.get_by_username('aaravs')
        account = AccountModel.get_primary_account(user['id'])
        initial_balance = float(account['balance'])

        txn, err = TransactionModel.deposit(account['id'], 5000.00, "Automated Test CDM Deposit")
        self.assertIsNone(err)
        self.assertIsNotNone(txn)
        self.assertEqual(txn['status'], 'SUCCESS')
        self.assertEqual(float(txn['amount']), 5000.00)

        # Verify balance updated in DB
        refreshed = AccountModel.get_by_id(account['id'])
        self.assertAlmostEqual(float(refreshed['balance']), initial_balance + 5000.00, places=2)

    def test_04_withdraw_insufficient_funds_rejection(self):
        """Test withdrawal greater than balance is rejected without deducting money."""
        # Use Rohan's account (balance is ₹32,000, withdrawal limit is ₹1,00,000)
        rohan = UserModel.get_by_username('rohanv')
        account = AccountModel.get_primary_account(rohan['id'])
        initial_balance = float(account['balance'])

        # Try withdrawing ₹50,000 (well within ₹1,00,000 limit, but exceeds available balance)
        overdraft_amount = 50000.00
        txn, err = TransactionModel.withdraw(account['id'], overdraft_amount, "Impossible Overdraft")
        self.assertIsNotNone(err)
        self.assertIn("Insufficient funds", err)
        self.assertIsNone(txn)

        # Also test limit exceeding (limit is ₹1,00,000.00)
        txn2, err2 = TransactionModel.withdraw(account['id'], 150000.00, "Exceeds Limit")
        self.assertIsNotNone(err2)
        self.assertIn("exceeds maximum limit", err2)
        self.assertIsNone(txn2)

        # Ensure balance was NOT modified
        refreshed = AccountModel.get_by_id(account['id'])
        self.assertEqual(float(refreshed['balance']), initial_balance)

    def test_05_successful_withdrawal(self):
        """Test valid ATM withdrawal in INR deducts balance and records transaction."""
        user = UserModel.get_by_username('aaravs')
        account = AccountModel.get_primary_account(user['id'])
        initial_balance = float(account['balance'])

        txn, err = TransactionModel.withdraw(account['id'], 2000.00, "RuPay ATM Cash Withdrawal")
        self.assertIsNone(err)
        self.assertIsNotNone(txn)
        self.assertEqual(txn['status'], 'SUCCESS')

        refreshed = AccountModel.get_by_id(account['id'])
        self.assertAlmostEqual(float(refreshed['balance']), initial_balance - 2000.00, places=2)

    def test_06_transfer_atomic_dual_update(self):
        """Test IMPS transfer between Aarav and Priya deducts sender and credits receiver."""
        aarav = UserModel.get_by_username('aaravs')
        priya = UserModel.get_by_username('priyap')

        aarav_acc = AccountModel.get_primary_account(aarav['id'])
        priya_acc = AccountModel.get_primary_account(priya['id'])

        aarav_initial = float(aarav_acc['balance'])
        priya_initial = float(priya_acc['balance'])
        transfer_amt = 5000.00

        txn, err = TransactionModel.transfer(
            sender_account_id=aarav_acc['id'],
            receiver_account_number=priya_acc['account_number'],
            amount=transfer_amt,
            description="Apartment Maintenance Fee via IMPS"
        )
        self.assertIsNone(err)
        self.assertIsNotNone(txn)
        self.assertEqual(txn['status'], 'SUCCESS')

        # Verify both balances atomically updated
        aarav_refreshed = AccountModel.get_by_id(aarav_acc['id'])
        priya_refreshed = AccountModel.get_by_id(priya_acc['id'])

        self.assertAlmostEqual(float(aarav_refreshed['balance']), aarav_initial - transfer_amt, places=2)
        self.assertAlmostEqual(float(priya_refreshed['balance']), priya_initial + transfer_amt, places=2)

    def test_07_transfer_to_invalid_or_self_account(self):
        """Test transferring to non-existent account or self is rejected."""
        aarav = UserModel.get_by_username('aaravs')
        aarav_acc = AccountModel.get_primary_account(aarav['id'])

        # 1. Invalid recipient
        txn, err = TransactionModel.transfer(aarav_acc['id'], '9999999999', 500.00, "To Fake Account")
        self.assertIsNotNone(err)
        self.assertIn("not found", err)

        # 2. Self-transfer
        txn, err = TransactionModel.transfer(aarav_acc['id'], aarav_acc['account_number'], 500.00, "To Self")
        self.assertIsNotNone(err)
        self.assertIn("Self-transfers to the same account are not permitted", err)

    def test_08_frozen_account_enforcement(self):
        """Test frozen accounts (Vikram Singh) cannot initiate transfers or withdrawals."""
        vikram = UserModel.get_by_username('vikrams')
        vikram_acc = AccountModel.get_primary_account(vikram['id'])
        self.assertEqual(vikram_acc['status'], 'FROZEN')

        # Withdrawal attempt
        txn, err = TransactionModel.withdraw(vikram_acc['id'], 500.00, "Frozen Withdrawal Attempt")
        self.assertIsNotNone(err)
        self.assertIn("FROZEN", err)

        # Transfer attempt
        priya_acc = AccountModel.get_by_number('1001202402')
        txn, err = TransactionModel.transfer(vikram_acc['id'], priya_acc['account_number'], 500.00, "Frozen Transfer")
        self.assertIsNotNone(err)
        self.assertIn("FROZEN", err)

    def test_09_statement_generation(self):
        """Test account statement compiles correct credits, debits, and running balance in INR."""
        aarav = UserModel.get_by_username('aaravs')
        aarav_acc = AccountModel.get_primary_account(aarav['id'])

        stmt = TransactionModel.get_account_statement_data(aarav_acc['id'])
        self.assertGreater(stmt['count'], 0)
        self.assertGreater(stmt['total_inflow'], 0)
        self.assertGreater(stmt['total_outflow'], 0)

    def test_10_pdf_generation(self):
        """Test receipt and statement PDF generators produce valid non-empty byte streams."""
        from app.utils.pdf_generator import generate_receipt_pdf, generate_statement_pdf
        txns = TransactionModel.get_all_transactions(limit=1)
        self.assertTrue(len(txns) > 0)
        receipt_buf = generate_receipt_pdf(txns[0])
        self.assertGreater(receipt_buf.getbuffer().nbytes, 1000)

        aarav = UserModel.get_by_username('aaravs')
        aarav_acc = AccountModel.get_primary_account(aarav['id'])
        stmt_data = TransactionModel.get_account_statement_data(aarav_acc['id'])
        stmt_buf = generate_statement_pdf(aarav_acc, stmt_data)
        self.assertGreater(stmt_buf.getbuffer().nbytes, 1000)

    def test_11_admin_kpis_and_audit(self):
        """Test Indian banking liquidity KPI aggregation and audit logs."""
        liquidity = AccountModel.get_bank_liquidity_summary()
        self.assertGreater(liquidity['total_liquidity'], 0.0)
        self.assertGreaterEqual(liquidity['active_accounts'], 3)
        self.assertGreaterEqual(liquidity['frozen_accounts'], 1)

        logs = AuditModel.get_logs(limit=10)
        self.assertGreater(len(logs), 0)

if __name__ == '__main__':
    unittest.main()
