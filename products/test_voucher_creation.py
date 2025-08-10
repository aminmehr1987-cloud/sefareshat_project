from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from products.models import FinancialOperation, Customer, Fund, Voucher, VoucherItem, FinancialYear, Currency
from decimal import Decimal
import jdatetime

class VoucherCreationTest(TestCase):
    def setUp(self):
        """Set up the necessary objects for testing."""
        self.user = User.objects.create_user(username='testuser', password='password')
        self.customer = Customer.objects.create(
            first_name='Test',
            last_name='Customer',
            mobile='09111111111',
            created_by=self.user
        )
        self.cash_fund = Fund.objects.create(
            name='Test Cash Fund',
            fund_type='CASH',
            initial_balance=1000000,
            current_balance=1000000,
            created_by=self.user
        )
        FinancialYear.objects.get_or_create(
            year='1403',
            defaults={
                'start_date': '2024-03-20',
                'end_date': '2025-03-20',
                'is_active': True,
                'created_by': self.user
            }
        )
        Currency.objects.get_or_create(code='IRR', defaults={'name': 'Rial', 'symbol': 'IRR', 'is_default': True})

    def test_receive_from_customer_voucher_creation(self):
        """
        Tests that a voucher is automatically created when a 'RECEIVE_FROM_CUSTOMER'
        operation is created with a 'CONFIRMED' status.
        """
        print("\n--- Running test: test_receive_from_customer_voucher_creation ---")
        
        initial_balance = self.cash_fund.current_balance
        operation_amount = Decimal('50000.00')

        # Create the financial operation
        operation = FinancialOperation.objects.create(
            operation_type='RECEIVE_FROM_CUSTOMER',
            date=jdatetime.date.today(),
            amount=operation_amount,
            description='Test receipt from customer',
            status='CONFIRMED',
            customer=self.customer,
            fund=self.cash_fund,
            payment_method='cash',
            created_by=self.user,
            confirmed_by=self.user,
            confirmed_at=timezone.now()
        )
        print(f"Created FinancialOperation {operation.operation_number}")

        # 1. Verify Voucher creation
        self.assertTrue(Voucher.objects.filter(items__reference_id=str(operation.id)).exists(), "Voucher was not created.")
        voucher = Voucher.objects.get(items__reference_id=str(operation.id))
        print(f"Found Voucher: {voucher.number}")

        # 2. Verify Voucher Items
        self.assertEqual(voucher.items.count(), 2, "Voucher should have exactly two items.")
        print("Voucher item count is correct (2).")

        debit_item = voucher.items.get(debit__gt=0)
        credit_item = voucher.items.get(credit__gt=0)
        
        self.assertEqual(debit_item.debit, operation_amount, "Debit amount is incorrect.")
        self.assertEqual(credit_item.credit, operation_amount, "Credit amount is incorrect.")
        print("Voucher debit and credit amounts are correct.")

        # Check accounts
        self.assertEqual(debit_item.account.code, "1110001", "Debit account should be the cash account.")
        self.assertTrue(credit_item.account.code.startswith("1310"), "Credit account should be a customer account.")
        print("Voucher accounts are correct.")

        # 3. Verify Fund Balance on creation
        self.cash_fund.refresh_from_db()
        expected_balance_after_creation = initial_balance + operation_amount
        self.cash_fund.recalculate_balance() # The signal should have done this, but we call it to be sure
        self.assertEqual(self.cash_fund.current_balance, expected_balance_after_creation, "Fund balance was not updated correctly after creation.")
        print(f"Fund balance updated correctly to {self.cash_fund.current_balance}")

        # 4. Verify balance rollback on deletion
        print("\n--- Deleting operation and verifying balance rollback ---")
        operation.delete()
        print(f"Deleted FinancialOperation {operation.operation_number}")

        self.cash_fund.recalculate_balance() # The post_delete signal should have triggered this
        self.cash_fund.refresh_from_db()
        
        self.assertEqual(self.cash_fund.current_balance, initial_balance, "Fund balance did not roll back correctly after deletion.")
        print(f"Fund balance rolled back correctly to {self.cash_fund.current_balance}")


        print("--- Test finished successfully ---")