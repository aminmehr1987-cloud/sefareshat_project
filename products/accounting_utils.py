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
        elif operation.operation_type == 'PETTY_CASH':
            self._create_petty_cash_items(operation, voucher)
    
    def _create_receive_from_customer_items(self, operation, voucher):
        """Create voucher items for receiving from customer"""
        # Get customer account
        customer_account = self._get_or_create_customer_account(operation.customer)
        
        # Get cash/bank account based on payment method
        cash_account = self._get_or_create_cash_account()
        
        # Create voucher items
        VoucherItem.objects.create(
            voucher=voucher,
            account=cash_account,
            description=f"دریافت از {operation.customer.get_full_name()}",
            debit=operation.amount,
            credit=0,
            reference_id=str(operation.id),
            reference_type='FinancialOperation'
        )
        
        VoucherItem.objects.create(
            voucher=voucher,
            account=customer_account,
            description=f"دریافت از {operation.customer.get_full_name()}",
            debit=0,
            credit=operation.amount,
            reference_id=str(operation.id),
            reference_type='FinancialOperation'
        )
    
    def _create_pay_to_customer_items(self, operation, voucher):
        """Create voucher items for paying to customer"""
        # Get customer account
        customer_account = self._get_or_create_customer_account(operation.customer)
        
        # Get cash/bank account based on payment method
        cash_account = self._get_or_create_cash_account()
        
        # Create voucher items
        VoucherItem.objects.create(
            voucher=voucher,
            account=customer_account,
            description=f"پرداخت به {operation.customer.get_full_name()}",
            debit=operation.amount,
            credit=0,
            reference_id=str(operation.id),
            reference_type='FinancialOperation'
        )
        
        VoucherItem.objects.create(
            voucher=voucher,
            account=cash_account,
            description=f"پرداخت به {operation.customer.get_full_name()}",
            debit=0,
            credit=operation.amount,
            reference_id=str(operation.id),
            reference_type='FinancialOperation'
        )
    
    def _create_receive_from_bank_items(self, operation, voucher):
        """Create voucher items for receiving from bank"""
        # Get bank account
        bank_account = self._get_or_create_bank_account(operation.bank_name, operation.account_number)
        
        # Get cash account
        cash_account = self._get_or_create_cash_account()
        
        # Create voucher items
        VoucherItem.objects.create(
            voucher=voucher,
            account=cash_account,
            description=f"دریافت از بانک {operation.bank_name}",
            debit=operation.amount,
            credit=0,
            reference_id=str(operation.id),
            reference_type='FinancialOperation'
        )
        
        VoucherItem.objects.create(
            voucher=voucher,
            account=bank_account,
            description=f"دریافت از بانک {operation.bank_name}",
            debit=0,
            credit=operation.amount,
            reference_id=str(operation.id),
            reference_type='FinancialOperation'
        )
    
    def _create_pay_to_bank_items(self, operation, voucher):
        """Create voucher items for paying to bank"""
        # Get bank account
        bank_account = self._get_or_create_bank_account(operation.bank_name, operation.account_number)
        
        # Get cash account
        cash_account = self._get_or_create_cash_account()
        
        # Create voucher items
        VoucherItem.objects.create(
            voucher=voucher,
            account=bank_account,
            description=f"پرداخت به بانک {operation.bank_name}",
            debit=operation.amount,
            credit=0,
            reference_id=str(operation.id),
            reference_type='FinancialOperation'
        )
        
        VoucherItem.objects.create(
            voucher=voucher,
            account=cash_account,
            description=f"پرداخت به بانک {operation.bank_name}",
            debit=0,
            credit=operation.amount,
            reference_id=str(operation.id),
            reference_type='FinancialOperation'
        )
    
    def _create_bank_transfer_items(self, operation, voucher):
        """Create voucher items for bank transfer"""
        # Get source and destination bank accounts
        source_bank = self._get_or_create_bank_account(operation.bank_name, operation.account_number)
        dest_bank = self._get_or_create_bank_account("حساب مقصد", "0000000000")
        
        # Create voucher items
        VoucherItem.objects.create(
            voucher=voucher,
            account=dest_bank,
            description=f"حواله بانکی به {operation.bank_name}",
            debit=operation.amount,
            credit=0,
            reference_id=str(operation.id),
            reference_type='FinancialOperation'
        )
        
        VoucherItem.objects.create(
            voucher=voucher,
            account=source_bank,
            description=f"حواله بانکی از {operation.bank_name}",
            debit=0,
            credit=operation.amount,
            reference_id=str(operation.id),
            reference_type='FinancialOperation'
        )
    
    def _create_cash_withdrawal_items(self, operation, voucher):
        """Create voucher items for cash withdrawal from bank"""
        # Get bank and cash accounts
        bank_account = self._get_or_create_bank_account(operation.bank_name, operation.account_number)
        cash_account = self._get_or_create_cash_account()
        
        # Create voucher items
        VoucherItem.objects.create(
            voucher=voucher,
            account=cash_account,
            description=f"برداشت نقدی از بانک {operation.bank_name}",
            debit=operation.amount,
            credit=0,
            reference_id=str(operation.id),
            reference_type='FinancialOperation'
        )
        
        VoucherItem.objects.create(
            voucher=voucher,
            account=bank_account,
            description=f"برداشت نقدی از بانک {operation.bank_name}",
            debit=0,
            credit=operation.amount,
            reference_id=str(operation.id),
            reference_type='FinancialOperation'
        )
    
    def _create_payment_to_cash_items(self, operation, voucher):
        """Create voucher items for payment to cash"""
        # Get cash account
        cash_account = self._get_or_create_cash_account()
        
        # Get expense account
        expense_account = self._get_or_create_expense_account()
        
        # Create voucher items
        VoucherItem.objects.create(
            voucher=voucher,
            account=expense_account,
            description="پرداخت به صندوق",
            debit=operation.amount,
            credit=0,
            reference_id=str(operation.id),
            reference_type='FinancialOperation'
        )
        
        VoucherItem.objects.create(
            voucher=voucher,
            account=cash_account,
            description="پرداخت به صندوق",
            debit=0,
            credit=operation.amount,
            reference_id=str(operation.id),
            reference_type='FinancialOperation'
        )
    
    def _create_payment_from_cash_items(self, operation, voucher):
        """Create voucher items for payment from cash"""
        # Get cash account
        cash_account = self._get_or_create_cash_account()
        
        # Get income account
        income_account = self._get_or_create_income_account()
        
        # Create voucher items
        VoucherItem.objects.create(
            voucher=voucher,
            account=cash_account,
            description="پرداخت از صندوق",
            debit=operation.amount,
            credit=0,
            reference_id=str(operation.id),
            reference_type='FinancialOperation'
        )
        
        VoucherItem.objects.create(
            voucher=voucher,
            account=income_account,
            description="پرداخت از صندوق",
            debit=0,
            credit=operation.amount,
            reference_id=str(operation.id),
            reference_type='FinancialOperation'
        )
    
    def _create_capital_investment_items(self, operation, voucher):
        """Create voucher items for capital investment"""
        # Get cash account
        cash_account = self._get_or_create_cash_account()
        
        # Get capital account
        capital_account = self._get_or_create_capital_account()
        
        # Create voucher items
        VoucherItem.objects.create(
            voucher=voucher,
            account=cash_account,
            description="سرمایه گذاری",
            debit=operation.amount,
            credit=0,
            reference_id=str(operation.id),
            reference_type='FinancialOperation'
        )
        
        VoucherItem.objects.create(
            voucher=voucher,
            account=capital_account,
            description="سرمایه گذاری",
            debit=0,
            credit=operation.amount,
            reference_id=str(operation.id),
            reference_type='FinancialOperation'
        )
    
    def _create_petty_cash_items(self, operation, voucher):
        """Create voucher items for petty cash operations"""
        # Get petty cash account
        petty_cash_account = self._get_or_create_petty_cash_account()
        
        # Get cash account
        cash_account = self._get_or_create_cash_account()
        
        # Create voucher items
        VoucherItem.objects.create(
            voucher=voucher,
            account=petty_cash_account,
            description="عملیات تنخواه",
            debit=operation.amount,
            credit=0,
            reference_id=str(operation.id),
            reference_type='FinancialOperation'
        )
        
        VoucherItem.objects.create(
            voucher=voucher,
            account=cash_account,
            description="عملیات تنخواه",
            debit=0,
            credit=operation.amount,
            reference_id=str(operation.id),
            reference_type='FinancialOperation'
        )
    
    def _get_or_create_customer_account(self, customer):
        """Get or create customer account"""
        if not customer:
            return self._get_or_create_general_account("حساب مشتریان", "1300")
        
        # Try to find existing customer account
        customer_account = Account.objects.filter(
            name__icontains=customer.get_full_name(),
            group__name__icontains="مشتریان"
        ).first()
        
        if customer_account:
            return customer_account
        
        # Create new customer account
        customer_group = self._get_or_create_account_group("حساب‌های دریافتنی", "1300")
        
        return Account.objects.create(
            group=customer_group,
            code=f"1300{customer.id:03d}",
            name=f"حساب {customer.get_full_name()}",
            level='DETAIL',
            currency=self.default_currency,
            description=f"حساب مشتری: {customer.get_full_name()}"
        )
    
    def _get_or_create_cash_account(self):
        """Get or create cash account"""
        cash_account = Account.objects.filter(
            name__icontains="صندوق",
            group__name__icontains="نقدی"
        ).first()
        
        if cash_account:
            return cash_account
        
        # Create cash account
        cash_group = self._get_or_create_account_group("موجودی نقدی", "1100")
        
        # Generate unique code
        existing_codes = Account.objects.filter(
            code__startswith="1100"
        ).values_list('code', flat=True)
        
        if existing_codes:
            max_code = max(existing_codes)
            try:
                last_number = int(max_code[4:])
                new_code = f"1100{last_number + 1:03d}"
            except ValueError:
                new_code = "1100001"
        else:
            new_code = "1100001"
        
        return Account.objects.create(
            group=cash_group,
            code=new_code,
            name="صندوق نقدی",
            level='DETAIL',
            currency=self.default_currency,
            description="حساب صندوق نقدی"
        )
    
    def _get_or_create_bank_account(self, bank_name, account_number):
        """Get or create bank account"""
        if not bank_name:
            bank_name = "بانک عمومی"
        
        bank_account = Account.objects.filter(
            name__icontains=bank_name,
            group__name__icontains="بانکی"
        ).first()
        
        if bank_account:
            return bank_account
        
        # Create bank account
        bank_group = self._get_or_create_account_group("حساب‌های بانکی", "1200")
        
        # Generate unique code
        existing_codes = Account.objects.filter(
            code__startswith="1200"
        ).values_list('code', flat=True)
        
        if existing_codes:
            max_code = max(existing_codes)
            try:
                last_number = int(max_code[4:])
                new_code = f"1200{last_number + 1:03d}"
            except ValueError:
                new_code = "1200001"
        else:
            new_code = "1200001"
        
        return Account.objects.create(
            group=bank_group,
            code=new_code,
            name=f"حساب بانکی {bank_name}",
            level='DETAIL',
            currency=self.default_currency,
            description=f"حساب بانکی {bank_name} - {account_number}"
        )
    
    def _get_or_create_expense_account(self):
        """Get or create expense account"""
        expense_account = Account.objects.filter(
            name__icontains="هزینه",
            group__name__icontains="هزینه"
        ).first()
        
        if expense_account:
            return expense_account
        
        # Create expense account
        expense_group = self._get_or_create_account_group("هزینه‌ها", "5200")
        
        # Generate unique code
        existing_codes = Account.objects.filter(
            code__startswith="5200"
        ).values_list('code', flat=True)
        
        if existing_codes:
            max_code = max(existing_codes)
            try:
                last_number = int(max_code[4:])
                new_code = f"5200{last_number + 1:03d}"
            except ValueError:
                new_code = "5200001"
        else:
            new_code = "5200001"
        
        return Account.objects.create(
            group=expense_group,
            code=new_code,
            name="هزینه‌های عمومی",
            level='DETAIL',
            currency=self.default_currency,
            description="حساب هزینه‌های عمومی"
        )
    
    def _get_or_create_income_account(self):
        """Get or create income account"""
        income_account = Account.objects.filter(
            name__icontains="درآمد",
            group__name__icontains="درآمد"
        ).first()
        
        if income_account:
            return income_account
        
        # Create income account
        income_group = self._get_or_create_account_group("درآمدها", "4100")
        
        # Generate unique code
        existing_codes = Account.objects.filter(
            code__startswith="4100"
        ).values_list('code', flat=True)
        
        if existing_codes:
            max_code = max(existing_codes)
            try:
                last_number = int(max_code[4:])
                new_code = f"4100{last_number + 1:03d}"
            except ValueError:
                new_code = "4100001"
        else:
            new_code = "4100001"
        
        return Account.objects.create(
            group=income_group,
            code=new_code,
            name="درآمدهای عمومی",
            level='DETAIL',
            currency=self.default_currency,
            description="حساب درآمدهای عمومی"
        )
    
    def _get_or_create_capital_account(self):
        """Get or create capital account"""
        capital_account = Account.objects.filter(
            name__icontains="سرمایه",
            group__name__icontains="سرمایه"
        ).first()
        
        if capital_account:
            return capital_account
        
        # Create capital account
        capital_group = self._get_or_create_account_group("سرمایه‌ها", "3100")
        
        # Generate unique code
        existing_codes = Account.objects.filter(
            code__startswith="3100"
        ).values_list('code', flat=True)
        
        if existing_codes:
            max_code = max(existing_codes)
            try:
                last_number = int(max_code[4:])
                new_code = f"3100{last_number + 1:03d}"
            except ValueError:
                new_code = "3100001"
        else:
            new_code = "3100001"
        
        return Account.objects.create(
            group=capital_group,
            code=new_code,
            name="سرمایه",
            level='DETAIL',
            currency=self.default_currency,
            description="حساب سرمایه"
        )
    
    def _get_or_create_petty_cash_account(self):
        """Get or create petty cash account"""
        petty_cash_account = Account.objects.filter(
            name__icontains="تنخواه",
            group__name__icontains="نقدی"
        ).first()
        
        if petty_cash_account:
            return petty_cash_account
        
        # Create petty cash account
        cash_group = self._get_or_create_account_group("موجودی نقدی", "1100")
        
        # Generate unique code
        existing_codes = Account.objects.filter(
            code__startswith="1100"
        ).values_list('code', flat=True)
        
        if existing_codes:
            max_code = max(existing_codes)
            try:
                last_number = int(max_code[4:])
                new_code = f"1100{last_number + 1:03d}"
            except ValueError:
                new_code = "1100002"
        else:
            new_code = "1100002"
        
        return Account.objects.create(
            group=cash_group,
            code=new_code,
            name="تنخواه",
            level='DETAIL',
            currency=self.default_currency,
            description="حساب تنخواه"
        )
    
    def _get_or_create_general_account(self, name, code_prefix):
        """Get or create general account"""
        account = Account.objects.filter(
            name__icontains=name
        ).first()
        
        if account:
            return account
        
        # Create general account
        group = self._get_or_create_account_group(name, code_prefix)
        
        # Generate unique code
        existing_codes = Account.objects.filter(
            code__startswith=code_prefix
        ).values_list('code', flat=True)
        
        if existing_codes:
            max_code = max(existing_codes)
            try:
                last_number = int(max_code[len(code_prefix):])
                new_code = f"{code_prefix}{last_number + 1:03d}"
            except ValueError:
                new_code = f"{code_prefix}001"
        else:
            new_code = f"{code_prefix}001"
        
        return Account.objects.create(
            group=group,
            code=new_code,
            name=name,
            level='DETAIL',
            currency=self.default_currency,
            description=f"حساب {name}"
        )
    
    def _get_or_create_account_group(self, name, code):
        """Get or create account group"""
        from .models import AccountGroup
        
        group = AccountGroup.objects.filter(
            name__icontains=name
        ).first()
        
        if group:
            return group
        
        return AccountGroup.objects.create(
            name=name,
            code=code,
            description=f"گروه حساب {name}"
        )
    
    def create_voucher_from_receipt(self, receipt):
        """Create voucher from receipt"""
        try:
            with transaction.atomic():
                # Create voucher
                voucher = Voucher.objects.create(
                    financial_year=self.current_financial_year,
                    number=self.get_next_voucher_number(),
                    date=receipt.date,
                    type='PERMANENT',
                    description=f"سند رسید دریافت از {receipt.customer.get_full_name()}",
                    created_by=receipt.created_by
                )
                
                # Get customer account
                customer_account = self._get_or_create_customer_account(receipt.customer)
                
                # Get cash account
                cash_account = self._get_or_create_cash_account()
                
                # Create voucher items
                VoucherItem.objects.create(
                    voucher=voucher,
                    account=cash_account,
                    description=f"دریافت از {receipt.customer.get_full_name()}",
                    debit=receipt.amount,
                    credit=0,
                    reference_id=str(receipt.id),
                    reference_type='Receipt'
                )
                
                VoucherItem.objects.create(
                    voucher=voucher,
                    account=customer_account,
                    description=f"دریافت از {receipt.customer.get_full_name()}",
                    debit=0,
                    credit=receipt.amount,
                    reference_id=str(receipt.id),
                    reference_type='Receipt'
                )
                
                return voucher
                
        except Exception as e:
            print(f"Error creating voucher for receipt {receipt.id}: {e}")
            return None
    
    def create_voucher_from_invoice(self, invoice, invoice_type):
        """Create voucher from invoice (purchase or sales)"""
        try:
            with transaction.atomic():
                # Create voucher
                voucher = Voucher.objects.create(
                    financial_year=self.current_financial_year,
                    number=self.get_next_voucher_number(),
                    date=invoice.invoice_date,
                    type='PERMANENT',
                    description=f"سند فاکتور {invoice_type} - {invoice.invoice_number}",
                    created_by=invoice.created_by
                )
                
                # Get customer account
                customer_account = self._get_or_create_customer_account(invoice.customer)
                
                # Get sales/purchase account
                if invoice_type == 'sales':
                    sales_account = self._get_or_create_sales_account()
                else:
                    purchase_account = self._get_or_create_purchase_account()
                
                # Create voucher items
                if invoice_type == 'sales':
                    VoucherItem.objects.create(
                        voucher=voucher,
                        account=customer_account,
                        description=f"فروش به {invoice.customer.get_full_name()}",
                        debit=invoice.total_amount,
                        credit=0,
                        reference_id=str(invoice.id),
                        reference_type='SalesInvoice'
                    )
                    
                    VoucherItem.objects.create(
                        voucher=voucher,
                        account=sales_account,
                        description=f"فروش به {invoice.customer.get_full_name()}",
                        debit=0,
                        credit=invoice.total_amount,
                        reference_id=str(invoice.id),
                        reference_type='SalesInvoice'
                    )
                else:
                    VoucherItem.objects.create(
                        voucher=voucher,
                        account=purchase_account,
                        description=f"خرید از {invoice.customer.get_full_name()}",
                        debit=invoice.total_amount,
                        credit=0,
                        reference_id=str(invoice.id),
                        reference_type='PurchaseInvoice'
                    )
                    
                    VoucherItem.objects.create(
                        voucher=voucher,
                        account=customer_account,
                        description=f"خرید از {invoice.customer.get_full_name()}",
                        debit=0,
                        credit=invoice.total_amount,
                        reference_id=str(invoice.id),
                        reference_type='PurchaseInvoice'
                    )
                
                return voucher
                
        except Exception as e:
            print(f"Error creating voucher for invoice {invoice.id}: {e}")
            return None
    
    def create_voucher_from_petty_cash_operation(self, petty_cash_operation):
        """Create voucher from petty cash operation"""
        try:
            with transaction.atomic():
                # اطمینان از وجود financial_year
                if not self.current_financial_year:
                    self._initialize_defaults()
                
                # اطمینان از وجود created_by
                created_by = petty_cash_operation.created_by
                if not created_by:
                    created_by = User.objects.first()
                
                # Create voucher
                voucher = Voucher.objects.create(
                    financial_year=self.current_financial_year,
                    number=self.get_next_voucher_number(),
                    date=petty_cash_operation.date,
                    type='PERMANENT',
                    description=f"سند عملیات تنخواه - {petty_cash_operation.operation_number}",
                    created_by=created_by
                )
                
                # Get petty cash account
                petty_cash_account = self._get_or_create_petty_cash_account()
                
                # Get cash account (source)
                cash_account = self._get_or_create_cash_account()
                
                # Create voucher items based on operation type
                if petty_cash_operation.operation_type == 'ADD':
                    # افزودن به تنخواه: بدهکار تنخواه، بستانکار صندوق نقدی
                    VoucherItem.objects.create(
                        voucher=voucher,
                        account=petty_cash_account,
                        description=f"افزودن به تنخواه - {petty_cash_operation.get_reason_display()}",
                        debit=petty_cash_operation.amount,
                        credit=0,
                        reference_id=str(petty_cash_operation.id),
                        reference_type='PettyCashOperation'
                    )
                    
                    VoucherItem.objects.create(
                        voucher=voucher,
                        account=cash_account,
                        description=f"افزودن به تنخواه - {petty_cash_operation.get_reason_display()}",
                        debit=0,
                        credit=petty_cash_operation.amount,
                        reference_id=str(petty_cash_operation.id),
                        reference_type='PettyCashOperation'
                    )
                else:
                    # برداشت از تنخواه: بدهکار صندوق نقدی، بستانکار تنخواه
                    VoucherItem.objects.create(
                        voucher=voucher,
                        account=cash_account,
                        description=f"برداشت از تنخواه - {petty_cash_operation.get_reason_display()}",
                        debit=petty_cash_operation.amount,
                        credit=0,
                        reference_id=str(petty_cash_operation.id),
                        reference_type='PettyCashOperation'
                    )
                    
                    VoucherItem.objects.create(
                        voucher=voucher,
                        account=petty_cash_account,
                        description=f"برداشت از تنخواه - {petty_cash_operation.get_reason_display()}",
                        debit=0,
                        credit=petty_cash_operation.amount,
                        reference_id=str(petty_cash_operation.id),
                        reference_type='PettyCashOperation'
                    )
                
                return voucher
                
        except Exception as e:
            print(f"Error creating voucher for petty cash operation {petty_cash_operation.id}: {e}")
            return None
    
    def _get_or_create_sales_account(self):
        """Get or create sales account"""
        sales_account = Account.objects.filter(
            name__icontains="فروش",
            group__name__icontains="فروش"
        ).first()
        
        if sales_account:
            return sales_account
        
        # Create sales account
        sales_group = self._get_or_create_account_group("فروش", "4100")
        
        return Account.objects.create(
            group=sales_group,
            code="4100001",
            name="فروش کالا",
            level='DETAIL',
            currency=self.default_currency,
            description="حساب فروش کالا"
        )
    
    def _get_or_create_purchase_account(self):
        """Get or create purchase account"""
        purchase_account = Account.objects.filter(
            name__icontains="خرید",
            group__name__icontains="خرید"
        ).first()
        
        if purchase_account:
            return purchase_account
        
        # Create purchase account
        purchase_group = self._get_or_create_account_group("خرید", "5100")
        
        return Account.objects.create(
            group=purchase_group,
            code="5100001",
            name="خرید کالا",
            level='DETAIL',
            currency=self.default_currency,
            description="حساب خرید کالا"
        )


# Global instance
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