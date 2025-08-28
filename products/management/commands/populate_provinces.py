from django.core.management.base import BaseCommand
from products.models import Province, County


class Command(BaseCommand):
    help = 'Populate database with sample provinces and counties'

    def handle(self, *args, **options):
        # Create provinces
        provinces_data = [
            'تهران',
            'اصفهان',
            'خراسان رضوی',
            'فارس',
            'آذربایجان شرقی',
            'آذربایجان غربی',
            'خوزستان',
            'گیلان',
            'مازندران',
            'یزد',
            'کرمان',
            'همدان',
            'قم',
            'البرز',
            'زنجان',
            'سمنان',
            'قزوین',
            'لرستان',
            'کردستان',
            'ایلام',
            'بوشهر',
            'هرمزگان',
            'سیستان و بلوچستان',
            'چهارمحال و بختیاری',
            'کهگیلویه و بویراحمد',
            'گلستان',
            'اردبیل',
            'مرکزی',
            'کرمانشاه',
            'خراسان شمالی',
            'خراسان جنوبی',
            'جنوب کرمان'
        ]

        # Create counties data (province_name: [county_names])
        counties_data = {
            'تهران': ['تهران', 'شهریار', 'ورامین', 'فیروزکوه', 'دماوند', 'پردیس', 'پیشوا', 'رباط کریم', 'فشم', 'ری', 'پردیس'],
            'اصفهان': ['اصفهان', 'کاشان', 'نجف‌آباد', 'خمینی‌شهر', 'شاهین‌شهر', 'مبارکه', 'گلپایگان', 'نطنز', 'نایین', 'خوانسار', 'فریدن'],
            'خراسان رضوی': ['مشهد', 'نیشابور', 'سبزوار', 'تربت حیدریه', 'کاشمر', 'قوچان', 'گناباد', 'تربت جام', 'چناران', 'سرخس', 'گناباد'],
            'فارس': ['شیراز', 'مرودشت', 'جهرم', 'فسا', 'کازرون', 'لار', 'داراب', 'نی‌ریز', 'آباده', 'اقلید', 'کوار'],
            'آذربایجان شرقی': ['تبریز', 'مراغه', 'میانه', 'اهر', 'بناب', 'سراب', 'شبستر', 'هشترود', 'جلفا', 'کلیبر', 'ملکان'],
            'آذربایجان غربی': ['ارومیه', 'خوی', 'میاندوآب', 'بوکان', 'مهاباد', 'سلماس', 'نقده', 'پیرانشهر', 'سردشت', 'اشنویه', 'بوکان'],
            'خوزستان': ['اهواز', 'دزفول', 'ماهشهر', 'آبادان', 'خرمشهر', 'ایذه', 'شوشتر', 'شوش', 'اندیمشک', 'بهبهان', 'دزفول'],
            'گیلان': ['رشت', 'انزلی', 'لاهیجان', 'آستارا', 'تالش', 'فومن', 'صومعه‌سرا', 'رودبار', 'املش', 'لنگرود', 'آستانه اشرفیه'],
            'مازندران': ['ساری', 'بابل', 'آمل', 'قائم‌شهر', 'بهشهر', 'نکا', 'نوشهر', 'تنکابن', 'چالوس', 'رامسر', 'جویبار'],
            'یزد': ['یزد', 'میبد', 'اردکان', 'بافق', 'مهریز', 'ابرکوه', 'تفت', 'اشکذر', 'خاتم', 'بهاباد', 'تفت']
        }

        self.stdout.write('Creating provinces and counties...')

        # Create provinces
        created_provinces = {}
        for province_name in provinces_data:
            province, created = Province.objects.get_or_create(name=province_name)
            if created:
                self.stdout.write(f'Created province: {province_name}')
            created_provinces[province_name] = province

        # Create counties
        for province_name, county_names in counties_data.items():
            if province_name in created_provinces:
                province = created_provinces[province_name]
                for county_name in county_names:
                    county, created = County.objects.get_or_create(
                        name=county_name,
                        province=province
                    )
                    if created:
                        self.stdout.write(f'Created county: {county_name} in {province_name}')

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created {len(created_provinces)} provinces and populated counties'
            )
        ) 