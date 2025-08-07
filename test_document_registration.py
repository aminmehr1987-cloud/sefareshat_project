#!/usr/bin/env python
"""
Test script for tracking document registration in customer receipt section
This script helps identify where documents are being registered and their document numbers
"""

import os
import sys
import django
from datetime import datetime, date
import jdatetime

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sefareshat_project.settings')
django.setup()

from products.models import (
    FinancialOperation, Receipt, Voucher, DocumentArticle, 
    Account, AccountGroup, Customer, User, FinancialYear, Currency
)
from django.db import transaction
from django.utils import timezone

def test_customer_receipt_registration():
    """
    Test customer receipt registration and track document creation
    """
    print("=== Testing Customer Receipt Registration ===\n")
    
    # Get or create test data
    try:
        # Get first customer
        customer = Customer.objects.first()
        if not customer:
            print("❌ No customers found in database")
            return
        
        # Get or create financial year
        financial_year, created = FinancialYear.objects.get_or_create(
            year='1404',
            defaults={
                'start_date': date(2025, 3, 21),
                'end_date': date(2026, 3, 20),
                'is_active': True,
                'created_by': User.objects.first()
            }
        )
        
        # Get or create currency
        currency, created = Currency.objects.get_or_create(
            code='IRR',
            defaults={
                'name': 'ریال ایران',
                'symbol': 'ریال',
                'is_default': True,
                'exchange_rate': 1.0
            }
        )
        
        # Get or create account groups
        cash_group, created = AccountGroup.objects.get_or_create(
            code='1100',
            defaults={
                'name': 'موجودی نقد',
                'type': 'ASSET',
                'is_active': True
            }
        )
        
        customer_group, created = AccountGroup.objects.get_or_create(
            code='1300',
            defaults={
                'name': 'حساب‌ها و اسناد دریافتنی',
                'type': 'ASSET',
                'is_active': True
            }
        )
        
        # Get or create cash account
        cash_account, created = Account.objects.get_or_create(
            code='1110',
            defaults={
                'name': 'صندوق',
                'level': 'MOEIN',
                'group': cash_group,
                'currency': currency,
                'is_active': True
            }
        )
        
        # Get or create customer account
        customer_account, created = Account.objects.get_or_create(
            code='1310',
            defaults={
                'name': 'حساب‌های دریافتنی',
                'level': 'MOEIN',
                'group': customer_group,
                'currency': currency,
                'is_active': True
            }
        )
        
        print(f"✅ Test data prepared:")
        print(f"   - Customer: {customer.get_full_name()}")
        print(f"   - Financial Year: {financial_year.year}")
        print(f"   - Currency: {currency.name}")
        print(f"   - Cash Account: {cash_account.name} ({cash_account.code})")
        print(f"   - Customer Account: {customer_account.name} ({customer_account.code})")
        
        # Test 1: Create a FinancialOperation (customer receipt)
        print(f"\n=== Test 1: Creating FinancialOperation (Customer Receipt) ===")
        
        with transaction.atomic():
            # Create financial operation
            operation = FinancialOperation.objects.create(
                operation_type='RECEIVE_FROM_CUSTOMER',
                date=date.today(),
                amount=1000000,  # 1,000,000 Rials
                description=f'دریافت از {customer.get_full_name()}',
                customer=customer,
                payment_method='cash',
                status='CONFIRMED',
                created_by=User.objects.first(),
                confirmed_by=User.objects.first(),
                confirmed_at=timezone.now()
            )
            
            print(f"✅ FinancialOperation created:")
            print(f"   - Operation Number: {operation.operation_number}")
            print(f"   - Operation Type: {operation.get_operation_type_display()}")
            print(f"   - Amount: {operation.amount:,} ریال")
            print(f"   - Customer: {operation.customer.get_full_name()}")
            print(f"   - Status: {operation.get_status_display()}")
            
            # Create voucher for this operation
            voucher = Voucher.objects.create(
                financial_year=financial_year,
                number=f"OP{operation.operation_number}",
                date=operation.date,
                type='PERMANENT',
                description=f"سند عملیات {operation.get_operation_type_display()} - {operation.operation_number}",
                is_confirmed=True,
                confirmed_by=User.objects.first(),
                confirmed_at=timezone.now(),
                created_by=User.objects.first()
            )
            
            print(f"✅ Voucher created:")
            print(f"   - Voucher Number: {voucher.number}")
            print(f"   - Voucher Type: {voucher.get_type_display()}")
            print(f"   - Description: {voucher.description}")
            
            # Create document articles (accounting entries)
            # Debit: Cash account
            debit_article = DocumentArticle.objects.create(
                voucher=voucher,
                account=cash_account,
                article_type='DEBIT',
                amount=operation.amount,
                description=f"دریافت از {customer.get_full_name()}",
                category='CASH',
                reference_id=str(operation.id),
                reference_type='FinancialOperation',
                is_posted=True,
                posted_by=User.objects.first(),
                posted_at=timezone.now()
            )
            
            # Credit: Customer account
            credit_article = DocumentArticle.objects.create(
                voucher=voucher,
                account=customer_account,
                article_type='CREDIT',
                amount=operation.amount,
                description=f"دریافت از {customer.get_full_name()}",
                category='CUSTOMER',
                reference_id=str(operation.id),
                reference_type='FinancialOperation',
                is_posted=True,
                posted_by=User.objects.first(),
                posted_at=timezone.now()
            )
            
            print(f"✅ Document Articles created:")
            print(f"   - Debit Article: {debit_article.account.name} - {debit_article.amount:,} ریال")
            print(f"   - Credit Article: {credit_article.account.name} - {credit_article.amount:,} ریال")
            
            # Update account balances
            cash_account.current_balance += operation.amount
            cash_account.save()
            
            customer_account.current_balance -= operation.amount
            customer_account.save()
            
            print(f"✅ Account balances updated:")
            print(f"   - Cash Account Balance: {cash_account.current_balance:,} ریال")
            print(f"   - Customer Account Balance: {customer_account.current_balance:,} ریال")
        
        print(f"\n=== Test 1 Summary ===")
        print(f"✅ Document Registration Complete:")
        print(f"   📄 Financial Operation: {operation.operation_number}")
        print(f"   📄 Voucher: {voucher.number}")
        print(f"   📄 Debit Article: {debit_article.id}")
        print(f"   📄 Credit Article: {credit_article.id}")
        print(f"   📄 Registration Location: Customer Receipt Section")
        
        # Test 2: Create a simple Receipt
        print(f"\n=== Test 2: Creating Simple Receipt ===")
        
        receipt = Receipt.objects.create(
            customer=customer,
            date=date.today(),
            amount=500000,  # 500,000 Rials
            payment_method='cash',
            description='رسید دریافت نقدی',
            created_by=User.objects.first()
        )
        
        print(f"✅ Simple Receipt created:")
        print(f"   - Receipt ID: {receipt.id}")
        print(f"   - Customer: {receipt.customer.get_full_name()}")
        print(f"   - Amount: {receipt.amount:,} ریال")
        print(f"   - Payment Method: {receipt.get_payment_method_display()}")
        print(f"   - Created At: {receipt.created_at}")
        
        print(f"\n=== Test 2 Summary ===")
        print(f"✅ Simple Receipt Registration Complete:")
        print(f"   📄 Receipt ID: {receipt.id}")
        print(f"   📄 Registration Location: Receipt Model")
        
        # Show all recent documents
        print(f"\n=== Recent Documents Summary ===")
        
        # Recent Financial Operations
        recent_operations = FinancialOperation.objects.order_by('-created_at')[:5]
        print(f"📋 Recent Financial Operations:")
        for op in recent_operations:
            print(f"   - {op.operation_number}: {op.get_operation_type_display()} - {op.amount:,} ریال")
        
        # Recent Vouchers
        recent_vouchers = Voucher.objects.order_by('-created_at')[:5]
        print(f"📋 Recent Vouchers:")
        for v in recent_vouchers:
            print(f"   - {v.number}: {v.description}")
        
        # Recent Document Articles
        recent_articles = DocumentArticle.objects.order_by('-created_at')[:10]
        print(f"📋 Recent Document Articles:")
        for art in recent_articles:
            print(f"   - {art.voucher.number}: {art.account.name} - {art.get_article_type_display()} {art.amount:,} ریال")
        
        # Recent Receipts
        recent_receipts = Receipt.objects.order_by('-created_at')[:5]
        print(f"📋 Recent Receipts:")
        for r in recent_receipts:
            print(f"   - {r.id}: {r.customer.get_full_name()} - {r.amount:,} ریال")
        
        print(f"\n=== Document Registration Tracking Complete ===")
        print(f"✅ All tests completed successfully!")
        print(f"📊 Documents created in this test:")
        print(f"   - 1 FinancialOperation")
        print(f"   - 1 Voucher")
        print(f"   - 2 DocumentArticles")
        print(f"   - 1 Receipt")
        
    except Exception as e:
        print(f"❌ Error during testing: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_customer_receipt_registration() 