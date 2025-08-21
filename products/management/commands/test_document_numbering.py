from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from products.models import DocumentNumber, DocumentNumberSettings, Customer, Product
from products.models import assign_document_number, get_document_number_display


class Command(BaseCommand):
    help = 'تست سیستم شماره‌گذاری اسناد'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=5,
            help='تعداد اسناد تست برای ایجاد'
        )
        parser.add_argument(
            '--starting-number',
            type=int,
            default=1,
            help='شماره شروع برای سیستم'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 شروع تست سیستم شماره‌گذاری اسناد...')
        )
        
        # تنظیم شماره شروع
        try:
            starting_number = options['starting_number']
            if starting_number > 1:
                # ایجاد کاربر تست
                test_user, created = User.objects.get_or_create(
                    username='test_admin',
                    defaults={
                        'first_name': 'تست',
                        'last_name': 'ادمین',
                        'email': 'test@example.com',
                        'is_staff': True,
                        'is_superuser': True
                    }
                )
                
                # تنظیم شماره شروع
                settings = DocumentNumberSettings.set_starting_number(starting_number, test_user)
                self.stdout.write(
                    self.style.SUCCESS(f'✅ شماره شروع به {starting_number} تنظیم شد')
                )
            else:
                # استفاده از تنظیمات پیش‌فرض
                settings = DocumentNumberSettings.get_settings()
                self.stdout.write(
                    self.style.SUCCESS(f'✅ استفاده از تنظیمات پیش‌فرض - شماره بعدی: {settings.next_number}')
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ خطا در تنظیم شماره شروع: {e}')
            )
            return
        
        # ایجاد مشتری تست
        test_customer, created = Customer.objects.get_or_create(
            mobile='09123456789',
            defaults={
                'first_name': 'مشتری',
                'last_name': 'تست',
                'store_name': 'فروشگاه تست'
            }
        )
        
        # ایجاد محصول تست
        test_product, created = Product.objects.get_or_create(
            code='TEST001',
            defaults={
                'name': 'محصول تست',
                'brand': 'برند تست',
                'car_group': 'عمومی',
                'price': 100000,
                'purchase_price': 80000,
                'quantity': 100
            }
        )
        
        # تست شماره‌گذاری برای مشتری
        self.stdout.write('\n📝 تست شماره‌گذاری برای مشتری:')
        customer_doc = assign_document_number(
            test_customer, 
            'CUSTOMER_BALANCE', 
            User.objects.first(),
            'ایجاد مشتری تست'
        )
        if customer_doc:
            self.stdout.write(
                self.style.SUCCESS(f'✅ مشتری با شماره سند {customer_doc.document_number} ثبت شد')
            )
        
        # تست شماره‌گذاری برای محصول
        self.stdout.write('\n📝 تست شماره‌گذاری برای محصول:')
        product_doc = assign_document_number(
            test_product, 
            'OTHER', 
            User.objects.first(),
            'ایجاد محصول تست'
        )
        if product_doc:
            self.stdout.write(
                self.style.SUCCESS(f'✅ محصول با شماره سند {product_doc.document_number} ثبت شد')
            )
        
        # تست شماره‌گذاری‌های متعدد
        count = options['count']
        self.stdout.write(f'\n📝 ایجاد {count} سند تست:')
        
        for i in range(count):
            # ایجاد مشتری‌های تست
            test_customer_i, created = Customer.objects.get_or_create(
                mobile=f'0912345678{i}',
                defaults={
                    'first_name': f'مشتری{i}',
                    'last_name': f'تست{i}',
                    'store_name': f'فروشگاه تست{i}'
                }
            )
            
            # اختصاص شماره سند
            doc = assign_document_number(
                test_customer_i, 
                'CUSTOMER_BALANCE', 
                User.objects.first(),
                f'مشتری تست شماره {i+1}'
            )
            
            if doc:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ سند {i+1}: مشتری {test_customer_i.get_full_name()} - شماره: {doc.document_number}')
                )
        
        # نمایش آمار
        stats = DocumentNumberSettings.get_statistics()
        self.stdout.write('\n📊 آمار سیستم شماره‌گذاری:')
        self.stdout.write(f'   شماره فعلی: {stats["current_number"]}')
        self.stdout.write(f'   شماره بعدی: {stats["next_number"]}')
        self.stdout.write(f'   کل اسناد: {stats["total_documents"]}')
        self.stdout.write(f'   اسناد حذف شده: {stats["deleted_documents"]}')
        self.stdout.write(f'   وضعیت: {"فعال" if stats["is_active"] else "غیرفعال"}')
        
        # نمایش آخرین اسناد
        self.stdout.write('\n📋 آخرین اسناد ایجاد شده:')
        recent_docs = DocumentNumber.objects.filter(is_deleted=False).order_by('-document_number')[:5]
        for doc in recent_docs:
            self.stdout.write(
                f'   سند {doc.document_number}: {doc.get_document_type_display()} - {doc.related_object_str}'
            )
        
        self.stdout.write(
            self.style.SUCCESS('\n🎉 تست سیستم شماره‌گذاری با موفقیت انجام شد!')
        ) 