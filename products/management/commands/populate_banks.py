from django.core.management.base import BaseCommand
from products.models import Bank


class Command(BaseCommand):
    help = 'Populate banks from IRANIAN_BANKS choices'

    def handle(self, *args, **options):
        banks_created = 0
        banks_updated = 0
        
        for code, name in Bank.IRANIAN_BANKS:
            bank, created = Bank.objects.get_or_create(
                code=code,
                defaults={'name': name}
            )
            
            if created:
                banks_created += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created bank: {name} ({code})')
                )
            else:
                # Update existing bank name if it's different
                if bank.name != name:
                    bank.name = name
                    bank.save()
                    banks_updated += 1
                    self.stdout.write(
                        self.style.WARNING(f'Updated bank: {name} ({code})')
                    )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully processed banks. Created: {banks_created}, Updated: {banks_updated}'
            )
        )
        
        # Show sample banks
        sample_banks = Bank.objects.values_list('name', 'code')[:5]
        self.stdout.write(f'Sample banks: {list(sample_banks)}') 