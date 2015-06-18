from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.contrib.sites.models import Site
from wfs.models import Service, FeatureType
import json

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
                version = map(int, value.split("."))
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


def getfeature(request, service):
    context = {}
    propertyname = None
    featureversion = None
    maxfeatures = None
    typename = None
    featureid = None
    filtr = None
    bbox = None

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
            bbox = low_value

    if propertyname is not None:
        raise NotImplementedError

    if featureversion is not None:
        raise NotImplementedError

    if filtr is not None:
        raise NotImplementedError

    if bbox is not None:
        raise NotImplementedError

    feature_list = []
    # If FeatureID is present we return every feature on the list of ID's
    if featureid is not None:
        # we assume every feature is identified by its Featuretype name + its object ID like "name.id"
        for feature in featureid.split(","):
            try:
                ftname, fid = get_feature_from_parameter(feature)
            except ValueError:
                return wfs_exception(request, "InvalidParameterValue", "featureid", feature)
            try:
                ft = service.featuretype_set.get(name=ftname)
                flter = json.loads(ft.query)
                try:
                    f = ft.model.model_class().objects.filter(**flter).filter(id=fid).gml()
                    feature_list.append((ft, f[0]))
                except:
                    return wfs_exception(request, "MalformedJSONQuery", "query")
            except FeatureType.DoesNotExist:
                return wfs_exception(request, "InvalidParameterValue", "featureid", feature)
    # If FeatureID isn't present we rely on TypeName and return every feature present it the requested FeatureTypes
    elif typename is not None:
        for typen in typename.split(","):
            try:
                ft = service.featuretype_set.get(name__iexact=typen)
            except FeatureType.DoesNotExist:
                return wfs_exception(request, "InvalidParameterValue", "typename", typen)
            try:
                flter = json.loads(ft.query)
                for i in ft.model.model_class().objects.all().filter(**flter).gml():
                    feature_list.append((ft, i))
            except:
                return wfs_exception(request, "MalformedJSONQuery", "query")
    else:
        return wfs_exception(request, "MissingParameter", "typename")

    context['features'] = features_to_xml(feature_list)
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


def features_to_xml(feature_list):
    for (ftype, feature) in feature_list:
        feature.xml = ""
        for field in feature._meta.fields:
            if len(ftype.fields) == 0 or field.name in ftype.fields.split(","):
                if hasattr(field, "geom_type"):
                    if feature.gml:
                        feature.xml += "<geometry>" + feature.gml + "</geometry>"
                else:
                    feature.xml += u"<{}>{}</{}>".format(field.name, getattr(feature, field.name), field.name)

    return feature_list


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
