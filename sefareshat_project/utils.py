import re

def normalize_text(text):
    """
    نرمال‌ساز حرفه‌ای متون فارسی برای جستجو و ذخیره‌سازی.
    تبدیل ي/ی و ك/ک، حذف اعراب و نیم‌فاصله و فاصله‌های اضافه و کوچک‌سازی
    """
    if not text:
        return text
    text = str(text)
    # تبدیل ي عربی (U+064A) به ی فارسی (U+06CC)
    text = text.replace('ي', 'ی')
    # تبدیل ك عربی (U+0643) به ک فارسی (U+06A9)
    text = text.replace('ك', 'ک')
    # حذف اعراب عربی (فتحه، کسره، ضمه و ...)
    text = re.sub(r'[\u064B-\u0652]', '', text)
    # حذف نیم‌فاصله
    text = text.replace('\u200c', '')
    # حذف فاصله‌های اضافه
    text = re.sub(r'\s+', ' ', text)
    # کوچک‌سازی (در صورت وجود متن انگلیسی)
    text = text.lower()
    # حذف فاصله ابتدا و انتها
    return text.strip()