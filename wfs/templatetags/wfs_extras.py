'''
Created on 08. Juni 2016

@author: wglas
'''
from django import template
from django.utils.html import format_html,mark_safe

register = template.Library()

@register.simple_tag
def gml_feature(ftype,feature):

    xml = mark_safe("")
    for field_name in ftype.fields.split(","):
        if field_name:
            field = ftype.get_model_field(field_name)
            if field:
                if hasattr(field, "geom_type"):
                    if feature.gml:
                        xml += mark_safe("<geometry>" + feature.gml + "</geometry>")
                else:
                    tag = mark_safe(field.name)
                    xml += format_html("<{}>{}</{}>",tag,getattr(feature, field.name),tag)
    
    return xml