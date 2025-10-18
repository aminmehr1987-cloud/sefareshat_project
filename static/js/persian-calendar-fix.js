/**
 * Persian Calendar Fix - تصحیح تقویم شمسی
 * 
 * این فایل مشکل محاسبه سال کبیسه در کتابخانه persian-datepicker را برطرف می‌کند
 * 
 * مشکل: سال 1403 یک سال کبیسه است (اسفند 30 روزه)
 * اما persian-datepicker آن را 29 روزه در نظر می‌گیرد
 * 
 * راه‌حل: محاسبه صحیح سال کبیسه بر اساس چرخه 33 ساله
 */

(function(window) {
    'use strict';

    /**
     * محاسبه صحیح سال کبیسه شمسی
     * 
     * قانون: در هر 33 سال، 8 سال کبیسه وجود دارد
     * سال‌های کبیسه در چرخه 33 ساله: 1، 5، 9، 13، 17، 22، 26، 30
     * 
     * @param {number} year - سال شمسی (مثل 1403)
     * @returns {boolean} - آیا سال کبیسه است؟
     */
    function isPersianLeapYear(year) {
        // چرخه 33 ساله تقویم شمسی
        const LEAP_YEARS_IN_CYCLE = [1, 5, 9, 13, 17, 22, 26, 30];
        
        // موقعیت سال در چرخه 33 ساله
        const cyclePosition = year % 33;
        
        // بررسی اینکه آیا در لیست سال‌های کبیسه است
        const isLeap = LEAP_YEARS_IN_CYCLE.includes(cyclePosition);
        
        return isLeap;
    }

    /**
     * تعداد روزهای هر ماه شمسی
     * 
     * @param {number} year - سال شمسی
     * @param {number} month - ماه شمسی (1-12)
     * @returns {number} - تعداد روزهای ماه
     */
    function getPersianMonthDays(year, month) {
        // ماه‌های 1 تا 6: 31 روز
        if (month >= 1 && month <= 6) {
            return 31;
        }
        // ماه‌های 7 تا 11: 30 روز
        else if (month >= 7 && month <= 11) {
            return 30;
        }
        // ماه 12 (اسفند): 29 یا 30 روز (بسته به کبیسه بودن)
        else if (month === 12) {
            return isPersianLeapYear(year) ? 30 : 29;
        }
        
        return 30; // پیش‌فرض
    }

    /**
     * اعتبارسنجی تاریخ شمسی
     * 
     * @param {number} year - سال
     * @param {number} month - ماه (1-12)
     * @param {number} day - روز
     * @returns {boolean} - آیا تاریخ معتبر است؟
     */
    function isValidPersianDate(year, month, day) {
        if (month < 1 || month > 12) return false;
        if (day < 1) return false;
        
        const maxDay = getPersianMonthDays(year, month);
        return day <= maxDay;
    }

    /**
     * تبدیل تاریخ شمسی به میلادی (الگوریتم ساده‌شده)
     * 
     * @param {number} jy - سال شمسی
     * @param {number} jm - ماه شمسی
     * @param {number} jd - روز شمسی
     * @returns {Date} - تاریخ میلادی
     */
    function jalaliToGregorian(jy, jm, jd) {
        // استفاده از کتابخانه moment-jalaali اگر موجود باشد
        if (typeof moment !== 'undefined' && moment.fn && moment.fn.jYear) {
            const m = moment(`${jy}/${jm}/${jd}`, 'jYYYY/jM/jD');
            return m.toDate();
        }
        
        // الگوریتم تبدیل (نسخه ساده)
        const gy = jy + 621;
        const totalDays = jd + 
                         (jm <= 6 ? (jm - 1) * 31 : (jm - 1) * 30 + 6) + 
                         Math.floor((jy - 1) / 33) * 8 + 
                         Math.floor(((jy - 1) % 33 + 3) / 4);
        
        const gd = new Date(gy, 2, 20); // 20 مارس = 1 فروردین (تقریبی)
        gd.setDate(gd.getDate() + totalDays - 1);
        
        return gd;
    }

    /**
     * تبدیل تاریخ میلادی به شمسی
     * 
     * @param {Date} gregorianDate - تاریخ میلادی
     * @returns {object} - {year, month, day}
     */
    function gregorianToJalali(gregorianDate) {
        // استفاده از moment-jalaali اگر موجود باشد
        if (typeof moment !== 'undefined' && moment.fn && moment.fn.jYear) {
            const m = moment(gregorianDate);
            return {
                year: m.jYear(),
                month: m.jMonth() + 1,
                day: m.jDate()
            };
        }
        
        // الگوریتم تبدیل (نسخه ساده)
        const gy = gregorianDate.getFullYear();
        const gm = gregorianDate.getMonth();
        const gd = gregorianDate.getDate();
        
        let jy = gy - 621;
        let jm = gm > 2 ? gm - 2 : gm + 10;
        let jd = gd;
        
        if (gm < 3 || (gm === 3 && gd < 21)) {
            jy--;
        }
        
        return { year: jy, month: jm, day: jd };
    }

    /**
     * محاسبه روز هفته برای تاریخ شمسی
     * 
     * @param {number} year - سال شمسی
     * @param {number} month - ماه شمسی
     * @param {number} day - روز شمسی
     * @returns {number} - روز هفته (0=شنبه، 1=یک‌شنبه، ..., 6=جمعه)
     */
    function getPersianDayOfWeek(year, month, day) {
        const gDate = jalaliToGregorian(year, month, day);
        const gDayOfWeek = gDate.getDay(); // 0=Sunday, 1=Monday, ...
        
        // تبدیل به فرمت شمسی: 0=شنبه، 1=یک‌شنبه، ..., 6=جمعه
        const pDayOfWeek = (gDayOfWeek + 1) % 7;
        
        return pDayOfWeek;
    }

    /**
     * نام روزهای هفته به فارسی
     */
    const PERSIAN_WEEKDAYS = [
        'شنبه',      // 0
        'یک‌شنبه',   // 1
        'دوشنبه',    // 2
        'سه‌شنبه',   // 3
        'چهارشنبه',  // 4
        'پنج‌شنبه',  // 5
        'جمعه'       // 6
    ];

    /**
     * نام ماه‌های شمسی
     */
    const PERSIAN_MONTHS = [
        '',          // 0 (استفاده نمی‌شود)
        'فروردین',  // 1
        'اردیبهشت', // 2
        'خرداد',     // 3
        'تیر',       // 4
        'مرداد',     // 5
        'شهریور',    // 6
        'مهر',       // 7
        'آبان',      // 8
        'آذر',       // 9
        'دی',        // 10
        'بهمن',      // 11
        'اسفند'      // 12
    ];

    /**
     * دریافت نام روز هفته
     */
    function getPersianWeekdayName(year, month, day) {
        const dayOfWeek = getPersianDayOfWeek(year, month, day);
        return PERSIAN_WEEKDAYS[dayOfWeek];
    }

    /**
     * دریافت نام ماه
     */
    function getPersianMonthName(month) {
        return PERSIAN_MONTHS[month] || '';
    }

    /**
     * تصحیح کتابخانه persian-datepicker
     * این تابع باید بعد از لود شدن persian-datepicker صدا زده شود
     */
    function fixPersianDatepicker() {
        console.log('🔧 در حال تصحیح persian-datepicker...');

        // تصحیح کتابخانه persian-date اگر موجود باشد
        if (typeof persianDate !== 'undefined') {
            try {
                const originalIsLeapYear = persianDate.prototype.isLeapYear;
                persianDate.prototype.isLeapYear = function() {
                    return isPersianLeapYear(this.year());
                };
                console.log('✅ persian-date.isLeapYear تصحیح شد');
            } catch (e) {
                console.warn('⚠️ خطا در تصحیح persian-date:', e.message);
            }
        }

        // تصحیح PersianDate اگر موجود باشد
        if (typeof PersianDate !== 'undefined') {
            try {
                const originalIsLeapYear = PersianDate.prototype.isLeapYear;
                PersianDate.prototype.isLeapYear = function() {
                    return isPersianLeapYear(this.year());
                };
                console.log('✅ PersianDate.isLeapYear تصحیح شد');
            } catch (e) {
                console.warn('⚠️ خطا در تصحیح PersianDate:', e.message);
            }
        }

        // تصحیح $.fn.pDatepicker اگر موجود باشد
        if (typeof $ !== 'undefined' && $.fn && $.fn.pDatepicker) {
            try {
                // ذخیره تنظیمات پیش‌فرض
                const originalDefaults = $.fn.pDatepicker.defaults;
                
                // اگر API برای تغییر تابع isLeapYear وجود دارد
                if (originalDefaults && originalDefaults.calendar && originalDefaults.calendar.persian) {
                    // تصحیح تابع محاسبه سال کبیسه
                    if (originalDefaults.calendar.persian.isLeapYear) {
                        originalDefaults.calendar.persian.isLeapYear = isPersianLeapYear;
                        console.log('✅ $.fn.pDatepicker.defaults.calendar.persian.isLeapYear تصحیح شد');
                    }
                }
            } catch (e) {
                console.warn('⚠️ خطا در تصحیح $.fn.pDatepicker:', e.message);
            }
        }

        // تصحیح moment-jalaali اگر موجود باشد
        if (typeof moment !== 'undefined' && moment.fn && moment.fn.jYear) {
            try {
                const originalIsLeapYear = moment.fn.isLeapJYear;
                if (originalIsLeapYear) {
                    moment.fn.isLeapJYear = function() {
                        return isPersianLeapYear(this.jYear());
                    };
                    console.log('✅ moment.isLeapJYear تصحیح شد');
                }
            } catch (e) {
                console.warn('⚠️ خطا در تصحیح moment-jalaali:', e.message);
            }
        }

        console.log('✅ تصحیح persian-datepicker کامل شد');
        return true;
    }

    /**
     * لاگ اطلاعات برای دیباگ
     */
    function debugPersianCalendar() {
        console.log('📅 Persian Calendar Debug Info:');
        console.log('-----------------------------------');
        
        // تست سال 1403
        const year = 1403;
        console.log(`سال ${year}:`);
        console.log(`  آیا کبیسه است؟ ${isPersianLeapYear(year) ? 'بله ✅' : 'خیر ❌'}`);
        console.log(`  اسفند ${year}: ${getPersianMonthDays(year, 12)} روز`);
        
        // تست 26 مهر 1404
        const testDate = { year: 1404, month: 7, day: 26 };
        console.log(`\n${testDate.day} ${getPersianMonthName(testDate.month)} ${testDate.year}:`);
        console.log(`  روز هفته: ${getPersianWeekdayName(testDate.year, testDate.month, testDate.day)}`);
        
        // تبدیل به میلادی
        const gDate = jalaliToGregorian(testDate.year, testDate.month, testDate.day);
        console.log(`  معادل میلادی: ${gDate.toLocaleDateString('en-US')}`);
        console.log(`  روز هفته میلادی: ${gDate.toLocaleDateString('fa-IR', {weekday: 'long'})}`);
        
        console.log('-----------------------------------');
    }

    // اضافه کردن توابع به window برای دسترسی عمومی
    window.PersianCalendarFix = {
        isPersianLeapYear: isPersianLeapYear,
        getPersianMonthDays: getPersianMonthDays,
        isValidPersianDate: isValidPersianDate,
        jalaliToGregorian: jalaliToGregorian,
        gregorianToJalali: gregorianToJalali,
        getPersianDayOfWeek: getPersianDayOfWeek,
        getPersianWeekdayName: getPersianWeekdayName,
        getPersianMonthName: getPersianMonthName,
        fixPersianDatepicker: fixPersianDatepicker,
        debug: debugPersianCalendar,
        PERSIAN_WEEKDAYS: PERSIAN_WEEKDAYS,
        PERSIAN_MONTHS: PERSIAN_MONTHS
    };

    // اجرای خودکار تصحیح زمانی که DOM آماده شد
    function attemptFix() {
        let attempts = 0;
        const maxAttempts = 10;
        
        const tryFix = function() {
            attempts++;
            console.log(`🔄 تلاش ${attempts} برای تصحیح تقویم...`);
            
            // اگر jQuery یا persian-datepicker موجود نیست، دوباره تلاش کن
            if (typeof $ === 'undefined' || typeof $.fn === 'undefined') {
                if (attempts < maxAttempts) {
                    setTimeout(tryFix, 200);
                }
                return;
            }
            
            fixPersianDatepicker();
            console.log('✅ تصحیح تقویم شمسی فعال شد');
            
            // نمایش اطلاعات دیباگ (فقط در حالت توسعه)
            if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || window.location.hostname.includes('192.168')) {
                debugPersianCalendar();
            }
        };
        
        tryFix();
    }

    // اجرا در زمان لود صفحه
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', attemptFix);
    } else {
        // DOM از قبل آماده است
        attemptFix();
    }

    console.log('✅ Persian Calendar Fix بارگذاری شد');

})(window);
