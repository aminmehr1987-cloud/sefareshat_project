"""
Django management command برای بازمحاسبه مبالغ تسویه شده فاکتورها
"""
from django.core.management.base import BaseCommand
from django.db import models
from products.models import SalesInvoice, FinancialOperation
from decimal import Decimal


class Command(BaseCommand):
    help = 'بازمحاسبه مبالغ تسویه شده تمام فاکتورها از روی تراکنش‌های واقعی'

    def add_arguments(self, parser):
        parser.add_argument(
            '--invoice',
            type=str,
            help='شماره فاکتور خاص برای بازمحاسبه (اختیاری)',
        )

    def handle(self, *args, **options):
        invoice_number = options.get('invoice')
        
        if invoice_number:
            # فقط یک فاکتور
            try:
                invoices = [SalesInvoice.objects.get(invoice_number=invoice_number)]
                self.stdout.write(f'🔍 بازمحاسبه فاکتور: {invoice_number}')
            except SalesInvoice.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'❌ فاکتور {invoice_number} یافت نشد'))
                return
        else:
            # تمام فاکتورها
            invoices = SalesInvoice.objects.all()
            self.stdout.write(f'🔍 بازمحاسبه {invoices.count()} فاکتور...')
        
        updated_count = 0
        errors_count = 0
        
        for invoice in invoices:
            try:
                # محاسبه تسویه‌ها از روی FinancialOperation
                # تراکنش‌هایی که برای این فاکتور ثبت شده‌اند
                operations = FinancialOperation.objects.filter(
                    description__icontains=invoice.invoice_number,
                    status='CONFIRMED'
                )
                
                # تسویه نقدی
                settle_cash = operations.filter(payment_method='cash').aggregate(
                    total=models.Sum('amount')
                )['total'] or Decimal('0')
                
                # تسویه کارتخوان
                settle_card = operations.filter(payment_method='card').aggregate(
                    total=models.Sum('amount')
                )['total'] or Decimal('0')
                
                # تسویه بانکی
                settle_bank = operations.filter(payment_method='bank_transfer').aggregate(
                    total=models.Sum('amount')
                )['total'] or Decimal('0')
                
                # تسویه چک
                settle_cheque = operations.filter(payment_method='cheque').aggregate(
                    total=models.Sum('amount')
                )['total'] or Decimal('0')
                
                # بروزرسانی فیلدها
                old_values = {
                    'cash': invoice.settle_cash,
                    'card': invoice.settle_card,
                    'bank': invoice.settle_bank,
                    'cheque': invoice.settle_cheque,
                }
                
                invoice.settle_cash = settle_cash
                invoice.settle_card = settle_card
                invoice.settle_bank = settle_bank
                invoice.settle_cheque = settle_cheque
                
                # محاسبه مانده
                total_settled = settle_cash + settle_card + settle_bank + settle_cheque + invoice.settle_extra_discount
                invoice.settle_balance = invoice.total_amount - total_settled
                
                # ذخیره فقط اگر تغییر کرده باشد
                if (old_values['cash'] != settle_cash or 
                    old_values['card'] != settle_card or 
                    old_values['bank'] != settle_bank or 
                    old_values['cheque'] != settle_cheque):
                    invoice.save()
                    updated_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✅ {invoice.invoice_number}: نقدی={settle_cash}, کارت={settle_card}, '
                            f'بانک={settle_bank}, چک={settle_cheque}, مانده={invoice.settle_balance}'
                        )
                    )
                
            except Exception as e:
                errors_count += 1
                self.stdout.write(
                    self.style.ERROR(f'❌ خطا در فاکتور {invoice.invoice_number}: {str(e)}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'\n✅ بازمحاسبه تمام شد: {updated_count} فاکتور بروز شد، {errors_count} خطا')
        )
