from django.core.management.base import BaseCommand
from django.db import transaction
from products.models import FinancialOperation, Customer, Fund, Voucher, VoucherItem, User, FinancialYear, Currency
from decimal import Decimal
import jdatetime

class Command(BaseCommand):
    help = 'Verifies the automatic creation of vouchers and fund balance updates after a financial operation.'

    def handle(self, *args, **options):
        self.stdout.write("Starting data persistence verification...")

        try:
            with transaction.atomic():
                # --- Setup Phase ---
                self.stdout.write("1. Setting up test data...")

                # Get or create a user
                user, _ = User.objects.get_or_create(username='testuser')

                # Get or create a customer
                customer, _ = Customer.objects.get_or_create(
                    mobile='09123456789',
                    defaults={'first_name': 'Test', 'last_name': 'Customer', 'created_by': user}
                )
                self.stdout.write(f"   - Using Customer: {customer.get_full_name()}")

                # Get or create the main cash fund
                cash_fund, _ = Fund.objects.get_or_create(
                    fund_type='CASH',
                    name='صندوق نقدی',
                    defaults={'initial_balance': 0, 'created_by': user}
                )
                self.stdout.write(f"   - Using Fund: {cash_fund.name}")

                # Record initial balance
                initial_balance = cash_fund.current_balance
                self.stdout.write(f"   - Initial Fund Balance: {initial_balance:,.2f}")

                # Get or create a financial year
                FinancialYear.objects.get_or_create(
                    year='1403',
                    defaults={
                        'start_date': '2024-03-20',
                        'end_date': '2025-03-20',
                        'is_active': True,
                        'created_by': user
                    }
                )
                # Get or create a currency
                Currency.objects.get_or_create(code='IRR', defaults={'name': 'Rial', 'symbol': 'IRR', 'is_default': True})


                # --- Action Phase ---
                self.stdout.write("\n2. Creating a 'Receive from Customer' Financial Operation...")
                operation_amount = Decimal('500000.00')
                
                operation = FinancialOperation.objects.create(
                    operation_type='RECEIVE_FROM_CUSTOMER',
                    date=jdatetime.date.today(),
                    amount=operation_amount,
                    description='Test operation for verification',
                    status='CONFIRMED',
                    customer=customer,
                    fund=cash_fund,
                    payment_method='cash',
                    created_by=user,
                    confirmed_by=user,
                    confirmed_at=jdatetime.datetime.now()
                )
                self.stdout.write(f"   - Created FinancialOperation: {operation.operation_number} for amount {operation_amount:,.2f}")


                # --- Verification Phase ---
                self.stdout.write("\n3. Verifying results...")

                # Verify Voucher creation
                self.stdout.write("   - Verifying Voucher creation...")
                try:
                    voucher = Voucher.objects.get(items__reference_id=str(operation.id))
                    self.stdout.write(self.style.SUCCESS(f"   ✔ SUCCESS: Voucher {voucher.number} was created automatically."))

                    # Verify Voucher Items
                    voucher_items = voucher.items.all()
                    if voucher_items.count() == 2:
                        self.stdout.write(self.style.SUCCESS("   ✔ SUCCESS: Voucher has 2 items."))
                        
                        debit = voucher_items.filter(debit=operation_amount).first()
                        credit = voucher_items.filter(credit=operation_amount).first()

                        if debit and credit:
                             self.stdout.write(self.style.SUCCESS("   ✔ SUCCESS: Correct debit and credit amounts found."))
                        else:
                            self.stdout.write(self.style.ERROR("   ✘ ERROR: Debit or credit item with correct amount not found."))
                            raise Exception("Voucher item amount mismatch.")

                    else:
                        self.stdout.write(self.style.ERROR(f"   ✘ ERROR: Expected 2 voucher items, but found {voucher_items.count()}."))
                        raise Exception("Incorrect number of voucher items.")

                except Voucher.DoesNotExist:
                    self.stdout.write(self.style.ERROR("   ✘ ERROR: No voucher was created for the operation."))
                    raise Exception("Voucher not created.")
                
                # Verify Fund Balance update
                self.stdout.write("   - Verifying Fund balance update...")
                cash_fund.refresh_from_db()
                expected_balance = initial_balance + operation_amount
                if cash_fund.current_balance == expected_balance:
                    self.stdout.write(self.style.SUCCESS(f"   ✔ SUCCESS: Fund balance updated correctly to {cash_fund.current_balance:,.2f}."))
                else:
                    self.stdout.write(self.style.ERROR(f"   ✘ ERROR: Fund balance is incorrect. Expected {expected_balance:,.2f}, but got {cash_fund.current_balance:,.2f}."))
                    raise Exception("Fund balance incorrect.")

                self.stdout.write(self.style.SUCCESS("\nVerification complete. Rolling back transaction."))
                # By raising an exception in a transaction block, we roll back the changes.
                raise Exception("ROLLBACK")

        except Exception as e:
            if str(e) == "ROLLBACK":
                self.stdout.write(self.style.SUCCESS("\nTest finished successfully and database has been rolled back to its original state."))
            else:
                self.stdout.write(self.style.ERROR(f"\nAn error occurred during verification: {e}"))
                self.stdout.write(self.style.ERROR("Transaction has been rolled back."))
