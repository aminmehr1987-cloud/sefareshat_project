from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import FinancialOperation, PettyCashOperation, Fund
from .accounting_utils import accounting_manager

@receiver(post_save, sender=FinancialOperation)
def financial_operation_post_save(sender, instance, created, **kwargs):
    """
    Signal to create an accounting voucher after a FinancialOperation is saved.
    """
    # Only create a voucher if the operation is confirmed and it's a new operation
    # or if an existing operation is moved to confirmed state.
    if instance.status == 'CONFIRMED':
        # We can add a check here to prevent re-creating vouchers if not desired.
        # For now, let's assume we want a voucher whenever it's confirmed.
        print(f"Signal received for confirmed FinancialOperation: {instance.operation_number}")
        accounting_manager.create_voucher_from_financial_operation(instance)

@receiver(post_save, sender=PettyCashOperation)
def petty_cash_operation_post_save(sender, instance, created, **kwargs):
    """
    Signal to create an accounting voucher after a PettyCashOperation is saved.
    """
    if created:
        print(f"Signal received for new PettyCashOperation: {instance.operation_number}")
        accounting_manager.create_voucher_from_petty_cash_operation(instance)

@receiver(post_delete, sender=FinancialOperation)
def financial_operation_post_delete(sender, instance, **kwargs):
    """
    Signal to recalculate fund balance after a FinancialOperation is deleted.
    """
    target_fund = instance.fund
    # Handle implicit cash operations
    if not target_fund and instance.payment_method == 'cash':
        target_fund = Fund.objects.filter(fund_type='CASH').first()

    if target_fund:
        print(f"Signal received for deleted FinancialOperation, recalculating balance for fund: {target_fund.name}")
        target_fund.recalculate_balance()

@receiver(post_delete, sender=PettyCashOperation)
def petty_cash_operation_post_delete(sender, instance, **kwargs):
    """
    Signal to recalculate balances after a PettyCashOperation is deleted.
    """
    # Recalculate the source fund's balance
    if instance.source_fund:
        print(f"Signal received for deleted PettyCashOperation, recalculating balance for source fund: {instance.source_fund.name}")
        instance.source_fund.recalculate_balance()
    elif instance.source_bank_account:
        bank_fund = Fund.objects.filter(
            fund_type='BANK',
            bank_name=instance.source_bank_account.bank.name,
            account_number=instance.source_bank_account.account_number
        ).first()
        if bank_fund:
            print(f"Signal received for deleted PettyCashOperation, recalculating balance for source bank fund: {bank_fund.name}")
            bank_fund.recalculate_balance()

    # Recalculate the main petty cash fund's balance
    petty_cash_fund = Fund.objects.filter(fund_type='PETTY_CASH').first()
    if petty_cash_fund:
        print(f"Signal received for deleted PettyCashOperation, recalculating balance for petty cash fund: {petty_cash_fund.name}")
        petty_cash_fund.recalculate_balance()
