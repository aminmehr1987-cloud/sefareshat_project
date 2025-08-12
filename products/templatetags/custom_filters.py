from django import template
from datetime import datetime, timezone
import jdatetime
from datetime import date
from django.contrib.humanize.templatetags.humanize import intcomma as humanize_intcomma

register = template.Library()

@register.filter
def timesince_in_days(value):
    if not value:
        return 0
    now = datetime.now(timezone.utc)
    delta = now - value
    return delta.days 

@register.filter
def mul(value, arg):
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return '' 
    

@register.filter
def multiply(value, arg):
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def format_number(value):
    """Format a number with thousand separator."""
    try:
        value = float(value)
        formatted = "{:,.0f}".format(value)
        return formatted.replace(',', '،')  # Replace English comma with Persian comma
    except (ValueError, TypeError):
        return value

@register.filter
def jformat(value, format_string):
    """Formats a date/datetime object into a Jalali date string."""
    if not value:
        return ''
    
    jalali_dt = None
    try:
        if isinstance(value, (jdatetime.datetime, jdatetime.date)):
            jalali_dt = value
        elif isinstance(value, datetime):
            jalali_dt = jdatetime.datetime.fromgregorian(datetime=value)
        elif isinstance(value, date):
            jalali_dt = jdatetime.date.fromgregorian(date=value)
        
        if jalali_dt:
            return jalali_dt.strftime(format_string)
    except (ValueError, TypeError, AttributeError):
        pass  # Fallback to returning the original value
        
    return str(value)

@register.filter
def persian_number_format(value):
    """
    فرمت کردن اعداد به صورت فارسی با کاما
    """
    if value is None:
        return "0"
    
    try:
        # تبدیل به عدد صحیح
        number = int(float(value))
        
        # فرمت کردن با کاما
        formatted = "{:,}".format(number)
        
        # تبدیل اعداد انگلیسی به فارسی
        persian_digits = {
            '0': '۰', '1': '۱', '2': '۲', '3': '۳', '4': '۴',
            '5': '۵', '6': '۶', '7': '۷', '8': '۸', '9': '۹'
        }
        
        for eng, per in persian_digits.items():
            formatted = formatted.replace(eng, per)
        
        return formatted
    except (ValueError, TypeError):
        return "0"

@register.filter
def jalali_date(value):
    """Converts a date/datetime object into a standard 'YYYY/MM/DD' Jalali date string."""
    if not value:
        return ''
    
    jalali_dt = None
    try:
        if isinstance(value, (jdatetime.datetime, jdatetime.date)):
            jalali_dt = value
        elif isinstance(value, datetime):
            jalali_dt = jdatetime.datetime.fromgregorian(datetime=value)
        elif isinstance(value, date):
            jalali_dt = jdatetime.date.fromgregorian(date=value)
        
        if jalali_dt:
            return jalali_dt.strftime("%Y/%m/%d")
    except (ValueError, TypeError, AttributeError):
        pass  # Fallback to returning the original value

    return str(value)

@register.filter
def jalali_date_time(value):
    """Converts a datetime object into a 'YYYY/MM/DD HH:MM' Jalali datetime string."""
    if not value:
        return ''
    
    jalali_dt = None
    try:
        if isinstance(value, jdatetime.datetime):
            jalali_dt = value
        elif isinstance(value, datetime):
            jalali_dt = jdatetime.datetime.fromgregorian(datetime=value)
        
        if jalali_dt:
            return jalali_dt.strftime("%Y/%m/%d %H:%M")
    except (ValueError, TypeError, AttributeError):
        pass

    return str(value)

@register.filter
def intcomma(value):
    """Format a number with thousand separator."""
    return humanize_intcomma(value)
    
    try:
        # تبدیل به عدد صحیح
        number = int(float(value))
        
        # فرمت کردن با کاما
        formatted = "{:,}".format(number)
        
        # تبدیل اعداد انگلیسی به فارسی
        persian_digits = {
            '0': '۰', '1': '۱', '2': '۲', '3': '۳', '4': '۴',
            '5': '۵', '6': '۶', '7': '۷', '8': '۸', '9': '۹'
        }
        
        for eng, per in persian_digits.items():
            formatted = formatted.replace(eng, per)
        
        return formatted
    except (ValueError, TypeError):
        return "0"