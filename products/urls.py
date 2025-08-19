from django.urls import path
from django.shortcuts import redirect
from . import views
from .views import dashboard_view

app_name = 'products'

urlpatterns = [
    path('', views.redirect_to_login, name='redirect_to_login'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),

    # محصولات و سفارشات
    path('order/', views.order_list_view, name='order'),  # صفحه لیست سفارش‌ها
    path('products/', views.product_list, name='product_list'),
    path('upload/', views.upload_excel, name='upload_excel'),
    path('api/upload-products/', views.upload_excel, name='upload_excel_api'),
    path('api/products/', views.get_products, name='get_products'),
    path('api/get-product/', views.get_product, name='get_product'),
    path('api/orders/', views.create_order, name='create_order'),
    path('api/orders/list/', views.get_orders, name='get_orders'),
    path('api/user_orders/', views.get_user_orders, name='get_user_orders'),

    # مشتریان
    path('create-customer/', views.create_customer, name='create_customer'),
    path('search-customers/', views.search_customers, name='search_customers'),

    # سبد خرید و تخصیص
    path('api/cart/', views.get_cart, name='get_cart'),  # باید view مربوطه را بسازی
    path('api/submit-allocation/', views.submit_allocation, name='submit_allocation'),
    path('products/api/allocate-items/', views.allocate_items, name='allocate_items'),
    path('api/cart/change_qty/', views.change_cart_qty, name='api_cart_change_qty'),
    path('api/cart/remove_item/', views.remove_cart_item, name='api_cart_remove_item'),
    path('api/cart/update_quantities/', views.update_cart_quantities, name='api_cart_update_quantities'),
    path('order/confirmation/', views.order_confirmation, name='order_confirmation'),  # صفحه تایید سفارش
    path('order/confirm/', views.confirm_order, name='confirm_order'),  # تایید نهایی سفارش
    path('read_notification/<int:notification_id>/', views.read_notification, name='read_notification'),
    

    # گزارش‌ها و PDF
    path('api/order_pdf/<int:order_id>/', views.order_pdf, name='order_pdf'),

    # مدیریت و پنل‌ها
    path('manager/', views.manager_dashboard, name='manager_dashboard'),
    path('manager/orders/', views.manager_order_list, name='manager_order_list'),
    path('visitor/', views.visitor_panel, name='visitor_panel'),
    path('customer/', lambda request: redirect('products:visitor_panel'), name='customer_panel'),
    path('warehouse/', views.warehouse_panel, name='warehouse_panel'),
    path('accounting/', views.accounting_panel, name='accounting_panel'),
    path('invoice-registration/', views.invoice_registration_view, name='invoice_registration'),
    path('purchase-invoice/', views.purchase_invoice_view, name='purchase_invoice'),
    # Add purchase invoice list and detail URLs
    path('purchase-invoice/list/', views.purchase_invoice_list_view, name='purchase_invoice_list'),
    path('purchase-invoice/<int:invoice_id>/detail/', views.purchase_invoice_detail_view, name='purchase_invoice_detail'),
    path('purchase-invoice/ajax-register/', views.ajax_purchase_invoice_register, name='ajax_purchase_invoice_register'),

    # Sales Invoice
    path('sales-invoice/', views.sales_invoice_view, name='sales_invoice_view'),
    path('sales-invoice/list/', views.sales_invoice_list_view, name='sales_invoice_list'),
    path('sales-invoice/<int:invoice_id>/detail/', views.sales_invoice_detail_view, name='sales_invoice_detail'),
    path('accounting/reports-menu/', views.accounting_reports_menu, name='accounting_reports_menu'),

    # سفارشات و ارسال‌ها
    path('edit-order/<int:order_id>/', views.edit_order, name='edit_order'),
    path('send_order_to_warehouse/', views.send_order_to_warehouse, name='send_order_to_warehouse'),
    path('api/update-order-status/', views.update_order_status, name='update_order_status'),
    path('api/update-warehouse-items/', views.update_warehouse_items, name='update_warehouse_items'),
    path('api/send-item-to-warehouse/', views.resend_backorder_item_to_warehouse, name='send_item_to_warehouse'),
    path('order/<int:order_id>/detail/', views.order_detail_view, name='order_detail_view'),
    path('allocate/<int:order_id>/', views.allocate_to_warehouse, name='allocate_to_warehouse'),
    path('add_to_cart/', views.add_to_cart, name='add_to_cart'),
    path('api/cart/', views.get_cart, name='api_cart'),


    # ارسال استانداردسازی شده
    path('order/<int:order_id>/shipment/create/', views.create_shipment_for_order, name='create_shipment'),
    path('shipment/<int:shipment_id>/status/', views.update_shipment_status, name='update_shipment_status'),

    # ابزارهای تست و دیباگ
    path('api/debug/', views.debug_view, name='debug_view'),
    path('api/create-test-users/', views.create_test_users, name='create_test_users'),
    path('api/parse-invoice-excel/', views.parse_invoice_excel, name='parse_invoice_excel'),
    path('accounting/reports/', views.accounting_reports, name='accounting_reports'),

    # این URL ها رو به انتهای urlpatterns در فایل urls.py اضافه کنید:

    # گزارشات مالی
    path('financial-report/<str:report_type>/', views.financial_report_view, name='financial_report'),
    
    # گزارشات انبار و موجودی
    path('inventory-report/<str:report_type>/', views.inventory_report_view, name='inventory_report'),
    
    # گزارشات عملیاتی و سفارشات
    path('operational-report/<str:report_type>/', views.operational_report_view, name='operational_report'),
    
    # گزارشات مشتریان
    path('customer-report/<str:report_type>/', views.customer_report_view, name='customer_report'),
    

    path('accounting/financial-operations-menu/', views.financial_operations_menu, name='financial_operations_menu'),
    path('accounting/reports-menu/', views.accounting_reports_menu, name='accounting_reports_menu'),

    # URL های مربوط به هر عملیات مالی:
    path('accounting/receive-from-customer/', views.receive_from_customer_view, name='receive_from_customer'),
    path('accounting/pay-to-customer/', views.pay_to_customer_view, name='pay_to_customer'),
    path('accounting/capital-investment/', views.capital_investment_view, name='capital_investment'),
    path('accounting/receive-from-bank/', views.receive_from_bank_view, name='receive_from_bank'),
    path('accounting/pay-to-bank/', views.pay_to_bank_view, name='pay_to_bank'),
    path('accounting/bank-transfer/', views.bank_transfer_view, name='bank_transfer'),
    path('accounting/cash-withdrawal/', views.cash_withdrawal_view, name='cash_withdrawal'),
    path('accounting/payment-from-cash/', views.payment_from_cash_view, name='payment_from_cash'),
    path('accounting/payment-to-cash/', views.payment_to_cash_view, name='payment_to_cash'),
    # در قسمت URL های مربوط به عملیات مالی (حدود خط 91)، بعد از سایر URL ها:
    path('accounting/petty-cash/', views.petty_cash_view, name='petty_cash'),

     # Financial Year URLs
    path('accounting/financial-years/', views.financial_year_list, name='financial_year_list'),
    path('accounting/financial-years/create/', views.financial_year_create, name='financial_year_create'),
    path('accounting/financial-years/<int:pk>/edit/', views.financial_year_edit, name='financial_year_edit'),
    
    # Currency URLs
    path('accounting/currencies/', views.currency_list, name='currency_list'),
    path('accounting/currencies/create/', views.currency_create, name='currency_create'),
    path('accounting/currencies/<int:pk>/edit/', views.currency_edit, name='currency_edit'),
    
    # Comprehensive Financial Operations URLs
    path('accounting/funds/', views.fund_list_view, name='fund_list'),
    path('accounting/funds/create/', views.fund_create_view, name='fund_create'),
    path('accounting/funds/<int:fund_id>/edit/', views.fund_edit_view, name='fund_edit'),
    path('accounting/funds/<int:fund_id>/detail/', views.fund_detail_view, name='fund_detail'),
    path('accounting/funds/<int:fund_id>/transactions/', views.fund_transactions_view, name='fund_transactions'),
    path('accounting/bank-accounts/create/', views.bank_account_create_view, name='bank_account_create'),
    path('accounting/bank-accounts/', views.bank_account_list_view, name='bank_account_list'),
    path('accounting/bank-accounts/<int:bank_account_id>/detail/', views.bank_account_detail_view, name='bank_account_detail'),
    path('accounting/bank-accounts/<int:bank_account_id>/edit/', views.bank_account_edit_view, name='bank_account_edit'),
    path('accounting/bank-accounts/<int:bank_account_id>/statement/', views.bank_statement_view, name='bank_statement'),
    path('accounting/bank-accounts/<int:bank_account_id>/available-checks/', views.available_checks_for_deposit_view, name='available_checks_for_deposit'),
    path('accounting/bank-accounts/<int:bank_account_id>/deposit-confirmation/<str:check_ids>/', views.deposit_confirmation_view, name='deposit_confirmation'),
    
    # دسته چک‌ها
    path('accounting/checkbooks/<int:checkbook_id>/detail/', views.checkbook_detail_view, name='checkbook_detail'),
    path('accounting/checkbooks/<int:checkbook_id>/edit/', views.checkbook_edit_view, name='checkbook_edit'),
    path('accounting/checkbooks/<int:checkbook_id>/issued-checks-report/', views.issued_checks_report_view, name='issued_checks_report'),
    path('accounting/issued-checks/', views.all_issued_checks_view, name='all_issued_checks'),
    path('accounting/vouchers/', views.voucher_list_view, name='voucher_list'),
    path('accounting/vouchers/<int:voucher_id>/', views.voucher_detail_view, name='voucher_detail'),
    
    path('accounting/operations/', views.financial_operation_list_view, name='financial_operation_list'),
    path('accounting/operations/<int:operation_id>/detail/', views.financial_operation_detail_view, name='financial_operation_detail'),
    path('accounting/operations/<int:operation_id>/edit/', views.financial_operation_edit_view, name='financial_operation_edit'),
    path('accounting/operations/<int:operation_id>/delete/', views.financial_operation_delete_view, name='financial_operation_delete'),
    
    path('accounting/customer-balances/', views.customer_balance_list_view, name='customer_balance_list'),
    path('accounting/customer-balances/<int:customer_id>/detail/', views.customer_balance_detail_view, name='customer_balance_detail'),
    
    path('accounting/dashboard/', views.financial_dashboard_view, name='financial_dashboard'),
    path('accounting/operation-confirmation/', views.operation_confirmation_view, name='operation_confirmation'),
    
    # Enhanced Financial Operation URLs with proper routing
    path('accounting/bank-operation/<str:operation_type>/', views.bank_operation_view, name='bank_operation'),
    path('accounting/cash-operation/<str:operation_type>/', views.cash_operation_view, name='cash_operation'),
    
    # Received Cheques
    path('accounting/received-cheques/', views.received_cheque_list_view, name='received_cheque_list'),
    path('accounting/received-cheques/<int:cheque_id>/change-status/', views.change_received_cheque_status, name='change_received_cheque_status'),
    path('accounting/received-cheques/<int:cheque_id>/detail/', views.received_cheque_detail_view, name='received_cheque_detail'),
    path('accounting/received-cheques/<int:cheque_id>/edit/', views.received_cheque_edit_view, name='received_cheque_edit'),
    path('accounting/received-checks/<int:check_id>/clear/', views.clear_received_check, name='clear_received_check'),
    path('accounting/received-checks/<int:check_id>/bounce/', views.bounce_received_check, name='bounce_received_check'),
    
    # URLs for check issuance
    path('accounting/combined-check-operation/', views.combined_check_operation_view, name='combined_check_operation'),
    path('accounting/issue-check/', views.issue_check_view, name='issue_check'),
    path('api/get-checkbooks/', views.get_checkbooks_for_bank_account, name='get_checkbooks_for_bank_account'),
    path('api/get-unused-checks/', views.get_unused_checks_for_checkbook, name='get_unused_checks_for_checkbook'),
    path('accounting/issued-checks/<int:check_id>/edit/', views.issued_check_edit_view, name='issued_check_edit'),
    path('accounting/issued-checks/<int:check_id>/delete/', views.issued_check_delete_view, name='issued_check_delete'),
    path('accounting/issued-checks/<int:check_id>/clear/', views.clear_issued_check, name='clear_issued_check'),
    path('accounting/issued-checks/<int:check_id>/bounce/', views.bounce_issued_check, name='bounce_issued_check'),
    path('accounting/issued-checks/<int:check_id>/reset/', views.reset_issued_check, name='reset_issued_check'),
    
    # URLs for spending received checks
    path('api/get-received-checks/', views.get_received_checks, name='get_received_checks'),
    path('accounting/spend-received-check/', views.spend_received_check_view, name='spend_received_check'),
    
]