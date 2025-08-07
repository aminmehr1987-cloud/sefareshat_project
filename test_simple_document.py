#!/usr/bin/env python
"""
Simple test for document creation in customer receipt registration
"""

import os
import sys
import django
from datetime import datetime, date

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sefareshat_project.settings')
django.setup()

from products.models import (
    FinancialOperation, Customer, User, FinancialYear, 
    Voucher, DocumentArticle, Account
)
from django.db import transaction
from django.utils import timezone

def test_simple_document_creation():
    """
    Simple test for document creation
    """
    print("=== Simple Document Creation Test ===")
    
    # Get required objects
    financial_year = FinancialYear.objects.filter(is_active=True).first()
    customer = Customer.objects.first()
    user = User.objects.first()
    
    if not all([financial_year, customer, user]):
        print("❌ Missing required objects")
        return
    
    print(f"✅ Financial Year: {financial_year.year}")
    print(f"✅ Customer: {customer.get_full_name()}")
    print(f"✅ User: {user.username}")
    
    try:
        with transaction.atomic():
            # Create a test financial operation
            operation = FinancialOperation.objects.create(
                operation_type='RECEIVE_FROM_CUSTOMER',
                operation_number=f'SIMPLE-{datetime.now().strftime("%Y%m%d%H%M%S")}',
                date=date.today(),
                amount=500000,  # 500,000 Rials
                description='تست ساده دریافت از مشتری',
                status='CONFIRMED',
                customer=customer,
                payment_method='cash',
                created_by=user,
                confirmed_by=user,
                confirmed_at=timezone.now()
            )
            
            print(f"✅ Created FinancialOperation: {operation.operation_number}")
            
            # Test the create_accounting_entries method
            voucher = operation.create_accounting_entries()
            
            if voucher:
                print(f"✅ Created Voucher: {voucher.number}")
                print(f"✅ Voucher Description: {voucher.description}")
                
                # Check document articles
                articles = voucher.articles.all()
                print(f"✅ Created {articles.count()} document articles")
                
                for article in articles:
                    print(f"   - {article.article_type}: {article.account.name} - {article.amount:,} ریال")
                
                print(f"\n🎉 Document creation test completed successfully!")
                print(f"   Document Number: {voucher.number}")
                print(f"   Operation Number: {operation.operation_number}")
                print(f"   Customer: {customer.get_full_name()}")
                print(f"   Amount: {operation.amount:,} ریال")
                
            else:
                print("❌ create_accounting_entries returned None")
                
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_simple_document_creation() 