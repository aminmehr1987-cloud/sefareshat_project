from django import forms
from django.forms import inlineformset_factory
from .models import Order, OrderItem, Product, Customer, ReceivedCheque
from .models import FinancialYear, Currency
from .models import FinancialOperation, Fund, PettyCashOperation, CustomerBalance
from .models import BankAccount, Bank, CheckBook, Check
from django.core.exceptions import ValidationError
from django.utils import timezone
import jdatetime




class FinancialYearForm(forms.ModelForm):
    start_date_shamsi = forms.CharField(
        label="تاریخ شروع",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'تاریخ شروع را انتخاب کنید',
            'readonly': 'readonly'
        }),
        required=True
    )
    
    end_date_shamsi = forms.CharField(
        label="تاریخ پایان",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'تاریخ پایان را انتخاب کنید',
            'readonly': 'readonly'
        }),
        required=True
    )
    
    class Meta:
        model = FinancialYear
        fields = ['year', 'is_active']
        widgets = {
            'year': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.start_date:
                self.fields['start_date_shamsi'].initial = self.instance.start_date.strftime('%Y/%m/%d')
            if self.instance.end_date:
                self.fields['end_date_shamsi'].initial = self.instance.end_date.strftime('%Y/%m/%d')
    
    def clean(self):
        cleaned_data = super().clean()
        start_date_shamsi = cleaned_data.get('start_date_shamsi')
        end_date_shamsi = cleaned_data.get('end_date_shamsi')
        
        if start_date_shamsi and end_date_shamsi:
            try:
                # تبدیل تاریخ شمسی به میلادی
                from .views import convert_shamsi_to_gregorian
                start_date = convert_shamsi_to_gregorian(start_date_shamsi)
                end_date = convert_shamsi_to_gregorian(end_date_shamsi)
                
                cleaned_data['start_date'] = start_date
                cleaned_data['end_date'] = end_date
                
                if start_date >= end_date:
                    raise ValidationError("تاریخ شروع باید قبل از تاریخ پایان باشد")
                
                # بررسی همپوشانی با سال‌های مالی دیگر
                overlapping_years = FinancialYear.objects.filter(
                    start_date__lte=end_date,
                    end_date__gte=start_date
                )
                if self.instance:
                    overlapping_years = overlapping_years.exclude(pk=self.instance.pk)
                
                if overlapping_years.exists():
                    raise ValidationError("این بازه زمانی با سال مالی دیگری همپوشانی دارد")
                    
            except ValueError as e:
                raise ValidationError(f"خطا در فرمت تاریخ: {str(e)}")

        return cleaned_data


class ReceivedCheckForm(forms.ModelForm):
    """
    فرم ثبت چک دریافتی در مودال
    """
    # Override bank_name to be a dropdown from the Bank model
    bank = forms.ModelChoiceField(
        queryset=Bank.objects.filter(is_active=True).order_by('name'),
        label="نام بانک",
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="بانک را انتخاب کنید"
    )

    class Meta:
        model = Check
        fields = [
            'endorsement', 'number', 'series', 'bank', 'bank_branch', 
            'account_number', 'sayadi_id', 'amount', 'owner_national_id', 'owner_name', 'date'
        ]
        widgets = {
            'endorsement': forms.TextInput(attrs={'class': 'form-control'}),
            'number': forms.TextInput(attrs={'class': 'form-control'}),
            'series': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_branch': forms.TextInput(attrs={'class': 'form-control'}),
            'account_number': forms.TextInput(attrs={'class': 'form-control'}),
            'sayadi_id': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 16}),
            'amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'owner_national_id': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 10}),
            'owner_name': forms.TextInput(attrs={'class': 'form-control'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
        labels = {
            'endorsement': "پشت نمره",
            'number': "سریال چک",
            'series': "سری چک",
            'bank': "نام بانک",
            'bank_branch': "نام شعبه",
            'account_number': "شماره حساب",
            'sayadi_id': "شناسه صیادی",
            'amount': "مبلغ",
            'owner_national_id': "کدملی صاحب حساب",
            'owner_name': "نام صاحب حساب",
            'date': "تاریخ سررسید",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['series'].required = False
        self.fields['owner_national_id'].required = False
        self.fields['owner_name'].required = False
        
        # Override the bank_name from the model with the ModelChoiceField
        self.fields['bank_name'] = self.fields.pop('bank')

    def clean_sayadi_id(self):
        sayadi_id = self.cleaned_data.get('sayadi_id')
        if sayadi_id and (not sayadi_id.isdigit() or len(sayadi_id) != 16):
            raise ValidationError("شناسه صیادی باید یک عدد 16 رقمی باشد.")
        return sayadi_id

class CurrencyForm(forms.ModelForm):
    class Meta:
        model = Currency
        fields = ['code', 'name', 'symbol', 'is_default', 'exchange_rate', 'is_active']
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'مثال: IRR یا USD'
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'مثال: ریال یا دلار'
            }),
            'symbol': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'مثال: ﷼ یا $'
            }),
            'exchange_rate': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.000001'
            }),
        }

    def clean_code(self):
        code = self.cleaned_data['code'].upper()
        if len(code) != 3:
            raise ValidationError("کد ارز باید دقیقاً 3 حرف باشد")
        return code

    def clean(self):
        cleaned_data = super().clean()
        is_default = cleaned_data.get('is_default')
        exchange_rate = cleaned_data.get('exchange_rate')

        if is_default and exchange_rate != 1:
            cleaned_data['exchange_rate'] = 1
        
        if is_default:
            # اگر این ارز به عنوان پیش‌فرض انتخاب شده، مطمئن شویم که ارز پیش‌فرض دیگری نداریم
            Currency.objects.filter(is_default=True).update(is_default=False)
        

class CustomerForm(forms.ModelForm):
    # ... (بدون تغییر، همان کد قبلی شما)
    first_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'نام را وارد کنید'
        }),
        error_messages={
            'required': 'لطفاً نام را وارد کنید'
        }
    )
    last_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'نام خانوادگی را وارد کنید'
        }),
        error_messages={
            'required': 'لطفاً نام خانوادگی را وارد کنید'
        }
    )
    store_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'نام فروشگاه را وارد کنید (اختیاری)'
        })
    )
    phone = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'شماره تلفن ثابت را وارد کنید (اختیاری)'
        })
    )
    mobile = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'شماره موبایل را وارد کنید'
        }),
        error_messages={
            'required': 'لطفاً شماره موبایل را وارد کنید',
            'unique': 'مشتری دیگری با این شماره همراه قبلاً ثبت شده است'
        }
    )
    address = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'آدرس را وارد کنید',
            'rows': 3
        }),
        error_messages={
            'required': 'لطفاً آدرس را وارد کنید'
        }
    )

    class Meta:
        model = Customer
        fields = ['first_name', 'last_name', 'store_name', 'phone', 'mobile', 'address']

    def clean_mobile(self):
        mobile = self.cleaned_data.get('mobile')
        if mobile:
            mobile = mobile.strip().replace(' ', '').replace('-', '')
            if not mobile.startswith('0'):
                raise forms.ValidationError('شماره موبایل باید با صفر شروع شود')
            if len(mobile) != 11:
                raise forms.ValidationError('شماره موبایل باید 11 رقم باشد')
            if not mobile.isdigit():
                raise forms.ValidationError('شماره موبایل باید فقط شامل اعداد باشد')
            if Customer.objects.filter(mobile=mobile).exists():
                if self.instance and self.instance.mobile == mobile:
                    return mobile
                raise forms.ValidationError('مشتری دیگری با این شماره همراه قبلاً ثبت شده است')
            return mobile
        return mobile


class UploadExcelForm(forms.Form):
    excel_file = forms.FileField(label="انتخاب فایل اکسل")
    upload_mode = forms.ChoiceField(
        choices=[
            ('update', 'ورود اولیه - آپدیت کامل (جایگزینی موجودی)'),
            ('purchase', ' خرید - آپدیت اطلاعات کالا (افزودن به موجودی قبلی)'),
        ],
        widget=forms.RadioSelect,
        initial='update',
        label='نوع عملیات'
    )

class OrderForm(forms.ModelForm):
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.all(),
        required=True,
        label='مشتری'
    )

    class Meta:
        model = Order
        fields = ['customer', 'visitor_name', 'payment_term']

class OrderItemForm(forms.ModelForm):
    class Meta:
        model = OrderItem
        fields = ['product', 'requested_quantity','allocated_quantity', 'price', 'payment_term']

    product_display = forms.CharField(
        label="محصول",
        required=False,
        disabled=True, # این فیلد قابل ویرایش نیست
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    product_id = forms.IntegerField(widget=forms.HiddenInput(), required=False) # required=False برای موارد جدید

    class Meta:
        model = OrderItem
        fields = ['product', 'requested_quantity', 'allocated_quantity', 'price', 'payment_term']
        widgets = {
            'product': forms.HiddenInput(),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'placeholder': 'تعداد'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'قیمت واحد'}),
            'payment_term': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'quantity': 'تعداد',
            'price': 'قیمت واحد',
            'payment_term': 'تسویه آیتم',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.product:
            self.fields['product_display'].initial = f"{self.instance.product.name} ({self.instance.product.code})"
            self.fields['product_id'].initial = self.instance.product.id
        if self.instance and self.instance.product:
            available_terms = self.instance.product.get_available_payment_terms()
            self.fields['payment_term'].choices = [
                (term, term_display) 
                for term, term_display in Product.PAYMENT_TERMS_CHOICES 
                if term in available_terms
            ]
        else:
            self.fields['payment_term'].choices = Product.PAYMENT_TERMS_CHOICES

    def clean(self):
        cleaned_data = super().clean()
        product_id = cleaned_data.get('product_id')
        product_instance = cleaned_data.get('product')
        if product_id is not None and product_instance is not None and product_instance.id != product_id:
            self.add_error('product_id', "شناسه محصول معتبر نیست.")
        elif product_id is not None and product_instance is None:
            try:
                cleaned_data['product'] = Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                self.add_error('product_id', "محصول انتخاب شده یافت نشد.")
        elif product_id is None and product_instance is None and self.prefix:
            if not (cleaned_data.get('quantity') or cleaned_data.get('price')):
                raise forms.ValidationError("لطفاً محصول و حداقل تعداد/قیمت را برای آیتم جدید وارد کنید یا آن را حذف کنید.", code='empty_row')
            else:
                self.add_error('product_id', "لطفاً محصول را انتخاب کنید.")

        return cleaned_data

from .models import Receipt

OrderItemFormSet = inlineformset_factory(
    Order,
    OrderItem,
    form=OrderItemForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)

class ReceiptForm(forms.ModelForm):
    date_shamsi = forms.CharField(
        label="تاریخ",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'تاریخ را انتخاب کنید',
            'readonly': 'readonly'
        }),
        required=True
    )
    
    class Meta:
        model = Receipt
        fields = ['customer', 'amount', 'payment_method', 'description']
        widgets = {
            'customer': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.date:
            self.fields['date_shamsi'].initial = self.instance.date.strftime('%Y/%m/%d')
    
    def clean(self):
        cleaned_data = super().clean()
        date_shamsi = cleaned_data.get('date_shamsi')
        
        if date_shamsi:
            try:
                from .views import convert_shamsi_to_gregorian
                date = convert_shamsi_to_gregorian(date_shamsi)
                cleaned_data['date'] = date
            except ValueError as e:
                raise ValidationError(f"خطا در فرمت تاریخ: {str(e)}")
        
        return cleaned_data

class ReceivedChequeEditForm(forms.ModelForm):
    due_date = forms.CharField(
        label="تاریخ سررسید",
        widget=forms.TextInput(attrs={'class': 'form-control autoformat-date', 'placeholder': 'YYYY/MM/DD'}),
        required=True
    )
    
    bank_name = forms.ChoiceField(
        label="نام بانک",
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=True
    )

    class Meta:
        model = ReceivedCheque
        fields = [
            'due_date', 'bank_name', 'branch_name', 'serial', 'series', 'sayadi_id', 
            'amount', 'owner_name', 'national_id', 'account_number', 'endorsement'
        ]
        widgets = {
            'branch_name': forms.TextInput(attrs={'class': 'form-control'}),
            'serial': forms.TextInput(attrs={'class': 'form-control'}),
            'series': forms.TextInput(attrs={'class': 'form-control'}),
            'sayadi_id': forms.TextInput(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'owner_name': forms.TextInput(attrs={'class': 'form-control'}),
            'national_id': forms.TextInput(attrs={'class': 'form-control'}),
            'account_number': forms.TextInput(attrs={'class': 'form-control'}),
            'endorsement': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate bank choices dynamically
        bank_choices = [(bank.name, bank.name) for bank in Bank.objects.filter(is_active=True).order_by('name')]
        self.fields['bank_name'].choices = [('', 'انتخاب بانک')] + bank_choices
        
        if self.instance and self.instance.pk:
            # Set initial value for due_date
            if self.instance.due_date:
                self.initial['due_date'] = jdatetime.date.fromgregorian(date=self.instance.due_date).strftime('%Y/%m/%d')
            
            # Set initial bank
            if self.instance.bank_name:
                self.initial['bank_name'] = self.instance.bank_name

    def clean_due_date(self):
        date_str = self.cleaned_data.get('due_date')
        if isinstance(date_str, str):
            try:
                year, month, day = map(int, date_str.split('/'))
                jdate = jdatetime.date(year, month, day)
                return jdate.togregorian()
            except (ValueError, TypeError):
                raise ValidationError("فرمت تاریخ نامعتبر است. لطفاً از انتخابگر تاریخ استفاده کنید.", code='invalid_date_format')
        return date_str

class ReceivedChequeStatusChangeForm(forms.ModelForm):
    class Meta:
        model = ReceivedCheque
        fields = ['status', 'recipient_name']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
            'recipient_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'نام کامل دریافت کننده چک را وارد کنید'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get("status")
        recipient_name = cleaned_data.get("recipient_name")

        if status == 'SPENT' and not recipient_name:
            self.add_error('recipient_name', 'برای وضعیت "خرج شده"، نام دریافت کننده الزامی است.')

        return cleaned_data


class FinancialOperationForm(forms.ModelForm):
    """
    فرم عملیات مالی
    """
    date_shamsi = forms.CharField(
        label="تاریخ",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'تاریخ را انتخاب کنید',
            'readonly': 'readonly'
        }),
        required=True
    )
    
    class Meta:
        model = FinancialOperation
        fields = [
            'operation_type', 'amount', 'description', 'customer', 
            'bank_name', 'account_number', 'payment_method', 
            'reference_number', 'cheque_number', 'cheque_date'
        ]
        widgets = {
            'operation_type': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'مبلغ را وارد کنید',
                'step': '0.01'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'توضیحات اضافی (اختیاری)'
            }),
            'customer': forms.Select(attrs={'class': 'form-control'}),
            'bank_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'نام بانک'
            }),
            'account_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'شماره حساب'
            }),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'reference_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'شماره مرجع'
            }),
            'cheque_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'شماره چک'
            }),
            'cheque_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # تنظیم فیلدهای اختیاری بر اساس نوع عملیات
        if 'operation_type' in self.initial:
            self.set_required_fields(self.initial['operation_type'])
    
    def set_required_fields(self, operation_type):
        """تنظیم فیلدهای اجباری بر اساس نوع عملیات"""
        if operation_type in ['RECEIVE_FROM_CUSTOMER', 'PAY_TO_CUSTOMER']:
            self.fields['customer'].required = True
            self.fields['bank_name'].required = False
            self.fields['account_number'].required = False
        elif operation_type in ['RECEIVE_FROM_BANK', 'PAY_TO_BANK', 'BANK_TRANSFER']:
            self.fields['customer'].required = False
            self.fields['bank_name'].required = True
            self.fields['account_number'].required = True
        else:
            self.fields['customer'].required = False
            self.fields['bank_name'].required = False
            self.fields['account_number'].required = False


class FundForm(forms.ModelForm):
    """
    فرم صندوق
    """
    class Meta:
        model = Fund
        fields = [
            'name', 'fund_type', 'initial_balance', 'bank_name', 
            'account_number', 'sheba_number', 'description'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'نام صندوق'
            }),
            'fund_type': forms.Select(attrs={'class': 'form-control'}),
            'initial_balance': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'موجودی اولیه',
                'step': '0.01'
            }),
            'bank_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'نام بانک'
            }),
            'account_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'شماره حساب'
            }),
            'sheba_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'شماره شبا'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'توضیحات'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # تنظیم فیلدهای اجباری بر اساس نوع صندوق
        if 'fund_type' in self.initial:
            self.set_required_fields(self.initial['fund_type'])
    
    def set_required_fields(self, fund_type):
        """تنظیم فیلدهای اجباری بر اساس نوع صندوق"""
        if fund_type == 'BANK':
            self.fields['bank_name'].required = True
            self.fields['account_number'].required = True
        else:
            self.fields['bank_name'].required = False
            self.fields['account_number'].required = False


class PettyCashOperationForm(forms.ModelForm):
    """
    فرم عملیات تنخواه
    """
    date_shamsi = forms.CharField(
        label="تاریخ",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'تاریخ را انتخاب کنید',
            'readonly': 'readonly'
        }),
        required=True
    )
    
    # فیلدهای جدید برای انتخاب منبع
    source_fund = forms.ModelChoiceField(
        label="صندوق منبع",
        queryset=Fund.objects.filter(fund_type__in=['CASH', 'PETTY_CASH'], is_active=True),
        widget=forms.Select(attrs={
            'class': 'form-control',
            'placeholder': 'انتخاب صندوق منبع'
        }),
        empty_label="انتخاب صندوق منبع",
        required=False
    )
    
    source_bank_account = forms.ModelChoiceField(
        label="حساب بانکی منبع",
        queryset=BankAccount.objects.filter(is_active=True),
        widget=forms.Select(attrs={
            'class': 'form-control',
            'placeholder': 'انتخاب حساب بانکی منبع'
        }),
        empty_label="انتخاب حساب بانکی منبع",
        required=False
    )
    
    # فیلد reason به صورت جداگانه تعریف می‌شود تا اجباری نباشد
    reason = forms.ChoiceField(
        label="دلیل عملیات",
        choices=[
            ('', 'انتخاب دلیل'),
            ('expense', 'هزینه روزانه'),
            ('emergency', 'اورژانس'),
            ('maintenance', 'نگهداری'),
            ('other', 'سایر'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=False
    )
    
    class Meta:
        model = PettyCashOperation
        fields = ['operation_type', 'amount', 'description', 'source_fund', 'source_bank_account']
        widgets = {
            'operation_type': forms.Select(attrs={'class': 'form-control'}, choices=[
                ('', 'انتخاب نوع عملیات'),
                ('ADD', 'افزودن به تنخواه'),
                ('WITHDRAW', 'برداشت از تنخواه'),
            ]),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'مبلغ را وارد کنید',
                'step': '0.01'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'توضیحات اضافی (اختیاری)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # تنظیم تاریخ فعلی
        current_date = jdatetime.datetime.now().strftime('%Y/%m/%d')
        self.fields['date_shamsi'].initial = current_date
    
    def clean(self):
        cleaned_data = super().clean()
        operation_type = cleaned_data.get('operation_type')
        source_fund = cleaned_data.get('source_fund')
        source_bank_account = cleaned_data.get('source_bank_account')
        reason = cleaned_data.get('reason')
        
        if operation_type == 'ADD':
            # برای افزودن به تنخواه، باید یکی از صندوق یا حساب بانکی انتخاب شود
            if not source_fund and not source_bank_account:
                raise forms.ValidationError('برای افزودن به تنخواه، باید صندوق یا حساب بانکی منبع انتخاب شود.')
            if source_fund and source_bank_account:
                raise forms.ValidationError('فقط یکی از صندوق یا حساب بانکی باید انتخاب شود.')
            # برای افزودن به تنخواه، دلیل عملیات اجباری نیست
            cleaned_data['reason'] = 'other'  # مقدار پیش‌فرض
        elif operation_type == 'WITHDRAW':
            # برای برداشت از تنخواه، دلیل عملیات اجباری است
            if not reason:
                raise forms.ValidationError('برای برداشت از تنخواه، دلیل عملیات الزامی است.')
        
        return cleaned_data


class CustomerBalanceForm(forms.ModelForm):
    """
    فرم موجودی مشتری
    """
    class Meta:
        model = CustomerBalance
        fields = ['current_balance']
        widgets = {
            'current_balance': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
        }


# Forms for specific financial operations
class ReceiveFromCustomerForm(forms.ModelForm):
    """
    فرم دریافت از مشتری
    """
    date_shamsi = forms.CharField(
        label="تاریخ",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'تاریخ را انتخاب کنید',
            'readonly': 'readonly'
        }),
        required=True
    )
    
    bank_account = forms.ModelChoiceField(
        label="حساب بانکی",
        queryset=BankAccount.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="انتخاب حساب بانکی",
        required=False
    )
    
    class Meta:
        model = FinancialOperation
        fields = ['operation_type', 'customer', 'amount', 'payment_method', 'card_reader_device', 'bank_account', 'description']
        widgets = {
            'operation_type': forms.HiddenInput(),
            'customer': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'مبلغ را وارد کنید',
                'step': '0.01'
            }),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'card_reader_device': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'توضیحات اضافی (اختیاری)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['operation_type'].initial = 'RECEIVE_FROM_CUSTOMER'
        
        # Set current date as initial value
        current_date = jdatetime.datetime.now().strftime('%Y/%m/%d')
        self.fields['date_shamsi'].initial = current_date

        # Limit payment_method choices to only specific methods for receive from customer
        self.fields['payment_method'].choices = [
            ('cash', 'نقدی'),
            ('bank_transfer', 'حواله بانکی'),
            ('cheque', 'چک'),
            ('pos', 'دستگاه POS'),
        ]


class PayToCustomerForm(forms.ModelForm):
    """
    فرم پرداخت به مشتری
    """
    date_shamsi = forms.CharField(
        label="تاریخ",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'تاریخ را انتخاب کنید',
            'readonly': 'readonly'
        }),
        required=True
    )
    
    class Meta:
        model = FinancialOperation
        fields = ['operation_type', 'customer', 'amount', 'payment_method', 'description']
        widgets = {
            'operation_type': forms.HiddenInput(),
            'customer': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'مبلغ را وارد کنید',
                'inputmode': 'numeric'
            }),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'توضیحات اضافی (اختیاری)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['operation_type'].initial = 'PAY_TO_CUSTOMER'
        self.fields['operation_type'].widget = forms.HiddenInput()
        
        # Set current date as initial value
        import jdatetime
        current_date = jdatetime.datetime.now().strftime('%Y/%m/%d')
        self.fields['date_shamsi'].initial = current_date

        # Filter payment_method choices
        self.fields['payment_method'].choices = [
            ('cash', 'نقدی'),
            ('cheque', 'چک'),
        ]


class BankOperationForm(forms.ModelForm):
    """
    فرم عملیات بانکی
    """
    date_shamsi = forms.CharField(
        label="تاریخ",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'تاریخ را انتخاب کنید',
            'readonly': 'readonly'
        }),
        required=True
    )
    
    class Meta:
        model = FinancialOperation
        fields = ['operation_type', 'bank_name', 'account_number', 'amount', 'payment_method', 'description']
        widgets = {
            'operation_type': forms.HiddenInput(),
            'bank_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'نام بانک'
            }),
            'account_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'شماره حساب'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'مبلغ را وارد کنید',
                'step': '0.01'
            }),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'توضیحات اضافی (اختیاری)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # operation_type will be set by the view based on the URL parameter


class BankTransferForm(forms.ModelForm):
    """
    فرم حواله بانکی - با انتخاب حساب‌های تعریف شده
    """
    date_shamsi = forms.CharField(
        label="تاریخ",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'تاریخ را انتخاب کنید',
            'readonly': 'readonly'
        }),
        required=True
    )
    
    from_bank_account = forms.ModelChoiceField(
        label="حساب بانکی مبدا",
        queryset=BankAccount.objects.filter(is_active=True),
        widget=forms.Select(attrs={
            'class': 'form-control',
            'placeholder': 'انتخاب حساب بانکی مبدا'
        }),
        empty_label="انتخاب حساب بانکی مبدا",
        required=True
    )
    
    to_bank = forms.ModelChoiceField(
        label="بانک مقصد",
        queryset=Bank.objects.filter(is_active=True),
        widget=forms.Select(attrs={
            'class': 'form-control',
            'placeholder': 'انتخاب بانک مقصد'
        }),
        empty_label="انتخاب بانک مقصد",
        required=True
    )
    
    recipient = forms.ModelChoiceField(
        label="گیرنده حواله",
        queryset=Customer.objects.all(),
        widget=forms.HiddenInput(),
        required=False  # تغییر به False
    )
    
    recipient_display = forms.CharField(
        label="گیرنده حواله",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'برای انتخاب گیرنده کلیک کنید',
            'readonly': 'readonly'
        }),
        required=False
    )
    
    to_account = forms.CharField(
        label="شماره حساب مقصد",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'شماره حساب مقصد را وارد کنید'
        }),
        required=True
    )
    
    class Meta:
        model = FinancialOperation
        fields = ['operation_type', 'amount', 'description']
        widgets = {
            'operation_type': forms.HiddenInput(),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'مبلغ را وارد کنید',
                'step': '0.01'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'توضیحات اضافی (اختیاری)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['operation_type'].initial = 'BANK_TRANSFER'
        self.fields['operation_type'].widget = forms.HiddenInput()
        # اطمینان از اینکه مقدار اولیه در POST data هم وجود دارد
        if 'data' in kwargs and kwargs['data']:
            kwargs['data'] = kwargs['data'].copy()
            kwargs['data']['operation_type'] = 'BANK_TRANSFER'


class CashOperationForm(forms.ModelForm):
    """
    فرم عملیات صندوق
    """
    date_shamsi = forms.CharField(
        label="تاریخ",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'تاریخ را انتخاب کنید',
            'readonly': 'readonly'
        }),
        required=True
    )
    
    class Meta:
        model = FinancialOperation
        fields = ['operation_type', 'amount', 'payment_method', 'description']
        widgets = {
            'operation_type': forms.HiddenInput(),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'مبلغ را وارد کنید',
                'step': '0.01'
            }),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'توضیحات اضافی (اختیاری)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # operation_type will be set by the view based on the URL parameter


class CapitalInvestmentForm(forms.ModelForm):
    """
    فرم سرمایه گذاری
    """
    date_shamsi = forms.CharField(
        label="تاریخ",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'تاریخ را انتخاب کنید',
            'readonly': 'readonly'
        }),
        required=True
    )
    
    investment_type = forms.ChoiceField(
        label="نوع سرمایه گذاری",
        choices=[
            ('', 'انتخاب نوع سرمایه گذاری'),
            ('equipment', 'تجهیزات'),
            ('property', 'املاک'),
            ('stocks', 'سهام'),
            ('bonds', 'اوراق قرضه'),
            ('other', 'سایر'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    expected_return = forms.DecimalField(
        label="بازده مورد انتظار (%)",
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'درصد بازده',
            'step': '0.01'
        })
    )
    
    class Meta:
        model = FinancialOperation
        fields = ['operation_type', 'amount', 'description']
        widgets = {
            'operation_type': forms.HiddenInput(),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'مبلغ سرمایه گذاری',
                'step': '0.01'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'توضیحات سرمایه گذاری (اختیاری)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['operation_type'].initial = 'CAPITAL_INVESTMENT'


class IssueCheckForm(forms.Form):
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.all(), 
        widget=forms.HiddenInput()
    )
    cheque_bank_account = forms.ModelChoiceField(
        queryset=BankAccount.objects.filter(is_active=True),
        label="حساب بانکی",
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="یک حساب بانکی انتخاب کنید"
    )
    checkbook = forms.ModelChoiceField(
        queryset=CheckBook.objects.none(),
        label="دسته چک",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    check_number = forms.ModelChoiceField(
        queryset=Check.objects.none(),
        label="شماره چک",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    cheque_amount = forms.DecimalField(
        label="مبلغ چک",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    cheque_due_date = forms.CharField(
        label="تاریخ سررسید",
        widget=forms.TextInput(attrs={'class': 'form-control persian-datepicker', 'placeholder': 'YYYY/MM/DD'})
    )
    cheque_payee = forms.CharField(
        label="در وجه",
        widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': True})
    )
    series = forms.CharField(
        label="سری چک",
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    sayadi_id = forms.CharField(
        label="شناسه صیادی",
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'maxlength': 16})
    )

class BankAccountForm(forms.ModelForm):
    """
    فرم حساب بانکی
    """
    class Meta:
        model = BankAccount
        fields = [
            'bank', 'account_number', 'sheba', 'card_number', 
            'account_type', 'title', 'has_card_reader', 'card_reader_device_1',
            'card_reader_device_2', 'card_reader_device_3', 'card_reader_device_4',
            'description', 'initial_balance'
        ]
        widgets = {
            'bank': forms.Select(attrs={
                'class': 'form-control',
                'placeholder': 'انتخاب بانک'
            }),
            'account_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'شماره حساب'
            }),
            'sheba': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'شماره شبا (IR...)',
                'maxlength': '26'
            }),
            'card_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'شماره کارت (اختیاری)'
            }),
            'account_type': forms.Select(attrs={
                'class': 'form-control',
                'placeholder': 'نوع حساب'
            }),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'عنوان حساب'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'توضیحات (اختیاری)'
            }),
            'initial_balance': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'موجودی اولیه',
                'step': '0.01'
            }),
            'has_card_reader': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'style': 'margin-left: 8px;'
            }),
            'card_reader_device_1': forms.Select(attrs={
                'class': 'form-control',
                'placeholder': 'انتخاب دستگاه کارت‌خوان 1'
            }),
            'card_reader_device_2': forms.Select(attrs={
                'class': 'form-control',
                'placeholder': 'انتخاب دستگاه کارت‌خوان 2'
            }),
            'card_reader_device_3': forms.Select(attrs={
                'class': 'form-control',
                'placeholder': 'انتخاب دستگاه کارت‌خوان 3'
            }),
            'card_reader_device_4': forms.Select(attrs={
                'class': 'form-control',
                'placeholder': 'انتخاب دستگاه کارت‌خوان 4'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set initial values
        self.fields['account_type'].initial = 'CHECKING'
        
        # Customize bank field to show better labels
        self.fields['bank'].queryset = Bank.objects.filter(is_active=True).order_by('name')
        self.fields['bank'].empty_label = "انتخاب بانک"
        self.fields['bank'].label = "نام بانک"
        
        # Customize initial_balance field
        self.fields['initial_balance'].label = "موجودی اولیه"
        self.fields['initial_balance'].help_text = "موجودی اولیه را وارد کنید تا با موجودی فعلی جمع شود"
        
        # Add new balance field (editable)
        self.fields['new_balance'] = forms.DecimalField(
            label="موجودی جدید",
            required=False,
            widget=forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'موجودی جدید محاسبه شده',
                'step': '0.01'
            })
        )
        
        # Configure card reader device fields
        from .models import CardReaderDevice
        card_reader_queryset = CardReaderDevice.objects.filter(is_active=True).order_by('name')
        
        self.fields['card_reader_device_1'].queryset = card_reader_queryset
        self.fields['card_reader_device_1'].empty_label = "انتخاب دستگاه کارت‌خوان 1"
        self.fields['card_reader_device_1'].required = False
        
        self.fields['card_reader_device_2'].queryset = card_reader_queryset
        self.fields['card_reader_device_2'].empty_label = "انتخاب دستگاه کارت‌خوان 2"
        self.fields['card_reader_device_2'].required = False
        
        self.fields['card_reader_device_3'].queryset = card_reader_queryset
        self.fields['card_reader_device_3'].empty_label = "انتخاب دستگاه کارت‌خوان 3"
        self.fields['card_reader_device_3'].required = False
        
        self.fields['card_reader_device_4'].queryset = card_reader_queryset
        self.fields['card_reader_device_4'].empty_label = "انتخاب دستگاه کارت‌خوان 4"
        self.fields['card_reader_device_4'].required = False
    
    def clean_sheba(self):
        sheba = self.cleaned_data.get('sheba')
        if sheba:
            # Validate sheba format (IR + 24 digits)
            if not sheba.startswith('IR'):
                raise forms.ValidationError('شماره شبا باید با IR شروع شود')
            if len(sheba) != 26:
                raise forms.ValidationError('شماره شبا باید 26 کاراکتر باشد')
            if not sheba[2:].isdigit():
                raise forms.ValidationError('بعد از IR فقط اعداد مجاز است')
        return sheba
    
    def clean_card_number(self):
        card_number = self.cleaned_data.get('card_number')
        if card_number:
            # Remove spaces and dashes
            card_number_clean = card_number.replace(' ', '').replace('-', '')
            if not card_number_clean.isdigit():
                raise forms.ValidationError('شماره کارت باید فقط شامل اعداد باشد')
            if len(card_number_clean) != 16:
                raise forms.ValidationError('شماره کارت باید 16 رقم باشد')
        return card_number
    
    def clean(self):
        cleaned_data = super().clean()
        has_card_reader = cleaned_data.get('has_card_reader')
        
        if has_card_reader:
            # Check if at least one card reader device is selected
            card_reader_devices = [
                cleaned_data.get('card_reader_device_1'),
                cleaned_data.get('card_reader_device_2'),
                cleaned_data.get('card_reader_device_3'),
                cleaned_data.get('card_reader_device_4')
            ]
            
            if not any(device for device in card_reader_devices):
                raise forms.ValidationError('در صورت فعال بودن کارت‌خوان، حداقل یک دستگاه کارت‌خوان باید انتخاب شود')
        
        return cleaned_data


class CheckBookForm(forms.ModelForm):
    """
    فرم دسته چک
    """
    class Meta:
        model = CheckBook
        fields = ['bank_account', 'serial', 'start_number', 'end_number', 'is_active']
        widgets = {
            'bank_account': forms.Select(attrs={
                'class': 'form-control',
                'placeholder': 'انتخاب حساب بانکی'
            }),
            'serial': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'سریال دسته چک'
            }),
            'start_number': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'شماره اولین چک'
            }),
            'end_number': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'شماره آخرین چک'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        labels = {
            'bank_account': 'حساب بانکی',
            'serial': 'سریال دسته چک',
            'start_number': 'شماره اولین چک',
            'end_number': 'شماره آخرین چک',
            'is_active': 'فعال',
        }

    def clean(self):
        cleaned_data = super().clean()
        start_number = cleaned_data.get('start_number')
        end_number = cleaned_data.get('end_number')
        
        if start_number and end_number:
            if start_number >= end_number:
                raise ValidationError("شماره اولین چک باید کمتر از شماره آخرین چک باشد")
            
            # بررسی تعداد چک‌ها (حداکثر 100 چک)
            check_count = end_number - start_number + 1
            if check_count > 100:
                raise ValidationError("تعداد چک‌ها نمی‌تواند بیشتر از 100 باشد")
        
        return cleaned_data

    def save(self, commit=True):
        checkbook = super().save(commit=False)
        
        # Set current_number to start_number initially
        if checkbook.start_number:
            checkbook.current_number = checkbook.start_number
        
        if commit:
            checkbook.save()
            
            # ایجاد چک‌ها
            start_number = self.cleaned_data.get('start_number')
            end_number = self.cleaned_data.get('end_number')
            
            if start_number and end_number:
                from .models import Check
                for check_number in range(start_number, end_number + 1):
                    Check.objects.create(
                        checkbook=checkbook,
                        number=str(check_number),
                        status='UNUSED'
                    )
        
        return checkbook

class ReceiveFromBankForm(forms.ModelForm):
    """
    فرم دریافت از بانک - با انتخاب حساب‌های تعریف شده
    """
    date_shamsi = forms.CharField(
        label="تاریخ",
        widget=forms.TextInput(attrs={
            'class': 'form-control persian-datepicker',
            'placeholder': 'تاریخ را انتخاب کنید',
            'readonly': 'readonly'
        }),
        required=True
    )
    
    bank_account = forms.ModelChoiceField(
        label="حساب بانکی",
        queryset=BankAccount.objects.filter(is_active=True),
        widget=forms.Select(attrs={
            'class': 'form-control',
            'placeholder': 'انتخاب حساب بانکی'
        }),
        empty_label="انتخاب حساب بانکی",
        required=True
    )
    
    payment_method = forms.ChoiceField(
        label="روش دریافت",
        choices=[
            ('', 'انتخاب روش دریافت'),
            ('cash', 'دریافت نقدی'),
            ('check', 'چک'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=True
    )
    
    class Meta:
        model = FinancialOperation
        fields = ['operation_type', 'amount', 'description']
        widgets = {
            'operation_type': forms.HiddenInput(),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'مبلغ را وارد کنید',
                'step': '0.01'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'توضیحات اضافی (اختیاری)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['operation_type'].initial = 'RECEIVE_FROM_BANK'
        self.fields['operation_type'].widget = forms.HiddenInput()
        # اطمینان از اینکه مقدار اولیه در POST data هم وجود دارد
        if 'data' in kwargs and kwargs['data']:
            kwargs['data'] = kwargs['data'].copy()
            kwargs['data']['operation_type'] = 'RECEIVE_FROM_BANK'

class FinancialOperationEditForm(forms.ModelForm):
    """
    فرم ویرایش عملیات مالی
    """
    date_shamsi = forms.CharField(
        label="تاریخ",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'تاریخ را انتخاب کنید',
            'readonly': 'readonly'
        }),
        required=True
    )
    
    class Meta:
        model = FinancialOperation
        fields = [
            'operation_type', 'amount', 'description', 'customer', 
            'bank_name', 'account_number', 'payment_method', 
            'reference_number', 'cheque_number', 'cheque_date', 'status',
            'card_reader_device'
        ]
        widgets = {
            'operation_type': forms.Select(attrs={
                'class': 'form-control',
                'placeholder': 'انتخاب نوع عملیات'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'مبلغ را وارد کنید',
                'step': '0.01'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'توضیحات عملیات',
                'rows': '3'
            }),
            'customer': forms.Select(attrs={
                'class': 'form-control',
                'placeholder': 'انتخاب مشتری'
            }),
            'bank_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'نام بانک'
            }),
            'account_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'شماره حساب'
            }),
            'payment_method': forms.Select(attrs={
                'class': 'form-control',
                'placeholder': 'انتخاب روش پرداخت'
            }),
            'reference_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'شماره مرجع'
            }),
            'cheque_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'شماره چک'
            }),
            'status': forms.Select(attrs={
                'class': 'form-control',
                'placeholder': 'وضعیت عملیات'
            }),
            'card_reader_device': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'operation_type': 'نوع عملیات',
            'amount': 'مبلغ',
            'description': 'توضیحات',
            'customer': 'مشتری',
            'bank_name': 'نام بانک',
            'account_number': 'شماره حساب',
            'payment_method': 'روش پرداخت',
            'reference_number': 'شماره مرجع',
            'cheque_number': 'شماره چک',
            'status': 'وضعیت',
            'card_reader_device': 'دستگاه کارتخوان',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.date:
                self.fields['date_shamsi'].initial = self.instance.date.strftime('%Y/%m/%d')
            if self.instance.cheque_date:
                self.fields['cheque_date'].widget = forms.TextInput(attrs={
                    'class': 'form-control',
                    'placeholder': 'تاریخ چک را انتخاب کنید',
                    'readonly': 'readonly'
                })
                self.fields['cheque_date'].initial = self.instance.cheque_date.strftime('%Y/%m/%d')

        # Make payment-specific fields not required by default
        self.fields['bank_name'].required = False
        self.fields['account_number'].required = False
        self.fields['reference_number'].required = False
        self.fields['cheque_number'].required = False
        self.fields['cheque_date'].required = False
        self.fields['card_reader_device'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        date_shamsi = cleaned_data.get('date_shamsi')
        payment_method = cleaned_data.get('payment_method')
        
        if date_shamsi:
            try:
                from .views import convert_shamsi_to_gregorian
                cleaned_data['date'] = convert_shamsi_to_gregorian(date_shamsi)
            except (ValueError, TypeError):
                self.add_error('date_shamsi', "فرمت تاریخ نامعتبر است.")

        # Server-side validation for payment-specific fields
        if payment_method == 'pos':
            if not cleaned_data.get('card_reader_device'):
                self.add_error('card_reader_device', 'برای پرداخت با کارتخوان، انتخاب دستگاه الزامی است.')
        
        elif payment_method == 'bank_transfer':
            if not cleaned_data.get('bank_name'):
                self.add_error('bank_name', 'برای حواله بانکی، نام بانک الزامی است.')
            if not cleaned_data.get('account_number'):
                self.add_error('account_number', 'برای حواله بانکی، شماره حساب الزامی است.')

        return cleaned_data

class IssuedCheckEditForm(forms.ModelForm):
    date_shamsi = forms.CharField(
        label="تاریخ سررسید",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'YYYY/MM/DD'}),
        required=True
    )

    class Meta:
        model = Check
        fields = ['payee', 'amount', 'series', 'sayadi_id', 'description']
        widgets = {
            'payee': forms.TextInput(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'series': forms.TextInput(attrs={'class': 'form-control'}),
            'sayadi_id': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 16}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'payee': 'در وجه',
            'amount': 'مبلغ',
            'series': 'سری چک',
            'sayadi_id': 'شناسه صیادی',
            'description': 'توضیحات',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and getattr(self.instance, 'date', None):
            try:
                self.fields['date_shamsi'].initial = self.instance.date.strftime('%Y/%m/%d')
            except Exception:
                pass

    def clean(self):
        cleaned_data = super().clean()
        date_str = cleaned_data.get('date_shamsi')
        if isinstance(date_str, str):
            try:
                year, month, day = map(int, date_str.split('/'))
                jdate = jdatetime.date(year, month, day)
                cleaned_data['date'] = jdate.togregorian()
            except (ValueError, TypeError):
                raise ValidationError("فرمت تاریخ نامعتبر است. لطفاً از انتخابگر تاریخ استفاده کنید.", code='invalid_date_format')
        return cleaned_data

    def clean_sayadi_id(self):
        sayadi_id = self.cleaned_data.get('sayadi_id')
        if sayadi_id:
            if not str(sayadi_id).isdigit() or len(str(sayadi_id)) != 16:
                raise ValidationError("شناسه صیادی باید یک عدد 16 رقمی باشد.")
        return sayadi_id

    def save(self, commit=True):
        instance = super().save(commit=False)
        date_value = self.cleaned_data.get('date')
        if date_value:
            instance.date = date_value
        if commit:
            instance.save()
        return instance