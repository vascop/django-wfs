# django-wfs
A WFS (web feature service) implementation as a Django application.

This implementation of WFS (currently) **very loosely** follows the [1.0.0 spec](http://www.opengeospatial.org/standards/wfs). It is currently **only tested with a PostGIS backend**.

What you can expect:
- GetCapabilities
- DescribeFeatureType
- GetFeature
- Django Queryset filtering

What is not here yet:
- Transactional requests
- Native WFS filtering (bbox and friends)

# Requirements
- Django
- Django sites framework
- PostgreSQL + PostGIS

# Example app
An example application can be found in the "example" folder of this repository.

# Installation

    pip install django-wfs

Add these to your `INSTALLED_APPS` setting:

    INSTALLED_APPS = (
        ...
        'django.contrib.gis',
        'django.contrib.sites',
        'wfs',
        ...
    )

And define a `SITE_ID` if you haven't yet:

    SITE_ID = 1

In your `urls.py` add (the actual regex can be anything, it doesn't have to be `^wfs/`):

    url(r'^wfs/', include('wfs.urls')),


Make sure you have a working PostGIS GeoDjango installation. Generally, if your database engine is `'django.contrib.gis.db.backends.postgis'`, stuff will probably not break too much. 

# WFS Service and Feature Types

In the admin you'll now have a WFS section with Services and Feature Types. These are the concepts present in the WFS spec but generally you can have multiple feature types in each service.

A Service is an endpoint like `/wfs/1` (service with ID 1). It has the parameters defined in the spec:

- Name
- Title
- Keywords
- Abstract
- Fees
- Access constraints

After you create a Service in the Django Admin you can then associate a Feature Type to the created service. A Feature Type has the following parameters:
- Service (foreign key)
- Name (**no spaces!!**)
- Title
- Keywords
- Abstract
- SRS: Spatial Reference System used by the Feature Type. Defaults to WGS 84 (EPSG:4326)
- Model (any model present in your Django project which contains a geo field)
- Fields (after selecting a Model and pressing the "Save and continue editing" button and you'll see its fields. The ones you select will be exposed through the service)
- Query (JSON representation of Django queryset filters. Example follows)

### Query

The JSON representation of Django queryset filters allow you cut down results presented by a Feature Type. Some examples:

Only display entries from a model if they belong to the "vascop" user:

    {"user__username":"vascop"}

Only display entries from a model if they belong to the "vascop" user and are published:

    {"user__username":"vascop", "published": true}


# Possible problems

If you have `APPEND_SLASH = True` (which is the Django default) and you're adding your WFS service to QGIS be sure to insert the connection with an appended slash, otherwise Django replies with a 301 code and QGIS won't display your layer.

Be sure to use Feature Type names which have no spaces or special characters. The title can have whatever you want.

Any other problem, submit an issue and I'll try to take a look at it.

