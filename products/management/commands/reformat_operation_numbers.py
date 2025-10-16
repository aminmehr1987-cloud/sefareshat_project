"""
Django management command برای تبدیل فرمت شماره عملیات به 10 رقم خالص
"""
from django.core.management.base import BaseCommand
from products.models import FinancialOperation


class Command(BaseCommand):
    help = 'تبدیل فرمت شماره عملیات به 10 رقم خالص (مثال: T-000001 -> 0000000001)'

    def handle(self, *args, **options):
        self.stdout.write("🚀 شروع تبدیل فرمت شماره عملیات...")
        
        # پیدا کردن تمام عملیات که شماره آن‌ها شامل حروف یا خط فاصله است
        from django.db.models import Q
        operations = FinancialOperation.objects.exclude(
            operation_number__regex=r'^\d{10}$'  # عددهای 10 رقمی خالص را رد کن
        ).filter(
            Q(operation_number__startswith='T-') |
            Q(operation_number__startswith='REC-') |
            Q(operation_number__regex=r'^\d{1,9}$')  # اعداد کمتر از 10 رقم
        ).order_by('operation_number')
        
        total_count = operations.count()
        self.stdout.write(f"🔍 تعداد عملیات برای تبدیل: {total_count}")
        
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS("✅ همه شماره‌ها قبلاً به فرمت 10 رقمی هستند."))
            return
        
        updated_count = 0
        skipped_count = 0
        
        for operation in operations:
            old_number = operation.operation_number
            
            # حذف تمام پیشوندها و خط فاصله‌ها
            number_part = old_number.replace('T-', '').replace('REC-', '').replace('-', '')
            
            try:
                # استخراج عدد و تبدیل به فرمت 10 رقمی خالص
                number_value = int(number_part)
                new_number = f'{number_value:010d}'
                
                # بررسی تکراری نبودن
                if new_number != old_number and FinancialOperation.objects.filter(operation_number=new_number).exists():
                    self.stdout.write(
                        self.style.WARNING(
                            f"⚠️  رد شد: {old_number} -> {new_number} (شماره تکراری)"
                        )
                    )
                    skipped_count += 1
                    continue
                
                # اگر شماره تغییر کرده، به‌روزرسانی کن
                if new_number != old_number:
                    operation.operation_number = new_number
                    operation.save(update_fields=['operation_number'])
                    
                    self.stdout.write(f"✅ {old_number} -> {new_number}")
                    updated_count += 1
                else:
                    skipped_count += 1
                    
            except (ValueError, AttributeError) as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"❌ خطا در پردازش {old_number}: {e}"
                    )
                )
                skipped_count += 1
        
        self.stdout.write("\n📊 خلاصه:")
        self.stdout.write(self.style.SUCCESS(f"   ✅ تبدیل شده: {updated_count}"))
        self.stdout.write(f"   ⏭️  رد شده: {skipped_count}")
        self.stdout.write(f"   📝 کل: {total_count}")
        self.stdout.write(self.style.SUCCESS("\n✅ کار تمام شد!"))
