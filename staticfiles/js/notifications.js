// سیستم نوتیفیکیشن مشترک برای تمام صفحات
(function() {
    'use strict';

    // بررسی اینکه آیا سیستم نوتیفیکیشن موجود است
    if (typeof showNotification === 'function') {
        // سیستم نوتیفیکیشن موجود است، از آن استفاده کن
        window.showMessage = function(message, type = 'info') {
            showNotification(message, type, 5000);
        };
    } else {
        // سیستم نوتیفیکیشن موجود نیست، یک سیستم ساده بساز
        window.showMessage = function(message, type = 'info') {
            const messageDiv = document.createElement('div');
            messageDiv.className = `alert alert-${type === 'success' ? 'success' : type === 'error' ? 'danger' : type === 'warning' ? 'warning' : 'info'}`;
            
            // استایل نوتیفیکیشن در گوشه راست پایین
            messageDiv.style.cssText = `
                position: fixed;
                bottom: 25px;
                right: 25px;
                z-index: 10000;
                padding: 18px 20px;
                border-radius: 12px;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12), 0 2px 16px rgba(0, 0, 0, 0.08);
                font-family: 'Vazirmatn', 'Tahoma', 'IRANSans', Arial, sans-serif;
                direction: rtl;
                text-align: right;
                max-width: 380px;
                word-wrap: break-word;
                font-size: 15px;
                line-height: 1.5;
                font-weight: 500;
                border-right: 5px solid;
                opacity: 0;
                transform: translateX(120%);
                transition: all 0.4s cubic-bezier(0.68, -0.55, 0.265, 1.55);
            `;

            // رنگ‌ها بر اساس نوع پیام
            const colors = {
                success: {
                    background: 'linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)',
                    borderColor: '#10b981',
                    color: '#065f46'
                },
                error: {
                    background: 'linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%)',
                    borderColor: '#ef4444',
                    color: '#991b1b'
                },
                warning: {
                    background: 'linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%)',
                    borderColor: '#f59e0b',
                    color: '#92400e'
                },
                info: {
                    background: 'linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%)',
                    borderColor: '#3b82f6',
                    color: '#1e40af'
                }
            };

            const colorScheme = colors[type] || colors.info;
            messageDiv.style.background = colorScheme.background;
            messageDiv.style.borderRightColor = colorScheme.borderColor;
            messageDiv.style.color = colorScheme.color;

            // آیکون بر اساس نوع پیام
            const icons = {
                success: '<i class="bi bi-check-circle-fill" style="margin-left: 10px; font-size: 18px; color: #10b981;"></i>',
                error: '<i class="bi bi-x-circle-fill" style="margin-left: 10px; font-size: 18px; color: #ef4444;"></i>',
                warning: '<i class="bi bi-exclamation-triangle-fill" style="margin-left: 10px; font-size: 18px; color: #f59e0b;"></i>',
                info: '<i class="bi bi-info-circle-fill" style="margin-left: 10px; font-size: 18px; color: #3b82f6;"></i>'
            };

            messageDiv.innerHTML = `${icons[type] || icons.info}${message}`;

            // اضافه کردن به صفحه
            document.body.appendChild(messageDiv);

            // انیمیشن ورود
            requestAnimationFrame(() => {
                messageDiv.style.opacity = '1';
                messageDiv.style.transform = 'translateX(0)';
            });

            // حذف خودکار بعد از 5 ثانیه
            setTimeout(() => {
                messageDiv.style.opacity = '0';
                messageDiv.style.transform = 'translateX(120%)';
                
                setTimeout(() => {
                    if (messageDiv.parentNode) {
                        messageDiv.parentNode.removeChild(messageDiv);
                    }
                }, 400);
            }, 5000);
        };
    }

    // تابع تست نوتیفیکیشن‌ها
    window.testNotifications = function() {
        showMessage('عملیات با موفقیت انجام شد! 🎉', 'success');
        setTimeout(() => showMessage('خطا در انجام عملیات! ❌', 'error'), 1000);
        setTimeout(() => showMessage('توجه: این یک هشدار است! ⚠️', 'warning'), 2000);
        setTimeout(() => showMessage('اطلاعات: عملیات در حال انجام... ℹ️', 'info'), 3000);
    };

    // کلیدهای میانبر برای تست (Ctrl+Shift+N)
    document.addEventListener('keydown', function(e) {
        if (e.ctrlKey && e.shiftKey && e.key === 'N') {
            testNotifications();
        }
    });

    console.log('✅ سیستم نوتیفیکیشن مشترک بارگیری شد');
})(); 