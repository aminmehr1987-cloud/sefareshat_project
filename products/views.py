from sefareshat_project.utils import normalize_text
from django.http import JsonResponse, HttpResponseRedirect, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.db.models import Count, Q, F, Sum
import pandas as pd
from django.utils import timezone
import jdatetime
import json
from .forms import UploadExcelForm, OrderForm
from .models import Product, Warehouse, Order, OrderItem, DocumentNumber, Customer, OrderStatusHistory, Shipment, ShipmentItem, PriceChange, PurchaseInvoice, PurchaseInvoiceItem, AccountingReport, AccountingReportDetail, SalesInvoice

from django.conf import settings
import logging
import subprocess
import os
from django.http import Http404
from django.db import IntegrityError, transaction
from django.contrib.auth.models import User, Group
from .forms import CustomerForm
from products.models import Notification
from django.core.paginator import Paginator
from datetime import timedelta
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView
from .models import FinancialYear, Currency, Receipt
from .forms import FinancialYearForm, CurrencyForm, ReceiptForm
from .models import Fund, FinancialOperation, CustomerBalance, PettyCashOperation
from .forms import FundForm, FinancialOperationForm, PettyCashOperationForm, ReceiveFromCustomerForm, PayToCustomerForm, BankOperationForm, BankTransferForm, CashOperationForm, CapitalInvestmentForm, IssueCheckForm
from functools import wraps
from decimal import Decimal
from .forms import BankAccountForm
from .models import Account, BankAccount, ReceivedCheque, CheckBook, Check
from .forms import ReceivedChequeStatusChangeForm, ReceivedChequeEditForm, IssuedCheckEditForm



logger = logging.getLogger(__name__)


@login_required
def order_confirmation(request):
    """
    نمایش صفحه تایید نهایی سفارش یا نمایش سفارش برای چاپ
    """
    try:
        order_id = request.GET.get('order_id')
        is_print_view = bool(order_id)
        
        if is_print_view:
            # Logic for printing an existing order for managers
            # Only managers should be able to access this view by order_id
            if not request.user.groups.filter(name='مدیر').exists():
                messages.error(request, 'شما اجازه دسترسی به این صفحه را ندارید.')
                return redirect('products:login')
            
            order = get_object_or_404(Order.objects.prefetch_related('items__product'), id=order_id)
            customer = order.customer

        else:
            # Existing logic for visitors/customers confirming their cart
            customer = None
            if hasattr(request.user, 'customer_profile'):
                customer = request.user.customer_profile
            elif request.user.groups.filter(name='ویزیتور').exists():
                customer_id = request.GET.get('customer_id') or request.session.get('selected_customer_id')
                if customer_id:
                    try:
                        customer = Customer.objects.get(id=customer_id)
                    except Customer.DoesNotExist:
                        messages.error(request, 'مشتری مورد نظر یافت نشد')
                        return redirect('products:product_list')
            
            if not customer:
                messages.error(request, 'مشتری یافت نشد')
                return redirect('products:product_list')

            order = Order.objects.filter(
                customer=customer,
                status='cart'
            ).prefetch_related('items__product').first()

        if not order or not order.items.exists():
            message = 'سفارش یافت نشد.' if is_print_view else 'سبد خرید شما خالی است.'
            messages.error(request, message)
            if request.user.groups.filter(name='مدیر').exists():
                return redirect('products:manager_order_list')
            return redirect('products:product_list')

        # محاسبه مجموع قیمت برای هر آیتم و کل سفارش
        order_items = []
        total_amount = 0
        for item in order.items.all():
            # For confirmed orders, use allocated_quantity, otherwise requested_quantity
            quantity = item.allocated_quantity if order.status not in ['cart', 'pending'] and item.allocated_quantity is not None else item.requested_quantity
            item_total = item.price * quantity
            total_amount += item_total
            order_items.append({
                'product': item.product,
                'quantity': quantity,
                'price': item.price,
                'total': item_total,
                'order_item_id': item.id,
                'payment_term': item.payment_term
            })

        context = {
            'customer': customer,
            'order': order,
            'order_items': order_items,
            'total_amount': total_amount,
            'is_print_view': is_print_view,
        }
        
        return render(request, 'products/order_confirmation.html', context)

    except Exception as e:
        import traceback
        traceback.print_exc()
        messages.error(request, f'خطا در نمایش صفحه تایید سفارش: {str(e)}')
        if request.user.groups.filter(name='مدیر').exists():
            return redirect('products:manager_order_list')
        return redirect('products:product_list')


@login_required
@require_POST
def confirm_order(request):
    """
    تایید نهایی سفارش و تغییر وضعیت آن
    """
    try:
        order_id = request.POST.get('order_id')
        if not order_id:
            messages.error(request, 'شناسه سفارش نامعتبر است')
            return redirect('products:product_list')

        order = Order.objects.filter(
            id=order_id,
            status='cart'
        ).first()

        if not order:
            messages.error(request, 'سفارش یافت نشد یا قبلاً تایید شده است')
            return redirect('products:product_list')

        # تغییر وضعیت سفارش به 'pending'
        order.status = 'pending'
        order.order_date = timezone.now()
        order.save()

        messages.success(request, 'سفارش شما با موفقیت ثبت شد')
        # Instead of redirecting, we will render the same page with a success flag
        # The template will handle showing the notification and hiding the form.
        context = {
            'success': True,
            'order_id': order.id
        }
        return render(request, 'products/order_confirmation.html', context)

    except Exception as e:
        messages.error(request, f'خطا در تایید سفارش: {str(e)}')
        return redirect('products:product_list')




@login_required
@require_POST
def update_shipment_status(request, shipment_id):
    """
    به‌روزرسانی وضعیت یک ارسال
    """
    shipment = get_object_or_404(Shipment, id=shipment_id)
    
    try:
        if shipment.status == 'in_transit':
            shipment.status = 'delivered'
            shipment.save()
            
            # به‌روزرسانی وضعیت سفارش مرتبط
            order = shipment.order
            if all(s.status == 'delivered' for s in order.shipments.all()):
                order.status = 'delivered'
                order.save()
            
            messages.success(request, 'وضعیت ارسال با موفقیت به‌روزرسانی شد.')
        else:
            messages.error(request, 'تغییر وضعیت فقط برای ارسال‌های در حال ارسال ممکن است.')
            
        return redirect('products:order_detail_view', order_id=shipment.order.id)
        
    except Exception as e:
        messages.error(request, f'خطا در به‌روزرسانی وضعیت: {str(e)}')
        return redirect('products:order_detail_view', order_id=shipment.order.id)

def get_shipped_orders():
    """
    دریافت لیست سفارش‌های ارسال شده
    """
    return Order.objects.filter(
        Q(status='delivered') &
        (Q(parent_order__isnull=True) | Q(id__in=Shipment.objects.filter(
            parent_order__isnull=False,
            status='delivered'
        ).values('order_id')))
    ).distinct()

from .models import Courier

@login_required
@transaction.atomic
def create_shipment_for_order(request, order_id):
    """
    ایجاد یک ارسال جدید برای سفارش و زیرسفارش‌های آن
    """
    logger.info(f"[SHIPMENT_CREATE] Starting create_shipment_for_order for order_id: {order_id}")
    order = get_object_or_404(Order, id=order_id)
    parent_order = order.parent_order if order.parent_order else order
    couriers = Courier.objects.filter(is_active=True)

    if request.method == 'POST':
        courier_id = request.POST.get('courier')
        description = request.POST.get('description', '')
        selected_sub_orders = request.POST.getlist('selected_sub_orders', [])

        if not courier_id:
            messages.error(request, 'پیک الزامی است.')
            return redirect('products:order_detail_view', order_id=order.id)

        try:
            courier = Courier.objects.get(id=courier_id)
        except Courier.DoesNotExist:
            messages.error(request, 'پیک انتخاب شده معتبر نیست.')
            return redirect('products:order_detail_view', order_id=order.id)

        try:
            # بررسی وجود ارسال قبلی برای سفارش اصلی
            if Shipment.objects.filter(order=parent_order).exists():
                messages.error(request, 'برای این سفارش قبلاً یک ارسال ثبت شده است.')
                return redirect('products:order_detail_view', order_id=order.id)

            # 1. ایجاد یک Shipment واحد برای سفارش اصلی
            new_shipment = Shipment.objects.create(
                order=parent_order,
                parent_order=parent_order,
                courier=courier,
                description=description,
                status='in_transit',
                is_backorder=order.order_number.startswith('BO-')
            )
            logger.info(f"[SHIPMENT_CREATE] Created Shipment object with id: {new_shipment.id} and number: {new_shipment.shipment_number}")

            # 2. جمع‌آوری آیتم‌های آماده ارسال از سفارش‌های انتخاب شده
            sub_orders_to_process = []
            if selected_sub_orders:
                sub_orders_to_process = Order.objects.filter(
                    id__in=selected_sub_orders,
                    parent_order=parent_order
                )
            else:
                sub_orders_to_process = [order]
            
            items_added = False
            for sub_order in sub_orders_to_process:
                logger.info(f"[SHIPMENT_CREATE] Processing sub_order with id: {sub_order.id} for shipment: {new_shipment.id}")
                # بررسی وجود ارسال قبلی برای زیرسفارش
                if Shipment.objects.filter(order=sub_order).exists():
                    continue  # رد کردن این زیرسفارش و رفتن به زیرسفارش بعدی

                order_items_to_ship = sub_order.items.filter(warehouse_status='ready')
                
                if order_items_to_ship.exists():
                    new_shipment.sub_orders.add(sub_order)
                    logger.info(f"[SHIPMENT_CREATE] Added sub_order {sub_order.id} to shipment {new_shipment.id}")
                    
                    for item in order_items_to_ship:
                        shipment_item = ShipmentItem.objects.create(
                            shipment=new_shipment,
                            order_item=item,
                            quantity_shipped=item.allocated_quantity
                        )
                        logger.info(f"[SHIPMENT_CREATE] Created ShipmentItem with id: {shipment_item.id} linking shipment {new_shipment.id} to OrderItem {item.id}")
                        item.warehouse_status = 'shipped'
                        item.save()
                        items_added = True

            if not items_added:
                messages.error(request, 'هیچ کالای آماده ارسالی وجود ندارد.')
                new_shipment.delete()
                logger.warning(f"[SHIPMENT_CREATE] No items were added to shipment {new_shipment.id}, so it was deleted.")
                return redirect('products:order_detail_view', order_id=order.id)

            # 3. به‌روزرسانی وضعیت سفارش‌ها
            for sub_order in sub_orders_to_process:
                if all(item.warehouse_status == 'shipped' for item in sub_order.items.all()):
                    sub_order.status = 'delivered'
                    sub_order.save()

            # بررسی وضعیت همه زیرسفارش‌های سفارش اصلی
            all_sub_orders = Order.objects.filter(parent_order=parent_order)
            if all(sub.status == 'delivered' for sub in all_sub_orders):
                parent_order.status = 'delivered'
                parent_order.save()

            messages.success(
                request, 
                f'ارسال جدید با شماره پیگیری {new_shipment.shipment_number} با موفقیت ثبت شد.'
            )
            return redirect('products:order_detail_view', order_id=order.id)

        except IntegrityError:
            messages.error(request, 'خطا در ثبت ارسال: این سفارش قبلاً ارسال شده است.')
            return redirect('products:order_detail_view', order_id=order.id)
        except Exception as e:
            logger.error(f"[SHIPMENT_CREATE] Exception in create_shipment_for_order: {str(e)}", exc_info=True)
            messages.error(request, f'خطا در ثبت ارسال: {str(e)}')
            return redirect('products:order_detail_view', order_id=order.id)

    available_sub_orders = Order.objects.filter(
        Q(id=order.id) | Q(parent_order=parent_order),
        items__warehouse_status='ready'
    ).distinct()

    return render(request, 'products/create_shipment.html', {
        'order': order,
        'available_sub_orders': available_sub_orders,
        'couriers': couriers
    })

@csrf_exempt
@login_required
@require_POST
@transaction.atomic
def submit_allocation(request):
    try:
        data = json.loads(request.body)
        backorder_id = data.get('order_id')
        items_data = data.get('items', [])
        document_number = data.get('document_number')  # دریافت شماره سند
        package_count = data.get('package_count')      # دریافت تعداد بسته

        if not backorder_id or not items_data or not document_number or not package_count:
            return JsonResponse({
                'success': False,
                'message': 'اطلاعات ناقص است'
            }, status=400)

        backorder = get_object_or_404(Order, id=backorder_id)
        allocated_items = []

        with transaction.atomic():
            for item_info in items_data:
                item_id = item_info.get('item_id')
                allocated_qty = int(item_info.get('quantity', 0))
                price = int(item_info.get('price', 0))

                backorder_item = get_object_or_404(OrderItem, id=item_id, order=backorder)

                if allocated_qty > backorder_item.requested_quantity:
                    return JsonResponse({'success': False, 'message': f'مقدار تخصیص برای کالای "{backorder_item.product.name}" بیشتر از تعداد مورد نیاز است.'}, status=400)

                backorder_item.requested_quantity = F('requested_quantity') - allocated_qty
                allocated_items.append({
                    'product': backorder_item.product,
                    'quantity': allocated_qty,
                    'price': price,
                    'payment_term': backorder_item.payment_term,
                    'warehouse': backorder_item.warehouse,
                })

                backorder_item.save()
                backorder_item.refresh_from_db()

                if backorder_item.requested_quantity == 0:
                    backorder_item.delete()

                if not backorder.items.exists():
                    backorder.delete()
                    
            if not allocated_items:
                return JsonResponse({'success': False, 'message': 'هیچ تخصیصی انجام نشد.'}, status=400)

            parent_order = backorder.parent_order if backorder.parent_order else backorder

            # گروه‌بندی آیتم‌ها بر اساس انبار
            items_by_warehouse = {}
            for entry in allocated_items:
                warehouse_name = entry['warehouse'].name if entry['warehouse'] else None
                if warehouse_name not in items_by_warehouse:
                    items_by_warehouse[warehouse_name] = []
                items_by_warehouse[warehouse_name].append(entry)

            created_orders = []
            for warehouse_name, items in items_by_warehouse.items():
                if warehouse_name == "انبار فروشگاه":
                    warehouse_code = "SHOP"
                elif warehouse_name == "انبار پخش":
                    warehouse_code = "PAKHSH"
                else:
                    warehouse_code = "OTHER"

                parent_order = backorder.parent_order if backorder.parent_order else backorder
                parent_order_number = parent_order.order_number   

                prefix = f"BO-{warehouse_code}-{parent_order_number}"
                allocation_count = Order.objects.filter(
                    parent_order=parent_order,
                    order_number__startswith=f"{prefix}-",
                    order_number__endswith='-TAMIN'
                ).count() + 1

                new_order_number = f"{prefix}-{str(allocation_count).zfill(4)}-TAMIN"

                new_order = Order(
                    customer=backorder.customer,
                    visitor_name=backorder.visitor_name,
                    payment_term=backorder.payment_term,
                    status='waiting_for_customer_shipment',
                    parent_order=parent_order,
                    order_number=new_order_number,
                    document_number=document_number,
                    package_count=package_count
                )
                new_order.save()
                created_orders.append(new_order)

                for entry in items:
                    OrderItem.objects.create(
                        order=new_order,
                        product=entry['product'],
                        requested_quantity=entry['quantity'],
                        allocated_quantity=entry['quantity'],
                        price=entry['price'],
                        payment_term=entry['payment_term'],
                        warehouse=entry['warehouse'],
                        warehouse_status='ready'
                    )
                created_orders.append(new_order)

        return JsonResponse({'success': True, 'message': 'تخصیص‌ها با موفقیت ثبت شدند.'})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': f'خطا در پردازش تخصیص: {str(e)}'}, status=500)



@login_required
def order_list_view(request):
    is_manager = request.user.groups.filter(name='مدیر').exists()
    if is_manager:
        orders = Order.objects.all().order_by('-created_at')
    else:
        orders = Order.objects.filter(visitor_name=request.user.username).order_by('-created_at')

    # افزودن مقدار total_price به هر سفارش (دینامیک و موقت)
    for order in orders:
        if order.status in ['pending', 'warehouse', 'parent']:
            order.total_price = sum(item.price * (item.requested_quantity or 0) for item in order.items.all())
        else:
            order.total_price = sum(item.price * (item.allocated_quantity or 0) for item in order.items.all())

    context = {
        'orders': orders,
        'is_manager': is_manager,
    }
    return render(request, 'products/order_list.html', context)


@login_required
def order_detail_view(request, order_id):
    """
    نمایش جزئیات سفارش.
    فقط کاربر ایجاد کننده سفارش و مدیران سیستم می‌توانند به این صفحه دسترسی داشته باشند.
    """
    order = get_object_or_404(Order, id=order_id)

    # بررسی دسترسی کاربر
    is_manager = request.user.groups.filter(name='مدیر').exists()
    is_accounting = request.user.groups.filter(name='حسابداری').exists()
    is_order_creator = (order.visitor_name == request.user.username)

    if not (is_manager or is_order_creator or is_accounting):
        messages.error(request, 'شما اجازه دسترسی به این سفارش را ندارید.')
        return redirect('products:product_list')

    # دریافت ارسال‌ها همراه با اقلام ارسالی
    shipments = order.shipments.all().prefetch_related(
        'items',  # برای ShipmentItem ها
        'items__order_item',  # برای دسترسی به OrderItem های مرتبط
        'items__order_item__product'  # برای دسترسی به محصولات
    )

    # Check if the order is "finalized"
    is_finalized = order.status in ['completed', 'delivered'] or shipments.filter(status='delivered').exists()

    if is_finalized:
        # If so, filter shipments to show only 'in_transit' and 'delivered'
        shipments = shipments.filter(status__in=['in_transit', 'delivered'])

    # --- محاسبه مبلغ کل مرحله ---
    # The total is calculated based on the most relevant quantity field depending on the order's progress.
    # 1. delivered_quantity: If available, it's the most accurate value for finalized orders.
    # 2. requested_quantity: For early-stage orders (pending, warehouse, backorder, cart).
    # 3. allocated_quantity: For orders processed by the warehouse but not yet delivered.
    stage_total = 0
    for item in order.items.all():
        quantity = 0
        # Priority 1: Use delivered quantity if available (most accurate for final totals)
        if item.delivered_quantity is not None:
            quantity = item.delivered_quantity
        # Priority 2: Use requested quantity for orders not yet processed by warehouse
        elif order.status in ['pending', 'warehouse', 'parent', 'backorder', 'cart']:
            quantity = item.requested_quantity or 0
        # Priority 3: Use allocated quantity for orders processed by warehouse but not yet delivered
        else:
            quantity = item.allocated_quantity or 0
        
        stage_total += (item.price or 0) * quantity

    # --- منطق دکمه بازگشت ---
    referer = request.META.get('HTTP_REFERER')
    # اگر کاربر از پنل حسابداری آمده، به همان صفحه بازگردد
    if referer and '/accounting/' in referer:
        back_url = referer
        back_text = "بازگشت به صورتحساب"
    # اگر کاربر مدیر است، به لیست سفارشات مدیر بازگردد
    elif is_manager:
        back_url = reverse('products:manager_order_list')
        back_text = "بازگشت به لیست سفارشات مدیر"
    # در غیر این صورت (ویزیتور)، به لیست سفارشات خودش بازگردد
    else:
        back_url = reverse('products:order')
        back_text = "بازگشت به لیست سفارشات"
    # ------------------------

    # Check if a final sales invoice exists for this order
    has_final_invoice = FinancialOperation.objects.filter(
        operation_type='SALES_INVOICE',
        description__icontains=f"سفارش شماره {order.order_number}"
    ).exists()

    context = {
        'order': order,
        'order_items': order.items.all(),
        'shipments': shipments,
        'stage_total': stage_total,
        'back_url': back_url,
        'back_text': back_text,
        'has_final_invoice': has_final_invoice,
    }
    return render(request, 'products/order_detail.html', context)

@login_required
@user_passes_test(lambda u: u.groups.filter(name='ویزیتور').exists())
def add_customer(request):
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.created_by = request.user
            customer.save()
            messages.success(request, 'مشتری با موفقیت اضافه شد.')
            return redirect('dashboard')  # یا هرجایی که لازمه برگرده
    else:
        form = CustomerForm()

    return render(request, 'products/add_customer.html', {'form': form})

@login_required
def create_customer(request):
    if not request.user.groups.filter(name='ویزیتور').exists():
        return render(request, 'error.html', {'message': 'دسترسی غیرمجاز'})

    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            try:
                customer = form.save(commit=False)
                customer.created_by = request.user
                customer.save()
                messages.success(request, 'مشتری جدید با موفقیت ایجاد شد.')
                form = CustomerForm()  # Reset form on success
                return render(request, 'products/create_customer.html', {'form': form, 'success': True})
            except Exception as e:
                messages.error(request, f'خطا در ثبت مشتری: {str(e)}')
                print(f"Error saving customer: {str(e)}")  # For debugging
        else:
            print(f"Form errors: {form.errors}")  # For debugging
    else:
        form = CustomerForm()

    return render(request, 'products/create_customer.html', {'form': form})


@login_required
def get_counties(request):
    """API endpoint برای دریافت لیست شهرستان‌ها"""
    from django.http import JsonResponse
    from .models import County
    
    counties = County.objects.select_related('province').values('id', 'name', 'province_id')
    return JsonResponse(list(counties), safe=False)


@csrf_exempt
@login_required
@require_POST
@transaction.atomic
def send_order_to_warehouse(request, order_id):
    try:
        # دریافت سفارش اصلی
        original_order = get_object_or_404(Order, id=order_id)
        created_orders = []  # Initialize the list here

        if original_order.status != 'pending':
            return JsonResponse({
                'success': False,
                'message': 'فقط سفارشات در انتظار تایید قابل ارسال به انبار هستند.'
            }, status=400)

        # اعتبارسنجی: بررسی وجود انبار برای همه آیتم‌ها
        for item in original_order.items.all():
            if not item.warehouse:
                return JsonResponse({
                    'success': False,
                    'message': f"کالای '{item.product.name}' انبار مشخصی ندارد. لطفاً ابتدا انبار کالا را در بخش محصولات مشخص کنید."
                }, status=400)

        # گروه‌بندی آیتم‌ها بر اساس انبار
        items_by_warehouse = {}
        for item in original_order.items.all():
            warehouse_name = item.warehouse.name
            if warehouse_name not in items_by_warehouse:
                items_by_warehouse[warehouse_name] = []
            items_by_warehouse[warehouse_name].append(item)

        # ابتدا وضعیت سفارش اصلی را به parent تغییر می‌دهیم
        original_order.status = 'parent'
        original_order.save()

        # ایجاد سفارشات جدید برای هر انبار
        for warehouse_name, items in items_by_warehouse.items():
            # ایجاد یک سفارش جدید برای هر انبار
            new_order = Order()
            new_order.visitor_name = original_order.visitor_name
            new_order.customer = original_order.customer
            new_order.payment_term = original_order.payment_term
            new_order.status = 'warehouse'
            new_order.parent_order = original_order
            new_order.warehouse_name = warehouse_name  # تنظیم نام انبار برای تولید شماره سفارش
            new_order.save()

            # ایجاد آیتم‌های سفارش جدید
            for item in items:
                OrderItem.objects.create(
                    order=new_order,
                    product=item.product,
                    requested_quantity=item.requested_quantity,  # 👈 مقدار درخواست شده از سفارش مادر
                    allocated_quantity=item.requested_quantity,  # 👈 در این مرحله همه درخواست‌ها تخصیص‌یافته فرض می‌شوند
                    price=item.price,
                    payment_term=item.payment_term,
                    warehouse=item.warehouse,
                    warehouse_status='pending'
                )
            created_orders.append(new_order)

        return JsonResponse({
            'success': True,
            'message': 'سفارش با موفقیت به انبارها ارسال شد و سفارشات جدید ایجاد گردید.'
        })

    except Order.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'سفارش یافت نشد.'
        }, status=404)
    except Exception as e:
        logging.error(f"Error in send_order_to_warehouse: {e}")
        return JsonResponse({
            'success': False,
            'message': f"خطا در ارسال سفارش به انبار: {e}"
        }, status=500)
    
@login_required
def group_by_order_items(queryset):
    grouped_orders = {}
    for item in queryset:
        order_id = item.order.id
        if order_id not in grouped_orders:
            grouped_orders[order_id] = {
                'order': item.order,
                'items': [],
                'total_price': 0, 
            }
        grouped_orders[order_id]['items'].append(item)
        # مطمئن شوید که price و requested_quantity در OrderItem موجود است
        grouped_orders[order_id]['total_price'] += item.price * item.requested_quantity 
    # برای نمایش در HTML، لیست مقادیر را برمی‌گردانیم
    # می‌توانید اینجا sort کنید، مثلاً بر اساس تاریخ ایجاد سفارش
    return sorted(list(grouped_orders.values()), key=lambda x: x['order'].created_at, reverse=True)


def group_required(group_name):
    """
    Custom decorator to check if a user belongs to a specific group.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if request.user.groups.filter(name=group_name).exists():
                return view_func(request, *args, **kwargs)
            else:
                messages.error(request, "You do not have permission to access this page.")
                return redirect('products:login')
        return _wrapped_view
    return decorator

@login_required
@group_required('حسابداری')
@require_POST
def spend_received_check_view(request):
    try:
        data = json.loads(request.body)
        check_ids = data.get('check_ids')
        customer_id = data.get('customer_id')

        if not check_ids or not isinstance(check_ids, list):
            return JsonResponse({'success': False, 'message': 'لیست شناسه‌های چک نامعتبر است.'}, status=400)

        # Use a shorter transaction to avoid database locks
        with transaction.atomic():
            # Lock the checks for update to prevent race conditions
            checks = ReceivedCheque.objects.select_for_update().filter(id__in=check_ids, status='RECEIVED')
            
            if len(checks) != len(check_ids):
                return JsonResponse({'success': False, 'message': 'یک یا چند چک یافت نشد یا وضعیت آن‌ها برای خرج کردن مناسب نیست.'}, status=404)

            customer = get_object_or_404(Customer, id=customer_id)
            
            total_amount = sum(check.amount for check in checks)
            check_serials = ", ".join(check.serial for check in checks)

            # Update all checks at once with recipient name
            checks.update(status='SPENT', recipient_name=customer.get_full_name())
            
            # Create a single financial operation for the total amount
            operation = FinancialOperation.objects.create(
                operation_type='PAY_TO_CUSTOMER',
                customer=customer,
                amount=total_amount,
                payment_method='spend_cheque',  # Changed to spend_cheque to match the template logic
                date=timezone.now().date(),
                description=f"خرج {len(checks)} فقره چک دریافتی به شماره سریال‌های {check_serials} به {customer.get_full_name()}",
                created_by=request.user,
                status='CONFIRMED',
                confirmed_by=request.user,
                confirmed_at=timezone.now()
            )
            
            # Link the spent cheques to the operation
            operation.spent_cheques.set(checks)

        return JsonResponse({
            'success': True, 
            'message': f'{len(checks)} فقره چک دریافتی با مبلغ {total_amount:,} ریال با موفقیت خرج شد.',
            'operation_id': operation.id
        })

    except Customer.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'مشتری یافت نشد.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'خطا در خرج چک: {str(e)}'}, status=500)

@login_required
@group_required('حسابداری')
def accounting_panel(request):
    """
    Displays the accounting panel, accessible only to users in the 'accounting' group.
    """
    return render(request, 'products/accounting_panel.html')

@login_required
@group_required('حسابداری')
def invoice_registration_view(request):
    """
    Renders the invoice registration pop-up.
    """
    return render(request, 'products/invoice_registration.html')


@login_required
@group_required('حسابداری')
def purchase_invoice_view(request):
    """
    Renders the purchase invoice page and handles invoice registration.
    """
    import jdatetime
    from django.contrib import messages
    today = jdatetime.date.today().strftime("%Y/%m/%d")
    customers = Customer.objects.all()

    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Get invoice fields
                customer_id = request.POST.get('customer_id')
                invoice_number = request.POST.get('invoice_number')
                invoice_date = request.POST.get('invoice_date')
                description = request.POST.get('description', '')
                customer = Customer.objects.get(id=customer_id)
                # Calculate total amount
                product_codes = request.POST.getlist('product_code')
                quantities = request.POST.getlist('quantity')
                prices = request.POST.getlist('price')
                discounts = request.POST.getlist('discount')
                profit_percentages = request.POST.getlist('profit_percentage')
                descriptions = request.POST.getlist('description')
                totals = request.POST.getlist('total')
                total_amount = 0
                for t in totals:
                    try:
                        total_amount += int(str(t).replace(',', ''))
                    except Exception:
                        pass
                # Create invoice
                invoice = PurchaseInvoice.objects.create(
                    invoice_number=invoice_number,
                    invoice_date=invoice_date,
                    customer=customer,
                    created_by=request.user,
                    total_amount=total_amount,
                    description=description,
                    status='registered',
                )
                # Create invoice items
                for i, code in enumerate(product_codes):
                    try:
                        product = Product.objects.get(code=code)
                        qty = int(quantities[i]) if i < len(quantities) and quantities[i] else 0
                        price = int(prices[i]) if i < len(prices) and prices[i] else product.purchase_price
                        discount = float(discounts[i]) if i < len(discounts) and discounts[i] else 0
                        profit_percentage = float(profit_percentages[i]) if i < len(profit_percentages) and profit_percentages[i] else 0
                        item_total = int(str(totals[i]).replace(',', '')) if i < len(totals) and totals[i] else 0
                        item_description = descriptions[i] if i < len(descriptions) else ''
                        PurchaseInvoiceItem.objects.create(
                            invoice=invoice,
                            product=product,
                            quantity=qty,
                            price=price,
                            discount=discount,
                            profit_percentage=profit_percentage,
                            total=item_total,
                            description=item_description,
                        )
                        # Update product inventory and price
                        product.quantity += qty
                        product.purchase_price = price - (price * discount / 100)
                        product.profit_percentage = profit_percentage
                        product.price = product.purchase_price + (product.purchase_price * profit_percentage / 100)
                        product.save()
                    except Product.DoesNotExist:
                        continue
                # Handle settlement fields if present
                invoice.settle_cash = request.POST.get('settle_cash', 0) or 0
                invoice.settle_card = request.POST.get('settle_card', 0) or 0
                invoice.settle_bank = request.POST.get('settle_bank', 0) or 0
                invoice.settle_cheque = request.POST.get('settle_cheque', 0) or 0
                invoice.settle_balance = request.POST.get('settle_balance', 0) or 0
                invoice.settle_extra_discount = request.POST.get('settle_extra_discount', 0) or 0
                invoice.save()
                messages.success(request, 'فاکتور خرید با موفقیت ثبت شد و موجودی و قیمت کالاها به‌روزرسانی شد.')
                return redirect('products:purchase_invoice_detail', invoice_id=invoice.id)
        except Exception as e:
            messages.error(request, f'خطا در ثبت فاکتور: {e}')
            return redirect(request.path)

    return render(request, 'products/purchase_invoice.html', {'today': today, 'customers': customers})

@login_required
def warehouse_panel(request):
    try:
        warehouse = Warehouse.objects.get(user=request.user)
        
        # محدود کردن به یک هفته اخیر
        one_week_ago = timezone.now() - timezone.timedelta(days=7)
        
        # دریافت همه زیرسفارش‌های مرتبط با این انبار
        # از prefetch_related استفاده می‌شود تا آیتم‌ها در یک کوئری اولیه واکشی شوند
        all_orders = Order.objects.filter(
            parent_order__isnull=False,  # فقط زیرسفارش‌ها
            items__warehouse=warehouse,  # فقط آیتم‌های مربوط به این انبار
            created_at__gte=one_week_ago  # فقط سفارش‌های یک هفته اخیر
        ).distinct().prefetch_related(
            'items',
            'items__product',
            'items__warehouse'
        )

        # دریافت فقط زیرسفارش‌های جدید (pending)
        new_orders = Order.objects.filter(
            parent_order__isnull=False,
            items__warehouse=warehouse,
            items__warehouse_status='pending',
            created_at__gte=one_week_ago
        ).exclude(status='backorder').distinct().prefetch_related(
            'items',
            'items__product',
            'items__warehouse'
        )
        
        # دریافت زیرسفارش‌های در انتظار موجودی (backorder/pending_supply)
        waiting_for_stock_orders = Order.objects.filter(
            Q(parent_order__isnull=False) &
            Q(items__warehouse=warehouse) &
            (Q(items__warehouse_status='backorder') | Q(items__warehouse_status='pending_supply')) &
            Q(created_at__gte=one_week_ago)
        ).distinct().prefetch_related(
            'items',
            'items__product',
            'items__warehouse'
        )

        # 🚨 دریافت زیرسفارش‌های در انتظار تایید انباردار 🚨
        waiting_for_confirmation_orders = Order.objects.filter(
            Q(parent_order__isnull=False) &
            Q(items__warehouse=warehouse) &
            Q(items__warehouse_status='waiting_for_warehouse_confirmation') &
            Q(created_at__gte=one_week_ago)
        ).distinct().prefetch_related(
            'items',
            'items__product',
            'items__warehouse'
        )
        print(f"waiting_for_confirmation_orders query result count: {waiting_for_confirmation_orders.count()}")
        for order in waiting_for_confirmation_orders:
            print(f"Order {order.id} - Items: {order.items.count()}")

        # دریافت زیرسفارش‌های آماده ارسال
        ready_orders = Order.objects.filter(
            Q(parent_order__isnull=False) &
            Q(items__warehouse=warehouse) &
            Q(items__warehouse_status='ready') &
            Q(status='ready') &
            Q(created_at__gte=one_week_ago)
        ).distinct().prefetch_related(
            'items',
            'items__product',
            'items__warehouse'
        )

        # 🚨 فیلتر کردن آیتم‌ها برای نمایش فقط آیتم‌های مربوط به انبار جاری 🚨
        # این حلقه‌ها دوباره اضافه شدند.
        for order in all_orders:
            order.filtered_items = order.items.filter(warehouse=warehouse)
            # محاسبه total_price برای هر سفارش در اینجا اگر لازم است
            order.total_price = sum((item.price * (item.allocated_quantity or item.requested_quantity)) for item in order.filtered_items if item.price and (item.allocated_quantity or item.requested_quantity))

        for order in new_orders:
            order.filtered_items = order.items.filter(
                Q(warehouse=warehouse) &
                Q(warehouse_status='pending')
            )
            order.total_price = sum((item.price * (item.allocated_quantity or item.requested_quantity)) for item in order.filtered_items if item.price and (item.allocated_quantity or item.requested_quantity))
        
        for order in ready_orders:
            order.filtered_items = order.items.filter(
                Q(warehouse=warehouse) &
                Q(warehouse_status='ready')
            )
            order.total_price = sum((item.price * (item.allocated_quantity or item.requested_quantity)) for item in order.filtered_items if item.price and (item.allocated_quantity or item.requested_quantity))

        for order in waiting_for_stock_orders:
            order.filtered_items = order.items.filter(
                Q(warehouse=warehouse) &
                (Q(warehouse_status='backorder') | Q(warehouse_status='pending_supply'))
            )
            order.total_price = sum((item.price * (item.allocated_quantity or item.requested_quantity)) for item in order.filtered_items if item.price and (item.allocated_quantity or item.requested_quantity))

        # 🚨 فیلتر کردن آیتم‌ها برای تب "در انتظار تایید انباردار" 🚨
        for order in waiting_for_confirmation_orders:
            order.filtered_items = order.items.filter(
                Q(warehouse=warehouse) &
                Q(warehouse_status='waiting_for_warehouse_confirmation')
            )
            order.total_price = sum((item.price * (item.allocated_quantity or item.requested_quantity)) for item in order.filtered_items if item.price and (item.allocated_quantity or item.requested_quantity))


        context = {
            'warehouse': warehouse,
            'all_orders': all_orders, # اگر همچنان به این نیاز دارید
            'new_orders': new_orders,
            'ready_orders': ready_orders,
            'waiting_for_stock_orders': waiting_for_stock_orders,
            'backorder_orders': waiting_for_stock_orders, # همچنان برای سازگاری نامی حفظ شد
            'waiting_for_confirmation_orders': waiting_for_confirmation_orders, # 👈 اضافه شدن به کانتکست
        }
        
        return render(request, 'products/warehouse_panel.html', context)
        
    except Warehouse.DoesNotExist:
        messages.error(request, 'شما دسترسی به پنل انبار را ندارید. لطفا با مدیر سیستم تماس بگیرید.')
        return redirect('products:login')
    except Exception as e: # برای گرفتن هر خطای غیرمنتظره دیگر
        import traceback
        traceback.print_exc() # این خط را برای دیباگ نگه دارید
        messages.error(request, f'خطای غیرمنتظره در پنل انبار: {e}')
        return redirect('products:login')


def edit_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    # بررسی اینکه فقط مدیر (is_staff) اجازه دسترسی دارد
    if not request.user.is_authenticated or not request.user.is_staff:
        messages.error(request, "شما دسترسی به این صفحه ندارید.")
        return redirect('products:product_list')  # یا هر آدرس مناسب دیگر

    if order.status != 'pending':
        messages.error(request, "تنها سفارشات در انتظار تأیید قابل ویرایش هستند.")
        return redirect('products:manager_order_list')

    if request.method == 'POST':
        # بروزرسانی آیتم‌های فعلی
        for item in order.items.all():
            if request.POST.get(f'delete_{item.id}') == 'true':
                item.delete()
                continue

            qty = request.POST.get(f'quantity_{item.id}')
            price = request.POST.get(f'price_{item.id}')
            term = request.POST.get(f'payment_term_{item.id}')

            if qty and qty.isdigit():
                item.requested_quantity = int(qty)

            if price and price.isdigit():
                item.price = int(price)

            if term:
                item.payment_term = term

            item.save()

        # افزودن کالای جدید در صورت وجود
        product_id = request.POST.get('new_product_id')
        quantity = request.POST.get('new_quantity')
        new_price = request.POST.get('new_price')
        new_term = request.POST.get('new_payment_term')

        if product_id and quantity and quantity.isdigit():
            product = get_object_or_404(Product, id=product_id)
            quantity = int(quantity)
            price = int(new_price) if new_price and new_price.isdigit() else product.price
            payment_term = new_term or 'cash'

            existing = order.items.filter(product=product).first()
            if existing:
                existing.requested_quantity += quantity
                existing.save()
            else:
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    requested_quantity=quantity,
                    price=price,
                    payment_term=payment_term,
                    warehouse=product.warehouse
                )

        messages.success(request, "تغییرات سفارش با موفقیت ذخیره شد.")
        return redirect('products:manager_order_list')

    # حالت GET: نمایش فرم
    products = Product.objects.all()
    brands = Product.objects.values('brand').distinct()
    car_groups = Product.objects.values('car_group').distinct()

    return render(request, 'orders/edit_order.html', {
        'order': order,
        'products': products,
        'brands': brands,
        'car_groups': car_groups,
    })
@login_required
def dashboard_view(request):
    if not request.user.groups.filter(name__in=['مشتری', 'ویزیتور']).exists():
        return redirect('login')
    return render(request, 'products/product_list.html')

def is_manager(user):
    return user.groups.filter(name='مدیر').exists()

@login_required
@user_passes_test(is_manager)
def upload_excel(request):
    if request.method == 'POST':
        form = UploadExcelForm(request.POST, request.FILES)
        if form.is_valid():
            excel_file = request.FILES['excel_file']
            upload_mode = form.cleaned_data.get('upload_mode', 'update')
            try:
                import pandas as pd
                from .models import Notification, Product, Warehouse, OrderItem
                from django.contrib.auth.models import User

                df = pd.read_excel(excel_file, engine='openpyxl', dtype={'کد کالا': str})

                # فقط ستون 'کد کالا' اجباری است
                if 'کد کالا' not in df.columns:
                    messages.error(request, "ستون 'کد کالا' در فایل یافت نشد و این ستون اجباری است.")
                    return render(request, 'products/upload_excel.html', {'form': form})

                # حذف ردیف‌هایی که مقدار کد کالا یا قیمت ندارند
                df = df.dropna(subset=['کد کالا', 'قیمت'])

                Warehouse.objects.get_or_create(name='انبار پخش')
                Warehouse.objects.get_or_create(name='انبار فروشگاه')

                # --- استخراج لیست کالاهای بک‌اوردر قبل از آپدیت ---
                backorder_products = list(Product.objects.filter(quantity=0).values_list('code', flat=True))

                # --- آپدیت یا ایجاد محصولات از روی فایل اکسل ---
                for idx, row in df.iterrows():
                    product_code = str(row['کد کالا']).strip()
                    price_val = row['قیمت'] if 'قیمت' in row else None
                    # چک price خالی یا نامعتبر
                    if pd.isna(price_val) or str(price_val).strip() == "":
                        print(f"[UPLOAD_EXCEL] ردیف {idx+2} - کد کالا: {product_code} - قیمت وجود ندارد یا خالی است.")
                        messages.error(
                            request,
                            f"قیمت برای محصول با کد '{product_code}' (یا نام '{row.get('نام محصول', '')}') در ردیف {idx+2} خالی است."
                        )
                        return render(request, 'products/upload_excel.html', {'form': form})
                    try:
                        price_float = float(str(price_val).replace(',', '').strip())
                    except Exception:
                        print(f"[UPLOAD_EXCEL] ردیف {idx+2} - کد کالا: {product_code} - قیمت نامعتبر: {price_val}")
                        messages.error(
                            request,
                            f"قیمت نامعتبر برای محصول با کد '{product_code}' (یا نام '{row.get('نام محصول', '')}') در ردیف {idx+2}."
                        )
                        return render(request, 'products/upload_excel.html', {'form': form})

                    # مقداردهی و ذخیره محصول
                    product, created = Product.objects.get_or_create(code=product_code, defaults={'price': price_float})
                    if not created:
                        product.price = price_float
                    # سایر فیلدها...
                    product.save()

                    if 'نام محصول' in row and pd.notna(row['نام محصول']):
                        product.name = str(row['نام محصول']).strip()
                    if 'گروه خودرو' in row and pd.notna(row['گروه خودرو']):
                        product.car_group = str(row['گروه خودرو']).strip()
                    product.price = price_float  # مقداردهی price (همیشه)
                    if 'موجودی' in row and pd.notna(row['موجودی']):
                        if upload_mode == 'update':
                            product.quantity = int(row['موجودی'])
                        elif upload_mode == 'purchase':
                            product.quantity = (product.quantity or 0) + int(row['موجودی'])
                    if 'نام انبار' in row and pd.notna(row['نام انبار']):
                        warehouse_name = str(row['نام انبار']).strip()
                        if warehouse_name in ['انبار پخش', 'انبار فروشگاه']:
                            warehouse = Warehouse.objects.get(name=warehouse_name)
                            product.warehouse = warehouse
                    if 'برند' in row and pd.notna(row['برند']):
                        product.brand = str(row['برند']).strip()
                    if 'مدت تسویه' in row and pd.notna(row['مدت تسویه']):
                        max_payment_term = str(row['مدت تسویه']).strip()
                        if max_payment_term in ['cash', '1m', '2m', '3m', '4m']:
                            product.max_payment_term = max_payment_term

                    product.save()

                # --- بعد از آپدیت، بررسی تامین کالاهای بک‌اوردر و ساخت اعلان ---
                supplied_products = Product.objects.filter(
                    code__in=backorder_products,
                    quantity__gt=0
                )
                if supplied_products.exists():
                    managers = User.objects.filter(groups__name='مدیر')
                    for product in supplied_products:
                        backorder_items = OrderItem.objects.filter(
                            product=product,
                            warehouse_status='backorder'
                        ).select_related('order', 'order__customer')

                        for backorder_item in backorder_items:
                            order_number = getattr(backorder_item.order, 'order_number', '')
                            customer = getattr(backorder_item.order, 'customer', None)
                            customer_name = f"{getattr(customer, 'first_name', '')} {getattr(customer, 'last_name', '')}".strip() if customer else ""
                            for manager in managers:
                                Notification.objects.create(
                                    title="تامین کالاهای بک‌اوردر",
                                    message="",
                                    target_user=manager,
                                    product_title=product.name,
                                    order_number=order_number,
                                    customer_name=customer_name,
                                )

                messages.success(request, "فایل اکسل با موفقیت ثبت شد.")
                return render(request, 'products/upload_excel.html', {'form': form})
            except Exception as e:
                messages.error(request, f"خطا در پردازش فایل: {str(e)}")
                return render(request, 'products/upload_excel.html', {'form': form})
    else:
        form = UploadExcelForm()
    return render(request, 'products/upload_excel.html', {'form': form})

@csrf_exempt
@login_required
def create_order(request):
    if request.method == 'POST':
        try:
            user = request.user
            data = json.loads(request.body)
            customer_id = data.get('customer_id')
            items = data.get('items', [])

            if not customer_id:
                return JsonResponse({
                    'success': False,
                    'message': 'شناسه مشتری الزامی است'
                }, status=400)

            if not items:
                return JsonResponse({
                    'success': False,
                    'message': 'حداقل یک کالا باید انتخاب شود'
                }, status=400)

            customer = get_object_or_404(Customer, id=customer_id)
            
            # ⛔ بررسی امنیتی: اگر کاربر مشتری است، فقط خودش را مجاز بداند
            if user.groups.filter(name='مشتری').exists():
                if not hasattr(user, 'customer_profile') or customer != user.customer_profile:
                    return JsonResponse({
                        'success': False,
                        'message': 'شما مجاز به ثبت سفارش برای این مشتری نیستید'
                    }, status=403)

            with transaction.atomic():
                order = Order.objects.create(
                    visitor_name=user.username,
                    customer=customer,
                    payment_term='cash',
                    status='pending'
                )

                for item in items:
                    product = get_object_or_404(Product, id=item['product_id'])
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        requested_quantity=item['quantity'],
                        allocated_quantity=0,
                        price=product.price,
                        payment_term=item['payment_term'],
                        warehouse=product.warehouse
                    )

            return JsonResponse({
                'success': True,
                'message': 'سفارش با موفقیت ثبت شد',
                'order_id': order.id
            })
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'داده‌های ارسالی نامعتبر است'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'خطا در ثبت سفارش: {str(e)}'
            }, status=500)


@login_required
def order_history(request):
    orders = Order.objects.filter(visitor_name=request.user.username).order_by('-created_at')[:10]
    orders_data = [
        {
            'id': order.id,
            'order_number': order.order_number,
            'customer_name': order.customer_name,
            'created_at': jdatetime.datetime.fromgregorian(datetime=order.created_at.replace(tzinfo=None)).strftime('%Y/%m/%d %H:%M'),
            'total_amount': sum((item.requested_quantity or 0) * (item.price or 0) for item in order.items.all()),
            'items': [
                {
                    'product_name': item.product.name,
                    'quantity': item.requested_quantity or 0,
                    'price': item.price or 0,
                    'payment_term': item.get_payment_term_display()
                } for item in order.items.all()
            ]
        } for order in orders
    ]
    import traceback
    traceback.print_exc()
    return JsonResponse({'orders': orders_data})

@login_required
def get_user_orders(request):
    try:
        orders = Order.objects.filter(
            visitor_name=request.user.username,
            parent_order__isnull=True,
            status__in=['pending', 'warehouse', 'ready', 'delivered', 'parent', 'completed', 'backorder', 'waiting_for_customer_shipment', 'sent_to_warehouse', 'waiting_for_warehouse_confirmation']
        ).exclude(status='cart').order_by('-created_at')[:10]
        orders_data = [
            {
                'id': order.id,
                'customer_name': order.customer_name,
                'created_at': jdatetime.datetime.fromgregorian(datetime=order.created_at).strftime('%H:%M - %Y/%m/%d '),
                'payment_term': order.get_payment_term_display(),
                'items': [
                    {
                        'product_name': item.product.name,
                        'product_code': item.product.code,
                        'quantity': item.requested_quantity,  # ✅ همیشه این را بفرست
                        'requested_quantity': item.requested_quantity,  # ✅ این هم اضافه کن
                        'price': float(item.price),  # Convert to float to ensure proper calculation
                        'total': float(item.price) * item.requested_quantity,  # Calculate total here
                        'payment_term': item.get_payment_term_display()
                    } for item in order.items.all()
                ]
            } for order in orders
        ]
        return JsonResponse({'orders': orders_data})
    except Exception as e:
        return JsonResponse({'message': 'خطا در دریافت سفارش‌ها', 'error': str(e)}, status=500)
    
@login_required
def order_pdf(request, order_id):
    logger.info(f"Request received for PDF of order {order_id} by user {request.user.username}")
    try:
        # Step 1: Get the order by ID first, without user filtering
        order = get_object_or_404(Order, id=order_id)

        # Step 2: Check permissions, similar to order_detail_view
        is_manager = request.user.groups.filter(name='مدیر').exists()
        is_accounting = request.user.groups.filter(name='حسابداری').exists()
        is_order_creator = (order.visitor_name == request.user.username)

        if not (is_manager or is_order_creator or is_accounting):
            logger.warning(f"Unauthorized PDF access attempt for order {order_id} by user {request.user.username}")
            return HttpResponse('شما اجازه دسترسی به این سند را ندارید.', status=403)

        items = order.items.all()
        logger.info(f"Order {order_id} found with {items.count()} items. User authorized.")

        # فیلدهای سفارش
        customer = order.customer or "-"
        order_number = order.order_number or "-"
        order_date = order.created_at.strftime('%Y/%m/%d %H:%M') if order.created_at else "-"
        payment_term = order.get_payment_term_display() if hasattr(order, "get_payment_term_display") else "-"
        visitor_name = order.visitor_name or "-"

        # اطلاعات مشتری از ارتباط ForeignKey
        if order.customer:
            customer_address = order.customer.address or "-"
            customer_mobile = order.customer.mobile or "-"
        else:
            customer_address = "-"
            customer_mobile = "-"

        # ویزیتور: نام و نام خانوادگی به جای username
        from django.contrib.auth.models import User
        try:
            user = User.objects.get(username=order.visitor_name)
            visitor_name = f"{user.first_name} {user.last_name}".strip() or user.username
        except User.DoesNotExist:
            visitor_name = order.visitor_name or "-"

        # تبدیل تاریخ به جلالی
        import jdatetime
        if order.created_at:
            order_date = jdatetime.datetime.fromgregorian(datetime=order.created_at.replace(tzinfo=None)).strftime('%H:%M - %Y/%m/%d')
        else:
            order_date = "-"

        tick_cash = '\\ding{51}' if payment_term == 'نقد' else ''
        tick_cheque = '\\ding{51}' if payment_term == 'چک' else ''
        tick_tasvie = '\\ding{51}' if payment_term == 'تسویه' else ''
        tick_card = '\\ding{51}' if payment_term == 'کارتخوان' else ''

        latex_content = f"""
\\documentclass[a4paper,12pt]{{article}}
\\usepackage{{geometry}}
\\geometry{{a4paper, margin=1in}}
\\usepackage{{longtable}}
\\usepackage{{colortbl}}
\\usepackage{{xcolor}}
\\usepackage{{setspace}}
\\usepackage{{graphicx}}
\\usepackage{{amssymb}}
\\setstretch{{1.2}}
\\usepackage{{xepersian}}
\\settextfont{{Vazirmatn}}
\\definecolor{{headerblue}}{{RGB}}{{44, 62, 80}}

\\begin{{document}}

% هدر و لوگو
\\begin{{center}}
    % اگر لوگو دارید، مسیر فایل را جایگزین کنید
    % \\includegraphics[width=3cm]{{logo.png}} \\\\
    {{\\Huge \\textbf{{   پیش فاکتور فروشگاه اکبرزاده }}}} \\\\
\\end{{center}}

\\vspace{{0.5cm}}

% اطلاعات مشتری و سفارش
\\noindent
\\begin{{tabular}}{{|p{{7cm}}|p{{7cm}}|}}
\\hline
\\textbf{{مشتری:}} {customer} & \\textbf{{تاریخ:}} {order_date} \\\\
\\hline
\\textbf{{موبایل:}} {customer_mobile} & \\textbf{{شماره:}} {order_number} \\\\
\\hline
\\multicolumn{{2}}{{|p{{14cm}}|}}{{\\textbf{{آدرس:}} {customer_address}}} \\\\
\\hline
\\end{{tabular}}

\\vspace{{0.5cm}}

% جدول کالاها
\\begin{{longtable}}{{|c|c|p{{4cm}}|c|c|c|c|}}
\\hline
\\rowcolor{{headerblue}} \\color{{white}}
\\textbf{{ردیف}} &  \\textbf{{کد کالا}} & \\textbf{{شرح}} & \\textbf{{مقدار}} & \\textbf{{واحد}} & \\textbf{{فی}} & \\textbf{{قیمت کل}} \\\\
\\hline
\\endhead
"""

        total = 0
        for idx, item in enumerate(items, 1):
            product_code = getattr(item.product, "code", "-") if hasattr(item, "product") else getattr(item, "code", "-")
            product_name = getattr(item.product, "name", "-") if hasattr(item, "product") else getattr(item, "name", "-")
            quantity = getattr(item, "requested_quantity", None) or getattr(item, "quantity", 1)
            price = getattr(item, "price", 0)
            item_total = price * quantity
            total += item_total
            latex_content += f"{idx} & {product_code} & {product_name} & {quantity} & عدد & {price:,} & {item_total:,} \\\\\n\\hline\n"

        latex_content += f"""\\end{{longtable}}

% جمع کل و بخش پرداخت
\\vspace{{0.3cm}}
\\noindent
\\begin{{tabular}}{{|p{{7cm}}|p{{7cm}}|}}
\\hline
\\textbf{{جمع کل کالاها و خدمات:}} & {total:,} ریال \\\\
\\hline
\\textbf{{تخفیف:}} & 0 ریال \\\\
\\hline
\\textbf{{مالیات/عوارض:}} & 0 ریال \\\\
\\hline
\\textbf{{مبلغ قابل پرداخت:}} & {total:,} ریال \\\\
\\hline
\\end{{tabular}}

\\vspace{{0.3cm}}

% نحوه تسویه
\\noindent
\\textbf{{نحوه تسویه:}}
\\begin{{tabular}}{{|c|c|c|c|}}
\\hline
نقد & چک & تسویه & کارتخوان \\\\
\\hline
{tick_cash} & {tick_cheque} & {tick_tasvie} & {tick_card} \\\\
\\hline
\\end{{tabular}}

\\vspace{{0.5cm}}

% توضیحات و مهر و امضا
\\noindent
\\textbf{{توضیحات:}} ...............................................................................................

\\vspace{{1.5cm}}

\\noindent
مهر و امضا خریدار \\hspace{{8cm}} مهر و امضا فروشنده

\\vfill

% متن پایین صفحه
\\noindent


\\end{{document}}
"""
        logger.info(f"LaTeX content generated for order {order_number}")

        temp_dir = os.path.join(settings.BASE_DIR, 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        tex_file = os.path.join(temp_dir, f'order_{order_number}.tex')
        with open(tex_file, 'w', encoding='utf-8') as f:
            f.write(latex_content)
        logger.info(f"TeX file written to {tex_file}")

        logger.info("Attempting to run xelatex")
        try:
            result = subprocess.run(['xelatex', '--version'], capture_output=True, text=True, check=True, timeout=10)
            logger.info(f"xelatex version: {result.stdout.splitlines()[0]}")
        except FileNotFoundError:
            logger.error("xelatex not found on server")
            return HttpResponse('xelatex روی سرور نصب نیست. لطفاً xelatex را نصب کنید.', status=500)
        except subprocess.CalledProcessError as e:
            logger.error(f"xelatex version check failed: {e.stderr}")
            return HttpResponse(f'خطا در بررسی xelatex: {e.stderr}', status=500)
        except subprocess.TimeoutExpired:
            logger.error("xelatex version check timed out")
            return HttpResponse('اجرای xelatex بیش از حد طول کشید.', status=500)

        try:
            result = subprocess.run(['xelatex', '-output-directory', temp_dir, tex_file], check=True, capture_output=True, text=True, timeout=180)
            logger.info(f"xelatex output: {result.stdout}")
        except subprocess.CalledProcessError as e:
            logger.error(f"xelatex failed: {e.stderr}")
            return HttpResponse(f'خطا در کامپایل LaTeX: {e.stderr}', status=500)
        except subprocess.TimeoutExpired:
            logger.error("xelatex compilation timed out")
            return HttpResponse('کامپایل LaTeX بیش از حد طول کشید.', status=500)

        pdf_file = os.path.join(temp_dir, f'order_{order_number}.pdf')
        if not os.path.exists(pdf_file):
            logger.error(f"PDF not found at {pdf_file}")
            return HttpResponse('فایل PDF تولید نشد.', status=500)
        with open(pdf_file, 'rb') as f:
            pdf_content = f.read()

        for ext in ['.tex', '.pdf', '.log', '.aux']:
            try:
                os.remove(os.path.join(temp_dir, f'order_{order_number}{ext}'))
            except OSError:
                pass

        logger.info(f"PDF generated successfully for order {order_number}")
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="order_{order_number}.pdf"'
        response.write(pdf_content)
        return response
    except Order.DoesNotExist:
        logger.error(f"PDF generation failed: Order {order_id} does not exist.")
        return HttpResponse('خطا در ایجاد PDF: سفارش مورد نظر یافت نشد.', status=404)
    except Exception as e:
        logger.error(f"PDF generation failed for order {order_id}: {str(e)}", exc_info=True)
        return HttpResponse(f'خطا در ایجاد PDF: {str(e)}', status=500)

@login_required
def get_products(request):
    query = request.GET.get('q', '')
    brand = request.GET.get('brand', '')
    car_group = request.GET.get('car_group', '')
    products = Product.objects.all()
    if query:
        products = products.filter(Q(name__icontains=query) | Q(code__icontains=query))
    if brand:
        products = products.filter(brand=brand)
    if car_group:
        products = products.filter(car_group=car_group)
    products_data = [
        {
            'id': p.id,
            'code': p.code,
            'name': p.name,
            'price': float(p.price),
            'quantity': p.quantity,
            'car_group': p.car_group,
            'max_payment_term': p.max_payment_term
        } for p in products
    ]
    return JsonResponse({'products': products_data})

@login_required
def get_orders(request):
    try:
        orders = Order.objects.all().prefetch_related('items')
        orders_data = [
            {
                'id': order.id,
                'visitor_name': order.visitor_name,
                'items': [
                    {
                        'product_name': item.product.name,
                        'quantity': item.quantity or 0,
                        'payment_term': item.get_payment_term_display()
                    } for item in order.items.all()
                ],
                'created_at': jdatetime.datetime.fromgregorian(datetime=order.created_at).strftime('%Y-%m-%d %H:%M:%S'),
            } for order in orders
        ]
        return JsonResponse({'orders': orders_data})
    except Exception as e:
        return JsonResponse({'message': 'خطا در دریافت سفارش‌ها', 'error': str(e)}, status=500)
@login_required
@require_POST
@transaction.atomic
def update_order_status(request):
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        shipment_id = data.get('shipment_id')
        current_status = data.get('current_status')
        courier_id = data.get('courier_id')
        description = data.get('description', '')
        
        logger.info(f"[SHIPMENT_UPDATE] Starting update_order_status. order_id: {order_id}, shipment_id: {shipment_id}, current_status: {current_status}")

        # منطق جدید برای نهایی کردن ارسال
        if current_status == 'shipped':
            if not shipment_id:
                logger.error("[SHIPMENT_UPDATE] Finalization failed: shipment_id is missing.")
                return JsonResponse({'success': False, 'message': 'شناسه ارسال ارسال نشده'}, status=400)
            
            try:
                shipment = Shipment.objects.get(id=shipment_id)
                items_data = data.get('items', [])
                logger.info(f"[SHIPMENT_UPDATE] Finalizing shipment {shipment.id} with {len(items_data)} items.")

                for item_data in items_data:
                    order_item = get_object_or_404(OrderItem, id=item_data['item_id'])
                    delivered_qty = int(item_data['delivered_quantity'])
                    
                    if delivered_qty > order_item.allocated_quantity:
                        return JsonResponse({'success': False, 'message': f'مقدار تحویلی برای کالای {order_item.product.name} بیش از مقدار تخصیص یافته است.'}, status=400)

                    order_item.delivered_quantity = delivered_qty
                    order_item.save()

                    # اگر مقداری برگشت خورده باشد، به موجودی انبار اضافه شود
                    returned_qty = order_item.allocated_quantity - delivered_qty
                    if returned_qty > 0:
                        product = order_item.product
                        product.quantity += returned_qty
                        product.save()

                # تغییر وضعیت ارسال به 'delivered' (نهایی شده)
                shipment.status = 'delivered'
                shipment.save()
                shipment.refresh_from_db()

                # --- START: Create Financial Operation ---
                customer = None
                description_op = ""
                
                # Case 1: Shipment has sub-orders (standard flow)
                sub_orders_in_shipment = shipment.sub_orders.all()
                if sub_orders_in_shipment.exists():
                    customer = sub_orders_in_shipment.first().customer
                    sub_order_numbers = ", ".join([so.order_number for so in sub_orders_in_shipment])
                    description_op = f"فاکتور فروش بابت سفارشات: {sub_order_numbers}"
                
                # Case 2: Shipment is a standalone backorder without sub-orders
                elif shipment.is_backorder and shipment.order:
                    customer = shipment.order.customer
                    description_op = f"فاکتور فروش بابت بک اوردر: {shipment.order.order_number}"

                # Proceed if we have a customer and description
                if customer and description_op:
                    if not FinancialOperation.objects.filter(operation_type='SALES_INVOICE', customer=customer, description=description_op).exists():
                        total_price = 0
                        for shipment_item in shipment.shipmentitem_set.all():
                            if shipment_item.order_item and shipment_item.order_item.price is not None:
                                total_price += shipment_item.order_item.price * shipment_item.quantity_shipped
                        
                        if total_price > 0:
                            user = customer.created_by or User.objects.filter(username=shipment.order.visitor_name).first() or User.objects.filter(is_superuser=True).first()
                            if user:
                                FinancialOperation.objects.create(
                                    operation_type='SALES_INVOICE',
                                    customer=customer,
                                    amount=total_price,
                                    payment_method='credit_sale',
                                    date=timezone.now().date(),
                                    description=description_op,
                                    created_by=user,
                                    status='CONFIRMED',
                                    confirmed_by=user,
                                    confirmed_at=timezone.now()
                                )
                # --- END: Create Financial Operation ---

                # Update the status of all sub-orders related to this shipment
                sub_orders_to_update = shipment.sub_orders.all()
                if not sub_orders_to_update.exists() and shipment.order:
                    try:
                        sub_orders_to_update = shipment.order.get_sub_orders()
                    except Exception:
                        sub_orders_to_update = shipment.order.order_set.all() if hasattr(shipment.order, 'order_set') else Order.objects.none()

                if sub_orders_to_update.exists():
                    sub_orders_to_update.update(status='delivered')

                if shipment.order:
                    shipment.order.status = 'delivered'
                    shipment.order.save()

                return JsonResponse({'success': True, 'message': 'ارسال با موفقیت نهایی شد و فاکتور فروش صادر گردید.'})

            except Shipment.DoesNotExist:
                return JsonResponse({'success': False, 'message': 'ارسال یافت نشد'}, status=404)
            except Exception as e:
                logger.error(f"[SHIPMENT_UPDATE] Exception during finalization: {str(e)}", exc_info=True)
                return JsonResponse({'success': False, 'message': f'خطا در نهایی کردن ارسال: {str(e)}'}, status=500)

        if not order_id:
            logger.error("[SHIPMENT_UPDATE] Status update failed: order_id is missing.")
            return JsonResponse({'success': False, 'message': 'شناسه سفارش ارسال نشده'}, status=400)

        order = get_object_or_404(Order, id=order_id)

        if current_status == 'pending':
            return send_order_to_warehouse(request, order_id)

        if current_status == 'waiting_for_customer_shipment':
            logger.info(f"[SHIPMENT_UPDATE] Processing 'waiting_for_customer_shipment' for order {order.id}")
            if not courier_id:
                return JsonResponse({'success': False, 'message': 'پیک انتخاب نشده است'}, status=400)
            
            try:
                courier = Courier.objects.get(id=courier_id)
            except (Courier.DoesNotExist, ValueError):
                return JsonResponse({'success': False, 'message': 'پیک معتبر نیست'}, status=400)
            
            is_standalone_backorder = order.parent_order and order.order_number and order.order_number.startswith('BO-')

            if is_standalone_backorder:
                order.status = 'shipped'
                order.courier = courier
                order.save()
                
                auto_description = f"ارسال بک اوردر {order.order_number}"
                final_description = f"{auto_description} - {description}" if description else auto_description
                shipment = Shipment.objects.create(
                    order=order,
                    parent_order=order.parent_order,
                    courier=courier,
                    status='shipped',
                    description=final_description,
                    is_backorder=True
                )
                logger.info(f"[SHIPMENT_UPDATE] Created Shipment for standalone backorder. Shipment ID: {shipment.id}, Number: {shipment.shipment_number}")
                shipment.sub_orders.add(order)
                logger.info(f"[SHIPMENT_UPDATE] Added backorder {order.id} to shipment {shipment.id}")

                for item in order.items.filter(allocated_quantity__gt=0):
                    shipment_item = ShipmentItem.objects.create(
                        shipment=shipment,
                        order_item=item,
                        quantity_shipped=item.allocated_quantity
                    )
                    logger.info(f"[SHIPMENT_UPDATE] Created ShipmentItem {shipment_item.id} for standalone backorder. Links shipment {shipment.id} to OrderItem {item.id}")
            else:
                sub_orders = order.get_sub_orders().filter(status__in=['ready', 'waiting_for_customer_shipment'])
                sub_orders.update(status='shipped', courier=courier)
                
                order.status = 'shipped'
                order.save()

                auto_description = f"ارسال سفارش اصلی {order.order_number}"
                final_description = f"{auto_description} - {description}" if description else auto_description
                shipment = Shipment.objects.create(
                    order=order,
                    courier=courier,
                    status='shipped',
                    description=final_description
                )
                logger.info(f"[SHIPMENT_UPDATE] Created Shipment for parent order. Shipment ID: {shipment.id}, Number: {shipment.shipment_number}")
                shipment.sub_orders.set(sub_orders)
                logger.info(f"[SHIPMENT_UPDATE] Set sub_orders for shipment {shipment.id}. Sub-order IDs: {[so.id for so in sub_orders]}")

                for sub_order in sub_orders:
                    for item in sub_order.items.filter(allocated_quantity__gt=0):
                        shipment_item = ShipmentItem.objects.create(
                            shipment=shipment,
                            order_item=item,
                            quantity_shipped=item.allocated_quantity
                        )
                        logger.info(f"[SHIPMENT_UPDATE] Created ShipmentItem {shipment_item.id} for parent order. Links shipment {shipment.id} to OrderItem {item.id}")

            return JsonResponse({
                'success': True,
                'message': 'وضعیت سفارش با موفقیت به "ارسال شده" تغییر یافت.',
                'next_status': 'shipped',
                'next_status_display': 'ارسال شده'
            })

        status_flow = {'warehouse': 'ready', 'ready': 'waiting_for_customer_shipment'}
        next_status = status_flow.get(current_status)

        if not next_status:
            return JsonResponse({'success': False, 'message': 'جریان وضعیت نامعتبر است'}, status=400)

        order.status = next_status
        order.save()
        
        is_backorder = order.order_number and order.order_number.startswith('BO-')
        if not is_backorder and order.parent_order and next_status in ['ready', 'waiting_for_customer_shipment']:
            parent = order.parent_order
            if parent.status not in ['delivered', 'completed', 'waiting_for_customer_shipment']:
                parent.status = 'waiting_for_customer_shipment'
                parent.save()

        return JsonResponse({
            'success': True,
            'message': 'وضعیت سفارش با موفقیت تغییر یافت',
            'next_status': next_status,
            'next_status_display': order.get_status_display()
        })

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in update_order_status: {str(e)}")
        return JsonResponse({'success': False, 'message': 'داده‌های ارسالی نامعتبر است'}, status=400)
    except Exception as e:
        logger.error(f"Unexpected error in update_order_status: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'message': f'خطای سرور: {str(e)}'}, status=500)

@login_required
def admin_panel(request):
    return render(request, 'products/manager_dashboard.html')
import openpyxl

@login_required
def product_list(request):
    if 'excel_output' in request.GET:
        return export_products_to_excel(request)
    brands = Product.objects.values_list('brand', flat=True).distinct()
    car_groups = Product.objects.values_list('car_group', flat=True).distinct()
    active_tab = request.GET.get('tab', 'all')

    customer_id = request.GET.get('customer_id')
    selected_customer = None
    if customer_id:
        try:
            selected_customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            pass
    
    # --- تعریف متغیر one_week_ago در اینجا ---
    one_week_ago = timezone.now() - timedelta(days=7)

    # --- بخش محصولات کلی ---
    products_query = Product.objects.all().order_by('id')
    q_all = request.GET.get('q')
    brand_all = request.GET.get('brand')
    car_group_all = request.GET.get('car_group')

    if brand_all and brand_all != "all":
        products_query = products_query.filter(brand=brand_all)
    if car_group_all and car_group_all != "all":
        products_query = products_query.filter(car_group=car_group_all)
    if q_all:
        products_query = products_query.filter(Q(normalized_name__icontains=normalize_text(q_all)) | Q(code__icontains=normalize_text(q_all)))

    paginator_all = Paginator(products_query, 50)
    page_all_number = request.GET.get('page_all')
    page_obj = paginator_all.get_page(page_all_number)

    # --- بخش تغییرات قیمت ---
    price_changes_query = PriceChange.objects.filter(change_date__gte=one_week_ago).select_related('product').order_by('-change_date')
    
    q_price = request.GET.get('q_price')
    brand_price = request.GET.get('brand_price')
    car_group_price = request.GET.get('car_group_price')

    if brand_price and brand_price != "all":
        price_changes_query = price_changes_query.filter(product__brand=brand_price)
    if car_group_price and car_group_price != "all":
        price_changes_query = price_changes_query.filter(product__car_group=car_group_price)
    if q_price:
        price_changes_query = price_changes_query.filter(Q(product__normalized_name__icontains=normalize_text(q_price)) | Q(product__code__icontains=normalize_text(q_price)))

    paginator_price = Paginator(price_changes_query, 50)
    page_price_number = request.GET.get('page_price')
    price_changes_page_obj = paginator_price.get_page(page_price_number)
    
    # --- بخش کالاهای جدید ---
    new_products_query = Product.objects.filter(created_at__gte=one_week_ago).order_by('-created_at')
    q_new = request.GET.get('q_new')
    brand_new = request.GET.get('brand_new')
    car_group_new = request.GET.get('car_group_new')

    if brand_new and brand_new != "all":
        new_products_query = new_products_query.filter(brand=brand_new)
    if car_group_new and car_group_new != "all":
        new_products_query = new_products_query.filter(car_group=car_group_new)
    if q_new:
        new_products_query = new_products_query.filter(Q(normalized_name__icontains=normalize_text(q_new)) | Q(code__icontains=normalize_text(q_new)))

    paginator_new = Paginator(new_products_query, 50)
    page_new_number = request.GET.get('page_new')
    new_products_page_obj = paginator_new.get_page(page_new_number)

    user_is_visitor = request.user.groups.filter(name='ویزیتور').exists()

    context = {
        'page_obj': page_obj,
        'price_changes_page_obj': price_changes_page_obj,
        'new_products_page_obj': new_products_page_obj,
        'brands': brands,
        'car_groups': car_groups,
        'active_tab': active_tab,
        'q_all': q_all,
        'selected_brand_all': brand_all,
        'selected_car_group_all': car_group_all,
        'q_price': q_price,
        'selected_brand_price': brand_price,
        'selected_car_group_price': car_group_price,
        'q_new': q_new,
        'selected_brand_new': brand_new,
        'selected_car_group_new': car_group_new,
        'selected_customer': selected_customer,
        'user_is_visitor': user_is_visitor,
    }
    return render(request, 'products/product_list.html', context)


def export_products_to_excel(request):
    output_type = request.GET.get('excel_output')
    
    if output_type == 'all':
        products_query = Product.objects.all().order_by('id')
        q_all = request.GET.get('q')
        brand_all = request.GET.get('brand')
        car_group_all = request.GET.get('car_group')

        if brand_all and brand_all != "all":
            products_query = products_query.filter(brand=brand_all)
        if car_group_all and car_group_all != "all":
            products_query = products_query.filter(car_group=car_group_all)
        if q_all:
            products_query = products_query.filter(Q(normalized_name__icontains=normalize_text(q_all)) | Q(code__icontains=normalize_text(q_all)))
        
        data = list(products_query.values('code', 'name', 'car_group', 'brand', 'price', 'max_payment_term'))
        df = pd.DataFrame(data)
        df.rename(columns={'code': 'کد کالا', 'name': 'نام کالا', 'car_group': 'گروه خودرو', 'brand': 'برند', 'price': 'قیمت', 'max_payment_term': 'حداکثر تسویه'}, inplace=True)
        df['حداکثر تسویه'] = df['حداکثر تسویه'].replace({
            '1m': '1 ماه',
            '2m': '2 ماه',
            '3m': '3 ماه',
            '4m': '4 ماه',
            'cash': 'نقدی'
        })

    elif output_type == 'price':
        one_week_ago = timezone.now() - timedelta(days=7)
        price_changes_query = PriceChange.objects.filter(change_date__gte=one_week_ago).select_related('product').order_by('-change_date')
        
        q_price = request.GET.get('q_price')
        brand_price = request.GET.get('brand_price')
        car_group_price = request.GET.get('car_group_price')

        if brand_price and brand_price != "all":
            price_changes_query = price_changes_query.filter(product__brand=brand_price)
        if car_group_price and car_group_price != "all":
            price_changes_query = price_changes_query.filter(product__car_group=car_group_price)
        if q_price:
            price_changes_query = price_changes_query.filter(Q(product__normalized_name__icontains=normalize_text(q_price)) | Q(product__code__icontains=normalize_text(q_price)))
        
        data = []
        for change in price_changes_query:
            data.append({
                'کد': change.product.code,
                'نام کالا': change.product.name,
                'ق. قدیم': change.old_price,
                'ق. جدید': change.new_price,
                'درصد': change.percentage_change,
                'تاریخ': jdatetime.datetime.fromgregorian(datetime=change.change_date).strftime('%y/%m/%d'),
                'تسویه': change.product.get_max_payment_term_display()
            })
        df = pd.DataFrame(data)
        df['تسویه'] = df['تسویه'].replace({
            '1m': '1 ماه',
            '2m': '2 ماه',
            '3m': '3 ماه',
            '4m': '4 ماه',
            'cash': 'نقدی'
        })

    elif output_type == 'new':
        one_week_ago = timezone.now() - timedelta(days=7)
        new_products_query = Product.objects.filter(created_at__gte=one_week_ago).order_by('-created_at')
        data = list(new_products_query.values('code', 'name', 'car_group', 'brand', 'price', 'max_payment_term'))
        df = pd.DataFrame(data)
        df.rename(columns={'code': 'کد کالا', 'name': 'نام کالا', 'car_group': 'گروه خودرو', 'brand': 'برند', 'price': 'قیمت', 'max_payment_term': 'حداکثر تسویه'}, inplace=True)
        df['حداکثر تسویه'] = df['حداکثر تسویه'].replace({
            '1m': '1 ماه',
            '2m': '2 ماه',
            '3m': '3 ماه',
            '4m': '4 ماه',
            'cash': 'نقدی'
        })
    
    else:
        return HttpResponse("Invalid output type")

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="products_{output_type}.xlsx"'
    df.to_excel(response, index=False, engine='openpyxl')
    
    return response


def upload_success(request):
    return HttpResponse("آپلود با موفقیت انجام شد.")

def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if user.groups.filter(name='مدیر').exists():
                return redirect('products:manager_dashboard')
            elif user.groups.filter(name='ویزیتور').exists():
                return redirect('products:product_list')
            elif user.groups.filter(name='مشتری').exists():
                return redirect('products:product_list')
            elif user.groups.filter(name='انباردار').exists():
                return redirect('products:warehouse_panel')
            elif user.groups.filter(name='حسابداری').exists():
                return redirect('products:accounting_panel')
            else:
                messages.error(request, 'نقش کاربری شما تعریف نشده است.')
                logout(request)
                return redirect('products:login')
        else:
            messages.error(request, 'نام کاربری یا رمز عبور اشتباه است.')
    return render(request, 'products/login.html')

@require_POST
def logout_view(request):
    logout(request)
    return redirect('products:login')

def user_logout(request):
    logout(request)
    return redirect('products:login')

@login_required
@user_passes_test(is_manager)
@never_cache
def manager_dashboard(request):
    return render(request, 'products/manager_dashboard.html')

@login_required
@user_passes_test(is_manager)
@never_cache
def manager_order_list(request):
    # Get filter parameters
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    order_number = request.GET.get('order_number')
    customer_name = request.GET.get('customer_name')
    visitor_name = request.GET.get('visitor_name')
    status = request.GET.get('status')

    # Create a base queryset for all orders that can be filtered
    base_query = Order.objects.select_related('customer').all().order_by('-created_at')

    # Apply common filters
    # Default date filter: last 30 days if no date is specified
    if not date_from and not date_to:
        thirty_days_ago = timezone.now() - timedelta(days=30)
        base_query = base_query.filter(created_at__gte=thirty_days_ago)
    else:
        if date_from:
            base_query = base_query.filter(created_at__date__gte=convert_shamsi_to_gregorian(date_from))
        if date_to:
            base_query = base_query.filter(created_at__date__lte=convert_shamsi_to_gregorian(date_to))

    if order_number:
        base_query = base_query.filter(order_number__icontains=order_number)
    if customer_name:
        base_query = base_query.filter(
            Q(customer__first_name__icontains=customer_name) | 
            Q(customer__last_name__icontains=customer_name) |
            Q(customer__store_name__icontains=customer_name)
        )
    if visitor_name:
        base_query = base_query.filter(visitor_name__icontains=visitor_name)
    if status:
        base_query = base_query.filter(status=status)

    # --- Main Order Tabs ---
    all_requests = base_query.filter(parent_order__isnull=True)
    pending_requests = all_requests.filter(status='pending')
    warehouse_requests = all_requests.filter(status='parent') # Corrected from parent_requests
    ready_requests = base_query.filter(
        Q(status='waiting_for_customer_shipment') &
        (Q(parent_order__isnull=True) | Q(order_number__startswith='BO-'))
    ).prefetch_related('items', 'customer').distinct()
    delivered_requests = all_requests.filter(status='delivered')
    parent_requests = all_requests.filter(status='parent') # Kept for backward compatibility if template uses it

    # --- Backorder & Supply Tabs (more complex logic on the filtered base) ---
    # These can include main orders and sub-orders, so we filter from the base_query directly
    backordered_requests = base_query.filter(
        Q(status='backorder') | Q(items__warehouse_status='backorder')
    ).distinct()
    
    supplied_requests = base_query.filter(
        Q(items__warehouse_status='waiting_for_warehouse_confirmation') | Q(status='sent_to_warehouse')
    ).distinct()

    backorder_ready_requests = base_query.filter(
        Q(order_number__startswith='BO-') & Q(order_number__endswith='-RE'),
        parent_order__isnull=False,
        status='ready'
    ).exclude(status='delivered').distinct()


    # --- Shipped and Delivered Shipments Tabs ---
    shipped_shipments_query = Shipment.objects.filter(status='shipped').select_related('order__customer').prefetch_related('sub_orders', 'sub_orders__items', 'sub_orders__warehouse').order_by('-shipment_date')
    delivered_shipments_query = Shipment.objects.filter(status='delivered').select_related('order__customer').prefetch_related('sub_orders', 'sub_orders__items', 'sub_orders__warehouse').order_by('-shipment_date')

    # Apply common filters to both shipment queries
    if date_from:
        gregorian_date_from = convert_shamsi_to_gregorian(date_from)
        shipped_shipments_query = shipped_shipments_query.filter(shipment_date__date__gte=gregorian_date_from)
        delivered_shipments_query = delivered_shipments_query.filter(delivery_date__date__gte=gregorian_date_from)
    if date_to:
        gregorian_date_to = convert_shamsi_to_gregorian(date_to)
        shipped_shipments_query = shipped_shipments_query.filter(shipment_date__date__lte=gregorian_date_to)
        delivered_shipments_query = delivered_shipments_query.filter(delivery_date__date__lte=gregorian_date_to)
    if order_number:
        shipped_shipments_query = shipped_shipments_query.filter(
            Q(order__order_number__icontains=order_number) | Q(shipment_number__icontains=order_number)
        )
        delivered_shipments_query = delivered_shipments_query.filter(
            Q(order__order_number__icontains=order_number) | Q(shipment_number__icontains=order_number)
        )
    if customer_name:
        shipped_shipments_query = shipped_shipments_query.filter(
            Q(order__customer__first_name__icontains=customer_name) |
            Q(order__customer__last_name__icontains=customer_name) |
            Q(order__customer__store_name__icontains=customer_name)
        )
        delivered_shipments_query = delivered_shipments_query.filter(
            Q(order__customer__first_name__icontains=customer_name) |
            Q(order__customer__last_name__icontains=customer_name) |
            Q(order__customer__store_name__icontains=customer_name)
        )

    couriers = Courier.objects.filter(is_active=True)

    context = {
        'all_requests': all_requests,
        'pending_requests': pending_requests,
        'warehouse_requests': warehouse_requests,
        'ready_requests': ready_requests,
        'delivered_requests': delivered_requests, # This is for the tile count, will be replaced
        'shipped_shipments': shipped_shipments_query,
        'delivered_shipments': delivered_shipments_query, # New context variable
        'backordered_requests': backordered_requests,
        'supplied_requests': supplied_requests,
        'backorder_ready_requests': backorder_ready_requests,
        'parent_requests': parent_requests,
        'status_choices': [choice for choice in Order.STATUS_CHOICES if choice[0] != 'cart'],
        'request': request,
        'couriers': couriers,
    }
    return render(request, 'products/manager_order_list.html', context)

@login_required
def read_notification(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, target_user=request.user)
    if request.method == 'POST':
        notification.read = True
        notification.save()
    return redirect('products:manager_order_list')

@login_required
def visitor_panel(request):
    user = request.user

    if not user.groups.filter(name__in=['ویزیتور', 'مشتری']).exists():
        return render(request, 'error.html', {'message': 'شما اجازه دسترسی به این بخش را ندارید.'})

    brands = Product.objects.values('brand').distinct()
    car_groups = Product.objects.values('car_group').distinct()

    if user.groups.filter(name='ویزیتور').exists():
        customers = Customer.objects.all().order_by('first_name', 'last_name')
    else:
        try:
            customers = [user.customer_profile]
        except Customer.DoesNotExist:
            customers = []

    return render(request, 'products/product_list.html', {
        'brands': brands,
        'car_groups': car_groups,
        'customers': customers,
        'user_is_visitor': user.groups.filter(name='ویزیتور').exists(),
        'user_is_customer': user.groups.filter(name='مشتری').exists(),
    })

@login_required
def customer_panel(request):
    return render(request, 'products/customer_panel.html')

def redirect_to_login(request):
    return redirect('products:login')

@login_required
def debug_view(request):
    return JsonResponse({'message': 'Debug view is working', 'user': request.user.username})

def update_parent_order_status(parent_order):
    """
    بررسی و به‌روزرسانی وضعیت سفارش مادر بر اساس وضعیت زیرسفارش‌ها
    """
    if not parent_order:
        return

    # دریافت همه زیرسفارش‌ها
    sub_orders = parent_order.sub_orders.all()
    if not sub_orders:
        return

    # بررسی وضعیت همه زیرسفارش‌ها
    all_ready = True  # فرض می‌کنیم همه ready هستند
    has_backorder = False
    
    for sub_order in sub_orders:
        if sub_order.status == 'backorder':
            has_backorder = True
        elif sub_order.status != 'ready':
            all_ready = False
            break
    
    # اگر همه زیرسفارش‌ها ready هستند یا ترکیبی از ready و backorder هستند
    if all_ready:
        parent_order.status = 'waiting_for_customer_shipment'
        parent_order.save()

@csrf_exempt
@login_required
@require_POST
def update_warehouse_items(request):
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        items_data = data.get('items', [])

        if not order_id or not items_data:
            return JsonResponse({
                'success': False,
                'message': 'اطلاعات ناقص است'
            })

        order = get_object_or_404(Order, id=order_id)
        warehouse = Warehouse.objects.get(user=request.user)

        with transaction.atomic():
            for item_data in items_data:
                item_id = item_data.get('item_id')
                status = item_data.get('status')
                note = item_data.get('note')

                item = get_object_or_404(OrderItem, id=item_id, order=order, warehouse=warehouse)
                item.warehouse_status = status
                item.warehouse_note = note
                item.save()

            # بررسی وضعیت همه آیتم‌های سفارش
            all_items = order.items.all()
            all_ready = all(item.warehouse_status == 'ready' for item in all_items)
            any_out_of_stock = any(item.warehouse_status == 'out_of_stock' for item in all_items)

            # به‌روزرسانی وضعیت سفارش
            if any_out_of_stock:
                order.status = 'backorder'
            elif all_ready:
                order.status = 'ready'
                # اگر این سفارش یک زیرسفارش است، وضعیت سفارش مادر را به‌روز می‌کنیم
                if order.parent_order:
                    update_parent_order_status(order.parent_order)
            
            order.save()

        return JsonResponse({
            'success': True,
            'message': 'وضعیت آیتم‌ها با موفقیت به‌روز شد'
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'فرمت JSON نامعتبر است'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'خطا در به‌روزرسانی وضعیت: {str(e)}'
        }, status=500)

@user_passes_test(is_manager)
def create_test_users(request):
    try:
        # ایجاد گروه انباردار اگر وجود نداشته باشد
        warehouse_group, _ = Group.objects.get_or_create(name='انباردار')
        
        # ایجاد کاربر برای انبار پخش
        warehouse1_user, created1 = User.objects.get_or_create(
            username='anbar_pakhsh',
            defaults={'is_staff': False}
        )
        if created1:
            warehouse1_user.set_password('1234')
            warehouse1_user.save()
            warehouse1_user.groups.add(warehouse_group)
            
            # اتصال کاربر به انبار
            warehouse1 = Warehouse.objects.get(name='انبار پخش')
            warehouse1.user = warehouse1_user
            warehouse1.save()

        # ایجاد کاربر برای انبار فروشگاه
        warehouse2_user, created2 = User.objects.get_or_create(
            username='anbar_forushgah',
            defaults={'is_staff': False}
        )
        if created2:
            warehouse2_user.set_password('1234')
            warehouse2_user.save()
            warehouse2_user.groups.add(warehouse_group)
            
            # اتصال کاربر به انبار
            warehouse2 = Warehouse.objects.get(name='انبار فروشگاه')
            warehouse2.user = warehouse2_user
            warehouse2.save()

        return JsonResponse({
            'success': True,
            'message': 'کاربران تست با موفقیت ایجاد شدند.',
            'users': {
                'anbar_pakhsh': 'ایجاد شد' if created1 else 'از قبل وجود داشت',
                'anbar_forushgah': 'ایجاد شد' if created2 else 'از قبل وجود داشت'
            }
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'خطا در ایجاد کاربران تست: {str(e)}'
        }, status=500)

@csrf_exempt
@require_POST
@login_required
def allocate_items(request):
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        document_number = data.get('document_number')
        package_count = data.get('package_count')
        allocations = data.get('allocations', {})

        if not all([order_id, document_number, package_count, allocations]):
            return JsonResponse({'success': False, 'message': 'اطلاعات ناقص است'}, status=400)

        order = get_object_or_404(Order, id=order_id)
        warehouse = Warehouse.objects.get(user=request.user)

        with transaction.atomic():
            order.document_number = document_number
            order.package_count = int(package_count)

            backorder_items_to_create = []
            has_allocated_items = False

            for item_id_str, allocation_data in allocations.items():
                item_id = int(item_id_str)
                item = get_object_or_404(OrderItem, id=item_id, order=order, warehouse=warehouse)

                try:
                    allocated_qty = int(allocation_data.get('quantity', 0))
                except (ValueError, TypeError):
                    return JsonResponse({'success': False, 'message': f'مقدار تخصیص برای آیتم {item_id} نامعتبر است'}, status=400)

                note = allocation_data.get('note', '')

                if allocated_qty > item.requested_quantity:
                    return JsonResponse({'success': False, 'message': f'مقدار تخصیص برای {item.product.name} از مقدار درخواستی بیشتر است.'}, status=400)

                if allocated_qty < 0:
                    return JsonResponse({'success': False, 'message': 'مقدار تخصیص نمی‌تواند منفی باشد.'}, status=400)
                
                if allocated_qty > 0:
                    product = item.product
                    if product.quantity < allocated_qty:
                        return JsonResponse({
                            'success': False,
                            'message': f'موجودی کافی برای "{product.name}" در انبار وجود ندارد (موجودی: {product.quantity})'
                        }, status=400)
                    product.quantity -= allocated_qty
                    product.save()

              
                item.allocated_quantity = allocated_qty
                item.warehouse_note = note
                item.warehouse_status = 'ready'
                item.save()

                if allocated_qty > 0:
                    has_allocated_items = True

                unallocated_qty = item.requested_quantity - allocated_qty
                if unallocated_qty > 0:
                    backorder_items_to_create.append({
                        'original_item': item,
                        'quantity': unallocated_qty,
                    })


            if not has_allocated_items and not backorder_items_to_create:
                return JsonResponse({'success': False, 'message': 'هیچ کالایی تخصیص داده نشده است. لطفاً مقادیر را وارد کنید.'}, status=400)

            if backorder_items_to_create:
                parent_order = order.parent_order or order

                backorder = Order(
                    visitor_name=order.visitor_name,
                    customer=order.customer,
                    payment_term=order.payment_term,
                    status='backorder',
                    parent_order=parent_order
                )
                backorder.warehouse_name = warehouse.name  # Set temporary attribute for save()
                backorder.save()

                for bo_item_data in backorder_items_to_create:
                    original_item = bo_item_data['original_item']
                    OrderItem.objects.create(
                        order=backorder,
                        product=original_item.product,
                        requested_quantity=bo_item_data['quantity'],
                        allocated_quantity=0,
                        price=original_item.price,
                        payment_term=original_item.payment_term,
                        warehouse=original_item.warehouse,
                        warehouse_status='backorder'
                    )

            if has_allocated_items:
                order.status = 'ready'
            else:
                order.status = 'closed_backordered'

            order.save()

            if order.parent_order:
                update_parent_order_status(order.parent_order)

        return JsonResponse({'success': True, 'message': 'تخصیص با موفقیت انجام شد.'})

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'داده‌های ارسالی نامعتبر است.'}, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': f'خطا در تخصیص کالا: {str(e)}'}, status=500)
    
@login_required
def search_customers(request):
    try:
        query = request.GET.get('q', '')
        print(f"جستجوی مشتری با عبارت: {query}")  # برای دیباگ
        
        # اگر query خالی باشد، همه مشتریان را برمی‌گرداند
        if not query:
            customers = Customer.objects.all().order_by('first_name', 'last_name')[:20]
        else:
            customers = Customer.objects.filter(
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query)
            ).order_by('first_name', 'last_name')[:10]
            
        print(f"تعداد {customers.count()} مشتری پیدا شد")  # برای دیباگ
        
        results = [{
            'id': customer.id,
            'first_name': customer.first_name,
            'last_name': customer.last_name,
            'store_name': customer.store_name or '',
            'mobile': customer.mobile or ''
        } for customer in customers]
        
        return JsonResponse({'customers': results})
    except Exception as e:
        print(f"خطا در جستجوی مشتریان: {str(e)}")  # برای دیباگ
        return JsonResponse({'error': str(e)}, status=500)
@login_required
@user_passes_test(is_manager)
@require_POST
@transaction.atomic
def send_selected_items_to_warehouse(request):
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        items_data = data.get('items', [])

        if not order_id or not items_data:
            return JsonResponse({'success': False, 'message': 'اطلاعات ارسالی ناقص است.'}, status=400)

        original_order = get_object_or_404(Order, id=order_id)
        
        # Group items by warehouse
        items_by_warehouse = {}
        for item_info in items_data:
            item = get_object_or_404(OrderItem, id=item_info['item_id'])
            if item.warehouse_status != 'backorder':
                 return JsonResponse({'success': False, 'message': f'آیتم {item.product.name} در وضعیت بک اوردر نیست.'}, status=400)
            
            quantity = int(item_info.get('quantity', 0))
            if quantity <= 0:
                continue # Skip items with no quantity
            if quantity > item.requested_quantity:
                return JsonResponse({'success': False, 'message': f'مقدار برای آیتم {item.product.name} بیش از حد مجاز است.'}, status=400)

            warehouse_id = item.warehouse.id if item.warehouse else None
            if warehouse_id not in items_by_warehouse:
                items_by_warehouse[warehouse_id] = []
            
            items_by_warehouse[warehouse_id].append({'item': item, 'quantity': quantity})

        if not items_by_warehouse:
            return JsonResponse({'success': False, 'message': 'هیچ کالایی برای ارسال انتخاب نشده است.'}, status=400)

        # Create one new order per warehouse
        for warehouse_id, grouped_items in items_by_warehouse.items():
            warehouse = get_object_or_404(Warehouse, id=warehouse_id) if warehouse_id else None
            
            # --- Generate new order number ---
            warehouse_name_fa = warehouse.name if warehouse else "UNKNOWN"
            warehouse_code = "PAKHSH" if warehouse_name_fa == "انبار پخش" else "SHOP" if warehouse_name_fa == "انبار فروشگاه" else "unknown"
            parent_order = original_order.parent_order or original_order
            prefix = f"BO-{warehouse_code}-{parent_order.order_number}-"
            existing_resends = Order.objects.filter(order_number__startswith=prefix, order_number__endswith='RE').count()
            new_order_number = f"BO-{warehouse_code}-{parent_order.order_number}-{str(existing_resends + 1).zfill(4)}-RE"

            # Create new resupply order
            new_order = Order.objects.create(
                parent_order=parent_order,
                status='waiting_for_warehouse_confirmation',
                customer=original_order.customer,
                order_number=new_order_number,
                warehouse=warehouse
            )

            for data in grouped_items:
                item = data['item']
                quantity = data['quantity']

                # Create new item in the resupply order
                OrderItem.objects.create(
                    order=new_order,
                    product=item.product,
                    requested_quantity=quantity,
                    price=item.price,
                    payment_term=item.payment_term,
                    warehouse=item.warehouse,
                    warehouse_status='waiting_for_warehouse_confirmation'
                )

                # Update original backorder item
                if quantity == item.requested_quantity:
                    item.delete()
                else:
                    item.requested_quantity -= quantity
                    item.save()

        # Check if original backorder should be removed
        if not original_order.items.exists():
            original_order.delete()

        return JsonResponse({'success': True, 'message': f'{len(items_data)} مورد با موفقیت به انبار ارسال شد.'})

    except Exception as e:
        logger.exception("An error occurred in send_selected_items_to_warehouse.")
        return JsonResponse({'success': False, 'message': f'خطا در سرور: {str(e)}'}, status=500)


@login_required
@user_passes_test(is_manager)
@require_POST
def resend_backorder_item_to_warehouse(request):
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        quantity = int(data.get('quantity', 0))

        item = get_object_or_404(OrderItem, id=item_id)
        order = item.order

        if item.warehouse_status != 'backorder':
            return JsonResponse({'success': False, 'message': 'این آیتم در وضعیت بک‌اوردر نیست.'}, status=400)

        if quantity > item.requested_quantity:
            return JsonResponse({'success': False, 'message': 'مقدار وارد شده بیش از تعداد مورد نیاز است.'}, status=400)
        if quantity <= 0:
            return JsonResponse({'success': False, 'message': 'تعداد باید بیشتر از صفر باشد.'}, status=400)

        # ساخت شماره سفارش RE جدید
        warehouse_name_fa = item.warehouse.name if item.warehouse else "UNKNOWN"

        if warehouse_name_fa == "انبار پخش":
            warehouse_name = "PAKHSH"
        elif warehouse_name_fa == "انبار فروشگاه":
            warehouse_name = "SHOP"
        else:
            warehouse_name = "unknown"

        parent_order = order.parent_order if hasattr(order, "parent_order") and order.parent_order else order
        parent_order_number = parent_order.order_number

        prefix = f"BO-{warehouse_name}-{parent_order_number}-"
        existing_resends = Order.objects.filter(
            order_number__startswith=prefix,
            order_number__endswith='RE'
        ).count()
        new_order_number = f"BO-{warehouse_name}-{parent_order_number}-{str(existing_resends+1).zfill(4)}-RE"

        # ایجاد سفارش جدید با شماره RE...
        new_order = Order.objects.create(
            parent_order=parent_order,
            status='waiting_for_warehouse_confirmation',
            customer=order.customer,
            order_number=new_order_number,
            warehouse=item.warehouse
        )

        # ایجاد آیتم جدید در سفارش جدید
        OrderItem.objects.create(
            order=new_order,
            product=item.product,
            requested_quantity=quantity,
            allocated_quantity=0,
            price=item.price,
            payment_term=item.payment_term,
            warehouse=item.warehouse,
            warehouse_status='waiting_for_warehouse_confirmation'
        )

        # کم کردن یا حذف آیتم قبلی
        if quantity == item.requested_quantity:
            item.delete()
        else:
            item.requested_quantity -= quantity
            item.save()

        update_order_status_based_on_items(order)
        remaining_backorder_items = order.items.filter(warehouse_status='backorder').exists()

        return JsonResponse({
            'success': True,
            'message': 'آیتم با موفقیت به انبار ارسال شد و سفارش RE جدید ساخته شد.',
            'item_id': item_id,
            'order_id': order.id,
            'order_should_remove': not remaining_backorder_items,
            'new_order_number': new_order_number
        })

    except Exception as e:
        logger.exception("An error occurred in resend_backorder_item_to_warehouse.")
        return JsonResponse({'success': False, 'message': f'خطا در تخصیص کالا: {str(e)}'}, status=500)

@csrf_exempt
@require_POST
def send_item_to_warehouse(request):
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')

        if not item_id:
            return JsonResponse({'success': False, 'message': 'شناسه آیتم لازم است.'}, status=400)

        order_item = get_object_or_404(OrderItem, id=item_id)
        order = order_item.order

        # تغییر وضعیت آیتم به 'backorder'
        order_item.warehouse_status = 'backorder'
        order_item.save()
        update_order_status_based_on_items(order)
        

        # بررسی آیتم‌های باقی‌مانده با وضعیت backorder
        remaining_backorder_items = order.items.filter(warehouse_status='backorder').count()

        if remaining_backorder_items == 0:
            # اگر هیچ آیتمی باقی نمانده، وضعیت سفارش را به closed_backordered تغییر بده
            order.status = 'closed_backordered'
            order.save()
            order_should_remove = True
        else:
            # اگر هنوز آیتم‌های backorder داریم، وضعیت سفارش را backorder نگه می‌داریم
            order.status = 'backorder'
            order.save()
            order_should_remove = False

        return JsonResponse({
            'success': True, 
            'message': 'آیتم با موفقیت به لیست تامین موجودی منتقل شد.',
            'order_should_remove': order_should_remove,
            'item_id': item_id,
            'order_id': order.id
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'درخواست نامعتبر JSON.'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

def update_order_status_based_on_items(order):
    items = order.items.all()
    if all(item.warehouse_status == 'ready' for item in items):
        order.status = 'ready'
    elif any(item.warehouse_status == 'backorder' for item in items):
        order.status = 'backorder'
    elif all(item.warehouse_status == 'delivered' for item in items):
        order.status = 'delivered'
    else:
        order.status = 'pending'
    order.save()

def allocate_to_warehouse(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    if order.status != 'pending':
        messages.error(request, 'فقط سفارش‌های در انتظار تأیید قابل ارسال به انبار هستند.')
        return redirect('manager_order_list')
    
    with transaction.atomic():
        order.status = 'parent'
        order.save()
        
        for item in order.items.all():
            product = item.product
            requested_quantity = item.requested_quantity
            allocated_quantity = 0
            
            # بررسی موجودی در انبارها
            warehouses = Warehouse.objects.filter(products__product=product).distinct()
            for warehouse in warehouses:
                warehouse_product = warehouse.products.filter(product=product).first()
                if not warehouse_product:
                    continue
                    
                available_quantity = warehouse_product.quantity
                if available_quantity >= requested_quantity - allocated_quantity:
                    # موجودی کافی در انبار
                    quantity_to_allocate = requested_quantity - allocated_quantity
                    warehouse_product.quantity -= quantity_to_allocate
                    warehouse_product.save()
                    
                    # ایجاد زیرسفارش برای انبار
                    sub_order = Order.objects.create(
                        parent_order=order,
                        status='warehouse',
                        customer=order.customer,
                        order_number=f"{order.order_number}-{warehouse.code}",
                        warehouse=warehouse
                    )
                    OrderItem.objects.create(
                        order=sub_order,
                        product=product,
                        requested_quantity=quantity_to_allocate,
                        allocated_quantity=quantity_to_allocate,
                        price=item.price
                    )
                    allocated_quantity += quantity_to_allocate
                else:
                    # موجودی ناکافی, تخصیص موجودی موجود
                    if available_quantity > 0:
                        warehouse_product.quantity = 0
                        warehouse_product.save()
                        
                        sub_order = Order.objects.create(
                            parent_order=order,
                            status='warehouse',
                            customer=order.customer,
                            order_number=f"{order.order_number}-{warehouse.code}",
                            warehouse=warehouse
                        )
                        OrderItem.objects.create(
                            order=sub_order,
                            product=product,
                            requested_quantity=available_quantity,
                            allocated_quantity=available_quantity,
                            price=item.price
                        )
                        allocated_quantity += available_quantity
            
            # اگر مقداری تخصیص نیافته باقی مانده، ایجاد بک‌اوردر
            if allocated_quantity < requested_quantity:
                backorder_quantity = requested_quantity - allocated_quantity
                backorder = Order.objects.create(
                    parent_order=order,
                    status='backorder',
                    customer=order.customer,
                    order_number=f"BO-{order.order_number}",
                    warehouse=None
                )
                OrderItem.objects.create(
                    order=backorder,
                    product=product,
                    requested_quantity=backorder_quantity,
                    allocated_quantity=0,
                    price=item.price
                )
        
        # به‌روزرسانی سفارش فعلی
        order.status = 'ready'
        order.save()

    messages.success(request, 'سفارش با موفقیت به انبارها تخصیص یافت.')
    return redirect('manager_order_list')

@csrf_exempt
@login_required
@require_POST
@transaction.atomic
def confirm_backorder_item(request):
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        order_id = data.get('order_id')
        allocated_qty = int(data.get('allocated_quantity', 0))
        note = data.get('note', '')
        document_number = data.get('document_number')
        package_count = int(data.get('package_count', 0))

        # دریافت مدل‌ها
        order_item = get_object_or_404(OrderItem, id=item_id)
        order = get_object_or_404(Order, id=order_id)
        parent_order_of_current_backorder = order.parent_order

        # Determine the parent for the new backorder if unallocated quantity remains
        parent_for_new_backorder = parent_order_of_current_backorder
        # If the parent order exists and is already delivered or completed,
        # or if the current 'order' itself was a top-level backorder (no parent),
        # then the new backorder should be independent.
        if parent_for_new_backorder and parent_for_new_backorder.status in ['delivered', 'completed']:
            parent_for_new_backorder = None
        elif not parent_order_of_current_backorder: # If current backorder itself was a top-level order
            parent_for_new_backorder = None

        # اعتبارسنجی
        if allocated_qty > order_item.requested_quantity:
            return JsonResponse({'success': False, 'message': 'مقدار تخصیص یافته نمی‌تواند از مقدار درخواستی بیشتر باشد.'}, status=400)
        
        unallocated_qty = order_item.requested_quantity - allocated_qty

        # به‌روزرسانی آیتم سفارش اصلی: این آیتم اکنون به عنوان آیتم تخصیص یافته در نظر گرفته می‌شود
        # و از 'backorder' خارج شده، وضعیت آن به 'ready' تغییر می‌کند.
        order_item.allocated_quantity = allocated_qty
        order_item.requested_quantity = allocated_qty # تعداد درخواستی را برابر با تخصیص یافته قرار می‌دهیم
        order_item.warehouse_status = 'ready'
        order_item.save()

        # به‌روزرسانی سفارش فعلی
        order.status = 'ready'
        order.save()

        return JsonResponse({'success': True, 'message': 'آیتم با موفقیت تایید و آماده ارسال شد.'})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': f'خطا در پردازش: {str(e)}'}, status=500)
    
@csrf_exempt
@login_required
def add_to_cart(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            product_id = data.get("product_id")
            quantity = int(data.get("quantity", 1))
            customer_id = data.get("customer_id")

            if not product_id or quantity <= 0:
                return JsonResponse({"success": False, "message": "اطلاعات ناقص"}, status=400)
            
            product = Product.objects.get(id=product_id)
            customer = None

            # کاربر مشتری
            if hasattr(request.user, 'customer_profile'):
                customer = request.user.customer_profile
            elif request.user.groups.filter(name='ویزیتور').exists():
                # اگر ویزیتور هست، باید customer_id ارسال شده باشد
                if not customer_id:
                    return JsonResponse({"success": False, "message": "لطفاً ابتدا مشتری را انتخاب کنید."}, status=400)
                customer = Customer.objects.get(id=customer_id)
            else:
                return JsonResponse({"success": False, "message": "نوع کاربری نامعتبر"}, status=403)

            # بررسی سفارش باز یا ساخت سفارش جدید (سبد خرید)
            cart_order, created = Order.objects.get_or_create(
                customer=customer,
                status='cart',  # وضعیت جدید برای سبد خرید
                defaults={
                    'visitor_name': request.user.username,
                    'payment_term': 'cash'
                }
            )

            # افزودن یا آپدیت آیتم در سبد خرید
            item, created = OrderItem.objects.get_or_create(
                order=cart_order,
                product=product,
                defaults={
                    'requested_quantity': quantity, 
                    'allocated_quantity': 0, 
                    'price': product.price, 
                    'payment_term': 'cash', 
                    'warehouse': product.warehouse
                }
            )
            if not created:
                item.requested_quantity += quantity
                item.save()

            # تعداد کل آیتم‌ها در سبد خرید
            cart_count = cart_order.items.count()
            return JsonResponse({
                "success": True, 
                "cart_count": cart_count,
                "message": "کالا به سبد خرید اضافه شد"
            })

        except Exception as e:
            return JsonResponse({"success": False, "message": f"خطا: {str(e)}"}, status=500)

    return JsonResponse({"success": False, "message": "روش درخواست نامعتبر"}, status=405)

@login_required
def get_cart(request):
    """
    دریافت محتویات سبد خرید کاربر
    """
    try:
        customer = None
        if hasattr(request.user, 'customer_profile'):
            customer = request.user.customer_profile
        elif request.user.groups.filter(name='ویزیتور').exists():
            # برای ویزیتور، از query parameter یا session بگیریم
            customer_id = request.GET.get('customer_id')
            if customer_id:
                customer = Customer.objects.get(id=customer_id)
        
        if not customer:
            return JsonResponse({
                'success': False,
                'message': 'مشتری یافت نشد'
            }, status=400)

        # دریافت سفارش cart کاربر
        cart_order = Order.objects.filter(
            customer=customer,
            status='cart'
        ).first()

        if not cart_order:
            return JsonResponse({
                'success': True,
                'cart': [],
                'total': 0
            })

        cart_items = []
        total = 0
        
        for item in cart_order.items.all().select_related('product'):
            item_total = item.price * item.requested_quantity
            total += item_total
            
            cart_items.append({
                'id': item.id,
                'product_id': item.product.id,
                'product_name': item.product.name,
                'product_code': item.product.code,
                'brand': item.product.brand if item.product.brand else None,
                'car_group': item.product.car_group if item.product.car_group else None,
                'quantity': item.requested_quantity,
                'price': float(item.price),
                'image': item.product.image.url if item.product.image else None,
                'total': float(item_total),
                
            })

        return JsonResponse({
            'success': True,
            'cart': cart_items,
            'total': float(total)
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'خطا در دریافت سبد خرید: {str(e)}'
        }, status=500)

@csrf_exempt
@login_required
@require_POST
def change_cart_qty(request):
    """
    تغییر تعداد آیتم در سبد خرید
    """
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        delta = int(data.get('delta', 0))
        customer_id = data.get('customer_id')

        if not item_id:
            return JsonResponse({
                'success': False,
                'message': 'شناسه آیتم ارسال نشده'
            }, status=400)

        # بررسی دسترسی کاربر به این آیتم
        customer = None
        if hasattr(request.user, 'customer_profile'):
            customer = request.user.customer_profile
        elif request.user.groups.filter(name='ویزیتور').exists():
            if customer_id:
                customer = Customer.objects.get(id=customer_id)

        if not customer:
            return JsonResponse({
                'success': False,
                'message': 'مشتری یافت نشد'
            }, status=400)

        item = OrderItem.objects.filter(
            id=item_id,
            order__customer=customer,
            order__status='cart'
        ).first()

        if not item:
            return JsonResponse({
                'success': False,
                'message': 'آیتم یافت نشد'
            }, status=404)

        new_quantity = item.requested_quantity + delta
        
        if new_quantity <= 0:
            # حذف آیتم اگر تعداد صفر یا منفی شود
            item.delete()
        else:
            item.requested_quantity = new_quantity
            item.save()

        return JsonResponse({
            'success': True,
            'message': 'تعداد با موفقیت تغییر یافت'
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'داده‌های ارسالی نامعتبر است'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'خطا در تغییر تعداد: {str(e)}'
        }, status=500)

@csrf_exempt
@login_required
@require_POST
def remove_cart_item(request):
    """
    حذف آیتم از سبد خرید
    """
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        customer_id = data.get('customer_id')

        if not item_id:
            return JsonResponse({
                'success': False,
                'message': 'شناسه آیتم ارسال نشده'
            }, status=400)

        # بررسی دسترسی کاربر به این آیتم
        customer = None
        if hasattr(request.user, 'customer_profile'):
            customer = request.user.customer_profile
        elif request.user.groups.filter(name='ویزیتور').exists():
            if customer_id:
                customer = Customer.objects.get(id=customer_id)

        if not customer:
            return JsonResponse({
                'success': False,
                'message': 'مشتری یافت نشد'
            }, status=400)

        item = OrderItem.objects.filter(
            id=item_id,
            order__customer=customer,
            order__status='cart'
        ).first()

        if not item:
            return JsonResponse({
                'success': False,
                'message': 'آیتم یافت نشد'
            }, status=404)

        item.delete()

        return JsonResponse({
            'success': True,
            'message': 'آیتم با موفقیت حذف شد'
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'داده‌های ارسالی نامعتبر است'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'خطا در حذف آیتم: {str(e)}'
        }, status=500)

@csrf_exempt
@login_required
@require_POST
def update_cart_quantities(request):
    """
    به‌روزرسانی تعداد آیتم‌های سبد خرید
    """
    try:
        data = json.loads(request.body)
        updates = data.get('updates', [])
        
        print(f"Received updates: {updates}")  # Debug log

        if not updates:
            return JsonResponse({
                'success': False,
                'message': 'هیچ به‌روزرسانی ارسال نشده'
            }, status=400)

        # بررسی دسترسی کاربر
        customer = None
        if hasattr(request.user, 'customer_profile'):
            customer = request.user.customer_profile
        elif request.user.groups.filter(name='ویزیتور').exists():
            # برای ویزیتور، از اولین آیتم customer_id را بگیریم
            if updates and 'customer_id' in updates[0]:
                customer_id = updates[0]['customer_id']
                try:
                    customer = Customer.objects.get(id=customer_id)
                except Customer.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'message': f'مشتری با شناسه {customer_id} یافت نشد'
                    }, status=404)

        if not customer:
            return JsonResponse({
                'success': False,
                'message': 'مشتری یافت نشد'
            }, status=400)

        updated_items = []
        for update in updates:
            item_id = update.get('item_id')
            quantity = update.get('quantity', 0)
            payment_term = update.get('payment_term', 'cash')

            if not item_id:
                continue

            item = OrderItem.objects.filter(
                id=item_id,
                order__customer=customer,
                order__status='cart'
            ).first()

            if item:
                print(f"Found item: {item.id}, current quantity: {item.requested_quantity}")  # Debug log
                if quantity <= 0:
                    # حذف آیتم اگر تعداد صفر یا منفی شود
                    item.delete()
                    print(f"Deleted item: {item_id}")  # Debug log
                else:
                    item.requested_quantity = quantity
                    item.payment_term = payment_term
                    item.save()
                    print(f"Updated item: {item_id} to quantity: {quantity}, payment_term: {payment_term}")  # Debug log
                    updated_items.append({
                        'item_id': item_id,
                        'quantity': quantity,
                        'payment_term': payment_term,
                        'total': item.price * quantity
                    })

        return JsonResponse({
            'success': True,
            'message': f'{len(updated_items)} آیتم با موفقیت به‌روزرسانی شد',
            'updated_items': updated_items
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'داده‌های ارسالی نامعتبر است'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'خطا در به‌روزرسانی تعداد: {str(e)}'
        }, status=500)

@csrf_exempt
@login_required
@require_POST
@transaction.atomic
def submit_order(request):
    """
    ثبت نهایی سفارش از سبد خرید
    """
    try:
        customer = None
        if hasattr(request.user, 'customer_profile'):
            customer = request.user.customer_profile
        elif request.user.groups.filter(name='ویزیتور').exists():
            # برای ویزیتور، باید از request body customer_id بگیریم
            data = json.loads(request.body)
            customer_id = data.get('customer_id')
            if customer_id:
                customer = Customer.objects.get(id=customer_id)

        if not customer:
            return JsonResponse({
                'success': False,
                'message': 'مشتری یافت نشد'
            }, status=400)

        # دریافت سفارش cart کاربر
        cart_order = Order.objects.filter(
            customer=customer,
            status='cart'
        ).first()

        if not cart_order or not cart_order.items.exists():
            return JsonResponse({
                'success': False,
                'message': 'سبد خرید خالی است'
            }, status=400)

        with transaction.atomic():
            # ایجاد شماره سفارش جدید
            order_count = Order.objects.filter(
                created_at__date=timezone.now().date()
            ).count()
            order_number = f"ORD-{timezone.now().strftime('%Y%m%d')}-{str(order_count + 1).zfill(4)}"
            
            # به‌روزرسانی سفارش
            cart_order.order_number = order_number
            cart_order.status = 'pending'  # در انتظار تایید
            cart_order.visitor_name = request.user.username
            
            # گروه‌بندی آیتم‌ها بر اساس انبار
            items_by_warehouse = {}
            for item in cart_order.items.all():
                warehouse = item.product.warehouse
                if warehouse not in items_by_warehouse:
                    items_by_warehouse[warehouse] = []
                items_by_warehouse[warehouse].append(item)
            
            # اگر کالاها از انبارهای مختلف هستند، سفارش را به چند زیرسفارش تقسیم کنیم
            if len(items_by_warehouse) > 1:
                cart_order.status = 'parent'  # این سفارش، سفارش مادر خواهد بود
                cart_order.save()
                
                # ایجاد زیرسفارش برای هر انبار
                for warehouse, items in items_by_warehouse.items():
                    sub_order = Order.objects.create(
                        customer=customer,
                        visitor_name=request.user.username,
                        parent_order=cart_order,
                        status='pending',
                        payment_term='cash',
                        order_number=f"{order_number}-{warehouse.code if warehouse else 'MISC'}"
                    )
                    
                    # انتقال آیتم‌ها به زیرسفارش
                    for item in items:
                        OrderItem.objects.create(
                            order=sub_order,
                            product=item.product,
                            requested_quantity=item.requested_quantity,
                            allocated_quantity=0,
                            price=item.price,
                            payment_term=item.payment_term,
                            warehouse=item.product.warehouse
                        )
                        
                    # حذف آیتم‌ها از سفارش اصلی
                    cart_order.items.filter(product__warehouse=warehouse).delete()
                    
            else:
                # اگر همه کالاها از یک انبار هستند، فقط سفارش اصلی را به‌روز کنیم
                cart_order.save()

        return JsonResponse({
            'success': True,
            'message': 'سفارش با موفقیت ثبت شد و منتظر تایید است',
            'order_number': order_number
        })

    except Customer.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'مشتری مورد نظر یافت نشد'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'خطا در ثبت سفارش: {str(e)}'
        }, status=500)


@login_required
def get_product(request):
    if request.method == 'GET':
        product_code = request.GET.get('code')
        try:
            product = Product.objects.get(code=product_code)
            return JsonResponse({
                'success': True,
                'product': {
                    'name': product.name,
                    'price': product.price,
                }
            })
        except Product.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'کالا یافت نشد'}, status=404)
    return JsonResponse({'success': False, 'message': 'درخواست نامعتبر'}, status=400)


@login_required
def sales_invoice_pdf(request, order_id):
    logger.info(f"Request received for sales invoice PDF of order {order_id}")
    try:
        order = get_object_or_404(Order, id=order_id)
        
        # Permission check
        is_manager = request.user.groups.filter(name='مدیر').exists()
        is_accounting = request.user.groups.filter(name='حسابداری').exists()
        is_order_creator = (order.visitor_name == request.user.username)
        if not (is_manager or is_order_creator or is_accounting):
            return HttpResponse('شما اجازه دسترسی به این سند را ندارید.', status=403)

        if order.status != 'delivered':
            return HttpResponse('فاکتور قطعی فقط برای سفارش‌های تحویل داده شده قابل صدور است.', status=400)

        items = order.items.all()
        logger.info(f"Order {order_id} found with {items.count()} items for final invoice.")

        # Fields from the order
        customer_name = order.customer.get_full_name() if order.customer else "-"
        invoice_number = order.order_number
        invoice_date = jdatetime.datetime.fromgregorian(datetime=timezone.now()).strftime('%Y/%m/%d')
        
        visitor_user = User.objects.filter(username=order.visitor_name).first()
        visitor_name = f"{visitor_user.first_name} {visitor_user.last_name}".strip() if visitor_user else order.visitor_name

        customer_address = order.customer.address or "-"
        customer_mobile = order.customer.mobile or "-"

        # Calculate total based on delivered quantity
        total = sum(item.price * (item.delivered_quantity or 0) for item in items)

        latex_content = f"""
\\documentclass[a4paper,10pt]{{article}}
\\usepackage{{geometry}}
\\geometry{{a4paper, margin=0.8in}}
\\usepackage{{longtable}}
\\usepackage{{colortbl}}
\\usepackage{{xcolor}}
\\usepackage{{setspace}}
\\usepackage{{graphicx}}
\\usepackage{{amssymb}}
\\setstretch{{1.2}}
\\usepackage{{xepersian}}
\\settextfont{{Vazirmatn}}
\\definecolor{{headerblue}}{{RGB}}{{44, 62, 80}}

\\begin{{document}}

% Header and Logo
\\begin{{center}}
    {{\\Huge \\textbf{{فاکتور فروش قطعی}}}} \\\\
    {{\\large فروشگاه اکبرزاده}}
\\end{{center}}

\\vspace{{0.5cm}}

% Customer and Invoice Information
\\noindent
\\begin{{tabular}}{{|p{{7cm}}|p{{7cm}}|}}
\\hline
\\textbf{{مشتری:}} {customer_name} & \\textbf{{تاریخ فاکتور:}} {invoice_date} \\\\
\\hline
\\textbf{{موبایل:}} {customer_mobile} & \\textbf{{شماره فاکتور:}} {invoice_number} \\\\
\\hline
\\multicolumn{{2}}{{|p{{14cm}}|}}{{\\textbf{{آدرس:}} {customer_address}}} \\\\
\\hline
\\end{{tabular}}

\\vspace{{0.5cm}}

% Items Table
\\begin{{longtable}}{{|c|p{{4cm}}|c|c|c|c|c|c|}}
\\hline
\\rowcolor{{headerblue}} \\color{{white}}
\\textbf{{ردیف}} & \\textbf{{شرح}} & \\textbf{{درخواست}} & \\textbf{{تخصیص}} & \\textbf{{تحویل}} & \\textbf{{واحد}} & \\textbf{{فی}} & \\textbf{{قیمت کل}} \\\\
\\hline
\\endhead
"""
        for idx, item in enumerate(items, 1):
            if item.delivered_quantity and item.delivered_quantity > 0:
                product_name = item.product.name
                req_qty = item.requested_quantity or 0
                alloc_qty = item.allocated_quantity or 0
                deliv_qty = item.delivered_quantity or 0
                price = item.price or 0
                item_total = price * deliv_qty
                latex_content += f"{idx} & {product_name} & {req_qty} & {alloc_qty} & {deliv_qty} & عدد & {price:,.0f} & {item_total:,.0f} \\\\\n\\hline\n"

        latex_content += f"""\\end{{longtable}}

% Totals and Payment Section
\\vspace{{0.3cm}}
\\noindent
\\begin{{tabular}}{{|p{{7cm}}|p{{7cm}}|}}
\\hline
\\textbf{{جمع کل کالاها و خدمات:}} & {total:,.0f} ریال \\\\
\\hline
\\textbf{{تخفیف:}} & 0 ریال \\\\
\\hline
\\textbf{{مبلغ قابل پرداخت:}} & {total:,.0f} ریال \\\\
\\hline
\\end{{tabular}}

\\vspace{{1.5cm}}

% Signatures
\\noindent
مهر و امضا خریدار \\hspace{{8cm}} مهر و امضا فروشنده

\\vfill

% Footer
\\noindent
\\begin{{center}}
    این فاکتور یک سند رسمی است.
\\end{{center}}

\\end{{document}}
"""
        logger.info(f"LaTeX content generated for sales invoice {invoice_number}")

        temp_dir = os.path.join(settings.BASE_DIR, 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        tex_file_path = os.path.join(temp_dir, f'sales_invoice_{invoice_number}.tex')
        
        with open(tex_file_path, 'w', encoding='utf-8') as f:
            f.write(latex_content)
        logger.info(f"TeX file written to {tex_file_path}")

        # Run XeLaTeX to generate PDF
        try:
            subprocess.run(
                ['xelatex', '-output-directory', temp_dir, tex_file_path],
                check=True, capture_output=True, text=True, timeout=180
            )
            logger.info(f"xelatex compilation successful for {invoice_number}")
        except subprocess.CalledProcessError as e:
            logger.error(f"xelatex failed for {invoice_number}: {e.stderr}")
            # Try to read the log file for more details
            log_file_path = tex_file_path.replace('.tex', '.log')
            log_content = "Log file not found."
            if os.path.exists(log_file_path):
                with open(log_file_path, 'r', encoding='utf-8') as log_file:
                    log_content = log_file.read()
            return HttpResponse(f'خطا در کامپایل LaTeX: <pre>{e.stderr}</pre><br>Log:<pre>{log_content}</pre>', status=500)
        
        pdf_file_path = os.path.join(temp_dir, f'sales_invoice_{invoice_number}.pdf')
        if not os.path.exists(pdf_file_path):
            logger.error(f"PDF not found at {pdf_file_path}")
            return HttpResponse('فایل PDF تولید نشد.', status=500)
        
        with open(pdf_file_path, 'rb') as f:
            pdf_content = f.read()

        # Clean up temporary files
        for ext in ['.tex', '.pdf', '.log', '.aux']:
            try:
                os.remove(os.path.join(temp_dir, f'sales_invoice_{invoice_number}{ext}'))
            except OSError:
                pass

        logger.info(f"PDF generated successfully for sales invoice {invoice_number}")
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="sales_invoice_{invoice_number}.pdf"'
        return response

    except Exception as e:
        logger.error(f"Sales invoice PDF generation failed for order {order_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return HttpResponse(f'خطا در ایجاد PDF فاکتور فروش: {str(e)}', status=500)
@csrf_exempt
@login_required
@group_required('حسابداری')
def parse_invoice_excel(request):
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        try:
            df = pd.read_excel(excel_file, engine='openpyxl', dtype=str)  # Force all columns to string
            # Try to find columns by Farsi or English names
            code_col = next((col for col in df.columns if 'کد' in col or 'code' in col.lower()), None)
            qty_col = next((col for col in df.columns if 'تعداد' in col or 'qty' in col.lower()), None)
            price_col = next((col for col in df.columns if 'قیمت' in col or 'price' in col.lower()), None)
            profit_col = next((col for col in df.columns if 'سود' in col or 'profit' in col.lower()), None)
            discount_col = next((col for col in df.columns if 'تخفیف' in col or 'discount' in col.lower()), None)
            if not code_col:
                return JsonResponse({'success': False, 'message': 'ستون کد کالا یافت نشد.'}, status=400)
            result = []
            for _, row in df.iterrows():
                code = str(row.get(code_col, '')).strip()  # Always string, preserves leading zeros
                if not code:
                    continue
                result.append({
                    'product_code': code,
                    'quantity': int(float(row.get(qty_col, 0))) if qty_col and row.get(qty_col, '').strip() else 0,
                    'price': float(row.get(price_col, 0)) if price_col and row.get(price_col, '').strip() else 0,
                    'profit_percentage': float(row.get(profit_col, 0)) if profit_col and row.get(profit_col, '').strip() else 0,
                    'discount': float(row.get(discount_col, 0)) if discount_col and row.get(discount_col, '').strip() else 0,
                })
            return JsonResponse({'success': True, 'items': result})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'خطا در خواندن فایل: {str(e)}'}, status=500)
    return JsonResponse({'success': False, 'message': 'درخواست نامعتبر'}, status=400)

@login_required
@group_required('حسابداری')
def purchase_invoice_list_view(request):
    invoices = PurchaseInvoice.objects.all().order_by('-invoice_date', '-created_at')
    return render(request, 'products/purchase_invoice_list.html', {'invoices': invoices})

@login_required
@group_required('حسابداری')
def purchase_invoice_detail_view(request, invoice_id):
    invoice = get_object_or_404(PurchaseInvoice, id=invoice_id)
    items = invoice.items.select_related('product').all()
    return render(request, 'products/purchase_invoice_detail.html', {'invoice': invoice, 'items': items})


@login_required
@group_required('حسابداری')
def sales_invoice_list_view(request):
    invoices = SalesInvoice.objects.all().order_by('-invoice_date', '-created_at')
    return render(request, 'products/sales_invoice_list.html', {'invoices': invoices})


@login_required
@group_required('حسابداری')
def sales_invoice_detail_view(request, invoice_id):
    invoice = get_object_or_404(SalesInvoice, id=invoice_id)
    items = invoice.items.select_related('product').all()
    return render(request, 'products/sales_invoice_detail.html', {'invoice': invoice, 'items': items})


@login_required
@group_required('حسابداری')
def sales_invoice_view(request):
    """
    Renders the sales invoice page and handles invoice registration.
    """
    import jdatetime
    from django.contrib import messages
    today = jdatetime.date.today().strftime("%Y/%m/%d")
    customers = Customer.objects.all()

    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Get invoice fields
                customer_id = request.POST.get('customer_id')
                invoice_number = request.POST.get('invoice_number')
                invoice_date = request.POST.get('invoice_date')
                description = request.POST.get('description', '')
                customer = Customer.objects.get(id=customer_id)
                # Calculate total amount
                product_codes = request.POST.getlist('product_code')
                quantities = request.POST.getlist('quantity')
                prices = request.POST.getlist('price')
                discounts = request.POST.getlist('discount')
                profit_percentages = request.POST.getlist('profit_percentage')
                descriptions = request.POST.getlist('description')
                totals = request.POST.getlist('total')
                total_amount = 0
                for t in totals:
                    try:
                        total_amount += int(str(t).replace(',', ''))
                    except Exception:
                        pass
                # Create invoice
                invoice = SalesInvoice.objects.create(
                    invoice_number=invoice_number,
                    invoice_date=invoice_date,
                    customer=customer,
                    created_by=request.user,
                    total_amount=total_amount,
                    description=description,
                    status='registered',
                )
                # Create invoice items
                for i, code in enumerate(product_codes):
                    try:
                        product = Product.objects.get(code=code)
                        qty = int(quantities[i]) if i < len(quantities) and quantities[i] else 0
                        price = int(prices[i]) if i < len(prices) and prices[i] else product.price
                        discount = float(discounts[i]) if i < len(discounts) and discounts[i] else 0
                        profit_percentage = float(profit_percentages[i]) if i < len(profit_percentages) and profit_percentages[i] else 0
                        item_total = int(str(totals[i]).replace(',', '')) if i < len(totals) and totals[i] else 0
                        item_description = descriptions[i] if i < len(descriptions) else ''
                        SalesInvoiceItem.objects.create(
                            invoice=invoice,
                            product=product,
                            quantity=qty,
                            price=price,
                            discount=discount,
                            profit_percentage=profit_percentage,
                            total=item_total,
                            description=item_description,
                        )
                        # Update product inventory
                        product.quantity -= qty
                        product.save()
                    except Product.DoesNotExist:
                        continue
                # Handle settlement fields if present
                invoice.settle_cash = request.POST.get('settle_cash', 0) or 0
                invoice.settle_card = request.POST.get('settle_card', 0) or 0
                invoice.settle_bank = request.POST.get('settle_bank', 0) or 0
                invoice.settle_cheque = request.POST.get('settle_cheque', 0) or 0
                invoice.settle_balance = request.POST.get('settle_balance', 0) or 0
                invoice.settle_extra_discount = request.POST.get('settle_extra_discount', 0) or 0
                invoice.save()
                messages.success(request, 'فاکتور فروش با موفقیت ثبت شد و موجودی کالاها به‌روزرسانی شد.')
                return redirect('products:sales_invoice_detail', invoice_id=invoice.id)
        except Exception as e:
            messages.error(request, f'خطا در ثبت فاکتور: {e}')
            return redirect(request.path)

    return render(request, 'products/sales_invoice.html', {'today': today, 'customers': customers})

@login_required
@require_POST
@csrf_protect
def ajax_purchase_invoice_register(request):
    try:
        with transaction.atomic():
            # Get and validate customer_id
            customer_id = request.POST.get('customer_id')
            if not customer_id:
                return JsonResponse({
                    'success': False,
                    'message': 'لطفاً طرف حساب را انتخاب کنید'
                }, status=400)

            # Get and validate invoice number
            invoice_number = request.POST.get('invoice_number')
            if not invoice_number:
                return JsonResponse({
                    'success': False,
                    'message': 'لطفاً شماره فاکتور را وارد کنید'
                }, status=400)

            # Check for duplicate invoice number
            if PurchaseInvoice.objects.filter(invoice_number=invoice_number).exists():
                return JsonResponse({
                    'success': False,
                    'message': 'این شماره فاکتور قبلاً ثبت شده است'
                }, status=400)

            # Get and validate invoice date
            invoice_date = request.POST.get('invoice_date')
            if not invoice_date:
                return JsonResponse({
                    'success': False,
                    'message': 'لطفاً تاریخ فاکتور را وارد کنید'
                }, status=400)
            
            try:
                # تبدیل تاریخ شمسی به میلادی
                from django.utils import timezone
                import jdatetime
                
                # تبدیل اعداد فارسی به انگلیسی
                invoice_date = invoice_date.replace('۰', '0').replace('۱', '1').replace('۲', '2')\
                    .replace('۳', '3').replace('۴', '4').replace('۵', '5')\
                    .replace('۶', '6').replace('۷', '7').replace('۸', '8').replace('۹', '9')
                
                # اگر تاریخ با خط تیره جدا شده، به اسلش تبدیل کنیم
                invoice_date = invoice_date.replace('-', '/')
                
                # بررسی فرمت تاریخ و اصلاح آن
                date_parts = invoice_date.split('/')
                if len(date_parts) == 3:
                    year = int(date_parts[0])
                    month = int(date_parts[1])
                    day = int(date_parts[2])
                    
                    # اگر سال کمتر از 100 است، 1300 اضافه کنیم
                    if year < 100:
                        year += 1300
                    
                    # ساخت تاریخ شمسی
                    jd = jdatetime.date(year, month, day)
                    # تبدیل به تاریخ میلادی
                    invoice_date = jd.togregorian()
                else:
                    raise ValueError("فرمت تاریخ نامعتبر است")
            except (ValueError, TypeError, AttributeError) as e:
                return JsonResponse({
                    'success': False,
                    'message': 'خطا در تبدیل تاریخ. لطفاً تاریخ را به فرمت صحیح وارد کنید (مثال: ۱۴۰۲/۰۱/۰۱)'
                }, status=400)

            try:
                customer = Customer.objects.get(id=customer_id)
            except Customer.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'طرف حساب انتخاب شده در سیستم وجود ندارد'
                }, status=400)
            except ValueError:
                return JsonResponse({
                    'success': False,
                    'message': 'شناسه طرف حساب نامعتبر است'
                }, status=400)

            description = request.POST.get('description', '')
            product_codes = request.POST.getlist('product_code')
            quantities = request.POST.getlist('quantity')
            prices = request.POST.getlist('price')
            discounts = request.POST.getlist('discount')
            profit_percentages = request.POST.getlist('profit_percentage')
            descriptions = request.POST.getlist('description')
            totals = request.POST.getlist('total')

            # Validate that there are product items
            if not product_codes:
                return JsonResponse({
                    'success': False,
                    'message': 'لطفاً حداقل یک کالا به فاکتور اضافه کنید'
                }, status=400)

            total_amount = 0
            for t in totals:
                try:
                    total_amount += int(str(t).replace(',', ''))
                except (ValueError, TypeError):
                    continue

            # Create invoice
            invoice = PurchaseInvoice.objects.create(
                invoice_number=invoice_number,
                invoice_date=invoice_date,
                customer=customer,
                created_by=request.user,
                total_amount=total_amount,
                description=description,
                status='registered',
            )

            # Process invoice items
            for i, code in enumerate(product_codes):
                if not code.strip():  # Skip empty product codes
                    continue
                    
                try:
                    product = Product.objects.get(code=code)
                    qty = int(quantities[i]) if i < len(quantities) and quantities[i] else 0
                    price = int(prices[i]) if i < len(prices) and prices[i] else product.purchase_price
                    discount = float(discounts[i]) if i < len(discounts) and discounts[i] else 0
                    profit_percentage = float(profit_percentages[i]) if i < len(profit_percentages) and profit_percentages[i] else 0
                    item_total = int(str(totals[i]).replace(',', '')) if i < len(totals) and totals[i] else 0
                    item_description = descriptions[i] if i < len(descriptions) else ''

                    if qty <= 0:
                        continue

                    PurchaseInvoiceItem.objects.create(
                        invoice=invoice,
                        product=product,
                        quantity=qty,
                        price=price,
                        discount=discount,
                        profit_percentage=profit_percentage,
                        total=item_total,
                        description=item_description,
                    )

                    # Update product
                    product.quantity += qty
                    product.purchase_price = price - (price * discount / 100)
                    product.profit_percentage = profit_percentage
                    product.price = product.purchase_price + (product.purchase_price * profit_percentage / 100)
                    product.save()

                except Product.DoesNotExist:
                    continue
                except (ValueError, TypeError) as e:
                    return JsonResponse({
                        'success': False,
                        'message': f'خطا در مقادیر ورودی برای کالای {code}: {str(e)}'
                    }, status=400)

            # Process settlement amounts
            try:
                invoice.settle_cash = int(request.POST.get('settle_cash', 0) or 0)
                invoice.settle_card = int(request.POST.get('settle_card', 0) or 0)
                invoice.settle_bank = int(request.POST.get('settle_bank', 0) or 0)
                invoice.settle_cheque = int(request.POST.get('settle_cheque', 0) or 0)
                invoice.settle_balance = int(request.POST.get('settle_balance', 0) or 0)
                invoice.settle_extra_discount = int(request.POST.get('settle_extra_discount', 0) or 0)
                invoice.save()
            except (ValueError, TypeError) as e:
                return JsonResponse({
                    'success': False,
                    'message': f'خطا در مقادیر تسویه: {str(e)}'
                }, status=400)

            return JsonResponse({
                'success': True,
                'redirect_url': reverse('products:purchase_invoice_detail', kwargs={'invoice_id': invoice.id})
            })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'خطا در ثبت فاکتور: {str(e)}'
        }, status=400)

def accounting_reports(request):
    invoices = Invoice.objects.all().order_by('-date')  # یا هر فیلد تاریخ ثبت
    return render(request, 'products/accounting_reports.html', {
        'invoices': invoices
    })

@login_required
def financial_year_list(request):
    years = FinancialYear.objects.all().order_by('-year')
    return render(request, 'products/accounting/financial_year_list.html', {'years': years})

@login_required
def financial_year_create(request):
    if request.method == 'POST':
        form = FinancialYearForm(request.POST)
        if form.is_valid():
            year = form.save(commit=False)
            year.created_by = request.user
            year.save()
            messages.success(request, 'سال مالی جدید با موفقیت ایجاد شد.')
            return redirect('financial_year_list')
    else:
        form = FinancialYearForm()
    
    return render(request, 'products/accounting/financial_year_form.html', {
        'form': form,
        'title': 'ایجاد سال مالی جدید'
    })

@login_required
def financial_year_edit(request, pk):
    year = get_object_or_404(FinancialYear, pk=pk)
    if request.method == 'POST':
        form = FinancialYearForm(request.POST, instance=year)
        if form.is_valid():
            form.save()
            messages.success(request, 'سال مالی با موفقیت ویرایش شد.')
            return redirect('financial_year_list')
    else:
        form = FinancialYearForm(instance=year)
    
    return render(request, 'products/accounting/financial_year_form.html', {
        'form': form,
        'title': 'ویرایش سال مالی'
    })

@login_required
def currency_list(request):
    currencies = Currency.objects.all().order_by('-is_default', 'code')
    return render(request, 'products/accounting/currency_list.html', {'currencies': currencies})

@login_required
def currency_create(request):
    if request.method == 'POST':
        form = CurrencyForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'ارز جدید با موفقیت ایجاد شد.')
            return redirect('currency_list')
    else:
        form = CurrencyForm()
    
    return render(request, 'products/accounting/currency_form.html', {
        'form': form,
        'title': 'تعریف ارز جدید'
    })

@login_required
def currency_edit(request, pk):
    currency = get_object_or_404(Currency, pk=pk)
    if request.method == 'POST':
        form = CurrencyForm(request.POST, instance=currency)
        if form.is_valid():
            form.save()
            messages.success(request, 'ارز با موفقیت ویرایش شد.')
            return redirect('currency_list')
    else:
        form = CurrencyForm(instance=currency)
    
    return render(request, 'products/accounting/currency_form.html', {
        'form': form,
        'title': 'ویرایش ارز'
    })
    
class AccountingReportListView(LoginRequiredMixin, ListView):
    model = AccountingReport
    template_name = 'products/accounting_report_list.html'
    context_object_name = 'reports'
    ordering = ['-created_at']
    paginate_by = 10

class AccountingReportDetailView(LoginRequiredMixin, DetailView):
    model = AccountingReport
    template_name = 'products/accounting_report_detail.html'
    context_object_name = 'report'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        report = self.get_object()
        
        # اضافه کردن جزئیات بدهکاران و بستانکاران
        context['debtors'] = AccountingReportDetail.objects.filter(
            report=report,
            transaction_type='debtor'
        ).order_by('-balance')[:10]  # 10 بدهکار برتر
        
        context['creditors'] = AccountingReportDetail.objects.filter(
            report=report,
            transaction_type='creditor'
        ).order_by('balance')[:10]  # 10 بستانکار برتر
        
        return context

class AccountingReportCreateView(LoginRequiredMixin, CreateView):
    model = AccountingReport
    template_name = 'products/accounting_report_create.html'
    fields = ['report_type']
    success_url = reverse_lazy('accounting-report-list')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['start_date_shamsi'] = forms.CharField(
            label="تاریخ شروع",
            widget=forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'تاریخ شروع را انتخاب کنید',
                'readonly': 'readonly'
            }),
            required=True
        )
        form.fields['end_date_shamsi'] = forms.CharField(
            label="تاریخ پایان",
            widget=forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'تاریخ پایان را انتخاب کنید',
                'readonly': 'readonly'
            }),
            required=True
        )
        return form

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        
        # تبدیل تاریخ‌های شمسی به میلادی
        start_date_shamsi = form.cleaned_data.get('start_date_shamsi')
        end_date_shamsi = form.cleaned_data.get('end_date_shamsi')
        
        if start_date_shamsi and end_date_shamsi:
            try:
                from .views import convert_shamsi_to_gregorian
                form.instance.start_date = convert_shamsi_to_gregorian(start_date_shamsi)
                form.instance.end_date = convert_shamsi_to_gregorian(end_date_shamsi)
            except ValueError as e:
                form.add_error(None, f"خطا در فرمت تاریخ: {str(e)}")
                return self.form_invalid(form)
        
        return super().form_valid(form)

    def get_initial(self):
        today = jdatetime.date.today()
        return {
            'report_type': 'monthly',
            'start_date_shamsi': today.replace(day=1).strftime('%Y/%m/%d'),  # اول ماه جاری
            'end_date_shamsi': today.strftime('%Y/%m/%d'),
        }


@login_required
@group_required('حسابداری')
def accounting_reports_menu(request):
    return render(request, 'products/accounting_reports_menu.html')        

@login_required
def financial_report_view(request, report_type):
    """نمایش گزارشات مالی"""
    
    # عناوین گزارش‌ها
    report_titles = {
        'profit_loss': 'گزارش سود و زیان',
        'sales_by_product': 'فروش به تفکیک کالا',
        'sales_by_customer': 'فروش به تفکیک مشتری',
        'product_profit': 'گزارش سود کالا',
        'customer_profit': 'گزارش سود مشتری',
        'accounts_receivable_payable': 'حساب‌های دریافتی و پرداختی',
        'cash_flow': 'گزارش گردش صندوق',
        'bank_statement': 'صورت حساب بانک',
        'checks': 'چک‌های دریافتی و پرداختی',
        'petty_cash': 'گزارش تنخواه'
    }
    
    context = {
        'report_type': report_type,
        'report_title': report_titles.get(report_type, 'گزارش مالی'),
        'current_date': timezone.now(),
    }
    
    # بر اساس نوع گزارش، داده‌های مختلف ارسال می‌کنیم
    if report_type == 'profit_loss':
        context.update(get_profit_loss_data(request))
    elif report_type == 'sales_by_product':
        context.update(get_sales_by_product_data(request))
    elif report_type == 'sales_by_customer':
        context.update(get_sales_by_customer_data(request))
    elif report_type == 'product_profit':
        context.update(get_product_profit_data(request))
    elif report_type == 'customer_profit':
        context.update(get_customer_profit_data(request))
    elif report_type == 'accounts_receivable_payable':
        context.update(get_accounts_receivable_payable_data(request))
    elif report_type == 'cash_flow':
        context.update(get_cash_flow_data(request))
    elif report_type == 'bank_statement':
        context.update(get_bank_statement_data(request))
    elif report_type == 'checks':
        context.update(get_checks_data(request))
    elif report_type == 'petty_cash':
        context.update(get_petty_cash_data(request))
    
    return render(request, f'products/reports/financial/{report_type}.html', context)

# =============================================================================
# گزارشات انبار و موجودی
# =============================================================================

@login_required
def inventory_report_view(request, report_type):
    """نمایش گزارشات انبار و موجودی"""
    
    report_titles = {
        'inventory_stock': 'گزارش موجودی کالا',
        'product_turnover': 'گزارش گردش کالا',
        'fast_slow_moving': 'کالاهای سریع و کند گردش',
        'quantity_sales': 'گزارش فروش تعدادی',
        'stock_depletion_estimate': 'تخمین زمان اتمام موجودی'
    }
    
    context = {
        'report_type': report_type,
        'report_title': report_titles.get(report_type, 'گزارش انبار'),
        'current_date': timezone.now(),
    }
    
    if report_type == 'inventory_stock':
        context.update(get_inventory_stock_data(request))
    elif report_type == 'product_turnover':
        context.update(get_product_turnover_data(request))
    elif report_type == 'fast_slow_moving':
        context.update(get_fast_slow_moving_data(request))
    elif report_type == 'quantity_sales':
        context.update(get_quantity_sales_data(request))
    elif report_type == 'stock_depletion_estimate':
        context.update(get_stock_depletion_data(request))
    
    return render(request, f'products/reports/inventory/{report_type}.html', context)

# =============================================================================
# گزارشات عملیاتی و سفارشات
# =============================================================================

@login_required
def operational_report_view(request, report_type):
    """نمایش گزارشات عملیاتی و سفارشات"""
    
    report_titles = {
        'order_status': 'گزارش وضعیت سفارشات',
        'shipping_delivery': 'گزارش ارسال و تحویل',
        'overdue_orders': 'گزارش سفارشات معوق',
        'purchase_invoices': 'گزارش فاکتورهای خرید',
        'price_change_history': 'تاریخ تغییر قیمت کالاها'
    }
    
    context = {
        'report_type': report_type,
        'report_title': report_titles.get(report_type, 'گزارش عملیاتی'),
        'current_date': timezone.now(),
    }
    
    if report_type == 'order_status':
        context.update(get_order_status_data(request))
    elif report_type == 'shipping_delivery':
        context.update(get_shipping_delivery_data(request))
    elif report_type == 'overdue_orders':
        context.update(get_overdue_orders_data(request))
    elif report_type == 'purchase_invoices':
        context.update(get_purchase_invoices_data(request))
    elif report_type == 'price_change_history':
        context.update(get_price_change_data(request))
    
    return render(request, f'products/reports/operational/{report_type}.html', context)

# =============================================================================
# گزارشات مشتریان
# =============================================================================

@login_required
def customer_report_view(request, report_type):
    """نمایش گزارشات مشتریان"""
    
    report_titles = {
        'customer_list': 'فهرست مشتریان',
        'debtors': 'گزارش بدهکاران',
        'creditors': 'گزارش بستانکاران',
        'customer_statements': 'صورتحساب مشتریان'
    }
    
    context = {
        'report_type': report_type,
        'report_title': report_titles.get(report_type, 'گزارش مشتریان'),
        'current_date': timezone.now(),
    }
    
    if report_type == 'customer_list':
        context.update(get_customer_list_data(request))
    elif report_type == 'debtors':
        context.update(get_debtors_data(request))
    elif report_type == 'creditors':
        context.update(get_creditors_data(request))
    elif report_type == 'customer_statements':
        context.update(get_customer_statements_data(request))
    
    return render(request, f'products/reports/customer/{report_type}.html', context)

@login_required
@group_required('حسابداری')
def financial_operations_menu(request):
    """
    نمایش منوی عملیات مالی
    """
    return render(request, 'products/financial_operations_menu.html')

@login_required
@group_required('حسابداری')
def accounting_reports_menu(request):
    """
    نمایش منوی گزارشات حسابداری
    """
    return render(request, 'products/accounting_reports_menu.html')

# در اینجا view های مربوط به هر عملیات مالی را اضافه می‌کنیم:



@login_required
@group_required('حسابداری')
def pay_to_customer_view(request):
    """
    پرداخت به طرف حساب مشتری
    """
    customers = Customer.objects.all()
    return render(request, 'financial_operations/pay_to_customer.html', {
        'customers': customers
    })

@login_required
@group_required('حسابداری')
def capital_investment_view(request):
    """
    سرمایه گذاری
    """
    return render(request, 'financial_operations/capital_investment.html')

@login_required
@group_required('حسابداری')
@transaction.atomic
def receive_from_bank_view(request):
    """
    دریافت از بانک - با منطق کامل و انتقال به صندوق
    """
    from .forms import ReceiveFromBankForm
    from .models import FinancialOperation, Fund
    if request.method == 'POST':
        form = ReceiveFromBankForm(request.POST)
        if form.is_valid():
            try:
                operation = form.save(commit=False)
                operation.operation_type = 'RECEIVE_FROM_BANK'  # دریافت از بانک
                operation.date = convert_shamsi_to_gregorian(form.cleaned_data['date_shamsi'])
                operation.created_by = request.user
                operation.status = 'CONFIRMED'
                operation.confirmed_by = request.user
                operation.confirmed_at = timezone.now()
                
                # تنظیم اطلاعات بانک از حساب انتخاب شده
                bank_account = form.cleaned_data['bank_account']
                operation.bank_name = bank_account.bank.name
                operation.account_number = bank_account.account_number
                
                operation.save()

                # به‌روزرسانی موجودی بانک (کسر مبلغ) - با استفاده از تابع محاسبه مجدد
                _update_bank_account_balance(bank_account.bank.name, bank_account.account_number)

                # انتقال به صندوق (افزایش موجودی صندوق)
                cash_fund, created = Fund.objects.get_or_create(
                    fund_type='CASH',
                    defaults={'name': 'صندوق نقدی', 'initial_balance': 0}
                )
                # فراخوانی متد محاسبه مجدد برای صندوق
                cash_fund.recalculate_balance()

                # The signal will now handle voucher creation automatically.
                success_message = f'عملیات دریافت از بانک با موفقیت ثبت شد. مبلغ {operation.amount:,} ریال از حساب {bank_account.title} به صندوق انتقال یافت.'
                request.session['success_message'] = success_message
                request.session['operation_type'] = 'receive_from_bank'
                return redirect('products:operation_confirmation')
            except Exception as e:
                messages.error(request, f'خطا در ثبت عملیات: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"خطا در فیلد {field}: {error}")
    else:
        form = ReceiveFromBankForm(initial={'operation_type': 'RECEIVE_FROM_BANK'})
    return render(request, 'financial_operations/receive_from_bank.html', {'form': form})

@login_required
@group_required('حسابداری')
@transaction.atomic
def pay_to_bank_view(request):
    """
    پرداخت به بانک - با منطق کامل
    """
    from .forms import BankOperationForm
    from .models import FinancialOperation
    if request.method == 'POST':
        form = BankOperationForm(request.POST)
        if form.is_valid():
            try:
                operation = form.save(commit=False)
                operation.operation_type = 'PAY_TO_BANK'
                operation.date = convert_shamsi_to_gregorian(form.cleaned_data['date_shamsi'])
                operation.created_by = request.user
                operation.status = 'CONFIRMED'
                operation.confirmed_by = request.user
                operation.confirmed_at = timezone.now()
                operation.save()

                # The signal will now handle voucher creation automatically.
                success_message = 'عملیات پرداخت به بانک با موفقیت ثبت شد.'
                request.session['success_message'] = success_message
                request.session['operation_type'] = 'pay_to_bank'
                return redirect('products:operation_confirmation')
            except Exception as e:
                messages.error(request, f'خطا در ثبت عملیات: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"خطا در فیلد {field}: {error}")
    else:
        form = BankOperationForm(initial={'operation_type': 'PAY_TO_BANK'})
    return render(request, 'financial_operations/pay_to_bank.html', {'form': form})

@login_required
@group_required('حسابداری')
def bank_transfer_view(request):
    """
    حواله بانکی
    """
    return render(request, 'financial_operations/bank_transfer.html')
@login_required
@group_required('حسابداری')
def cash_withdrawal_view(request):
    """
    برداشت نقدی از بانک
    """
    return render(request, 'financial_operations/cash_withdrawal.html')

@login_required
@group_required('حسابداری')
def payment_from_cash_view(request):
    """
    پرداخت از صندوق
    """
    return render(request, 'financial_operations/payment_from_cash.html')

@login_required
@group_required('حسابداری')
def payment_to_cash_view(request):
    """
    پرداخت به صندوق
    """
    return render(request, 'financial_operations/payment_to_cash.html')

# Financial Operations Views
@login_required
@group_required('حسابداری')
def fund_list_view(request):
    """
    نمایش لیست صندوق‌ها
    """
    funds = Fund.objects.filter(is_active=True).order_by('fund_type', 'name')
    
    # آمار حساب‌های بانکی
    bank_accounts = BankAccount.objects.filter(is_active=True)
    total_bank_accounts_balance = sum(account.current_balance for account in bank_accounts)
    
    # محاسبه مانده‌ها از دیتابیس
    total_cash_balance = 0
    total_bank_balance = 0
    
    for fund in funds:
        if fund.fund_type == 'CASH':
            # به‌روزرسانی مانده از عملیات‌ها
            fund.recalculate_balance()
            total_cash_balance += fund.current_balance
        elif fund.fund_type == 'BANK':
            # به‌روزرسانی مانده از عملیات‌ها
            fund.recalculate_balance()
            total_bank_balance += fund.current_balance
    
    # محاسبه مانده تنخواه از عملیات تنخواه
    total_petty_cash_balance = Fund.get_petty_cash_balance()
    
    context = {
        'funds': funds,
        'total_cash_balance': total_cash_balance,
        'total_bank_balance': total_bank_balance,
        'total_petty_cash_balance': total_petty_cash_balance,
        'total_bank_accounts_balance': total_bank_accounts_balance,
        'bank_accounts': bank_accounts,
    }
    
    return render(request, 'products/fund_list.html', context)


@login_required
@group_required('حسابداری')
def fund_create_view(request):
    """
    ایجاد صندوق جدید
    """
    if request.method == 'POST':
        form = FundForm(request.POST)
        if form.is_valid():
            fund = form.save(commit=False)
            fund.created_by = request.user
            fund.current_balance = fund.initial_balance
            fund.save()
            messages.success(request, 'صندوق با موفقیت ایجاد شد.')
            return redirect('products:fund_list')
    else:
        form = FundForm()
    
    return render(request, 'products/fund_form.html', {'form': form, 'title': 'ایجاد صندوق جدید'})


@login_required
@group_required('حسابداری')
def fund_edit_view(request, fund_id):
    """
    ویرایش صندوق
    """
    fund = get_object_or_404(Fund, id=fund_id)
    
    if request.method == 'POST':
        form = FundForm(request.POST, instance=fund)
        if form.is_valid():
            # ذخیره تغییرات موجودی اولیه
            old_initial_balance = fund.initial_balance
            fund = form.save(commit=False)
            
            # اگر موجودی اولیه تغییر کرده، موجودی فعلی را به‌روزرسانی کن
            if fund.initial_balance != old_initial_balance:
                # محاسبه تفاوت موجودی اولیه
                balance_difference = fund.initial_balance - old_initial_balance
                # به‌روزرسانی موجودی فعلی
                fund.current_balance += balance_difference
            
            fund.save()
            messages.success(request, 'صندوق با موفقیت ویرایش شد.')
            return redirect('products:fund_list')
    else:
        form = FundForm(instance=fund)
    
    return render(request, 'products/fund_form.html', {
        'form': form, 
        'fund': fund,
        'title': 'ویرایش صندوق'
    })


@login_required
@group_required('حسابداری')
def fund_detail_view(request, fund_id):
    """
    نمایش جزئیات صندوق
    """
    if not fund_id or fund_id == '':
        from django.http import Http404
        raise Http404("Fund not found")

    try:
        fund = get_object_or_404(Fund, id=fund_id)
    except (ValueError, TypeError):
        from django.http import Http404
        raise Http404("Invalid fund ID")

    # Recalculate balance to ensure it's up-to-date and consistent with list view
    fund.recalculate_balance()
    fund.refresh_from_db()

    all_operations_for_display = []
    
    # Define IN/OUT operations for clarity
    IN_OPERATIONS = ['RECEIVE_FROM_CUSTOMER', 'RECEIVE_FROM_BANK', 'PAYMENT_TO_CASH', 'CAPITAL_INVESTMENT', 'ADD']
    OUT_OPERATIONS = ['PAY_TO_CUSTOMER', 'PAY_TO_BANK', 'PAYMENT_FROM_CASH', 'CASH_WITHDRAWAL', 'WITHDRAW', 'EXPENSE', 'PETTY_CASH_WITHDRAW']

    # Fetch operations
    if fund.fund_type == 'PETTY_CASH':
        from .models import PettyCashOperation
        operations = PettyCashOperation.objects.all().order_by('date', 'created_at')
        for op in operations:
            source_info = ""
            if op.operation_type == 'ADD':
                source_info = f"شارژ تنخواه از {op.source_fund.name if op.source_fund else (op.source_bank_account.title if op.source_bank_account else 'نامشخص')}"
            elif op.operation_type == 'WITHDRAW':
                source_info = f"برداشت: {op.get_reason_display()}"
            
            op_data = {
                'date': op.date, 
                'description': op.description or source_info, 
                'amount': op.amount,
                'operation_type': op.operation_type, 
                'status': 'CONFIRMED', # Petty cash ops are always confirmed
                'type': 'petty_cash', 
                'operation': op
            }
            all_operations_for_display.append(op_data)
    else:
        financial_filter = Q(fund=fund)
        # Query for display (includes CANCELLED items)
        financial_ops_display = FinancialOperation.objects.filter(financial_filter).select_related('customer').order_by('date', 'created_at')

        for op in financial_ops_display:
            description = op.description
            if op.operation_type == 'RECEIVE_FROM_CUSTOMER' and op.customer:
                description = f"دریافت از مشتری {op.customer.get_full_name()} طی سند شماره {op.operation_number}"
            elif op.operation_type == 'PAY_TO_CUSTOMER' and op.customer:
                description = f"پرداخت به مشتری {op.customer.get_full_name()} طی سند شماره {op.operation_number}"

            op_data = {
                'date': op.date, 
                'description': description, 
                'amount': op.amount,
                'operation_type': op.operation_type, 
                'status': op.status,
                'type': 'financial', 
                'operation': op
            }
            all_operations_for_display.append(op_data)
        
        from .models import PettyCashOperation
        petty_cash_as_source = PettyCashOperation.objects.filter(source_fund=fund).order_by('date', 'created_at')
        for op in petty_cash_as_source:
            op_data = {
                'date': op.date, 
                'description': f"برداشت برای تنخواه: {op.get_reason_display()}",
                'amount': op.amount, 
                'operation_type': 'WITHDRAW', 
                'status': 'CONFIRMED',
                'type': 'petty_cash', 
                'operation': op
            }
            all_operations_for_display.append(op_data)

    # Sort all operations chronologically for display
    all_operations_for_display.sort(key=lambda x: (x['date'], x['operation'].created_at if hasattr(x.get('operation'), 'created_at') else timezone.now()))
    
    # Create a separate list for calculation, excluding cancelled items
    all_operations_for_calc = [op for op in all_operations_for_display if op.get('status') != 'CANCELLED']

    # Calculate totals for the stats box using the 'calc' list
    total_in = sum(op['amount'] for op in all_operations_for_calc if op['operation_type'] in IN_OPERATIONS)
    total_out = sum(op['amount'] for op in all_operations_for_calc if op['operation_type'] in OUT_OPERATIONS)

    # Start with the opening balance for running balance calculation
    running_balance = fund.initial_balance
    opening_balance_description = "مانده اول دوره"
    from .models import FinancialYear
    try:
        financial_year = FinancialYear.objects.get(start_date__lte=fund.created_at.date(), end_date__gte=fund.created_at.date())
        if financial_year.is_closed:
            opening_balance_description = "انتقالی از سال قبل"
    except FinancialYear.DoesNotExist:
        pass

    # Create the list for display, starting with the opening balance
    display_list = [{
        'date': fund.created_at,
        'description': opening_balance_description,
        'amount': fund.initial_balance,
        'operation_type': 'ADD' if fund.initial_balance >= 0 else 'WITHDRAW',
        'status': 'CONFIRMED',
        'type': 'system',
        'running_balance': running_balance,
        'operation': None,
    }]

    # Process all operations for display, but only update balance for non-cancelled items
    for op_data in all_operations_for_display:
        # Update running balance ONLY if the operation is not cancelled
        if op_data.get('status') != 'CANCELLED':
            if op_data['operation_type'] in IN_OPERATIONS:
                running_balance += op_data['amount']
            elif op_data['operation_type'] in OUT_OPERATIONS:
                running_balance -= op_data['amount']
        
        op_with_balance = op_data.copy()
        op_with_balance['running_balance'] = running_balance
        display_list.append(op_with_balance)
    
    # Reverse for display (newest first)
    display_list.reverse()

    # Create dynamic page title based on fund type and name
    fund_type_titles = {
        'CASH': 'جزئیات صندوق نقدی',
        'BANK': 'جزئیات حساب بانکی',
        'PETTY_CASH': 'جزئیات تنخواه',
        'OTHER': 'جزئیات صندوق',
    }
    
    fund_type_title = fund_type_titles.get(fund.fund_type, 'جزئیات صندوق')
    page_title = f"{fund_type_title} - {fund.name}"

    context = {
        'fund': fund,
        'operations': display_list,
        'total_in': total_in,
        'total_out': total_out,
        'current_balance': fund.current_balance,
        'balance_history': fund.get_balance_history()[:20] if hasattr(fund, 'get_balance_history') else [],
        'page_title': page_title
    }
    
    return render(request, 'products/fund_detail.html', context)


@login_required
@group_required('حسابداری')
def financial_operation_list_view(request):
    """
    نمایش لیست عملیات مالی
    """
    # Fetch all operations for display, including deleted ones
    operations_for_display = FinancialOperation.objects.all().order_by('-date', '-created_at')
    
    # Create a separate query for calculations which excludes deleted items
    operations_for_calc = operations_for_display.filter(is_deleted=False)

    # فیلترها
    operation_type = request.GET.get('operation_type')
    status = request.GET.get('status')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Apply filters to both queries
    if operation_type:
        operations_for_display = operations_for_display.filter(operation_type=operation_type)
        operations_for_calc = operations_for_calc.filter(operation_type=operation_type)
    if status:
        operations_for_display = operations_for_display.filter(status=status)
        operations_for_calc = operations_for_calc.filter(status=status)
    if date_from:
        try:
            from .views import convert_shamsi_to_gregorian
            date_from_gregorian = convert_shamsi_to_gregorian(date_from)
            operations_for_display = operations_for_display.filter(date__gte=date_from_gregorian)
            operations_for_calc = operations_for_calc.filter(date__gte=date_from_gregorian)
        except ValueError:
            pass
    if date_to:
        try:
            from .views import convert_shamsi_to_gregorian
            date_to_gregorian = convert_shamsi_to_gregorian(date_to)
            operations_for_display = operations_for_display.filter(date__lte=date_to_gregorian)
            operations_for_calc = operations_for_calc.filter(date__lte=date_to_gregorian)
        except ValueError:
            pass
    
    # آمار کلی - based on non-deleted and filtered operations
    total_amount = operations_for_calc.aggregate(Sum('amount'))['amount__sum'] or 0
    confirmed_operations = operations_for_calc.filter(status='CONFIRMED')
    confirmed_amount = confirmed_operations.aggregate(Sum('amount'))['amount__sum'] or 0
    
    context = {
        'operations': operations_for_display, # Pass the display query to the template
        'total_amount': total_amount,
        'confirmed_amount': confirmed_amount,
        'operation_types': FinancialOperation.OPERATION_TYPES,
        'status_choices': FinancialOperation.STATUS_CHOICES,
    }
    
    return render(request, 'products/financial_operation_list.html', context)


@login_required
@group_required('حسابداری')
def financial_operation_detail_view(request, operation_id):
    """
    نمایش جزئیات عملیات مالی
    """
    operation = get_object_or_404(FinancialOperation, id=operation_id)
    
    # New logic to find related orders for sales invoices (supports both new and old formats)
    related_orders = []
    if operation.operation_type == 'SALES_INVOICE' and operation.description:
        import re
        # New format: "فاکتور فروش بابت سفارشات: ORD-1, ORD-2"
        if 'فاکتور فروش بابت سفارشات:' in operation.description:
            try:
                # Extract the part after the colon and split by comma
                order_numbers_str = operation.description.split(':', 1)[1]
                order_numbers = [num.strip() for num in order_numbers_str.split(',') if num.strip()]
                if order_numbers:
                    related_orders = list(Order.objects.filter(order_number__in=order_numbers))
            except Exception as e:
                logger.error(f"Error parsing new invoice description format: {e}")
                related_orders = [] # Reset on error
        # Backorder format: "فاکتور فروش بابت بک اوردر: BO-..."
        elif 'فاکتور فروش بابت بک اوردر:' in operation.description:
            try:
                order_number_str = operation.description.split(':', 1)[1].strip()
                if order_number_str:
                    related_orders = list(Order.objects.filter(order_number=order_number_str))
            except Exception as e:
                logger.error(f"Error parsing backorder invoice description format: {e}")
                related_orders = []
        # Old format: "فاکتور فروش بابت سفارش شماره PARENT-ORD-1"
        else:
            match = re.search(r'سفارش شماره (.*?)$', operation.description)
            if match:
                order_number = match.group(1).strip()
                # For old format, we find the parent and then its sub-orders that were shipped
                parent_order = Order.objects.filter(order_number=order_number).first()
                if parent_order:
                    # Attempt to find the specific sub-orders that were part of a shipment
                    # This is an approximation for backward compatibility
                    shipped_sub_orders = parent_order.sub_orders.filter(status='delivered')
                    if shipped_sub_orders.exists():
                        related_orders = list(shipped_sub_orders)
                    else:
                        # Fallback to just showing the parent if no delivered sub-orders are found
                        related_orders = [parent_order]


    context = {
        'operation': operation,
        'transactions': operation.transactions.all(),
        'related_orders': related_orders, # Use 'related_orders' (plural)
    }
    
    return render(request, 'products/financial_operation_detail.html', context)


def _restore_check_statuses_on_operation_delete(operation):
    """
    بازگردانی وضعیت چک‌ها به حالت قبلی هنگام حذف عملیات مالی
    """
    from .models import Check, ReceivedCheque
    
    try:
        # بازگردانی چک‌های صادر شده به حالت UNUSED
        issued_checks = operation.issued_checks.all()
        if issued_checks.exists():
            print(f"Restoring {issued_checks.count()} issued checks to UNUSED status")
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
        spent_cheques = operation.spent_cheques.all()
        if spent_cheques.exists():
            print(f"Restoring {spent_cheques.count()} spent cheques to RECEIVED status")
            for cheque in spent_cheques:
                cheque.status = 'RECEIVED'
                cheque.recipient_name = ''  # پاک کردن نام گیرنده
                cheque.save()
            # حذف ارتباط با عملیات مالی
            operation.spent_cheques.clear()
        
        # بازگردانی چک‌های واگذار شده به حالت RECEIVED
        deposited_cheques = operation.received_cheques.filter(status='DEPOSITED')
        if deposited_cheques.exists():
            print(f"Restoring {deposited_cheques.count()} deposited cheques to RECEIVED status")
            for cheque in deposited_cheques:
                cheque.status = 'RECEIVED'
                cheque.deposited_bank_account = None  # پاک کردن مرجع بانک
                cheque.save()
            
        print(f"Successfully restored check statuses for operation {operation.operation_number}")
        
    except Exception as e:
        print(f"Error restoring check statuses for operation {operation.operation_number}: {e}")


def _update_bank_account_balance(bank_name, account_number):
    """
    موجودی حساب بانکی را بر اساس عملیات‌های مالی حذف نشده، مجدداً محاسبه و به‌روزرسانی می‌کند.
    """
    from .models import BankAccount, FinancialOperation
    from django.db.models import Sum

    try:
        bank_account = BankAccount.objects.get(
            bank__name=bank_name,
            account_number=account_number
        )

        # تعریف عملیات‌های بستانکار (واریز) و بدهکار (برداشت)
        CREDIT_OPS = ['RECEIVE_FROM_CUSTOMER', 'PAY_TO_BANK', 'CAPITAL_INVESTMENT']
        DEBIT_OPS = ['PAY_TO_CUSTOMER', 'RECEIVE_FROM_BANK', 'BANK_TRANSFER']

        # دریافت تمام عملیات‌های تایید شده و حذف نشده برای این حساب بانکی
        operations = FinancialOperation.objects.filter(
            bank_name=bank_account.bank.name,
            account_number=bank_account.account_number,
            status='CONFIRMED',
            is_deleted=False
        )

        total_credit = operations.filter(operation_type__in=CREDIT_OPS).aggregate(Sum('amount'))['amount__sum'] or 0
        total_debit = operations.filter(operation_type__in=DEBIT_OPS).aggregate(Sum('amount'))['amount__sum'] or 0

        # محاسبه مجدد موجودی فعلی
        bank_account.current_balance = bank_account.initial_balance + total_credit - total_debit
        bank_account.save(update_fields=['current_balance'])

    except BankAccount.DoesNotExist:
        # اگر حساب بانکی وجود نداشته باشد، کاری انجام نمی‌شود
        pass




@login_required
@group_required('حسابداری')
def financial_operation_delete_view(request, operation_id):
    """
    حذف نرم عملیات مالی و به‌روزرسانی موجودی حساب بانکی و مشتری
    """
    operation = get_object_or_404(FinancialOperation, id=operation_id)
    
    if request.method == 'POST':
        operation_number = operation.operation_number
        bank_name = operation.bank_name
        account_number = operation.account_number
        customer = operation.customer

        # بازگردانی وضعیت چک‌های مرتبط قبل از حذف عملیات
        _restore_check_statuses_on_operation_delete(operation)

        # حذف نرم عملیات
        operation.soft_delete(request.user)

        # اگر عملیات مربوط به یک حساب بانکی بود، موجودی آن حساب را به‌روزرسانی می‌کنیم
        if bank_name and account_number:
            _update_bank_account_balance(bank_name, account_number)

        # اگر عملیات مربوط به یک مشتری بود، موجودی آن مشتری را به‌روزرسانی می‌کنیم
        if customer:
            # Use get_or_create to ensure the balance object exists, then update it.
            # This is more robust than the previous try/except block.
            customer_balance, created = CustomerBalance.objects.get_or_create(customer=customer)
            customer_balance.update_balance()

        messages.success(request, f'عملیات مالی {operation_number} با موفقیت حذف شد و موجودی‌ها به‌روز گردید.')
        referer_url = request.META.get('HTTP_REFERER', reverse('products:financial_operation_list'))
        return HttpResponseRedirect(referer_url)
    
    context = {
        'operation': operation,
        'title': 'حذف عملیات مالی'
    }
    return render(request, 'financial_operations/operation_confirm_delete.html', context)


@login_required
@group_required('حسابداری')
@transaction.atomic
def financial_operation_edit_view(request, operation_id):
    """
    ویرایش عملیات مالی و به‌روزرسانی موجودی حساب بانکی
    """
    from .forms import FinancialOperationEditForm
    
    operation = get_object_or_404(FinancialOperation, id=operation_id)
    
    if request.method == 'POST':
        form = FinancialOperationEditForm(request.POST, instance=operation)
        if form.is_valid():
            operation = form.save(commit=False)
            
            # Handle cheque data if payment method is cheque
            if operation.payment_method == 'cheque':
                cheques_data = {}
                for key, value in request.POST.items():
                    if key.startswith('cheque_'):
                        parts = key.split('_')
                        cheque_id = parts[1]
                        field_name = '_'.join(parts[2:])
                        if cheque_id not in cheques_data:
                            cheques_data[cheque_id] = {}
                        cheques_data[cheque_id][field_name] = value
                
                total_cheque_amount = Decimal('0')
                for cheque_id, data in cheques_data.items():
                    try:
                        cheque = ReceivedCheque.objects.get(id=cheque_id, financial_operation=operation)
                        
                        # Update fields
                        amount_value = data.get('amount', '0')
                        # Convert to string first, then remove commas
                        amount_str = str(amount_value).replace(',', '')
                        cheque.amount = Decimal(amount_str)
                        
                        # Handle date conversion safely
                        due_date_str = data.get('due_date', '')
                        if due_date_str:
                            try:
                                cheque.due_date = convert_shamsi_to_gregorian(due_date_str)
                            except Exception as e:
                                print(f"Error converting date {due_date_str}: {e}")
                                # Keep the original date if conversion fails
                        
                        cheque.bank_name = data.get('bank_name', '')
                        cheque.branch_name = data.get('branch_name', '')
                        cheque.sayadi_id = data.get('sayadi_id', '')
                        cheque.owner_name = data.get('owner_name', '')
                        cheque.endorsement = data.get('endorsement', '')
                        cheque.series = data.get('series', '')
                        cheque.serial = data.get('serial', '')
                        cheque.national_id = data.get('national_id', '')
                        cheque.account_number = data.get('account_number', '')
                        cheque.save()
                        
                        total_cheque_amount += cheque.amount
                    except ReceivedCheque.DoesNotExist:
                        # Handle case where cheque might not exist or belong to this operation
                        continue
                
                # Update the main operation amount to the sum of its cheques
                operation.amount = total_cheque_amount

            operation.updated_at = timezone.now()
            operation.save()
            
            # Save the many-to-many data for the form
            form.save_m2m()

            # علامت‌گذاری به عنوان اصلاح شده
            operation.mark_as_modified(request.user)

            # اگر عملیات مربوط به یک حساب بانکی بود، موجودی آن حساب را به‌روزرسانی می‌کنیم
            if operation.bank_name and operation.account_number:
                _update_bank_account_balance(operation.bank_name, operation.account_number)
            
            # Update customer balance if linked
            if operation.customer:
                customer_balance, created = CustomerBalance.objects.get_or_create(customer=operation.customer)
                customer_balance.update_balance()

            messages.success(request, f'عملیات مالی {operation.operation_number} با موفقیت ویرایش شد و سوابق به‌روز گردید.')
            return redirect('products:financial_operation_detail', operation_id=operation.id)
    else:
        form = FinancialOperationEditForm(instance=operation)
    
    # Fetch related cheques if the payment method is cheque
    related_cheques = None
    if operation.payment_method == 'cheque':
        related_cheques = operation.received_cheques.all()

    # Fetch all active banks for the dropdown
    from .models import Bank
    banks = Bank.objects.filter(is_active=True).order_by('name')

    context = {
        'form': form,
        'operation': operation,
        'related_cheques': related_cheques,
        'banks': banks,
        'title': 'ویرایش عملیات مالی'
    }
    return render(request, 'financial_operations/operation_edit.html', context)


@login_required
@group_required('حسابداری')
@transaction.atomic
def receive_from_customer_view(request):
    """
    دریافت از مشتری - با منطق کامل
    """
    from .models import Bank
    from .forms import ReceivedCheckForm

    if request.method == 'POST':
        form = ReceiveFromCustomerForm(request.POST)
        if form.is_valid():
            try:
                operation = form.save(commit=False)
                operation.operation_type = 'RECEIVE_FROM_CUSTOMER'
                operation.date = convert_shamsi_to_gregorian(form.cleaned_data['date_shamsi'])
                operation.created_by = request.user
                operation.status = 'CONFIRMED'
                operation.confirmed_by = request.user
                operation.confirmed_at = timezone.now()

                if operation.payment_method == 'cash':
                    # Explicitly link cash operations to the cash fund
                    cash_fund = Fund.objects.filter(fund_type='CASH').first()
                    if cash_fund:
                        operation.fund = cash_fund
                elif operation.payment_method == 'bank_transfer':
                    bank_account_id = request.POST.get('bank_account')
                    if not bank_account_id:
                        form.add_error('bank_account', 'برای حواله بانکی، انتخاب حساب بانکی الزامی است.')
                        customers = Customer.objects.all().order_by('first_name', 'last_name')
                        banks = Bank.objects.filter(is_active=True).order_by('name')
                        return render(request, 'financial_operations/receive_from_customer.html', {
                            'form': form,
                            'customers': customers,
                            'banks': banks
                        })

                    try:
                        bank_account = BankAccount.objects.get(id=bank_account_id, is_active=True)
                    except BankAccount.DoesNotExist:
                        form.add_error('bank_account', 'حساب بانکی انتخاب شده معتبر نیست.')
                        customers = Customer.objects.all().order_by('first_name', 'last_name')
                        banks = Bank.objects.filter(is_active=True).order_by('name')
                        return render(request, 'financial_operations/receive_from_customer.html', {
                            'form': form,
                            'customers': customers,
                            'banks': banks
                        })
                    
                    operation.fund = None
                    operation.bank_account = bank_account
                    _update_bank_account_balance(bank_account.bank.name, bank_account.account_number)
                    operation.bank_name = bank_account.bank.name
                    operation.account_number = bank_account.account_number
                    if not operation.description:
                        operation.description = f"دریافت حواله بانکی از {operation.customer.get_full_name()} به حساب {bank_account.title}"
                
                elif operation.payment_method == 'pos':
                    device = operation.card_reader_device
                    if not device:
                        form.add_error('card_reader_device', 'برای پرداخت با پوز، انتخاب دستگاه الزامی است.')
                        customers = Customer.objects.all().order_by('first_name', 'last_name')
                        banks = Bank.objects.filter(is_active=True).order_by('name')
                        return render(request, 'financial_operations/receive_from_customer.html', {
                            'form': form,
                            'customers': customers,
                            'banks': banks
                        })

                    bank_account = device.bank_account
                    if not bank_account:
                        messages.error(request, f"دستگاه کارتخوان '{device.name}' به هیچ حساب بانکی متصل نیست.")
                        customers = Customer.objects.all().order_by('first_name', 'last_name')
                        banks = Bank.objects.filter(is_active=True).order_by('name')
                        return render(request, 'financial_operations/receive_from_customer.html', {
                            'form': form,
                            'customers': customers,
                            'banks': banks
                        })
                    
                    operation.fund = None
                    _update_bank_account_balance(bank_account.bank.name, bank_account.account_number)
                    operation.bank_name = bank_account.bank.name
                    operation.account_number = bank_account.account_number
                    if not operation.description:
                        operation.description = f"دریافت از {operation.customer.get_full_name()} با دستگاه پوز {device.name}"
                
                elif operation.payment_method == 'cheque':
                    cheques_data_json = request.POST.get('cheques_data')
                    if not cheques_data_json:
                        cheques_data_json = '[]'
                    cheques_data = json.loads(cheques_data_json)
                    
                    if not cheques_data:
                        messages.error(request, 'برای ثبت دریافت چکی، حداقل یک چک باید اضافه شود.')
                        customers = Customer.objects.all().order_by('first_name', 'last_name')
                        banks = Bank.objects.filter(is_active=True).order_by('name')
                        return render(request, 'financial_operations/receive_from_customer.html', {'form': form, 'customers': customers, 'banks': banks})

                    total_cheque_amount = 0
                    saved_cheques = []
                    for cheque_data in cheques_data:
                        # Convert amount to Decimal
                        amount = Decimal(cheque_data['amount'].replace(',', ''))
                        total_cheque_amount += amount
                        
                        # Convert date
                        due_date_gregorian = convert_shamsi_to_gregorian(cheque_data['due_date'])
                        
                        cheque = ReceivedCheque.objects.create(
                            customer=operation.customer,
                            endorsement=cheque_data.get('endorsement'),
                            due_date=due_date_gregorian,
                            bank_name=cheque_data['bank_name'],
                            branch_name=cheque_data.get('branch_name'),
                            series=cheque_data.get('series'),
                            serial=cheque_data.get('serial'),
                            sayadi_id=cheque_data['sayadi_id'],
                            amount=amount,
                            owner_name=cheque_data['owner_name'],
                            national_id=cheque_data.get('national_id'),
                            account_number=cheque_data['account_number'],
                            created_by=request.user
                        )
                        saved_cheques.append(cheque)

                    operation.amount = total_cheque_amount
                    if not operation.description:
                        operation.description = f"دریافت {len(saved_cheques)} فقره چک از {operation.customer.get_full_name()}"
                
                operation.save()

                # If cheques were processed, link them to the operation
                if operation.payment_method == 'cheque' and 'saved_cheques' in locals():
                    for cheque in saved_cheques:
                        cheque.financial_operation = operation
                        cheque.save(update_fields=['financial_operation'])
                
                # به‌روزرسانی موجودی مشتری
                customer_balance, created = CustomerBalance.objects.get_or_create(
                    customer=operation.customer,
                    defaults={'current_balance': 0, 'total_received': 0, 'total_paid': 0}
                )
                customer_balance.update_balance()
                
                # نمایش پیام تأیید
                success_message = f'عملیات دریافت از مشتری با موفقیت ثبت شد. شماره عملیات: {operation.operation_number}'
                
                # ذخیره پیام در session برای نمایش در صفحه تأیید
                request.session['success_message'] = success_message
                request.session['operation_type'] = 'receive_from_customer'
                return redirect('products:operation_confirmation')
                
            except Exception as e:
                messages.error(request, f'خطا در ثبت عملیات: {str(e)}')
                return redirect('products:financial_operations_menu')
    else:
        form = ReceiveFromCustomerForm()
    
    customers = Customer.objects.all().order_by('first_name', 'last_name')
    banks = Bank.objects.filter(is_active=True).order_by('name')
    cheque_form = ReceivedCheckForm()

    return render(request, 'financial_operations/receive_from_customer.html', {
        'form': form,
        'customers': customers,
        'banks': banks,
        'cheque_form': cheque_form
    })


@login_required
@group_required('حسابداری')
@transaction.atomic
def pay_to_customer_view(request):
    """
    پرداخت به مشتری - با منطق کامل
    """
    if request.method == 'POST':
        # Check if this is a form submission after spending checks
        # If so, don't create another financial operation
        if request.POST.get('spent_checks_processed') == 'true':
            success_message = 'عملیات پرداخت به مشتری با موفقیت ثبت شد.'
            request.session['success_message'] = success_message
            request.session['operation_type'] = 'pay_to_customer'
            return redirect('products:operation_confirmation')
        
        # This view will now only handle the main form submission (cash, pos, etc.)
        # The check issuance will be handled by a separate AJAX view.
        form = PayToCustomerForm(request.POST)
        if form.is_valid():
            operation = form.save(commit=False)
            operation.operation_type = 'PAY_TO_CUSTOMER'
            operation.date = convert_shamsi_to_gregorian(form.cleaned_data['date_shamsi'])
            operation.created_by = request.user
            operation.status = 'CONFIRMED'
            operation.confirmed_by = request.user
            operation.confirmed_at = timezone.now()

            if operation.payment_method == 'cash':
                cash_fund = Fund.objects.filter(fund_type='CASH').first()
                if cash_fund:
                    operation.fund = cash_fund
            
            operation.save()
            
            customer_balance, created = CustomerBalance.objects.get_or_create(
                customer=operation.customer
            )
            customer_balance.update_balance()
            
            success_message = 'عملیات پرداخت به مشتری با موفقیت ثبت شد.'
            request.session['success_message'] = success_message
            request.session['operation_type'] = 'pay_to_customer'
            return redirect('products:operation_confirmation')
    else:
        form = PayToCustomerForm()

    issue_check_form = IssueCheckForm()
    customers = Customer.objects.all().order_by('first_name', 'last_name')
    bank_accounts = BankAccount.objects.filter(is_active=True)
    
    # Serialize bank accounts for JS
    bank_accounts_list = list(bank_accounts.values('id', 'title'))
    bank_accounts_json = json.dumps(bank_accounts_list)

    return render(request, 'financial_operations/pay_to_customer.html', {
        'form': form,
        'issue_check_form': issue_check_form,
        'customers': customers,
        'bank_accounts': bank_accounts,
        'bank_accounts_json': bank_accounts_json,
    })


@login_required
@group_required('حسابداری')
@transaction.atomic
def bank_operation_view(request, operation_type):
    """
    عملیات بانکی - دریافت از بانک یا پرداخت به بانک
    """
    if request.method == 'POST':
        form = BankOperationForm(request.POST)
        if form.is_valid():
            operation = form.save(commit=False)
            operation.operation_type = operation_type
            operation.date = convert_shamsi_to_gregorian(form.cleaned_data['date_shamsi'])
            operation.created_by = request.user
            operation.status = 'CONFIRMED'
            operation.confirmed_by = request.user
            operation.confirmed_at = timezone.now()
            operation.save()
            
            messages.success(request, f'عملیات {operation.get_operation_type_display()} با موفقیت ثبت شد.')
            return redirect('products:financial_operation_list')
    else:
        form = BankOperationForm()
    
    title = 'دریافت از بانک' if operation_type == 'RECEIVE_FROM_BANK' else 'پرداخت به بانک'
    template = 'receive_from_bank.html' if operation_type == 'RECEIVE_FROM_BANK' else 'pay_to_bank.html'
    
    return render(request, f'financial_operations/{template}', {
        'form': form,
        'title': title
    })
def bank_transfer_view(request):
    """
    حواله بانکی - با انتخاب حساب‌های تعریف شده و بانک‌های موجود
    """
    if request.method == 'POST':
        form = BankTransferForm(request.POST)
        if form.is_valid():
            try:
                # دریافت اطلاعات فرم
                amount = form.cleaned_data['amount']
                date_shamsi = form.cleaned_data['date_shamsi']
                description = form.cleaned_data['description']
                from_bank_account = form.cleaned_data['from_bank_account']
                recipient = form.cleaned_data['recipient']
                
                # بررسی موجودی حساب مبدا
                if from_bank_account.current_balance < amount:
                    messages.error(request, f'موجودی حساب {from_bank_account.title} کافی نیست. موجودی فعلی: {from_bank_account.current_balance:,} ریال')
                    customers = Customer.objects.all().order_by('first_name', 'last_name')
                    return render(request, 'financial_operations/bank_transfer.html', {'form': form, 'customers': customers})

                # ایجاد یک عملیات مالی واحد از نوع حواله بانکی
                operation = FinancialOperation.objects.create(
                    operation_type='BANK_TRANSFER',
                    date=convert_shamsi_to_gregorian(date_shamsi),
                    amount=amount,
                    customer=recipient,
                    bank_name=from_bank_account.bank.name,
                    account_number=from_bank_account.account_number,
                    payment_method='bank_transfer',
                    description=f"حواله از حساب {from_bank_account.title} به {recipient.get_full_name()} - {description}",
                    created_by=request.user,
                    status='CONFIRMED',
                    confirmed_by=request.user,
                    confirmed_at=timezone.now()
                )

                # The signal for FinancialOperation's post_save will automatically handle:
                # 1. Updating customer balance (customer_balance.update_balance())
                # 2. Updating the source bank account's balance via fund recalculation
                # 3. Creating the accounting voucher (create_voucher_for_financial_operation)

                success_message = f'حواله بانکی به مبلغ {amount:,} ریال با موفقیت ثبت شد. شماره عملیات: {operation.operation_number}'
                
                request.session['success_message'] = success_message
                request.session['operation_type'] = 'bank_transfer'
                return redirect('products:operation_confirmation')

            except Exception as e:
                import traceback
                traceback.print_exc()
                messages.error(request, f'خطا در ثبت عملیات حواله بانکی: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"خطا در فیلد '{form.fields[field].label}': {error}")

    else:
        form = BankTransferForm()
    
    customers = Customer.objects.all().order_by('first_name', 'last_name')
    return render(request, 'financial_operations/bank_transfer.html', {
        'form': form,
        'customers': customers
    })


@login_required
@group_required('حسابداری')
@transaction.atomic
def cash_operation_view(request, operation_type):
    """
    عملیات صندوق - پرداخت به صندوق یا پرداخت از صندوق
    """
    if request.method == 'POST':
        form = CashOperationForm(request.POST)
        if form.is_valid():
            operation = form.save(commit=False)
            operation.operation_type = operation_type
            operation.date = convert_shamsi_to_gregorian(form.cleaned_data['date_shamsi'])
            operation.created_by = request.user
            operation.status = 'CONFIRMED'
            operation.confirmed_by = request.user
            operation.confirmed_at = timezone.now()
            operation.save()
            
            messages.success(request, f'عملیات {operation.get_operation_type_display()} با موفقیت ثبت شد.')
            return redirect('products:financial_operation_list')
    else:
        form = CashOperationForm()
    
    title = 'پرداخت به صندوق' if operation_type == 'PAYMENT_TO_CASH' else 'پرداخت از صندوق'
    template = 'payment_to_cash.html' if operation_type == 'PAYMENT_TO_CASH' else 'payment_from_cash.html'
    
    return render(request, f'financial_operations/{template}', {
        'form': form,
        'title': title
    })


@login_required
@group_required('حسابداری')
@transaction.atomic
def capital_investment_view(request):
    """
    سرمایه گذاری - با منطق کامل
    """
    if request.method == 'POST':
        form = CapitalInvestmentForm(request.POST)
        if form.is_valid():
            operation = form.save(commit=False)
            operation.operation_type = 'CAPITAL_INVESTMENT'
            operation.date = convert_shamsi_to_gregorian(form.cleaned_data['date_shamsi'])
            operation.created_by = request.user
            operation.status = 'CONFIRMED'
            operation.confirmed_by = request.user
            operation.confirmed_at = timezone.now()
            operation.save()
            
            messages.success(request, 'عملیات سرمایه گذاری با موفقیت ثبت شد.')
            return redirect('products:financial_operation_list')
    else:
        form = CapitalInvestmentForm()
    
    return render(request, 'financial_operations/capital_investment.html', {'form': form})


@login_required
@group_required('حسابداری')
def petty_cash_view(request):
    """
    عملیات تنخواه - با منطق کامل
    """
    if request.method == 'POST':
        print("=== DEBUG: POST request received ===")
        print(f"POST data: {request.POST}")
        
        form = PettyCashOperationForm(request.POST)
        print(f"Form is valid: {form.is_valid()}")
        
        if form.is_valid():
            print("=== DEBUG: Form is valid ===")
            print(f"Cleaned data: {form.cleaned_data}")
            
            try:
                # Use transaction.atomic to ensure data consistency
                with transaction.atomic():
                    operation = form.save(commit=False)
                    operation.date = convert_shamsi_to_gregorian(form.cleaned_data['date_shamsi'])
                    operation.created_by = request.user
                    
                    print(f"Operation type: {operation.operation_type}")
                    print(f"Amount: {operation.amount}")
                    print(f"Date: {operation.date}")
                    
                    # منطق جدید برای عملیات تنخواه
                    if operation.operation_type == 'ADD':
                        print("=== DEBUG: Processing ADD operation ===")
                        # افزودن به تنخواه
                        source_fund = form.cleaned_data.get('source_fund')
                        source_bank_account = form.cleaned_data.get('source_bank_account')
                        
                        print(f"Source fund: {source_fund}")
                        print(f"Source bank account: {source_bank_account}")
                        
                        # به‌روزرسانی موجودی منبع و ثبت گردش
                        if source_fund:
                            print(f"Updating fund balance: {source_fund.current_balance} -> {source_fund.current_balance - operation.amount}")
                            source_fund.current_balance -= operation.amount
                            source_fund.save()
                            
                            # ثبت گردش صندوق منبع (خروجی)
                            source_fund.add_transaction(
                                transaction_type='OUT',
                                amount=operation.amount,
                                description=f"برداشت برای تنخواه - {operation.get_reason_display()}",
                                reference_id=str(operation.id),
                                reference_type='PettyCashOperation'
                            )
                            
                        elif source_bank_account:
                            print(f"Updating bank account balance for: {source_bank_account.title}")
                            # Recalculate the source bank account's balance using the helper function
                            _update_bank_account_balance(source_bank_account.bank.name, source_bank_account.account_number)
                        
                        # ذخیره عملیات تنخواه (بدون ایجاد صندوق)
                        operation.save()
                        print(f"Petty cash operation saved: {operation.operation_type} - {operation.amount}")
                        
                        # The signal will now handle voucher creation automatically.
                        operation.save()
                        success_message = f'مبلغ {operation.amount:,} تومان با موفقیت به تنخواه اضافه شد.'
                        
                        # ذخیره پیام در session برای نمایش در صفحه تأیید
                        request.session['success_message'] = success_message
                        request.session['operation_type'] = 'petty_cash_add'
                        return redirect('products:operation_confirmation')
                        
                    else:
                        print("=== DEBUG: Processing WITHDRAW operation ===")
                        # برداشت از تنخواه
                        operation.save()
                        
                        # The signal will now handle voucher creation automatically.
                        success_message = f'مبلغ {operation.amount:,} تومان با موفقیت از تنخواه برداشت شد.'
                        
                        # ذخیره پیام در session برای نمایش در صفحه تأیید
                        request.session['success_message'] = success_message
                        request.session['operation_type'] = 'petty_cash_withdraw'
                        return redirect('products:operation_confirmation')
                    
                    print("=== DEBUG: Operation saved successfully ===")
                
            except Exception as e:
                print(f"=== DEBUG: Error in operation processing: {e} ===")
                import traceback
                traceback.print_exc()
                messages.error(request, f'خطا در ثبت عملیات: {str(e)}')
        else:
            print("=== DEBUG: Form is not valid ===")
            print(f"Form errors: {form.errors}")
            for field, errors in form.errors.items():
                print(f"Field {field}: {errors}")
            messages.error(request, 'خطا در فرم. لطفاً اطلاعات را بررسی کنید.')
    else:
        form = PettyCashOperationForm()
    
    # نمایش موجودی تنخواه
    petty_cash_fund = Fund.objects.filter(fund_type='PETTY_CASH').first()
    petty_cash_operations = PettyCashOperation.objects.all().order_by('-date', '-created_at')[:20]
    
    # دریافت لیست صندوق‌ها و حساب‌های بانکی
    available_funds = Fund.objects.filter(fund_type__in=['CASH', 'PETTY_CASH'], is_active=True)
    available_bank_accounts = BankAccount.objects.filter(is_active=True)
    
    context = {
        'form': form,
        'petty_cash_fund': petty_cash_fund,
        'petty_cash_operations': petty_cash_operations,
        'available_funds': available_funds,
        'available_bank_accounts': available_bank_accounts
    }
    
    return render(request, 'products/petty_cash.html', context)


@login_required
@group_required('حسابداری')
def customer_balance_list_view(request):
    """
    نمایش لیست موجودی مشتریان
    """
    # Recalculate the balance for all customers to ensure data is fresh.
    customers = Customer.objects.all()
    for customer in customers:
        customer_balance, created = CustomerBalance.objects.get_or_create(customer=customer)
        # Use the robust update_balance method from the model
        customer_balance.update_balance()

    customer_balances = CustomerBalance.objects.select_related('customer').all().order_by('-current_balance')
    
    # فیلترها
    search = request.GET.get('search')
    if search:
        customer_balances = customer_balances.filter(
            Q(customer__first_name__icontains=search) |
            Q(customer__last_name__icontains=search) |
            Q(customer__store_name__icontains=search)
        )
    
    # آمار کلی - محاسبه از عملیات‌های واقعی
    all_operations = FinancialOperation.objects.filter(
        customer__isnull=False,
        is_deleted=False
    )
    
    # عملیات‌هایی که مشتری بدهکار می‌شود (ما به آنها پرداخت کردیم)
    debit_ops = ['PAY_TO_CUSTOMER', 'BANK_TRANSFER', 'CHECK_BOUNCE', 'SALES_INVOICE']
    total_paid = all_operations.filter(
        operation_type__in=debit_ops
    ).aggregate(Sum('amount'))['amount__sum'] or 0
    
    # عملیات‌هایی که مشتری بستانکار می‌شود (آنها به ما پرداخت کردند یا چک ما برگشت خورد)
    credit_ops = ['RECEIVE_FROM_CUSTOMER', 'SPENT_CHEQUE_RETURN', 'ISSUED_CHECK_BOUNCE', 'PURCHASE_INVOICE']
    total_received = all_operations.filter(
        operation_type__in=credit_ops
    ).aggregate(Sum('amount'))['amount__sum'] or 0
    
    # موجودی کل = بدهکاری - بستانکاری (مثبت یعنی ما به مشتریان بدهکاریم، منفی یعنی مشتریان به ما بدهکارند)
    total_balance = total_paid - total_received
    
    context = {
        'customer_balances': customer_balances,
        'total_balance': total_balance,
        'total_received': total_received,  # مجموع بستانکاری (مشتریان به ما پرداخت کردند)
        'total_paid': total_paid,          # مجموع بدهکاری (ما به مشتریان پرداخت کردیم)
    }
    
    return render(request, 'products/customer_balance_list.html', context)


@login_required
@group_required('حسابداری')
def customer_balance_detail_view(request, customer_id):
    """
    نمایش جزئیات موجودی مشتری
    """
    customer = get_object_or_404(Customer, id=customer_id)
    customer_balance, created = CustomerBalance.objects.get_or_create(
        customer=customer,
        defaults={'current_balance': 0, 'total_received': 0, 'total_paid': 0}
    )
    
    # Ensure the balance is up-to-date by calling the model's method
    customer_balance.update_balance()
    customer_balance.refresh_from_db()

    # Fetch all operations (including deleted) for display purposes
    operations = FinancialOperation.objects.filter(
        customer=customer
    ).order_by('-date', '-created_at')

    # Use the correctly calculated values from the customer_balance object
    total_received = customer_balance.total_received
    total_paid = customer_balance.total_paid
    current_balance = customer_balance.current_balance
    
    context = {
        'customer': customer,
        'customer_balance': customer_balance,
        'operations': operations,
        'total_received': total_received,
        'total_paid': total_paid,
        'current_balance': current_balance,
    }
    
    return render(request, 'products/customer_balance_detail.html', context)


@login_required
def get_received_checks(request):
    checks = ReceivedCheque.objects.filter(status='RECEIVED').select_related('customer').order_by('-due_date', '-created_at')
    data = [{
        'id': check.id,
        'number': check.serial,
        'bank': check.bank_name,
        'amount': check.amount,
        'due_date': jdatetime.date.fromgregorian(date=check.due_date).strftime('%Y/%m/%d'),
        'customer': check.customer.get_full_name() if check.customer else '',
        'endorsement': check.endorsement,
        'sayadi_id': check.sayadi_id,
    } for check in checks]
    return JsonResponse(data, safe=False)

@login_required
@group_required('حسابداری')
@require_POST
@transaction.atomic
def combined_check_operation_view(request):
    """
    پردازش ترکیبی چک‌های خرجی و صدور شده در یک عملیات مالی واحد
    """
    try:
        data = json.loads(request.body)
        customer_id = data.get('customer')
        payee_name = data.get('payee', '')
        issued_checks_data = data.get('issued_checks', [])
        spent_check_ids = data.get('spent_check_ids', [])



        if not customer_id:
            return JsonResponse({'success': False, 'message': 'شناسه مشتری ارسال نشده است.'}, status=400)

        if not issued_checks_data and not spent_check_ids:
            return JsonResponse({'success': False, 'message': 'هیچ چکی برای پردازش ارسال نشده است.'}, status=400)

        customer = get_object_or_404(Customer, id=customer_id)
        total_amount = Decimal('0')
        operation_description_parts = []
        issued_check_numbers = []

        # پردازش چک‌های صدور شده
        if issued_checks_data:
            for check_data in issued_checks_data:
                check_id = check_data.get('check_number')
                amount_value = check_data.get('amount', '0')
                amount_str = str(amount_value).replace(',', '')
                amount = Decimal(amount_str)
                due_date_shamsi = check_data.get('due_date')
                series = check_data.get('series')
                sayadi_id = check_data.get('sayadi_id')

                if not all([check_id, amount, due_date_shamsi]):
                    return JsonResponse({'success': False, 'message': 'اطلاعات یکی از چک‌های جدید ناقص است.'}, status=400)

                try:
                    check = Check.objects.get(id=check_id)
                    if check.status != 'UNUSED':
                        return JsonResponse({
                            'success': False, 
                            'message': f'چک شماره {check.number} در وضعیت {check.get_status_display()} است و قابل صدور نیست.'
                        }, status=400)
                except Check.DoesNotExist:
                    return JsonResponse({
                        'success': False, 
                        'message': f'چک با شناسه {check_id} یافت نشد.'
                    }, status=404)

                # Update the check
                check.status = 'ISSUED'
                check.amount = amount
                check.date = convert_shamsi_to_gregorian(due_date_shamsi)
                check.payee = payee_name or customer.get_full_name()
                check.series = series
                check.sayadi_id = sayadi_id
                check.save()

                total_amount += amount
                issued_check_numbers.append(check.number)

            if issued_check_numbers:
                operation_description_parts.append(f"صدور {len(issued_check_numbers)} فقره چک شماره: {', '.join(issued_check_numbers)}")

        # پردازش چک‌های خرجی
        spent_checks = []
        if spent_check_ids:
            spent_checks = list(ReceivedCheque.objects.select_for_update().filter(
                id__in=spent_check_ids, 
                status='RECEIVED'
            ))
            
            if len(spent_checks) != len(spent_check_ids):
                return JsonResponse({
                    'success': False, 
                    'message': 'یک یا چند چک دریافتی یافت نشد یا وضعیت آن‌ها برای خرج کردن مناسب نیست.'
                }, status=404)

            spent_amount = sum(check.amount for check in spent_checks)
            spent_serials = ", ".join(check.serial for check in spent_checks)
            
            # Update spent checks status and recipient information
            ReceivedCheque.objects.filter(id__in=spent_check_ids).update(
                status='SPENT',
                recipient_name=customer.get_full_name(),
                recipient_customer=customer
            )
            
            total_amount += spent_amount
            operation_description_parts.append(f"خرج {len(spent_checks)} فقره چک دریافتی شماره: {spent_serials}")

        # ایجاد یک عملیات مالی واحد
        if total_amount > 0:
            operation = FinancialOperation.objects.create(
                operation_type='PAY_TO_CUSTOMER',
                customer=customer,
                amount=total_amount,
                payment_method='cheque' if issued_checks_data and len(spent_checks) == 0 else 'spend_cheque' if len(spent_checks) > 0 and not issued_checks_data else 'mixed_cheque',
                date=timezone.now().date(),
                description=f"پرداخت به {customer.get_full_name()} - {' + '.join(operation_description_parts)}",
                created_by=request.user,
                status='CONFIRMED',
                confirmed_by=request.user,
                confirmed_at=timezone.now()
            )

            # Link issued checks to the operation
            if issued_check_numbers:
                Check.objects.filter(number__in=issued_check_numbers).update(financial_operation=operation)

            # Link spent cheques to the operation
            if spent_checks:
                operation.spent_cheques.set(spent_checks)

        return JsonResponse({
            'success': True, 
            'message': f'عملیات پرداخت با مبلغ کل {total_amount:,} ریال با موفقیت ثبت شد.',
            'operation_id': operation.id
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'درخواست نامعتبر.'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'خطا در پردازش عملیات: {str(e)}'}, status=500)


@login_required
@group_required('حسابداری')
@require_POST
def issue_check_view(request):
    """
    Handles the submission of multiple checks from the modal.
    """
    try:
        data = json.loads(request.body)
        customer_id = data.get('customer')
        payee_name = data.get('payee')
        checks_data = data.get('checks', [])

        if not customer_id or not payee_name or not checks_data:
            return JsonResponse({'success': False, 'message': 'اطلاعات ارسالی ناقص است.'}, status=400)

        customer = get_object_or_404(Customer, id=customer_id)
        total_amount = Decimal('0')
        issued_check_numbers = []

        for check_data in checks_data:
            check_id = check_data.get('check_number')
            amount_value = check_data.get('amount', '0')
            # Convert to string first, then remove commas
            amount_str = str(amount_value).replace(',', '')
            amount = Decimal(amount_str)
            due_date_shamsi = check_data.get('due_date')
            series = check_data.get('series')
            sayadi_id = check_data.get('sayadi_id')

            if not all([check_id, amount, due_date_shamsi]):
                return JsonResponse({'success': False, 'message': 'اطلاعات یکی از چک‌ها ناقص است.'}, status=400)

            # Check if the check exists and is unused
            try:
                check = Check.objects.get(id=check_id)
                if check.status != 'UNUSED':
                    return JsonResponse({
                        'success': False, 
                        'message': f'چک شماره {check.number} در وضعیت {check.get_status_display()} است و قابل صدور نیست.'
                    }, status=400)
            except Check.DoesNotExist:
                return JsonResponse({
                    'success': False, 
                    'message': f'چک با شناسه {check_id} یافت نشد.'
                }, status=404)
            
            # Update the check
            check.status = 'ISSUED'
            check.amount = amount
            check.date = convert_shamsi_to_gregorian(due_date_shamsi)
            check.payee = payee_name
            check.series = series
            check.sayadi_id = sayadi_id
            check.save()
            
            total_amount += amount
            issued_check_numbers.append(check.number)

        # Create a single financial operation for the batch of checks
        if total_amount > 0:
            operation = FinancialOperation.objects.create(
                operation_type='PAY_TO_CUSTOMER',
                customer=customer,
                amount=total_amount,
                payment_method='cheque',
                date=timezone.now().date(),
                description=f'پرداخت طی چک‌های شماره: {", ".join(issued_check_numbers)} به {payee_name}',
                created_by=request.user,
                status='CONFIRMED',
                confirmed_by=request.user,
                confirmed_at=timezone.now()
            )
            # Link the checks to the operation
            Check.objects.filter(number__in=issued_check_numbers).update(financial_operation=operation)
        
        return JsonResponse({'success': True, 'message': f'{len(issued_check_numbers)} فقره چک با موفقیت صادر شد.'})

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'درخواست نامعتبر.'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'خطا در صدور چک: {str(e)}'}, status=500)

@login_required
def get_checkbooks_for_bank_account(request):
    bank_account_id = request.GET.get('bank_account_id')
    checkbooks = CheckBook.objects.filter(bank_account_id=bank_account_id, is_active=True)
    data = [{'id': cb.id, 'name': f"{cb.serial} ({cb.bank_account.bank.name})"} for cb in checkbooks]
    return JsonResponse(data, safe=False)

@login_required
def get_unused_checks_for_checkbook(request):
    checkbook_id = request.GET.get('checkbook_id')
    checks = Check.objects.filter(checkbook_id=checkbook_id, status='UNUSED').order_by('number')
    data = [{'id': c.id, 'name': c.number} for c in checks]
    return JsonResponse(data, safe=False)


@login_required
@group_required('حسابداری')
def change_received_cheque_status(request, cheque_id):
    cheque = get_object_or_404(ReceivedCheque, id=cheque_id)
    if request.method == 'POST':
        form = ReceivedChequeStatusChangeForm(request.POST, instance=cheque)
        if form.is_valid():
            form.save()
            messages.success(request, f'وضعیت چک {cheque.sayadi_id} با موفقیت به‌روز شد.')
            return redirect('products:received_cheque_list')
    else:
        form = ReceivedChequeStatusChangeForm(instance=cheque)

    return render(request, 'products/received_cheque_change_status.html', {
        'form': form,
        'cheque': cheque
    })

@login_required
@group_required('حسابداری')
def received_cheque_detail_view(request, cheque_id):
    cheque = get_object_or_404(ReceivedCheque, id=cheque_id)
    return render(request, 'products/received_cheque_detail.html', {'cheque': cheque})

@login_required
@group_required('حسابداری')
@transaction.atomic
def received_cheque_edit_view(request, cheque_id):
    cheque = get_object_or_404(ReceivedCheque, id=cheque_id)
    if request.method == 'POST':
        form = ReceivedChequeEditForm(request.POST, instance=cheque)
        if form.is_valid():
            updated_cheque = form.save()

            # Check if the cheque is part of a financial operation
            if updated_cheque.financial_operation:
                operation = updated_cheque.financial_operation
                
                # Recalculate the total amount from all related cheques
                new_total_amount = operation.received_cheques.aggregate(
                    total=Sum('amount')
                )['total'] or 0
                
                # Update the operation's amount if it has changed
                if operation.amount != new_total_amount:
                    operation.amount = new_total_amount
                    operation.save(update_fields=['amount'])
            
            messages.success(request, f'چک {cheque.sayadi_id} با موفقیت ویرایش شد و سوابق مالی به‌روز گردید.')
            return redirect('products:received_cheque_detail', cheque_id=cheque.id)
    else:
        form = ReceivedChequeEditForm(instance=cheque)

    return render(request, 'products/received_cheque_edit.html', {
        'form': form,
        'cheque': cheque
    })


@login_required
@group_required('حسابداری')
@require_POST
def clear_received_cheque_view(request, cheque_id):
    """
    وصول چک واگذار شده - تبدیل از DEPOSITED به CLEARED
    """
    try:
        with transaction.atomic():
            cheque = get_object_or_404(ReceivedCheque, id=cheque_id, status='DEPOSITED')
            
            # Change status to CLEARED
            cheque.status = 'CLEARED'
            cheque.cleared_at = timezone.now()
            cheque.cleared_by = request.user
            cheque.save()
            
            # Update bank account balance if deposited to a bank account
            if cheque.deposited_bank_account:
                # Add cheque amount to bank account balance
                bank_account = cheque.deposited_bank_account
                # You may need to implement a method to update bank balance
                # For now, we'll just update the cheque status
                
            return JsonResponse({
                'success': True,
                'message': f'چک شناسه صیادی {cheque.sayadi_id} با موفقیت وصول شد.'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@group_required('حسابداری')
@require_POST
def bounce_received_cheque_view(request, cheque_id):
    """
    برگشت چک واگذار شده - تبدیل از DEPOSITED به RECEIVED
    """
    try:
        with transaction.atomic():
            cheque = get_object_or_404(ReceivedCheque, id=cheque_id, status='DEPOSITED')
            
            # Change status back to RECEIVED
            cheque.status = 'RECEIVED'
            cheque.bounced_at = timezone.now()
            cheque.bounced_by = request.user
            # Clear deposit information
            cheque.deposited_bank_account = None
            cheque.save()
            
            return JsonResponse({
                'success': True,
                'message': f'چک شناسه صیادی {cheque.sayadi_id} با موفقیت برگشت خورد و به چک‌های نزد صندوق منتقل شد.'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@group_required('حسابداری')
@require_POST
def return_received_cheque_to_customer_view(request, cheque_id):
    """
    عودت چک دریافتی به طرف حساب - تبدیل از RECEIVED به RETURNED
    و ایجاد عملیات مالی برگشت چک دریافتی
    """
    try:
        with transaction.atomic():
            cheque = get_object_or_404(ReceivedCheque, id=cheque_id, status='RECEIVED')
            
            # تغییر وضعیت چک به RETURNED
            cheque.status = 'RETURNED'
            cheque.returned_at = timezone.now()
            cheque.returned_by = request.user
            cheque.save()
            
            # ایجاد عملیات مالی برگشت چک دریافتی
            operation = FinancialOperation.objects.create(
                operation_type='CHECK_BOUNCE',  # برگشت چک دریافتی
                customer=cheque.customer,
                amount=cheque.amount,
                payment_method='cheque_bounce',
                description=f'برگشت چک دریافتی - شناسه صیادی: {cheque.sayadi_id}',
                date=timezone.now().date(),
                created_by=request.user,
                status='CONFIRMED'
            )
            
            # به‌روزرسانی موجودی مشتری (بدهکار)
            from .models import CustomerBalance
            customer_balance, created = CustomerBalance.objects.get_or_create(customer=cheque.customer)
            customer_balance.update_balance()
            
            messages.success(request, f'چک شناسه صیادی {cheque.sayadi_id} با موفقیت به طرف حساب عودت داده شد.')
            
            return JsonResponse({
                'success': True,
                'message': f'چک شناسه صیادی {cheque.sayadi_id} با موفقیت به طرف حساب عودت داده شد.'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@group_required('حسابداری')
def received_cheque_list_view(request):
    """
    Displays a list of received cheques with filtering and pagination.
    """
    cheques_list = ReceivedCheque.objects.select_related('customer', 'created_by').order_by('-due_date', '-cleared_at', '-created_at')
    
    # Enhanced filtering - similar to the deleted advanced_cheque_filter_view
    search_query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    bank_filter = request.GET.get('bank', '')
    start_date_filter = request.GET.get('start_date', '')
    end_date_filter = request.GET.get('end_date', '')
    customer_filter = request.GET.get('customer', '')
    sayadi_filter = request.GET.get('sayadi', '')
    owner_filter = request.GET.get('owner', '')
    serial_filter = request.GET.get('serial', '')
    endorsement_filter = request.GET.get('endorsement', '')
    amount_min = request.GET.get('amount_min', '')
    amount_max = request.GET.get('amount_max', '')

    if search_query:
        cheques_list = cheques_list.filter(
            Q(sayadi_id__icontains=search_query) |
            Q(customer__first_name__icontains=search_query) |
            Q(customer__last_name__icontains=search_query) |
            Q(owner_name__icontains=search_query) |
            Q(amount__icontains=search_query) |
            Q(endorsement__icontains=search_query) |
            Q(serial__icontains=search_query)
        )
    
    if status_filter:
        cheques_list = cheques_list.filter(status=status_filter)
        
    if bank_filter:
        cheques_list = cheques_list.filter(bank_name__icontains=bank_filter)
        
    if customer_filter:
        cheques_list = cheques_list.filter(customer_id=customer_filter)
    
    if sayadi_filter:
        cheques_list = cheques_list.filter(sayadi_id__icontains=sayadi_filter)
    
    if owner_filter:
        cheques_list = cheques_list.filter(owner_name__icontains=owner_filter)
    
    if serial_filter:
        cheques_list = cheques_list.filter(serial__icontains=serial_filter)
    
    if endorsement_filter:
        cheques_list = cheques_list.filter(endorsement__icontains=endorsement_filter)

    if start_date_filter:
        start_date_gregorian = convert_shamsi_to_gregorian(start_date_filter)
        cheques_list = cheques_list.filter(due_date__gte=start_date_gregorian)
        
    if end_date_filter:
        end_date_gregorian = convert_shamsi_to_gregorian(end_date_filter)
        cheques_list = cheques_list.filter(due_date__lte=end_date_gregorian)
        
    if amount_min:
        try:
            from decimal import Decimal, InvalidOperation
            min_amount = Decimal(amount_min.replace(',', ''))
            cheques_list = cheques_list.filter(amount__gte=min_amount)
        except (ValueError, InvalidOperation):
            pass
    
    if amount_max:
        try:
            from decimal import Decimal, InvalidOperation
            max_amount = Decimal(amount_max.replace(',', ''))
            cheques_list = cheques_list.filter(amount__lte=max_amount)
        except (ValueError, InvalidOperation):
            pass

    # Pagination
    paginator = Paginator(cheques_list, 25)  # 25 cheques per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get customers for filter dropdown
    customers = Customer.objects.all().order_by('first_name', 'last_name')
    
    # Calculate totals for current filtered results
    from django.db.models import Sum
    total_amount = cheques_list.aggregate(Sum('amount'))['amount__sum'] or 0
    total_count = cheques_list.count()

    # Determine page title based on status filter
    status_titles = {
        'RECEIVED': 'لیست چکهای نزد صندوق',
        'DEPOSITED': 'لیست چکهای واگذار شده به بانک',
        'CLEARED': 'لیست چکهای وصول شده',
        'SPENT': 'لیست چکهای خرج شده',
        'BOUNCED': 'لیست چکهای برگشتی',
        'RETURNED': 'لیست چکهای برگشت داده شده',
    }
    
    if status_filter and status_filter in status_titles:
        page_title = status_titles[status_filter]
    else:
        page_title = 'لیست چکهای دریافتی'

    context = {
        'page_obj': page_obj,
        'customers': customers,
        'status_choices': ReceivedCheque.STATUS_CHOICES,
        'total_amount': total_amount,
        'total_count': total_count,
        'page_title': page_title,
        'filters': {
            'q': search_query,
            'status': status_filter,
            'bank': bank_filter,
            'start_date': start_date_filter,
            'end_date': end_date_filter,
            'customer': customer_filter,
            'sayadi': sayadi_filter,
            'owner': owner_filter,
            'serial': serial_filter,
            'endorsement': endorsement_filter,
            'amount_min': amount_min,
            'amount_max': amount_max,
        }
    }
    return render(request, 'products/received_cheque_list.html', context)


# Helper functions
def convert_shamsi_to_gregorian(shamsi_date_str):
    """
    تبدیل تاریخ شمسی به میلادی
    """
    try:
        # فرض بر این است که تاریخ شمسی در فرمت YYYY/MM/DD است
        year, month, day = map(int, shamsi_date_str.split('/'))
        
        # بررسی صحت تاریخ
        if year < 1300 or year > 1500:  # محدوده منطقی برای سال شمسی
            return timezone.now().date()
        if month < 1 or month > 12:
            return timezone.now().date()
        if day < 1 or day > 31:
            return timezone.now().date()
            
        jdate = jdatetime.date(year, month, day)
        return jdate.togregorian()
    except Exception as e:
        print(f"Error converting date {shamsi_date_str}: {e}")
        return timezone.now().date()


@login_required
@group_required('حسابداری')
def operation_confirmation_view(request):
    """
    صفحه تأیید عملیات مالی
    """
    success_message = request.session.get('success_message')
    operation_type = request.session.get('operation_type')
    
    if not success_message or not operation_type:
        return redirect('products:financial_dashboard')
    
    # حذف پیام از session بعد از نمایش
    del request.session['success_message']
    del request.session['operation_type']
    
    context = {
        'success_message': success_message,
        'operation_type': operation_type
    }
    
    return render(request, 'financial_operations/operation_confirmation.html', context)

@login_required
@group_required('حسابداری')
def financial_dashboard_view(request):
    """
    داشبورد مالی - نمایش آمار و اطلاعات کلی
    """
    from django.db.models import Sum, Q
    
    # Get all active funds
    funds = Fund.objects.filter(is_active=True)
    
    # Recalculate and sum balances using the corrected model method
    total_cash_balance = 0
    total_bank_balance = 0
    
    for fund in funds:
        # This now contains the correct, centralized logic
        fund.recalculate_balance()
        if fund.fund_type == 'CASH':
            total_cash_balance += fund.current_balance
        elif fund.fund_type == 'BANK':
            total_bank_balance += fund.current_balance

    # Petty cash balance is calculated separately via its own class method
    total_petty_cash_balance = Fund.get_petty_cash_balance()
    
    # Bank accounts statistics (this seems to be a separate concept from BANK Funds)
    bank_accounts = BankAccount.objects.filter(is_active=True)
    total_bank_accounts_balance = sum(account.current_balance for account in bank_accounts)
    
    # The grand total preserves the original logic of summing all balance types
    total_balance = total_cash_balance + total_bank_balance + total_petty_cash_balance + total_bank_accounts_balance
    
    # آمار عملیات‌های مالی - فقط برای صندوق نقدی
    today = timezone.now().date()
    today_cash_operations = FinancialOperation.objects.filter(
        date=today,
        status='CONFIRMED',
        fund__fund_type='CASH',
        is_deleted=False
    )
    
    # Note: These definitions determine what counts as income/expense *for the cash fund*.
    # For example, RECEIVE_FROM_BANK is income for the cash fund.
    CASH_INCOME_OPS = ['RECEIVE_FROM_CUSTOMER', 'PAYMENT_TO_CASH', 'RECEIVE_FROM_BANK']
    CASH_EXPENSE_OPS = ['PAY_TO_CUSTOMER', 'PAYMENT_FROM_CASH', 'PAY_TO_BANK']

    today_income = sum(op.amount for op in today_cash_operations if op.operation_type in CASH_INCOME_OPS)
    today_expense = sum(op.amount for op in today_cash_operations if op.operation_type in CASH_EXPENSE_OPS)
    
    # آمار مشتریان - محاسبه از عملیات‌های واقعی
    all_customer_operations = FinancialOperation.objects.filter(
        customer__isnull=False,
        status='CONFIRMED',
        is_deleted=False
    )
    
    # عملیات‌هایی که مشتری بدهکار می‌شود (ما به آنها پرداخت کردیم)
    debit_ops = ['PAY_TO_CUSTOMER', 'BANK_TRANSFER', 'CHECK_BOUNCE']
    total_paid = all_customer_operations.filter(
        operation_type__in=debit_ops
    ).aggregate(Sum('amount'))['amount__sum'] or 0
    
    # عملیات‌هایی که مشتری بستانکار می‌شود (آنها به ما پرداخت کردند یا چک ما برگشت خورد)
    credit_ops = ['RECEIVE_FROM_CUSTOMER', 'SPENT_CHEQUE_RETURN', 'ISSUED_CHECK_BOUNCE']
    total_received = all_customer_operations.filter(
        operation_type__in=credit_ops
    ).aggregate(Sum('amount'))['amount__sum'] or 0
    
    # کل موجودی = بدهکاری - بستانکاری
    total_customer_balance = total_paid - total_received
    
    # شمارش بدهکاران و بستانکاران
    customer_balances = CustomerBalance.objects.all()
    debtor_count = customer_balances.filter(current_balance__gt=0).count()
    creditor_count = customer_balances.filter(current_balance__lt=0).count()
    
    # عملیات‌های اخیر
    recent_operations = FinancialOperation.objects.filter(status='CONFIRMED', is_deleted=False).order_by('-date', '-created_at')[:10]
    
    # Received Cheque Summary
    all_cheques = ReceivedCheque.objects.all()
    total_cheques_amount = all_cheques.aggregate(Sum('amount'))['amount__sum'] or 0
    on_hand_cheques_amount = all_cheques.filter(status='RECEIVED').aggregate(Sum('amount'))['amount__sum'] or 0
    deposited_cheques_amount = all_cheques.filter(status='DEPOSITED').aggregate(Sum('amount'))['amount__sum'] or 0
    cleared_cheques_amount = all_cheques.filter(status='CLEARED').aggregate(Sum('amount'))['amount__sum'] or 0
    bounced_cheques_amount = all_cheques.filter(status='BOUNCED').aggregate(Sum('amount'))['amount__sum'] or 0
    spent_cheques_amount = all_cheques.filter(status='SPENT').aggregate(Sum('amount'))['amount__sum'] or 0
    returned_cheques_amount = all_cheques.filter(status='RETURNED').aggregate(Sum('amount'))['amount__sum'] or 0
    
    # Issued Checks Summary
    all_issued_checks = Check.objects.filter(checkbook__isnull=False)  # فقط چک‌های صادر شده
    total_issued_amount = all_issued_checks.aggregate(Sum('amount'))['amount__sum'] or 0
    issued_checks_amount = all_issued_checks.filter(status='ISSUED').aggregate(Sum('amount'))['amount__sum'] or 0
    issued_cleared_amount = all_issued_checks.filter(status='CLEARED').aggregate(Sum('amount'))['amount__sum'] or 0
    issued_bounced_amount = all_issued_checks.filter(status='BOUNCED').aggregate(Sum('amount'))['amount__sum'] or 0

    context = {
        'total_balance': total_balance,
        'total_cash_balance': total_cash_balance,
        'total_bank_balance': total_bank_balance,
        'total_petty_cash_balance': total_petty_cash_balance,
        'total_bank_accounts_balance': total_bank_accounts_balance,
        'bank_accounts': bank_accounts,
        'today_income': today_income,
        'today_expense': today_expense,
        'today_net': today_income - today_expense,
        'total_customer_balance': total_customer_balance,
        'debtor_count': debtor_count,
        'creditor_count': creditor_count,
        'recent_operations': recent_operations,
        'funds': funds,
        # Cheque context
        'total_cheques_amount': total_cheques_amount,
        'on_hand_cheques_amount': on_hand_cheques_amount,
        'deposited_cheques_amount': deposited_cheques_amount,
        'cleared_cheques_amount': cleared_cheques_amount,
        'bounced_cheques_amount': bounced_cheques_amount,
        'spent_cheques_amount': spent_cheques_amount,
        'returned_cheques_amount': returned_cheques_amount,
        # Issued Checks context
        'total_issued_amount': total_issued_amount,
        'issued_checks_amount': issued_checks_amount,
        'issued_cleared_amount': issued_cleared_amount,
        'issued_bounced_amount': issued_bounced_amount,
    }
    
    return render(request, 'products/financial_dashboard.html', context)


@login_required
@group_required('حسابداری')
def spent_cheques_list_view(request):
    """
    نمایش لیست چک‌های خرج شده با امکان فیلتر و برگشت
    """
    cheques_list = ReceivedCheque.objects.filter(status='SPENT').select_related('customer', 'created_by').order_by('-updated_at', '-created_at')
    
    # Filtering
    search_query = request.GET.get('q')
    customer_filter = request.GET.get('customer')
    bank_filter = request.GET.get('bank')
    start_date_filter = request.GET.get('start_date')
    end_date_filter = request.GET.get('end_date')

    if search_query:
        cheques_list = cheques_list.filter(
            Q(sayadi_id__icontains=search_query) |
            Q(customer__first_name__icontains=search_query) |
            Q(customer__last_name__icontains=search_query) |
            Q(owner_name__icontains=search_query) |
            Q(amount__icontains=search_query) |
            Q(recipient_name__icontains=search_query) |
            Q(serial__icontains=search_query)
        )
    
    if customer_filter:
        cheques_list = cheques_list.filter(customer_id=customer_filter)
        
    if bank_filter:
        cheques_list = cheques_list.filter(bank_name__icontains=bank_filter)

    if start_date_filter:
        start_date_gregorian = convert_shamsi_to_gregorian(start_date_filter)
        cheques_list = cheques_list.filter(due_date__gte=start_date_gregorian)
        
    if end_date_filter:
        end_date_gregorian = convert_shamsi_to_gregorian(end_date_filter)
        cheques_list = cheques_list.filter(due_date__lte=end_date_gregorian)

    # Pagination
    paginator = Paginator(cheques_list, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get customers for filter dropdown
    customers = Customer.objects.all().order_by('first_name', 'last_name')

    context = {
        'page_obj': page_obj,
        'customers': customers,
        'filters': {
            'q': search_query or '',
            'customer': customer_filter or '',
            'bank': bank_filter or '',
            'start_date': start_date_filter or '',
            'end_date': end_date_filter or '',
        }
    }
    return render(request, 'products/spent_cheques_list.html', context)





@login_required
@group_required('حسابداری')
@require_POST
def return_spent_cheque_view(request, cheque_id):
    """
    برگشت چک خرج شده و تبدیل به چک برگشتی
    """
    try:
        with transaction.atomic():
            cheque = get_object_or_404(ReceivedCheque, id=cheque_id, status='SPENT')
            
            # Change cheque status to BOUNCED
            cheque.status = 'BOUNCED'
            cheque.bounced_at = timezone.now()
            cheque.bounced_by = request.user
            cheque.save()
            
            # پیدا کردن گیرنده چک (کسی که چک را دریافت کرده)
            # اول از فیلد recipient_customer استفاده کن، سپس از recipient_name
            recipient_customer = cheque.recipient_customer
            if not recipient_customer and cheque.recipient_name:
                # جستجو در نام کامل مشتریان
                from django.db.models import Q
                recipient_customer = Customer.objects.filter(
                    Q(first_name__icontains=cheque.recipient_name) | 
                    Q(last_name__icontains=cheque.recipient_name) |
                    Q(company_name__icontains=cheque.recipient_name)
                ).first()
            
            # اگر گیرنده پیدا نشد، از صاحب چک استفاده کن
            target_customer = recipient_customer if recipient_customer else cheque.customer
            
            # Create a financial operation for the cheque return
            # This reverses the original PAY_TO_CUSTOMER operation
            operation = FinancialOperation.objects.create(
                operation_type='RECEIVE_FROM_CUSTOMER',
                customer=target_customer,
                amount=cheque.amount,
                payment_method='cheque_return',
                date=timezone.now().date(),
                description=f'برگشت چک خرج شده به شماره صیادی {cheque.sayadi_id} از {target_customer.get_full_name()}',
                created_by=request.user,
                status='CONFIRMED',
                confirmed_by=request.user,
                confirmed_at=timezone.now()
            )
            
            # Update customer balance using the existing update_balance method
            customer_balance, created = CustomerBalance.objects.get_or_create(
                customer=target_customer,
                defaults={'current_balance': 0}
            )
            customer_balance.update_balance()  # This recalculates from all operations
            
            # پیام مناسب بر اساس اینکه مبلغ در کدام حساب اعمال شده
            if recipient_customer:
                messages.success(request, f'چک شماره صیادی {cheque.sayadi_id} با موفقیت برگشت زده شد و مبلغ {cheque.amount:,} ریال به عنوان بستانکاری گیرنده چک ({recipient_customer.get_full_name()}) ثبت گردید. سند شماره: {operation.operation_number}')
            else:
                messages.success(request, f'چک شماره صیادی {cheque.sayadi_id} با موفقیت برگشت زده شد و مبلغ {cheque.amount:,} ریال به عنوان بستانکاری صاحب چک ({cheque.customer.get_full_name()}) ثبت گردید. سند شماره: {operation.operation_number}')
            
    except Exception as e:
        messages.error(request, f'خطا در برگشت چک: {str(e)}')
    
    # Redirect based on the HTTP_REFERER or a next parameter
    next_url = request.GET.get('next') or request.POST.get('next')
    if next_url:
        return redirect(next_url)
    
    # Check if request came from received cheque list
    referer = request.META.get('HTTP_REFERER', '')
    if 'received-cheques' in referer:
        return redirect('products:received_cheque_list')
    
    return redirect('products:spent_cheques_list')


@login_required
@group_required('حسابداری')
@require_POST
def return_bounced_to_customer_view(request, cheque_id):
    """
    برگشت چک برگشتی به مشتری و اضافه کردن مبلغ به حساب
    """
    try:
        with transaction.atomic():
            cheque = get_object_or_404(ReceivedCheque, id=cheque_id, status='BOUNCED')
            
            # Change cheque status to RETURNED
            cheque.status = 'RETURNED'
            cheque.save()
            
            # Create a financial operation for returning bounced cheque to customer
            operation = FinancialOperation.objects.create(
                operation_type='PAY_TO_CUSTOMER',  # This adds to customer's debt (our receivable)
                customer=cheque.customer,
                amount=cheque.amount,
                payment_method='bounced_cheque_return',
                date=timezone.now().date(),
                description=f'عودت چک برگشتی به طرف حساب - شماره صیادی {cheque.sayadi_id} به {cheque.customer.get_full_name()}',
                created_by=request.user,
                status='CONFIRMED',
                confirmed_by=request.user,
                confirmed_at=timezone.now()
            )
            
            # Update customer balance using the existing update_balance method
            customer_balance, created = CustomerBalance.objects.get_or_create(
                customer=cheque.customer,
                defaults={'current_balance': 0}
            )
            customer_balance.update_balance()  # This recalculates from all operations
            
            messages.success(request, f'چک برگشتی شماره صیادی {cheque.sayadi_id} با موفقیت به {cheque.customer.get_full_name()} برگشت داده شد و مبلغ {cheque.amount:,} ریال به عنوان بدهی مشتری ثبت گردید. سند شماره: {operation.operation_number}')
            
    except Exception as e:
        messages.error(request, f'خطا در برگشت چک به طرف حساب: {str(e)}')
    
    return redirect('products:received_cheque_list')


@login_required
@group_required('حسابداری')
@require_POST
def transfer_bounced_to_fund_view(request, cheque_id):
    """
    انتقال چک برگشتی به چکهای نزد صندوق
    """
    try:
        with transaction.atomic():
            cheque = get_object_or_404(ReceivedCheque, id=cheque_id, status='BOUNCED')
            
            # Change cheque status to RECEIVED (back to fund)
            cheque.status = 'RECEIVED'
            cheque.bounced_at = None
            cheque.bounced_by = None
            cheque.save()
            
            messages.success(request, f'چک برگشتی شماره صیادی {cheque.sayadi_id} با موفقیت به چکهای نزد صندوق منتقل شد.')
            
    except Exception as e:
        messages.error(request, f'خطا در انتقال چک به صندوق: {str(e)}')
    
    return redirect('products:received_cheque_list')


@login_required
@group_required('حسابداری')
@require_POST
@transaction.atomic
def manually_clear_received_cheque(request, cheque_id):
    """
    Handles the manual clearing of a received cheque (from 'RECEIVED' to 'MANUALLY_CLEARED').
    This is used when a check is cleared directly into a cash fund, not a bank.
    """
    try:
        cheque = get_object_or_404(ReceivedCheque, id=cheque_id, status='RECEIVED')
        
        # Get the main cash fund
        cash_fund = Fund.objects.filter(fund_type='CASH').first()
        if not cash_fund:
            return JsonResponse({'success': False, 'error': 'صندوق نقدی اصلی یافت نشد.'}, status=404)

        # Update cheque status
        cheque.status = 'MANUALLY_CLEARED'
        cheque.cleared_at = timezone.now()
        cheque.cleared_by = request.user
        cheque.save()

        # Create a financial operation to reflect the cash moving into the fund
        operation = FinancialOperation.objects.create(
            operation_type='PAYMENT_TO_CASH', # This correctly increases fund balance
            fund=cash_fund,
            amount=cheque.amount,
            payment_method='cheque',
            date=timezone.now().date(),
            description=f"وصول دستی چک شماره صیادی {cheque.sayadi_id} از {cheque.customer.get_full_name()} به صندوق",
            created_by=request.user,
            status='CONFIRMED',
            confirmed_by=request.user,
            confirmed_at=timezone.now()
        )
        
        # Link the cheque to the operation for tracking
        operation.received_cheques.add(cheque)
        
        # The post_save signal on FinancialOperation will handle updating the fund balance
        # and creating the accounting voucher.

        return JsonResponse({
            'success': True,
            'message': 'چک با موفقیت به صورت دستی وصول شد و مبلغ به صندوق اضافه گردید.'
        })

    except ReceivedCheque.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'چک یافت نشد یا وضعیت آن برای این عملیات مناسب نیست.'}, status=404)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': f'خطای سیستمی: {str(e)}'}, status=500)


# =============================================================================
# توابع داده برای گزارشات مالی
# =============================================================================

def get_profit_loss_data(request):
    """داده‌های گزارش سود و زیان"""
    from django.db.models import Sum, Q
    from datetime import datetime, timedelta
    
    # دریافت تاریخ‌های فیلتر
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # اگر تاریخ مشخص نشده، ماه جاری
    if not start_date or not end_date:
        today = datetime.now()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
    
    # محاسبه درآمدها (فروش)
    sales_revenue = SalesInvoice.objects.filter(
        invoice_date__range=[start_date, end_date],
        status='confirmed'
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    # محاسبه هزینه‌ها (خرید)
    purchase_cost = PurchaseInvoice.objects.filter(
        invoice_date__range=[start_date, end_date],
        status='confirmed'
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    # محاسبه سود ناخالص
    gross_profit = sales_revenue - purchase_cost
    
    # محاسبه هزینه‌های عملیاتی (عملیات مالی)
    operational_expenses = FinancialOperation.objects.filter(
        date__range=[start_date, end_date],
        operation_type__in=['PAYMENT_FROM_CASH', 'PAY_TO_BANK', 'PETTY_CASH'],
        status='CONFIRMED'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # سود خالص
    net_profit = gross_profit - operational_expenses
    
    return {
        'start_date': start_date,
        'end_date': end_date,
        'sales_revenue': sales_revenue,
        'purchase_cost': purchase_cost,
        'gross_profit': gross_profit,
        'operational_expenses': operational_expenses,
        'net_profit': net_profit,
    }
def get_sales_by_product_data(request):
    """داده‌های فروش به تفکیک کالا - نسخه بهبود یافته"""
    from django.db.models import Sum, Count, Avg, F, ExpressionWrapper, DecimalField
    from django.db.models.functions import Coalesce
    
    # دریافت پارامترهای فیلتر
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    product_category = request.GET.get('category', '')
    min_amount = request.GET.get('min_amount', '')
    max_amount = request.GET.get('max_amount', '')
    sort_by = request.GET.get('sort_by', 'total_amount')
    sort_order = request.GET.get('sort_order', 'desc')
    
    # تنظیم تاریخ پیش‌فرض
    if not start_date or not end_date:
        today = datetime.now()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
    
    # فیلتر پایه
    base_query = SalesInvoiceItem.objects.filter(
        invoice__invoice_date__range=[start_date, end_date],
        invoice__status='confirmed'
    )
    
    # اعمال فیلترهای اضافی
    if product_category:
        base_query = base_query.filter(product__car_group__icontains=product_category)
    
    # محاسبه آمار کلی
    total_stats = base_query.aggregate(
        total_sales_amount=Coalesce(Sum('total'), 0),
        total_quantity=Coalesce(Sum('quantity'), 0),
        total_invoices=Count('invoice', distinct=True),
        avg_amount_per_invoice=Coalesce(Sum('total') / Count('invoice', distinct=True), 0)
    )
    
    # فروش به تفکیک محصول با محاسبات پیشرفته
    sales_by_product = base_query.values(
        'product__name',
        'product__code',
        'product__car_group',
        'product__purchase_price'
    ).annotate(
        total_quantity=Sum('quantity'),
        total_amount=Sum('total'),
        invoice_count=Count('invoice', distinct=True),
        avg_quantity_per_invoice=ExpressionWrapper(
            F('total_quantity') / F('invoice_count'),
            output_field=DecimalField()
        ),
        avg_amount_per_invoice=ExpressionWrapper(
            F('total_amount') / F('invoice_count'),
            output_field=DecimalField()
        ),
        # محاسبه سود
        total_cost=Sum(F('quantity') * F('product__purchase_price')),
        profit=ExpressionWrapper(
            F('total_amount') - F('total_cost'),
            output_field=DecimalField()
        ),
        profit_margin=ExpressionWrapper(
            (F('profit') / F('total_amount')) * 100,
            output_field=DecimalField()
        ),
        # محاسبه درصد از کل فروش
        percentage_of_total=ExpressionWrapper(
            (F('total_amount') / total_stats['total_sales_amount']) * 100,
            output_field=DecimalField()
        )
    )
    
    # اعمال فیلترهای مبلغ
    if min_amount:
        sales_by_product = sales_by_product.filter(total_amount__gte=min_amount)
    if max_amount:
        sales_by_product = sales_by_product.filter(total_amount__lte=max_amount)
    
    # مرتب‌سازی
    if sort_order == 'desc':
        sales_by_product = sales_by_product.order_by(f'-{sort_by}')
    else:
        sales_by_product = sales_by_product.order_by(sort_by)
    
    # محاسبه رتبه‌بندی
    for i, item in enumerate(sales_by_product):
        item['rank'] = i + 1
    
    # آمار تکمیلی
    additional_stats = {
        'total_products': sales_by_product.count(),
        'top_product': sales_by_product.first(),
        'bottom_product': sales_by_product.last() if sales_by_product.count() > 1 else None,
        'avg_profit_margin': sales_by_product.aggregate(
            avg_margin=Coalesce(Avg('profit_margin'), 0)
        )['avg_margin'],
        'total_profit': sales_by_product.aggregate(
            total_profit=Coalesce(Sum('profit'), 0)
        )['total_profit']
    }
    
    # گروه‌بندی بر اساس دسته‌بندی محصولات
    category_stats = base_query.values('product__car_group').annotate(
        category_total=Sum('total'),
        category_quantity=Sum('quantity'),
        category_invoices=Count('invoice', distinct=True)
    ).order_by('-category_total')
    
    return {
        'start_date': start_date,
        'end_date': end_date,
        'sales_by_product': sales_by_product,
        'total_stats': total_stats,
        'additional_stats': additional_stats,
        'category_stats': category_stats,
        'filters': {
            'category': product_category,
            'min_amount': min_amount,
            'max_amount': max_amount,
            'sort_by': sort_by,
            'sort_order': sort_order
        }
    }

def get_sales_by_customer_data(request):
    """داده‌های فروش به تفکیک مشتری"""
    from django.db.models import Sum, Count
    
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if not start_date or not end_date:
        today = datetime.now()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
    
    # فروش به تفکیک مشتری
    sales_by_customer = SalesInvoice.objects.filter(
        invoice_date__range=[start_date, end_date],
        status='confirmed'
    ).values(
        'customer__first_name',
        'customer__last_name',
        'customer__store_name'
    ).annotate(
        total_amount=Sum('total_amount'),
        invoice_count=Count('id'),
        avg_amount=Sum('total_amount') / Count('id')
    ).order_by('-total_amount')
    
    # محاسبه جمع کل
    totals = sales_by_customer.aggregate(
        total_amount=Sum('total_amount'),
        avg_amount=Sum('total_amount') / Count('id')
    )
    
    return {
        'start_date': start_date,
        'end_date': end_date,
        'sales_by_customer': sales_by_customer,
        'total_amount': totals['total_amount'] or 0,
        'avg_amount': totals['avg_amount'] or 0,
    }

def get_product_profit_data(request):
    """داده‌های سود کالا"""
    from django.db.models import Sum, F, ExpressionWrapper, DecimalField
    
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if not start_date or not end_date:
        today = datetime.now()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
    
    # محاسبه سود هر محصول
    product_profits = SalesInvoiceItem.objects.filter(
        invoice__invoice_date__range=[start_date, end_date],
        invoice__status='confirmed'
    ).values(
        'product__name',
        'product__code'
    ).annotate(
        total_sales=Sum('total'),
        total_cost=Sum(F('quantity') * F('product__purchase_price')),
        profit=ExpressionWrapper(
            F('total_sales') - F('total_cost'),
            output_field=DecimalField()
        ),
        profit_margin=ExpressionWrapper(
            (F('profit') / F('total_sales')) * 100,
            output_field=DecimalField()
        )
    ).order_by('-profit')
    
    # محاسبه جمع کل
    totals = product_profits.aggregate(
        total_profit=Sum('profit'),
        avg_profit_margin=Sum('profit_margin')
    )
    
    return {
        'start_date': start_date,
        'end_date': end_date,
        'product_profits': product_profits,
        'total_profit': totals['total_profit'] or 0,
        'avg_profit_margin': (totals['avg_profit_margin'] or 0) / max(len(product_profits), 1),
    }

def get_customer_profit_data(request):
    """داده‌های سود مشتری"""
    from django.db.models import Sum, F, ExpressionWrapper, DecimalField
    
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if not start_date or not end_date:
        today = datetime.now()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
    
    # محاسبه سود هر مشتری
    customer_profits = SalesInvoice.objects.filter(
        invoice_date__range=[start_date, end_date],
        status='confirmed'
    ).values(
        'customer__first_name',
        'customer__last_name',
        'customer__store_name'
    ).annotate(
        total_sales=Sum('total_amount'),
        total_cost=Sum(F('items__quantity') * F('items__product__purchase_price')),
        profit=ExpressionWrapper(
            F('total_sales') - F('total_cost'),
            output_field=DecimalField()
        ),
        profit_margin=ExpressionWrapper(
            (F('profit') / F('total_sales')) * 100,
            output_field=DecimalField()
        )
    ).order_by('-profit')
    
    # محاسبه جمع کل
    totals = customer_profits.aggregate(
        total_profit=Sum('profit'),
        avg_profit_margin=Sum('profit_margin')
    )
    
    return {
        'start_date': start_date,
        'end_date': end_date,
        'customer_profits': customer_profits,
        'total_profit': totals['total_profit'] or 0,
        'avg_profit_margin': (totals['avg_profit_margin'] or 0) / max(len(customer_profits), 1),
    }

def get_accounts_receivable_payable_data(request):
    """داده‌های حساب‌های دریافتی و پرداختی"""
    from django.db.models import Sum
    
    # حساب‌های دریافتی (بدهکاران)
    accounts_receivable = CustomerBalance.objects.filter(
        current_balance__gt=0
    ).select_related('customer').order_by('-current_balance')
    
    # حساب‌های پرداختی (بستانکاران)
    accounts_payable = CustomerBalance.objects.filter(
        current_balance__lt=0
    ).select_related('customer').order_by('current_balance')
    
    # جمع کل
    total_receivable = accounts_receivable.aggregate(
        total=Sum('current_balance')
    )['total'] or 0
    
    total_payable = abs(accounts_payable.aggregate(
        total=Sum('current_balance')
    )['total'] or 0)
    
    return {
        'accounts_receivable': accounts_receivable,
        'accounts_payable': accounts_payable,
        'total_receivable': total_receivable,
        'total_payable': total_payable,
    }

def get_cash_flow_data(request):
    """داده‌های گردش صندوق"""
    from django.db.models import Sum
    from datetime import datetime, timedelta
    
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if not start_date or not end_date:
        today = datetime.now()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
    
    # دریافتی‌های نقدی
    cash_inflows = FinancialOperation.objects.filter(
        date__range=[start_date, end_date],
        operation_type__in=['RECEIVE_FROM_CUSTOMER', 'RECEIVE_FROM_BANK', 'PAYMENT_TO_CASH'],
        payment_method='cash',
        status='CONFIRMED'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # پرداخت‌های نقدی
    cash_outflows = FinancialOperation.objects.filter(
        date__range=[start_date, end_date],
        operation_type__in=['PAY_TO_CUSTOMER', 'PAY_TO_BANK', 'PAYMENT_FROM_CASH', 'CASH_WITHDRAWAL'],
        payment_method='cash',
        status='CONFIRMED'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # گردش خالص
    net_cash_flow = cash_inflows - cash_outflows
    
    return {
        'start_date': start_date,
        'end_date': end_date,
        'cash_inflows': cash_inflows,
        'cash_outflows': cash_outflows,
        'net_cash_flow': net_cash_flow,
    }

def get_bank_statement_data(request):
    """داده‌های صورت حساب بانک"""
    from django.db.models import Sum
    
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if not start_date or not end_date:
        today = datetime.now()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
    
    # تراکنش‌های بانکی
    bank_transactions = FinancialOperation.objects.filter(
        date__range=[start_date, end_date],
        operation_type__in=['RECEIVE_FROM_BANK', 'PAY_TO_BANK', 'BANK_TRANSFER'],
        status='CONFIRMED'
    ).order_by('-date')
    
    # جمع دریافتی‌های بانکی
    bank_inflows = bank_transactions.filter(
        operation_type__in=['RECEIVE_FROM_BANK', 'BANK_TRANSFER']
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # جمع پرداخت‌های بانکی
    bank_outflows = bank_transactions.filter(
        operation_type__in=['PAY_TO_BANK']
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    return {
        'start_date': start_date,
        'end_date': end_date,
        'bank_transactions': bank_transactions,
        'bank_inflows': bank_inflows,
        'bank_outflows': bank_outflows,
        'net_bank_flow': bank_inflows - bank_outflows,
    }

def get_checks_data(request):
    """داده‌های چک‌های دریافتی و پرداختی"""
    from django.db.models import Sum
    
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if not start_date or not end_date:
        today = datetime.now()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
    
    # چک‌های دریافتی
    received_checks = Check.objects.filter(
        date__range=[start_date, end_date],
        status='RECEIVED'
    ).order_by('-date')
    
    # چک‌های پرداختی
    issued_checks = Check.objects.filter(
        date__range=[start_date, end_date],
        status='ISSUED'
    ).order_by('-date')
    
    # جمع مبالغ
    total_received = received_checks.aggregate(total=Sum('amount'))['total'] or 0
    total_issued = issued_checks.aggregate(total=Sum('amount'))['total'] or 0
    
    return {
        'start_date': start_date,
        'end_date': end_date,
        'received_checks': received_checks,
        'issued_checks': issued_checks,
        'total_received': total_received,
        'total_issued': total_issued,
    }

def get_petty_cash_data(request):
    """داده‌های تنخواه"""
    from django.db.models import Sum
    
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if not start_date or not end_date:
        today = datetime.now()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
    
    # عملیات تنخواه
    petty_cash_operations = PettyCashOperation.objects.filter(
        date__range=[start_date, end_date]
    ).order_by('-date')
    
    total_withdrawals = petty_cash_operations.filter(
        operation_type='WITHDRAW'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # موجودی تنخواه (فرضی)
    petty_cash_balance = 1000000  # این مقدار باید از مدل Fund محاسبه شود
    
    return {
        'start_date': start_date,
        'end_date': end_date,
        'petty_cash_operations': petty_cash_operations,
        'total_withdrawals': total_withdrawals,
        'petty_cash_balance': petty_cash_balance,
    }

# =============================================================================
# توابع داده‌های انبار و موجودی
# =============================================================================

def get_inventory_stock_data(request):
    """داده‌های موجودی کالا"""
    from django.db.models import Sum, F, ExpressionWrapper, DecimalField
    
    # دریافت تمام محصولات با موجودی
    inventory_items = Product.objects.annotate(
        total_value=ExpressionWrapper(
            F('quantity') * F('price'),
            output_field=DecimalField()
        )
    ).order_by('-quantity')
    
    # محاسبه جمع کل موجودی و ارزش
    totals = inventory_items.aggregate(
        total_quantity=Sum('quantity'),
        total_value=Sum(F('quantity') * F('price'))
    )
    
    return {
        'inventory_items': inventory_items,
        'total_quantity': totals['total_quantity'] or 0,
        'total_value': totals['total_value'] or 0,
    }

def get_product_turnover_data(request):
    """داده‌های گردش کالا"""
    from django.db.models import Sum, Count, Avg
    
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if not start_date or not end_date:
        today = datetime.now()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
    
    # گردش کالا
    product_turnover = SalesInvoiceItem.objects.filter(
        invoice__invoice_date__range=[start_date, end_date],
        invoice__status='confirmed'
    ).values(
        'product__name',
        'product__code',
        'product__car_group'
    ).annotate(
        total_sold=Sum('quantity'),
        total_revenue=Sum('total'),
        avg_price=Avg('price'),
        invoice_count=Count('invoice', distinct=True)
    ).order_by('-total_sold')
    
    return {
        'start_date': start_date,
        'end_date': end_date,
        'product_turnover': product_turnover,
    }

def get_fast_slow_moving_data(request):
    """داده‌های کالاهای سریع و کند گردش"""
    from django.db.models import Sum, Count, Avg
    
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if not start_date or not end_date:
        today = datetime.now()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
    
    # کالاهای سریع گردش
    fast_moving = SalesInvoiceItem.objects.filter(
        invoice__invoice_date__range=[start_date, end_date],
        invoice__status='confirmed'
    ).values(
        'product__name',
        'product__code'
    ).annotate(
        total_sold=Sum('quantity'),
        total_revenue=Sum('total')
    ).filter(total_sold__gte=10).order_by('-total_sold')[:10]
    
    # کالاهای کند گردش
    slow_moving = SalesInvoiceItem.objects.filter(
        invoice__invoice_date__range=[start_date, end_date],
        invoice__status='confirmed'
    ).values(
        'product__name',
        'product__code'
    ).annotate(
        total_sold=Sum('quantity'),
        total_revenue=Sum('total')
    ).filter(total_sold__lt=5).order_by('total_sold')[:10]
    
    return {
        'start_date': start_date,
        'end_date': end_date,
        'fast_moving': fast_moving,
        'slow_moving': slow_moving,
    }

def get_quantity_sales_data(request):
    """داده‌های فروش تعدادی"""
    from django.db.models import Sum, Count
    
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if not start_date or not end_date:
        today = datetime.now()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
    
    # فروش تعدادی
    quantity_sales = SalesInvoiceItem.objects.filter(
        invoice__invoice_date__range=[start_date, end_date],
        invoice__status='confirmed'
    ).values(
        'product__name',
        'product__code'
    ).annotate(
        total_quantity=Sum('quantity'),
        total_amount=Sum('total'),
        avg_quantity=Sum('quantity') / Count('invoice', distinct=True)
    ).order_by('-total_quantity')
    
    return {
        'start_date': start_date,
        'end_date': end_date,
        'quantity_sales': quantity_sales,
    }

def get_stock_depletion_data(request):
    """داده‌های تخمین زمان اتمام موجودی"""
    from django.db.models import Sum, Avg, F, ExpressionWrapper, DecimalField
    
    # تخمین زمان اتمام موجودی بر اساس فروش متوسط
    stock_depletion = Product.objects.annotate(
        avg_daily_sales=ExpressionWrapper(
            F('sales_invoice_items__quantity') / 30,  # فرض 30 روز
            output_field=DecimalField()
        ),
        days_to_depletion=ExpressionWrapper(
            F('quantity') / F('avg_daily_sales'),
            output_field=DecimalField()
        )
    ).filter(quantity__gt=0).order_by('days_to_depletion')
    
    return {
        'stock_depletion': stock_depletion,
    }

# =============================================================================
# توابع داده‌های عملیاتی
# =============================================================================

def get_order_status_data(request):
    """داده‌های وضعیت سفارشات"""
    from django.db.models import Count
    
    # سفارشات بر اساس وضعیت
    orders = Order.objects.select_related('customer').order_by('-created_at')
    completed_orders = orders.filter(status='completed')
    pending_orders = orders.filter(status__in=['pending', 'warehouse', 'ready'])
    
    return {
        'orders': orders,
        'completed_orders': completed_orders,
        'pending_orders': pending_orders,
    }

def get_shipping_delivery_data(request):
    """داده‌های ارسال و تحویل"""
    from django.db.models import Count
    
    # ارسال‌ها
    shipments = Shipment.objects.select_related('order').order_by('-shipment_date')
    delivered_shipments = shipments.filter(status='delivered')
    in_transit_shipments = shipments.filter(status='in_transit')
    
    return {
        'shipments': shipments,
        'delivered_shipments': delivered_shipments,
        'in_transit_shipments': in_transit_shipments,
    }

def get_overdue_orders_data(request):
    """داده‌های سفارشات معوق"""
    from datetime import timedelta
    
    # سفارشات معوق (بیش از 7 روز)
    cutoff_date = timezone.now() - timedelta(days=7)
    overdue_orders = Order.objects.filter(
        created_at__lt=cutoff_date,
        status__in=['pending', 'warehouse', 'ready']
    ).select_related('customer').order_by('created_at')
    
    return {
        'overdue_orders': overdue_orders,
        'cutoff_date': cutoff_date,
    }

def get_purchase_invoices_data(request):
    """داده‌های فاکتورهای خرید"""
    from django.db.models import Sum
    
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if not start_date or not end_date:
        today = datetime.now()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
    
    # فاکتورهای خرید
    purchase_invoices = PurchaseInvoice.objects.filter(
        invoice_date__range=[start_date, end_date],
        status='confirmed'
    ).select_related('customer').order_by('-invoice_date')
    
    total_amount = purchase_invoices.aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    return {
        'start_date': start_date,
        'end_date': end_date,
        'purchase_invoices': purchase_invoices,
        'total_amount': total_amount,
    }

def get_price_change_history_data(request):
    """داده‌های تاریخ تغییر قیمت کالاها"""
    from django.db.models import Count
    
    # تغییرات قیمت
    price_changes = PriceChange.objects.select_related('product').order_by('-change_date')
    
    return {
        'price_changes': price_changes,
    }

# =============================================================================
# توابع داده‌های مشتریان
# =============================================================================

def get_customer_list_data(request):
    """داده‌های لیست مشتریان"""
    from django.db.models import Count, Sum
    
    # مشتریان با آمار سفارش
    customers = Customer.objects.annotate(
        order_count=Count('orders'),
        total_purchase=Sum('orders__total_price')
    ).order_by('-order_count')
    
    active_customers = customers.filter(order_count__gt=0)
    new_customers = customers.filter(created_at__month=timezone.now().month)
    
    return {
        'customers': customers,
        'active_customers': active_customers,
        'new_customers': new_customers,
    }

def get_debtors_data(request):
    """داده‌های بدهکاران"""
    # مشتریان با مانده بدهی
    debtors = Customer.objects.filter(
        customer_balance__current_balance__gt=0
    ).select_related('customer_balance').order_by('-customer_balance__current_balance')
    
    return {
        'debtors': debtors,
    }

def get_creditors_data(request):
    """داده‌های بستانکاران"""
    # مشتریان با مانده بستانکاری
    creditors = Customer.objects.filter(
        customer_balance__current_balance__lt=0
    ).select_related('customer_balance').order_by('customer_balance__current_balance')
    
    return {
        'creditors': creditors,
    }

def get_customer_statements_data(request):
    """داده‌های صورت حساب مشتریان"""
    from django.db.models import Sum
    
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if not start_date or not end_date:
        today = datetime.now()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
    
    # صورت حساب مشتریان
    customer_statements = Customer.objects.annotate(
        total_sales=Sum('sales_invoices__total_amount'),
        total_purchases=Sum('purchase_invoices__total_amount')
    ).filter(
        sales_invoices__invoice_date__range=[start_date, end_date]
    ).distinct()
    
    return {
        'start_date': start_date,
        'end_date': end_date,
        'customer_statements': customer_statements,
    }
def bank_account_create_view(request):
    """
    ایجاد حساب بانکی جدید
    """
    from .forms import BankAccountForm
    from .models import Account, BankAccount, AccountGroup, Currency
    
    if request.method == 'POST':
        form = BankAccountForm(request.POST)
        if form.is_valid():
            try:
                # Get default currency (IRR)
                default_currency = Currency.objects.filter(is_default=True).first()
                if not default_currency:
                    # Create default currency if it doesn't exist
                    default_currency = Currency.objects.create(
                        code='IRR',
                        name='ریال',
                        symbol='﷼',
                        is_default=True,
                        exchange_rate=1
                    )
                
                # Get or create bank account group
                bank_group, created = AccountGroup.objects.get_or_create(
                    name='حساب‌های بانکی',
                    defaults={'code': '1200', 'description': 'حساب‌های بانکی و نقدی'}
                )
                
                # Create the Account record first
                account = Account.objects.create(
                    group=bank_group,
                    code=f"1200{Account.objects.filter(group=bank_group).count() + 1:03d}",
                    name=form.cleaned_data['title'],
                    level='DETAIL',
                    currency=default_currency,
                    opening_balance=form.cleaned_data['initial_balance'],
                    current_balance=form.cleaned_data['initial_balance'],
                    description=f"حساب بانکی {form.cleaned_data['bank'].name} - {form.cleaned_data['account_number']}"
                )
                
                # Create the BankAccount record
                bank_account = form.save(commit=False)
                bank_account.account = account
                bank_account.created_by = request.user
                bank_account.current_balance = bank_account.initial_balance
                bank_account.save()
                
                messages.success(request, 'حساب بانکی با موفقیت ایجاد شد.')
                return redirect('products:bank_account_list')
            except Exception as e:
                messages.error(request, f'خطا در ایجاد حساب بانکی: {str(e)}')
    else:
        form = BankAccountForm()
    
    return render(request, 'products/bank_account_form.html', {
        'form': form, 
        'title': 'تعریف حساب بانکی جدید'
    })


@login_required
@group_required('حسابداری')
def bank_account_list_view(request):
    """
    نمایش لیست حساب‌های بانکی
    """
    bank_accounts = BankAccount.objects.select_related('bank', 'account', 'created_by').order_by('-created_at')
    
    context = {
        'bank_accounts': bank_accounts,
        'title': 'لیست حساب‌های بانکی'
    }
    
    return render(request, 'products/bank_account_list.html', context)


@login_required
@group_required('حسابداری')
def bank_account_detail_view(request, bank_account_id):
    """
    نمایش جزئیات حساب بانکی
    """
    from django.shortcuts import get_object_or_404
    
    bank_account = get_object_or_404(BankAccount.objects.select_related(
        'bank', 'account', 'created_by'
    ), id=bank_account_id)
    
    # Defensive recalculation to ensure the balance is always up-to-date
    _update_bank_account_balance(bank_account.bank.name, bank_account.account_number)
    bank_account.refresh_from_db()  # Refresh the object to get the updated balance
    
    # چک‌های واگذار شده به این حساب بانکی (مرتب شده بر اساس تاریخ سررسید)
    deposited_checks = ReceivedCheque.objects.filter(
        status='DEPOSITED',
        deposited_bank_account=bank_account
    ).select_related('customer').order_by('-due_date', '-cleared_at', '-created_at')
    
    context = {
        'bank_account': bank_account,
        'title': f'جزئیات حساب بانکی {bank_account.title}',
        'deposited_checks': deposited_checks
    }
    
    return render(request, 'products/bank_account_detail.html', context)


@login_required
@group_required('حسابداری')
@require_POST
def clear_received_check(request, check_id):
    """
    وصول چک دریافتی و اضافه کردن مبلغ به حساب بانکی
    """
    import json
    
    try:
        check = get_object_or_404(ReceivedCheque, id=check_id)
        
        if check.status != 'DEPOSITED':
            return JsonResponse({
                'success': False,
                'error': 'تنها چک‌های واگذار شده قابل وصول هستند'
            })
        
        bank_account = check.deposited_bank_account
        if not bank_account:
            return JsonResponse({
                'success': False,
                'error': 'حساب بانکی مرتبط با چک یافت نشد'
            })
        
        with transaction.atomic():
            # تغییر وضعیت چک به وصول شده
            check.status = 'CLEARED'
            check.cleared_at = timezone.now()
            check.cleared_by = request.user
            check.save()
            
            # اضافه کردن مبلغ به حساب بانکی
            bank_account.current_balance += check.amount
            bank_account.save()
            
            # ایجاد عملیات مالی برای وصول چک
            operation = FinancialOperation.objects.create(
                operation_type='CHECK_CLEARANCE',
                amount=check.amount,
                payment_method='cheque',
                date=timezone.now().date(),
                description=f"وصول چک دریافتی با شناسه صیادی {check.sayadi_id} از {check.customer.get_full_name()}",
                created_by=request.user,
                status='CONFIRMED',
                confirmed_by=request.user,
                confirmed_at=timezone.now()
            )
            
            # ربط چک به عملیات مالی
            check.financial_operation = operation
            check.save()
        
        return JsonResponse({
            'success': True,
            'message': 'چک با موفقیت وصول شد',
            'new_balance': float(bank_account.current_balance)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@group_required('حسابداری')
@require_POST
def bounce_received_check(request, check_id):
    """
    برگشت چک دریافتی و انتقال به چک‌های نزد صندوق
    """
    import json
    
    try:
        check = get_object_or_404(ReceivedCheque, id=check_id)
        
        if check.status != 'DEPOSITED':
            return JsonResponse({
                'success': False,
                'error': 'تنها چک‌های واگذار شده قابل برگشت هستند'
            })
        
        with transaction.atomic():
            # تغییر وضعیت چک به برگشت خورده
            check.status = 'BOUNCED'
            check.bounced_at = timezone.now()
            check.bounced_by = request.user
            # حذف ارتباط با حساب بانکی
            check.deposited_bank_account = None
            check.save()
            
            # ایجاد عملیات مالی برای برگشت چک
            operation = FinancialOperation.objects.create(
                operation_type='CHECK_BOUNCE',
                amount=check.amount,
                payment_method='cheque',
                date=timezone.now().date(),
                description=f"برگشت چک دریافتی با شناسه صیادی {check.sayadi_id} از {check.customer.get_full_name()}",
                created_by=request.user,
                status='CONFIRMED',
                confirmed_by=request.user,
                confirmed_at=timezone.now()
            )
            
            # ربط چک به عملیات مالی
            check.financial_operation = operation
            check.save()
        
        return JsonResponse({
            'success': True,
            'message': 'چک با موفقیت برگشت خورد و به چک‌های نزد صندوق منتقل شد'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@group_required('حسابداری')
@require_POST
def clear_issued_check(request, check_id):
    """
    وصول چک صادر شده و کسر مبلغ از حساب بانکی
    """
    import json
    
    try:
        check = get_object_or_404(Check, id=check_id)
        
        if check.status != 'ISSUED':
            return JsonResponse({
                'success': False,
                'error': 'تنها چک‌های صادر شده قابل وصول هستند'
            })
        
        bank_account = check.checkbook.bank_account
        if not bank_account:
            return JsonResponse({
                'success': False,
                'error': 'حساب بانکی مرتبط با چک یافت نشد'
            })
        
        # Check if bank account has sufficient balance
        if bank_account.current_balance < check.amount:
            return JsonResponse({
                'success': False,
                'error': f'موجودی حساب کافی نیست. موجودی فعلی: {bank_account.current_balance:,} ریال'
            })
        
        with transaction.atomic():
            # تغییر وضعیت چک به وصول شده
            check.status = 'CLEARED'
            check.cleared_at = timezone.now()
            check.cleared_by = request.user
            check.save()
            
            # کسر مبلغ از حساب بانکی
            bank_account.current_balance -= check.amount
            bank_account.save()
            
            # ایجاد عملیات مالی برای وصول چک
            operation = FinancialOperation.objects.create(
                operation_type='ISSUED_CHECK_CLEARANCE',
                amount=check.amount,
                payment_method='cheque',
                date=timezone.now().date(),
                description=f"وصول چک صادر شده شماره {check.number} در وجه {check.payee}",
                created_by=request.user,
                status='CONFIRMED',
                confirmed_by=request.user,
                confirmed_at=timezone.now()
            )
        
        return JsonResponse({
            'success': True,
            'message': 'چک با موفقیت وصول شد',
            'new_balance': float(bank_account.current_balance)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@group_required('حسابداری')
@require_POST
def bounce_issued_check(request, check_id):
    """
    برگشت چک صادر شده و اضافه کردن مبلغ به حساب مشتری
    """
    import json
    
    try:
        check = get_object_or_404(Check, id=check_id)
        
        if check.status != 'ISSUED':
            return JsonResponse({
                'success': False,
                'error': 'تنها چک‌های صادر شده قابل برگشت هستند'
            })
        
        # پیدا کردن مشتری بر اساس نام در وجه
        customer = None
        if check.payee:
            try:
                # ابتدا جستجوی دقیق نام کامل
                payee_parts = check.payee.strip().split()
                if len(payee_parts) >= 2:
                    # جستجوی دقیق با نام و نام خانوادگی
                    customer = Customer.objects.filter(
                        first_name__icontains=payee_parts[0],
                        last_name__icontains=payee_parts[-1]
                    ).first()
                
                # اگر پیدا نشد، جستجوی کلی انجام بده
                if not customer:
                    from django.db.models import Q
                    customer = Customer.objects.filter(
                        Q(first_name__icontains=check.payee) | 
                        Q(last_name__icontains=check.payee) |
                        Q(store_name__icontains=check.payee)
                    ).first()
            except Exception as e:
                print(f"خطا در جستجوی مشتری: {e}")
                pass
        
        with transaction.atomic():
            # تغییر وضعیت چک به برگشت خورده
            check.status = 'BOUNCED'
            check.bounced_at = timezone.now()
            check.bounced_by = request.user
            check.save()
            
            # اگر مشتری پیدا شد، عملیات مالی ایجاد کن
            if customer:
                # ایجاد عملیات مالی برای برگشت چک صادر شده
                operation = FinancialOperation.objects.create(
                    operation_type='ISSUED_CHECK_BOUNCE',
                    amount=check.amount,
                    payment_method='cheque',
                    date=timezone.now().date(),
                    description=f"برگشت چک صادر شده شماره {check.number} در وجه {check.payee}",
                    customer=customer,
                    created_by=request.user,
                    status='CONFIRMED',
                    confirmed_by=request.user,
                    confirmed_at=timezone.now()
                )
                
                # به‌روزرسانی موجودی مشتری (بستانکار)
                customer_balance, created = CustomerBalance.objects.get_or_create(customer=customer)
                customer_balance.update_balance()
                
                message = f'چک برگشتی شماره {check.number} با موفقیت به {customer.get_full_name()} برگشت داده شد و مبلغ {check.amount:,} ریال به عنوان بستانکاری مشتری ثبت گردید. سند شماره: {operation.operation_number}'
            else:
                # ایجاد عملیات مالی بدون مشتری
                operation = FinancialOperation.objects.create(
                    operation_type='ISSUED_CHECK_BOUNCE',
                    amount=check.amount,
                    payment_method='cheque',
                    date=timezone.now().date(),
                    description=f"برگشت چک صادر شده شماره {check.number} در وجه {check.payee} (مشتری شناسایی نشد)",
                    created_by=request.user,
                    status='CONFIRMED',
                    confirmed_by=request.user,
                    confirmed_at=timezone.now()
                )
                
                message = 'چک با موفقیت برگشت خورد (مشتری مرتبط شناسایی نشد)'
        
        return JsonResponse({
            'success': True,
            'message': message
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@group_required('حسابداری')
@require_POST
def reset_issued_check(request, check_id):
    """
    بازگشت چک صادر شده به حالت اولیه (UNUSED) و اصلاح عملیات مالی مرتبط
    """
    try:
        with transaction.atomic():
            check = get_object_or_404(Check.objects.select_for_update(), id=check_id)

            if check.status == 'UNUSED':
                return JsonResponse({'success': False, 'error': 'چک در حال حاضر در وضعیت اولیه قرار دارد.'})

            # Store related info before modification
            original_operation = check.financial_operation
            customer = original_operation.customer if original_operation else None

            # Reset the check to its initial state
            check.status = 'UNUSED'
            check.amount = 0
            check.date = None
            check.payee = ''
            check.description = ''
            check.series = ''
            check.sayadi_id = ''
            check.financial_operation = None
            check.cleared_at = None
            check.cleared_by = None
            check.bounced_at = None
            check.bounced_by = None
            check.save()

            if original_operation:
                # Recalculate the operation's amount from all associated checks (issued and spent)
                issued_total = original_operation.issued_checks.all().aggregate(total=Sum('amount'))['total'] or Decimal('0')
                spent_total = original_operation.spent_cheques.all().aggregate(total=Sum('amount'))['total'] or Decimal('0')
                new_amount = issued_total + spent_total

                if new_amount <= 0:
                    # If no checks are left, soft-delete the entire operation
                    original_operation.soft_delete(request.user)
                else:
                    # Otherwise, update the operation's amount and description
                    original_operation.amount = new_amount
                    
                    # Rebuild the description based on remaining checks
                    desc_parts = []
                    remaining_issued = original_operation.issued_checks.all()
                    if remaining_issued.exists():
                        desc_parts.append(f"صدور چک‌های: {', '.join([c.number for c in remaining_issued])}")
                    
                    remaining_spent = original_operation.spent_cheques.all()
                    if remaining_spent.exists():
                        desc_parts.append(f"خرج چک‌های دریافتی: {', '.join([c.serial for c in remaining_spent])}")
                    
                    original_operation.description = f"پرداخت به {customer.get_full_name() if customer else 'ناشناس'} - {' + '.join(desc_parts)}"
                    original_operation.save()

            # Trigger a balance update for the related customer
            if customer:
                # The post_save signal on FinancialOperation should handle this,
                # but an explicit call ensures correctness.
                customer_balance, _ = CustomerBalance.objects.get_or_create(customer=customer)
                customer_balance.update_balance()

        return JsonResponse({
            'success': True,
            'message': 'چک با موفقیت به حالت اولیه بازگشت و عملیات مالی مرتبط اصلاح شد.'
        })

    except Check.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'چک یافت نشد.'}, status=404)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': f'خطای سیستمی: {str(e)}'}, status=500)


@login_required
@group_required('حسابداری')
def available_checks_for_deposit_view(request, bank_account_id):
    """
    نمایش لیست چک‌های قابل واگذاری به بانک
    """
    bank_account = get_object_or_404(BankAccount, id=bank_account_id)
    
    # چک‌های دریافتی که در صندوق هستند (وضعیت RECEIVED)
    available_checks = ReceivedCheque.objects.filter(
        status='RECEIVED'
    ).order_by('-due_date', '-created_at')
    
    if request.method == 'POST':
        selected_check_ids = request.POST.getlist('selected_checks')
        if selected_check_ids:
            return redirect('products:deposit_confirmation', bank_account_id=bank_account_id, check_ids=','.join(selected_check_ids))
        else:
            messages.error(request, 'لطفاً حداقل یک چک انتخاب کنید.')
    
    context = {
        'bank_account': bank_account,
        'available_checks': available_checks,
        'title': f'چک‌های قابل واگذاری به {bank_account.bank.name}'
    }
    
    return render(request, 'products/available_checks_for_deposit.html', context)


@login_required
@group_required('حسابداری')
def deposit_confirmation_view(request, bank_account_id, check_ids):
    """
    صفحه تایید واگذاری چک‌ها به بانک
    """
    bank_account = get_object_or_404(BankAccount, id=bank_account_id)
    check_id_list = check_ids.split(',')
    
    # دریافت چک‌های انتخاب شده
    selected_checks = ReceivedCheque.objects.filter(
        id__in=check_id_list,
        status='RECEIVED'
    ).order_by('-due_date', '-created_at')
    
    if not selected_checks.exists():
        messages.error(request, 'چک‌های انتخاب شده یافت نشد یا وضعیت آن‌ها برای واگذاری مناسب نیست.')
        return redirect('products:available_checks_for_deposit', bank_account_id=bank_account_id)
    
    total_amount = sum(check.amount for check in selected_checks)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # تغییر وضعیت چک‌ها به DEPOSITED و تنظیم حساب بانکی واگذار شده
                selected_checks.update(status='DEPOSITED', deposited_bank_account=bank_account)
                
                # ایجاد عملیات مالی برای واگذاری چک‌ها
                check_serials = ", ".join(check.sayadi_id for check in selected_checks)
                operation = FinancialOperation.objects.create(
                    operation_type='DEPOSIT_TO_BANK',
                    amount=total_amount,
                    payment_method='cheque',
                    date=timezone.now().date(),
                    description=f"واگذاری {selected_checks.count()} فقره چک دریافتی به بانک {bank_account.bank.name} - شناسه‌های صیادی: {check_serials}",
                    created_by=request.user,
                    status='CONFIRMED',
                    confirmed_by=request.user,
                    confirmed_at=timezone.now()
                )
                
                # ربط چک‌ها به عملیات مالی
                operation.received_cheques.set(selected_checks)
                
            messages.success(request, f'{selected_checks.count()} فقره چک با مجموع مبلغ {total_amount:,} ریال با موفقیت به بانک {bank_account.bank.name} واگذار شد.')
            return redirect('products:bank_account_detail', bank_account_id=bank_account_id)
            
        except Exception as e:
            messages.error(request, f'خطا در واگذاری چک‌ها: {str(e)}')
    
    context = {
        'bank_account': bank_account,
        'selected_checks': selected_checks,
        'total_amount': total_amount,
        'title': f'تایید واگذاری چک‌ها به {bank_account.bank.name}'
    }
    
    return render(request, 'products/deposit_confirmation.html', context)


@login_required
@group_required('حسابداری')
def checkbook_detail_view(request, checkbook_id):
    """
    نمایش جزئیات دسته چک
    """
    from django.shortcuts import get_object_or_404
    from .models import CheckBook, Check
    
    checkbook = get_object_or_404(CheckBook.objects.select_related(
        'bank_account', 'bank_account__bank', 'created_by'
    ), id=checkbook_id)
    
    # دریافت چک‌های مرتبط با مرتب‌سازی هوشمند
    # راه‌حل ساده: جداگانه query کردن و سپس ترکیب کردن
    unused_checks = Check.objects.filter(
        checkbook=checkbook, 
        status='UNUSED'
    ).order_by('number')
    
    other_checks = Check.objects.filter(
        checkbook=checkbook
    ).exclude(
        status='UNUSED'
    ).order_by('date', '-cleared_at', '-bounced_at', '-created_at')
    
    # ترکیب دو queryset به صورت لیست (چک‌های صادر شده اول، سپس UNUSED)
    checks = list(other_checks) + list(unused_checks)
    
    context = {
        'checkbook': checkbook,
        'checks': checks,
        'title': f'جزئیات دسته چک {checkbook.serial}'
    }
    
    return render(request, 'products/checkbook_detail.html', context)


@login_required
@group_required('حسابداری')
def checkbook_edit_view(request, checkbook_id):
    """
    ویرایش دسته چک
    """
    from django.shortcuts import get_object_or_404, redirect
    from .forms import CheckBookForm
    from .models import CheckBook
    
    checkbook = get_object_or_404(CheckBook, id=checkbook_id)
    
    if request.method == 'POST':
        form = CheckBookForm(request.POST, instance=checkbook)
        if form.is_valid():
            form.save()
            messages.success(request, 'دسته چک با موفقیت ویرایش شد.')
            return redirect('products:checkbook_detail', checkbook_id=checkbook.id)
    else:
        form = CheckBookForm(instance=checkbook)
    
    context = {
        'form': form,
        'checkbook': checkbook,
        'title': f'ویرایش دسته چک {checkbook.serial}'
    }
    
    return render(request, 'products/checkbook_edit.html', context)


@login_required
@group_required('حسابداری')
def issued_checks_report_view(request, checkbook_id):
    """
    گزارش چک‌های خرجی
    """
    from django.shortcuts import get_object_or_404
    from .models import CheckBook, Check
    from django.db import models
    
    checkbook = get_object_or_404(CheckBook.objects.select_related(
        'bank_account', 'bank_account__bank'
    ), id=checkbook_id)
    
    # دریافت چک‌های صادر شده
    issued_checks = Check.objects.filter(
        checkbook=checkbook,
        status__in=['ISSUED', 'RECEIVED', 'DEPOSITED', 'CLEARED', 'BOUNCED']
    ).order_by('-date', '-cleared_at', '-bounced_at', '-created_at')
    
    # محاسبه آمار
    total_amount = issued_checks.aggregate(
        total=models.Sum('amount')
    )['total'] or 0
    
    cleared_amount = issued_checks.filter(status='CLEARED').aggregate(
        total=models.Sum('amount')
    )['total'] or 0
    
    bounced_amount = issued_checks.filter(status='BOUNCED').aggregate(
        total=models.Sum('amount')
    )['total'] or 0
    
    pending_amount = issued_checks.filter(
        status__in=['ISSUED', 'RECEIVED', 'DEPOSITED']
    ).aggregate(
        total=models.Sum('amount')
    )['total'] or 0
    
    context = {
        'checkbook': checkbook,
        'issued_checks': issued_checks,
        'total_amount': total_amount,
        'cleared_amount': cleared_amount,
        'bounced_amount': bounced_amount,
        'pending_amount': pending_amount,
        'title': f'گزارش چک‌های خرجی - {checkbook.serial}'
    }
    
    return render(request, 'products/issued_checks_report.html', context)


@login_required
@group_required('حسابداری')
def all_issued_checks_view(request):
    """
    نمایش تمام چک‌های صادر شده با امکان فیلتر بر اساس وضعیت
    """
    from django.db import models
    
    # فیلتر بر اساس وضعیت
    status_filter = request.GET.get('status', None)
    
    # دریافت تمام چک‌های صادر شده (بجز چک‌های استفاده نشده)
    issued_checks = Check.objects.filter(
        checkbook__isnull=False  # فقط چک‌های صادر شده
    ).exclude(
        status='UNUSED'  # حذف چک‌های استفاده نشده
    ).select_related('checkbook', 'checkbook__bank_account', 'created_by')
    
    if status_filter:
        issued_checks = issued_checks.filter(status=status_filter)
    
    # مرتب‌سازی بر اساس تاریخ سررسید (جدیدترین اول)
    issued_checks = issued_checks.order_by('-date', '-cleared_at', '-bounced_at', '-created_at')
    
    # محاسبه آمار
    total_amount = issued_checks.aggregate(
        total=models.Sum('amount')
    )['total'] or 0
    
    cleared_amount = issued_checks.filter(status='CLEARED').aggregate(
        total=models.Sum('amount')
    )['total'] or 0
    
    bounced_amount = issued_checks.filter(status='BOUNCED').aggregate(
        total=models.Sum('amount')
    )['total'] or 0
    
    pending_amount = issued_checks.filter(
        status__in=['ISSUED', 'RECEIVED', 'DEPOSITED']
    ).aggregate(
        total=models.Sum('amount')
    )['total'] or 0
    
    # Determine page title based on status filter
    status_titles = {
        'ISSUED': 'لیست چکهای صادر شده',
        'CLEARED': 'لیست چکهای وصول شده (صادری)',
        'BOUNCED': 'لیست چکهای برگشتی (صادری)',
        'RECEIVED': 'لیست چکهای دریافت شده',
        'DEPOSITED': 'لیست چکهای واگذار شده',
    }
    
    if status_filter and status_filter in status_titles:
        page_title = status_titles[status_filter]
    else:
        page_title = 'لیست چکهای صادر شده'

    context = {
        'issued_checks': issued_checks,
        'total_amount': total_amount,
        'cleared_amount': cleared_amount,
        'bounced_amount': bounced_amount,
        'pending_amount': pending_amount,
        'status_filter': status_filter,
        'page_title': page_title,
        'title': page_title  # Keep title for backward compatibility
    }
    
    return render(request, 'products/all_issued_checks.html', context)


@login_required
@group_required('حسابداری')
@transaction.atomic
def issued_check_edit_view(request, check_id):
    check = get_object_or_404(Check, id=check_id)
    if not check.checkbook:
        messages.error(request, 'این چک پرداختی نیست یا به دسته چک تعلق ندارد.')
        return redirect('products:accounting_panel')

    if request.method == 'POST':
        form = IssuedCheckEditForm(request.POST, instance=check)
        if form.is_valid():
            form.save()
            messages.success(request, f'چک شماره {check.number} با موفقیت ویرایش شد.')
            return redirect('products:checkbook_detail', checkbook_id=check.checkbook.id)
    else:
        form = IssuedCheckEditForm(instance=check)

    return render(request, 'products/issued_check_edit.html', {
        'form': form,
        'check': check,
    })


@login_required
@group_required('حسابداری')
@require_POST
@transaction.atomic
def issued_check_delete_view(request, check_id):
    check = get_object_or_404(Check, id=check_id)
    if not check.checkbook:
        messages.error(request, 'این چک پرداختی نیست یا به دسته چک تعلق ندارد.')
        return redirect('products:accounting_panel')

    allowed_statuses = ['UNUSED', 'ISSUED', 'VOID']
    if check.status not in allowed_statuses:
        messages.error(request, 'حذف این چک در وضعیت فعلی مجاز نیست.')
        return redirect('products:checkbook_detail', checkbook_id=check.checkbook.id)

    checkbook_id = check.checkbook.id
    check_number = check.number
    check.delete()
    messages.success(request, f'چک شماره {check_number} با موفقیت حذف شد.')
    return redirect('products:checkbook_detail', checkbook_id=checkbook_id)


@login_required
@group_required('حسابداری')
def bank_account_edit_view(request, bank_account_id):
    """
    ویرایش حساب بانکی
    """
    from django.shortcuts import get_object_or_404, redirect
    from .forms import BankAccountForm, CheckBookForm
    
    bank_account = get_object_or_404(BankAccount, id=bank_account_id)
    
    # Initialize forms
    form = BankAccountForm(instance=bank_account)
    checkbook_form = CheckBookForm()
    
    if request.method == 'POST':
        if 'add_checkbook' in request.POST:
            # اضافه کردن دسته چک جدید
            checkbook_form = CheckBookForm(request.POST)
            if checkbook_form.is_valid():
                checkbook = checkbook_form.save(commit=False)
                checkbook.bank_account = bank_account
                checkbook.created_by = request.user
                checkbook.save()
                
                # ایجاد چک‌ها
                start_number = checkbook_form.cleaned_data.get('start_number')
                end_number = checkbook_form.cleaned_data.get('end_number')
                
                if start_number and end_number:
                    from .models import Check
                    for check_number in range(start_number, end_number + 1):
                        Check.objects.create(
                            checkbook=checkbook,
                            number=str(check_number),
                            status='UNUSED',
                            amount=0,  # مقدار پیش‌فرض
                            date=timezone.now().date(),  # تاریخ پیش‌فرض
                            payee='',  # خالی
                            description='',  # خالی
                            created_by=request.user  # کاربر ایجاد کننده
                        )
                
                messages.success(request, 'دسته چک با موفقیت اضافه شد.')
                return redirect('products:bank_account_detail', bank_account_id=bank_account.id)
        else:
            # ویرایش اطلاعات حساب بانکی
            form = BankAccountForm(request.POST, instance=bank_account)
            if form.is_valid():
                new_balance = form.cleaned_data.get('new_balance')
                
                # Save the form to update fields like initial_balance
                bank_account = form.save(commit=False)
                
                if new_balance is not None and new_balance != '':
                    # If a manual balance is provided, use it
                    bank_account.current_balance = new_balance
                    bank_account.save()
                    messages.success(request, f'حساب بانکی با موفقیت ویرایش و موجودی به صورت دستی به {new_balance:,.2f} ریال تغییر یافت.')
                else:
                    # Otherwise, save the changes (like initial_balance) and then recalculate
                    bank_account.save()
                    _update_bank_account_balance(bank_account.bank.name, bank_account.account_number)
                    messages.success(request, 'حساب بانکی با موفقیت ویرایش شد و موجودی مجدداً محاسبه گردید.')
                
                return redirect('products:bank_account_list')
    
    context = {
        'form': form,
        'checkbook_form': checkbook_form,
        'bank_account': bank_account,
        'title': f'ویرایش حساب بانکی {bank_account.title}'
    }
    
    return render(request, 'products/bank_account_edit.html', context)


@login_required
@group_required('حسابداری')
def bank_statement_view(request, bank_account_id):
    """
    نمایش صورتحساب بانکی
    """
    from django.shortcuts import get_object_or_404
    from django.db.models import Sum
    from datetime import datetime
    
    bank_account = get_object_or_404(BankAccount, id=bank_account_id)
    
    # Defensive recalculation to ensure the balance is always up-to-date
    _update_bank_account_balance(bank_account.bank.name, bank_account.account_number)
    bank_account.refresh_from_db()
    
    # Define which operations are credits (deposits) and debits (withdrawals) for a bank account
    CREDIT_OPS = ['RECEIVE_FROM_CUSTOMER', 'PAY_TO_BANK', 'CAPITAL_INVESTMENT']
    DEBIT_OPS = ['PAY_TO_CUSTOMER', 'RECEIVE_FROM_BANK', 'BANK_TRANSFER']

    # دریافت پارامترهای فیلتر
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # فیلتر کردن تراکنش‌ها - بر اساس نام بانک و شماره حساب
    transactions_query = FinancialOperation.objects.filter(
        bank_name=bank_account.bank.name,
        account_number=bank_account.account_number
    )
    
    # Apply date filters if they exist
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            transactions_query = transactions_query.filter(date__gte=start_date_obj)
        except (ValueError, TypeError):
            start_date = None
    
    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            transactions_query = transactions_query.filter(date__lte=end_date_obj)
        except (ValueError, TypeError):
            end_date = None
            
    # Order transactions chronologically for calculation
    transactions = transactions_query.order_by('date', 'created_at')

    # Get the count of actual database transactions before converting to a list
    transaction_count = transactions.count()

    # Create a separate query for calculations that excludes deleted items
    transactions_for_calc = transactions_query.filter(is_deleted=False, status='CONFIRMED')

    # Calculate totals for the stats box using the correct query
    total_credit = transactions_for_calc.filter(operation_type__in=CREDIT_OPS).aggregate(Sum('amount'))['amount__sum'] or 0
    total_debit = transactions_for_calc.filter(operation_type__in=DEBIT_OPS).aggregate(Sum('amount'))['amount__sum'] or 0

    # Start with the opening balance
    running_balance = bank_account.initial_balance
    
    # Create the list for display, starting with the opening balance
    display_operations = [{
        'date': bank_account.created_at,
        'description': "موجودی اول دوره",
        'credit': bank_account.initial_balance if bank_account.initial_balance >= 0 else 0,
        'debit': abs(bank_account.initial_balance) if bank_account.initial_balance < 0 else 0,
        'is_credit': bank_account.initial_balance >= 0,
        'balance_after': running_balance,
        'operation': None, # No actual operation object
    }]

    # Process all other operations
    for op in transactions:
        is_credit = op.operation_type in CREDIT_OPS
        
        if is_credit:
            running_balance += op.amount
            credit_amount = op.amount
            debit_amount = 0
        else: # is_debit
            running_balance -= op.amount
            credit_amount = 0
            debit_amount = op.amount
        
        display_operations.append({
            'date': op.date,
            'description': op.description or op.get_operation_type_display(),
            'credit': credit_amount,
            'debit': debit_amount,
            'is_credit': is_credit,
            'balance_after': running_balance,
            'operation': op
        })
    
    # Reverse for display (newest first)
    display_operations.reverse()

    context = {
        'bank_account': bank_account,
        'transactions': display_operations,
        'transaction_count': transaction_count,
        'total_credit': total_credit,
        'total_debit': total_debit,
        'final_balance': bank_account.current_balance,
        'start_date': start_date,
        'end_date': end_date,
        'title': f'صورتحساب بانکی - {bank_account.title}',
        'initial_balance': bank_account.initial_balance,
        'current_balance': bank_account.current_balance,
    }
    
    return render(request, 'products/bank_statement.html', context)


@login_required
@group_required('حسابداری')
def voucher_list_view(request):
    """
    نمایش لیست اسناد حسابداری
    """
    from .models import Voucher
    
    vouchers = Voucher.objects.select_related(
        'financial_year', 'created_by', 'confirmed_by'
    ).prefetch_related('items__account').order_by('-date', '-created_at')
    
    # محاسبه آمار
    confirmed_count = vouchers.filter(is_confirmed=True).count()
    unconfirmed_count = vouchers.filter(is_confirmed=False).count()
    
    context = {
        'vouchers': vouchers,
        'confirmed_count': confirmed_count,
        'unconfirmed_count': unconfirmed_count,
        'title': 'لیست اسناد حسابداری'
    }
    
    return render(request, 'products/voucher_list.html', context)


@login_required
@group_required('حسابداری')
def voucher_detail_view(request, voucher_id):
    """
    نمایش جزئیات سند حسابداری
    """
    from .models import Voucher
    from django.shortcuts import get_object_or_404
    from django.db.models import Sum
    
    voucher = get_object_or_404(Voucher.objects.select_related(
        'financial_year', 'created_by', 'confirmed_by'
    ).prefetch_related('items__account'), id=voucher_id)
    
    # محاسبه جمع کل بدهکار و بستانکار
    totals = voucher.items.aggregate(
        total_debit=Sum('debit'),
        total_credit=Sum('credit')
    )
    
    context = {
        'voucher': voucher,
        'total_debit': totals['total_debit'] or 0,
        'total_credit': totals['total_credit'] or 0,
        'title': f'سند حسابداری شماره {voucher.number}'
    }
    
    return render(request, 'products/voucher_detail.html', context)


@login_required
@group_required('حسابداری')
def fund_transactions_view(request, fund_id):
    """
    نمایش گردش صندوق
    """
    try:
        fund = Fund.objects.get(id=fund_id)
        transactions = fund.get_transactions()
        
        # محاسبه آمار
        total_in = sum(t.amount for t in transactions if t.transaction_type == 'IN')
        total_out = sum(t.amount for t in transactions if t.transaction_type == 'OUT')
        
        context = {
            'fund': fund,
            'transactions': transactions,
            'total_in': total_in,
            'total_out': total_out,
        }
        
        return render(request, 'products/fund_transactions.html', context)
        
    except Fund.DoesNotExist:
        messages.error(request, 'صندوق مورد نظر یافت نشد.')
        return redirect('products:fund_list')
    except Exception as e:
        messages.error(request, f'خطا در بارگذاری گردش صندوق: {str(e)}')
        return redirect('products:fund_list')

@login_required
def backorder_pdf(request, order_id):
    logger.info(f"Request received for PDF of backorder {order_id}")
    try:
        order = get_object_or_404(Order, id=order_id)
        # Filter for backordered items
        items = order.items.filter(warehouse_status='backorder')
        
        if not items.exists():
            return HttpResponse('هیچ کالای بک‌اوردر برای این سفارش یافت نشد.', status=404)

        logger.info(f"Backorder {order.order_number} found with {items.count()} backordered items")

        customer = order.customer.get_full_name() if order.customer else "-"
        order_number = order.order_number or "-"
        order_date = jdatetime.datetime.fromgregorian(datetime=order.created_at.replace(tzinfo=None)).strftime('%Y/%m/%d') if order.created_at else "-"
        visitor_name = order.visitor_name or "-"
        
        try:
            user = User.objects.get(username=order.visitor_name)
            visitor_name = f"{user.first_name} {user.last_name}".strip() or user.username
        except User.DoesNotExist:
            pass

        latex_content = f"""
\\documentclass[a4paper,12pt]{{article}}
\\usepackage{{geometry}}
\\geometry{{a4paper, margin=1in}}
\\usepackage{{longtable}}
\\usepackage{{colortbl}}
\\usepackage{{xcolor}}
\\usepackage{{setspace}}
\\usepackage{{graphicx}}
\\usepackage{{amssymb}}
\\setstretch{{1.2}}
\\usepackage{{xepersian}}
\\settextfont{{Vazirmatn}}
\\definecolor{{headerblue}}{{RGB}}{{217, 83, 79}}

\\begin{{document}}

\\begin{{center}}
    {{\\Huge \\textbf{{   لیست کسری سفارش   }}}} \\\\
\\end{{center}}

\\vspace{{0.5cm}}

\\noindent
\\begin{{tabular}}{{|p{{7cm}}|p{{7cm}}|}}
\\hline
\\textbf{{مشتری:}} {customer} & \\textbf{{تاریخ سفارش:}} {order_date} \\\\
\\hline
\\textbf{{ویزیتور:}} {visitor_name} & \\textbf{{شماره سفارش:}} {order_number} \\\\
\\hline
\\end{{tabular}}

\\vspace{{0.5cm}}

\\begin{{longtable}}{{|c|c|p{{6cm}}|c|c|}}
\\hline
\\rowcolor{{headerblue}} \\color{{white}}
\\textbf{{ردیف}} &  \\textbf{{کد کالا}} & \\textbf{{شرح کالا}} & \\textbf{{تعداد کسری}} & \\textbf{{انبار}} \\\\
\\hline
\\endhead
"""
        total_qty = 0
        for idx, item in enumerate(items, 1):
            product_code = item.product.code
            product_name = item.product.name
            quantity = item.requested_quantity - item.allocated_quantity
            total_qty += quantity
            warehouse = item.warehouse.name if item.warehouse else "نامشخص"
            latex_content += f"{idx} & {product_code} & {product_name} & {quantity} & {warehouse} \\\\\n\\hline\n"

        latex_content += f"""
\\end{{longtable}}

\\vspace{{0.3cm}}
\\noindent
\\begin{{tabular}}{{|p{{7cm}}|p{{7cm}}|}}
\\hline
\\textbf{{جمع کل تعداد کسری:}} & {total_qty} عدد \\\\
\\hline
\\end{{tabular}}

\\vspace{{1.5cm}}

\\noindent
مهر و امضا انباردار \\hspace{{8cm}} مهر و امضا مدیر فروش

\\end{{document}}
"""
        logger.info(f"LaTeX content generated for backorder {order_number}")

        temp_dir = os.path.join(settings.BASE_DIR, 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        tex_file = os.path.join(temp_dir, f'backorder_{order_number}.tex')
        with open(tex_file, 'w', encoding='utf-8') as f:
            f.write(latex_content)

        try:
            subprocess.run(['xelatex', '-output-directory', temp_dir, tex_file], check=True, capture_output=True, text=True, timeout=180)
        except subprocess.CalledProcessError as e:
            logger.error(f"xelatex failed for backorder {order_number}: {e.stderr}")
            return HttpResponse(f'خطا در کامپایل LaTeX: {e.stderr}', status=500)

        pdf_file = os.path.join(temp_dir, f'backorder_{order_number}.pdf')
        if not os.path.exists(pdf_file):
            return HttpResponse('فایل PDF تولید نشد.', status=500)
        with open(pdf_file, 'rb') as f:
            pdf_content = f.read()

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="backorder_{order_number}.pdf"'
        response.write(pdf_content)
        return response
    except Exception as e:
        logger.error(f"Backorder PDF generation failed: {str(e)}")
        return HttpResponse(f'خطا در ایجاد PDF کسری: {str(e)}', status=500)