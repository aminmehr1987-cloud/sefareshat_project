# products/context_processors.py
from .models import Order, Notification
from django.db.models import Count

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