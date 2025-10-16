"""
Django management command برای به‌روزرسانی شماره عملیات مالی از REC- و T- به عدد خالص
"""
from django.core.management.base import BaseCommand
from products.models import FinancialOperation


class Command(BaseCommand):
    help = 'تغییر شماره عملیات مالی دریافتی از REC- و T- به فرمت عددی خالص'

    def handle(self, *args, **options):
        self.stdout.write("🚀 شروع به‌روزرسانی شماره عملیات...")
        
        # پیدا کردن تمام عملیات با شماره REC- یا T-
        from django.db.models import Q
        operations = FinancialOperation.objects.filter(
            Q(operation_number__startswith='REC-') | 
            Q(operation_number__startswith='T-')
        ).order_by('operation_number')
        
        total_count = operations.count()
        self.stdout.write(f"🔍 تعداد عملیات با پیشوند REC- یا T-: {total_count}")
        
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS("✅ هیچ عملیاتی برای به‌روزرسانی وجود ندارد."))
            return
        
        updated_count = 0
        
        for operation in operations:
            old_number = operation.operation_number
            # تبدیل REC-000001 یا T-0000000001 به 0000000001
            # استخراج شماره
            try:
                number_part = old_number.replace('REC-', '').replace('T-', '')
                number_value = int(number_part)
                new_number = f'{number_value:010d}'
            except (ValueError, AttributeError):
                self.stdout.write(
                    self.style.ERROR(
                        f"❌ خطا در پردازش {old_number}"
                    )
                )
                continue
            
            # بررسی تکراری نبودن شماره جدید
            if FinancialOperation.objects.filter(operation_number=new_number).exists():
                self.stdout.write(
                    self.style.WARNING(
                        f"⚠️  رد شد: {old_number} -> {new_number} (شماره تکراری)"
                    )
                )
                continue
            
            # به‌روزرسانی شماره
            operation.operation_number = new_number
            operation.save(update_fields=['operation_number'])
            
            self.stdout.write(f"✅ {old_number} -> {new_number}")
            updated_count += 1
        
        self.stdout.write("\n📊 خلاصه:")
        self.stdout.write(self.style.SUCCESS(f"   ✅ به‌روزرسانی شده: {updated_count}"))
        self.stdout.write(f"   📝 کل: {total_count}")
        self.stdout.write(self.style.SUCCESS("\n✅ کار تمام شد!"))
