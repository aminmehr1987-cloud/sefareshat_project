# 📅 تصحیح مشکل تقویم شمسی

## 🔍 مشکل
کتابخانه `persian-datepicker` نسخه 1.2.0 محاسبه اشتباهی از سال کبیسه دارد:
- **سال 1403 یک سال کبیسه است** (اسفند 30 روزه)
- اما کتابخانه آن را 29 روزه در نظر می‌گیرد
- این باعث می‌شود تمام تاریخ‌های بعد از اسفند 1403 یک روز عقب باشند
- مثال: 26 مهر 1404 باید شنبه باشد، اما کتابخانه آن را جمعه نشان می‌دهد

## ✅ راه‌حل پیاده‌سازی شده

### 1️⃣ فایل تصحیح JavaScript ایجاد شد
فایل: `/static/js/persian-calendar-fix.js`

این فایل شامل:
- ✅ محاسبه صحیح سال کبیسه بر اساس چرخه 33 ساله
- ✅ تصحیح خودکار کتابخانه‌های persian-datepicker، moment-jalaali و persian-date
- ✅ توابع کمکی برای تبدیل تاریخ و محاسبه روز هفته
- ✅ قابلیت دیباگ برای بررسی صحت محاسبات

### 2️⃣ به‌روزرسانی تمام صفحات HTML
این فایل به **26 صفحه** اضافه شده است:

#### صفحات عملیات مالی:
- ✅ `financial_operations/invoice_settlement.html`
- ✅ `financial_operations/receive_from_customer.html`
- ✅ `financial_operations/pay_to_customer.html`
- ✅ `financial_operations/pay_to_bank.html`
- ✅ `financial_operations/receive_from_bank.html`
- ✅ `financial_operations/payment_to_cash.html`
- ✅ `financial_operations/payment_from_cash.html`
- ✅ `financial_operations/bank_transfer.html`
- ✅ `financial_operations/capital_investment.html`
- ✅ `financial_operations/cash_withdrawal.html`
- ✅ `financial_operations/operation_edit.html`

#### صفحات محصولات و چک‌ها:
- ✅ `products/sales_invoice.html`
- ✅ `products/purchase_invoice.html`
- ✅ `products/spent_cheques_list.html`
- ✅ `products/received_cheque_list.html`
- ✅ `products/received_cheque_edit.html`
- ✅ `products/all_issued_checks.html`
- ✅ `products/available_checks_for_deposit.html`

#### صفحات دیگر:
- ✅ `products/manager_order_list.html`
- ✅ `products/petty_cash.html`
- ✅ `products/fund_detail.html`
- ✅ `products/bank_account_detail.html`
- ✅ `products/financial_operation_list.html`
- ✅ `products/bank_statement.html`
- ✅ `products/reports/financial/base_report.html`

### 3️⃣ فایل Backend به‌روزرسانی شد
فایل: `/products/persian_calendar.py`
- ✅ توضیحات مشکل اضافه شد
- ✅ کتابخانه `jdatetime` (Python) محاسبه صحیح انجام می‌دهد ✓

## 🚀 دستورالعمل نصب و اجرا

### گام 1: بررسی فایل‌ها
تأیید کنید که فایل‌های زیر موجود هستند:
```bash
ls -la /workspace/static/js/persian-calendar-fix.js
ls -la /workspace/staticfiles/js/persian-calendar-fix.js
```

### گام 2: اجرای collectstatic (اگر نیاز است)
اگر از Django staticfiles استفاده می‌کنید:
```bash
cd /workspace
python manage.py collectstatic --noinput
```

### گام 3: ریستارت سرور
سرور Django را ریستارت کنید:
```bash
# اگر با runserver اجرا می‌کنید:
python manage.py runserver

# اگر با gunicorn:
sudo systemctl restart gunicorn

# یا:
pkill -f "python.*manage.py"
python manage.py runserver 0.0.0.0:8000
```

### گام 4: پاک کردن کش مرورگر
در مرورگر:
1. `Ctrl + Shift + Delete` (یا `Cmd + Shift + Delete` در Mac)
2. پاک کردن کش و Cookies
3. یا استفاده از `Ctrl + F5` برای Refresh کامل صفحه

## 🧪 تست تصحیح

### در Console مرورگر:
```javascript
// باز کردن Console: F12 یا Ctrl+Shift+I

// بررسی بارگذاری فایل:
console.log(window.PersianCalendarFix);

// تست سال کبیسه:
console.log("سال 1403 کبیسه است؟", PersianCalendarFix.isPersianLeapYear(1403)); // باید true برگرداند
console.log("اسفند 1403 چند روز دارد؟", PersianCalendarFix.getPersianMonthDays(1403, 12)); // باید 30 برگرداند

// تست تاریخ خاص:
console.log("26 مهر 1404 چه روزی است؟", PersianCalendarFix.getPersianWeekdayName(1404, 7, 26)); // باید "شنبه" برگرداند

// نمایش اطلاعات کامل:
PersianCalendarFix.debug();
```

### تست در صفحه تسویه فاکتور:
1. باز کردن صفحه: `http://192.168.1.150/accounting/invoice-settlement/`
2. کلیک روی فیلد تاریخ
3. رفتن به مهر 1404
4. بررسی کنید که 26 مهر زیر ستون "شنبه" باشد ✓

## 📊 جزئیات فنی

### الگوریتم سال کبیسه
تقویم شمسی از چرخه 33 ساله استفاده می‌کند:
- در هر 33 سال، 8 سال کبیسه وجود دارد
- سال‌های کبیسه در چرخه: **1، 5، 9، 13، 17، 22، 26، 30**

برای سال 1403:
```
1403 ÷ 33 = 42 باقی‌مانده 17
17 در لیست سال‌های کبیسه است → 1403 کبیسه است ✓
```

### محاسبه روز هفته
1. تبدیل تاریخ شمسی به میلادی
2. محاسبه روز هفته میلادی (0=Sunday)
3. تبدیل به روز هفته شمسی (0=Saturday)

## 🐛 عیب‌یابی

### اگر تقویم هنوز اشتباه است:

#### 1. بررسی بارگذاری فایل:
```javascript
// در Console:
console.log(window.PersianCalendarFix ? "✅ بارگذاری شد" : "❌ بارگذاری نشد");
```

#### 2. بررسی خطاها:
```javascript
// در Console → Network:
// فیلتر: persian-calendar-fix.js
// باید Status: 200 باشد
```

#### 3. بررسی ترتیب بارگذاری:
مطمئن شوید که فایل‌ها به این ترتیب بارگذاری می‌شوند:
```html
<!-- 1. jQuery -->
<script src="...jquery..."></script>

<!-- 2. persian-datepicker -->
<script src="...persian-datepicker.min.js"></script>

<!-- 3. فایل تصحیح ما (بعد از persian-datepicker) -->
<script src="{% static 'js/persian-calendar-fix.js' %}"></script>
```

#### 4. پاک کردن کامل کش:
```bash
# در مرورگر:
# Settings → Privacy → Clear browsing data
# یا استفاده از حالت Incognito/Private
```

## 📝 لیست تغییرات

| فایل | نوع تغییر | توضیحات |
|------|-----------|---------|
| `static/js/persian-calendar-fix.js` | ایجاد | فایل اصلی تصحیح |
| `staticfiles/js/persian-calendar-fix.js` | کپی | نسخه collectstatic |
| `products/persian_calendar.py` | به‌روزرسانی | اضافه شدن توضیحات |
| 26 فایل HTML | به‌روزرسانی | اضافه شدن script tag |

## ✅ نتیجه نهایی

بعد از اعمال این تصحیحات:
- ✅ اسفند 1403 به درستی 30 روزه نمایش داده می‌شود
- ✅ تمام تاریخ‌های بعد از اسفند 1403 با روز هفته درست تطابق دارند
- ✅ 26 مهر 1404 زیر ستون "شنبه" نمایش داده می‌شود (نه "جمعه")
- ✅ تمام محاسبات تاریخ در سیستم صحیح هستند

## 🔗 منابع

- [jdatetime - Python Persian Date](https://github.com/slashmili/python-jalali)
- [persian-datepicker](https://github.com/babakhani/pwt.datepicker)
- [moment-jalaali](https://github.com/jalaali/moment-jalaali)
- [الگوریتم تقویم شمسی](https://en.wikipedia.org/wiki/Solar_Hijri_calendar)

---

**تاریخ ایجاد:** 1404/07/27  
**آخرین به‌روزرسانی:** 1404/07/27  
**نسخه:** 1.0.0

در صورت بروز هرگونه مشکل، لطفاً به مستندات فوق مراجعه کنید یا با تیم پشتیبانی تماس بگیرید.
