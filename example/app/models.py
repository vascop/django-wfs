from django.contrib.gis.db import models


class MyGeoClass(models.Model):
    geopoint = models.PointField()
    objects = models.GeoManager()
