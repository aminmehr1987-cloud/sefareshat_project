#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sefareshat_project.settings')
django.setup()

from products.models import ReceivedCheque, Customer, User, FinancialOperation, CustomerBalance
from django.test import RequestFactory
from django.contrib.auth.models import User as AuthUser
import jdatetime

def test_return_spent_cheque():
    print("🚀 تست تابع برگشت چک خرج شده...")
    
    # دریافت کاربر اول
    user = User.objects.first()
    if not user:
        print("❌ کاربری یافت نشد!")
        return
    
    # دریافت مشتری اول
    customer = Customer.objects.first()
    if not customer:
        print("❌ مشتری‌ای یافت نشد!")
        return
    
    print(f"📋 استفاده از کاربر: {user.username}")
    print(f"👤 مشتری: {customer.first_name} {customer.last_name}")
    
    # بررسی موجودی اولیه
    customer_balance, _ = CustomerBalance.objects.get_or_create(
        customer=customer,
        defaults={'current_balance': 0, 'total_received': 0, 'total_paid': 0}
    )
    
    print(f"📊 موجودی اولیه: {customer_balance.current_balance:,}")
    
    # ایجاد چک دریافتی
    received_cheque = ReceivedCheque.objects.create(
        customer=customer,
        sayadi_id=f'RETURN123456789{user.id:06d}',
        amount=300000,
        due_date=jdatetime.date.today().togregorian(),
        bank_name='بانک تست',
        owner_name='مالک تست',
        account_number='123456789',
        created_by=user,
        status='RECEIVED'
    )
    print(f"✅ چک دریافتی ایجاد شد: {received_cheque.sayadi_id}")
    
    # شبیه‌سازی خرج کردن چک
    received_cheque.status = 'SPENT'
    received_cheque.recipient_name = customer.get_full_name()
    received_cheque.recipient_customer = customer
    received_cheque.save()
    print(f"✅ چک خرج شد و به {customer.get_full_name()} داده شد")
    
    # ایجاد عملیات مالی برای خرج کردن چک
    spend_operation = FinancialOperation.objects.create(
        operation_type='PAY_TO_CUSTOMER',
        customer=customer,
        amount=300000,
        payment_method='spend_cheque',
        date=jdatetime.date.today().togregorian(),
        description=f'خرج چک {received_cheque.sayadi_id} به {customer.get_full_name()}',
        created_by=user,
        status='CONFIRMED'
    )
    print(f"✅ عملیات خرج چک ایجاد شد: {spend_operation.operation_number}")
    
    # بروزرسانی موجودی
    customer_balance.update_balance()
    print(f"📊 موجودی بعد از خرج: {customer_balance.current_balance:,}")
    
    # شبیه‌سازی درخواست HTTP
    print("\n🔥 شبیه‌سازی برگشت چک...")
    
    # بررسی وضعیت چک قبل از برگشت
    print(f"📋 وضعیت چک قبل از برگشت: {received_cheque.status}")
    print(f"📋 گیرنده چک: {received_cheque.recipient_customer}")
    print(f"📋 نام گیرنده: {received_cheque.recipient_name}")
    
    # تغییر وضعیت چک به BOUNCED
    received_cheque.status = 'BOUNCED'
    received_cheque.bounced_at = django.utils.timezone.now()
    received_cheque.bounced_by = user
    received_cheque.save()
    
    # پیدا کردن گیرنده چک
    recipient_customer = received_cheque.recipient_customer
    if not recipient_customer and received_cheque.recipient_name:
        from django.db.models import Q
        recipient_customer = Customer.objects.filter(
            Q(first_name__icontains=received_cheque.recipient_name) | 
            Q(last_name__icontains=received_cheque.recipient_name) |
            Q(company_name__icontains=received_cheque.recipient_name)
        ).first()
    
    target_customer = recipient_customer if recipient_customer else received_cheque.customer
    print(f"📋 مشتری هدف برای برگشت: {target_customer.get_full_name()}")
    
    # ایجاد عملیات مالی برای برگشت چک
    bounce_operation = FinancialOperation.objects.create(
        operation_type='RECEIVE_FROM_CUSTOMER',
        customer=target_customer,
        amount=300000,
        payment_method='cheque_return',
        date=jdatetime.date.today().togregorian(),
        description=f'چک برگشتی {received_cheque.sayadi_id}',
        created_by=user,
        status='CONFIRMED',
        confirmed_by=user,
        confirmed_at=django.utils.timezone.now()
    )
    print(f"✅ عملیات برگشت چک ایجاد شد: {bounce_operation.operation_number}")
    
    # بروزرسانی موجودی
    customer_balance.update_balance()
    print(f"📊 موجودی بعد از برگشت: {customer_balance.current_balance:,}")
    
    # بررسی منطق
    print("\n🔍 بررسی منطق:")
    if customer_balance.current_balance > 0:
        print("✅ مبلغ برگشتی در حساب اعمال شد")
    else:
        print("❌ مبلغ برگشتی در حساب اعمال نشد")
    
    # پاکسازی
    print("\n🧹 پاکسازی...")
    if FinancialOperation.objects.filter(pk=spend_operation.pk).exists():
        spend_operation.delete()
    if FinancialOperation.objects.filter(pk=bounce_operation.pk).exists():
        bounce_operation.delete()
    received_cheque.delete()
    
    print("✅ تست تابع برگشت چک خرج شده کامل شد!")

if __name__ == '__main__':
    test_return_spent_cheque() 