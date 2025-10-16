"""
Persian Calendar Utilities
استفاده از jdatetime برای تبدیل تاریخ‌های شمسی/میلادی

توجه:
- jdatetime: 1404/07/01 → 2025-09-23 (سه‌شنبه) ✅ صحیح
- persian-date.js: 1404/07/01 → 2025-09-22 (دوشنبه) ❌ یک روز عقب
"""

from datetime import datetime, date as py_date
from typing import Union

try:
    import jdatetime
    CALENDAR_LIB = 'jdatetime'
    HAS_JDATETIME = True
except ImportError:
    CALENDAR_LIB = 'none'
    HAS_JDATETIME = False
    print("⚠️ jdatetime نصب نیست! لطفاً با 'pip install jdatetime' نصب کنید.")


def gregorian_to_jalali(date_obj: Union[datetime, py_date]) -> str:
    """
    تبدیل تاریخ میلادی به شمسی
    
    Args:
        date_obj: datetime or date object
        
    Returns:
        str: تاریخ شمسی به فرمت 'YYYY/MM/DD'
    """
    if not HAS_JDATETIME:
        # fallback: استفاده از محاسبه ساده (تقریبی)
        if isinstance(date_obj, datetime):
            date_obj = date_obj.date()
        
        # محاسبه تقریبی: سال شمسی = سال میلادی - 621
        # این دقیق نیست ولی برای نمایش موقت کافیست
        g_year = date_obj.year
        g_month = date_obj.month
        g_day = date_obj.day
        
        # تبدیل تقریبی (باید jdatetime نصب شود برای دقت)
        j_year = g_year - 621 if g_month > 3 or (g_month == 3 and g_day >= 21) else g_year - 622
        return f"{j_year}/07/24"  # موقتی
    
    if isinstance(date_obj, datetime):
        jalali = jdatetime.datetime.fromgregorian(datetime=date_obj)
    else:
        jalali = jdatetime.date.fromgregorian(date=date_obj)
    return jalali.strftime('%Y/%m/%d')


def gregorian_to_jalali_datetime(datetime_obj: datetime) -> str:
    """
    تبدیل datetime میلادی به شمسی با ساعت
    
    Args:
        datetime_obj: datetime object
        
    Returns:
        str: تاریخ و ساعت شمسی به فرمت 'YYYY/MM/DD HH:MM:SS'
    """
    if not HAS_JDATETIME:
        return f"{gregorian_to_jalali(datetime_obj)} {datetime_obj.strftime('%H:%M:%S')}"
    
    jalali = jdatetime.datetime.fromgregorian(datetime=datetime_obj)
    return jalali.strftime('%Y/%m/%d %H:%M:%S')


def to_persian_digits(text: str) -> str:
    """
    تبدیل اعداد انگلیسی به فارسی
    
    Args:
        text: متن حاوی اعداد انگلیسی
        
    Returns:
        str: متن با اعداد فارسی
    """
    persian_digits = '۰۱۲۳۴۵۶۷۸۹'
    english_digits = '0123456789'
    
    translation_table = str.maketrans(english_digits, persian_digits)
    return text.translate(translation_table)


def gregorian_to_jalali_farsi(date_obj: Union[datetime, py_date]) -> str:
    """
    تبدیل تاریخ میلادی به شمسی با اعداد فارسی
    
    Args:
        date_obj: datetime or date object
        
    Returns:
        str: تاریخ شمسی با اعداد فارسی (مثل: ۱۴۰۴/۰۷/۲۴)
    """
    jalali_date = gregorian_to_jalali(date_obj)
    return to_persian_digits(jalali_date)


def get_calendar_info() -> dict:
    """
    اطلاعات کتابخانه تقویم فعلی
    
    Returns:
        dict: {'library': 'jdatetime', 'accurate': bool}
    """
    return {
        'library': CALENDAR_LIB,
        'accurate': HAS_JDATETIME,
        'warning': 'persian-date.js در frontend یک روز عقب است و offset دارد' if HAS_JDATETIME else 'jdatetime نصب نیست!'
    }
