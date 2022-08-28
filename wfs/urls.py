from django.conf.urls import url
from wfs.views import global_handler,related_handler

# APP
urlpatterns = [
    url(r'^(?P<service_id>\d+)/$',global_handler, name='wfs'),
    url(r'^(?P<service_id>\d+)/related/$',related_handler, name='wfs-related'),
]
