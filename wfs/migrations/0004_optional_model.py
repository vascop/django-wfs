# -*- coding: utf-8 -*-
# Generated by Django 1.10.3 on 2016-12-02 20:25
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('wfs', '0003_resolutionfilter'),
    ]

    operations = [
        migrations.AlterField(
            model_name='featuretype',
            name='model',
            field=models.ForeignKey(blank=True, help_text='django model or null, if a raw SQL query should be delivered.', null=True, on_delete=django.db.models.deletion.CASCADE, to='contenttypes.ContentType'),
        ),
        migrations.AlterField(
            model_name='featuretype',
            name='query',
            field=models.TextField(default='{}', help_text='JSON containing the query to be passed to a Django queryset .filter() or a raw SQL query.'),
        ),
    ]
