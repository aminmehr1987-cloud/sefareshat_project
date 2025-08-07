from django import template
from datetime import datetime, timezone
import jdatetime
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
    """Format datetime objects to Jalali/Persian date format."""
    if not value:
        return ''
    
    try:
        # Convert to Jalali datetime
        if isinstance(value, datetime):
            jalali_date = jdatetime.datetime.fromgregorian(datetime=value)
        else:
            # If it's already a date object
            jalali_date = jdatetime.date.fromgregorian(date=value)
        
        # Format the Jalali date
        return jalali_date.strftime(format_string)
    except (ValueError, TypeError, AttributeError):
        # Fallback to original value if conversion fails
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
    """Convert Gregorian date to Jalali date format."""
    if not value:
        return ''
    
    try:
        # Convert to Jalali date
        if isinstance(value, datetime):
            jalali_date = jdatetime.datetime.fromgregorian(datetime=value)
        else:
            # If it's already a date object
            jalali_date = jdatetime.date.fromgregorian(date=value)
        
        # Format the Jalali date as Y/m/d
        return jalali_date.strftime("%Y/%m/%d")
    except (ValueError, TypeError, AttributeError):
        # Fallback to original value if conversion fails
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