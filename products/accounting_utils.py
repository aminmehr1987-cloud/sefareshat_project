"""
Accounting Utilities - Automatic Voucher Creation System
سیستم خودکار ایجاد اسناد حسابداری
"""

from django.db import transaction
from django.utils import timezone
from django.contrib.auth.models import User
from .models import (
    Voucher, VoucherItem, Account, FinancialYear, Currency,
    FinancialOperation, Receipt, PurchaseInvoice, SalesInvoice,
    BankAccount, CashRegister, Fund, Customer, CustomerBalance
)
import jdatetime


class AccountingVoucherManager:
    """
    مدیریت خودکار اسناد حسابداری
    """
    
    def __init__(self):
        self.default_currency = None
        self.current_financial_year = None
        self._initialize_defaults()
    
    def _initialize_defaults(self):
        """Initialize default currency and financial year"""
        try:
            self.default_currency = Currency.objects.filter(is_default=True).first()
            if not self.default_currency:
                self.default_currency = Currency.objects.create(
                    code='IRR',
                    name='ریال',
                    symbol='﷼',
                    is_default=True,
                    exchange_rate=1
                )
            
            # Get current financial year
            current_date = timezone.now().date()
            self.current_financial_year = FinancialYear.objects.filter(
                start_date__lte=current_date,
                end_date__gte=current_date,
                is_active=True
            ).first()
            
            if not self.current_financial_year:
                # Create default financial year if none exists
                current_year = current_date.year
                self.current_financial_year = FinancialYear.objects.create(
                    year=str(current_year),
                    start_date=f"{current_year}-03-21",
                    end_date=f"{current_year + 1}-03-20",
                    is_active=True,
                    created_by=User.objects.first()
                )
                
        except Exception as e:
            print(f"Error initializing accounting defaults: {e}")
    
    def get_next_voucher_number(self):
        """Get next voucher number for current financial year"""
        if not self.current_financial_year:
            self._initialize_defaults()
            if not self.current_financial_year:
                return "0001"
        
        last_voucher = Voucher.objects.filter(
            financial_year=self.current_financial_year
        ).order_by('-number').first()
        
        if last_voucher and last_voucher.number:
            try:
                last_number = int(last_voucher.number)
                return f"{last_number + 1:04d}"
            except ValueError:
                return "0001"
        return "0001"
    
    def create_voucher_from_financial_operation(self, operation):
        """
        Create voucher from financial operation
        ایجاد سند حسابداری از عملیات مالی
        """
        existing_voucher = Voucher.objects.filter(items__reference_id=str(operation.id)).first()
        if existing_voucher:
            return existing_voucher
        
        try:
            with transaction.atomic():
                # اطمینان از وجود financial_year
                if not self.current_financial_year:
                    self._initialize_defaults()
                
                # اطمینان از وجود created_by
                created_by = operation.created_by
                if not created_by:
                    created_by = User.objects.first()
                
                # Create voucher
                voucher = Voucher.objects.create(
                    financial_year=self.current_financial_year,
                    number=self.get_next_voucher_number(),
                    date=operation.date,
                    type='PERMANENT',
                    description=f"سند {operation.get_operation_type_display()} - {operation.operation_number}",
                    created_by=created_by
                )
                
                # Create voucher items based on operation type
                self._create_voucher_items_for_operation(operation, voucher)
                
                return voucher
                
        except Exception as e:
            print(f"Error creating voucher for operation {operation.id}: {e}")
            return None
    
    def _create_voucher_items_for_operation(self, operation, voucher):
        """Create voucher items based on operation type"""
        
        if operation.operation_type == 'RECEIVE_FROM_CUSTOMER':
            self._create_receive_from_customer_items(operation, voucher)
        elif operation.operation_type == 'PAY_TO_CUSTOMER':
            self._create_pay_to_customer_items(operation, voucher)
        elif operation.operation_type == 'RECEIVE_FROM_BANK':
            self._create_receive_from_bank_items(operation, voucher)
        elif operation.operation_type == 'PAY_TO_BANK':
            self._create_pay_to_bank_items(operation, voucher)
        elif operation.operation_type == 'BANK_TRANSFER':
            self._create_bank_transfer_items(operation, voucher)
        elif operation.operation_type == 'CASH_WITHDRAWAL':
            self._create_cash_withdrawal_items(operation, voucher)
        elif operation.operation_type == 'PAYMENT_TO_CASH':
            self._create_payment_to_cash_items(operation, voucher)
        elif operation.operation_type == 'PAYMENT_FROM_CASH':
            self._create_payment_from_cash_items(operation, voucher)
        elif operation.operation_type == 'CAPITAL_INVESTMENT':
            self._create_capital_investment_items(operation, voucher)
        
    def create_voucher_from_petty_cash_operation(self, operation):
        """
        Create voucher from petty cash operation.
        This logic is moved from the old `create_petty_cash_voucher` function.
        """
        try:
            with transaction.atomic():
                if not self.current_financial_year:
                    self._initialize_defaults()
                
                created_by = operation.created_by or User.objects.first()
                
                voucher = Voucher.objects.create(
                    financial_year=self.current_financial_year,
                    number=self.get_next_voucher_number(),
                    date=operation.date,
                    type='PERMANENT',
                    description=f"سند عملیات تنخواه - {operation.get_operation_type_display()} - {operation.operation_number}",
                    created_by=created_by,
                    is_confirmed=True,
                    confirmed_by=created_by,
                    confirmed_at=timezone.now()
                )
                
                petty_cash_account = self._get_or_create_petty_cash_account()
                expense_account = self._get_or_create_expense_account()

                if operation.operation_type == 'ADD':
                    source_account = None
                    if operation.source_fund:
                        source_account = self._get_or_create_cash_account()
                    elif operation.source_bank_account:
                        source_account = self._get_or_create_bank_account(
                            operation.source_bank_account.bank.name,
                            operation.source_bank_account.account_number
                        )
                    
                    if source_account:
                        # Debit Petty Cash, Credit Source (Cash/Bank)
                        VoucherItem.objects.create(
                            voucher=voucher, account=petty_cash_account,
                            description=f"افزودن به تنخواه از {source_account.name}",
                            debit=operation.amount, credit=0,
                            reference_id=str(operation.id), reference_type='PettyCashOperation'
                        )
                        VoucherItem.objects.create(
                            voucher=voucher, account=source_account,
                            description=f"برداشت برای تنخواه",
                            debit=0, credit=operation.amount,
                            reference_id=str(operation.id), reference_type='PettyCashOperation'
                        )
                
                elif operation.operation_type == 'WITHDRAW':
                    # Debit Expense, Credit Petty Cash
                    VoucherItem.objects.create(
                        voucher=voucher, account=expense_account,
                        description=f"هزینه از تنخواه: {operation.get_reason_display()}",
                        debit=operation.amount, credit=0,
                        reference_id=str(operation.id), reference_type='PettyCashOperation'
                    )
                    VoucherItem.objects.create(
                        voucher=voucher, account=petty_cash_account,
                        description=f"برداشت از تنخواه بابت {operation.get_reason_display()}",
                        debit=0, credit=operation.amount,
                        reference_id=str(operation.id), reference_type='PettyCashOperation'
                    )
                
                return voucher

        except Exception as e:
            print(f"Error creating voucher for petty cash operation {operation.id}: {e}")
            return None

    def _get_debit_credit_accounts(self, operation):
        """
        Determines the debit and credit accounts based on the financial operation type.
        This is the core of the double-entry logic.
        """
        customer_account = self._get_or_create_customer_account(operation.customer) if operation.customer else self._get_or_create_general_account("حساب‌های دریافتنی/پرداختنی", "1300")
        cash_account = self._get_or_create_cash_account()
        bank_account = self._get_or_create_bank_account(operation.bank_name, operation.account_number) if operation.bank_name else cash_account
        capital_account = self._get_or_create_capital_account()
        expense_account = self._get_or_create_expense_account()

        # Default to cash/customer for unknown types
        debit_account = cash_account
        credit_account = customer_account

        op_type = operation.operation_type
        payment_method = operation.payment_method

        # Determine the primary account (cash or bank) based on payment method
        primary_account = bank_account if payment_method in ['bank_transfer', 'pos'] else cash_account

        if op_type == 'RECEIVE_FROM_CUSTOMER':
            debit_account = primary_account
            credit_account = customer_account
        elif op_type == 'PAY_TO_CUSTOMER':
            debit_account = customer_account
            credit_account = primary_account
        elif op_type == 'RECEIVE_FROM_BANK': # برداشت از بانک و واریز به صندوق
            debit_account = cash_account
            credit_account = bank_account
        elif op_type == 'PAY_TO_BANK': # پرداخت از صندوق به بانک
            debit_account = bank_account
            credit_account = cash_account
        elif op_type == 'BANK_TRANSFER':
            # حواله از حساب بانکی شرکت به یک مشتری
            # بدهکار: حساب مشتری
            # بستانکار: حساب بانکی شرکت
            debit_account = customer_account
            credit_account = bank_account
        elif op_type == 'CASH_WITHDRAWAL': # Same as RECEIVE_FROM_BANK
            debit_account = cash_account
            credit_account = bank_account
        elif op_type == 'PAYMENT_TO_CASH': # واریز وجه به صندوق (مثلا از درآمد نامشخص)
            debit_account = cash_account
            credit_account = self._get_or_create_income_account()
        elif op_type == 'PAYMENT_FROM_CASH': # پرداخت هزینه از صندوق
            debit_account = expense_account
            credit_account = cash_account
        elif op_type == 'CAPITAL_INVESTMENT': # افزایش سرمایه
            debit_account = primary_account
            credit_account = capital_account

        return debit_account, credit_account


    def _create_receive_from_customer_items(self, operation, voucher):
        """Create voucher items for receiving from customer"""
        debit_account, credit_account = self._get_debit_credit_accounts(operation)
        VoucherItem.objects.create(
            voucher=voucher, account=debit_account,
            description=f"دریافت از {operation.customer.get_full_name()}",
            debit=operation.amount, credit=0,
            reference_id=str(operation.id), reference_type='FinancialOperation'
        )
        VoucherItem.objects.create(
            voucher=voucher, account=credit_account,
            description=f"تسویه حساب مشتری {operation.customer.get_full_name()}",
            debit=0, credit=operation.amount,
            reference_id=str(operation.id), reference_type='FinancialOperation'
        )

    def _create_pay_to_customer_items(self, operation, voucher):
        """Create voucher items for paying to customer"""
        debit_account, credit_account = self._get_debit_credit_accounts(operation)
        VoucherItem.objects.create(
            voucher=voucher, account=debit_account,
            description=f"پرداخت به {operation.customer.get_full_name()}",
            debit=operation.amount, credit=0,
            reference_id=str(operation.id), reference_type='FinancialOperation'
        )
        VoucherItem.objects.create(
            voucher=voucher, account=credit_account,
            description=f"پرداخت از {credit_account.name}",
            debit=0, credit=operation.amount,
            reference_id=str(operation.id), reference_type='FinancialOperation'
        )
    
    def _create_receive_from_bank_items(self, operation, voucher):
        debit_account, credit_account = self._get_debit_credit_accounts(operation)
        VoucherItem.objects.create(
            voucher=voucher, account=debit_account,
            description=f"برداشت از بانک {operation.bank_name}",
            debit=operation.amount, credit=0,
            reference_id=str(operation.id), reference_type='FinancialOperation'
        )
        VoucherItem.objects.create(
            voucher=voucher, account=credit_account,
            description=f"واریز به صندوق از بانک {operation.bank_name}",
            debit=0, credit=operation.amount,
            reference_id=str(operation.id), reference_type='FinancialOperation'
        )

    def _create_pay_to_bank_items(self, operation, voucher):
        debit_account, credit_account = self._get_debit_credit_accounts(operation)
        VoucherItem.objects.create(
            voucher=voucher, account=debit_account,
            description=f"واریز به بانک {operation.bank_name}",
            debit=operation.amount, credit=0,
            reference_id=str(operation.id), reference_type='FinancialOperation'
        )
        VoucherItem.objects.create(
            voucher=voucher, account=credit_account,
            description=f"برداشت از صندوق برای واریز به بانک",
            debit=0, credit=operation.amount,
            reference_id=str(operation.id), reference_type='FinancialOperation'
        )

    def _create_bank_transfer_items(self, operation, voucher):
        """Create voucher items for a bank transfer to a customer."""
        debit_account, credit_account = self._get_debit_credit_accounts(operation)

        # Debit the customer's account
        VoucherItem.objects.create(
            voucher=voucher,
            account=debit_account,
            description=f"حواله به مشتری: {operation.customer.get_full_name()} از حساب {credit_account.name}",
            debit=operation.amount,
            credit=0,
            reference_id=str(operation.id),
            reference_type='FinancialOperation'
        )
        
        # Credit the source bank account
        VoucherItem.objects.create(
            voucher=voucher,
            account=credit_account,
            description=f"برداشت بابت حواله به مشتری: {operation.customer.get_full_name()}",
            debit=0,
            credit=operation.amount,
            reference_id=str(operation.id),
            reference_type='FinancialOperation'
        )

    def _create_cash_withdrawal_items(self, operation, voucher):
        self._create_receive_from_bank_items(operation, voucher)

    def _create_payment_to_cash_items(self, operation, voucher):
        debit_account, credit_account = self._get_debit_credit_accounts(operation)
        VoucherItem.objects.create(
            voucher=voucher, account=debit_account,
            description=f"واریز وجه به صندوق",
            debit=operation.amount, credit=0,
            reference_id=str(operation.id), reference_type='FinancialOperation'
        )
        VoucherItem.objects.create(
            voucher=voucher, account=credit_account,
            description=f"منبع واریز به صندوق",
            debit=0, credit=operation.amount,
            reference_id=str(operation.id), reference_type='FinancialOperation'
        )

    def _create_payment_from_cash_items(self, operation, voucher):
        debit_account, credit_account = self._get_debit_credit_accounts(operation)
        VoucherItem.objects.create(
            voucher=voucher, account=debit_account,
            description=f"پرداخت هزینه از صندوق",
            debit=operation.amount, credit=0,
            reference_id=str(operation.id), reference_type='FinancialOperation'
        )
        VoucherItem.objects.create(
            voucher=voucher, account=credit_account,
            description=f"برداشت از صندوق بابت هزینه",
            debit=0, credit=operation.amount,
            reference_id=str(operation.id), reference_type='FinancialOperation'
        )

    def _create_capital_investment_items(self, operation, voucher):
        debit_account, credit_account = self._get_debit_credit_accounts(operation)
        VoucherItem.objects.create(
            voucher=voucher, account=debit_account,
            description=f"افزایش سرمایه",
            debit=operation.amount, credit=0,
            reference_id=str(operation.id), reference_type='FinancialOperation'
        )
        VoucherItem.objects.create(
            voucher=voucher, account=credit_account,
            description=f"ثبت آورده نقدی/بانکی",
            debit=0, credit=operation.amount,
            reference_id=str(operation.id), reference_type='FinancialOperation'
        )
    
    def _get_or_create_account(self, name, code, group_name, group_code, group_type):
        """A more generic and robust way to get or create an account."""
        from .models import AccountGroup
        group, _ = AccountGroup.objects.get_or_create(
            code=group_code,
            defaults={'name': group_name, 'type': group_type}
        )
        account, _ = Account.objects.get_or_create(
            code=code,
            defaults={
                'group': group,
                'name': name,
                'level': 'TAFSILI' if len(code) > 4 else 'MOEIN',
                'currency': self.default_currency,
                'description': f"حساب خودکار {name}"
            }
        )
        return account

    def _get_or_create_customer_account(self, customer):
        if not customer:
            return self._get_or_create_account("حساب مشتریان عمومی", "1310000", "حساب‌های دریافتنی", "1310", "ASSET")
        
        # Construct a unique code for the customer
        customer_code = f"1310{str(customer.id).zfill(3)}"
        return self._get_or_create_account(f"حساب {customer.get_full_name()}", customer_code, "حساب‌های دریافتنی", "1310", "ASSET")

    def _get_or_create_cash_account(self):
        return self._get_or_create_account("صندوق", "1110001", "موجودی نقد", "1110", "ASSET")

    def _get_or_create_bank_account(self, bank_name, account_number):
        if not bank_name:
            return self._get_or_create_account("بانک عمومی", "1120000", "بانک‌ها", "1120", "ASSET")

        # Attempt to find the specific BankAccount model to get its ID
        try:
            bank_model = BankAccount.objects.get(account_number=account_number, bank__name=bank_name)
            bank_code = f"1120{str(bank_model.id).zfill(3)}"
            account_name = f"بانک {bank_name} - {account_number}"
        except BankAccount.DoesNotExist:
            bank_code = f"1120999" # Fallback code
            account_name = f"بانک {bank_name}"

        return self._get_or_create_account(account_name, bank_code, "بانک‌ها", "1120", "ASSET")

    def _get_or_create_expense_account(self):
        return self._get_or_create_account("هزینه‌های عمومی و اداری", "5300001", "هزینه‌های اداری", "5300", "EXPENSE")

    def _get_or_create_income_account(self):
        return self._get_or_create_account("درآمدهای متفرقه", "4300001", "درآمدهای غیرعملیاتی", "4300", "REVENUE")

    def _get_or_create_capital_account(self):
        return self._get_or_create_account("سرمایه", "3110001", "سرمایه", "3110", "EQUITY")
        
    def _get_or_create_petty_cash_account(self):
        return self._get_or_create_account("تنخواه گردان", "1130001", "تنخواه گردان", "1130", "ASSET")

    def _get_or_create_sales_account(self):
        return self._get_or_create_account("فروش کالا", "4110001", "فروش کالا", "4110", "REVENUE")

    def _get_or_create_purchase_account(self):
        return self._get_or_create_account("بهای تمام شده کالای فروش رفته", "5110001", "بهای تمام شده کالای فروش رفته", "5110", "EXPENSE")


# Global instance
accounting_manager = AccountingVoucherManager()

def reset_accounting_manager():
    global accounting_manager
    accounting_manager = AccountingVoucherManager()


def create_voucher_for_financial_operation(operation):
    """Create voucher for financial operation"""
    return accounting_manager.create_voucher_from_financial_operation(operation)


def create_voucher_for_receipt(receipt):
    """Create voucher for receipt"""
    return accounting_manager.create_voucher_from_receipt(receipt)


def create_voucher_for_invoice(invoice, invoice_type):
    """Create voucher for invoice"""
    return accounting_manager.create_voucher_from_invoice(invoice, invoice_type)


def create_voucher_for_petty_cash_operation(petty_cash_operation):
    """Create voucher for petty cash operation"""
    return accounting_manager.create_voucher_from_petty_cash_operation(petty_cash_operation) 