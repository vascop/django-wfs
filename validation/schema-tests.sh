#!/bin/sh
#
# These tests may be performed to check schema compliance of the generated XML files.
#
# It depends on a configured feature with name 'sections' and sections objects
# with DB ID 2 and 3 in the database.
#
curl 'http://localhost:8011/wfs/1/?SERVICE=WFS&VERSION=1.0.0&REQUEST=GetCapabilities' > capabilities-1.0.0.xml
xmllint --schema http://schemas.opengis.net/wfs/1.0.0/WFS-capabilities.xsd --noout capabilities-1.0.0.xml 

curl 'http://localhost:8011/wfs/1/?SERVICE=WFS&VERSION=1.1.0&REQUEST=GetCapabilities' > capabilities-1.1.0.xml
xmllint --schema http://schemas.opengis.net/wfs/1.1.0/wfs.xsd --noout capabilities-1.1.0.xml 

curl 'http://localhost:8011/wfs/1/?SERVICE=WFS&VERSION=1.0.0&TYPENAME=sections&REQUEST=DescribeFeatureType' > sections-1.0.0.xsd
curl 'http://localhost:8011/wfs/1/?SERVICE=WFS&VERSION=1.0.0&REQUEST=GetFeature&TYPENAME=sections&SRSNAME=EPSG:4326&FEATUREID=sections.2,sections.3' > section2-1.0.0.xml
xmllint --schema sections-1.0.0.xsd --noout section2-1.0.0.xml

curl 'http://localhost:8011/wfs/1/?SERVICE=WFS&VERSION=1.1.0&TYPENAME=sections&REQUEST=DescribeFeatureType' > sections-1.1.0.xsd
curl 'http://localhost:8011/wfs/1/?SERVICE=WFS&VERSION=1.1.0&REQUEST=GetFeature&TYPENAME=sections&SRSNAME=EPSG:4326&FEATUREID=sections.2,sections.3' > section2-1.1.0.xml
xmllint --schema sections-1.1.0.xsd --noout section2-1.1.0.xml
