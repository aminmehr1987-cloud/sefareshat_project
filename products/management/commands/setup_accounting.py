from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from products.models import Bank, AccountGroup, Account, Currency
from decimal import Decimal


class Command(BaseCommand):
    help = 'راه‌اندازی کامل سیستم حسابداری با گروه‌ها و حساب‌های استاندارد ایرانی'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('=' * 80))
        self.stdout.write(self.style.WARNING('راه‌اندازی سیستم حسابداری ایران'))
        self.stdout.write(self.style.WARNING('=' * 80))
        
        # 1. ایجاد ارز پیش‌فرض
        self.create_currency()
        
        # 2. ایجاد بانک‌های ایرانی
        self.create_banks()
        
        # 3. ایجاد گروه‌های حساب
        self.create_account_groups()
        
        # 4. ایجاد حساب‌های استاندارد
        self.create_standard_accounts()
        
        # 5. نمایش خلاصه
        self.show_summary()
        
        self.stdout.write(self.style.SUCCESS('\n✅ راه‌اندازی سیستم حسابداری با موفقیت انجام شد!'))

    def create_currency(self):
        """ایجاد ارز پیش‌فرض (ریال ایران)"""
        self.stdout.write('\n📍 مرحله 1: ایجاد ارز پیش‌فرض...')
        
        currency, created = Currency.objects.get_or_create(
            code='IRR',
            defaults={
                'name': 'ریال ایران',
                'symbol': 'ریال',
                'is_default': True,
                'is_active': True,
                'exchange_rate': Decimal('1.00')
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'  ✓ ایجاد شد: {currency.name}'))
        else:
            self.stdout.write(f'  ℹ قبلاً ایجاد شده: {currency.name}')
        
        self.currency = currency

    def create_banks(self):
        """ایجاد بانک‌های ایرانی"""
        self.stdout.write('\n📍 مرحله 2: ایجاد بانک‌های ایرانی...')
        
        banks_created = 0
        for code, name in Bank.IRANIAN_BANKS:
            bank, created = Bank.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'is_active': True
                }
            )
            if created:
                banks_created += 1
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ تعداد بانک‌های جدید: {banks_created}'))
        self.stdout.write(f'  ℹ مجموع بانک‌ها: {Bank.objects.count()}')

    def create_account_groups(self):
        """ایجاد گروه‌های حساب بر اساس استانداردهای ایرانی"""
        self.stdout.write('\n📍 مرحله 3: ایجاد گروه‌های حساب...')
        
        # گروه‌های اصلی حسابداری
        groups = [
            # دارایی‌ها (1xxx)
            {'code': '1000', 'name': 'دارایی‌ها', 'type': 'ASSET', 'parent': None},
            {'code': '1100', 'name': 'دارایی‌های جاری', 'type': 'ASSET', 'parent': '1000'},
            {'code': '1110', 'name': 'موجودی نقد', 'type': 'ASSET', 'parent': '1100'},
            {'code': '1120', 'name': 'بانک‌ها', 'type': 'ASSET', 'parent': '1100'},
            {'code': '1130', 'name': 'تنخواه گردان', 'type': 'ASSET', 'parent': '1100'},
            {'code': '1300', 'name': 'حساب‌ها و اسناد دریافتنی', 'type': 'ASSET', 'parent': '1000'},
            {'code': '1310', 'name': 'حساب‌های دریافتنی', 'type': 'ASSET', 'parent': '1300'},
            {'code': '1320', 'name': 'اسناد دریافتنی', 'type': 'ASSET', 'parent': '1300'},
            {'code': '1400', 'name': 'موجودی کالا', 'type': 'ASSET', 'parent': '1000'},
            {'code': '1600', 'name': 'دارایی‌های ثابت', 'type': 'ASSET', 'parent': '1000'},
            
            # بدهی‌ها (2xxx)
            {'code': '2000', 'name': 'بدهی‌ها', 'type': 'LIABILITY', 'parent': None},
            {'code': '2100', 'name': 'بدهی‌های جاری', 'type': 'LIABILITY', 'parent': '2000'},
            {'code': '2110', 'name': 'حساب‌های پرداختنی', 'type': 'LIABILITY', 'parent': '2100'},
            {'code': '2120', 'name': 'اسناد پرداختنی', 'type': 'LIABILITY', 'parent': '2100'},
            {'code': '2400', 'name': 'بدهی‌های بلندمدت', 'type': 'LIABILITY', 'parent': '2000'},
            
            # سرمایه (3xxx)
            {'code': '3000', 'name': 'سرمایه', 'type': 'EQUITY', 'parent': None},
            {'code': '3100', 'name': 'سرمایه صاحبان سهام', 'type': 'EQUITY', 'parent': '3000'},
            {'code': '3200', 'name': 'سود (زیان) انباشته', 'type': 'EQUITY', 'parent': '3000'},
            
            # درآمدها (4xxx)
            {'code': '4000', 'name': 'درآمدها', 'type': 'REVENUE', 'parent': None},
            {'code': '4100', 'name': 'درآمد فروش', 'type': 'REVENUE', 'parent': '4000'},
            {'code': '4200', 'name': 'سایر درآمدها', 'type': 'REVENUE', 'parent': '4000'},
            
            # هزینه‌ها (5xxx)
            {'code': '5000', 'name': 'هزینه‌ها', 'type': 'EXPENSE', 'parent': None},
            {'code': '5100', 'name': 'بهای تمام شده کالای فروش رفته', 'type': 'EXPENSE', 'parent': '5000'},
            {'code': '5200', 'name': 'هزینه‌های فروش', 'type': 'EXPENSE', 'parent': '5000'},
            {'code': '5300', 'name': 'هزینه‌های اداری', 'type': 'EXPENSE', 'parent': '5000'},
        ]
        
        groups_created = 0
        for group_data in groups:
            parent = None
            if group_data['parent']:
                parent = AccountGroup.objects.filter(code=group_data['parent']).first()
            
            group, created = AccountGroup.objects.get_or_create(
                code=group_data['code'],
                defaults={
                    'name': group_data['name'],
                    'type': group_data['type'],
                    'parent': parent,
                    'is_active': True
                }
            )
            
            if created:
                groups_created += 1
                self.stdout.write(f'    ✓ {group.code} - {group.name}')
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ تعداد گروه‌های جدید: {groups_created}'))

    def create_standard_accounts(self):
        """ایجاد حساب‌های استاندارد"""
        self.stdout.write('\n📍 مرحله 4: ایجاد حساب‌های استاندارد...')
        
        # یافتن یا ایجاد کاربر پیش‌فرض
        user = User.objects.filter(is_superuser=True).first()
        if not user:
            user = User.objects.first()
        
        if not user:
            self.stdout.write(self.style.ERROR('  ✗ هیچ کاربری یافت نشد! لطفاً ابتدا یک کاربر ایجاد کنید.'))
            return
        
        # حساب‌های استاندارد
        accounts = [
            # موجودی نقد (1110)
            {'code': '111001', 'name': 'صندوق اصلی', 'group': '1110', 'level': 'TAFSILI', 'parent': None},
            {'code': '111002', 'name': 'صندوق فرعی', 'group': '1110', 'level': 'TAFSILI', 'parent': None},
            
            # بانک‌ها (1120) - این حساب‌ها برای BankAccount استفاده می‌شوند
            {'code': '112001', 'name': 'بانک ملی - حساب جاری', 'group': '1120', 'level': 'TAFSILI', 'parent': None},
            {'code': '112002', 'name': 'بانک ملت - حساب جاری', 'group': '1120', 'level': 'TAFSILI', 'parent': None},
            {'code': '112003', 'name': 'بانک سپه - حساب جاری', 'group': '1120', 'level': 'TAFSILI', 'parent': None},
            {'code': '112004', 'name': 'بانک صادرات - حساب جاری', 'group': '1120', 'level': 'TAFSILI', 'parent': None},
            {'code': '112005', 'name': 'بانک پاسارگاد - حساب جاری', 'group': '1120', 'level': 'TAFSILI', 'parent': None},
            
            # تنخواه گردان (1130)
            {'code': '113001', 'name': 'تنخواه گردان', 'group': '1130', 'level': 'TAFSILI', 'parent': None},
            
            # حساب‌های دریافتنی (1310)
            {'code': '131001', 'name': 'حساب‌های دریافتنی تجاری', 'group': '1310', 'level': 'TAFSILI', 'parent': None},
            
            # اسناد دریافتنی (1320)
            {'code': '132001', 'name': 'اسناد دریافتنی تجاری', 'group': '1320', 'level': 'TAFSILI', 'parent': None},
            
            # موجودی کالا (1400)
            {'code': '140001', 'name': 'موجودی کالا', 'group': '1400', 'level': 'TAFSILI', 'parent': None},
            
            # حساب‌های پرداختنی (2110)
            {'code': '211001', 'name': 'حساب‌های پرداختنی تجاری', 'group': '2110', 'level': 'TAFSILI', 'parent': None},
            
            # اسناد پرداختنی (2120)
            {'code': '212001', 'name': 'اسناد پرداختنی تجاری', 'group': '2120', 'level': 'TAFSILI', 'parent': None},
            
            # سرمایه (3100)
            {'code': '310001', 'name': 'سرمایه اولیه', 'group': '3100', 'level': 'TAFSILI', 'parent': None},
            
            # درآمد فروش (4100)
            {'code': '410001', 'name': 'درآمد فروش کالا', 'group': '4100', 'level': 'TAFSILI', 'parent': None},
            
            # هزینه‌ها (5xxx)
            {'code': '510001', 'name': 'بهای تمام شده کالای فروش رفته', 'group': '5100', 'level': 'TAFSILI', 'parent': None},
        ]
        
        accounts_created = 0
        for acc_data in accounts:
            group = AccountGroup.objects.filter(code=acc_data['group']).first()
            
            if not group:
                self.stdout.write(self.style.WARNING(f'    ⚠ گروه {acc_data["group"]} یافت نشد'))
                continue
            
            account, created = Account.objects.get_or_create(
                code=acc_data['code'],
                defaults={
                    'group': group,
                    'name': acc_data['name'],
                    'level': acc_data['level'],
                    'parent': acc_data.get('parent'),
                    'currency': self.currency,
                    'is_active': True,
                    'description': f'حساب {acc_data["name"]}'
                }
            )
            
            if created:
                accounts_created += 1
                self.stdout.write(f'    ✓ {account.code} - {account.name}')
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ تعداد حساب‌های جدید: {accounts_created}'))

    def show_summary(self):
        """نمایش خلاصه اطلاعات"""
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.WARNING('📊 خلاصه سیستم حسابداری'))
        self.stdout.write('=' * 80)
        
        self.stdout.write(f'\n💰 ارزها: {Currency.objects.count()}')
        self.stdout.write(f'🏦 بانک‌ها: {Bank.objects.count()}')
        self.stdout.write(f'📂 گروه‌های حساب: {AccountGroup.objects.count()}')
        self.stdout.write(f'📋 حساب‌ها: {Account.objects.count()}')
        
        # نمایش حساب‌های بانکی قابل استفاده
        bank_accounts = Account.objects.filter(code__startswith='1120', is_active=True)
        if bank_accounts.exists():
            self.stdout.write(f'\n🏦 حساب‌های بانکی قابل استفاده برای BankAccount:')
            for acc in bank_accounts:
                self.stdout.write(f'   • {acc.code} - {acc.name}')
        
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('📝 نکات مهم:'))
        self.stdout.write('=' * 80)
        self.stdout.write('\n1️⃣  برای ایجاد حساب بانکی جدید:')
        self.stdout.write('   - به صفحه /admin/products/bankaccount/add/ بروید')
        self.stdout.write('   - یکی از حساب‌های بانکی بالا را انتخاب کنید')
        self.stdout.write('   - اطلاعات بانک و شماره حساب را وارد کنید')
        
        self.stdout.write('\n2️⃣  برای افزودن حساب بانکی بیشتر:')
        self.stdout.write('   - به /admin/products/account/add/ بروید')
        self.stdout.write('   - گروه را "1120 - بانک‌ها" انتخاب کنید')
        self.stdout.write('   - کد حساب جدید (مثل 112006) تعریف کنید')
        
        self.stdout.write('\n3️⃣  برای مشاهده ساختار کامل حساب‌ها:')
        self.stdout.write('   - به /admin/products/accountgroup/ بروید')
        self.stdout.write('   - به /admin/products/account/ بروید')
        
        self.stdout.write('\n')
