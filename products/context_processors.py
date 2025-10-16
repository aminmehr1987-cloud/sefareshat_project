# products/context_processors.py
from .models import Order, Notification
from django.db.models import Count
from django.utils import timezone
import jdatetime

def recent_orders_processor(request):
    recent_orders_count = 0
    if request.user.is_authenticated:
        # اصلاح فیلتر: از customer__created_by استفاده کنید
        recent_orders_count = Order.objects.filter(customer__created_by=request.user).order_by('-created_at')[:5].count()
    return {'recent_orders_count': recent_orders_count}

def notifications_processor(request):
    if request.user.is_authenticated and request.user.groups.filter(name='مدیر').exists():
        unread_notifications = Notification.objects.filter(target_user=request.user, read=False).order_by('-created_at')
        return {'unread_notifications': unread_notifications}
    return {'unread_notifications': []}

def server_datetime_processor(request):
    """
    اضافه کردن تاریخ و ساعت سرور به تمام template ها
    """
    now = timezone.now()
    server_date = now.date()
    server_time = now.time()
    
    # تبدیل به شمسی
    jalali_now = jdatetime.datetime.fromgregorian(datetime=now)
    
    return {
        'server_now': now,
        'server_date': server_date.strftime('%Y-%m-%d'),
        'server_time': server_time.strftime('%H:%M:%S'),
        'server_datetime_jalali': jalali_now.strftime('%Y/%m/%d %H:%M:%S'),
        'server_date_jalali': jalali_now.strftime('%Y/%m/%d'),
        'server_time_jalali': jalali_now.strftime('%H:%M:%S'),
    }