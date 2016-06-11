from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.contrib.gis.db.models.functions import AsGML, Transform, AsGeoJSON
from django.contrib.gis.geos import Polygon
from wfs.models import Service, FeatureType
import json
import logging
from django.contrib.gis.db.models.aggregates import Extent
from wfs.helpers import CRS, WGS84_CRS
from django.http.response import StreamingHttpResponse
import decimal

log = logging.getLogger(__name__)

# xmllint --schema wfs/validation_schemas/WFS-capabilities.xsd
# "http://localhost:8000/wfs/?SERVICE=WFS&REQUEST=GetCapabilities&VERSION=99.99.99&bbox=1.2,3,4.5,-7" --noout


@csrf_exempt
def global_handler(request, service_id):
    request_type = None
    service = None
    available_requests = ("getcapabilities", "describefeaturetype", "getfeature")
    available_services = ("wfs",)

    wfs_version = "1.1.0"

    try:
        wfs = Service.objects.get(id=service_id)
    except Service.DoesNotExist:
        return wfs_exception(request, "UnknownService", "", service_id)

    for key, value in request.GET.items():
        low_key = key.lower()
        low_value = value.lower()

        if low_key == "request":
            request_type = low_value
            if request_type not in available_requests:
                return wfs_exception(request, "InvalidRequest", "request", value)

        elif low_key == "version":
            if value != "1.0.0" and value != "1.1.0":
                return wfs_exception(request, "VersionNegotiationFailed", "version", value)
            wfs_version = value

        elif low_key == "service":
            service = low_value
            if service not in available_services:
                return wfs_exception(request, "InvalidService", "service", service)

    if request_type is None:
        return wfs_exception(request, "MissingParameter", "request")

    if service is None:
        return wfs_exception(request, "MissingParameter", "service")

    if request_type == "getcapabilities":
        return getcapabilities(request, wfs,wfs_version)
    elif request_type == "describefeaturetype":
        return describefeaturetype(request, wfs,wfs_version)
    elif request_type == "getfeature":
        return getfeature(request, wfs,wfs_version)

    return wfs_exception(request, "UnknownError", "")


def getcapabilities(request, service,wfs_version):
    context = {}
    context['service'] = service
    context['version'] = wfs_version
    context['wfs_path'] = "1.0.0/WFS-capabilities.xsd" if wfs_version == "1.0.0" else "1.1.0/wfs.xsd"

    return render(request, 'getCapabilities.xml', context, content_type="text/xml")


# PostgreSQL generate xml schema
# SELET * FROM table_to_xml(tbl regclass, nulls boolean, tableforest boolean, targetns text)
def describefeaturetype(request, service,wfs_version):
    typename = None
    outputformat = None
    available_formats = ("xmlschema",)

    for key, value in request.GET.items():
        low_key = key.lower()
        low_value = value.lower()

        if low_key == "typename":
            typename = value

        elif low_key == "outputformat":
            outputformat = low_value
            if outputformat not in available_formats:
                return wfs_exception(request, "InvalidParameterValue", "outputformat", value)

    if typename is None:
        ft = service.featuretype_set.all()
    else:
        ft = service.featuretype_set.filter(name__in=typename.split(","))

    if len(ft) < 1:
        return wfs_exception(request, "InvalidParameterValue", "typename", typename)

    featuretype_to_xml(ft)

    context = {}
    context['featuretypes'] = ft
    context['version'] = wfs_version
    context['gml_path'] = "2.1.2/feature.xsd" if wfs_version == "1.0.0" else "3.1.1/base/gml.xsd"

    return render(request, 'describeFeatureType.xml', context, content_type="text/xml")

class type_feature_iter:
    def __init__(self):
        self.types_with_features = []
    
    def add_type_with_features(self,ftype,feature_iter):
        self.types_with_features.append((ftype,feature_iter))
    
    def __iter__(self):
        for ftype,feature_iter in self.types_with_features:
            for feature in feature_iter:
                yield ftype,feature

class DecimalEncoder(json.JSONEncoder):
    
    def default(self,o):
        if isinstance(o, decimal.Decimal):
            return float(o)
        return super(DecimalEncoder,self).default(o)

class GeoJsonIterator:
    '''
        This iterator renders a coordinate reference System, a bounding box and
        an iterator returning pairs for FeatureType and GeoJson Features in the following
        format::
        
            {"type": "FeatureCollection",
             "totalFeatures": 98,
             "bbox": [-8935094.49, 5372483.33, -8881826.36, 5395217.69]
             "crs":  {type: "name", properties: {name: "urn:ogc:def:crs:EPSG::3857"}}
             "features": [
               {"type": "Feature",
                "id": "water_areas.2381",
                "geometry": {type: "Polygon",…},
                "properties": {"name":"gallaway creek","ref_id":1252,… },
               …]
            }

        :ivar crs: The coordinate reference system to be included in the response.
        :ivar bbox: The bounding box tuple of 4 numbers to be included in the response.
        :ivar feature_iter: An iterator returning a pair (FeatureType,Feature) of the
                            features to be rendere in the response.
    '''
    
    def __init__(self,crs,bbox,feature_iter):
        self.crs=crs
        self.bbox = bbox
        self.feature_iter = feature_iter
        
    def __iter__(self):
        
        yield '{"type":"FeatureCollection","crs":{"type":"name","properties":{"name":%s}},"bbox":%s,"features":['%(json.dumps(str(self.crs)),json.dumps(self.bbox))
        
        nfeatures = 0
        sep = ""
        
        for ftype,feature in self.feature_iter:
            
            props = {}
            geometry = None
            
            for field_name in ftype.fields.split(","):
                if field_name:
                    field = ftype.get_model_field(field_name)
                if field:
                    if hasattr(field, "geom_type"):
                        if feature.geojson:
                            geometry = feature.geojson
                    else:
                        props[field.name] = getattr(feature, field.name)

            yield '%s{"type":"Feature","id":%s,"geometry":%s,"properties":%s}'%(
                            sep,json.dumps("%s.%d"%(ftype.name,feature.id)),
                            geometry,
                            json.dumps(props,cls=DecimalEncoder))
            sep = ","
            nfeatures += 1
        
        yield '],"totalFeatures":%d}'%nfeatures

XML_OUTPUT_FORMAT = "application/gml+xml"
ALL_XML_OUTPUT_FORMATS = ( XML_OUTPUT_FORMAT, "application/xml", "text/xml", "xml", "gml" )

JSON_OUTPUT_FORMAT = "application/json"
ALL_JSON_OUTPUT_FORMATS = ( JSON_OUTPUT_FORMAT, "json" )

def getfeature(request, service,wfs_version):
    context = {}
    propertyname = None
    featureversion = None
    maxfeatures = None
    typename = None
    featureid = None
    filtr = None
    bbox = None
    bbox_has_crs = False
    outputFormat = None
    
    # A fallback value, if no features can be found
    crs = WGS84_CRS

    for key, value in request.GET.items():
        low_key = key.lower()
        low_value = value.lower()

        if low_key == "propertyname":
            propertyname = low_value

        elif low_key == "featureversion":
            featureversion = low_value

        elif low_key == "maxfeatures":
            try:
                maxfeatures = int(low_value)
            except:
                return wfs_exception(request, "InvalidParameterValue", "maxfeatures", value)
            else:
                if maxfeatures < 1:
                    return wfs_exception(request, "InvalidParameterValue", "maxfeatures", value)

        elif low_key == "typename":
            typename = low_value

        elif low_key == "featureid":
            featureid = low_value

        elif low_key == "filter":
            filtr = low_value

        elif low_key == "bbox":
            #
            # See the following URL for all the gory details on the passed in bounding box:
            #
            # http://augusttown.blogspot.co.at/2010/08/mysterious-bbox-parameter-in-web.html
            bbox_values = low_value.split(",")
            
            if len(bbox_values) != 4 and (wfs_version == "1.0.0" or len(bbox_values) !=5):
                return wfs_exception(request, "InvalidParameterValue", "bbox", value)
            
            try:
                bbox_has_crs =  len(bbox_values) == 5
                
                bbox_crs = CRS(bbox_values[4]) if bbox_has_crs else crs
    
                if bbox_crs.crsid == "CRS84":
                    # we and GeoDjango operate in longitude/latitude mode, so ban CRS84
                    bbox = Polygon.from_bbox((float(bbox_values[1]),float(bbox_values[0]),float(bbox_values[3]),float(bbox_values[2])))
                    bbox_crs = WGS84_CRS
                else:
                    bbox = Polygon.from_bbox((float(bbox_values[0]),float(bbox_values[1]),float(bbox_values[2]),float(bbox_values[3])))
                
                bbox.set_srid(bbox_crs.srid)
            except:
                return wfs_exception(request, "InvalidParameterValue", "maxfeatures", value)

        elif low_key == "srsname":
            try:
                crs = CRS(low_value)
    
                if crs.crsid == "CRS84":
                    # we and GeoDjango operate in longitude/latitude mode, so ban CRS84
                    crs = WGS84_CRS

            except:
                return wfs_exception(request, "InvalidParameterValue", "maxfeatures", value)
            
            # This is for the case, that srsname is hit after the bbox parameter above
            if bbox and not bbox_has_crs:
                bbox.set_srid(crs.srid)

        elif low_key == "filter":
            filtr = low_value
        
        elif low_key == "outputformat":
            
            if low_value in ALL_JSON_OUTPUT_FORMATS:
                outputFormat = JSON_OUTPUT_FORMAT
            elif low_value in ALL_XML_OUTPUT_FORMATS:
                outputFormat = XML_OUTPUT_FORMAT
            else:
                return wfs_exception(request, "InvalidParameterValue", "outputformat", value)

    if propertyname is not None:
        raise NotImplementedError

    if featureversion is not None:
        raise NotImplementedError

    if filtr is not None:
        raise NotImplementedError

    result_bbox=None

    # If FeatureID is present we return every feature on the list of ID's
    if featureid is not None:
        
        feature_list = []
        
        # we assume every feature is identified by its Featuretype name + its object ID like "name.id"
        for feature in featureid.split(","):
            try:
                ftname, fid = get_feature_from_parameter(feature)
            except ValueError:
                return wfs_exception(request, "InvalidParameterValue", "featureid", feature)
            try:
                ft = service.featuretype_set.get(name=ftname)
                ft_crs = CRS(ft.srs)
                try:
                    geom_field = ft.find_first_geometry_field()
                    if geom_field is None:
                        return wfs_exception(request, "NoGeometryField", "feature")
            
                    flter = json.loads(ft.query)
                    objs=ft.model.model_class().objects

                    if bbox:
                        bbox_args = { geom_field+"__bboverlaps":bbox }
                        objs=objs.filter(**bbox_args)
                    
                    if crs.srid != ft_crs.srid:
                        objs = objs.annotate(xform=Transform(geom_field,crs.srid))
                        geom_field = "xform"

                    if outputFormat == JSON_OUTPUT_FORMAT:
                        objs = objs.annotate(geojson=AsGeoJSON(geom_field))
                    else:
                        objs = objs.annotate(gml=AsGML(geom_field))

                    if flter:
                        objs = objs.filter(**flter)
                        
                    f = objs.filter(id=fid)

                    bb_res = f.aggregate(Extent(geom_field))[geom_field+'__extent']

                    if log.getEffectiveLevel() <= logging.DEBUG:
                        log.debug("Bounding box for feature [%s] is [%s]"%(feature,bb_res))
                    
                    if result_bbox is None:
                        result_bbox = bb_res
                    else:
                        result_bbox =(min(result_bbox[0],bb_res[0]),min(result_bbox[1],bb_res[1]),
                                      max(result_bbox[2],bb_res[2]),max(result_bbox[3],bb_res[3]) )

                    feature_list.append((ft, f[0]))
                except:
                    log.exception("caught exception in request [%s %s?%s]",request.method,request.path,request.environ['QUERY_STRING'])
                    return wfs_exception(request, "MalformedJSONQuery", "query")
            except FeatureType.DoesNotExist:
                return wfs_exception(request, "InvalidParameterValue", "featureid", feature)
    # If FeatureID isn't present we rely on TypeName and return every feature present it the requested FeatureTypes
    elif typename is not None:
        
        feature_list = type_feature_iter()
        
        for typen in typename.split(","):
            try:
                ft = service.featuretype_set.get(name__iexact=typen)
                ft_crs = CRS(ft.srs)
            except FeatureType.DoesNotExist:
                return wfs_exception(request, "InvalidParameterValue", "typename", typen)
            try:
                geom_field = ft.find_first_geometry_field()
                if geom_field is None:
                    return wfs_exception(request, "NoGeometryField", "feature")
            
                flter = json.loads(ft.query)
                
                objs=ft.model.model_class().objects

                if bbox:
                    bbox_args = { geom_field+"__bboverlaps":bbox }
                    objs=objs.filter(**bbox_args)

                if crs.srid != ft_crs.srid:
                    objs = objs.annotate(xform=Transform(geom_field,crs.srid))
                    geom_field = "xform"

                if outputFormat == JSON_OUTPUT_FORMAT:
                    objs = objs.annotate(geojson=AsGeoJSON(geom_field))
                else:
                    objs = objs.annotate(gml=AsGML(geom_field))

                if flter:
                    objs = objs.filter(**flter)
                else:
                    objs=objs.all()

                bb_res = objs.aggregate(Extent(geom_field))[geom_field+'__extent']

                if log.getEffectiveLevel() <= logging.DEBUG:
                    log.debug("Bounding box for feature type [%s] is [%s]"%(typen,bb_res))

                if result_bbox is None:
                    result_bbox = bb_res
                else:
                    result_bbox =(min(result_bbox[0],bb_res[0]),min(result_bbox[1],bb_res[1]),
                                   max(result_bbox[2],bb_res[2]),max(result_bbox[3],bb_res[3]) )

                feature_list.add_type_with_features(ft,objs)

            except:
                log.exception("caught exception in request [%s %s?%s]",request.method,request.path,request.environ['QUERY_STRING'])
                return wfs_exception(request, "MalformedJSONQuery", "query")
    else:
        return wfs_exception(request, "MissingParameter", "typename")

    if outputFormat == JSON_OUTPUT_FORMAT:
        
        return StreamingHttpResponse(streaming_content=GeoJsonIterator(crs,result_bbox,feature_list),content_type="application/json")
        
    else:
        context['features'] = feature_list
        context['bbox0'] = result_bbox[0]
        context['bbox1'] = result_bbox[1]
        context['bbox2'] = result_bbox[2]
        context['bbox3'] = result_bbox[3]
        context['crs'] = crs
        context['version'] = wfs_version
        context['wfs_path'] = "1.0.0/WFS-basic.xsd" if wfs_version == "1.0.0" else "1.1.0/wfs.xsd"
        return render(request, 'getFeature.xml', context, content_type="text/xml")


def wfs_exception(request, code, locator, parameter=None):
    context = {}
    context['code'] = code
    context['locator'] = locator

    text = ""
    if code == "InvalidParameterValue":
        text = "Invalid value '" + str(parameter) + "' in parameter '" + str(locator) + "'."
    elif code == "VersionNegotiationFailed":
        text = "'" + str(parameter) + "' is an invalid version number."
    elif code == "InvalidRequest":
        text = "'" + str(parameter) + "' is an invalid request."
    elif code == "InvalidService":
        text = "'" + str(parameter) + "' is an invalid service."
    elif code == "MissingParameter":
        text = "Missing required '" + str(locator) + "' parameter."
    elif code == "UnknownService":
        text = "No available WFS service with id '" + str(parameter) + "'."
    elif code == "MalformedJSONQuery":
        text = "The JSON query defined for this feature type is malformed."
    elif code == "NoGeometryField":
        text = "The feature does not reference at least one geometry field."
    elif code == "UnknownError":
        text = "Something went wrong."

    context['text'] = text
    return render(request, 'exception.xml', context, content_type="text/xml")

#
# This list a synthesis of this geomtry type in
#   http://schemas.opengis.net/gml/2.1.2/feature.xsd
# and
#   http://www.opengeospatial.org/standards/sfs
#
GML_GEOTYPES = { 'POINT':           'gml:PointPropertyType',
                 'LINESTRING':      'gml:LineStringPropertyType',
                 'POLYGON':         'gml:PolygonPropertyType',
                 'MULTIPOINT':      'gml:MultiPointPropertyType',
                 'MULTILINESTRING': 'gml:MultiLineStringPropertyType',
                 'MULTIPOLYGON':    'gml:MultiPolygonPropertyType',
                 'GEOMCOLLECTION':  'gml:MultiGeometryPropertyType',
                }

def featuretype_to_xml(featuretypes):
    for ft in featuretypes:
        ft.xml = ""
        fields = ft.model.model_class()._meta.fields
        for field in fields:
            if len(ft.fields) == 0 or field.name in ft.fields.split(","):
                ft.xml += '<xsd:element name="'
                if hasattr(field, "geom_type"):
                    
                    gmlType = GML_GEOTYPES.get(field.geom_type,"gml:PointPropertyType")
                    ft.xml += 'geometry" type="%s"/>' % gmlType
                else:
                    ft.xml += field.name + '" type="xsd:string"/>'

def get_feature_from_parameter(parameter):
    dot = 0
    for c in parameter:
        if c == ".":
            dot += 1
            if dot > 1:
                break
    if dot != 1:
        raise ValueError

    return parameter.split(".")
