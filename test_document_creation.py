#!/usr/bin/env python
"""
Test script for document creation in customer receipt registration
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
    FinancialOperation, Customer, User, FinancialYear, 
    Voucher, DocumentArticle, Account
)
from django.db import transaction
from django.utils import timezone

def test_document_creation():
    """
    Test document creation for customer receipt
    """
    print("=== Testing Document Creation ===")
    
    # Get active financial year
    financial_year = FinancialYear.objects.filter(is_active=True).first()
    if not financial_year:
        print("❌ No active financial year found")
        return
    
    print(f"✅ Active Financial Year: {financial_year.year}")
    
    # Get a customer
    customer = Customer.objects.first()
    if not customer:
        print("❌ No customer found")
        return
    
    print(f"✅ Customer: {customer.get_full_name()}")
    
    # Get required accounts
    cash_account = Account.objects.filter(code__startswith='11').first()
    customer_account = Account.objects.filter(code__startswith='13').first()
    
    if not cash_account or not customer_account:
        print("❌ Required accounts not found")
        print(f"   Cash account: {cash_account}")
        print(f"   Customer account: {customer_account}")
        return
    
    print(f"✅ Cash account: {cash_account.code} - {cash_account.name}")
    print(f"✅ Customer account: {customer_account.code} - {customer_account.name}")
    
    # Get a user
    user = User.objects.first()
    if not user:
        print("❌ No user found")
        return
    
    print(f"✅ User: {user.username}")
    
    try:
        with transaction.atomic():
            # Create a test financial operation
            operation = FinancialOperation.objects.create(
                operation_type='RECEIVE_FROM_CUSTOMER',
                operation_number=f'TEST-{datetime.now().strftime("%Y%m%d%H%M%S")}',
                date=date.today(),
                amount=1000000,  # 1,000,000 Rials
                description='تست دریافت از مشتری',
                status='CONFIRMED',
                customer=customer,
                payment_method='cash',
                created_by=user,
                confirmed_by=user,
                confirmed_at=timezone.now()
            )
            
            print(f"✅ Created FinancialOperation: {operation.operation_number}")
            
            # Create voucher
            last_voucher = Voucher.objects.filter(financial_year=financial_year).order_by('-number').first()
            if last_voucher:
                try:
                    next_number = str(int(last_voucher.number) + 1).zfill(6)
                except ValueError:
                    next_number = '000001'
            else:
                next_number = '000001'
            
            voucher = Voucher.objects.create(
                financial_year=financial_year,
                number=next_number,
                date=operation.date,
                type='PERMANENT',
                description=f"دریافت از مشتری {operation.customer.get_full_name()} - مبلغ: {operation.amount:,} ریال",
                is_confirmed=True,
                confirmed_by=user,
                confirmed_at=timezone.now(),
                created_by=user
            )
            
            print(f"✅ Created Voucher: {voucher.number}")
            
            # Create document articles
            articles = DocumentArticle.create_from_operation(operation, voucher)
            
            print(f"✅ Created {len(articles)} document articles")
            
            for article in articles:
                print(f"   - {article.article_type}: {article.account.name} - {article.amount:,} ریال")
            
            # Test the create_accounting_entries method
            print("\n=== Testing create_accounting_entries method ===")
            voucher2 = operation.create_accounting_entries()
            
            if voucher2:
                print(f"✅ create_accounting_entries created voucher: {voucher2.number}")
            else:
                print("❌ create_accounting_entries returned None")
            
            print(f"\n🎉 Document creation test completed successfully!")
            print(f"   Document Number: {voucher.number}")
            print(f"   Operation Number: {operation.operation_number}")
            print(f"   Customer: {customer.get_full_name()}")
            print(f"   Amount: {operation.amount:,} ریال")
            
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_document_creation() 