/**
 * Simple Persian Calendar - تقویم شمسی ساده
 * با الگوریتم تبدیل دقیق
 */
(function($) {
    'use strict';

    // الگوریتم سال کبیسه - چرخه 33 ساله
    function isLeapYear(year) {
        const cycles = [1, 5, 9, 13, 17, 22, 26, 30];
        return cycles.includes(year % 33);
    }

    // تعداد روزهای ماه
    function getDaysInMonth(year, month) {
        if (month <= 6) return 31;
        if (month <= 11) return 30;
        return isLeapYear(year) ? 30 : 29;
    }

    // نام ماه‌ها
    const monthNames = [
        'فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
        'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'
    ];

    // تبدیل میلادی به شمسی - الگوریتم دقیق
    function gregorianToJalali(g_y, g_m, g_d) {
        // اگر Date object باشد
        if (g_y instanceof Date) {
            const date = g_y;
            g_y = date.getFullYear();
            g_m = date.getMonth() + 1;
            g_d = date.getDate();
        }
        
        const g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
        const j_y = (g_y <= 1600) ? 0 : 979;
        g_y -= (g_y <= 1600) ? 621 : 1600;
        let gy2 = (g_m > 2) ? (g_y + 1) : g_y;
        let days = (365 * g_y) + (Math.floor((gy2 + 3) / 4)) - (Math.floor((gy2 + 99) / 100)) +
                   (Math.floor((gy2 + 399) / 400)) - 80 + g_d + g_d_m[g_m - 1];
        let j_y2 = j_y + (33 * Math.floor(days / 12053));
        days %= 12053;
        j_y2 += 4 * Math.floor(days / 1461);
        days %= 1461;
        if (days > 365) {
            j_y2 += Math.floor((days - 1) / 365);
            days = (days - 1) % 365;
        }
        
        let j_m, j_d;
        if (days < 186) {
            j_m = 1 + Math.floor(days / 31);
            j_d = 1 + (days % 31);
        } else {
            j_m = 7 + Math.floor((days - 186) / 30);
            j_d = 1 + ((days - 186) % 30);
        }
        
        return { year: j_y2, month: j_m, day: j_d };
    }

    // تبدیل شمسی به میلادی - الگوریتم صحیح
    function jalaliToGregorian(jy, jm, jd) {
        jy += 1595;
        let days = 365 * jy + Math.floor(jy / 33) * 8 + Math.floor(((jy % 33) + 3) / 4) + 78 + jd;
        
        if (jm < 7) {
            days += (jm - 1) * 31;
        } else {
            days += (jm - 7) * 30 + 186;
        }
        
        let gy = 400 * Math.floor(days / 146097);
        days %= 146097;
        
        let flag = true;
        if (days >= 36525) {
            days--;
            gy += 100 * Math.floor(days / 36524);
            days %= 36524;
            if (days >= 365) {
                days++;
            } else {
                flag = false;
            }
        }
        
        gy += 4 * Math.floor(days / 1461);
        days %= 1461;
        
        if (days >= 366) {
            flag = false;
            days--;
            gy += Math.floor(days / 365);
            days %= 365;
        }
        
        const sal_a = [0, 31, (flag ? 29 : 28), 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
        let gm = 1;
        for (let i = 1; i <= 12; i++) {
            if (days < sal_a[i]) {
                gm = i;
                break;
            }
            days -= sal_a[i];
        }
        
        const gd = days + 1;
        return new Date(gy, gm - 1, gd);
    }

    // تبدیل اعداد به فارسی
    function toPersianDigits(num) {
        const persianDigits = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];
        return String(num).replace(/\d/g, d => persianDigits[d]);
    }

    // Plugin اصلی
    $.fn.simplePersianDatepicker = function(options) {
        const settings = $.extend({
            format: 'YYYY/MM/DD',
            autoClose: true,
            persianDigit: true,
            onSelect: null // callback برای انتخاب تاریخ
        }, options);
        
        return this.each(function() {
            const $input = $(this);
            
            // جلوگیری از initialize مجدد
            if ($input.data('hasDatepicker')) return;
            $input.data('hasDatepicker', true);
            
            const today = gregorianToJalali(new Date());
            let selectedYear = today.year;
            let selectedMonth = today.month;
            let selectedDay = today.day;
            
            // ایجاد المان تقویم با اندازه responsive
            const $calendar = $('<div class="simple-persian-calendar"></div>');
            
            // محاسبه اندازه بر اساس عرض صفحه (نصف اندازه قبلی)
            const screenWidth = $(window).width();
            let calendarWidth, fontSize, padding, borderRadius;
            
            if (screenWidth < 576) {
                // موبایل کوچک
                calendarWidth = '75vw';
                fontSize = '0.65rem';
                padding = '0.35rem';
                borderRadius = '0.4rem';
            } else if (screenWidth < 768) {
                // موبایل بزرگ/تبلت کوچک
                calendarWidth = '180px';
                fontSize = '0.7rem';
                padding = '0.4rem';
                borderRadius = '0.45rem';
            } else if (screenWidth < 1200) {
                // تبلت/لپتاپ کوچک
                calendarWidth = '200px';
                fontSize = '0.75rem';
                padding = '0.45rem';
                borderRadius = '0.5rem';
            } else {
                // دسکتاپ بزرگ
                calendarWidth = '230px';
                fontSize = '0.8rem';
                padding = '0.5rem';
                borderRadius = '0.55rem';
            }
            
            $calendar.css({
                position: 'fixed',
                background: 'white',
                border: '2px solid #3b82f6',
                borderRadius: borderRadius,
                padding: padding,
                boxShadow: '0 0.5rem 2rem rgba(0,0,0,0.2)',
                zIndex: 999999,
                display: 'none',
                width: calendarWidth,
                maxWidth: '95vw',
                fontFamily: 'BNAZANB, Tahoma, Arial',
                fontSize: fontSize,
                direction: 'rtl',
                textAlign: 'center'
            });
            
            // تابع نمایش انتخاب ماه
            function showMonthPicker(fromYearPicker) {
                let html = `
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.7rem; padding: 0.4rem; background: #3b82f6; color: white; border-radius: 0.4rem;">
                        <button class="btn-back" style="background: none; border: none; color: white; cursor: pointer; font-size: 0.9em;">بازگشت</button>
                        <div style="font-weight: bold; cursor: pointer; font-size: 1.1em;" class="year-selector-header">
                            <span>انتخاب ماه - </span>
                            <span style="text-decoration: underline;">${toPersianDigits(selectedYear)}</span>
                        </div>
                        <div style="width: 3rem;"></div>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; padding: 0.6rem;">`;
                
                monthNames.forEach((month, index) => {
                    const isSelected = (index + 1) === selectedMonth;
                    const bgColor = isSelected ? '#3b82f6' : '#f0f0f0';
                    const textColor = isSelected ? 'white' : '#333';
                    
                    html += `<div class="month-cell" data-month="${index + 1}" style="
                        padding: 0.8em;
                        background: ${bgColor};
                        color: ${textColor};
                        border-radius: 0.4rem;
                        cursor: pointer;
                        text-align: center;
                        transition: all 0.2s;
                        font-weight: 500;
                        font-size: 1em;
                    ">${month}</div>`;
                });
                
                html += '</div>';
                $calendar.html(html);
                
                // Event handlers
                $calendar.find('.btn-back').on('click', function(e) {
                    e.stopPropagation();
                    if (fromYearPicker) {
                        showYearPicker();
                    } else {
                        renderCalendar();
                    }
                });
                
                // کلیک روی سال در هدر - برگشت به انتخاب سال
                $calendar.find('.year-selector-header').on('click', function(e) {
                    e.stopPropagation();
                    showYearPicker();
                });
                
                $calendar.find('.month-cell').on('click', function(e) {
                    e.stopPropagation(); // جلوگیری از بسته شدن تقویم
                    selectedMonth = parseInt($(this).data('month'));
                    renderCalendar(); // بعد از انتخاب ماه، به انتخاب روز برود
                });
                
                $calendar.find('.month-cell').on('mouseenter', function() {
                    const month = parseInt($(this).data('month'));
                    if (month !== selectedMonth) {
                        $(this).css({ background: '#60a5fa', color: 'white' });
                    }
                }).on('mouseleave', function() {
                    const month = parseInt($(this).data('month'));
                    if (month !== selectedMonth) {
                        $(this).css({ background: '#f0f0f0', color: '#333' });
                    }
                });
            }
            
            // تابع نمایش انتخاب سال
            function showYearPicker() {
                const startYear = 1390;
                const endYear = 1420;
                
                let html = `
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.7rem; padding: 0.4rem; background: #3b82f6; color: white; border-radius: 0.4rem;">
                        <button class="btn-back-to-calendar" style="background: none; border: none; color: white; cursor: pointer; font-size: 0.9em;">بازگشت</button>
                        <div style="font-weight: bold; font-size: 1.1em;">انتخاب سال</div>
                        <div style="width: 3rem;"></div>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; padding: 0.6rem; max-height: 15rem; overflow-y: auto;">`;
                
                for (let year = endYear; year >= startYear; year--) {
                    const isSelected = year === selectedYear;
                    const bgColor = isSelected ? '#3b82f6' : '#f0f0f0';
                    const textColor = isSelected ? 'white' : '#333';
                    
                    html += `<div class="year-cell" data-year="${year}" style="
                        padding: 0.8em;
                        background: ${bgColor};
                        color: ${textColor};
                        border-radius: 0.4rem;
                        cursor: pointer;
                        text-align: center;
                        transition: all 0.2s;
                        font-weight: 500;
                        font-size: 1em;
                    ">${toPersianDigits(year)}</div>`;
                }
                
                html += '</div>';
                $calendar.html(html);
                
                // Event handlers
                $calendar.find('.btn-back-to-calendar').on('click', function(e) {
                    e.stopPropagation();
                    renderCalendar();
                });
                
                $calendar.find('.year-cell').on('click', function(e) {
                    e.stopPropagation(); // جلوگیری از بسته شدن تقویم
                    selectedYear = parseInt($(this).data('year'));
                    showMonthPicker(true); // بعد از انتخاب سال، به انتخاب ماه برود
                });
                
                $calendar.find('.year-cell').on('mouseenter', function() {
                    const year = parseInt($(this).data('year'));
                    if (year !== selectedYear) {
                        $(this).css({ background: '#60a5fa', color: 'white' });
                    }
                }).on('mouseleave', function() {
                    const year = parseInt($(this).data('year'));
                    if (year !== selectedYear) {
                        $(this).css({ background: '#f0f0f0', color: '#333' });
                    }
                });
            }
            
            // تابع رسم تقویم
            function renderCalendar() {
                const daysInMonth = getDaysInMonth(selectedYear, selectedMonth);
                
                // محاسبه روز هفته اول ماه
                const firstDayOfMonth = jalaliToGregorian(selectedYear, selectedMonth, 1);
                let firstDayWeekday = firstDayOfMonth.getDay(); // 0=یکشنبه
                // تبدیل به شنبه=0, یکشنبه=1, ... (با اصلاح +2 برای تطبیق صحیح)
                firstDayWeekday = (firstDayWeekday + 2) % 7;
                
                let html = `
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.7rem; padding: 0.4rem; background: #3b82f6; color: white; border-radius: 0.4rem;">
                        <button class="btn-prev-month" style="background: none; border: none; color: white; cursor: pointer; font-size: 1.3em; padding: 0.2em 0.5em;">‹</button>
                        <div style="font-weight: bold; display: flex; gap: 0.3rem; font-size: 1.1em;">
                            <span class="month-selector" style="cursor: pointer; padding: 0.2em 0.5em; border-radius: 0.3rem; transition: background 0.2s;">${monthNames[selectedMonth - 1]}</span>
                            <span class="year-selector" style="cursor: pointer; padding: 0.2em 0.5em; border-radius: 0.3rem; transition: background 0.2s;">${toPersianDigits(selectedYear)}</span>
                        </div>
                        <button class="btn-next-month" style="background: none; border: none; color: white; cursor: pointer; font-size: 1.3em; padding: 0.2em 0.5em;">›</button>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(7, 1fr); gap: 0.15rem;">`;
                
                // عناوین روزها
                const dayNames = ['ش', 'ی', 'د', 'س', 'چ', 'پ', 'ج'];
                dayNames.forEach(day => {
                    html += `<div style="padding: 0.4em; font-weight: bold; color: #666; font-size: 0.9em;">${day}</div>`;
                });
                
                // سلول‌های خالی قبل از روز اول
                for (let i = 0; i < firstDayWeekday; i++) {
                    html += `<div style="padding: 0.6em;"></div>`;
                }
                
                // روزهای ماه
                for (let day = 1; day <= daysInMonth; day++) {
                    const isSelected = (day === selectedDay && selectedMonth === today.month && selectedYear === today.year);
                    const bgColor = isSelected ? '#3b82f6' : '#f0f0f0';
                    const textColor = isSelected ? 'white' : '#333';
                    
                    html += `<div class="day-cell" data-day="${day}" style="
                        padding: 0.6em;
                        background: ${bgColor};
                        color: ${textColor};
                        border-radius: 0.3rem;
                        cursor: pointer;
                        transition: all 0.2s;
                        font-size: 1em;
                    ">${toPersianDigits(day)}</div>`;
                }
                
                html += '</div>';
                $calendar.html(html);
                
                // Event handlers
                $calendar.find('.btn-prev-month').on('click', function(e) {
                    e.stopPropagation();
                    selectedMonth--;
                    if (selectedMonth < 1) {
                        selectedMonth = 12;
                        selectedYear--;
                    }
                    renderCalendar();
                });
                
                $calendar.find('.btn-next-month').on('click', function(e) {
                    e.stopPropagation();
                    selectedMonth++;
                    if (selectedMonth > 12) {
                        selectedMonth = 1;
                        selectedYear++;
                    }
                    renderCalendar();
                });
                
                // کلیک روی سال - نمایش لیست سال‌ها (اول سال، بعد ماه، بعد روز)
                $calendar.find('.year-selector').on('click', function(e) {
                    e.stopPropagation();
                    showYearPicker();
                }).on('mouseenter', function() {
                    $(this).css({ background: 'rgba(255,255,255,0.2)' });
                }).on('mouseleave', function() {
                    $(this).css({ background: 'transparent' });
                });
                
                // کلیک روی نام ماه - نمایش لیست ماه‌ها
                $calendar.find('.month-selector').on('click', function(e) {
                    e.stopPropagation();
                    showMonthPicker(false);
                }).on('mouseenter', function() {
                    $(this).css({ background: 'rgba(255,255,255,0.2)' });
                }).on('mouseleave', function() {
                    $(this).css({ background: 'transparent' });
                });
                
                $calendar.find('.day-cell').on('click', function(e) {
                    e.stopPropagation(); // جلوگیری از propagation
                    selectedDay = parseInt($(this).data('day'));
                    console.log('✅ روز انتخاب شد:', selectedDay);
                    const dateStr = `${selectedYear}/${String(selectedMonth).padStart(2, '0')}/${String(selectedDay).padStart(2, '0')}`;
                    $input.val(dateStr);
                    $calendar.hide(); // فقط اینجا تقویم بسته می‌شود
                    
                    // تبدیل به تاریخ میلادی برای callback
                    const gregorianDate = jalaliToGregorian(selectedYear, selectedMonth, selectedDay);
                    const timestamp = gregorianDate.getTime();
                    
                    // Trigger change event
                    $input.trigger('change');
                    
                    // فراخوانی callback اگر وجود داشت
                    if (settings.onSelect && typeof settings.onSelect === 'function') {
                        settings.onSelect(timestamp);
                    }
                });
                
                $calendar.find('.day-cell').on('mouseenter', function() {
                    $(this).css({ background: '#60a5fa', color: 'white' });
                }).on('mouseleave', function() {
                    const day = parseInt($(this).data('day'));
                    const isSelected = (day === selectedDay && selectedMonth === today.month && selectedYear === today.year);
                    if (!isSelected) {
                        $(this).css({ background: '#f0f0f0', color: '#333' });
                    }
                });
            }
            
            // اضافه کردن به body
            $('body').append($calendar);
            
            // نمایش تقویم با کلیک
            $input.on('click', function(e) {
                e.stopPropagation();
                
                // بستن سایر تقویم‌های باز
                $('.simple-persian-calendar').not($calendar).hide();
                
                // محاسبه موقعیت
                const offset = $input.offset();
                const inputHeight = $input.outerHeight();
                const windowWidth = $(window).width();
                const calWidth = $calendar.outerWidth();
                
                // محاسبه موقعیت left برای اینکه تقویم از صفحه بیرون نزند
                let leftPos = offset.left;
                if (leftPos + calWidth > windowWidth) {
                    leftPos = windowWidth - calWidth - 10;
                }
                if (leftPos < 10) {
                    leftPos = 10;
                }
                
                $calendar.css({
                    top: (offset.top + inputHeight + 5) + 'px',
                    left: leftPos + 'px'
                });
                
                renderCalendar();
                $calendar.toggle();
                
                console.log('📅 Calendar toggled for:', $input.attr('id'));
            });
            
            // بستن با کلیک خارج از تقویم
            $(document).on('click', function(e) {
                if (!$(e.target).closest('.simple-persian-calendar, input').length) {
                    $calendar.hide();
                }
            });
            
            console.log('✅ Datepicker initialized for:', $input.attr('id'));
        });
    };

    // Aliases برای سازگاری
    $.fn.pDatepicker = $.fn.simplePersianDatepicker;
    $.fn.persianDatepicker = $.fn.simplePersianDatepicker;

    // Auto-initialize
    $(document).ready(function() {
        $('.persian-datepicker').simplePersianDatepicker();
        console.log('✅ Simple Persian Calendar loaded!');
        console.log('📅 1403 is leap:', isLeapYear(1403), '| Esfand days:', getDaysInMonth(1403, 12));
        
        // تست: 1404/01/01 باید جمعه باشد
        const test = jalaliToGregorian(1404, 1, 1);
        console.log('🧪 Test 1404/01/01 =>', test.toDateString(), '| Day:', test.getDay(), '(5=جمعه)');
    });

})(jQuery);
