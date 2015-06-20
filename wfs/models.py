from django.db import models
from django.core.urlresolvers import reverse
from django.contrib.sites.models import Site
from django.contrib.contenttypes.models import ContentType


class Service(models.Model):
    name = models.CharField(max_length=254)
    title = models.CharField(max_length=254)
    keywords = models.CharField(null=True, blank=True, max_length=254, help_text='Comma separated list of keywords.')
    abstract = models.TextField(null=True, blank=True)
    fees = models.CharField(null=True, blank=True, max_length=254)
    access_constraints = models.CharField(null=True, blank=True, max_length=254)

    def online_resource(self):
        return 'http://%s%s' % (Site.objects.get_current().domain, self.get_absolute_url())

    def get_absolute_url(self):
        return reverse('global_handler', kwargs={'service_id': self.pk})

    def __unicode__(self):
        return self.name


class FeatureType(models.Model):
    service = models.ForeignKey(Service)
    name = models.CharField(max_length=254)
    title = models.CharField(null=True, blank=True, max_length=254)
    keywords = models.CharField(null=True, blank=True, max_length=254)
    abstract = models.TextField(null=True, blank=True)
    srs = models.CharField(max_length=254, default="EPSG:4326")
    model = models.ForeignKey(ContentType)
    fields = models.CharField(max_length=254, null=True, blank=True)
    query = models.TextField(default="{}", help_text="JSON containing the query to be passed to a Django queryset .filter()")

    def __unicode__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.pk is not None:
            orig = FeatureType.objects.get(pk=self.pk)
            if orig.model != self.model:
                self.fields = ""
        super(FeatureType, self).save(*args, **kwargs)


class MetadataURL(models.Model):
    featuretype = models.ForeignKey(FeatureType)
    url = models.URLField()

    def __unicode__(self):
        return self.url


class BoundingBox(models.Model):
    featuretype = models.ForeignKey(FeatureType)
    minx = models.CharField(max_length=254)
    miny = models.CharField(max_length=254)
    maxx = models.CharField(max_length=254)
    maxy = models.CharField(max_length=254)

    def __unicode__(self):
        return "((" + self.minx + ", ", self.miny + "), (" + self.maxx + ", " + self.maxy + "))"
