# Generated manually on 2025-10-11

from django.db import migrations, models
import django_jalali.db.models as jmodels
import jdatetime


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0010_invoicesettlementdraft'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoicesettlementdraft',
            name='work_date',
            field=jmodels.jDateField(
                db_index=True, 
                help_text='تاریخ ثبت تسویه\u200cهای این draft', 
                verbose_name='تاریخ کار',
                default=jdatetime.date.today
            ),
            preserve_default=False,
        ),
        migrations.AlterModelOptions(
            name='invoicesettlementdraft',
            options={
                'ordering': ['-work_date', '-updated_at'],
                'verbose_name': 'پیش\u200cنویس تسویه فاکتور',
                'verbose_name_plural': 'پیش\u200cنویس\u200cهای تسویه فاکتور'
            },
        ),
        migrations.AddIndex(
            model_name='invoicesettlementdraft',
            index=models.Index(fields=['-work_date', '-updated_at'], name='products_in_work_da_idx'),
        ),
        migrations.AddIndex(
            model_name='invoicesettlementdraft',
            index=models.Index(fields=['work_date', 'status'], name='products_in_work_st_idx'),
        ),
    ]
