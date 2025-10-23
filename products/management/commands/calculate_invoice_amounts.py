"""
Management command برای محاسبه مبالغ نقدی و چکی فاکتورهای موجود

این command باید یک بار اجرا شود تا فاکتورهای موجود را آپدیت کند
"""

from django.core.management.base import BaseCommand
from products.models import SalesInvoice


class Command(BaseCommand):
    help = 'محاسبه مبالغ نقدی و چکی برای تمام فاکتورهای فروش'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='محاسبه مجدد حتی برای فاکتورهایی که قبلاً محاسبه شده‌اند',
        )

    def handle(self, *args, **options):
        force = options['force']
        
        # دریافت فاکتورهای فروش
        if force:
            invoices = SalesInvoice.objects.all()
            self.stdout.write(self.style.WARNING(
                f'🔄 محاسبه مجدد برای {invoices.count()} فاکتور...'
            ))
        else:
            invoices = SalesInvoice.objects.filter(
                cash_amount=0,
                cheque_amount=0
            )
            self.stdout.write(self.style.WARNING(
                f'🔄 محاسبه برای {invoices.count()} فاکتور جدید...'
            ))
        
        if invoices.count() == 0:
            self.stdout.write(self.style.SUCCESS(
                '✅ هیچ فاکتوری برای محاسبه وجود ندارد'
            ))
            return
        
        success_count = 0
        error_count = 0
        
        for invoice in invoices:
            try:
                # محاسبه مبالغ
                invoice.calculate_cash_and_cheque_amounts()
                success_count += 1
                
                self.stdout.write(
                    f'✅ فاکتور {invoice.invoice_number}: '
                    f'نقدی={invoice.cash_amount:,.0f}, '
                    f'چکی={invoice.cheque_amount:,.0f}, '
                    f'سررسید={invoice.cheque_due_date}'
                )
                
            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(
                    f'❌ خطا در محاسبه فاکتور {invoice.invoice_number}: {str(e)}'
                ))
        
        # خلاصه
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(
            f'✅ موفق: {success_count} فاکتور'
        ))
        
        if error_count > 0:
            self.stdout.write(self.style.ERROR(
                f'❌ خطا: {error_count} فاکتور'
            ))
        
        self.stdout.write('='*60 + '\n')
        
        self.stdout.write(self.style.SUCCESS(
            '🎉 محاسبات با موفقیت انجام شد!'
        ))
