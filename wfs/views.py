from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.contrib.gis.db.models.functions import AsGML, Transform
from django.contrib.gis.geos import Polygon
from wfs.functions import parse_query
from wfs.models import Service, FeatureType
import json
import logging
from django.contrib.gis.db.models.aggregates import Extent
from wfs.helpers import CRS, WGS84_CRS
from django.http.response import StreamingHttpResponse
import decimal
import re
from django.db import connection
from django.contrib.gis.geos.geometry import GEOSGeometry
import io
from wfs.sqlutils import parse_single, get_identifiers, find_identifier,\
    build_function_call, add_condition, build_comparison, replace_identifier

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

def atoi(text):
    return int(text) if text.isdigit() else text


def _is_geom_column(colinfo):
    '''
    Check, if a raw SQL column info represents a geometry column.
    
    :param colinfo: A tuple with the column name and the column type according to PEP-249.
    '''
    return colinfo[0] == "shape"

def _is_id_column(colinfo):
    '''
    Check, if a raw SQL column info represents an ID column.
    
    :param colinfo: A tuple with the column name and the column type according to PEP-249.
    '''
    return colinfo[0] == "id"

def natural_keys(text):
    '''
    alist.sort(key=natural_keys) sorts in human order
    http://nedbatchelder.com/blog/200712/human_sorting.html
    (See Toothy's implementation in the comments)
    '''
    return [ atoi(c) for c in re.split('(\\d+)', text) ]

def getcapabilities(request, service,wfs_version):
    context = {}
    context['service'] = service
    context['version'] = wfs_version
    context['wfs_path'] = "1.0.0/WFS-capabilities.xsd" if wfs_version == "1.0.0" else "1.1.0/wfs.xsd"

    if wfs_version != "1.0.0":
        
        featuretypes = service.featuretype_set.all()
    
        allsrs = set()
        
        for featuretype in featuretypes:
            
            allsrs.add(featuretype.srs)
            
            for srs in featuretype.get_other_srs_names():
                allsrs.add(srs)
        
        allsrsnames = list(allsrs)
        allsrsnames.sort(key=natural_keys)
        context['allsrs'] = allsrsnames
        context['keywords'] = service.get_keywords_list()
        return render(request, 'getCapabilities-1-1.xml', context, content_type="text/xml")
    else:   
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
    def __init__(self,raw,srid,precision = None):
        self.types_with_features = []
        self.raw = raw
        self.srid = srid
        self.precision = precision
    
    def add_type_with_features(self,ftype,feature_iter):
        self.types_with_features.append((ftype,feature_iter))
        
    def __iter__(self):
        for ftype,feature_iter in self.types_with_features:
            
            if ftype.model is None:
                for feature in feature_iter:
                    yield ftype,RawFeature(feature_iter.description,feature,self.srid)
            else:
                for feature in feature_iter:
                    if self.raw:
                        yield ftype,feature
                    else:
                        yield ftype,DjangoFeature(ftype,feature,self.precision)

    def close(self):
        for ftype,feature_iter in self.types_with_features:  # @UnusedVariable
            if hasattr(feature_iter,"close"):
                try:
                    feature_iter.close()
                except:
                    log.exception("Error closing feature iterator.")
    
class DecimalEncoder(json.JSONEncoder):
    
    def default(self,o):
        if isinstance(o, decimal.Decimal):
            return float(o)
        return super(DecimalEncoder,self).default(o)

class RawFeature:
    
    def __init__(self,colinfos,row,srid):
        '''
        Convert a SQL result set row and a list of SQL result set colinfos
        to a properties array and a geometry geojson string.
        
        :param colinfos: A list of PEP-249 colinfo tuples.
        :param row: An SQL result set row with as many members as ``colinfos``
        :param srid: The target spatial reference ID to convert the geometry to.
        '''
        
        self.props = {}
        self.id = None
        self.geometry = None
        
        for i,colinfo in enumerate(colinfos):
            if _is_geom_column(colinfo):
                
                geom = GEOSGeometry(row[i])
                
                if srid is not None and srid != geom.srid:
                    geom.transform(srid)
                
                self.geometry = geom
                    
            else:
                if _is_id_column(colinfo):
                    self.id = row[i]
                
                self.props[colinfo[0]] = row[i]

class DjangoFeature:
    
    def __init__(self,ftype,feature,precision=None):
        '''
        Convert a django feature and a feature type to a properties array and a    
        geometry geojson string. 
        
        :param ftype: A feature type
        :param feature: A feature
        :param precision: A precision for simplifying geometries or None to
                          to skip geometry simplifications.
        '''
        
        self.props = {}
        self.id = feature.id
        self.geometry = None
        
        for field_name in ftype.fields.split(","):
            if field_name:
                field = ftype.get_model_field(field_name)
            if field:
                if hasattr(field, "geom_type"):
                    if precision is None:
                        self.geometry = getattr(feature,field.name)
                    else:
                        self.geometry = getattr(feature,field.name).simplify(precision)
                elif field.concrete:
                    self.props[field.name] = getattr(feature, field.name)
                elif field.one_to_many:
                    self.props[field.name] = {"url": "/wfs/%d/related/?id=%s.%d&field=%s" %(self.service_id,ftype.name,feature.id,field.name)}


class GeoJsonIterator:
    '''
        This iterator renders a coordinate reference System, a bounding box and
        an iterator returning pairs for FeatureType and GeoJson Features in the following
        format::
        
            {"type": "FeatureCollection",
             "totalFeatures": 98,
             "bbox": [-8935094.49, 5372483.33, -8881826.36, 5395217.69]
             "crs":  {type: "name", properties: {name: "EPSG:3857"}}
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
    
    def __init__(self,service_id,crs,bbox,feature_iter):
        self.service_id = service_id
        self.crs=crs
        self.bbox = bbox
        self.feature_iter = feature_iter
        
    def __iter__(self):

        os = io.StringIO()
        
        try:
            if self.bbox:        
                os.write('{"type":"FeatureCollection","crs":{"type":"name","properties":{"name":%s}},"bbox":%s,"features":['%(json.dumps(self.crs.get_legacy()),json.dumps(self.bbox)))
            else:
                os.write('{"type":"FeatureCollection","crs":{"type":"name","properties":{"name":%s}},"features":['%json.dumps(self.crs.get_legacy()))
            
            nfeatures = 0
            sep = ""
            
            for ftype,feature in self.feature_iter:
                
                os.write('%s{"type":"Feature","id":%s,"geometry":%s,"properties":%s}'%(
                                sep,json.dumps("%s.%d"%(ftype.name,feature.id)),
                                feature.geometry.geojson,
                                json.dumps(feature.props,cls=DecimalEncoder)))
                
                if os.tell() > 16383:
                    v = os.getvalue()
                    os.close()
                    os = io.StringIO()
                    yield v
    
                sep = ","
                nfeatures += 1
            
            os.write('],"totalFeatures":%d}'%nfeatures)
            yield os.getvalue()

        finally:
            os.close()

    def close(self):
        
        if hasattr(self.feature_iter,"close"):
            self.feature_iter.close()

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
    resolution = None
    precision = None
    
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

        elif low_key == "resolution":
            try:
                resolution = float(low_value)
            except:
                return wfs_exception(request, "InvalidParameterValue", "resolution", value)

        elif low_key == "precision":
            try:
                precision = float(low_value)
            except:
                return wfs_exception(request, "InvalidParameterValue", "precision", value)

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
                return wfs_exception(request, "InvalidParameterValue", "bbox", value)

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

    closeable = None

    try:
    
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
                        
                        if ft.model is None:

                            # GML output of raw results not yet implemented
                            if outputFormat != JSON_OUTPUT_FORMAT:
                                raise NotImplementedError
                            
                            # prepare SQL statement
                            select = parse_single(ft.query)
                            identifiers = get_identifiers(select)
                            shape = find_identifier(identifiers,"shape")
                            idi = find_identifier(identifiers,"id")
                            
                            # replace shape by ST_Simplify(shape,%s)
                            if precision is not None:
                                simplified = build_function_call("ST_Simplify",shape,1,True)
                                replace_identifier(identifiers,shape,simplified)
                            
                            # add restriction id=%s
                            add_condition(select,build_comparison(idi,"="))

                            sql = str(select)
                                
                            if log.getEffectiveLevel() <= logging.DEBUG:
                                log.debug("Final SQL for feature [%s] is [%s]"%(feature,sql))
                            
                            # raw SQL result set
                            with connection.cursor() as cur:
                               
                                if precision is None:
                                    cur.execute(ft.query,(fid,))
                                else:
                                    cur.execute(ft.query,(precision,fid))
                        
                                row = cur.fetchone()
                                
                                feature = RawFeature(cur.description,row,crs.srid)
                            
                                if feature.geometry is None:
                                    return wfs_exception(request, "NoGeometryField", "feature")
                                
                                feature_list.append((ft,feature))
                        else:
                            # django model based result set.
                            geom_field = ft.find_first_geometry_field()
                            if geom_field is None:
                                return wfs_exception(request, "NoGeometryField", "feature")
                    
                            flter = parse_query(ft.query)
                            objs=ft.model.model_class().objects
        
                            if flter:
                                objs = objs.filter(**flter)
                                
                            if bbox:
                                bbox_args = { geom_field+"__bboverlaps":bbox }
                                objs=objs.filter(**bbox_args)

                            objs = objs.filter(id=fid)
                            
                            if crs.srid != ft_crs.srid:
                                objs = objs.annotate(xform=Transform(geom_field,crs.srid))
                                geom_field = "xform"
        
                            bb_res = objs.aggregate(Extent(geom_field))[geom_field+'__extent']
        
                            if log.getEffectiveLevel() <= logging.DEBUG:
                                log.debug("Bounding box for feature [%s] is [%s]"%(feature,bb_res))
                            
                            if result_bbox is None:
                                result_bbox = bb_res
                            else:
                                result_bbox =(min(result_bbox[0],bb_res[0]),min(result_bbox[1],bb_res[1]),
                                              max(result_bbox[2],bb_res[2]),max(result_bbox[3],bb_res[3]) )
                                
                            if outputFormat == XML_OUTPUT_FORMAT:
                                objs = objs.annotate(gml=AsGML(geom_field))
        
                            f = objs.first()
        
                            if f is None:
                                log.warning("Feature with ID [%s] not found."%feature)
                            else:
                                if outputFormat == JSON_OUTPUT_FORMAT:
                                    feature_list.append((ft, DjangoFeature(ft,objs[0],precision)))
                                else:
                                    feature_list.append((ft, objs[0]))
                                    
                    except:
                        log.exception("caught exception in request [%s %s?%s]",request.method,request.path,request.environ['QUERY_STRING'])
                        return wfs_exception(request, "MalformedJSONQuery", "query")
                except FeatureType.DoesNotExist:
                    return wfs_exception(request, "InvalidParameterValue", "featureid", feature)
        # If FeatureID isn't present we rely on TypeName and return every feature present it the requested FeatureTypes
        elif typename is not None:
            
            feature_list = type_feature_iter(outputFormat != JSON_OUTPUT_FORMAT,crs.srid,precision)
            closeable = feature_list
            
            for typen in typename.split(","):
                try:
                    ft = service.featuretype_set.get(name__iexact=typen)
                    ft_crs = CRS(ft.srs)
                except FeatureType.DoesNotExist:
                    return wfs_exception(request, "InvalidParameterValue", "typename", typen)
                
                if ft.model is None:

                    # raw SQL result set
                    
                    # GML output of raw results not yet implemented
                    if outputFormat != JSON_OUTPUT_FORMAT:
                        raise NotImplementedError
                    
                    # prepare SQL statement
                    select = parse_single(ft.query)
                    identifiers = get_identifiers(select)
                    shape = find_identifier(identifiers,"shape")
                    idi = find_identifier(identifiers,"id")
                            
                    # parameters of SQL query
                    params = []        
                    
                    # replace shape by ST_Simplify(shape,%s)
                    if precision is not None:
                        simplified = build_function_call("ST_Simplify",shape,1,True)
                        replace_identifier(identifiers,shape,simplified)
                        params.append(resolution)
                            
                    if resolution is not None:
                            
                        res_flter = ft.resolutionfilter_set.filter(min_resolution__lte = resolution).order_by("-min_resolution").first()
                            
                        if res_flter:
                            if log.getEffectiveLevel() <= logging.DEBUG:
                                log.debug("Applying extra filter [%s] with condition [%s] for resolution [%f]"%(res_flter,res_flter.query,resolution))
                            
                            res_flter_parsed = parse_single(res_flter.query)
                                
                            add_condition(select,res_flter_parsed)
                            
                    if bbox is not None:
                        add_condition(select,build_function_call("ST_Intersects",shape,1))
                        params.append(bbox.hexewkb.decode("utf-8"))    

                    sql = str(select)
                                
                    if log.getEffectiveLevel() <= logging.DEBUG:
                        log.debug("Final SQL for feature [%s] is [%s]"%(ft.name,sql))

                    cur = connection.cursor()
    
                    try:
                        cur.execute(sql,params)
                    
                        has_geometry = False
                    
                        for colinfo in cur.description:
                            if _is_geom_column(colinfo):
                                has_geometry = True
                                break
                    
                        if not has_geometry:
                            return wfs_exception(request, "NoGeometryField", "feature")

                        feature_list.add_type_with_features(ft,cur)
                        
                    except:
                        cur.close()
                        log.exception("caught exception in request [%s %s?%s]",request.method,request.path,request.environ['QUERY_STRING'])
                        return wfs_exception(request, "MalformedJSONQuery", "query")
                
                else:
                    try:
                        geom_field = ft.find_first_geometry_field()
                        if geom_field is None:
                            return wfs_exception(request, "NoGeometryField", "feature")
                    
                        flter = parse_query(ft.query)
                        
                        objs=ft.model.model_class().objects
        
                        if flter:
                            objs = objs.filter(**flter)
        
                        if resolution is not None:
                            
                            res_flter = ft.resolutionfilter_set.filter(min_resolution__lte = resolution).order_by("-min_resolution").first()
                            
                            if res_flter:
                                log.debug("Applying extra filter [%s] with condition [%s] for resolution [%f]"%(res_flter,res_flter.query,resolution))
                                res_flter_parsed = parse_query(res_flter.query)
                                objs = objs.filter(**res_flter_parsed)
        
                        if bbox:
                            bbox_args = { geom_field+"__bboverlaps":bbox }
                            objs=objs.filter(**bbox_args)
        
                        if crs.srid != ft_crs.srid:
                            objs = objs.annotate(xform=Transform(geom_field,crs.srid))
                            geom_field = "xform"
        
                        bb_res = objs.aggregate(Extent(geom_field))[geom_field+'__extent']
        
                        if log.getEffectiveLevel() <= logging.DEBUG:
                            log.debug("Bounding box for feature type [%s] is [%s]"%(typen,bb_res))
        
                        if result_bbox is None:
                            result_bbox = bb_res
                        else:
                            result_bbox =(min(result_bbox[0],bb_res[0]),min(result_bbox[1],bb_res[1]),
                                           max(result_bbox[2],bb_res[2]),max(result_bbox[3],bb_res[3]) )
        
                        if outputFormat == XML_OUTPUT_FORMAT:
                            objs = objs.annotate(gml=AsGML(geom_field))
        
                        feature_list.add_type_with_features(ft,objs)
        
                    except:
                        log.exception("caught exception in request [%s %s?%s]",request.method,request.path,request.environ['QUERY_STRING'])
                        return wfs_exception(request, "MalformedJSONQuery", "query")
        else:
            return wfs_exception(request, "MissingParameter", "typename")
    
        if outputFormat == JSON_OUTPUT_FORMAT:
            
            ret = StreamingHttpResponse(streaming_content=GeoJsonIterator(service.id,crs,result_bbox,feature_list),content_type="application/json")
            
        else:
            context['features'] = feature_list
            if result_bbox:
                context['bbox0'] = result_bbox[0]
                context['bbox1'] = result_bbox[1]
                context['bbox2'] = result_bbox[2]
                context['bbox3'] = result_bbox[3]
            context['crs'] = crs
            context['version'] = wfs_version
            context['wfs_path'] = "1.0.0/WFS-basic.xsd" if wfs_version == "1.0.0" else "1.1.0/wfs.xsd"
            ret = render(request, 'getFeature.xml', context, content_type="text/xml")

        # Now, closing of resources is delegated to the HTTP response
        closeable = None
        return ret

    finally:
        if closeable is not None:
            try:
                closeable.close()
            except:
                log.exception("Error closing left-over SQL cursor in WFS service.")

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
# This list a synthesis of this geometry type in
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
        
        model = ft.model.model_class()
        
        if model is None:
            
            with connection.cursor() as cur:
                cur.execute(ft.query)
        
                for colinfo in cur.description:
                    
                    ft.xml += '<xsd:element name="'
                    
                    if _is_geom_column(colinfo):
                        
                        ft.xml += 'geometry" type="gml:GeometryAssociationType"/>'
                    else:
                        ft.xml += colinfo[0] + '" type="xsd:string"/>'
        
        fields = model._meta.fields
        for field in fields:
            if len(ft.fields) == 0 or field.name in ft.fields.split(","):
                ft.xml += '<xsd:element name="'
                if hasattr(field, "geom_type"):
                    
                    gmlType = GML_GEOTYPES.get(field.geom_type,"gml:PointPropertyType")
                    ft.xml += 'geometry" type="%s"/>' % gmlType
                else:
                    ft.xml += field.name + '" type="xsd:string"/>'

def get_feature_from_parameter(parameter):
    '''
    Split a parameter name given as featurename.id into
    a pair (featurename,id)
    :param parameter: A featurename dot id string.
    '''
    dot = parameter.index(".")
    
    return (parameter[:dot],int(parameter[dot+1:]))

class RelatedJsonIterator:
    '''
        This iterator renders a list of related DB objects::

        :ivar model: A model instance describing the feaures fto be rendered.
        :ivar feature_iter: An iterator returning the objects to be renderd as JSON objects.
    '''
    
    def __init__(self,model,feature_iter):
        self.model = model
        self.feature_iter = feature_iter
        
    def __iter__(self):

        yield '{"type":"RelationCollection","objects":['
        
        nfeatures = 0
        sep = ""
        
        for feature in self.feature_iter:
            
            props = {}
            
            for field in self.model._meta.get_fields():
                if field.concrete and not field.is_relation:
                    props[field.name] = getattr(feature, field.name)

            yield '%s%s'%(sep,json.dumps(props,cls=DecimalEncoder))
            sep = ","
            nfeatures += 1
        
        yield '],"totalObjects":%d}'%nfeatures

@csrf_exempt
def related_handler(request,service_id):

    featureid = request.GET.get("id")
    field_name = request.GET.get("field")
    
    typen,fid = get_feature_from_parameter(featureid)
    
    service = Service.objects.get(id=service_id)
    
    ft = service.featuretype_set.get(name__iexact=typen)

    model =  ft.model.model_class()
    
    relation_field = model._meta.get_field(field_name)
    
    kwargs = { relation_field.remote_field.name + "_id" : fid }
    
    related_model = relation_field.target_field.model
    
    related_objs = related_model.objects.filter(**kwargs)
    
    return StreamingHttpResponse(streaming_content=RelatedJsonIterator(related_model,related_objs),content_type="application/json")

    
