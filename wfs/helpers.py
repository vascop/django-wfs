# -*- coding: utf-8 -*-
'''
Created on 09. Juni 2016

@author: wglas
'''

from __future__ import unicode_literals

from django.utils.encoding import python_2_unicode_compatible

import re
import logging

log = logging.getLogger(__name__)

CRS_URN_REGEX = re.compile("^urn:([a-z]+):def:crs:([a-z]+):([0-9]+\\.[0-9]+(\\.[0-9]+)?)?:([0-9]+|crs84)$")

DEFAULT_EPSG_VERSION="6.9"

@python_2_unicode_compatible
class CRS:
    '''
    Represents a CRS (Coordinate Reference System), which preferably follows the URN format
    as specified by `the OGC consortium`_.

    .. _the OGC consortium: http://www.opengeospatial.org/ogcUrnPolicy
    
    :ivar domain: Either "ogc" or "opengis", whereas "ogc" is highly recommended.
    :ivar authority: Either "OGC" or "EPSG".
    :ivar version: The version of the authorities' SRS registry, which is empty
                or contains two or three numeric components separatedby dots like
                "6.9" or "6.11.9".
    :ivar crsid: A string representation of tje coordinate system reference ID.
                For OGC, only "CRS84" is supported as crsid. For EPSG, this is the
                string formatted CRSID.
    :ivar srid: The integer representing the numeric spatial reference ID as
                used by the EPSG and GIS database backends.
    '''

    def __init__(self,uri):
        '''
        Parse an CRS (Coordinate Reference System) URI, which preferably follows the URN format
        as specified by `the OGC consortium`_ and construct a new CRS instance.
    
        .. _the OGC consortium: http://www.opengeospatial.org/ogcUrnPolicy
        
        :param uri: A URI in OGC URN format or a legacy CRS URI. An int
                    instance repreenting a numeric SRID may also passed in,
                    which is equivalent to specifyin  an URN in the format
                    "urn:ogc:def:crs:EPSG:6.9:<SRID>" 
        '''
        try:
            legacy_found = False
        
            if type(uri) == int:
                self.crsid = str(uri)
                self.srid = uri
                legacy_found = True
            else:
                luri = uri.lower()
                
                r = CRS_URN_REGEX.match(luri)
            
                if r:
                    self.domain = r.group(1)
                
                    if self.domain != "ogc" and self.domain != "opengis":
                        raise SyntaxError("CRS URI [%s] contains unknown domain [%s]"%(uri,self.domain))
                
                    self.authority = r.group(2).upper()
                    self.version = r.group(3)
                
                    if self.authority == "EPSG":
                        self.crsid = r.group(5)
                        self.srid = int(self.crsid)
                
                    elif self.authority == "OGC":
                        self.crsid = r.group(5).upper()
                        
                        if self.crsid != "CRS84":
                            raise SyntaxError("OGC CRS URI from [%s] contains unknown id [%s]"%(uri,id))
                    
                        self.srid = 4326
                    
                    else:
                        raise SyntaxError("CRS URI [%s] contains unknown authority [%s]"%(uri,self.authority))
                    
                    return
                    
                for head in ("epsg:","http://www.opengis.net/def/crs/epsg/0/","http://www.opengis.net/gml/srs/epsg.xml#"):
                
                    if luri.startswith(head):
                        self.crsid = luri[len(head):]
                        self.srid = int(self.crsid)
                        legacy_found = True
                        break
    
            if legacy_found:    
                self.authority = "EPSG"
                self.domain = "ogc"
                self.version = DEFAULT_EPSG_VERSION
            else:
                raise SyntaxError("Unknown CRS URI [%s] specified"%uri)
        
        except ValueError:
            raise SyntaxError("CRS URI [%s] contains an alphanumeric string where an SRID number is expected."%uri)            
    
    def get_legacy(self):
        '''
        Return a legacy string in the format "EPSG:<srid>"
        '''
        return "EPSG:%d" % self.srid
    
    def get_urn(self):
        '''
        :return: The OGC URN corresponding to this CRS.
        '''
        return "urn:%s:def:crs:%s:%s:%s"%(self.domain,self.authority,self.version,self.crsid)
    
    def __str__(self):  # @DontTrace
        '''
        Equivalent to get_urn().
        '''
        return self.get_urn()

WGS84_CRS = CRS(4326)
