from django.contrib import admin
from django import forms
from django.http import HttpResponse
import xlsxwriter
from io import BytesIO
import jdatetime
# django-jalali automatically provides jalali widgets for jDateField and jDateTimeField
from django_jalali.admin.widgets import AdminjDateWidget
from django.utils.html import format_html
from django.urls import reverse
# مطمئن شوید که همه مدل‌هایتان را از models.py ایمپورت کرده‌اید
from .models import (
    Customer, Product, Warehouse, Order, OrderItem, DocumentNumber, OrderStatusHistory, 
    Shipment, ShipmentItem, PriceChange,  PurchaseInvoice, PurchaseInvoiceItem,
    Notification, SalesInvoice, AccountingReport, AccountingReportDetail,
    FinancialYear, Currency, AccountGroup, Account, BankAccount, 
    CashRegister, CheckBook, Check, Voucher, VoucherItem, SalesInvoiceItem,
    Fund, FundBalanceHistory, FinancialOperation, CustomerBalance, PettyCashOperation,
    FinancialTransaction, Bank, CardReaderDevice, FundTransaction, FundStatement, ReceivedCheque
)
import jdatetime as jmodels
from django.db.models import Q, F, Sum
from django.utils.html import format_html







# --- اینها کلاس‌هایی هستند که باید در admin.py باشند ---
class ShipmentItemInline(admin.TabularInline):
    model = ShipmentItem
    extra = 1
    readonly_fields = ('order_item', 'quantity_shipped')

@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ['shipment_number', 'order', 'parent_order', 'shipment_date', 
                   'courier_name', 'status', 'is_backorder']
    list_filter = ['shipment_date', 'status', 'is_backorder']
    search_fields = ['shipment_number', 'courier_name', 'order__order_number']
    readonly_fields = ['shipment_number']
    inlines = [ShipmentItemInline]
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # در حالت ویرایش
            return ['shipment_number', 'order', 'parent_order']
        return ['shipment_number']


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "first_name", 
        "last_name", 
        "store_name", 
        "mobile", 
        "view_transactions_link",
        "created_at"
    )
    search_fields = ("first_name", "last_name", "store_name", "mobile", "phone", "address")
    list_filter = ("created_by", "created_at")
    readonly_fields = ("created_at", "view_transactions_link")
    fieldsets = (
        (None, {
            "fields": (
                "first_name", 
                "last_name", 
                "store_name",
            )
        }),
        ("اطلاعات تماس و ورود", {
            "fields": (
                "mobile", 
                "phone", 
                "address", 
                "user",
            )
        }),
        ("گردش حساب و اطلاعات سیستمی", {
            "fields": (
                "view_transactions_link",
                "created_by", 
                "created_at"
            )
        }),
    )

    def view_transactions_link(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html
        
        url = (
            reverse("admin:products_financialoperation_changelist")
            + f"?customer__id__exact={obj.id}"
        )
        return format_html('<a href="{}" target="_blank">مشاهده گردش حساب</a>', url)
    
    view_transactions_link.short_description = "گردش حساب"

    def created_at_jalali(self, obj):
        return obj.created_at.strftime('%Y/%m/%d %H:%M')

    created_at_jalali.short_description = 'تاریخ ایجاد (شمسی)'

# --- این تابع export_model_to_excel مربوط به actions ادمین است و باید در admin.py باشد ---
def export_model_to_excel(modeladmin, request, queryset):
    model_name = modeladmin.model._meta.verbose_name_plural
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet(str(model_name))
    worksheet.right_to_left()

    header_style = workbook.add_format({
        'bold': True,
        'align': 'center',
        'valign': 'vcenter',
        'text_wrap': True,
        'border': 1,
        'bg_color': '#4e9af1',
        'font_color': 'white',
        'font_size': 12
    })

    cell_style = workbook.add_format({
        'align': 'center',
        'valign': 'vcenter',
        'text_wrap': True,
        'border': 1,
        'font_size': 11
    })

    fields = [field.name for field in modeladmin.model._meta.fields]

    for col, field in enumerate(fields):
        worksheet.write(0, col, field, header_style)

    for row, obj in enumerate(queryset, start=1):
        for col, field in enumerate(fields):
            value = getattr(obj, field)
            if hasattr(value, 'strftime'):
                try:
                    value = jdatetime.datetime.fromgregorian(datetime=value).strftime('%Y/%m/%d %H:%M')
                except:
                    value = str(value)
            if field == "warehouse_status" and hasattr(obj, "get_warehouse_status_display"):
                value = obj.get_warehouse_status_display()
            worksheet.write(row, col, str(value), cell_style)

    workbook.close()
    output.seek(0)
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename={model_name}.xlsx'
    return response

export_model_to_excel.short_description = "دریافت خروجی اکسل از موارد انتخاب شده"


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ('name', 'user')
    search_fields = ('name', 'user__username')
    list_filter = ('name',)
    actions = [export_model_to_excel]

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'brand', 'car_group', 'price', 'purchase_price', 'quantity', 'warehouse', 'get_created_at_jalali', 'max_payment_term') # purchase_price added
    search_fields = ('code', 'name', 'brand', 'car_group')
    list_filter = ('brand', 'car_group', 'warehouse', 'created_at', 'max_payment_term') # created_at به فیلترها اضافه شد
    ordering = ('-created_at',) # مرتب‌سازی بر اساس جدیدترین‌ها
    actions = [export_model_to_excel]

    def get_created_at_jalali(self, obj):
        if obj.created_at:
            return obj.created_at.strftime('%Y/%m/%d %H:%M')
        return "-"
    get_created_at_jalali.short_description = 'تاریخ ایجاد'
    get_created_at_jalali.admin_order_field = 'created_at'


class OrderItemForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'product' in self.data:
            try:
                product_id = int(self.data.get('product'))
                product = Product.objects.get(id=product_id)
                available_terms = product.get_available_payment_terms()
                self.fields['payment_term'].choices = [
                    (term, Product.PAYMENT_TERMS_CHOICES[Product.PAYMENT_TERMS_CHOICES.index((term, term_dict[term]))][1])
                    for term in available_terms
                    for term_dict in [dict(Product.PAYMENT_TERMS_CHOICES)]
                    if term in term_dict
                ]
            except (ValueError, Product.DoesNotExist):
                pass
        elif self.instance.pk and self.instance.product:
            available_terms = self.instance.product.get_available_payment_terms()
            self.fields['payment_term'].choices = [
                (term, Product.PAYMENT_TERMS_CHOICES[Product.PAYMENT_TERMS_CHOICES.index((term, term_dict[term]))][1])
                for term in available_terms
                for term_dict in [dict(Product.PAYMENT_TERMS_CHOICES)]
                if term in term_dict
            ]

    class Meta:
        model = OrderItem
        fields = '__all__'

    def clean_payment_term(self):
        payment_term = self.cleaned_data['payment_term']
        product = self.cleaned_data.get('product')
        if product:
            available_terms = product.get_available_payment_terms()
            if payment_term not in available_terms:
                raise forms.ValidationError(f"شرایط تسویه باید یکی از {available_terms} باشد.")
        return payment_term

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    form = OrderItemForm
    extra = 1
    readonly_fields = ('item_total',)
    fields = ('product', 'requested_quantity', 'allocated_quantity', 'price', 'payment_term', 'warehouse', 'warehouse_status', 'item_total')
    autocomplete_fields = ['product', 'warehouse']

    def item_total(self, obj):
        price = obj.price if obj.price is not None else 0
        quantity = obj.quantity if obj.quantity is not None else 0
        total = quantity * price
        return f"{total:,.0f} ریال"
    item_total.short_description = 'مجموع قیمت'

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'document_number', 'package_count', 'courier_name', 'visitor_name', 'customer_name', 'created_at_jalali', 'payment_term', 'status', 'total_price')
    list_filter = (
        'status',
        'payment_term',
        'created_at',
        ('document_number', admin.EmptyFieldListFilter),
        ('courier_name', admin.EmptyFieldListFilter),
        'package_count',
    )
    search_fields = [
        'order_number',
        'document_number',
        'visitor_name',
        'customer_name',
        'courier_name',
    ]
    date_hierarchy = 'created_at'
    inlines = [OrderItemInline]
    ordering = ('-created_at',)
    actions = ['export_to_excel']

    def created_at_jalali(self, obj):
        return obj.created_at.strftime('%Y/%m/%d %H:%M')
    created_at_jalali.short_description = 'تاریخ ثبت (شمسی)'

    def total_price(self, obj):
        total = sum(
            (item.requested_quantity if item.requested_quantity is not None else 0) *
            (item.price if item.price is not None else 0)
            for item in obj.items.all()
        )
        return f"{total:,.0f} ریال"
    total_price.short_description = 'جمع کل مبلغ'

    def get_status_display_name(self, status):
        status_dict = dict(Order.STATUS_CHOICES)
        return status_dict.get(status, status)

    def export_to_excel(self, request, queryset):
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet('سفارشات')
        worksheet.right_to_left()

        header_style = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'text_wrap': True,
            'border': 1,
            'pattern': 1,
            'bg_color': '#4e9af1',
            'font_color': 'white',
            'font_size': 12
        })

        cell_style = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'text_wrap': True,
            'border': 1,
            'font_size': 11
        })

        worksheet.set_column('A:K', 15)

        headers = [
            'شماره سفارش',
            'شماره سند',
            'تعداد بسته',
            'نام پیک',
            'نام ویزیتور',
            'نام مشتری',
            'تاریخ ثبت',
            'شرایط تسویه',
            'وضعیت',
            'جمع کل مبلغ',
            'آیتم‌های سفارش'
        ]

        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_style)

        for row, obj in enumerate(queryset, start=1):
            jalali_date = obj.created_at.strftime('%Y/%m/%d %H:%M')

            total = sum(
                (item.requested_quantity if item.requested_quantity is not None else 0) *
                (item.price if item.price is not None else 0)
                for item in obj.items.all()
            )

            items_list = []
            for item in obj.items.all():
                try:
                    status_display = item.get_warehouse_status_display()
                except AttributeError:  
                    status_display = item.warehouse_status
                items_list.append(
                    f"{item.product.name} - {item.requested_quantity} عدد - [{status_display}]"
                )
                
            items_str = "\n".join(items_list)

            data = [
                obj.order_number or '',
                obj.document_number or '',
                obj.package_count or 0,
                obj.courier_name or '',
                obj.visitor_name,
                obj.customer_name,
                jalali_date,
                obj.get_payment_term_display(),
                self.get_status_display_name(obj.status),
                f"{total:,} ریال",
                items_str
            ]

            for col, value in enumerate(data):
                worksheet.write(row, col, value, cell_style)

        workbook.close()
        output.seek(0)
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename=orders.xlsx'
        return response
    
    export_to_excel.short_description = "دریافت خروجی اکسل از سفارش‌های انتخاب شده"

# --- کلاس‌های OrderItemAdmin و BackorderFilter باید اینجا باشند ---
class BackorderFilter(admin.SimpleListFilter):
    title = 'آیتم بک‌اوردر؟'
    parameter_name = 'is_backorder'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'بک‌اوردر'),
            ('no', 'غیربک‌اوردر'),
        )

    def queryset(self, request, queryset):
        """
        فیلترها را اعمال می‌کند.
        """
        if self.value() == 'yes':
            # بک‌اوردر کامل: تعداد درخواستی بیشتر از تخصیص یافته و هیچ مقداری تخصیص نیافته باشد
            return queryset.filter(requested_quantity__gt=F('allocated_quantity'), allocated_quantity=0)
        if self.value() == 'partial':
            # بک‌اوردر جزئی: مقداری تخصیص یافته و تعداد درخواستی هنوز بیشتر از تخصیص یافته است
            return queryset.filter(allocated_quantity__gt=0, requested_quantity__gt=F('allocated_quantity'))
        if self.value() == 'no':
            # بدون بک‌اوردر: تمام درخواست‌ها تخصیص یافته‌اند یا هیچ درخواستی وجود ندارد (مقدار تخصیص یافته با درخواستی برابر است)
            return queryset.filter(Q(requested_quantity=F('allocated_quantity')) | Q(requested_quantity__isnull=True)) # تغییر برای شامل شدن آیتم‌های بدون درخواست اولیه
        return queryset

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    form = OrderItemForm
    list_display = [
        'id',
        'order',
        'product',
        'requested_quantity',
        'allocated_quantity',
        'get_backorder_quantity',
        'is_backorder',
        'price',
        'payment_term',
        'warehouse',
        'warehouse_status',
        'total_price_display',
        'warehouse_note'
    ]
    list_filter = [
        'warehouse',
        'warehouse_status',
        'payment_term',
        BackorderFilter,  # ← اضافه کردن فیلتر سفارشی
        ('warehouse_note', admin.EmptyFieldListFilter),
    ]
    search_fields = [
        'order__order_number',
        'order__document_number',
        'product__name',
        'product__code',
        'warehouse_note'
    ]
    raw_id_fields = ['order', 'product']
    autocomplete_fields = ['product', 'warehouse']
    ordering = ('-order__created_at',)
    actions = [export_model_to_excel]

    def total_price_display(self, obj):
        return f"{obj.total_price:,.0f} ریال"
    total_price_display.short_description = 'مجموع قیمت'

    def get_backorder_quantity(self, obj):
        if obj.requested_quantity and obj.allocated_quantity:
            return max(obj.requested_quantity - obj.allocated_quantity, 0)
        return 0
    get_backorder_quantity.short_description = 'تعداد بک‌اوردر'

    def is_backorder(self, obj):
        return obj.warehouse_status == 'backorder'
    is_backorder.boolean = True
    is_backorder.short_description = 'بک‌اوردر؟'

@admin.register(PriceChange)
class PriceChangeAdmin(admin.ModelAdmin):
    list_display = ('product', 'old_price', 'new_price', 'change_date_jalali', 'percentage_change_display')
    list_filter = ('change_date',)
    search_fields = ('product__name', 'product__code')
    date_hierarchy = 'change_date'
    actions = [export_model_to_excel]

    def change_date_jalali(self, obj):
        return obj.change_date.strftime('%Y/%m/%d %H:%M')
    change_date_jalali.short_description = 'تاریخ تغییر (شمسی)'
    change_date_jalali.admin_order_field = 'change_date'

    def percentage_change_display(self, obj):
        percentage = obj.percentage_change
        color = 'green' if percentage > 0 else 'red' if percentage < 0 else 'black'
        
        # عدد را ابتدا فرمت می‌کنیم
        formatted_percentage = f"{percentage:.2f}%"
        
        # سپس رشته فرمت شده را به format_html می‌دهیم
        return format_html('<b style="color:{};">{}</b>', color, formatted_percentage)
    percentage_change_display.short_description = 'درصد تغییر'



class PurchaseInvoiceItemInline(admin.TabularInline):
    model = PurchaseInvoiceItem
    extra = 1
    fields = ('product', 'quantity', 'price', 'discount', 'profit_percentage', 'total', 'description')
    autocomplete_fields = ['product']

@admin.register(PurchaseInvoice)
class PurchaseInvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'customer', 'invoice_date', 'total_amount', 'status', 'created_by', 'created_at')
    search_fields = ('invoice_number', 'customer__first_name', 'customer__last_name')
    list_filter = ('status', 'invoice_date', 'created_by')
    date_hierarchy = 'invoice_date'
    inlines = [PurchaseInvoiceItemInline]
    readonly_fields = ('created_at', 'updated_at')

@admin.register(PurchaseInvoiceItem)
class PurchaseInvoiceItemAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'product', 'quantity', 'price', 'discount', 'profit_percentage', 'total', 'description')
    search_fields = ('invoice__invoice_number', 'product__name', 'product__code')
    list_filter = ('product',)
    autocomplete_fields = ['invoice', 'product']


admin.site.register(Notification)


class SalesInvoiceItemInline(admin.TabularInline):
    model = SalesInvoiceItem
    extra = 1
    fields = ('product', 'quantity', 'price', 'discount', 'profit_percentage', 'total', 'description')
    autocomplete_fields = ['product']

@admin.register(SalesInvoice)
class SalesInvoiceAdmin(admin.ModelAdmin):
    inlines = [SalesInvoiceItemInline]
    list_display = ('invoice_number', 'customer', 'invoice_date', 'total_amount', 'status', 'created_by', 'created_at')
    search_fields = ('invoice_number', 'customer__first_name', 'customer__last_name')
    list_filter = ('status', 'invoice_date', 'created_by')
    date_hierarchy = 'invoice_date'
    readonly_fields = ('created_at', 'updated_at')

# admin.site.register(SalesInvoice) # Will be registered with an inline
admin.site.register(AccountingReport)
admin.site.register(AccountingReportDetail)
admin.site.register(DocumentNumber)
admin.site.register(OrderStatusHistory)
@admin.register(FinancialYear)
class FinancialYearAdmin(admin.ModelAdmin):
    list_display = ('year', 'start_date', 'end_date', 'is_active', 'is_closed', 'created_by')
    list_filter = ('is_active', 'is_closed', 'year')
    search_fields = ('year',)
    readonly_fields = ('created_at', 'created_by')
    date_hierarchy = 'start_date'
    
    fieldsets = (
        (None, {
            'fields': ('year', 'start_date', 'end_date', 'is_active', 'is_closed')
        }),
        ('اطلاعات سیستمی', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    formfield_overrides = {
        'jDateField': {'widget': AdminjDateWidget},
    }

    def save_model(self, request, obj, form, change):
        if not change:  # Only for new objects
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class CheckInline(admin.TabularInline):
    model = Check
    extra = 0
    readonly_fields = ('number', 'status', 'amount', 'date', 'payee', 'created_at')
    fields = ('number', 'status', 'amount', 'date', 'payee', 'description')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False  # چک‌ها فقط از طریق سیستم ایجاد می‌شوند

@admin.register(CheckBook)
class CheckBookAdmin(admin.ModelAdmin):
    list_display = ('serial', 'bank_account', 'start_number', 'end_number', 'current_number', 'is_active', 'created_by', 'created_at', 'get_checks_link')
    list_filter = ('is_active', 'created_at', 'bank_account__bank')
    search_fields = ('serial', 'bank_account__title', 'bank_account__account_number')
    readonly_fields = ('current_number', 'created_at', 'created_by')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    inlines = [CheckInline]
    
    fieldsets = (
        (None, {
            'fields': ('bank_account', 'serial', 'start_number', 'end_number', 'current_number', 'is_active')
        }),
        ('اطلاعات سیستمی', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_checks_link(self, obj):
        """لینک برای مشاهده چک‌های دسته چک"""
        if obj.pk:
            url = reverse('admin:products_check_changelist') + f'?checkbook__id__exact={obj.pk}'
            return format_html('<a href="{}" target="_blank">مشاهده چک‌ها</a>', url)
        return '-'
    get_checks_link.short_description = 'چک‌ها'
    
    def get_total_checks(self, obj):
        """تعداد کل چک‌های دسته چک"""
        return obj.total_checks
    get_total_checks.short_description = 'تعداد کل چک‌ها'
    
    def get_used_checks(self, obj):
        """تعداد چک‌های استفاده شده"""
        return obj.used_checks
    get_used_checks.short_description = 'چک‌های استفاده شده'
    
    def get_remaining_checks(self, obj):
        """تعداد چک‌های باقی‌مانده"""
        return obj.remaining_checks
    get_remaining_checks.short_description = 'چک‌های باقی‌مانده'
    
    def get_issued_checks(self, obj):
        """تعداد چک‌های صادر شده"""
        return obj.issued_checks
    get_issued_checks.short_description = 'چک‌های صادر شده'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only for new objects
            obj.created_by = request.user
            if obj.start_number:
                obj.current_number = obj.start_number
        super().save_model(request, obj, form, change)

admin.site.register(Currency)
admin.site.register(AccountGroup)
admin.site.register(Account)
@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ('title', 'bank', 'account_number', 'current_balance', 'is_active', 'view_transactions_link')
    list_filter = ('bank', 'account_type', 'is_active', 'has_card_reader')
    search_fields = ('title', 'account_number', 'card_number', 'bank__name')
    readonly_fields = ('current_balance', 'created_at', 'created_by', 'view_transactions_link')
    
    fieldsets = (
        (None, {
            'fields': ('account', 'bank', 'account_number', 'sheba', 'card_number', 'account_type', 'title')
        }),
        ('کارت‌خوان', {
            'fields': ('has_card_reader', 'card_reader_device_1', 'card_reader_device_2', 'card_reader_device_3', 'card_reader_device_4'),
            'classes': ('collapse',)
        }),
        ('موجودی و گردش حساب', {
            'fields': ('initial_balance', 'current_balance', 'view_transactions_link'),
            'classes': ('collapse',)
        }),
        ('وضعیت', {
            'fields': ('is_active', 'description'),
            'classes': ('collapse',)
        }),
        ('اطلاعات سیستمی', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )

    def view_transactions_link(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html
        import urllib.parse

        # Use direct field lookups for a more reliable filter
        query_string = urllib.parse.urlencode({
            'bank_name__exact': obj.bank.name,
            'account_number__exact': obj.account_number
        })
        
        url = reverse("admin:products_financialoperation_changelist") + '?' + query_string
        return format_html('<a href="{}" target="_blank">مشاهده گردش حساب</a>', url)
    
    view_transactions_link.short_description = "گردش حساب"
    
    def get_card_readers_count(self, obj):
        if not obj.has_card_reader:
            return "بدون کارت‌خوان"
        
        count = 0
        if obj.card_reader_device_1: count += 1
        if obj.card_reader_device_2: count += 1
        if obj.card_reader_device_3: count += 1
        if obj.card_reader_device_4: count += 1
        
        return f"{count} دستگاه" if count > 0 else "بدون انتخاب"
    get_card_readers_count.short_description = "تعداد کارت‌خوان‌ها"
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only for new objects
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
# admin.site.register(CashRegister)  # حذف شده چون با Fund تداخل دارد
# admin.site.register(Check)  # حذف شده چون فقط دسته چک‌ها باید در منو باشد
admin.site.register(Bank)
admin.site.register(FinancialTransaction)

@admin.register(CardReaderDevice)
class CardReaderDeviceAdmin(admin.ModelAdmin):
    list_display = ('name', 'device_type', 'terminal_number', 'bank_account', 'is_active', 'view_transactions_link')
    list_filter = ('device_type', 'is_active', 'manufacturer', 'bank_account__bank', 'created_at')
    search_fields = ('name', 'terminal_number', 'serial_number', 'manufacturer', 'model', 'support_company', 'support_phone', 'bank_account__title')
    readonly_fields = ('created_at', 'created_by', 'view_transactions_link')
    ordering = ('name', 'terminal_number')
    
    fieldsets = (
        (None, {
            'fields': ('name', 'device_type', 'terminal_number', 'is_active')
        }),
        ('ارتباط و تراکنش‌ها', {
            'fields': ('bank_account', 'view_transactions_link'),
        }),
        ('اطلاعات فنی', {
            'fields': ('serial_number', 'manufacturer', 'model'),
            'classes': ('collapse',)
        }),
        ('اطلاعات پشتیبانی', {
            'fields': ('support_company', 'support_phone', 'support_email'),
            'classes': ('collapse',)
        }),
        ('توضیحات', {
            'fields': ('description',),
            'classes': ('collapse',)
        }),
        ('اطلاعات سیستمی', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )

    def view_transactions_link(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html
        
        url = (
            reverse("admin:products_financialoperation_changelist")
            + f"?card_reader_device__id__exact={obj.id}"
        )
        return format_html('<a href="{}" target="_blank">مشاهده تراکنش‌ها</a>', url)
    
    view_transactions_link.short_description = "گردش حساب"
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only for new objects
            obj.created_by = request.user
        super().save_model(request, obj, form, change)



@admin.register(Check)
class CheckAdmin(admin.ModelAdmin):
    list_display = ('number', 'checkbook', 'amount', 'date', 'payee', 'status', 'created_at')
    list_filter = ('status', 'date', 'checkbook__bank_account__bank', 'checkbook')
    search_fields = ('number', 'payee', 'description', 'checkbook__serial')
    readonly_fields = ('created_at', 'created_by')
    date_hierarchy = 'date'
    ordering = ('-date', '-created_at')
    
    fieldsets = (
        (None, {
            'fields': ('checkbook', 'number', 'amount', 'date', 'payee', 'status')
        }),
        ('اطلاعات اضافی', {
            'fields': ('description', 'bank_name', 'bank_branch', 'account_number'),
            'classes': ('collapse',)
        }),
        ('اطلاعات سیستمی', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    formfield_overrides = {
        'jDateField': {'widget': AdminjDateWidget},
    }
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only for new objects
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

class VoucherItemInline(admin.TabularInline):
    model = VoucherItem
    extra = 1

from .models import Receipt

@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    inlines = [VoucherItemInline]
    list_display = ('number', 'date', 'type', 'description', 'is_confirmed', 'created_by', 'created_at')
    list_filter = ('type', 'is_confirmed', 'date')
    search_fields = ('number', 'description')

admin.site.register(VoucherItem)

@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'date', 'amount', 'payment_method', 'created_by', 'created_at')
    list_filter = ('payment_method', 'date')
    search_fields = ('customer__first_name', 'customer__last_name', 'amount')
    date_hierarchy = 'date'


@admin.register(Fund)
class FundAdmin(admin.ModelAdmin):
    list_display = ('name', 'fund_type', 'initial_balance', 'current_balance', 'calculated_balance', 'is_active', 'get_transactions_link', 'get_statement_link', 'created_by', 'created_at')
    list_filter = ('fund_type', 'is_active', 'created_at')
    search_fields = ('name', 'bank_name', 'account_number')
    readonly_fields = ('current_balance', 'calculated_balance', 'created_at', 'updated_at')
    actions = ['delete_selected', 'delete_empty_funds', 'recalculate_balances', 'generate_statements', 'export_fund_report', 'generate_balance_report']
    fieldsets = (
        (None, {
            'fields': ('name', 'fund_type', 'initial_balance', 'current_balance', 'calculated_balance', 'is_active')
        }),
        ('اطلاعات بانکی', {
            'fields': ('bank_name', 'account_number', 'sheba_number'),
            'classes': ('collapse',)
        }),
        ('توضیحات', {
            'fields': ('description',),
            'classes': ('collapse',)
        }),
        ('اطلاعات سیستمی', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def calculated_balance(self, obj):
        """محاسبه مانده از عملیات مالی"""
        try:
            calculated = obj.calculate_balance_from_operations()
            if calculated == obj.current_balance:
                return format_html('<span style="color: green;">{:,}</span>', calculated)
            else:
                return format_html('<span style="color: red;">{:,} (متفاوت)</span>', calculated)
        except:
            return '-'
    calculated_balance.short_description = 'مانده محاسبه شده'

    def save_model(self, request, obj, form, change):
        if not change:  # Only for new objects
            obj.created_by = request.user
            obj.current_balance = obj.initial_balance
        super().save_model(request, obj, form, change)

    def get_transactions_link(self, obj):
        """لینک برای مشاهده عملیات مالی صندوق"""
        if obj.pk:
            url = reverse('admin:products_financialoperation_changelist') + f'?fund__id__exact={obj.pk}'
            return format_html('<a href="{}" target="_blank">مشاهده عملیات مالی</a>', url)
        return '-'
    get_transactions_link.short_description = 'عملیات مالی'

    def get_statement_link(self, obj):
        """لینک برای مشاهده صورتحساب صندوق"""
        if obj.pk:
            url = reverse('admin:products_fundstatement_changelist') + f'?fund__id__exact={obj.pk}'
            return format_html('<a href="{}" target="_blank">مشاهده صورتحساب</a>', url)
        return '-'
    get_statement_link.short_description = 'صورتحساب'
    
    def delete_empty_funds(self, request, queryset):
        """حذف صندوق‌های خالی"""
        empty_funds = queryset.filter(current_balance=0)
        count = empty_funds.count()
        empty_funds.delete()
        self.message_user(request, f'{count} صندوق خالی حذف شد.')
    delete_empty_funds.short_description = "حذف صندوق‌های خالی"

    def recalculate_balances(self, request, queryset):
        """محاسبه مجدد مانده صندوق‌ها"""
        updated_count = 0
        for fund in queryset:
            try:
                old_balance = fund.current_balance
                new_balance = fund.recalculate_balance()
                if old_balance != new_balance:
                    updated_count += 1
            except Exception as e:
                self.message_user(request, f'خطا در محاسبه مانده صندوق {fund.name}: {str(e)}', level='ERROR')
        
        self.message_user(request, f'مانده {updated_count} صندوق به‌روزرسانی شد.')
    recalculate_balances.short_description = "محاسبه مجدد مانده"

    def generate_statements(self, request, queryset):
        """تولید صورتحساب برای صندوق‌ها"""
        from .models import FundStatement
        from django.utils import timezone
        import jdatetime
        
        generated_count = 0
        for fund in queryset:
            try:
                # محاسبه مانده فعلی
                current_balance = fund.calculate_balance_from_operations()
                
                # ایجاد رکورد صورتحساب
                statement = FundStatement.objects.create(
                    fund=fund,
                    date=jdatetime.date.today(),
                    operation_type='BALANCE_CALCULATION',
                    amount=0,
                    running_balance=current_balance,
                    description='محاسبه مانده از عملیات مالی',
                    created_by=request.user
                )
                generated_count += 1
            except Exception as e:
                self.message_user(request, f'خطا در تولید صورتحساب صندوق {fund.name}: {str(e)}', level='ERROR')
        
        self.message_user(request, f'صورتحساب برای {generated_count} صندوق تولید شد.')
    generate_statements.short_description = "تولید صورتحساب"

    def export_fund_report(self, request, queryset):
        """خروجی گزارش صندوق‌ها"""
        return export_model_to_excel(self, request, queryset)
    export_fund_report.short_description = "خروجی گزارش صندوق‌ها"

    def get_queryset(self, request):
        """بهینه‌سازی کوئری برای نمایش بهتر"""
        return super().get_queryset(request).select_related('created_by')

    def get_fund_summary(self, request):
        """نمایش خلاصه وضعیت صندوق‌ها"""
        from django.db.models import Sum, Count
        
        total_funds = Fund.objects.count()
        active_funds = Fund.objects.filter(is_active=True).count()
        total_balance = Fund.objects.aggregate(Sum('current_balance'))['current_balance__sum'] or 0
        
        cash_funds = Fund.objects.filter(fund_type='CASH').aggregate(Sum('current_balance'))['current_balance__sum'] or 0
        bank_funds = Fund.objects.filter(fund_type='BANK').aggregate(Sum('current_balance'))['current_balance__sum'] or 0
        petty_cash_funds = Fund.objects.filter(fund_type='PETTY_CASH').aggregate(Sum('current_balance'))['current_balance__sum'] or 0
        
        return {
            'total_funds': total_funds,
            'active_funds': active_funds,
            'total_balance': total_balance,
            'cash_funds': cash_funds,
            'bank_funds': bank_funds,
            'petty_cash_funds': petty_cash_funds,
        }

    def generate_balance_report(self, request, queryset):
        """تولید گزارش مانده صندوق‌ها"""
        from django.http import HttpResponse
        import csv
        import jdatetime
        
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="fund_balance_report_{jdatetime.date.today()}.csv"'
        
        # Write BOM for UTF-8
        response.write('\ufeff')
        
        writer = csv.writer(response)
        writer.writerow([
            'نام صندوق',
            'نوع صندوق',
            'موجودی اولیه',
            'موجودی فعلی',
            'مانده محاسبه شده',
            'وضعیت',
            'تاریخ ایجاد'
        ])
        
        for fund in queryset:
            calculated_balance = fund.calculate_balance_from_operations()
            writer.writerow([
                fund.name,
                fund.get_fund_type_display(),
                fund.initial_balance,
                fund.current_balance,
                calculated_balance,
                'فعال' if fund.is_active else 'غیرفعال',
                fund.created_at.strftime('%Y/%m/%d')
            ])
        
        return response
    generate_balance_report.short_description = "تولید گزارش مانده"

    def changelist_view(self, request, extra_context=None):
        """نمایش خلاصه در صفحه لیست صندوق‌ها"""
        extra_context = extra_context or {}
        extra_context['fund_summary'] = self.get_fund_summary(request)
        return super().changelist_view(request, extra_context)


@admin.register(FundTransaction)
class FundTransactionAdmin(admin.ModelAdmin):
    list_display = ('fund', 'transaction_type', 'amount', 'date', 'description', 'reference_type', 'created_by')
    list_filter = ('fund', 'transaction_type', 'date', 'fund__fund_type')
    search_fields = ('fund__name', 'description', 'reference_id')
    readonly_fields = ('created_at', 'created_by')
    date_hierarchy = 'date'
    ordering = ('-date', '-created_at')
    actions = ['export_transactions_to_excel']
    
    fieldsets = (
        (None, {
            'fields': ('fund', 'transaction_type', 'amount', 'date', 'description')
        }),
        ('اطلاعات مرجع', {
            'fields': ('reference_id', 'reference_type'),
            'classes': ('collapse',)
        }),
        ('اطلاعات سیستمی', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    formfield_overrides = {
        'date': {'widget': AdminjDateWidget},
    }
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only for new objects
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def export_transactions_to_excel(self, request, queryset):
        """خروجی اکسل از گردش صندوق‌ها"""
        return export_model_to_excel(self, request, queryset)
    export_transactions_to_excel.short_description = "خروجی اکسل"

    def get_transaction_summary(self, request):
        """نمایش خلاصه گردش صندوق‌ها"""
        from django.db.models import Sum, Count
        
        total_transactions = FundTransaction.objects.count()
        total_in = FundTransaction.objects.filter(transaction_type='IN').aggregate(Sum('amount'))['amount__sum'] or 0
        total_out = FundTransaction.objects.filter(transaction_type='OUT').aggregate(Sum('amount'))['amount__sum'] or 0
        net_flow = total_in - total_out
        
        return {
            'total_transactions': total_transactions,
            'total_in': total_in,
            'total_out': total_out,
            'net_flow': net_flow,
        }


@admin.register(FundStatement)
class FundStatementAdmin(admin.ModelAdmin):
    list_display = ('fund', 'date', 'operation_type', 'amount', 'running_balance', 'description', 'reference_type')
    list_filter = ('fund', 'operation_type', 'date', 'fund__fund_type')
    search_fields = ('fund__name', 'description', 'reference_id')
    readonly_fields = ('created_at',)
    date_hierarchy = 'date'
    ordering = ('-date', '-created_at')
    actions = ['export_statements_to_excel']
    
    fieldsets = (
        (None, {
            'fields': ('fund', 'date', 'operation_type', 'amount', 'running_balance', 'description')
        }),
        ('اطلاعات مرجع', {
            'fields': ('reference_id', 'reference_type'),
            'classes': ('collapse',)
        }),
        ('اطلاعات سیستمی', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    formfield_overrides = {
        'date': {'widget': AdminjDateWidget},
    }

    def export_statements_to_excel(self, request, queryset):
        """خروجی اکسل از صورتحساب صندوق‌ها"""
        return export_model_to_excel(self, request, queryset)
    export_statements_to_excel.short_description = "خروجی اکسل"


@admin.register(FundBalanceHistory)
class FundBalanceHistoryAdmin(admin.ModelAdmin):
    list_display = ('fund', 'date', 'previous_balance', 'change_amount', 'new_balance', 'operation', 'description')
    list_filter = ('fund', 'date', 'fund__fund_type')
    search_fields = ('fund__name', 'description')
    readonly_fields = ('fund', 'date', 'previous_balance', 'change_amount', 'new_balance', 'operation', 'description')
    date_hierarchy = 'date'


@admin.register(FinancialOperation)
class FinancialOperationAdmin(admin.ModelAdmin):
    list_display = ('operation_number', 'operation_type', 'date', 'amount', 'status', 'customer', 'fund_info', 'created_by', 'bank_name', 'account_number')
    list_filter = ('operation_type', 'status', 'date', 'payment_method', 'fund', 'bank_name', 'card_reader_device', 'customer')
    search_fields = ('operation_number', 'description', 'customer__first_name', 'customer__last_name', 'fund__name', 'fund__fund_type', 'bank_name', 'account_number')
    readonly_fields = ('operation_number', 'created_at', 'updated_at')
    date_hierarchy = 'date'
    ordering = ('-date', '-created_at')
    list_per_page = 20
    actions = ['confirm_operations', 'export_operations_to_excel']
    
    fieldsets = (
        (None, {
            'fields': ('operation_type', 'operation_number', 'date', 'amount', 'status')
        }),
        ('اطلاعات طرف حساب', {
            'fields': ('customer', 'fund', 'bank_name', 'account_number'),
            'classes': ('collapse',)
        }),
        ('اطلاعات پرداخت', {
            'fields': ('payment_method', 'reference_number', 'cheque_number', 'cheque_date'),
            'classes': ('collapse',)
        }),
        ('توضیحات', {
            'fields': ('description',),
            'classes': ('collapse',)
        }),
        ('اطلاعات سیستمی', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    formfield_overrides = {
        'date': {'widget': AdminjDateWidget},
    }

    def fund_info(self, obj):
        """نمایش اطلاعات صندوق مرتبط"""
        if obj.fund:
            return format_html('<span style="color: blue;">{}</span>', obj.fund.name)
        return '-'
    fund_info.short_description = 'صندوق مرتبط'

    def confirm_operations(self, request, queryset):
        """تأیید عملیات‌های انتخاب شده"""
        confirmed_count = 0
        for operation in queryset.filter(status='DRAFT'):
            try:
                operation.confirm_operation(request.user)
                confirmed_count += 1
            except Exception as e:
                self.message_user(request, f'خطا در تأیید عملیات {operation.operation_number}: {str(e)}', level='ERROR')
        
        self.message_user(request, f'{confirmed_count} عملیات تأیید شد.')
    confirm_operations.short_description = "تأیید عملیات‌های انتخاب شده"

    def export_operations_to_excel(self, request, queryset):
        """خروجی اکسل از عملیات مالی"""
        return export_model_to_excel(self, request, queryset)
    export_operations_to_excel.short_description = "خروجی اکسل"
    
    class Meta:
        verbose_name = "عملیات مالی"
        verbose_name_plural = "عملیات‌های مالی"


@admin.register(CustomerBalance)
class CustomerBalanceAdmin(admin.ModelAdmin):
    list_display = ('customer', 'current_balance', 'total_received', 'total_paid', 'last_transaction_date')
    list_filter = ('last_transaction_date',)
    search_fields = ('customer__first_name', 'customer__last_name')
    readonly_fields = ('customer', 'current_balance', 'total_received', 'total_paid', 'last_transaction_date')
    actions = ['recalculate_customer_balances']

    def recalculate_customer_balances(self, request, queryset):
        """محاسبه مجدد مانده مشتریان"""
        updated_count = 0
        for balance in queryset:
            try:
                # محاسبه مجدد از عملیات مالی
                operations = FinancialOperation.objects.filter(
                    customer=balance.customer,
                    status='CONFIRMED'
                )
                
                total_received = operations.filter(
                    operation_type__in=['RECEIVE_FROM_CUSTOMER', 'RECEIVE_FROM_BANK']
                ).aggregate(Sum('amount'))['amount__sum'] or 0
                
                total_paid = operations.filter(
                    operation_type__in=['PAY_TO_CUSTOMER', 'PAY_TO_BANK']
                ).aggregate(Sum('amount'))['amount__sum'] or 0
                
                balance.total_received = total_received
                balance.total_paid = total_paid
                balance.current_balance = total_received - total_paid
                balance.save()
                updated_count += 1
            except Exception as e:
                self.message_user(request, f'خطا در محاسبه مانده مشتری {balance.customer}: {str(e)}', level='ERROR')
        
        self.message_user(request, f'مانده {updated_count} مشتری به‌روزرسانی شد.')
    recalculate_customer_balances.short_description = "محاسبه مجدد مانده مشتریان"


@admin.register(PettyCashOperation)
class PettyCashOperationAdmin(admin.ModelAdmin):
    list_display = ('operation_number', 'operation_type', 'date', 'amount', 'reason', 'source_fund', 'created_by')
    list_filter = ('operation_type', 'date', 'reason', 'source_fund')
    search_fields = ('operation_number', 'reason', 'description')
    readonly_fields = ('operation_number', 'created_at')
    date_hierarchy = 'date'
    actions = ['calculate_petty_cash_balance']
    
    fieldsets = (
        (None, {
            'fields': ('operation_type', 'operation_number', 'date', 'amount', 'reason')
        }),
        ('اطلاعات منبع', {
            'fields': ('source_fund', 'source_bank_account'),
            'classes': ('collapse',)
        }),
        ('توضیحات', {
            'fields': ('description',),
            'classes': ('collapse',)
        }),
        ('اطلاعات سیستمی', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    formfield_overrides = {
        'date': {'widget': AdminjDateWidget},
    }

    def calculate_petty_cash_balance(self, request, queryset):
        """محاسبه مانده تنخواه"""
        try:
            balance = Fund.get_petty_cash_balance()
            self.message_user(request, f'مانده تنخواه: {balance:,} ریال')
        except Exception as e:
            self.message_user(request, f'خطا در محاسبه مانده تنخواه: {str(e)}', level='ERROR')
    calculate_petty_cash_balance.short_description = "محاسبه مانده تنخواه"

    def get_petty_cash_summary(self, request):
        """نمایش خلاصه عملیات تنخواه"""
        from django.db.models import Sum, Count
        
        total_operations = PettyCashOperation.objects.count()
        total_add = PettyCashOperation.objects.filter(operation_type='ADD').aggregate(Sum('amount'))['amount__sum'] or 0
        total_withdraw = PettyCashOperation.objects.filter(operation_type='WITHDRAW').aggregate(Sum('amount'))['amount__sum'] or 0
        current_balance = total_add - total_withdraw
        
        return {
            'total_operations': total_operations,
            'total_add': total_add,
            'total_withdraw': total_withdraw,
            'current_balance': current_balance,
        }

@admin.register(ReceivedCheque)
class ReceivedChequeAdmin(admin.ModelAdmin):
    list_display = ('sayadi_id', 'customer', 'amount', 'jalali_due_date', 'bank_name', 'status', 'created_by', 'jalali_created_at')
    list_filter = ('status', 'bank_name', 'due_date', 'created_by')
    search_fields = (
        'sayadi_id', 
        'customer__first_name', 
        'customer__last_name', 
        'owner_name', 
        'serial',
        'series',
        'bank_name',
        'branch_name',
        'account_number',
        'national_id',
        'endorsement'
    )
    readonly_fields = ('jalali_created_at', 'jalali_updated_at', 'created_by')
    fieldsets = (
        (None, {
            'fields': ('customer', 'financial_operation', 'status')
        }),
        ('اطلاعات چک', {
            'fields': ('sayadi_id', 'amount', 'due_date', 'bank_name', 'branch_name', 'account_number', 'owner_name', 'national_id', 'series', 'serial')
        }),
        ('اطلاعات تکمیلی', {
            'fields': ('endorsement', 'created_by', 'jalali_created_at', 'jalali_updated_at')
        }),
    )

    def jalali_due_date(self, obj):
        if obj.due_date:
            return jdatetime.date.fromgregorian(date=obj.due_date).strftime('%Y/%m/%d')
        return '-'
    jalali_due_date.short_description = "تاریخ سررسید"
    jalali_due_date.admin_order_field = 'due_date'

    def jalali_created_at(self, obj):
        if obj.created_at:
            return jdatetime.datetime.fromgregorian(datetime=obj.created_at).strftime('%Y/%m/%d %H:%M')
        return '-'
    jalali_created_at.short_description = "تاریخ ثبت"
    jalali_created_at.admin_order_field = 'created_at'

    def jalali_updated_at(self, obj):
        if obj.updated_at:
            return jdatetime.datetime.fromgregorian(datetime=obj.updated_at).strftime('%Y/%m/%d %H:%M')
        return '-'
    jalali_updated_at.short_description = "تاریخ بروزرسانی"
    jalali_updated_at.admin_order_field = 'updated_at'

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)