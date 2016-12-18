'''

  SQL utilities base on the sqlparser library.

'''

from six import string_types
from sqlparse import parse, tokens, sql

def parse_single(sql):
    
    statements = parse(sql)
    
    if len(statements) != 1:
        raise ValueError("String [%s] contains multiple SQL statements."%sql)
    
    return statements[0]

def append_token(tokenlist,token):
    token.parent = tokenlist
    tokenlist.tokens.append(token) 

def get_identifiers(select):

    identifiers = select.token_matching(lambda x: isinstance(x,sql.IdentifierList),0)
    
    if identifiers is None:
        raise ValueError("Query [%s] does not contain an identifier list."%(select,))

    return identifiers

def find_identifier(identifiers,alias):

    for identifier in identifiers.get_identifiers():
        if identifier.get_name() == alias:
            return identifier
 
    raise ValueError("Query [%s] does not contain an identifier with alias [%s]."%(identifiers.parent,alias))

def replace_identifier(identifiers,original,replacement):

    identifiers.insert_after(original,replacement)
 
    identifiers.tokens.remove(original)

def bare_identifier(identifier):
    '''
    Copy an identifier without any aliases.
    :param identifier: An identifier to copy.
    '''
    itokens = []
    for token in identifier.tokens:
        if token.ttype in (tokens.Name,tokens.Punctuation):
            itokens.append(sql.Token(token.ttype,token.value))
        else:
            break
    return sql.Identifier(itokens)
    

def build_comparison(identifier,operator):
    '''
    Build an SQL token representing a comparison ``identifier operator %s``
    
    :param identifier: An identifier previously found by calling ``find_identifier``
    :param operator: An operator like =, <, >=, ...
    '''
    
    return sql.Comparison([bare_identifier(identifier),
                           sql.Token(tokens.Whitespace," "),
                           sql.Token(tokens.Comparison,operator),
                           sql.Token(tokens.Whitespace," "),
                           sql.Token(tokens.Wildcard,"%s")])

def build_function_call(function,identifier,num_params=1,add_alias= False):
    '''
     Build an SQL token representing ``function(identifier,%s,...)``
     
    :param function: The function name to generate
    :param identifier: An identifier previously found by calling ``find_identifier``
    :param num_params: The number of additional ``%s`` parameters to add.
    :param add_alias: If True, add an eventual alias for using the function call in
                      a select identifier list.
    '''
    
    identifiers = [bare_identifier(identifier)]
    
    for i in range(0,num_params):  # @UnusedVariable
        identifiers.append(sql.Token(tokens.Punctuation,','))
        identifiers.append(sql.Token(tokens.Wildcard,"%s"))
    
    ftokens = [sql.Token(tokens.Name,function),
               sql.Parenthesis([sql.Token(tokens.Punctuation,'('),
                                sql.IdentifierList(identifiers),
                                sql.Token(tokens.Punctuation,')')
                                ])
               ]
     
    if add_alias:
        alias = identifier.get_alias()
        
        if alias is not None:
            ftokens.append(sql.Token(tokens.Whitespace,' '))
            ftokens.append(sql.Token(tokens.Keyword,'AS'))
            ftokens.append(sql.Token(tokens.Whitespace,' '))
            ftokens.append(sql.Token(tokens.Name,alias))
    
    
    return sql.Function(ftokens)

def add_condition(select,condition):
    
    if isinstance(condition,string_types):
        condition = parse_single(condition)
    
    where = select.token_matching(lambda x: isinstance(x,sql.Where),0)

    if where is None:
        
        where = sql.Where([sql.Token(tokens.Keyword,"where"),sql.Token(tokens.Whitespace,' ')])
        
        order = select.token_matching(lambda x: x.ttype==tokens.Keyword and x.value=='order',0)
        
        if order is None:
            append_token(select,sql.Token(tokens.Whitespace," "))
            append_token(select,where)
        else:
            select.insert_before(order,where)
        
    else:
        append_token(where,sql.Token(tokens.Whitespace," "))
        append_token(where,sql.Token(tokens.Keyword,"and"))
        append_token(where,sql.Token(tokens.Whitespace," "))
    
    for token in condition.tokens:
        append_token(where,token)
