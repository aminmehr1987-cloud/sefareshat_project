from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.db import transaction
from .models import FinancialOperation, PettyCashOperation, Fund
from .accounting_utils import accounting_manager

@receiver(post_save, sender=FinancialOperation)
def financial_operation_post_save(sender, instance, created, **kwargs):
    """
    Signal to create an accounting voucher after a FinancialOperation is saved.
    """
    # Only create a voucher if the operation is confirmed and it's a new operation
    # or if an existing operation is moved to confirmed state.
    if created and instance.status == 'CONFIRMED':
        print(f"Signal received for confirmed FinancialOperation: {instance.operation_number}")
        # Use a separate transaction to avoid database locks
        try:
            with transaction.atomic():
                accounting_manager.create_voucher_from_financial_operation(instance)
        except Exception as e:
            print(f"Error in financial_operation_post_save signal: {e}")

@receiver(post_save, sender=PettyCashOperation)
def petty_cash_operation_post_save(sender, instance, created, **kwargs):
    """
    Signal to create an accounting voucher after a PettyCashOperation is saved.
    """
    if created:
        print(f"Signal received for new PettyCashOperation: {instance.operation_number}")
        # Use a separate transaction to avoid database locks
        try:
            with transaction.atomic():
                accounting_manager.create_voucher_from_petty_cash_operation(instance)
        except Exception as e:
            print(f"Error in petty_cash_operation_post_save signal: {e}")

@receiver(post_delete, sender=FinancialOperation)
def financial_operation_post_delete(sender, instance, **kwargs):
    """
    Signal to recalculate fund balance and restore check statuses after a FinancialOperation is deleted.
    """
    # Use a separate transaction to avoid database locks
    try:
        with transaction.atomic():
            # بازگردانی وضعیت چک‌ها قبل از حذف کامل
            _restore_check_statuses_on_hard_delete(instance)
            
            target_fund = instance.fund
            # Handle implicit cash operations
            if not target_fund and instance.payment_method == 'cash':
                target_fund = Fund.objects.filter(fund_type='CASH').first()

            if target_fund:
                print(f"Signal received for deleted FinancialOperation, recalculating balance for fund: {target_fund.name}")
                target_fund.recalculate_balance()
    except Exception as e:
        print(f"Error in financial_operation_post_delete signal: {e}")


def _restore_check_statuses_on_hard_delete(operation):
    """
    بازگردانی وضعیت چک‌ها به حالت قبلی هنگام حذف کامل عملیات مالی
    """
    from .models import Check, ReceivedCheque
    
    try:
        # بازگردانی چک‌های صادر شده به حالت UNUSED
        issued_checks = Check.objects.filter(financial_operation=operation)
        if issued_checks.exists():
            print(f"Hard delete: Restoring {issued_checks.count()} issued checks to UNUSED status")
            for check in issued_checks:
                check.status = 'UNUSED'
                check.amount = 0
                check.date = timezone.now().date()
                check.payee = ''
                check.series = ''
                check.sayadi_id = ''
                check.financial_operation = None
                check.save()
        
        # بازگردانی چک‌های خرج شده به حالت RECEIVED
        spent_cheques = ReceivedCheque.objects.filter(spending_operations=operation)
        if spent_cheques.exists():
            print(f"Hard delete: Restoring {spent_cheques.count()} spent cheques to RECEIVED status")
            for cheque in spent_cheques:
                cheque.status = 'RECEIVED'
                cheque.recipient_name = ''  # پاک کردن نام گیرنده
                cheque.save()
        
        # بازگردانی چک‌های واگذار شده به حالت RECEIVED
        deposited_cheques = operation.received_cheques.filter(status='DEPOSITED')
        if deposited_cheques.exists():
            print(f"Hard delete: Restoring {deposited_cheques.count()} deposited cheques to RECEIVED status")
            for cheque in deposited_cheques:
                cheque.status = 'RECEIVED'
                cheque.deposited_bank_account = None  # پاک کردن مرجع بانک
                cheque.save()
            
        print(f"Successfully restored check statuses for hard deleted operation {operation.operation_number}")
        
    except Exception as e:
        print(f"Error restoring check statuses for hard deleted operation {operation.operation_number}: {e}")


@receiver(pre_save, sender=FinancialOperation)
def handle_check_statuses_on_operation_status_change(sender, instance, **kwargs):
    """
    مدیریت وضعیت چک‌ها هنگام تغییر وضعیت عملیات مالی
    """
    if not instance.pk:
        return  # عملیات جدید، کاری نمی‌کنیم

    try:
        old_instance = sender.objects.get(pk=instance.pk)
        
        # اگر وضعیت به CANCELLED تغییر کند، چک‌ها را بازگردانی کن
        if instance.status == 'CANCELLED' and old_instance.status != 'CANCELLED':
            _restore_check_statuses_on_operation_cancel(instance)
        
        # اگر عملیات حذف شده بازگردانی شود، چک‌ها را دوباره فعال کن
        elif old_instance.is_deleted and instance.status == 'CONFIRMED':
            _restore_check_statuses_on_operation_restore(instance)
            
    except sender.DoesNotExist:
        pass


def _restore_check_statuses_on_operation_cancel(operation):
    """
    بازگردانی وضعیت چک‌ها هنگام کنسل کردن عملیات
    """
    try:
        # بازگردانی چک‌های صادر شده به حالت UNUSED
        issued_checks = operation.issued_checks.all()
        if issued_checks.exists():
            from django.utils import timezone
            from datetime import date
            print(f"Cancel operation: Restoring {issued_checks.count()} issued checks to UNUSED status")
            for check in issued_checks:
                check.status = 'UNUSED'
                check.amount = 0
                check.date = date.today()  # تاریخ امروز به جای None
                check.payee = ''
                check.series = ''
                check.sayadi_id = ''
                check.save()
        
        # بازگردانی چک‌های خرج شده به حالت RECEIVED
        spent_cheques = operation.spent_cheques.all()
        if spent_cheques.exists():
            print(f"Cancel operation: Restoring {spent_cheques.count()} spent cheques to RECEIVED status")
            for cheque in spent_cheques:
                cheque.status = 'RECEIVED'
                cheque.recipient_name = ''  # پاک کردن نام گیرنده
                cheque.save()
        
        # بازگردانی چک‌های واگذار شده به حالت RECEIVED
        deposited_cheques = operation.received_cheques.filter(status='DEPOSITED')
        if deposited_cheques.exists():
            print(f"Cancel operation: Restoring {deposited_cheques.count()} deposited cheques to RECEIVED status")
            for cheque in deposited_cheques:
                cheque.status = 'RECEIVED'
                cheque.deposited_bank_account = None  # پاک کردن مرجع بانک
                cheque.save()
                
    except Exception as e:
        print(f"Error restoring check statuses on operation cancel: {e}")


def _restore_check_statuses_on_operation_restore(operation):
    """
    بازگردانی وضعیت چک‌ها هنگام restore کردن عملیات
    """
    try:
        # بازگردانی چک‌های صادر شده به حالت ISSUED
        issued_checks = operation.issued_checks.all()
        if issued_checks.exists():
            print(f"Restore operation: Setting {issued_checks.count()} checks to ISSUED status")
            for check in issued_checks:
                check.status = 'ISSUED'
                check.save()
        
        # بازگردانی چک‌های خرج شده به حالت SPENT
        spent_cheques = operation.spent_cheques.all()
        if spent_cheques.exists():
            print(f"Restore operation: Setting {spent_cheques.count()} cheques to SPENT status")
            for cheque in spent_cheques:
                cheque.status = 'SPENT'
                # بازگردانی نام گیرنده از عملیات مالی
                if operation.customer:
                    cheque.recipient_name = operation.customer.get_full_name()
                cheque.save()
        
        # بازگردانی چک‌های واگذار شده به حالت DEPOSITED
        deposited_cheques = operation.received_cheques.all()
        if deposited_cheques.exists():
            print(f"Restore operation: Setting {deposited_cheques.count()} cheques to DEPOSITED status")
            for cheque in deposited_cheques:
                cheque.status = 'DEPOSITED'
                # نیازی به بازگردانی deposited_bank_account نیست چون از طریق عملیات قابل شناسایی است
                cheque.save()
                
    except Exception as e:
        print(f"Error restoring check statuses on operation restore: {e}")


@receiver(post_delete, sender=PettyCashOperation)
def petty_cash_operation_post_delete(sender, instance, **kwargs):
    """
    Signal to recalculate balances after a PettyCashOperation is deleted.
    """
    # Use a separate transaction to avoid database locks
    try:
        with transaction.atomic():
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
    except Exception as e:
        print(f"Error in petty_cash_operation_post_delete signal: {e}")
