from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.contrib.sites.models import Site
from django.contrib.gis.db.models.functions import AsGML, Transform
from django.contrib.gis.geos import Polygon
from wfs.models import Service, FeatureType
import json
import logging
from django.contrib.gis.db.models.aggregates import Extent
from wfs.helpers import CRS, WGS84_CRS

log = logging.getLogger(__name__)

# xmllint --schema wfs/validation_schemas/WFS-capabilities.xsd
# "http://localhost:8000/wfs/?SERVICE=WFS&REQUEST=GetCapabilities&VERSION=99.99.99&bbox=1.2,3,4.5,-7" --noout


@csrf_exempt
def global_handler(request, service_id):
    request_type = None
    version = None
    service = None
    available_requests = ("getcapabilities", "describefeaturetype", "getfeature")
    available_services = ("wfs",)

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

        if low_key == "version":
            try:
                version = [int(x) for x in value.split(".")]
            except:
                return wfs_exception(request, "VersionNegotiationFailed", "version", value)
            else:
                if len(version) != 3:
                    return wfs_exception(request, "VersionNegotiationFailed", "version", value)

        if low_key == "service":
            service = low_value
            if service not in available_services:
                return wfs_exception(request, "InvalidService", "service", service)

    if request_type is None:
        return wfs_exception(request, "MissingParameter", "request")

    if service is None:
        return wfs_exception(request, "MissingParameter", "service")

    if request_type == "getcapabilities":
        return getcapabilities(request, wfs)
    elif request_type == "describefeaturetype":
        return describefeaturetype(request, wfs)
    elif request_type == "getfeature":
        return getfeature(request, wfs)

    return wfs_exception(request, "UnknownError", "")


def getcapabilities(request, service):
    context = {}
    context['service'] = service
    context['namespaces'] = [Site.objects.get_current()]

    return render(request, 'getCapabilities.xml', context, content_type="text/xml")


# PostgreSQL generate xml schema
# SELET * FROM table_to_xml(tbl regclass, nulls boolean, tableforest boolean, targetns text)
def describefeaturetype(request, service):
    typename = None
    outputformat = None
    available_formats = ("xmlschema",)

    for key, value in request.GET.items():
        low_key = key.lower()
        low_value = value.lower()

        if low_key == "typename":
            typename = value

        if low_key == "outputformat":
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

def getfeature(request, service):
    context = {}
    propertyname = None
    featureversion = None
    maxfeatures = None
    typename = None
    featureid = None
    filtr = None
    bbox = None
    # A fallback value, if no features can be found
    crs = WGS84_CRS

    for key, value in request.GET.items():
        low_key = key.lower()
        low_value = value.lower()

        if low_key == "propertyname":
            propertyname = low_value

        if low_key == "featureversion":
            featureversion = low_value

        if low_key == "maxfeatures":
            try:
                maxfeatures = int(low_value)
            except:
                return wfs_exception(request, "InvalidParameterValue", "maxfeatures", value)
            else:
                if maxfeatures < 1:
                    return wfs_exception(request, "InvalidParameterValue", "maxfeatures", value)

        if low_key == "typename":
            typename = low_value

        if low_key == "featureid":
            featureid = low_value

        if low_key == "filter":
            filtr = low_value

        if low_key == "bbox":
            #
            # See the following URL for all the gory details on the passed in bounding box:
            #
            # http://augusttown.blogspot.co.at/2010/08/mysterious-bbox-parameter-in-web.html
            bbox_values = low_value.split(",")
            
            if len(bbox_values) != 4 and len(bbox_values) !=5:
                return wfs_exception(request, "InvalidParameterValue", "bbox", value)
            
            try:
                bbox_crs = CRS(bbox_values[4]) if len(bbox_values) == 5 else WGS84_CRS
    
                if bbox_crs.crsid == "CRS84":
                    # we and GeoDjango operate in longitude/latitude mode, so ban CRS84
                    bbox = Polygon.from_bbox((float(bbox_values[1]),float(bbox_values[0]),float(bbox_values[3]),float(bbox_values[2])))
                    bbox_crs = WGS84_CRS
                else:
                    bbox = Polygon.from_bbox((float(bbox_values[0]),float(bbox_values[1]),float(bbox_values[2]),float(bbox_values[3])))
                
                bbox.set_srid(bbox_crs.srid)
            except:
                return wfs_exception(request, "InvalidParameterValue", "maxfeatures", value)

        if low_key == "srsname":
            try:
                crs = CRS(low_value)
    
                if crs.crsid == "CRS84":
                    # we and GeoDjango operate in longitude/latitude mode, so ban CRS84
                    crs = WGS84_CRS

            except:
                return wfs_exception(request, "InvalidParameterValue", "maxfeatures", value)
            

        if low_key == "filter":
            filtr = low_value
        

    if propertyname is not None:
        raise NotImplementedError

    if featureversion is not None:
        raise NotImplementedError

    if filtr is not None:
        raise NotImplementedError

    if bbox is not None:
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
                    
                    if crs.srid != ft_crs.srid:
                        objs = objs.annotate(xform=Transform(geom_field,crs.srid))
                        geom_field = "xform"

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

                if crs.srid != ft_crs.srid:
                    objs = objs.annotate(xform=Transform(geom_field,crs.srid))
                    geom_field = "xform"

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

    context['features'] = feature_list
    context['bbox0'] = result_bbox[0]
    context['bbox1'] = result_bbox[1]
    context['bbox2'] = result_bbox[2]
    context['bbox3'] = result_bbox[3]
    context['crs'] = crs
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


def featuretype_to_xml(featuretypes):
    for ft in featuretypes:
        ft.xml = ""
        fields = ft.model.model_class()._meta.fields
        for field in fields:
            if len(ft.fields) == 0 or field.name in ft.fields.split(","):
                ft.xml += '<element name="'
                if hasattr(field, "geom_type"):
                    ft.xml += 'geometry" type="gml:PointPropertyType"/>'
                else:
                    ft.xml += field.name + '" type="string"/>'

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
