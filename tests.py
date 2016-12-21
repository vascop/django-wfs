from unittest import TestCase
from wfs.helpers import CRS
from wfs.sqlutils import parse_single,replace_identifier,build_function_call,build_comparison,find_identifier,get_identifiers,add_condition
import logging
import sys

# development-mode logging
handler = logging.StreamHandler(sys.stderr)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s') 
handler.setFormatter(formatter)
handler.setLevel(logging.DEBUG)
    
root_logger = logging.getLogger()
root_logger.addHandler(handler)
root_logger.setLevel(logging.DEBUG)

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

# Create your tests here.

class Test(TestCase):

    def testParseSrsUri(self):
        self.assertEqual(4326, CRS("http://www.opengis.net/def/crs/EPSG/0/4326").srid)
        self.assertEqual(4258, CRS("EPSG:4258").srid)
        self.assertEqual(4258, CRS("http://www.opengis.net/gml/srs/epsg.xml#4258").srid)
        self.assertEqual(4258, CRS("urn:ogc:def:crs:epsg::4258").srid)
        self.assertEqual(4258, CRS("urn:opengis:def:crs:epsg::4258").srid)
        self.assertEqual(4326, CRS("urn:ogc:def:crs:OGC:1.3:CRS84").srid)
        self.assertEqual("CRS84", CRS("urn:ogc:def:crs:OGC:1.3:CRS84").crsid)
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

    def testSimplify(self):
        
        select = parse_single("select objectid as id, name,area,wkb_geometry as shape from import.abc_polygon")
        identifiers = get_identifiers(select)
        shape = find_identifier(identifiers,"shape")
        idi = find_identifier(identifiers,"id")
        simplified = build_function_call("ST_Simplify",shape,1,True)
        replace_identifier(identifiers,shape,simplified)
        log.info(select)
        
        self.assertEquals("select objectid as id, name,area,ST_Simplify(wkb_geometry,%s) AS shape from import.abc_polygon",str(select))

        add_condition(select,build_function_call("ST_Intersects",shape,1))

        log.info(select)

        self.assertEquals("select objectid as id, name,area,ST_Simplify(wkb_geometry,%s) AS shape from import.abc_polygon where ST_Intersects(wkb_geometry,%s)",str(select))

        add_condition(select,build_comparison(idi,"="))

        log.info(select)

        self.assertEquals("select objectid as id, name,area,ST_Simplify(wkb_geometry,%s) AS shape from import.abc_polygon where ST_Intersects(wkb_geometry,%s) and objectid = %s",str(select))

    def testSimplifyWhere(self):
        
        select = parse_single("select objectid as id, name,area,wkb_geometry as shape from import.abc_polygon where area > 1000000")
        identifiers = get_identifiers(select)
        shape = find_identifier(identifiers,"shape")
        idi = find_identifier(identifiers,"id")
        simplified = build_function_call("ST_Simplify",shape,1,True)
        replace_identifier(identifiers,shape,simplified)
        log.info(select)
        
        self.assertEquals("select objectid as id, name,area,ST_Simplify(wkb_geometry,%s) AS shape from import.abc_polygon where area > 1000000",str(select))

        add_condition(select,build_function_call("ST_Intersects",shape,1))

        log.info(select)

        self.assertEquals("select objectid as id, name,area,ST_Simplify(wkb_geometry,%s) AS shape from import.abc_polygon where area > 1000000 and ST_Intersects(wkb_geometry,%s)",str(select))

        add_condition(select,build_comparison(idi,"="))

        log.info(select)

        self.assertEquals("select objectid as id, name,area,ST_Simplify(wkb_geometry,%s) AS shape from import.abc_polygon where area > 1000000 and ST_Intersects(wkb_geometry,%s) and objectid = %s",str(select))

    def testSimplifyAlias(self):
        
        select = parse_single("select a.objectid as id, a.name,a.area,a.wkb_geometry as shape from import.abc_polygon a")
        identifiers = get_identifiers(select)
        shape = find_identifier(identifiers,"shape")
        idi = find_identifier(identifiers,"id")
        simplified = build_function_call("ST_Simplify",shape,1,True)
        replace_identifier(identifiers,shape,simplified)
        log.info(select)
        
        self.assertEquals("select a.objectid as id, a.name,a.area,ST_Simplify(a.wkb_geometry,%s) AS shape from import.abc_polygon a",str(select))

        add_condition(select,build_function_call("ST_Intersects",shape,1))

        log.info(select)

        self.assertEquals("select a.objectid as id, a.name,a.area,ST_Simplify(a.wkb_geometry,%s) AS shape from import.abc_polygon a where ST_Intersects(a.wkb_geometry,%s)",str(select))

        add_condition(select,build_comparison(idi,"="))

        log.info(select)

        self.assertEquals("select a.objectid as id, a.name,a.area,ST_Simplify(a.wkb_geometry,%s) AS shape from import.abc_polygon a where ST_Intersects(a.wkb_geometry,%s) and a.objectid = %s",str(select))

    def testAddCondition(self):
        
        select = parse_single("select objectid as id, name,area,wkb_geometry as shape from import.abc_polygon")
        identifiers = get_identifiers(select)
        shape = find_identifier(identifiers,"shape")
        idi = find_identifier(identifiers,"id")
        
        condition = parse_single("area > 1000000")
        
        simplified = build_function_call("ST_Simplify",shape,1,True)
        replace_identifier(identifiers,shape,simplified)
        log.info(select)
        
        self.assertEquals("select objectid as id, name,area,ST_Simplify(wkb_geometry,%s) AS shape from import.abc_polygon",str(select))

        add_condition(select,build_function_call("ST_Intersects",shape,1))

        log.info(select)

        self.assertEquals("select objectid as id, name,area,ST_Simplify(wkb_geometry,%s) AS shape from import.abc_polygon where ST_Intersects(wkb_geometry,%s)",str(select))

        add_condition(select,condition)

        log.info(select)

        self.assertEquals("select objectid as id, name,area,ST_Simplify(wkb_geometry,%s) AS shape from import.abc_polygon where ST_Intersects(wkb_geometry,%s) and area > 1000000",str(select))

