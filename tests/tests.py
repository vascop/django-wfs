from unittest import TestCase
from wfs.helpers import CRS

# Create your tests here.

class Test(TestCase):

    def testParseSrsUri(self):
        self.assertEqual(4326, CRS("http://www.opengis.net/def/crs/EPSG/0/4326").srid)
        self.assertEqual(4258, CRS("EPSG:4258").srid)
        self.assertEqual(4258, CRS("http://www.opengis.net/gml/srs/epsg.xml#4258").srid)
        self.assertEqual(4258, CRS("urn:ogc:def:crs:epsg::4258").srid)
        self.assertEqual(4258, CRS("urn:opengis:def:crs:epsg::4258").srid)
        self.assertEqual(4326, CRS("urn:ogc:def:crs:OGC:1.3:CRS84").srid)
        self.assertEqual(28992,CRS("urn:ogc:def:crs:EPSG:6.9:28992").srid)
        self.assertEqual(4326, CRS("urn:ogc:def:crs:EPSG:6.9:4326").srid)
        self.assertEqual(4326, CRS("urn:ogc:def:crs:EPSG:6.11:4326").srid)
        self.assertEqual(32633, CRS("urn:ogc:def:crs:EPSG:6.11.3:32633").srid)
        
        self.assertEqual("urn:ogc:def:crs:EPSG:6.9:32633",str(CRS(32633)))

        with self.assertRaises(SyntaxError):
            CRS("EPSG:CRS84")

        with self.assertRaises(SyntaxError):
            CRS("urn:ogc:def:crs:OGC:7:CRS84")

        with self.assertRaises(SyntaxError):
            CRS("urn:ogc:def:crs:EPSG:7.4:CRS84")
