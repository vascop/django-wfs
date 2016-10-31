from django.conf.urls import url
from wfs.views import global_handler

# APP
urlpatterns = [
    url(r'^(?P<service_id>\d+)/$', global_handler, name='wfs'),
]
