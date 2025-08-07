from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from products.models import Bank, AccountGroup, Account, Currency
from decimal import Decimal


class Command(BaseCommand):
    help = 'Initialize accounting system with standard accounts, banks, and account groups'

    def handle(self, *args, **options):
        self.stdout.write('Starting accounting system initialization...')
        
        # Create default currency (IRR)
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
            self.stdout.write(self.style.SUCCESS(f'Created currency: {currency.name}'))
        else:
            self.stdout.write(f'Currency already exists: {currency.name}')

        # Create Iranian banks
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
        
        self.stdout.write(self.style.SUCCESS(f'Created {banks_created} Iranian banks'))

        # Create main account groups
        groups_created = 0
        for code, name in AccountGroup.MAIN_GROUPS:
            # Determine account type based on code
            if code.startswith('1'):
                account_type = 'ASSET'
            elif code.startswith('2'):
                account_type = 'LIABILITY'
            elif code.startswith('3'):
                account_type = 'EQUITY'
            elif code.startswith('4'):
                account_type = 'REVENUE'
            else:
                account_type = 'EXPENSE'
            
            group, created = AccountGroup.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'type': account_type,
                    'is_active': True
                }
            )
            if created:
                groups_created += 1
        
        self.stdout.write(self.style.SUCCESS(f'Created {groups_created} account groups'))

        # Create standard accounts
        accounts_created = Account.create_standard_accounts(currency)
        self.stdout.write(self.style.SUCCESS(f'Created {len(accounts_created)} standard accounts'))

        self.stdout.write(self.style.SUCCESS('Accounting system initialization completed successfully!'))
        
        # Print summary
        self.stdout.write('\nSummary:')
        self.stdout.write(f'- Banks: {Bank.objects.count()}')
        self.stdout.write(f'- Account Groups: {AccountGroup.objects.count()}')
        self.stdout.write(f'- Accounts: {Account.objects.count()}')
        self.stdout.write(f'- Currencies: {Currency.objects.count()}') 