# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2020-10-20 09:25
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wfs', '0004_optional_model'),
    ]

    operations = [
        migrations.AlterField(
            model_name='featuretype',
            name='name',
            field=models.CharField(max_length=254, unique=True),
        ),
    ]