from django.core.management.base import BaseCommand
from products.models import Fund
from django.db import models


class Command(BaseCommand):
    help = 'حذف صندوق‌های خالی و غیرفعال'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='نمایش صندوق‌هایی که حذف خواهند شد بدون حذف کردن',
        )
        parser.add_argument(
            '--inactive-only',
            action='store_true',
            help='فقط صندوق‌های غیرفعال را حذف کن',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        inactive_only = options['inactive_only']

        if inactive_only:
            funds_to_delete = Fund.objects.filter(is_active=False)
            self.stdout.write(f'صندوق‌های غیرفعال یافت شده: {funds_to_delete.count()}')
        else:
            # صندوق‌های خالی (موجودی صفر) یا غیرفعال
            funds_to_delete = Fund.objects.filter(
                models.Q(current_balance=0) | models.Q(is_active=False)
            )
            self.stdout.write(f'صندوق‌های خالی یا غیرفعال یافت شده: {funds_to_delete.count()}')

        if funds_to_delete.exists():
            self.stdout.write('\nصندوق‌های یافت شده:')
            for fund in funds_to_delete:
                self.stdout.write(
                    f'- ID: {fund.id}, نام: {fund.name}, نوع: {fund.get_fund_type_display()}, '
                    f'موجودی: {fund.current_balance}, فعال: {fund.is_active}'
                )

            if not dry_run:
                count = funds_to_delete.count()
                funds_to_delete.delete()
                self.stdout.write(
                    self.style.SUCCESS(f'\n{count} صندوق با موفقیت حذف شد.')
                )
            else:
                self.stdout.write(
                    self.style.WARNING('\nاین یک تست است. هیچ صندوقی حذف نشد.')
                )
        else:
            self.stdout.write(
                self.style.SUCCESS('هیچ صندوق خالی یا غیرفعالی یافت نشد.')
            ) 