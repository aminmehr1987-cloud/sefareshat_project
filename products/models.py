from django.db import models, transaction, IntegrityError
from django.utils import timezone
import jdatetime
from django.contrib.auth.models import User
# from django.contrib import admin # این خط هم احتمالا باید حذف شود، زیرا admin در models.py استفاده نمی‌شود.
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Max, Sum, F, DecimalField, Q
import uuid
from django.utils.translation import gettext_lazy as _
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db.models.signals import pre_save
from decimal import Decimal
from django.core.validators import MinValueValidator





class Customer(models.Model):
    first_name = models.CharField(max_length=100, verbose_name="نام")
    last_name = models.CharField(max_length=100, verbose_name="نام خانوادگی")
    store_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="نام فروشگاه")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="تلفن ثابت")
    mobile = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="شماره موبایل",
        error_messages={
            'unique': 'مشتری دیگری با این شماره همراه قبلاً ثبت شده است.'
        }
    )
    address = models.TextField(blank=True, null=True, verbose_name="آدرس")
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='created_customers', verbose_name="ایجاد شده توسط"
    )
    user = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='customer_profile', verbose_name="کاربر مرتبط"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")

    class Meta:
        verbose_name = "مشتری"
        verbose_name_plural = "مشتریان"

    def __str__(self):
        return f'{self.first_name} {self.last_name}'

    def get_full_name(self):
        """Return the full name of the customer"""
        return f'{self.first_name} {self.last_name}'


class Warehouse(models.Model):
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="نام انبار"
    )
    user = models.OneToOneField(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='warehouse',
        verbose_name="کاربر انباردار"
    )

    def __str__(self):
        return self.name

class Product(models.Model):
    PAYMENT_TERMS_CHOICES = [
        ('cash', 'نقدی'),
        ('1m', '1 ماهه'),
        ('2m', '2 ماهه'),
        ('3m', '3 ماهه'),
        ('4m', '4 ماهه'),
    ]

    brand = models.CharField(
        max_length=100,
        verbose_name="برند",
        blank=True,
    )
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="کد کالا"
    )
    name = models.CharField(
        max_length=200,
        verbose_name="نام کالا"
    )
    car_group = models.CharField(
        max_length=100,
        default="عمومی",
        verbose_name="گروه خودرو"
    )
    price = models.DecimalField(
        max_digits=100,
        decimal_places=0,
        verbose_name="قیمت"
    )
    purchase_price = models.DecimalField(
        max_digits=100,
        decimal_places=0,
        verbose_name="قیمت خرید",
        default=0
    )
    quantity = models.PositiveIntegerField(
        default=0,
        verbose_name="موجودی"
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="انبار"
    )

    image = models.ImageField(
        upload_to='product_images/',
        blank=True,
        null=True,
        verbose_name="تصویر کالا"
    )
    
    max_payment_term = models.CharField(
        max_length=10,
        choices=PAYMENT_TERMS_CHOICES,
        blank=True,
        null=True,
        verbose_name="حداکثر مهلت تسویه"
    )
    
    created_at = models.DateTimeField(default=timezone.now, verbose_name="تاریخ ایجاد")

    normalized_name = models.CharField(max_length=255, blank=True, db_index=True)

    profit_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="درصد سود",
        default=0
    )

    def save(self, *args, **kwargs):
        from sefareshat_project.utils import normalize_text
        self.normalized_name = normalize_text(self.name)
        super().save(*args, **kwargs)

    def get_available_payment_terms(self):
        payment_terms_map = {
            'cash': ['cash'],
            '1m': ['cash', '1m'],
            '2m': ['cash', '1m', '2m'],
            '3m': ['cash', '1m', '2m', '3m'],
            '4m': ['cash', '1m', '2m', '3m', '4m'],
        }
        return payment_terms_map.get(self.max_payment_term, ['cash'])

    def __str__(self):
        return f"{self.name} ({self.code})"

class Order(models.Model):
    STATUS_CHOICES = [
        ('cart', 'سبد خرید'),
        ('pending', 'در انتظار تأیید'),
        ('warehouse', 'ارسال شده به انبار'),
        ('ready', 'آماده تحویل'),
        ('delivered', 'تحویل داده شده'),
        ('parent', 'تفکیک شده به انبارها'),
        ('completed', 'نهایی شده'),
        ('backorder', 'در انتظار موجودی'),
        ('waiting_for_customer_shipment', 'در انتظار ارسال به مشتری'),
        ('sent_to_warehouse', ' ارسال شده به انبار از بک اوردر'),
        ('waiting_for_warehouse_confirmation', 'در انتظار تایید انباردار'),
        
    ]

    order_number = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="شماره درخواست",
        blank=True,
        null=True
    )
    document_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="شماره سند"
    )
    package_count = models.PositiveIntegerField(
        default=0,
        null=True,
        blank=True,
        verbose_name="تعداد بسته"
    )
    courier_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="نام پیک"
    )
    visitor_name = models.CharField(max_length=100, verbose_name="نام ویزیتور")
    customer = models.ForeignKey(
        Customer, 
        on_delete=models.PROTECT,   # پیشنهاد امنیتی: سفارش بدون مشتری باقی نماند
        verbose_name="مشتری"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ثبت")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ به‌روزرسانی")
    payment_term = models.CharField(
        max_length=10,
        choices=Product.PAYMENT_TERMS_CHOICES,
        verbose_name="شرایط تسویه"
    )

    status = models.CharField(
        max_length=100,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="وضعیت سفارش"
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        verbose_name="سفارش مادر (قدیمی)"
    )
    is_sub_order = models.BooleanField(default=False, verbose_name="آیا زیرسفارش است؟ (قدیمی)")
    parent_order = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sub_orders',
        verbose_name="سفارش والد (جدید)"
    )

    warehouse = models.ForeignKey(
        'Warehouse',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='orders',
        verbose_name="انبار"
    )

    total_price = models.DecimalField(
        max_digits=100,
        decimal_places=0,
        default=0,
        verbose_name="جمع کل سفارش"
    )



    def save(self, *args, **kwargs):
        is_new = not self.pk

        if is_new and not self.order_number:
            now_time = timezone.now()
            today_jalali = jdatetime.datetime.fromgregorian(datetime=now_time).strftime('%Y%m%d')

            if self.parent_order:
                if self.status == 'backorder':
                    # استفاده از نام انبار ذخیره‌شده (در views مقداردهی شده)
                    warehouse_name = getattr(self, 'warehouse_name', None)

                    # تعیین پیشوند بر اساس نام انبار
                    if warehouse_name == "انبار فروشگاه":
                        prefix = "BO-SHOP"
                    elif warehouse_name == "انبار پخش":
                        prefix = "BO-PAKHSH"
                    else:
                        prefix = "BO"

                    self.order_number = f"{prefix}-{self.parent_order.order_number}"

                else:
                    # برای سفارش‌های عادی تفکیک‌شده بر اساس انبار
                    warehouse_name = getattr(self, 'warehouse_name', None)
                    if warehouse_name:
                        prefix = "PAKHSH" if warehouse_name == "انبار پخش" else "SHOP"
                        self.order_number = f"{prefix}-{self.parent_order.order_number}"
                    else:
                        # در صورت نبودن نام انبار
                        self.order_number = f"SUB-{self.parent_order.order_number}"
            else:
                # سفارش اصلی
                count_today = Order.objects.filter(
                    order_number__startswith=today_jalali,
                    parent_order__isnull=True
                ).count() + 1
                self.order_number = f"{today_jalali}{count_today:03d}"

        super().save(*args, **kwargs)

        # ذخیره تاریخچه وضعیت فقط اگر وضعیت جدید است یا تغییر کرده
        if is_new:
            OrderStatusHistory.objects.create(
                order=self,
                status=self.status
            )
        elif 'status' in kwargs.get('update_fields', ['status']):
            old_order = Order.objects.get(pk=self.pk)
            if old_order.status != self.status:
                OrderStatusHistory.objects.create(
                    order=self,
                    status=self.status
                ) 
    
    
    def get_sub_orders(self):
        return self.sub_orders.all().order_by('-created_at')
    
    @property
    def customer_name(self):
        if self.customer:
            return f"{self.customer.first_name} {self.customer.last_name}"

    def __str__(self):
        return f"{self.order_number} - {self.customer_name}" + (f" (زیرمجموعه {self.parent_order.order_number})" if self.parent_order else "")

    def get_status_history(self):
        return self.status_history.all()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['document_number'],
                name='unique_document_number',
                condition=models.Q(document_number__isnull=False) & ~models.Q(document_number='')
            )
        ]


class DocumentNumber(models.Model):
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name='document_numbers',
        verbose_name="انبار"
    )
    number = models.PositiveIntegerField(verbose_name="شماره سند")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    order_item = models.OneToOneField(
        'OrderItem',
        on_delete=models.CASCADE,
        related_name='document_number_obj',
        verbose_name="آیتم سفارش"
    )

    class Meta:
        unique_together = ('warehouse', 'number')
        ordering = ['-number']
        verbose_name = "شماره سند"
        verbose_name_plural = "شماره سندها"

    def __str__(self):
        # این متد __str__ برای DocumentNumber به 'order' و 'product' نیاز دارد که در مدل نیست.
        # باید به OrderItem مرتبط باشد یا فقط فیلدهای خود DocumentNumber را استفاده کند.
        # مثلا:
        return f"{self.warehouse.name} - سند: {self.number}"
    
    @classmethod
    def get_next_number(cls, warehouse):
        last_number = cls.objects.filter(warehouse=warehouse).order_by('-number').first()
        return (last_number.number + 1) if last_number else 1

class OrderItem(models.Model):
    WAREHOUSE_STATUS_CHOICES = [
        ('pending', 'در انتظار تایید انبار'),
        ('confirmed', 'تایید شده توسط انبار'),
        ('ready', 'آماده ارسال'),
        ('out_of_stock', 'ناموجود'),
        ('backorder', 'در انتظار موجودی'),
        ('pending_supply', 'در انتظار تامین موجودی'),
        ('waiting_for_warehouse_confirmation', 'در انتظار تایید انباردار'),  # اصلاح شده به 'waiting_for_warehouse_confirmation'
        
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name="سفارش")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="محصول")
    requested_quantity = models.IntegerField(null=True, blank=True, verbose_name="تعداد درخواستی")
    allocated_quantity = models.IntegerField(default=0, verbose_name="تعداد تخصیص یافته")
    price = models.DecimalField(max_digits=50, decimal_places=0, null=True, blank=True, verbose_name="قیمت")
    payment_term = models.CharField(max_length=50, choices=Product.PAYMENT_TERMS_CHOICES, default='cash', verbose_name="شرایط پرداخت")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="انبار")
    warehouse_status = models.CharField(max_length=100, choices=WAREHOUSE_STATUS_CHOICES, default='pending', verbose_name="وضعیت انبار")
    warehouse_note = models.TextField(blank=True, null=True, verbose_name="یادداشت انبار")

    class Meta:
        verbose_name = "آیتم سفارش"
        verbose_name_plural = "آیتم‌های سفارش"

    def __str__(self):
        order_number = self.order.order_number if self.order and self.order.order_number else "بدون شماره سفارش"
        product_name = self.product.name if self.product else "بدون محصول"
        return f"{order_number} - {product_name} - درخواستی: {self.requested_quantity} / تخصیص: {self.allocated_quantity}"
    
    @property
    def total_price(self):
        if self.price:
            if self.allocated_quantity:
                return self.allocated_quantity * self.price
            elif self.requested_quantity:
                return self.requested_quantity * self.price
        return 0

    def is_backorder(self):
        return self.warehouse_status == 'backorder'
    is_backorder.boolean = True
    is_backorder.short_description = 'بک اوردر'

    @property
    def backorder_quantity(self):
        if self.requested_quantity is not None and self.allocated_quantity is not None:
            return max(self.requested_quantity - self.allocated_quantity, 0)
        return 0

class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')
    status = models.CharField(max_length=50, choices=Order.STATUS_CHOICES)
    timestamp = models.DateTimeField(default=timezone.now)
    note = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']

# --- مدل Shipment در جای صحیح (آخرین مدل در فایل) ---
class Shipment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'در انتظار'),
        ('in_transit', 'در حال ارسال'),
        ('delivered', 'تحویل داده شده'),
    ]

    order = models.ForeignKey('Order', on_delete=models.CASCADE, related_name='shipments', verbose_name="سفارش مرتبط")
    parent_order = models.ForeignKey(
        'Order', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='parent_shipments', 
        verbose_name="سفارش اصلی"
    )
    shipment_number = models.CharField(max_length=50, unique=True, verbose_name="شماره ارسال")
    shipment_date = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ارسال")
    courier_name = models.CharField(max_length=100, verbose_name="نام پیک")
    is_backorder = models.BooleanField(default=False, verbose_name="ارسال بک‌اوردر")
    description = models.TextField(blank=True, null=True, verbose_name="توضیحات")
    items = models.ManyToManyField('OrderItem', through='ShipmentItem', related_name='shipments')
    sub_orders = models.ManyToManyField(
        'Order',
        related_name='included_in_shipments',
        verbose_name="زیرسفارش‌های شامل شده",
        blank=True
    )
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="وضعیت ارسال"
    )
    
    def save(self, *args, **kwargs):
        if not self.parent_order and self.order and self.order.parent_order:
            self.parent_order = self.order.parent_order
            
        if not self.shipment_number:
            today_jalali = jdatetime.date.today().strftime('%Y%m%d')
            
            # استفاده از select_for_update برای جلوگیری از race condition
            with transaction.atomic():
                last_shipment = Shipment.objects.select_for_update().filter(
                    shipment_number__startswith=f"{today_jalali}-"
                ).order_by('-shipment_number').first()

                if last_shipment:
                    try:
                        last_suffix = int(last_shipment.shipment_number.split('-')[-1])
                        new_suffix = last_suffix + 1
                    except ValueError:
                        new_suffix = 1
                else:
                    new_suffix = 1
                
                self.shipment_number = f"{today_jalali}-{new_suffix:03d}"
        
        try:
            # چک کردن وجود ارسال قبلی برای این سفارش
            if not self.pk and Shipment.objects.filter(order=self.order).exists():
                raise ValidationError('برای این سفارش قبلاً یک ارسال ثبت شده است.')
            super().save(*args, **kwargs)
        except IntegrityError:
            raise ValidationError('خطا در ذخیره‌سازی ارسال. لطفاً مجدداً تلاش کنید.')

    def __str__(self):
        return f"ارسال {self.shipment_number}"

    class Meta:
        ordering = ['-shipment_date']
        verbose_name = "ارسال"
        verbose_name_plural = "ارسال‌ها"
        constraints = [
            models.UniqueConstraint(
                fields=['order'],
                name='unique_order_shipment'
            )
        ]


class ShipmentItem(models.Model):
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE)
    order_item = models.ForeignKey('OrderItem', on_delete=models.CASCADE)
    quantity_shipped = models.PositiveIntegerField(verbose_name="تعداد ارسال شده")

    class Meta:
        verbose_name = "قلم ارسالی"
        verbose_name_plural = "اقلام ارسالی"
        unique_together = ['shipment', 'order_item']  # جلوگیری از تکرار آیتم در یک ارسال


class Notification(models.Model):
    title = models.CharField(max_length=255, verbose_name="عنوان")
    message = models.TextField(verbose_name="پیام")
    target_user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="کاربر هدف")
    read = models.BooleanField(default=False, verbose_name="خوانده شده؟")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    # فیلدهای جدید جهت ذخیره اطلاعات داینامیک اعلان
    product_title = models.CharField(max_length=255, verbose_name="نام کالا", blank=True, null=True)
    order_number = models.CharField(max_length=50, verbose_name="شماره سفارش", blank=True, null=True)
    customer_name = models.CharField(max_length=255, verbose_name="نام مشتری", blank=True, null=True)

    def __str__(self):
        return f"{self.title} - برای {self.target_user.username}"
@receiver(post_save, sender=OrderItem)
def update_order_total_on_item_save(sender, instance, created, **kwargs):
    """
    هنگام ذخیره (ایجاد یا به‌روزرسانی) هر OrderItem، جمع کل سفارش مربوطه را به‌روزرسانی می‌کند.
    """
    # اطمینان حاصل کنید که instance.order وجود دارد
    if instance.order:
        # جمع کل قیمت‌های تخصیص یافته OrderItemهای مربوط به این سفارش را محاسبه کنید
        # از allocated_quantity استفاده می‌کنیم چون نشان‌دهنده کالای تایید شده است.
        total_sum = instance.order.items.aggregate(
            total=Sum(F('allocated_quantity') * F('price'), output_field=DecimalField())
        )['total']
        
        # اگر هیچ OrderItemای وجود نداشت (مثلاً همه حذف شدند)، جمع کل را صفر کنید
        if total_sum is None:
            total_sum = 0
            
        # فقط در صورتی به‌روزرسانی کنید که مقدار تغییر کرده باشد تا از حلقه‌های بی‌نهایت جلوگیری شود
        if instance.order.total_price != total_sum:
            instance.order.total_price = total_sum
            instance.order.save(update_fields=['total_price']) # فقط فیلد total_price را به‌روزرسانی کنید

@receiver(models.signals.post_delete, sender=OrderItem)
def update_order_total_on_item_delete(sender, instance, **kwargs):
    """
    هنگام حذف یک OrderItem، جمع کل سفارش مربوطه را به‌روزرسانی می‌کند.
    """
    if instance.order:
        # پس از حذف، دوباره جمع کل را محاسبه کنید
        total_sum = instance.order.items.aggregate(
            total=Sum(F('allocated_quantity') * F('price'), output_field=DecimalField())
        )['total']
        
        if total_sum is None:
            total_sum = 0

        if instance.order.total_price != total_sum:
            instance.order.total_price = total_sum
            instance.order.save(update_fields=['total_price'])   


class PriceChange(models.Model):
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='price_changes', verbose_name="محصول")
    old_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="قیمت قدیم")
    new_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="قیمت جدید")
    change_date = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ تغییر")

    class Meta:
        verbose_name = "تغییر قیمت"
        verbose_name_plural = "تغییرات قیمت"
        ordering = ['-change_date']

    @property
    def percentage_change(self):
        if self.old_price == 0:
            return float('inf') if self.new_price > 0 else 0
        return ((self.new_price - self.old_price) / self.old_price) * 100    

    def __str__(self):
        return f"تغییر قیمت برای {self.product.name} در {self.change_date.strftime('%Y-%m-%d')}"   
       
           
@receiver(pre_save, sender=Product)
def create_price_change_on_update(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_instance = Product.objects.get(pk=instance.pk)
            if old_instance.price != instance.price:
                PriceChange.objects.create(
                    product=instance,
                    old_price=old_instance.price,
                    new_price=instance.price,
                )
        except Product.DoesNotExist:
            pass
        

from django_jalali.db import models as jmodels

class PurchaseInvoice(models.Model):
    STATUS_CHOICES = [
        ('draft', 'پیش‌نویس'),
        ('registered', 'ثبت شده'),
        ('confirmed', 'تایید شده'),
        ('cancelled', 'باطل شده'),
    ]
    invoice_number = models.CharField(max_length=100, verbose_name="شماره فاکتور", unique=True)
    invoice_date = jmodels.jDateField(verbose_name="تاریخ فاکتور")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, verbose_name="طرف حساب")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="ثبت‌کننده")
    total_amount = models.DecimalField(max_digits=18, decimal_places=0, verbose_name="جمع کل فاکتور")
    description = models.TextField(blank=True, null=True, verbose_name="توضیحات")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='registered', verbose_name="وضعیت")
    created_at = jmodels.jDateTimeField(auto_now_add=True, verbose_name="تاریخ ثبت")
    updated_at = jmodels.jDateTimeField(auto_now=True, verbose_name="تاریخ ویرایش")
    # Settlement fields
    settle_cash = models.DecimalField(max_digits=18, decimal_places=0, default=0, verbose_name="تسویه نقدی")
    settle_card = models.DecimalField(max_digits=18, decimal_places=0, default=0, verbose_name="تسویه کارتخوان")
    settle_bank = models.DecimalField(max_digits=18, decimal_places=0, default=0, verbose_name="تسویه بانکی")
    settle_cheque = models.DecimalField(max_digits=18, decimal_places=0, default=0, verbose_name="تسویه چک")
    settle_balance = models.DecimalField(max_digits=18, decimal_places=0, default=0, verbose_name="مانده حساب")
    settle_extra_discount = models.DecimalField(max_digits=18, decimal_places=0, default=0, verbose_name="تخفیف مازاد")

    class Meta:
        verbose_name = "فاکتور خرید"
        verbose_name_plural = "فاکتورهای خرید"
        ordering = ['-invoice_date', '-created_at']

    def __str__(self):
        return f"فاکتور {self.invoice_number} - {self.customer.get_full_name()}"

    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status)

class PurchaseInvoiceItem(models.Model):
    invoice = models.ForeignKey(PurchaseInvoice, on_delete=models.CASCADE, related_name='items', verbose_name="فاکتور خرید")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name="کالا")
    quantity = models.PositiveIntegerField(verbose_name="تعداد")
    price = models.DecimalField(max_digits=18, decimal_places=0, verbose_name="قیمت")
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="درصد تخفیف")
    profit_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="درصد سود")
    total = models.DecimalField(max_digits=18, decimal_places=0, verbose_name="مبلغ کل")
    description = models.CharField(max_length=255, blank=True, null=True, verbose_name="توضیحات")

    class Meta:
        verbose_name = "آیتم فاکتور خرید"
        verbose_name_plural = "آیتم‌های فاکتور خرید"

    def __str__(self):
        return f"{self.product.name} - {self.quantity} عدد در فاکتور {self.invoice.invoice_number}"


class SalesInvoice(models.Model):
    STATUS_CHOICES = [
        ('draft', 'پیش‌نویس'),
        ('registered', 'ثبت شده'),
        ('confirmed', 'تایید شده'),
        ('cancelled', 'باطل شده'),
    ]
    invoice_number = models.CharField(max_length=100, verbose_name="شماره فاکتور", unique=True)
    invoice_date = jmodels.jDateField(verbose_name="تاریخ فاکتور")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, verbose_name="طرف حساب")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="ثبت‌کننده")
    total_amount = models.DecimalField(max_digits=18, decimal_places=0, verbose_name="جمع کل فاکتور")
    description = models.TextField(blank=True, null=True, verbose_name="توضیحات")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='registered', verbose_name="وضعیت")
    created_at = jmodels.jDateTimeField(auto_now_add=True, verbose_name="تاریخ ثبت")
    updated_at = jmodels.jDateTimeField(auto_now=True, verbose_name="تاریخ ویرایش")
    # Settlement fields
    settle_cash = models.DecimalField(max_digits=18, decimal_places=0, default=0, verbose_name="تسویه نقدی")
    settle_card = models.DecimalField(max_digits=18, decimal_places=0, default=0, verbose_name="تسویه کارتخوان")
    settle_bank = models.DecimalField(max_digits=18, decimal_places=0, default=0, verbose_name="تسویه بانکی")
    settle_cheque = models.DecimalField(max_digits=18, decimal_places=0, default=0, verbose_name="تسویه چک")
    settle_balance = models.DecimalField(max_digits=18, decimal_places=0, default=0, verbose_name="مانده حساب")
    settle_extra_discount = models.DecimalField(max_digits=18, decimal_places=0, default=0, verbose_name="تخفیف مازاد")

    class Meta:
        verbose_name = "فاکتور فروش"
        verbose_name_plural = "فاکتورهای فروش"
        ordering = ['-invoice_date', '-created_at']

    def __str__(self):
        return f"فاکتور {self.invoice_number} - {self.customer.get_full_name()}"


class SalesInvoiceItem(models.Model):
    invoice = models.ForeignKey(SalesInvoice, on_delete=models.CASCADE, related_name='items', verbose_name="فاکتور فروش")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name="کالا")
    quantity = models.PositiveIntegerField(verbose_name="تعداد")
    price = models.DecimalField(max_digits=18, decimal_places=0, verbose_name="قیمت")
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="درصد تخفیف")
    profit_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="درصد سود")
    total = models.DecimalField(max_digits=18, decimal_places=0, verbose_name="مبلغ کل")
    description = models.CharField(max_length=255, blank=True, null=True, verbose_name="توضیحات")

    class Meta:
        verbose_name = "آیتم فاکتور فروش"
        verbose_name_plural = "آیتم‌های فاکتور فروش"

    def __str__(self):
        return f"{self.product.name} - {self.quantity} عدد در فاکتور {self.invoice.invoice_number}"


class AccountingReport(models.Model):
    REPORT_TYPE_CHOICES = [
        ('daily', 'گزارش روزانه'),
        ('weekly', 'گزارش هفتگی'),
        ('monthly', 'گزارش ماهانه'),
        ('yearly', 'گزارش سالانه'),
        ('custom', 'گزارش دلخواه'),
    ]

    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES, verbose_name="نوع گزارش")
    start_date = jmodels.jDateField(verbose_name="تاریخ شروع")
    end_date = jmodels.jDateField(verbose_name="تاریخ پایان")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="ایجاد کننده")
    created_at = jmodels.jDateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    
    # Box 1: Total Sales
    total_sales = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="مجموع فروش")
    total_sales_count = models.PositiveIntegerField(default=0, verbose_name="تعداد فاکتورهای فروش")
    
    # Box 2: Total Purchases
    total_purchases = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="مجموع خرید")
    total_purchases_count = models.PositiveIntegerField(default=0, verbose_name="تعداد فاکتورهای خرید")
    
    # Box 3: Settlement Summary
    total_cash_settled = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="مجموع تسویه نقدی")
    total_card_settled = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="مجموع تسویه کارت")
    total_bank_settled = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="مجموع تسویه بانکی")
    total_cheque_settled = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="مجموع تسویه چک")
    
    # Box 4: Outstanding Balances
    total_customer_balance = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="مجموع مانده حساب مشتریان")
    total_supplier_balance = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="مجموع مانده حساب تامین‌کنندگان")
    
    # Box 5: Profit Analysis
    total_profit = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="مجموع سود")
    average_profit_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="میانگین درصد سود")
    
    # Box 6: Discounts
    total_discounts = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="مجموع تخفیفات")
    total_extra_discounts = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="مجموع تخفیفات مازاد")

    # Box 7: Account Statements (معین اشخاص)
    total_transactions = models.PositiveIntegerField(default=0, verbose_name="تعداد کل تراکنش‌ها")
    total_debit = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="مجموع بدهکار")
    total_credit = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="مجموع بستانکار")
    net_balance = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="مانده خالص")

    # Box 8: Debtors and Creditors (بدهکاران و بستانکاران)
    total_debtors = models.PositiveIntegerField(default=0, verbose_name="تعداد بدهکاران")
    total_creditors = models.PositiveIntegerField(default=0, verbose_name="تعداد بستانکاران")
    total_debtors_amount = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="مجموع مبلغ بدهکاران")
    total_creditors_amount = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="مجموع مبلغ بستانکاران")
    highest_debtor_amount = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="بیشترین مبلغ بدهکار")
    highest_creditor_amount = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="بیشترین مبلغ بستانکار")

    class Meta:
        verbose_name = "گزارش حسابداری"
        verbose_name_plural = "گزارشات حسابداری"
        ordering = ['-created_at']

    def __str__(self):
        return f"گزارش {self.get_report_type_display()} از {self.start_date} تا {self.end_date}"

    def calculate_report(self):
        """محاسبه مقادیر گزارش بر اساس بازه زمانی"""
        # فروش
        sales = SalesInvoice.objects.filter(
            invoice_date__gte=self.start_date,
            invoice_date__lte=self.end_date,
            status='confirmed'
        )
        self.total_sales = sales.aggregate(total=Sum('total_amount'))['total'] or 0
        self.total_sales_count = sales.count()

        # خرید
        purchases = PurchaseInvoice.objects.filter(
            invoice_date__gte=self.start_date,
            invoice_date__lte=self.end_date,
            status='confirmed'
        )
        self.total_purchases = purchases.aggregate(total=Sum('total_amount'))['total'] or 0
        self.total_purchases_count = purchases.count()

        # تسویه‌ها
        self.total_cash_settled = sales.aggregate(total=Sum('settle_cash'))['total'] or 0
        self.total_card_settled = sales.aggregate(total=Sum('settle_card'))['total'] or 0
        self.total_bank_settled = sales.aggregate(total=Sum('settle_bank'))['total'] or 0
        self.total_cheque_settled = sales.aggregate(total=Sum('settle_cheque'))['total'] or 0

        # مانده حساب‌ها
        self.total_customer_balance = sales.aggregate(total=Sum('settle_balance'))['total'] or 0
        self.total_supplier_balance = purchases.aggregate(total=Sum('settle_balance'))['total'] or 0

        # تخفیفات
        self.total_discounts = (
            SalesInvoiceItem.objects.filter(
                invoice__invoice_date__gte=self.start_date,
                invoice__invoice_date__lte=self.end_date,
                invoice__status='confirmed'
            ).aggregate(
                total=Sum(F('price') * F('quantity') * F('discount') / 100)
            )['total'] or 0
        )
        
        self.total_extra_discounts = sales.aggregate(total=Sum('settle_extra_discount'))['total'] or 0

        # محاسبه سود
        sales_items = SalesInvoiceItem.objects.filter(
            invoice__invoice_date__gte=self.start_date,
            invoice__invoice_date__lte=self.end_date,
            invoice__status='confirmed'
        )
        
        total_profit = Decimal('0')
        total_profit_percentage = Decimal('0')
        items_count = sales_items.count()
        
        for item in sales_items:
            item_profit = (item.price * item.quantity) * (item.profit_percentage / 100)
            total_profit += item_profit
            total_profit_percentage += item.profit_percentage
            
        self.total_profit = total_profit
        self.average_profit_percentage = total_profit_percentage / items_count if items_count > 0 else 0

        # محاسبه معین اشخاص
        all_customers = Customer.objects.all()
        self.total_transactions = sales.count() + purchases.count()
        self.total_debit = sales.aggregate(total=Sum('total_amount'))['total'] or 0
        self.total_credit = purchases.aggregate(total=Sum('total_amount'))['total'] or 0
        self.net_balance = self.total_debit - self.total_credit

        # محاسبه بدهکاران و بستانکاران
        customers_with_balance = all_customers.annotate(
            total_sales=Sum('salesinvoice__total_amount', filter=Q(
                salesinvoice__status='confirmed',
                salesinvoice__invoice_date__gte=self.start_date,
                salesinvoice__invoice_date__lte=self.end_date
            )),
            total_purchases=Sum('purchaseinvoice__total_amount', filter=Q(
                purchaseinvoice__status='confirmed',
                purchaseinvoice__invoice_date__gte=self.start_date,
                purchaseinvoice__invoice_date__lte=self.end_date
            )),
            balance=F('total_sales') - F('total_purchases')
        )

        debtors = customers_with_balance.filter(balance__gt=0)
        creditors = customers_with_balance.filter(balance__lt=0)

        self.total_debtors = debtors.count()
        self.total_creditors = creditors.count()
        self.total_debtors_amount = debtors.aggregate(total=Sum('balance'))['total'] or 0
        self.total_creditors_amount = abs(creditors.aggregate(total=Sum('balance'))['total'] or 0)
        
        max_debtor = debtors.order_by('-balance').first()
        max_creditor = creditors.order_by('balance').first()
        
        self.highest_debtor_amount = max_debtor.balance if max_debtor else 0
        self.highest_creditor_amount = abs(max_creditor.balance) if max_creditor else 0

        self.save()

    def save(self, *args, **kwargs):
        if not self.pk:  # اگر رکورد جدید است
            super().save(*args, **kwargs)
            self.calculate_report()
        else:
            super().save(*args, **kwargs)
class AccountingReportDetail(models.Model):
    TRANSACTION_TYPE_CHOICES = [
        ('debtor', 'بدهکار'),
        ('creditor', 'بستانکار'),
    ]

    report = models.ForeignKey(AccountingReport, on_delete=models.CASCADE, related_name='details', verbose_name="گزارش مربوطه")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, verbose_name="شخص")
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE_CHOICES, verbose_name="نوع تراکنش")
    
    # مبالغ و تعداد تراکنش‌ها
    total_sales = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="مجموع فروش")
    total_purchases = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="مجموع خرید")
    sales_count = models.PositiveIntegerField(default=0, verbose_name="تعداد فاکتورهای فروش")
    purchases_count = models.PositiveIntegerField(default=0, verbose_name="تعداد فاکتورهای خرید")
    
    # تسویه‌ها
    total_cash_settled = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="تسویه نقدی")
    total_card_settled = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="تسویه کارتی")
    total_bank_settled = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="تسویه بانکی")
    total_cheque_settled = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="تسویه چک")
    
    # مانده حساب
    balance = models.DecimalField(max_digits=20, decimal_places=0, default=0, verbose_name="مانده حساب")
    last_transaction_date = jmodels.jDateField(verbose_name="تاریخ آخرین تراکنش")

    class Meta:
        verbose_name = "جزئیات گزارش حسابداری"
        verbose_name_plural = "جزئیات گزارشات حسابداری"
        ordering = ['-balance', 'customer__last_name']

    def __str__(self):
        return f"{self.customer.get_full_name()} - {self.get_transaction_type_display()}"

    def calculate_details(self):
        """محاسبه جزئیات برای یک شخص خاص"""
        start_date = self.report.start_date
        end_date = self.report.end_date
        
        # محاسبه فروش‌ها
        sales = SalesInvoice.objects.filter(
            customer=self.customer,
            invoice_date__gte=start_date,
            invoice_date__lte=end_date,
            status='confirmed'
        )
        self.total_sales = sales.aggregate(total=Sum('total_amount'))['total'] or 0
        self.sales_count = sales.count()
        
        # محاسبه خریدها
        purchases = PurchaseInvoice.objects.filter(
            customer=self.customer,
            invoice_date__gte=start_date,
            invoice_date__lte=end_date,
            status='confirmed'
        )
        self.total_purchases = purchases.aggregate(total=Sum('total_amount'))['total'] or 0
        self.purchases_count = purchases.count()
        
        # محاسبه تسویه‌ها
        self.total_cash_settled = sales.aggregate(total=Sum('settle_cash'))['total'] or 0
        self.total_card_settled = sales.aggregate(total=Sum('settle_card'))['total'] or 0
        self.total_bank_settled = sales.aggregate(total=Sum('settle_bank'))['total'] or 0
        self.total_cheque_settled = sales.aggregate(total=Sum('settle_cheque'))['total'] or 0
        
        # محاسبه مانده
        self.balance = self.total_sales - self.total_purchases
        self.transaction_type = 'debtor' if self.balance > 0 else 'creditor'
        
        # آخرین تراکنش
        last_transaction = max(
            sales.order_by('-invoice_date').first(),
            purchases.order_by('-invoice_date').first(),
            key=lambda x: x.invoice_date if x else start_date
        )
        self.last_transaction_date = last_transaction.invoice_date if last_transaction else start_date
        
        self.save()

@receiver(post_save, sender=AccountingReport)
def create_report_details(sender, instance, created, **kwargs):
    """ایجاد جزئیات گزارش برای هر مشتری پس از ایجاد گزارش"""
    if created:
        customers = Customer.objects.all()
        for customer in customers:
            detail = AccountingReportDetail.objects.create(
                report=instance,
                customer=customer
            )
            detail.calculate_details()   

class FinancialYear(models.Model):
    year = models.CharField(max_length=4, unique=True, verbose_name="سال مالی")
    start_date = jmodels.jDateField(verbose_name="تاریخ شروع")
    end_date = jmodels.jDateField(verbose_name="تاریخ پایان")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    is_closed = models.BooleanField(default=False, verbose_name="بسته شده")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)

    class Meta:
        verbose_name = "سال مالی"
        verbose_name_plural = "سال‌های مالی"

    def __str__(self):
        return f"سال مالی {self.year}"

class Currency(models.Model):
    code = models.CharField(max_length=3, unique=True, verbose_name="کد ارز")
    name = models.CharField(max_length=50, verbose_name="نام ارز")
    symbol = models.CharField(max_length=5, verbose_name="نماد")
    is_default = models.BooleanField(default=False, verbose_name="ارز پیش‌فرض")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    exchange_rate = models.DecimalField(
        max_digits=18, 
        decimal_places=6,
        default=1.0,
        verbose_name="نرخ تبدیل به ارز پیش‌فرض"
    )

    class Meta:
        verbose_name = "ارز"
        verbose_name_plural = "ارزها"

    def __str__(self):
        return f"{self.name} ({self.code})"

class AccountGroup(models.Model):
    """
    گروه‌های حساب بر اساس استانداردهای حسابداری ایران
    """
    ACCOUNT_TYPES = [
        ('ASSET', 'دارایی'),
        ('LIABILITY', 'بدهی'),
        ('EQUITY', 'سرمایه'),
        ('REVENUE', 'درآمد'),
        ('EXPENSE', 'هزینه'),
    ]

    # گروه‌های اصلی حساب‌ها
    MAIN_GROUPS = [
        # دارایی‌ها
        ('1000', 'دارایی‌های جاری'),
        ('1100', 'موجودی نقد'),
        ('1200', 'سرمایه‌گذاری‌های کوتاه‌مدت'),
        ('1300', 'حساب‌ها و اسناد دریافتنی'),
        ('1400', 'موجودی کالا'),
        ('1500', 'پیش‌پرداخت‌ها'),
        ('1600', 'دارایی‌های ثابت'),
        ('1700', 'سرمایه‌گذاری‌های بلندمدت'),
        ('1800', 'دارایی‌های نامشهود'),
        
        # بدهی‌ها
        ('2000', 'بدهی‌های جاری'),
        ('2100', 'حساب‌ها و اسناد پرداختنی'),
        ('2200', 'پیش‌دریافت‌ها'),
        ('2300', 'ذخایر'),
        ('2400', 'بدهی‌های بلندمدت'),
        
        # سرمایه
        ('3000', 'سرمایه'),
        ('3100', 'سرمایه‌گذاری‌های صاحبان سهام'),
        ('3200', 'سود انباشته'),
        ('3300', 'سود سال جاری'),
        
        # درآمدها
        ('4000', 'درآمدهای عملیاتی'),
        ('4100', 'فروش کالا'),
        ('4200', 'فروش خدمات'),
        ('4300', 'درآمدهای غیرعملیاتی'),
        ('4400', 'سود سرمایه‌گذاری‌ها'),
        
        # هزینه‌ها
        ('5000', 'هزینه‌های عملیاتی'),
        ('5100', 'بهای تمام شده کالای فروش رفته'),
        ('5200', 'هزینه‌های فروش'),
        ('5300', 'هزینه‌های اداری'),
        ('5400', 'هزینه‌های مالی'),
        ('5500', 'هزینه‌های غیرعملیاتی'),
    ]

    code = models.CharField(max_length=10, unique=True, verbose_name="کد گروه", choices=MAIN_GROUPS)
    name = models.CharField(max_length=100, verbose_name="نام گروه")
    type = models.CharField(max_length=20, choices=ACCOUNT_TYPES, verbose_name="نوع حساب")
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, verbose_name="گروه والد")
    description = models.TextField(blank=True, null=True, verbose_name="توضیحات")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ ویرایش")
    
    class Meta:
        verbose_name = "گروه حساب"
        verbose_name_plural = "گروه‌های حساب"
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"

    def get_full_path(self):
        """دریافت مسیر کامل گروه حساب"""
        path = [self.name]
        parent = self.parent
        while parent:
            path.insert(0, parent.name)
            parent = parent.parent
        return ' > '.join(path)

    @classmethod
    def get_main_groups(cls):
        """دریافت گروه‌های اصلی (بدون والد)"""
        return cls.objects.filter(parent__isnull=True, is_active=True).order_by('code')

    @classmethod
    def get_sub_groups(cls, parent_code):
        """دریافت زیرگروه‌های یک گروه اصلی"""
        return cls.objects.filter(parent__code=parent_code, is_active=True).order_by('code')

class Account(models.Model):
    """
    حساب‌های تفصیلی بر اساس استانداردهای حسابداری ایران
    """
    ACCOUNT_LEVELS = [
        ('KOL', 'کل'),
        ('MOEIN', 'معین'),
        ('TAFSILI', 'تفصیلی'),
    ]

    # کدهای استاندارد حساب‌های کل
    STANDARD_CODES = {
        '1100': 'موجودی نقد',
        '1110': 'صندوق',
        '1120': 'بانک‌ها',
        '1130': 'تنخواه گردان',
        '1200': 'سرمایه‌گذاری‌های کوتاه‌مدت',
        '1300': 'حساب‌ها و اسناد دریافتنی',
        '1310': 'حساب‌های دریافتنی',
        '1320': 'اسناد دریافتنی',
        '1330': 'پیش‌پرداخت‌ها',
        '1400': 'موجودی کالا',
        '1410': 'موجودی مواد اولیه',
        '1420': 'موجودی کالای در جریان ساخت',
        '1430': 'موجودی کالای ساخته شده',
        '1500': 'پیش‌پرداخت‌ها',
        '1600': 'دارایی‌های ثابت',
        '1610': 'زمین',
        '1620': 'ساختمان',
        '1630': 'ماشین‌آلات و تجهیزات',
        '1640': 'وسایل نقلیه',
        '1650': 'اثاثیه و لوازم اداری',
        '1660': 'استهلاک انباشته',
        '1700': 'سرمایه‌گذاری‌های بلندمدت',
        '1800': 'دارایی‌های نامشهود',
        '1810': 'سرقفلی',
        '1820': 'حق اختراع',
        '1830': 'نرم‌افزار',
        
        '2100': 'حساب‌ها و اسناد پرداختنی',
        '2110': 'حساب‌های پرداختنی',
        '2120': 'اسناد پرداختنی',
        '2130': 'پیش‌دریافت‌ها',
        '2200': 'پیش‌دریافت‌ها',
        '2300': 'ذخایر',
        '2310': 'ذخیره مطالبات مشکوک‌الوصول',
        '2320': 'ذخیره مزایای پایان خدمت',
        '2400': 'بدهی‌های بلندمدت',
        '2410': 'وام‌های بلندمدت',
        '2420': 'اوراق قرضه',
        
        '3100': 'سرمایه‌گذاری‌های صاحبان سهام',
        '3110': 'سرمایه',
        '3120': 'سود انباشته',
        '3130': 'سود سال جاری',
        
        '4100': 'فروش کالا',
        '4110': 'فروش کالای اصلی',
        '4120': 'فروش کالای فرعی',
        '4200': 'فروش خدمات',
        '4300': 'درآمدهای غیرعملیاتی',
        '4310': 'درآمد سود بانکی',
        '4320': 'درآمد سود سرمایه‌گذاری',
        '4400': 'سود سرمایه‌گذاری‌ها',
        
        '5100': 'بهای تمام شده کالای فروش رفته',
        '5110': 'بهای تمام شده کالای اصلی',
        '5120': 'بهای تمام شده کالای فرعی',
        '5200': 'هزینه‌های فروش',
        '5210': 'حقوق و دستمزد فروشندگان',
        '5220': 'هزینه‌های تبلیغات',
        '5230': 'هزینه‌های حمل و نقل',
        '5300': 'هزینه‌های اداری',
        '5310': 'حقوق و دستمزد کارکنان',
        '5320': 'هزینه‌های اجاره',
        '5330': 'هزینه‌های آب و برق',
        '5340': 'هزینه‌های تلفن و اینترنت',
        '5400': 'هزینه‌های مالی',
        '5410': 'هزینه‌های بهره',
        '5420': 'هزینه‌های کارمزد بانکی',
        '5500': 'هزینه‌های غیرعملیاتی',
    }

    group = models.ForeignKey(AccountGroup, on_delete=models.PROTECT, verbose_name="گروه حساب")
    code = models.CharField(max_length=20, unique=True, verbose_name="کد حساب")
    name = models.CharField(max_length=200, verbose_name="نام حساب")
    level = models.CharField(max_length=10, choices=ACCOUNT_LEVELS, verbose_name="سطح حساب")
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, verbose_name="حساب والد")
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, verbose_name="ارز")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    description = models.TextField(blank=True, verbose_name="توضیحات")
    opening_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="موجودی اولیه")
    current_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="موجودی فعلی")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ ویرایش")

    class Meta:
        verbose_name = "حساب"
        verbose_name_plural = "حساب‌ها"
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.generate_account_code()
        super().save(*args, **kwargs)

    def generate_account_code(self):
        """تولید کد حساب خودکار"""
        if self.parent:
            # کد حساب معین یا تفصیلی
            parent_code = self.parent.code
            last_child = Account.objects.filter(
                parent=self.parent,
                code__startswith=parent_code
            ).order_by('-code').first()
            
            if last_child:
                last_number = int(last_child.code[-3:])
                new_number = last_number + 1
            else:
                new_number = 1
            
            return f"{parent_code}{new_number:03d}"
        else:
            # کد حساب کل
            return self.STANDARD_CODES.get(str(self.group.code), f"{self.group.code}000")

    def get_full_path(self):
        """دریافت مسیر کامل حساب"""
        path = [self.name]
        parent = self.parent
        while parent:
            path.insert(0, parent.name)
            parent = parent.parent
        return ' > '.join(path)

    def get_children(self):
        """دریافت حساب‌های فرزند"""
        return Account.objects.filter(parent=self, is_active=True).order_by('code')

    def get_balance(self):
        """دریافت موجودی حساب"""
        return self.current_balance

    @classmethod
    def get_main_accounts(cls):
        """دریافت حساب‌های کل (بدون والد)"""
        return cls.objects.filter(parent__isnull=True, is_active=True).order_by('code')

    @classmethod
    def get_sub_accounts(cls, parent_code):
        """دریافت حساب‌های معین یک حساب کل"""
        return cls.objects.filter(parent__code=parent_code, is_active=True).order_by('code')

    @classmethod
    def create_standard_accounts(cls, currency):
        """ایجاد حساب‌های استاندارد"""
        accounts_created = []
        
        for code, name in cls.STANDARD_CODES.items():
            # تعیین گروه حساب
            group_code = code[:4] + '000'
            group, created = AccountGroup.objects.get_or_create(
                code=group_code,
                defaults={
                    'name': f"گروه {code[:4]}",
                    'type': 'ASSET' if code.startswith('1') else 'LIABILITY' if code.startswith('2') else 'EQUITY' if code.startswith('3') else 'REVENUE' if code.startswith('4') else 'EXPENSE'
                }
            )
            
            # تعیین سطح حساب
            level = 'KOL' if code.endswith('000') else 'MOEIN' if code.endswith('00') else 'TAFSILI'
            
            # تعیین حساب والد
            parent = None
            if not code.endswith('000'):
                parent_code = code[:-3] + '000' if code.endswith('00') else code[:-3] + '00'
                parent = cls.objects.filter(code=parent_code).first()
            
            # ایجاد حساب
            account, created = cls.objects.get_or_create(
                code=code,
                defaults={
                    'group': group,
                    'name': name,
                    'level': level,
                    'parent': parent,
                    'currency': currency,
                    'description': f"حساب {name}"
                }
            )
            
            if created:
                accounts_created.append(account)
        
        return accounts_created

class Bank(models.Model):
    """
    مدل بانک‌های ایرانی با کدهای استاندارد
    """
    IRANIAN_BANKS = [
        ('001', 'بانک مرکزی جمهوری اسلامی ایران'),
        ('010', 'بانک ملی ایران'),
        ('011', 'بانک سپه'),
        ('012', 'بانک صادرات ایران'),
        ('013', 'بانک کشاورزی'),
        ('014', 'بانک مسکن'),
        ('015', 'بانک صنعت و معدن'),
        ('016', 'بانک توسعه صادرات ایران'),
        ('017', 'بانک توسعه تعاون'),
        ('018', 'بانک تجارت'),
        ('019', 'بانک ملت'),
        ('020', 'بانک رفاه کارگران'),
        ('021', 'بانک پست بانک ایران'),
        ('022', 'بانک پارسیان'),
        ('023', 'بانک اقتصاد نوین'),
        ('024', 'بانک سینا'),
        ('025', 'بانک سرمایه'),
        ('026', 'بانک سامان'),
        ('027', 'بانک پاسارگاد'),
        ('028', 'بانک کارآفرین'),
        ('029', 'بانک شهر'),
        ('030', 'بانک دی'),
        ('031', 'بانک انصار'),
        
        ('033', 'بانک آینده'),
        ('034', 'بانک گردشگری'),
        ('035', 'بانک ایران زمین'),
        ('036', 'بانک قوامین'),
        ('037', 'بانک خاورمیانه'),
        ('038', 'بانک کوثر'),
        ('039', 'بانک مهر اقتصاد'),
        ('040', 'بانک حکمت ایرانیان'),
        ('041', 'بانک کارگزاران'),
        ('042', 'بانک رسالت'),
        ('043', 'بانک قرض‌الحسنه مهر ایران'),
        ('044', 'بانک قرض‌الحسنه رسالت'),
        ('045', 'بانک قرض‌الحسنه قوامین'),
        
        ('047', 'بانک قرض‌الحسنه امام رضا'),
        ('048', 'بانک قرض‌الحسنه نور'),
        ('049', 'بانک قرض‌الحسنه ولیعصر'),
        ('050', 'بانک قرض‌الحسنه عسکریه'),
        ('051', 'بانک قرض‌الحسنه انصار'),
        ('052', 'بانک قرض‌الحسنه رسالت'),
        
        ('054', 'بانک قرض‌الحسنه قوامین'),
        ('055', 'بانک قرض‌الحسنه امام رضا'),
        ('056', 'بانک قرض‌الحسنه نور'),
        ('057', 'بانک قرض‌الحسنه ولیعصر'),
        ('058', 'بانک قرض‌الحسنه عسکریه'),
        ('059', 'بانک قرض‌الحسنه انصار'),
        ('060', 'بانک قرض‌الحسنه رسالت'),
        
        ('062', 'بانک قرض‌الحسنه قوامین'),
        ('063', 'بانک قرض‌الحسنه امام رضا'),
        ('064', 'بانک قرض‌الحسنه نور'),
        ('065', 'بانک قرض‌الحسنه ولیعصر'),
        ('066', 'بانک قرض‌الحسنه عسکریه'),
        ('067', 'بانک قرض‌الحسنه انصار'),
        ('068', 'بانک قرض‌الحسنه رسالت'),
        
        ('070', 'بانک قرض‌الحسنه قوامین'),
        ('071', 'بانک قرض‌الحسنه امام رضا'),
        ('072', 'بانک قرض‌الحسنه نور'),
        ('073', 'بانک قرض‌الحسنه ولیعصر'),
        ('074', 'بانک قرض‌الحسنه عسکریه'),
        ('075', 'بانک قرض‌الحسنه انصار'),
        ('076', 'بانک قرض‌الحسنه رسالت'),
        
        ('078', 'بانک قرض‌الحسنه قوامین'),
        ('079', 'بانک قرض‌الحسنه امام رضا'),
        ('080', 'بانک قرض‌الحسنه نور'),
        ('081', 'بانک قرض‌الحسنه ولیعصر'),
        ('082', 'بانک قرض‌الحسنه عسکریه'),
        ('083', 'بانک قرض‌الحسنه انصار'),
        ('084', 'بانک قرض‌الحسنه رسالت'),
        
        ('086', 'بانک قرض‌الحسنه قوامین'),
        ('087', 'بانک قرض‌الحسنه امام رضا'),
        ('088', 'بانک قرض‌الحسنه نور'),
        ('089', 'بانک قرض‌الحسنه ولیعصر'),
        ('090', 'بانک قرض‌الحسنه عسکریه'),
        ('091', 'بانک قرض‌الحسنه انصار'),
        ('092', 'بانک قرض‌الحسنه رسالت'),
        
        ('094', 'بانک قرض‌الحسنه قوامین'),
        ('095', 'بانک قرض‌الحسنه امام رضا'),
        ('096', 'بانک قرض‌الحسنه نور'),
        ('097', 'بانک قرض‌الحسنه ولیعصر'),
        ('098', 'بانک قرض‌الحسنه عسکریه'),
        ('099', 'بانک قرض‌الحسنه انصار'),
    ]

    name = models.CharField(max_length=100, verbose_name="نام بانک")
    code = models.CharField(max_length=20, unique=True, verbose_name="کد بانک", choices=IRANIAN_BANKS)
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    website = models.URLField(blank=True, null=True, verbose_name="وب‌سایت")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="تلفن")
    address = models.TextField(blank=True, null=True, verbose_name="آدرس")

    class Meta:
        verbose_name = "بانک"
        verbose_name_plural = "بانک‌ها"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"

    @classmethod
    def get_iranian_banks(cls):
        """دریافت لیست بانک‌های ایرانی فعال"""
        return cls.objects.filter(is_active=True).order_by('name')

class CardReaderDevice(models.Model):
    """
    مدل دستگاه کارت‌خوان - برای تعریف دستگاه‌های کارت‌خوان در سیستم
    """
    DEVICE_TYPES = [
        ('POS', 'دستگاه POS'),
        ('PINPAD', 'دستگاه PINPAD'),
        ('MOBILE', 'دستگاه موبایل'),
        ('TABLET', 'دستگاه تبلت'),
        ('OTHER', 'سایر'),
    ]
    
    name = models.CharField(max_length=100, verbose_name="نام دستگاه")
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPES, verbose_name="نوع دستگاه")
    terminal_number = models.CharField(max_length=50, unique=True, verbose_name="شماره پایانه")
    serial_number = models.CharField(max_length=100, blank=True, null=True, verbose_name="شماره سریال")
    manufacturer = models.CharField(max_length=100, blank=True, null=True, verbose_name="سازنده")
    model = models.CharField(max_length=100, blank=True, null=True, verbose_name="مدل")
    
    # اطلاعات پشتیبانی
    support_company = models.CharField(max_length=100, blank=True, null=True, verbose_name="شرکت پشتیبان")
    support_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="شماره تماس پشتیبان")
    support_email = models.EmailField(blank=True, null=True, verbose_name="ایمیل پشتیبان")
    
    # ارتباط با حساب بانکی (اختیاری)
    bank_account = models.ForeignKey('BankAccount', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="حساب بانکی مرتبط")
    
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    description = models.TextField(blank=True, verbose_name="توضیحات")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="ایجاد کننده")

    class Meta:
        verbose_name = "دستگاه کارت‌خوان"
        verbose_name_plural = "دستگاه‌های کارت‌خوان"
        ordering = ['name', 'terminal_number']

    def __str__(self):
        bank_info = f" - {self.bank_account.title}" if self.bank_account else ""
        return f"{self.name} - {self.get_device_type_display()} ({self.terminal_number}){bank_info}"

class BankAccount(models.Model):
    ACCOUNT_TYPES = [
        ('CHECKING', 'جاری'),
        ('SAVINGS', 'پس‌انداز'),
        ('CURRENT', 'قرض‌الحسنه جاری'),
        ('SAVING_QARZ', 'قرض‌الحسنه پس‌انداز'),
    ]

    account = models.OneToOneField(Account, on_delete=models.PROTECT, verbose_name="حساب مرتبط")
    bank = models.ForeignKey(Bank, on_delete=models.PROTECT, verbose_name="بانک")
    account_number = models.CharField(max_length=50, verbose_name="شماره حساب")
    sheba = models.CharField(max_length=26, unique=True, verbose_name="شماره شبا")
    card_number = models.CharField(max_length=25, blank=True, null=True, verbose_name="شماره کارت", help_text="شماره کارت باید دقیقاً 16 رقم باشد")
    has_card_reader = models.BooleanField(default=False, verbose_name="دارای کارت‌خوان")
    card_reader_device_1 = models.ForeignKey(CardReaderDevice, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="دستگاه کارت‌خوان 1", related_name='bank_accounts_1')
    card_reader_device_2 = models.ForeignKey(CardReaderDevice, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="دستگاه کارت‌خوان 2", related_name='bank_accounts_2')
    card_reader_device_3 = models.ForeignKey(CardReaderDevice, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="دستگاه کارت‌خوان 3", related_name='bank_accounts_3')
    card_reader_device_4 = models.ForeignKey(CardReaderDevice, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="دستگاه کارت‌خوان 4", related_name='bank_accounts_4')

    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES, verbose_name="نوع حساب")
    title = models.CharField(max_length=200, verbose_name="عنوان حساب")
    initial_balance = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        verbose_name="موجودی اولیه"
    )
    current_balance = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        verbose_name="موجودی فعلی"
    )
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    description = models.TextField(blank=True, verbose_name="توضیحات")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="ایجاد کننده")

    class Meta:
        verbose_name = "حساب بانکی"
        verbose_name_plural = "حساب‌های بانکی"
        unique_together = ['bank', 'account_number']

    def __str__(self):
        return f"{self.bank.name} - {self.title} ({self.account_number})"

class CashRegister(models.Model):
    account = models.OneToOneField(Account, on_delete=models.PROTECT, verbose_name="حساب مرتبط")
    title = models.CharField(max_length=200, verbose_name="عنوان صندوق")
    initial_balance = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        verbose_name="موجودی اولیه"
    )
    current_balance = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        verbose_name="موجودی فعلی"
    )
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    description = models.TextField(blank=True, verbose_name="توضیحات")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="ایجاد کننده")

    class Meta:
        verbose_name = "صندوق نقدی قدیمی"
        verbose_name_plural = "صندوق‌های نقدی قدیمی"

class CheckBook(models.Model):
    bank_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT, related_name='checkbooks', verbose_name="حساب بانکی")
    serial = models.CharField(max_length=50, unique=True, verbose_name="سریال دسته چک")
    start_number = models.IntegerField(verbose_name="شماره شروع")
    end_number = models.IntegerField(verbose_name="شماره پایان")
    current_number = models.IntegerField(verbose_name="شماره فعلی")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="ایجاد کننده")

    class Meta:
        verbose_name = "دسته چک"
        verbose_name_plural = "دسته چک‌ها"

    def __str__(self):
        return f"{self.serial} - {self.bank_account.title}"

    @property
    def total_checks(self):
        """تعداد کل برگ‌های چک"""
        return self.end_number - self.start_number + 1

    @property
    def used_checks(self):
        """تعداد برگ‌های استفاده شده"""
        return Check.objects.filter(
            checkbook=self,
            status__in=['ISSUED', 'RECEIVED', 'DEPOSITED', 'CLEARED', 'BOUNCED']
        ).count()

    @property
    def remaining_checks(self):
        """تعداد برگ‌های باقی‌مانده"""
        return self.total_checks - self.used_checks

    @property
    def issued_checks(self):
        """تعداد برگ‌های صادر شده"""
        return Check.objects.filter(
            checkbook=self,
            status='ISSUED'
        ).count()

    @property
    def received_checks(self):
        """تعداد برگ‌های دریافتی"""
        return Check.objects.filter(
            checkbook=self,
            status='RECEIVED'
        ).count()

    @property
    def cleared_checks(self):
        """تعداد برگ‌های وصول شده"""
        return Check.objects.filter(
            checkbook=self,
            status='CLEARED'
        ).count()

    @property
    def bounced_checks(self):
        """تعداد برگ‌های برگشت خورده"""
        return Check.objects.filter(
            checkbook=self,
            status='BOUNCED'
        ).count()

class Check(models.Model):
    STATUS_CHOICES = [
        ('UNUSED', 'استفاده نشده'),
        ('ISSUED', 'صادر شده'),
        ('RECEIVED', 'دریافت شده'),
        ('DEPOSITED', 'واگذار شده'),
        ('CLEARED', 'وصول شده'),
        ('BOUNCED', 'برگشت خورده'),
        ('VOID', 'باطل شده'),
    ]

    checkbook = models.ForeignKey(CheckBook, null=True, blank=True, on_delete=models.PROTECT, verbose_name="دسته چک")
    number = models.CharField(max_length=50, verbose_name="شماره چک")
    amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="مبلغ")
    date = jmodels.jDateField(verbose_name="تاریخ سررسید")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='UNUSED', verbose_name="وضعیت")
    payee = models.CharField(max_length=200, verbose_name="در وجه")
    description = models.TextField(blank=True, verbose_name="توضیحات")
    bank_name = models.CharField(max_length=100, blank=True, verbose_name="نام بانک")  # برای چک‌های دریافتی
    bank_branch = models.CharField(max_length=100, blank=True, verbose_name="شعبه بانک")  # برای چک‌های دریافتی
    account_number = models.CharField(max_length=50, blank=True, verbose_name="شماره حساب")  # برای چک‌های دریافتی
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="ایجاد کننده")

    class Meta:
        verbose_name = "چک"
        verbose_name_plural = "چک‌ها"
        unique_together = ['checkbook', 'number']
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.number} - {self.payee} - {self.amount}"

    @property
    def is_issued(self):
        """آیا چک صادر شده است؟"""
        return self.status == 'ISSUED'

    @property
    def is_received(self):
        """آیا چک دریافتی است؟"""
        return self.status == 'RECEIVED'

    @property
    def is_cleared(self):
        """آیا چک وصول شده است؟"""
        return self.status == 'CLEARED'

    @property
    def is_bounced(self):
        """آیا چک برگشت خورده است؟"""
        return self.status == 'BOUNCED'

    @property
    def is_void(self):
        """آیا چک باطل شده است؟"""
        return self.status == 'VOID'

    @property
    def is_unused(self):
        """آیا چک استفاده نشده است؟"""
        return self.status == 'UNUSED'

    @property
    def is_deposited(self):
        """آیا چک واگذار شده است؟"""
        return self.status == 'DEPOSITED'

    @property
    def status_display(self):
        """نمایش وضعیت به فارسی"""
        return dict(self.STATUS_CHOICES).get(self.status, self.status)

    @property
    def bank_account_info(self):
        """اطلاعات حساب بانکی مرتبط"""
        if self.checkbook:
            return self.checkbook.bank_account
        return None

class Voucher(models.Model):
    VOUCHER_TYPES = [
        ('TEMPORARY', 'موقت'),
        ('PERMANENT', 'دائم'),
    ]
    
    financial_year = models.ForeignKey(FinancialYear, on_delete=models.PROTECT, verbose_name="سال مالی")
    number = models.CharField(max_length=20, verbose_name="شماره سند")
    date = jmodels.jDateField(verbose_name="تاریخ سند")
    type = models.CharField(max_length=20, choices=VOUCHER_TYPES, default='TEMPORARY', verbose_name="نوع سند")
    description = models.TextField(verbose_name="شرح سند")
    is_confirmed = models.BooleanField(default=False, verbose_name="تأیید شده")
    confirmed_by = models.ForeignKey(
        User, 
        null=True, 
        blank=True, 
        on_delete=models.PROTECT, 
        related_name='confirmed_vouchers',
        verbose_name="تأیید کننده"
    )
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ تأیید")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    created_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='created_vouchers',
        verbose_name="ایجاد کننده"
    )

    class Meta:
        verbose_name = "سند حسابداری"
        verbose_name_plural = "اسناد حسابداری"
        unique_together = ['financial_year', 'number']

class VoucherItem(models.Model):
    voucher = models.ForeignKey(Voucher, on_delete=models.CASCADE, related_name='items', verbose_name="سند")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, verbose_name="حساب")
    description = models.CharField(max_length=500, verbose_name="شرح")
    debit = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="بدهکار")
    credit = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="بستانکار")
    reference_id = models.CharField(max_length=100, blank=True, verbose_name="شناسه مرجع")
    reference_type = models.CharField(max_length=50, blank=True, verbose_name="نوع مرجع")

    class Meta:
        verbose_name = "آرتیکل سند"
        verbose_name_plural = "آرتیکل‌های سند"

    def __str__(self):
        return f"{self.account.name} - {self.description}"

class Receipt(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, verbose_name="مشتری")
    date = jmodels.jDateField(verbose_name="تاریخ")
    amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="مبلغ")
    payment_method = models.CharField(max_length=20, choices=[
        ('cash', 'نقدی'),
        ('bank_transfer', 'حواله بانکی'),
        ('cheque', 'چک'),
        ('pos', 'دستگاه POS'),
    ], verbose_name="روش پرداخت")
    description = models.TextField(blank=True, verbose_name="توضیحات")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="ایجاد کننده")

    class Meta:
        verbose_name = "رسید دریافت"
        verbose_name_plural = "رسیدهای دریافت"
        ordering = ['-date']

    def __str__(self):
        return f"رسید {self.id} از {self.customer} به مبلغ {self.amount}"

class FinancialOperation(models.Model):
    """
    مدل اصلی برای عملیات مالی - شامل تمام تراکنش‌های مالی
    """
    OPERATION_TYPES = [
        ('RECEIVE_FROM_CUSTOMER', 'دریافت از مشتری'),
        ('PAY_TO_CUSTOMER', 'پرداخت به مشتری'),
        ('RECEIVE_FROM_BANK', 'دریافت از بانک'),
        ('PAY_TO_BANK', 'پرداخت به بانک'),
        ('BANK_TRANSFER', 'حواله بانکی'),
        ('CASH_WITHDRAWAL', 'برداشت نقدی از بانک'),
        ('PAYMENT_TO_CASH', 'پرداخت به صندوق'),
        ('PAYMENT_FROM_CASH', 'پرداخت از صندوق'),
        ('CAPITAL_INVESTMENT', 'سرمایه گذاری'),
        ('PETTY_CASH', 'تنخواه'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', 'پیش‌نویس'),
        ('CONFIRMED', 'تأیید شده'),
        ('CANCELLED', 'باطل شده'),
    ]
    
    # اطلاعات اصلی
    operation_type = models.CharField(max_length=50, choices=OPERATION_TYPES, verbose_name="نوع عملیات")
    operation_number = models.CharField(max_length=50, unique=True, verbose_name="شماره عملیات")
    date = jmodels.jDateField(verbose_name="تاریخ عملیات")
    amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="مبلغ")
    description = models.TextField(blank=True, verbose_name="توضیحات")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name="وضعیت")
    
    # اطلاعات طرف حساب
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, null=True, blank=True, verbose_name="مشتری")
    fund = models.ForeignKey('Fund', on_delete=models.PROTECT, null=True, blank=True, verbose_name="صندوق مرتبط")
    bank_name = models.CharField(max_length=100, blank=True, verbose_name="نام بانک")
    account_number = models.CharField(max_length=50, blank=True, verbose_name="شماره حساب")
    
    # اطلاعات روش پرداخت
    payment_method = models.CharField(max_length=20, choices=[
        ('cash', 'نقدی'),
        ('bank_transfer', 'حواله بانکی'),
        ('cheque', 'چک'),
        ('pos', 'دستگاه POS'),
    ], verbose_name="روش پرداخت")
    card_reader_device = models.ForeignKey('CardReaderDevice', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="دستگاه کارت‌خوان")
    
    # اطلاعات اضافی
    reference_number = models.CharField(max_length=100, blank=True, verbose_name="شماره مرجع")
    cheque_number = models.CharField(max_length=50, blank=True, verbose_name="شماره چک")
    cheque_date = jmodels.jDateField(null=True, blank=True, verbose_name="تاریخ چک")
    
    # اطلاعات سیستمی
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="ایجاد کننده")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ ویرایش")
    confirmed_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        null=True, 
        blank=True, 
        related_name='confirmed_operations',
        verbose_name="تأیید کننده"
    )
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ تأیید")
    
    # فیلدهای حذف نرم و تاریخچه اصلاح
    is_deleted = models.BooleanField(default=False, verbose_name="حذف شده")
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ حذف")
    deleted_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='deleted_operations',
        verbose_name="حذف کننده"
    )
    is_modified = models.BooleanField(default=False, verbose_name="اصلاح شده")
    modified_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ اصلاح")
    modified_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='modified_operations',
        verbose_name="اصلاح کننده"
    )
    
    class Meta:
        verbose_name = "عملیات مالی"
        verbose_name_plural = "عملیات مالی"
        ordering = ['-date', '-created_at']
    
    def __str__(self):
        return f"{self.get_operation_type_display()} - {self.operation_number} - {self.amount:,}"
    
    def soft_delete(self, user):
        """حذف نرم عملیات مالی"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save()
    
    def restore(self):
        """بازگردانی عملیات حذف شده"""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save()
    
    def mark_as_modified(self, user):
        """علامت‌گذاری به عنوان اصلاح شده"""
        self.is_modified = True
        self.modified_at = timezone.now()
        self.modified_by = user
        self.save()
    
    @property
    def status_display(self):
        """نمایش وضعیت با در نظر گرفتن حذف نرم"""
        if self.is_deleted:
            return "حذف شده"
        return self.get_status_display()
    
    @property
    def row_class(self):
        """کلاس CSS برای ردیف بر اساس وضعیت"""
        if self.is_deleted:
            return "table-danger"  # قرمز برای حذف شده
        elif self.is_modified:
            return "table-success"  # سبز برای اصلاح شده
        else:
            return ""  # مشکی برای عادی
    
    def save(self, *args, **kwargs):
        if not self.operation_number:
            self.operation_number = self.generate_operation_number()
        super().save(*args, **kwargs)
    
    def generate_operation_number(self):
        """تولید شماره عملیات خودکار"""
        from datetime import datetime
        prefix = datetime.now().strftime('%Y%m%d')
        last_operation = FinancialOperation.objects.filter(
            operation_number__startswith=prefix
        ).order_by('-operation_number').first()
        
        if last_operation:
            last_number = int(last_operation.operation_number[-4:])
            new_number = last_number + 1
        else:
            new_number = 1
        
        return f"{prefix}{new_number:04d}"
    
    def confirm_operation(self, user):
        """تأیید عملیات مالی"""
        if self.status == 'DRAFT':
            self.status = 'CONFIRMED'
            self.confirmed_by = user
            self.confirmed_at = timezone.now()
            self.save()
            
            # ایجاد تراکنش‌های حسابداری
            self.create_accounting_entries()
    
    def create_accounting_entries(self):
        """ایجاد تراکنش‌های حسابداری مرتبط"""
        from .models import Voucher, FinancialYear
        
        # دریافت سال مالی فعال
        financial_year = FinancialYear.objects.filter(is_active=True).first()
        if not financial_year:
            return None
        
        # ایجاد شماره سند
        last_voucher = Voucher.objects.filter(financial_year=financial_year).order_by('-number').first()
        if last_voucher:
            try:
                next_number = str(int(last_voucher.number) + 1).zfill(6)
            except ValueError:
                next_number = '000001'
        else:
            next_number = '000001'
        
        # ایجاد سند
        voucher = Voucher.objects.create(
            financial_year=financial_year,
            number=next_number,
            date=self.date,
            type='PERMANENT',
            description=f"{self.get_operation_type_display()} - {self.description or 'بدون توضیح'}",
            is_confirmed=True,
            confirmed_by=self.created_by,
            confirmed_at=timezone.now(),
            created_by=self.created_by
        )
        
        # ایجاد آرتیکل‌های سند

        
        return voucher


class Fund(models.Model):
    """
    مدل صندوق - مدیریت موجودی‌های نقدی و بانکی
    """
    FUND_TYPES = [
        ('CASH', 'صندوق نقدی'),
        ('BANK', 'حساب بانکی'),
        ('PETTY_CASH', 'تنخواه'),
    ]
    
    name = models.CharField(max_length=100, verbose_name="نام صندوق")
    fund_type = models.CharField(max_length=20, choices=FUND_TYPES, verbose_name="نوع صندوق")
    initial_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="موجودی اولیه")
    current_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="موجودی فعلی")
    
    # اطلاعات بانکی (برای حساب‌های بانکی)
    bank_name = models.CharField(max_length=100, blank=True, verbose_name="نام بانک")
    account_number = models.CharField(max_length=50, blank=True, verbose_name="شماره حساب")
    sheba_number = models.CharField(max_length=26, blank=True, verbose_name="شماره شبا")
    
    # وضعیت
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    description = models.TextField(blank=True, verbose_name="توضیحات")
    
    # اطلاعات سیستمی
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="ایجاد کننده")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ ویرایش")
    
    class Meta:
        verbose_name = "صندوق"
        verbose_name_plural = "صندوق‌ها"
        ordering = ['fund_type', 'name']
    
    def __str__(self):
        return f"{self.get_fund_type_display()} - {self.name}"
    
    def update_balance(self, amount, operation_type):
        """به‌روزرسانی موجودی صندوق"""
        if operation_type in ['RECEIVE_FROM_CUSTOMER', 'RECEIVE_FROM_BANK', 'PAYMENT_TO_CASH']:
            self.current_balance += amount
        elif operation_type in ['PAY_TO_CUSTOMER', 'PAY_TO_BANK', 'PAYMENT_FROM_CASH', 'CASH_WITHDRAWAL']:
            self.current_balance -= amount
        
        self.save()
    
    def get_balance_history(self):
        """دریافت تاریخچه موجودی"""
        return FundBalanceHistory.objects.filter(fund=self).order_by('-date')
    
    def get_current_balance_from_statement(self):
        """محاسبه مانده فعلی از صورتحساب"""
        last_statement = self.statements.order_by('-date', '-created_at').first()
        if last_statement:
            return last_statement.running_balance
        return 0
    
    def get_statement_entries(self, limit=50):
        """دریافت ورودی‌های صورتحساب"""
        return self.statements.order_by('-date', '-created_at')[:limit]
    
    def calculate_balance_from_operations(self):
        """محاسبه مانده از عملیات‌های مالی"""
        from .models import FinancialOperation
        from django.db.models import Q
        
        # عملیات‌های مرتبط با این صندوق
        if self.fund_type == 'CASH':
            # برای صندوق نقدی، عملیات‌های مربوط به صندوق نقدی را در نظر بگیر
            operations = FinancialOperation.objects.filter(
                Q(operation_type__in=['RECEIVE_FROM_CUSTOMER', 'PAY_TO_CUSTOMER', 'PAYMENT_TO_CASH', 'PAYMENT_FROM_CASH', 'CAPITAL_INVESTMENT']) |
                Q(operation_type='PETTY_CASH', source_fund=self),
                status='CONFIRMED'
            )
        else:
            # برای حساب‌های بانکی، بر اساس نام بانک و شماره حساب
            operations = FinancialOperation.objects.filter(
                Q(bank_name=self.bank_name) | Q(account_number=self.account_number),
                status='CONFIRMED'
            )
        
        total_in = sum(op.amount for op in operations if 'RECEIVE' in op.operation_type or op.operation_type in ['PAYMENT_TO_CASH', 'CAPITAL_INVESTMENT'])
        total_out = sum(op.amount for op in operations if 'PAY' in op.operation_type or op.operation_type == 'PAYMENT_FROM_CASH')
        
        return self.initial_balance + total_in - total_out
    
    def calculate_balance_from_transactions(self):
        """محاسبه مانده از گردش صندوق"""
        try:
            transactions = self.transactions.all()
            
            total_in = sum(t.amount for t in transactions if t.transaction_type == 'IN')
            total_out = sum(t.amount for t in transactions if t.transaction_type == 'OUT')
            
            return self.initial_balance + total_in - total_out
        except Exception as e:
            print(f"خطا در محاسبه مانده از گردش صندوق: {e}")
            return self.current_balance
    
    def update_balance_from_transactions(self):
        """به‌روزرسانی مانده فعلی از گردش صندوق"""
        try:
            self.current_balance = self.calculate_balance_from_transactions()
            self.save()
            return self.current_balance
        except Exception as e:
            print(f"خطا در به‌روزرسانی مانده صندوق: {e}")
            return self.current_balance
    
    def add_transaction(self, transaction_type, amount, description, reference_id=None, reference_type=None):
        """افزودن تراکنش جدید به گردش صندوق"""
        
        try:
            transaction = FundTransaction.objects.create(
                fund=self,
                transaction_type=transaction_type,
                amount=amount,
                description=description,
                reference_id=reference_id,
                reference_type=reference_type,
                created_by=self.created_by
            )
            
            # به‌روزرسانی مانده فعلی
            self.update_balance_from_transactions()
            
            return transaction
        except Exception as e:
            print(f"خطا در ایجاد گردش صندوق: {e}")
            # Return None if transaction creation fails
            return None
    
    def get_transactions(self, limit=None):
        """دریافت گردش صندوق"""
        transactions = self.transactions.all().order_by('-date', '-created_at')
        if limit:
            transactions = transactions[:limit]
        return transactions
    
    @classmethod
    def get_petty_cash_balance(cls):
        """محاسبه مانده تنخواه از عملیات تنخواه"""
        from .models import PettyCashOperation
        
        # محاسبه مانده از عملیات تنخواه
        petty_ops = PettyCashOperation.objects.all()
        
        total_in = sum(op.amount for op in petty_ops if op.operation_type == 'ADD')
        total_out = sum(op.amount for op in petty_ops if op.operation_type == 'WITHDRAW')
        
        return total_in - total_out

    def recalculate_balance(self):
        """محاسبه مجدد موجودی فعلی صندوق بر اساس تمام عملیات‌های مرتبط."""
        from django.db.models import Sum, Q
        from .models import FinancialOperation, PettyCashOperation

        total_in = Decimal('0')
        total_out = Decimal('0')

        IN_OPERATIONS = ['RECEIVE_FROM_CUSTOMER', 'RECEIVE_FROM_BANK', 'PAYMENT_TO_CASH', 'CAPITAL_INVESTMENT', 'ADD']
        OUT_OPERATIONS = ['PAY_TO_CUSTOMER', 'PAY_TO_BANK', 'PAYMENT_FROM_CASH', 'CASH_WITHDRAWAL', 'WITHDRAW', 'EXPENSE', 'PETTY_CASH_WITHDRAW']

        if self.fund_type == 'PETTY_CASH':
            # For a petty cash fund, its balance changes by all petty cash operations.
            operations = PettyCashOperation.objects.all()
            total_in = operations.filter(operation_type='ADD').aggregate(total=Sum('amount'))['total'] or Decimal('0')
            total_out = operations.filter(operation_type='WITHDRAW').aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        else:
            # For CASH and BANK funds
            financial_filter = Q()
            if self.fund_type == 'CASH':
                # Cash operations are those explicitly linked to this fund, or those with no bank details.
                financial_filter = Q(fund=self) | Q(bank_name__isnull=True, account_number__isnull=True)
            elif self.fund_type == 'BANK':
                # Bank operations are those explicitly linked, or matching bank details.
                financial_filter = Q(fund=self) | Q(bank_name=self.bank_name, account_number=self.account_number)

            if financial_filter:
                financial_ops = FinancialOperation.objects.filter(financial_filter, status='CONFIRMED')
                
                # Money coming into this fund from financial operations
                in_ops = financial_ops.filter(operation_type__in=IN_OPERATIONS).aggregate(total=Sum('amount'))['total']
                total_in += in_ops or Decimal('0')
                
                # Money going out of this fund from financial operations
                out_ops = financial_ops.filter(operation_type__in=OUT_OPERATIONS).aggregate(total=Sum('amount'))['total']
                total_out += out_ops or Decimal('0')

            # Also account for when this fund is the source for petty cash (always an outflow)
            petty_cash_source_ops = PettyCashOperation.objects.filter(source_fund=self)
            total_out += petty_cash_source_ops.aggregate(total=Sum('amount'))['total'] or Decimal('0')

        # Calculate and save the new balance
        self.current_balance = self.initial_balance + total_in - total_out
        self.save(update_fields=['current_balance'])
        
        return self.current_balance


class FundTransaction(models.Model):
    """
    گردش صندوق‌ها - برای ثبت دقیق‌تر تراکنش‌های صندوق
    """
    TRANSACTION_TYPES = [
        ('IN', 'ورودی'),
        ('OUT', 'خروجی'),
    ]
    
    fund = models.ForeignKey('Fund', on_delete=models.CASCADE, related_name='transactions', verbose_name="صندوق")
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES, verbose_name="نوع تراکنش")
    amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="مبلغ")
    description = models.CharField(max_length=255, verbose_name="شرح")
    date = jmodels.jDateField(auto_now_add=True, verbose_name="تاریخ")
    reference_id = models.CharField(max_length=100, blank=True, verbose_name="شناسه مرجع")
    reference_type = models.CharField(max_length=50, blank=True, verbose_name="نوع مرجع")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="ایجاد کننده")
    
    class Meta:
        verbose_name = "گردش صندوق"
        verbose_name_plural = "گردش صندوق‌ها"
        ordering = ['-date', '-created_at']
    
    def __str__(self):
        return f"{self.fund.name} - {self.get_transaction_type_display()} - {self.amount:,}"


class FundBalanceHistory(models.Model):
    """
    تاریخچه موجودی صندوق‌ها
    """
    fund = models.ForeignKey('Fund', on_delete=models.CASCADE, related_name='balance_history', verbose_name="صندوق")
    date = jmodels.jDateField(verbose_name="تاریخ")
    previous_balance = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="موجودی قبلی")
    change_amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="مبلغ تغییر")
    new_balance = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="موجودی جدید")
    operation = models.ForeignKey(FinancialOperation, on_delete=models.CASCADE, verbose_name="عملیات مرتبط")
    description = models.CharField(max_length=255, verbose_name="شرح")
    
    class Meta:
        verbose_name = "تاریخچه موجودی صندوق"
        verbose_name_plural = "تاریخچه موجودی صندوق‌ها"
        ordering = ['-date', '-id']


class FundStatement(models.Model):
    """
    صورتحساب صندوق‌ها - برای محاسبه دقیق مانده‌ها
    """
    fund = models.ForeignKey('Fund', on_delete=models.CASCADE, related_name='statements', verbose_name="صندوق")
    date = jmodels.jDateField(verbose_name="تاریخ")
    operation_type = models.CharField(max_length=50, verbose_name="نوع عملیات")
    amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="مبلغ")
    running_balance = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="مانده پس از عملیات")
    description = models.CharField(max_length=255, verbose_name="شرح")
    reference_id = models.CharField(max_length=100, blank=True, verbose_name="شناسه مرجع")
    reference_type = models.CharField(max_length=50, blank=True, verbose_name="نوع مرجع")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="ایجاد کننده")
    
    class Meta:
        verbose_name = "صورتحساب صندوق"
        verbose_name_plural = "صورتحساب‌های صندوق"
        ordering = ['fund', 'date', 'created_at']
    
    def __str__(self):
        return f"{self.fund.name} - {self.date} - {self.amount:,} ریال"


class CustomerBalance(models.Model):
    """
    موجودی حساب مشتریان
    """
    customer = models.OneToOneField(Customer, on_delete=models.CASCADE, verbose_name="مشتری")
    current_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="موجودی فعلی")
    total_received = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="مجموع دریافتی")
    total_paid = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="مجموع پرداختی")
    last_transaction_date = jmodels.jDateField(null=True, blank=True, verbose_name="تاریخ آخرین تراکنش")
    
    class Meta:
        verbose_name = "موجودی مشتری"
        verbose_name_plural = "موجودی مشتریان"
    
    def __str__(self):
        return f"{self.customer.get_full_name()} - {self.current_balance:,}"
    
    def update_balance(self, amount, operation_type):
        """به‌روزرسانی موجودی مشتری"""
        if operation_type == 'RECEIVE_FROM_CUSTOMER':
            self.current_balance -= amount  # بدهی مشتری کاهش می‌یابد
            self.total_received += amount
        elif operation_type == 'PAY_TO_CUSTOMER':
            self.current_balance += amount  # بدهی مشتری افزایش می‌یابد
            self.total_paid += amount
        
        self.last_transaction_date = timezone.now().date()
        self.save()


class FinancialTransaction(models.Model):
    """
    تراکنش‌های مالی - برای ثبت دقیق‌تر عملیات‌های مالی
    """
    TRANSACTION_TYPES = [
        ('DEBIT', 'بدهکار'),
        ('CREDIT', 'بستانکار'),
    ]
    
    operation = models.ForeignKey(FinancialOperation, on_delete=models.CASCADE, related_name='transactions', verbose_name="عملیات")
    fund = models.ForeignKey('Fund', on_delete=models.PROTECT, verbose_name="صندوق")
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES, verbose_name="نوع تراکنش")
    amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="مبلغ")
    description = models.CharField(max_length=255, verbose_name="شرح")
    date = jmodels.jDateField(verbose_name="تاریخ تراکنش")
    
    class Meta:
        verbose_name = "تراکنش مالی"
        verbose_name_plural = "تراکنش‌های مالی"
        ordering = ['-date', '-id']


class PettyCashOperation(models.Model):
    """
    عملیات تنخواه
    """
    OPERATION_TYPES = [
        ('ADD', 'افزودن به تنخواه'),
        ('WITHDRAW', 'برداشت از تنخواه'),
    ]
    
    REASON_CHOICES = [
        ('expense', 'هزینه روزانه'),
        ('emergency', 'اورژانس'),
        ('maintenance', 'نگهداری'),
        ('stationery', 'خرید لوازم التحریر'),
        ('transportation', 'هزینه حمل و نقل'),
        ('meals', 'هزینه غذا'),
        ('other', 'سایر'),
    ]
    
    operation_number = models.CharField(max_length=50, unique=True, verbose_name="شماره عملیات")
    operation_type = models.CharField(max_length=20, choices=OPERATION_TYPES, verbose_name="نوع عملیات")
    date = jmodels.jDateField(verbose_name="تاریخ")
    amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="مبلغ")
    reason = models.CharField(max_length=100, choices=REASON_CHOICES, verbose_name="دلیل عملیات")
    description = models.TextField(blank=True, verbose_name="توضیحات")
    
    # فیلدهای جدید برای انتخاب منبع (صندوق یا بانک)
    source_fund = models.ForeignKey(
        Fund, 
        on_delete=models.PROTECT, 
        null=True, 
        blank=True, 
        verbose_name="صندوق منبع",
        related_name='petty_cash_source_operations'
    )
    source_bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="حساب بانکی منبع",
        related_name='petty_cash_source_operations'
    )
    
    # اطلاعات سیستمی
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="ایجاد کننده")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    
    class Meta:
        verbose_name = "عملیات تنخواه"
        verbose_name_plural = "عملیات تنخواه"
        ordering = ['-date', '-created_at']
    
    def __str__(self):
        return f"{self.get_operation_type_display()} - {self.operation_number} - {self.amount:,}"
    
    def save(self, *args, **kwargs):
        if not self.operation_number:
            self.operation_number = self.generate_operation_number()
        
        # Set date to today if not provided
        if not self.date:
            import jdatetime
            self.date = jdatetime.date.today()
            
        super().save(*args, **kwargs)
    
    def generate_operation_number(self):
        """تولید شماره عملیات تنخواه"""
        from datetime import datetime
        import time
        
        prefix = f"PC{datetime.now().strftime('%Y%m%d')}"
        
        # Try to get the last operation number, but handle potential transaction issues
        try:
            last_operation = PettyCashOperation.objects.filter(
                operation_number__startswith=prefix
            ).order_by('-operation_number').first()
            
            if last_operation:
                last_number = int(last_operation.operation_number[-4:])
                new_number = last_number + 1
            else:
                new_number = 1
        except Exception as e:
            # If there's a transaction issue, use timestamp-based numbering
            print(f"Error getting last operation number: {e}")
            timestamp = int(time.time() * 1000) % 10000  # Use last 4 digits of timestamp
            new_number = timestamp
        
        return f"{prefix}{new_number:04d}"


# Signals for automatic balance updates
@receiver(post_save, sender=FinancialOperation)
def update_balances_on_operation_save(sender, instance, created, **kwargs):
    """به‌روزرسانی خودکار موجودی‌ها پس از ثبت عملیات مالی"""
    if created and instance.status == 'CONFIRMED':
        # به‌روزرسانی موجودی مشتری
        if instance.customer:
            customer_balance, created = CustomerBalance.objects.get_or_create(
                customer=instance.customer,
                defaults={'current_balance': 0, 'total_received': 0, 'total_paid': 0}
            )
            customer_balance.update_balance(instance.amount, instance.operation_type)
        
        # به‌روزرسانی موجودی صندوق
        # این بخش نیاز به تعیین صندوق مناسب دارد
        pass
        
        # ایجاد سند حسابداری خودکار
        try:
            from .accounting_utils import create_voucher_for_financial_operation
            create_voucher_for_financial_operation(instance)
        except Exception as e:
            print(f"خطا در ایجاد سند حسابداری برای عملیات {instance.id}: {e}")


@receiver(post_save, sender=PettyCashOperation)
def update_petty_cash_balance(sender, instance, created, **kwargs):
    """به‌روزرسانی موجودی تنخواه و ایجاد سند حسابداری"""
    if created:
        try:
            # Use a separate transaction to avoid conflicts
            from django.db import transaction
            
            with transaction.atomic():
                # به‌روزرسانی موجودی تنخواه
                petty_cash_fund, created = Fund.objects.get_or_create(
                    fund_type='PETTY_CASH',
                    defaults={
                        'name': 'تنخواه',
                        'initial_balance': 0,
                        'current_balance': 0,
                        'created_by': instance.created_by
                    }
                )
                
                if instance.operation_type == 'ADD':
                    petty_cash_fund.current_balance += instance.amount
                else:
                    petty_cash_fund.current_balance -= instance.amount
                
                petty_cash_fund.save()
                
                # ایجاد گردش صندوق
                try:
                    transaction_type = 'IN' if instance.operation_type == 'ADD' else 'OUT'
                    petty_cash_fund.add_transaction(
                        transaction_type=transaction_type,
                        amount=instance.amount,
                        description=f"{instance.get_operation_type_display()} - {instance.get_reason_display()}",
                        reference_id=str(instance.id),
                        reference_type='PettyCashOperation'
                    )
                except Exception as e:
                    print(f"خطا در ایجاد گردش صندوق برای عملیات تنخواه {instance.id}: {e}")
                    
        except Exception as e:
            print(f"خطا در به‌روزرسانی موجودی تنخواه برای عملیات {instance.id}: {e}")


@receiver(post_delete, sender=PettyCashOperation)
def update_petty_cash_balance_on_delete(sender, instance, **kwargs):
    """به‌روزرسانی موجودی تنخواه پس از حذف عملیات و حذف اسناد مرتبط"""
    try:
        # حذف اسناد حسابداری مرتبط با این عملیات تنخواه
        from .models import Voucher, VoucherItem
        
        # حذف آرتیکل‌های سند که به این عملیات تنخواه اشاره می‌کنند
        voucher_items_to_delete = VoucherItem.objects.filter(
            reference_id=str(instance.id),
            reference_type='PettyCashOperation'
        )
        
        # حذف اسناد مرتبط
        vouchers_to_delete = Voucher.objects.filter(
            items__in=voucher_items_to_delete
        ).distinct()
        
        # حذف آرتیکل‌ها و اسناد
        voucher_items_to_delete.delete()
        vouchers_to_delete.delete()
        
        print(f"=== DEBUG: Deleted {voucher_items_to_delete.count()} voucher items and {vouchers_to_delete.count()} vouchers for petty cash operation {instance.id} ===")
        
        # حذف گردش صندوق مرتبط
        fund_transactions_to_delete = FundTransaction.objects.filter(
            reference_id=str(instance.id),
            reference_type='PettyCashOperation'
        )
        
        deleted_transactions_count = fund_transactions_to_delete.count()
        fund_transactions_to_delete.delete()
        
        print(f"=== DEBUG: Deleted {deleted_transactions_count} fund transactions for petty cash operation {instance.id} ===")
        
        # حذف عملیات مالی مرتبط (اگر از بانک یا صندوق بوده)
        if instance.source_fund or instance.source_bank_account:
            from .models import FinancialOperation
            
            # پیدا کردن عملیات مالی مرتبط
            related_operations = FinancialOperation.objects.filter(
                operation_type__in=['RECEIVE_FROM_BANK', 'PAY_TO_BANK', 'BANK_TRANSFER', 'PAYMENT_TO_CASH', 'PAYMENT_FROM_CASH'],
                amount=instance.amount,
                date=instance.date,
                created_by=instance.created_by
            )
            
            # حذف عملیات‌های مرتبط
            deleted_count = related_operations.count()
            related_operations.delete()
            
            print(f"=== DEBUG: Deleted {deleted_count} related financial operations ===")
        
        # محاسبه مجدد مانده تنخواه از تمام عملیات‌های باقی‌مانده
        petty_ops = PettyCashOperation.objects.all()
        
        total_in = sum(op.amount for op in petty_ops if op.operation_type == 'ADD')
        total_out = sum(op.amount for op in petty_ops if op.operation_type == 'WITHDRAW')
        
        # به‌روزرسانی مانده در صندوق‌های تنخواه (اگر وجود داشته باشند)
        petty_cash_funds = Fund.objects.filter(name__icontains='تنخواه')
        for fund in petty_cash_funds:
            fund.current_balance = total_in - total_out
            fund.save()
        
        print(f"=== DEBUG: Petty cash balance updated after delete: {total_in - total_out} ===")
        
    except Exception as e:
        print(f"=== ERROR: Failed to clean up related records for petty cash operation {instance.id}: {e} ===")


@receiver(post_save, sender=Receipt)
def create_voucher_for_receipt_save(sender, instance, created, **kwargs):
    """ایجاد سند حسابداری برای رسید دریافت"""
    if created:
        try:
            from .accounting_utils import create_voucher_for_receipt
            create_voucher_for_receipt(instance)
        except Exception as e:
            print(f"خطا در ایجاد سند حسابداری برای رسید {instance.id}: {e}")


@receiver(post_save, sender=PurchaseInvoice)
def create_voucher_for_purchase_invoice_save(sender, instance, created, **kwargs):
    """ایجاد سند حسابداری برای فاکتور خرید"""
    if created and instance.status == 'confirmed':
        try:
            from .accounting_utils import create_voucher_for_invoice
            create_voucher_for_invoice(instance, 'purchase')
        except Exception as e:
            print(f"خطا در ایجاد سند حسابداری برای فاکتور خرید {instance.id}: {e}")


@receiver(post_save, sender=SalesInvoice)
def create_voucher_for_sales_invoice_save(sender, instance, created, **kwargs):
    """ایجاد سند حسابداری برای فاکتور فروش"""
    if created:
        try:
            # ایجاد سند حسابداری
            voucher = Voucher.objects.create(
                financial_year=FinancialYear.get_current_year(),
                number=get_next_voucher_number(),
                date=instance.invoice_date,
                type='PERMANENT',
                description=f"فاکتور فروش {instance.invoice_number}",
                created_by=instance.created_by
            )
            
            # ایجاد آرتیکل‌های سند
            # بدهکار: حساب مشتری
            customer_account = Account.objects.filter(code__startswith='13').first()
            if customer_account:
                VoucherItem.objects.create(
                    voucher=voucher,
                    account=customer_account,
                    description=f"فاکتور فروش {instance.invoice_number}",
                    debit=instance.total_amount,
                    credit=0,
                    reference_id=str(instance.id),
                    reference_type='SalesInvoice'
                )
            
            # بستانکار: حساب فروش
            sales_account = Account.objects.filter(code__startswith='41').first()
            if sales_account:
                VoucherItem.objects.create(
                    voucher=voucher,
                    account=sales_account,
                    description=f"فاکتور فروش {instance.invoice_number}",
                    debit=0,
                    credit=instance.total_amount,
                    reference_id=str(instance.id),
                    reference_type='SalesInvoice'
                )
                
        except Exception as e:
            print(f"خطا در ایجاد سند حسابداری برای فاکتور فروش {instance.id}: {e}")

@receiver(post_save, sender=FinancialOperation)
def update_fund_balance_on_save(sender, instance, **kwargs):
    """
    Recalculates the balance of the relevant fund whenever a FinancialOperation
    is saved. This handles both operations explicitly linked to a fund and
    implicit cash operations.
    """
    target_fund = instance.fund
    
    # If the operation is not linked to a specific fund, check if it's a cash operation.
    if not target_fund and instance.bank_name is None and instance.account_number is None:
        # This is likely a general cash operation, find the default cash fund.
        target_fund = Fund.objects.filter(fund_type='CASH').first()

    # If we have a fund to update, recalculate its balance.
    if target_fund:
        target_fund.recalculate_balance()

@receiver(post_delete, sender=FinancialOperation)
def update_fund_balance_on_delete(sender, instance, **kwargs):
    if hasattr(instance, 'fund') and instance.fund:
        instance.fund.recalculate_balance()

@receiver(post_save, sender=FundTransaction)
def create_fund_statement_on_transaction_save(sender, instance, created, **kwargs):
    """ایجاد صورتحساب صندوق هنگام ایجاد تراکنش جدید"""
    if created:
        try:
            # محاسبه مانده فعلی از تراکنش‌های قبلی
            previous_statements = instance.fund.statements.order_by('-date', '-created_at')
            previous_balance = 0
            if previous_statements.exists():
                previous_balance = previous_statements.first().running_balance
            else:
                # اگر صورتحساب قبلی وجود ندارد، از موجودی اولیه استفاده کن
                previous_balance = instance.fund.initial_balance
            
            # محاسبه مانده جدید
            if instance.transaction_type == 'IN':
                new_balance = previous_balance + instance.amount
            else:  # OUT
                new_balance = previous_balance - instance.amount
            
            # ایجاد صورتحساب جدید
            FundStatement.objects.create(
                fund=instance.fund,
                date=instance.date,
                operation_type=f'TRANSACTION_{instance.transaction_type}',
                amount=instance.amount,
                running_balance=new_balance,
                description=instance.description,
                reference_id=instance.reference_id,
                reference_type=instance.reference_type,
                created_by=instance.created_by
            )
            
            print(f"=== DEBUG: Created FundStatement for transaction {instance.id} with balance {new_balance} ===")
            
        except Exception as e:
            print(f"خطا در ایجاد صورتحساب صندوق برای تراکنش {instance.id}: {e}")


@receiver(post_delete, sender=FundTransaction)
def update_fund_statements_on_transaction_delete(sender, instance, **kwargs):
    """به‌روزرسانی صورتحساب‌های صندوق پس از حذف تراکنش"""
    try:
        # حذف صورتحساب مرتبط با این تراکنش
        related_statements = FundStatement.objects.filter(
            fund=instance.fund,
            date=instance.date,
            amount=instance.amount,
            description=instance.description,
            reference_id=instance.reference_id,
            reference_type=instance.reference_type
        )
        
        deleted_count = related_statements.count()
        related_statements.delete()
        
        print(f"=== DEBUG: Deleted {deleted_count} fund statements for transaction {instance.id} ===")
        
        # محاسبه مجدد مانده‌های بعدی
        remaining_transactions = instance.fund.transactions.order_by('date', 'created_at')
        current_balance = instance.fund.initial_balance
        
        for transaction in remaining_transactions:
            if transaction.transaction_type == 'IN':
                current_balance += transaction.amount
            else:
                current_balance -= transaction.amount
            
            # به‌روزرسانی یا ایجاد صورتحساب
            statement, created = FundStatement.objects.get_or_create(
                fund=transaction.fund,
                date=transaction.date,
                amount=transaction.amount,
                description=transaction.description,
                reference_id=transaction.reference_id,
                reference_type=transaction.reference_type,
                defaults={
                    'operation_type': f'TRANSACTION_{transaction.transaction_type}',
                    'running_balance': current_balance,
                    'created_by': transaction.created_by
                }
            )
            
            if not created:
                statement.running_balance = current_balance
                statement.save()
        
        print(f"=== DEBUG: Recalculated fund statements after transaction delete ===")
        
    except Exception as e:
        print(f"خطا در به‌روزرسانی صورتحساب‌های صندوق پس از حذف تراکنش {instance.id}: {e}")


@receiver(post_save, sender=PettyCashOperation)
def update_source_fund_balance_on_petty_cash_save(sender, instance, **kwargs):
    """
    Recalculates the balance of the source fund (if any) after a
    PettyCashOperation is saved.
    """
    if instance.source_fund:
        instance.source_fund.recalculate_balance()
    elif instance.source_bank_account:
        # A Petty Cash top-up from a bank account implies an outflow from the corresponding BANK fund.
        bank_fund = Fund.objects.filter(
            fund_type='BANK',
            bank_name=instance.source_bank_account.bank.name,
            account_number=instance.source_bank_account.account_number
        ).first()
        if bank_fund:
            bank_fund.recalculate_balance()

@receiver(post_delete, sender=PettyCashOperation)
def update_source_fund_balance_on_petty_cash_delete(sender, instance, **kwargs):
    """
    Recalculates the balance of the source fund (if any) after a
    PettyCashOperation is deleted.
    """
    if instance.source_fund:
        instance.source_fund.recalculate_balance()
    elif instance.source_bank_account:
        bank_fund = Fund.objects.filter(
            fund_type='BANK',
            bank_name=instance.source_bank_account.bank.name,
            account_number=instance.source_bank_account.account_number
        ).first()
        if bank_fund:
            bank_fund.recalculate_balance()






