# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import common.validators


class Migration(migrations.Migration):

    dependencies = [
        ('hq', '0009_auto_20170812_2117'),
    ]

    operations = [
        migrations.AlterField(
            model_name='person',
            name='latitude',
            field=models.FloatField(blank=True, null=True, validators=[common.validators.RangeValidator(-90, 90)]),
        ),
        migrations.AlterField(
            model_name='person',
            name='longitude',
            field=models.FloatField(blank=True, null=True, validators=[common.validators.RangeValidator(-180, 180)]),
        ),
    ]
