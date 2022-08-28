'''
Functions to be evaluated in query json structures.
'''

import json
import math
from datetime import datetime

FUNCTION_KEY = '__function__'

context = {
    "current_datetime":          lambda: datetime.now(),
    "current_timestamp_millis":  lambda: math.floor(datetime.now().timestamp() * 1000),
    "current_timestamp_seconds": lambda: datetime.now().timestamp(),
}

def evaluate_functions(dct,cache):
    
    if  FUNCTION_KEY in dct:
        
        name = dct[FUNCTION_KEY]
        func = context.get(name)
        
        if func is None:
            raise ValueError("Unsupported function [%s] in __function__ query dictionary.")
        
        ret = cache.get(name)
        if ret is None:
            ret = func()
            cache[name] = ret
        
        return ret
    
    return dct

def parse_query(query):
    '''
    Parse a JSON formatted django query.
    Dictionaries like ``{"__function__": "current_timestamp_millis"}`` are evaluated
    as a call to the functions defined in ``context``
    
    :param query: A json-formatted query string.
    :return: A dictionary with kwargs for filter() of the django wuery API.
    '''
    cache = {}
    
    return json.loads(query,object_hook=lambda dct: evaluate_functions(dct,cache))
