from django.core.management.base import BaseCommand
from products.models import FinancialOperation


class Command(BaseCommand):
    help = 'بازگردانی وضعیت چک‌های مرتبط با عملیات‌های حذف شده'

    def add_arguments(self, parser):
        parser.add_argument(
            '--operation-number',
            type=str,
            help='شماره سند خاص برای بازگردانی (اختیاری)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='فقط نمایش تغییرات بدون اعمال آنها'
        )

    def handle(self, *args, **options):
        operation_number = options.get('operation_number')
        dry_run = options.get('dry_run', False)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('حالت تست - تغییرات اعمال نخواهند شد'))
        
        # فیلتر عملیات‌های مرتبط با چک‌ها که حذف شده‌اند
        operations_filter = {
            'is_deleted': True,
            'operation_type__in': ['ISSUED_CHECK_BOUNCE', 'CHECK_BOUNCE', 'SPENT_CHEQUE_RETURN']
        }
        
        if operation_number:
            operations_filter['operation_number'] = operation_number
            
        deleted_operations = FinancialOperation.objects.filter(**operations_filter)
        
        if not deleted_operations.exists():
            self.stdout.write(self.style.WARNING('هیچ عملیات حذف شده‌ای یافت نشد'))
            return
        
        self.stdout.write(f'یافت شد: {deleted_operations.count()} عملیات حذف شده')
        
        success_count = 0
        error_count = 0
        
        for operation in deleted_operations:
            self.stdout.write(f'\n--- پردازش سند {operation.operation_number} ---')
            self.stdout.write(f'نوع: {operation.get_operation_type_display()}')
            self.stdout.write(f'توضیحات: {operation.description[:100]}...')
            
            if not dry_run:
                try:
                    result = operation.restore_related_check_statuses()
                    if result:
                        success_count += 1
                        self.stdout.write(self.style.SUCCESS('✅ موفق'))
                    else:
                        error_count += 1
                        self.stdout.write(self.style.ERROR('❌ ناموفق'))
                except Exception as e:
                    error_count += 1
                    self.stdout.write(self.style.ERROR(f'❌ خطا: {e}'))
            else:
                # در حالت dry-run فقط نمایش می‌دهیم
                import re
                if operation.operation_type == 'ISSUED_CHECK_BOUNCE':
                    match = re.search(r'شماره (\d+)', operation.description or '')
                    if match:
                        self.stdout.write(f'چک صادر شده {match.group(1)} بازگردانی خواهد شد')
                elif operation.operation_type in ['CHECK_BOUNCE', 'SPENT_CHEQUE_RETURN']:
                    sayadi_match = re.search(r'شناسه صیادی:?\s*(\d+)', operation.description or '')
                    if not sayadi_match:
                        sayadi_match = re.search(r'شماره صیادی:?\s*(\d+)', operation.description or '')
                    if sayadi_match:
                        self.stdout.write(f'چک دریافتی {sayadi_match.group(1)} بازگردانی خواهد شد')
        
        if not dry_run:
            self.stdout.write(f'\n=== خلاصه ===')
            self.stdout.write(self.style.SUCCESS(f'موفق: {success_count}'))
            self.stdout.write(self.style.ERROR(f'ناموفق: {error_count}'))
            self.stdout.write(f'کل: {success_count + error_count}')
        else:
            self.stdout.write(f'\n=== برای اجرای واقعی، --dry-run را حذف کنید ===')