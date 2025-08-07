import os
import django

# تنظیم محیط Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sefareshat_project.settings')
django.setup()

# اطمینان از وجود مسیر فایل‌ها
os.makedirs('products/templates', exist_ok=True)

# ذخیره فایل visitor_panel.html
with open('products/templates/visitor_panel.html', 'w', encoding='utf-8') as f:
    f.write('''{% extends 'products/base.html' %}
{% block content %}
<style>
    body { font-family: 'Vazir', Arial, sans-serif; direction: rtl; background-color: #f0f4f8; }
    .container { max-width: 1200px; margin: 20px auto; padding: 20px; }
    h3 { color: #2c3e50; text-align: center; margin-bottom: 20px; }
    .filter-search { display: flex; gap: 20px; margin-bottom: 20px; align-items: center; }
    .filter-search select, .filter-search input { padding: 10px; border-radius: 8px; border: 1px solid #ccc; width: 200px; }
    .autocomplete { position: relative; width: 300px; }
    .autocomplete-items { position: absolute; border: 1px solid #ddd; background: white; max-height: 200px; overflow-y: auto; z-index: 1000; width: 100%; border-radius: 8px; }
    .autocomplete-items div { padding: 10px; cursor: pointer; }
    .autocomplete-items div:hover { background: #e0e0e0; }
    .order-table { width: 100%; border-collapse: collapse; margin-top: 20px; background: white; border-radius: 8px; overflow: hidden; }
    .order-table th, .order-table td { padding: 12px; text-align: right; border-bottom: 1px solid #ddd; }
    .order-table th { background: #3498db; color: white; }
    .order-table select, .order-table input { padding: 5px; border-radius: 5px; border: 1px solid #ccc; }
    .total { font-weight: bold; color: #e74c3c; margin-top: 10px; text-align: left; }
    button { background: #2ecc71; color: white; padding: 10px 20px; border: none; border-radius: 8px; cursor: pointer; }
    button:hover { background: #27ae60; }
    .remove-item { background: #e74c3c; padding: 5px 10px; }
    .remove-item:hover { background: #c0392b; }
    #message { margin-top: 20px; }
    .success { color: #2ecc71; }
    .error { color: #e74c3c; }
</style>

<h3>پنل ویزیتور - ثبت سفارش</h3>
<div class="container">
    <form id="orderForm" method="POST">
        {% csrf_token %}
        <div class="filter-search">
            <div class="autocomplete">
                <input type="text" id="search" placeholder="جستجو بر اساس نام یا کد کالا" autocomplete="off">
                <div id="autocomplete-items" class="autocomplete-items"></div>
            </div>
            <select id="brandFilter">
                <option value="">همه برندها</option>
                {% for brand in brands %}
                    <option value="{{ brand.brand }}">{{ brand.brand }}</option>
                {% endfor %}
            </select>
            <select id="carGroupFilter">
                <option value="">همه گروه‌های خودرو</option>
                {% for car_group in car_groups %}
                    <option value="{{ car_group.car_group }}">{{ car_group.car_group }}</option>
                {% endfor %}
            </select>
        </div>
        <div>
            <label for="customer">نام مشتری:</label>
            <input type="text" id="customer" name="customer" required>
        </div>
        <h4>کالاهای انتخاب‌شده</h4>
        <table class="order-table">
            <thead>
                <tr>
                    <th>کد کالا</th>
                    <th>نام کالا</th>
                    <th>تعداد</th>
                    <th>قیمت</th>
                    <th>نحوه تسویه</th>
                    <th>جمع</th>
                    <th>حذف</th>
                </tr>
            </thead>
            <tbody id="selectedItems"></tbody>
        </table>
        <div class="total">جمع کل: <span id="totalPrice">0</span> تومان</div>
        <button type="submit">ثبت سفارش</button>
    </form>
    <div id="message"></div>
</div>

<script>
    let selectedProducts = [];

    async function fetchProducts(query = '', brand = '', carGroup = '') {
        try {
            const response = await fetch(`/api/products/?q=${encodeURIComponent(query)}&brand=${encodeURIComponent(brand)}&car_group=${encodeURIComponent(carGroup)}`);
            if (!response.ok) throw new Error('خطا در دریافت داده‌ها');
            return await response.json();
        } catch (error) {
            console.error('خطا:', error);
            return { products: [] };
        }
    }

    function updateSelectedItems() {
        const selectedItemsTable = document.getElementById('selectedItems');
        selectedItemsTable.innerHTML = '';
        let totalPrice = 0;
        selectedProducts.forEach(product => {
            const price = product.price * product.quantity;
            totalPrice += price;
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${product.code}</td>
                <td>${product.name}</td>
                <td><input type="number" value="${product.quantity}" min="1" max="${product.max_quantity}" data-id="${product.id}" class="quantity-input"></td>
                <td>${product.price.toLocaleString()}</td>
                <td>
                    <select class="payment-term" data-id="${product.id}" required>
                        ${product.payment_terms.map(term => `<option value="${term}" ${term === product.payment_term ? 'selected' : ''}>${term}</option>`).join('')}
                    </select>
                </td>
                <td>${price.toLocaleString()}</td>
                <td><button class="remove-item" data-id="${product.id}">حذف</button></td>
            `;
            selectedItemsTable.appendChild(row);
        });
        document.getElementById('totalPrice').textContent = totalPrice.toLocaleString();
    }

    async function populateAutocomplete(query, brand, carGroup) {
        const data = await fetchProducts(query, brand, carGroup);
        const autocompleteItems = document.getElementById('autocomplete-items');
        autocompleteItems.innerHTML = '';
        data.products.forEach(product => {
            if (!selectedProducts.find(p => p.id === product.id)) {
                const item = document.createElement('div');
                item.textContent = `${product.name} (${product.code})`;
                item.addEventListener('click', () => {
                    selectedProducts.push({
                        id: product.id,
                        code: product.code,
                        name: product.name,
                        price: product.price,
                        quantity: 1,
                        max_quantity: product.quantity,
                        payment_term: product.payment_terms[0],
                        payment_terms: product.payment_terms
                    });
                    updateSelectedItems();
                    autocompleteItems.innerHTML = '';
                    document.getElementById('search').value = '';
                });
                autocompleteItems.appendChild(item);
            }
        });
    }

    document.getElementById('search').addEventListener('input', async (e) => {
        const query = e.target.value.toLowerCase();
        const brand = document.getElementById('brandFilter').value;
        const carGroup = document.getElementById('carGroupFilter').value;
        if (query.length >= 2) {
            await populateAutocomplete(query, brand, carGroup);
        } else {
            document.getElementById('autocomplete-items').innerHTML = '';
        }
    });

    document.getElementById('brandFilter').addEventListener('change', async () => {
        const query = document.getElementById('search').value;
        const brand = document.getElementById('brandFilter').value;
        const carGroup = document.getElementById('carGroupFilter').value;
        if (query.length >= 2) {
            await populateAutocomplete(query, brand, carGroup);
        }
    });

    document.getElementById('carGroupFilter').addEventListener('change', async () => {
        const query = document.getElementById('search').value;
        const brand = document.getElementById('brandFilter').value;
        const carGroup = document.getElementById('carGroupFilter').value;
        if (query.length >= 2) {
            await populateAutocomplete(query, brand, carGroup);
        }
    });

    document.getElementById('orderForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const customer = document.getElementById('customer').value;
        if (!customer) {
            document.getElementById('message').innerHTML = '<p class="error">نام مشتری الزامی است.</p>';
            return;
        }
        if (selectedProducts.length === 0) {
            document.getElementById('message').innerHTML = '<p class="error">حداقل یک کالا انتخاب کنید.</p>';
            return;
        }
        const items = selectedProducts.map(product => ({
            product_id: product.id,
            quantity: product.quantity,
            payment_term: product.payment_term
        }));
        try {
            const response = await fetch('/api/orders/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': '{{ csrf_token }}' },
                body: JSON.stringify({ customer, items })
            });
            const result = await response.json();
            document.getElementById('message').innerHTML = `<p class="${response.ok ? 'success' : 'error'}">${result.message}</p>`;
            if (response.ok) {
                selectedProducts = [];
                updateSelectedItems();
                document.getElementById('orderForm').reset();
            }
        } catch (error) {
            document.getElementById('message').innerHTML = '<p class="error">خطا در ارتباط با سرور</p>';
        }
    });

    document.addEventListener('change', (e) => {
        if (e.target.classList.contains('quantity-input')) {
            const id = e.target.dataset.id;
            const product = selectedProducts.find(p => p.id == id);
            product.quantity = parseInt(e.target.value) || 1;
            updateSelectedItems();
        }
        if (e.target.classList.contains('payment-term')) {
            const id = e.target.dataset.id;
            const product = selectedProducts.find(p => p.id == id);
            product.payment_term = e.target.value;
            updateSelectedItems();
        }
    });

    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('remove-item')) {
            const id = e.target.dataset.id;
            selectedProducts = selectedProducts.filter(p => p.id != id);
            updateSelectedItems();
        }
    });
</script>
{% endblock %}
''')

# ذخیره فایل views.py
with open('products/views.py', 'w', encoding='utf-8') as f:
    f.write('''
from django.http import JsonResponse, HttpResponseRedirect, HttpResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
import pandas as pd
import json
from .forms import UploadExcelForm
from .models import Product, Warehouse, Order, OrderItem

def is_manager(user):
    return user.groups.filter(name='مدیر').exists()

@login_required
@user_passes_test(is_manager)
def upload_excel(request):
    if request.method == 'POST':
        form = UploadExcelForm(request.POST, request.FILES)
        if form.is_valid():
            excel_file = request.FILES['excel_file']
            try:
                df = pd.read_excel(excel_file, engine='openpyxl', dtype={'کد کالا': str})
                required_columns = ['کد کالا', 'نام کالا', 'گروه خودرو', 'نام انبار', 'قیمت', 'موجودی', 'برند', 'مدت تسویه']
                if not all(col in df.columns for col in required_columns):
                    missing_cols = [col for col in required_columns if col not in df.columns]
                    messages.error(request, f"ستون‌های زیر در فایل یافت نشدند: {', '.join(missing_cols)}")
                    return render(request, 'products/upload_excel.html', {'form': form})

                Warehouse.objects.get_or_create(name='انبار پخش')
                Warehouse.objects.get_or_create(name='انبار فروشگاه')

                for _, row in df.iterrows():
                    warehouse_name = str(row['نام انبار']).strip()
                    if warehouse_name not in ['انبار پخش', 'انبار فروشگاه']:
                        messages.error(request, f"نام انبار '{warehouse_name}' معتبر نیست. فقط 'انبار پخش' یا 'انبار فروشگاه' مجاز است.")
                        return render(request, 'products/upload_excel.html', {'form': form})

                    warehouse = Warehouse.objects.get(name=warehouse_name)
                    max_payment_term = str(row['مدت تسویه']).strip()
                    if max_payment_term not in ['cash', '1m', '2m', '3m', '4m']:
                        messages.error(request, f"مدت تسویه '{max_payment_term}' معتبر نیست.")
                        return render(request, 'products/upload_excel.html', {'form': form})

                    Product.objects.update_or_create(
                        code=str(row['کد کالا']).strip(),
                        defaults={
                            'name': str(row['نام کالا']).strip(),
                            'car_group': str(row['گروه خودرو']).strip(),
                            'price': float(row['قیمت']),
                            'quantity': int(row['موجودی']),
                            'warehouse': warehouse,
                            'brand': str(row['برند']).strip(),
                            'max_payment_term': max_payment_term,
                        }
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
def create_order(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            customer = data.get('customer')
            items = data.get('items')
            if not customer or not items:
                return JsonResponse({'message': 'نام مشتری، حداقل یک کالا و شرایط تسویه الزامی است.'}, status=400)

            order = Order.objects.create(
                visitor_name=request.user.username,
                customer_name=customer,
                payment_term=items[0]['payment_term'],
                status='در انتظار'
            )
            for item in items:
                product = Product.objects.get(id=item['product_id'])
                if item['quantity'] > product.quantity:
                    return JsonResponse({'message': f"موجودی کافی برای {product.name} نیست."}, status=400)
                if item['payment_term'] not in product.get_available_payment_terms():
                    return JsonResponse({'message': f"شرایط تسویه '{item['payment_term']}' برای {product.name} مجاز نیست."}, status=400)
                OrderItem.objects.create(order=order, product=product, quantity=item['quantity'])

            return JsonResponse({'message': 'سفارش ثبت شد', 'order_id': order.id})
        except Exception as e:
            return JsonResponse({'message': 'خطا در ثبت سفارش', 'error': str(e)}, status=500)
    return JsonResponse({'message': 'درخواست نامعتبر است'}, status=400)

def get_orders(request):
    try:
        orders = Order.objects.all().prefetch_related('items__product')
        orders_data = [
            {
                'id': order.id,
                'visitor_name': order.visitor_name,
                'customer_name': order.customer_name,
                'status': order.status,
                'payment_term': order.payment_term,
                'items': [
                    {'product': item.product.name, 'quantity': item.quantity, 'warehouse': item.product.warehouse.name}
                    for item in order.items.all()
                ]
            }
            for order in orders
        ]
        return JsonResponse({'orders': orders_data})
    except Exception as e:
        return JsonResponse({'message': 'خطا در دریافت سفارش‌ها', 'error': str(e)}, status=500)

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
            'payment_terms': p.get_available_payment_terms()
        } for p in products[:20]
    ]
    return JsonResponse({'products': products_data})

def admin_panel(request):
    return render(request, 'products/manager_dashboard.html')

def product_list(request):
    products = Product.objects.all()
    return render(request, 'products/product_list.html', {'products': products})

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
                return redirect('products:visitor_panel')
            elif user.groups.filter(name='مشتری').exists():
                return redirect('products:customer_panel')
            elif user.groups.filter(name='انباردار').exists():
                return redirect('products:warehouse_panel')
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
    return render(request, 'products/manager_order_list.html')

@login_required
def visitor_panel(request):
    brands = Product.objects.values('brand').distinct()
    car_groups = Product.objects.values('car_group').distinct()
    return render(request, 'products/visitor_panel.html', {'brands': brands, 'car_groups': car_groups})

@login_required
def customer_panel(request):
    return render(request, 'products/customer_panel.html')

@login_required
def warehouse_panel(request):
    return render(request, 'products/warehouse_panel.html')

def redirect_to_login(request):
    return redirect('products:login')
''')

# اطمینان از وجود URL برای get_products
with open('products/urls.py', 'r', encoding='utf-8') as f:
    urls_content = f.read()

if "path('api/products/', views.get_products, name='get_products')" not in urls_content:
    with open('products/urls.py', 'a', encoding='utf-8') as f:
        f.write("\npath('api/products/', views.get_products, name='get_products'),")

# اجرای مایگریشن‌ها
os.system('python manage.py makemigrations')
os.system('python manage.py migrate')

# ری‌استارت سرور
print("لطفاً سرور را با اجرای دستور زیر ری‌استارت کنید:")
print("python manage.py runserver 192.168.1.150:8000")