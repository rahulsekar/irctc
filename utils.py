#!/usr/bin/python

import sys, socket, urllib#, xml.dom.minidom

DEBUG    = False
READ_LEN = 1200

def get_socket( URL ):
    s = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
    s.connect( ( URL, 443 ) )
    sslSock = socket.ssl( s )
    return sslSock

def link_split( link ):
    
    if link.find( '../' ) == 0:
        link = '/'.join( BASE_URI.split( '/' )[:-2] ) + '/' + '/'.join( link.split( '/' )[1:] )

    if link.find( 'http://' ) != 0 and link.find( 'https://' ) != 0:
        return ( '', link )

    host = link.split( '/' )[2]
    page = link[link.find( host ) + len( host ):]

    return ( host, page )

def urlencode_form_str( string ):
    
    ret   = ''
    parts = string.split( '&' )
    for part in parts:
        if len( ret ):
            ret += '&'
        ret += urllib.quote_plus( part.split('=')[0] )
        ret += '='
        ret += urllib.quote_plus( part.split('=')[1] )
        
    return ret
    
def urlencode_form( form ):
    
    parts = []
    for key in form:
        if key != '_submit_':
            parts.append( urllib.quote_plus( key ) + '=' + urllib.quote_plus( form[ key ] ) )
        
    return '&'.join( parts )
    
#read response from the socket
def http_read( sock ):
    
    buf = sock.read( READ_LEN )

    if DEBUG:
        print 'http_read:', buf
        
    #header and body
    idx     = buf.find( '\r\n\r\n' )
    header  = buf[:idx]
    body    = buf[idx+4:]
    toread  = int( header[ header.find( "Content-Length:" )+15:].split('\r\n')[0] )
    toread -= len( body )

    if header.split()[1] == '200': # OK
        while toread > 0:
            buf     = sock.read( min( READ_LEN, toread ) );
            toread -= len( buf )
            body   += buf;
            
    elif header.split()[1] == '302': # Moved Temporarily
        URI = header[ header.find( 'Location: ' ) + 10: ].split()[0]
#        print "Redirecting...", URI
        return http_get( URI )

    return body

def http_post( URI, msg, ctype, referer = '',ajax = False, debug = False ):

    ( URL, page ) = link_split( URI )
    sock          = get_socket( URL )

    header  = 'POST ' + page + ' HTTP/1.0\r\n'
    header += 'Host: ' + URL + '\r\n'
    header += 'Content-Type: ' + ctype + '\r\n'
    header += 'Content-Length: ' + str( len( msg ) ) + '\r\n'
    header += 'User-Agent: Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.97 Safari/537.11' + '\r\n'

    if len( referer):
        header += 'Referer: ' + referer + '\r\n'

    if ajax:
        header += 'X-Prototype-Version: 1.5.1.2' + '\r\n'
        header += 'X-Requested-With: XMLHttpRequest' + '\r\n'

    header += '\r\n'
    
    if debug:
        print 'Posting:', header, msg

    sock.write( header + msg )

    ret = http_read( sock )

    return ret

def http_get( URI, referer = '' ):

    ( URL, page ) = link_split( URI )
    sock          = get_socket( URL )
    header  = 'GET ' + page + ' HTTP/1.1\r\n'
    header += 'Host: ' + URL + '\r\n'

    if len( referer):
        header += 'Referer: ' + referer + '\r\n'

    sock.write( header + '\r\n' )

    global BASE_URI
    BASE_URI = 'https://' + str( URL + page ).split( '?' )[0]

    return http_read( sock )

def form_elements( page ):

    ret = []
    
    for ( start, end ) in [ ( '<input ', '>' ), ( '<select ', '</select>' ) ]:
        
        page_lower = page.lower()
        page_      = page

        idx        = page_lower.find( start )
        while idx != -1:
            idx       += len( start )
            page_lower = page_lower[idx:]
            page_      = page_[idx:]

            e_idx      = page_lower.find( end )
            elem       = page_[:e_idx]

            ret.append( elem )
            idx = page_lower.find( start )
    
    return ret

def get_value_for_key( string, key, caseSensitive = False ):

    if caseSensitive == False:
        idx = string.lower().find( key.lower() )
    else:
        idx = string.find( key )
    
    if idx == -1:
        return ''

    #key="value"...
    #key='value'...
    #key = "value"...
    #key = 'value'...

    idx += len( key ) #skip the key

    while string[idx] != '=': #find the =
        idx += 1

    idx += 1 #skip the =

    while string[idx] == ' ': #skip the spaces
        idx += 1

    ret = ''

    if string[idx] == '"' or string[idx] == "'":
        idx += 1
        while string[idx] !='"' and string[idx] != "'":
            ret += string[idx]
            idx += 1
    else:
        while string[idx] != ' ' and string[idx] != '\r':
            ret += string[idx]
            idx += 1

    return ret
            
def parse_form( msg, formname, fields = [] ):

    #    dom = xml.dom.minidom.parseString( msg );
    #    print dom;

    if msg.find( formname ) == -1:
        print formname, 'not available in page'
        return {}

    msg  = msg[ msg.find( '<form '):msg.find('</form>')];

    if DEBUG:
        print msg

    ret    = { "_submit_": get_value_for_key( msg, 'action' ) }
    inputs = form_elements( msg )

    for input in inputs:
        
        # name="blah" -> blah
        key = get_value_for_key( input, 'name' )
        
        if key == '':
            continue

        if key == 'Submit':
            continue
        
        ret[ key ] = get_value_for_key( input, 'value' )
        
    return ret
