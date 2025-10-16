"""
Django management command برای به‌روزرسانی اطلاعات بانکی عملیات POS
"""
from django.core.management.base import BaseCommand
from products.models import FinancialOperation


class Command(BaseCommand):
    help = 'به‌روزرسانی فیلدهای bank_name و account_number برای عملیات POS'

    def handle(self, *args, **options):
        self.stdout.write("🚀 شروع به‌روزرسانی عملیات POS...")
        
        # پیدا کردن تمام عملیات POS که فیلدهای بانک خالی دارند
        pos_operations = FinancialOperation.objects.filter(
            payment_method='pos',
            status='CONFIRMED',
            is_deleted=False
        ).filter(
            bank_name__isnull=True
        ) | FinancialOperation.objects.filter(
            payment_method='pos',
            status='CONFIRMED',
            is_deleted=False,
            bank_name=''
        )
        
        total_count = pos_operations.distinct().count()
        self.stdout.write(f"🔍 تعداد عملیات POS با فیلدهای بانک خالی: {total_count}")
        
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS("✅ همه عملیات POS دارای اطلاعات بانک هستند."))
            return
        
        updated_count = 0
        skipped_count = 0
        
        for operation in pos_operations.distinct():
            # اگر دستگاه کارتخوان مشخص است
            if operation.card_reader_device:
                card_reader = operation.card_reader_device
                
                # اگر دستگاه به حساب بانکی متصل است
                if card_reader.bank_account:
                    bank_account = card_reader.bank_account
                    
                    # به‌روزرسانی فیلدهای بانک
                    operation.bank_name = bank_account.bank.name
                    operation.account_number = bank_account.account_number
                    
                    # اگر bank_account در operation ست نشده، آن را هم ست کن
                    if not operation.bank_account:
                        operation.bank_account = bank_account
                    
                    operation.save(update_fields=['bank_name', 'account_number', 'bank_account'])
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✅ به‌روزرسانی شد: {operation.operation_number} -> "
                            f"{bank_account.bank.name} ({bank_account.account_number})"
                        )
                    )
                    updated_count += 1
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"⚠️  رد شد: {operation.operation_number} - "
                            f"دستگاه {card_reader.name} به حساب بانکی متصل نیست"
                        )
                    )
                    skipped_count += 1
            
            # اگر حساب بانکی مستقیماً مشخص است (ولی فیلدهای بانک خالی است)
            elif operation.bank_account:
                bank_account = operation.bank_account
                operation.bank_name = bank_account.bank.name
                operation.account_number = bank_account.account_number
                operation.save(update_fields=['bank_name', 'account_number'])
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ به‌روزرسانی شد: {operation.operation_number} -> "
                        f"{bank_account.bank.name} ({bank_account.account_number})"
                    )
                )
                updated_count += 1
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"⚠️  رد شد: {operation.operation_number} - "
                        f"نه دستگاه کارتخوان و نه حساب بانکی مشخص نیست"
                    )
                )
                skipped_count += 1
        
        self.stdout.write("\n📊 خلاصه:")
        self.stdout.write(self.style.SUCCESS(f"   ✅ به‌روزرسانی شده: {updated_count}"))
        self.stdout.write(self.style.WARNING(f"   ⚠️  رد شده: {skipped_count}"))
        self.stdout.write(f"   📝 کل: {total_count}")
        self.stdout.write(self.style.SUCCESS("\n✅ کار تمام شد!"))
