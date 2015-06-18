from django.conf.urls import patterns, url
from wfs.views import global_handler

# APP
urlpatterns = patterns('',
    url(r'^(?P<service_id>\d+)/$', global_handler, name='global_handler'),
)
