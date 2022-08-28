from django.db import models
from django.urls import reverse
from django.contrib.sites.models import Site
from django.contrib.contenttypes.models import ContentType

import re

def split_comma_separated(value):
    '''
    Split a comma-separated list of words from a comma-separated database
    field value. The members of the returned list have leading and trailing
    whitespace stripped.
    
    :param value: A comma separated database field value.
    '''
    s = value.strip()
    if s:
        return re.split("\\s*,\\s*",s)
    else:
        return []
  

class Service(models.Model):
    name = models.CharField(max_length=254)
    title = models.CharField(max_length=254)
    keywords = models.CharField(null=True, blank=True, max_length=254, help_text='Comma separated list of keywords.')
    abstract = models.TextField(null=True, blank=True)
    fees = models.CharField(null=True, blank=True, max_length=254)
    access_constraints = models.CharField(null=True, blank=True, max_length=254)

    def online_resource(self):
        
        domain = Site.objects.get_current().domain
        
        if "://" in domain:
            # allow the configuration of https:// URL in the site plugin.
            return domain + self.get_absolute_url()
        else:
            return 'http://%s%s' % (domain, self.get_absolute_url())

    def get_absolute_url(self):
        return reverse('wfs', kwargs={'service_id': self.pk})

    def get_keywords_list(self):
        '''
        :return: A list of keywords as parsed from
                 the comma-separated member 'keywords'. 
        '''
        return split_comma_separated(self.keywords)
        
    def __str__(self):
        return self.name


class FeatureType(models.Model):
    service = models.ForeignKey(Service,on_delete=models.CASCADE)
    name = models.CharField(max_length=254,unique=True)
    title = models.CharField(null=True, blank=True, max_length=254)
    keywords = models.CharField(null=True, blank=True, max_length=254)
    abstract = models.TextField(null=True, blank=True)
    srs = models.CharField(max_length=254, default="EPSG:4326")
    othersrs = models.CharField(max_length=1020, default="EPSG:3857",null=True, blank=True,
                                help_text='Comma separated list of alternative Spatial Reference Systems to which database-persisted coordinates may be transformed.')
    model = models.ForeignKey(ContentType,on_delete=models.PROTECT,null=True, blank=True, help_text="django model or null, if a raw SQL query should be delivered.")
    fields = models.CharField(max_length=254, null=True, blank=True)
    query = models.TextField(default="{}", help_text="JSON containing the query to be passed to a Django queryset .filter() or a raw SQL query.")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.pk is not None:
            orig = FeatureType.objects.get(pk=self.pk)
            if orig.model != self.model:
                self.fields = ""
        super(FeatureType, self).save(*args, **kwargs)

    def find_first_geometry_field(self):
        for field_name in self.fields.split(','):
            if self.is_geom_field(field_name):
                return field_name
        return None
    
    def get_other_srs_names(self):
        '''
        :return: A list of alternative spatial reference systems as parsed from
                 the comma-separated member 'othersrs'. 
        '''
        return split_comma_separated(self.othersrs)
    
    def get_keywords_list(self):
        '''
        :return: A list of keywords as parsed from
                 the comma-separated member 'keywords'. 
        '''
        return split_comma_separated(self.keywords)

    def get_model_field(self,field_name):
        return self.model.model_class()._meta.get_field(field_name)

    def is_geom_field(self,field_name):
        field = self.get_model_field(field_name)
        return field and hasattr(field, "geom_type")

class MetadataURL(models.Model):
    featuretype = models.ForeignKey(FeatureType,on_delete=models.CASCADE)
    url = models.URLField()

    def __str__(self):
        return self.url


class BoundingBox(models.Model):
    featuretype = models.ForeignKey(FeatureType,on_delete=models.CASCADE)
    minx = models.CharField(max_length=254)
    miny = models.CharField(max_length=254)
    maxx = models.CharField(max_length=254)
    maxy = models.CharField(max_length=254)

    def __str__(self):
        return "((" + self.minx + ", " + self.miny + "), (" + self.maxx + ", " + self.maxy + "))"

class ResolutionFilter(models.Model):
    featuretype = models.ForeignKey(FeatureType,on_delete=models.CASCADE)
    min_resolution = models.FloatField(help_text="The minimal resolution at which to apply the additional query filter.",db_index=True)
    query = models.TextField(default="{}", help_text="JSON containing the query to be passed to a Django queryset .filter()")

    def __str__(self):
        return "res \u2265 %f" % self.min_resolution
