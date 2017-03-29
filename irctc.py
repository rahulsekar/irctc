#!/usr/bin/python

import sys
import time
import webbrowser
import random
import re

DEBUG = False
import utils

class TktBooker:

    login_URI   = 'https://www.irctc.co.in/cgi-bin/bv60.dll/irctc/services/login.do'
    planner_URI = ''
    session     = ''
    avail_URI   = '../booking/PlannerAjaxAction.do?' #SessionID, EngineID and Time
    booking_URI = '../booking/bookticket.do?click=true'
    captcha_URI = '../recaptcha/GenCaptchaImage.jsp?' # random(), SessionID

    trvl_details  = { 'date':'', 'from':'', 'to':'', 'tickettype':'', 'quota':'', 'train/class':'' }
    pass_details  = { 'name':'',
                      'age':'',
                      'sex':'',
                      'berthpreference':'',
                      'foodpreference':'',
                      'idcardtype':'',
                      'idcardno':'' }
    login_details = { 'username': '', 'password': '' }

    trains = {}

    ########
    ##### Load the details from file
    ########
    def load_travel_details( self, filename = '' ):
        
        print 'Loading details...',

        if filename == '':
            print 'No Input, exiting.'
            sys.exit(0)
        else:
            f    = open( filename, 'r' )
            data = f.read()
            data = re.split( "[\r\n]+", data )
            f.close()
            
        for line in data:

            key  = line.split( ':' )[0].strip().lower().replace( ' ', '' )

            if key == '' or key[0] == '#':
                continue
            
            val  = line.split( ':' )[1].strip()
            
            if key in self.trvl_details:
                self.trvl_details[ key ] = val
            elif key in self.pass_details:
                self.pass_details[ key ] = val
            elif key in self.login_details:
                self.login_details[ key ] = val
                
        tcs = self.trvl_details[ 'train/class' ]
        tcs = [ tc.strip() for tc in tcs.split( ',' ) ]
        self.trvl_details[ 'train/class' ] = tcs

        print 'OK'

    ########
    ##### Login
    ########
    def login( self, attempts = 1 ):

        if attempts <= 0:
            print 'Unable to login, exiting'
            sys.exit( 0 )
        
        login_dict = { 'userName' : self.login_details[ 'username' ],
                       'password' : self.login_details[ 'password' ],
                       'forwordType' : 'planner' }
        
        #print 'Requesting login page...',
        #sys.stdout.flush()
        #l_form = utils.http_get( self.login_URI )
        #print 'OK'
        
        #login_form   = utils.parse_form( l_form, 'LoginForm', [] )
        #print login_form
        
        login_form = {}
        for key in login_dict:
            login_form[ key ] = login_dict[ key ]
            
        print 'Logging in as', login_form[ 'userName' ] + '...',# url, page,#l_msg
        sys.stdout.flush()

        ret = utils.http_post( self.login_URI,
                               utils.urlencode_form( login_form ),
                               'application/x-www-form-urlencoded' )
                
        if ret.find( 'BookTicketForm' ) != -1:
            print 'OK'
        elif ret.find( 'Invalid Username or Password' ) != -1:
            print 'Invalid Username or Password.'
        else:
            print 'FAILED'
            self.login( attempts - 1 )

        self.session    = utils.parse_form( ret, 'BookTicketForm' )[ '_submit_' ].split( '?' )[1]
        self.avail_URI += self.session + '&ax=' + str( int( time.time() * 1000 ) )

        return ret


    ########
    ##### Fill and submit the planner form and get the list of trains
    ########
    def submit_planner_form( self, planner_page ):

        planner_dict = { 'stationFrom'  : self.trvl_details[ 'from' ],
                         'stationTo'    : self.trvl_details[ 'to' ],
                         'JDatee1'      : self.trvl_details[ 'date' ],
                         'ticketType'   : self.trvl_details[ 'tickettype' ],
                         'quota'        : self.trvl_details[ 'quota' ],
                         'submitClicks' : '1' }

        planner_dict[ 'day' ]   = planner_dict[ 'JDatee1' ].split('/')[0]
        planner_dict[ 'month' ] = planner_dict[ 'JDatee1' ].split('/')[1]
        planner_dict[ 'year' ]  = planner_dict[ 'JDatee1' ].split('/')[2]
#        planner_dict[ 'screen' ]       = 'trainsFromTo' 

        self.planner_form = utils.parse_form( planner_page, 'BookTicketForm', [] )

        for key in planner_dict:
            self.planner_form[ key ] = planner_dict[ key ]
            
        #DEBUG=True
        print 'Fetching trains list...',
        sys.stdout.flush()
        trains_page = utils.http_post( self.planner_form[ '_submit_' ],
                                       utils.urlencode_form( self.planner_form ),
                                       'application/x-www-form-urlencoded',
                                       self.planner_form[ '_submit_' ] )
        print 'OK'
        #DEBUG=False

        return trains_page

    ########
    ##### Extract train information from trains list
    ########
    def extract_trains_info( self, trains_page ):
        
        idx_map = [ 'trainNo',
                    'trainName',
                    'boardPoint',
                    'departure',
                    'destStation',
                    'arrival',
                    'runsOn',
                    'trainType',
                    'notStrTrn',
                    'clss' ]
        
        trains_page = trains_page[ trains_page.find( "trainList['0']['0'] = " ):]
        ret         = {}
        
        for i in range(100):
            if trains_page.find( "trainList['" + str(i) + "']['9'] = " ) != -1:

                trainNo = ''
                
                for j in range( len( idx_map ) ):
                    
                    toFind = "trainList['" + str(i) + "']['" + str(j) + "'] = "
                    pos    = trains_page.find( toFind )
                    
                    if pos != -1:
                        val = trains_page[ pos + len( toFind ):].split(';')[0].replace( "'", "" )
                    else:
                        print 'Some error occured in extracting trains list: toFind =', toFind, ', exiting.'
                        sys.exit(0)

                    if j == 0:
                        ret[ val ] = { idx_map[j] : val }
                        trainNo    = val
                    else:
                        ret[ trainNo ][ idx_map[j] ] = val

        self.trains = ret

        return ret

    ########
    ##### Check availabilty for train/class
    ########
    def check_avail( self, attempts = 5 ):
        
        for option in self.trvl_details[ 'train/class' ]:
            
            trainNo = option.split('/')[0]
            classCode = option.split('/')[1]
            
            if ( trainNo in self.trains ) == False :
                print 'Train number', trainNo, 'is not listed.'
                continue
            
            if self.trains[ trainNo ][ 'clss' ].find( classCode ) == -1:
                print self.trains[ trainNo ][ 'trainName' ], '(' + trainNo + ')', 'does not have class', classCode
                continue
            
            msg = self.session + '&trainTo=true&AVaction=true'
            msg += '&hdnTrnNo=' + trainNo
            msg += '&hdnDay=' + self.trvl_details[ 'date' ].split( '/' )[0]
            msg += '&hdnMonth=' + str(int(self.trvl_details[ 'date' ].split( '/' )[1]))
            msg += '&hdnYear=' + self.trvl_details[ 'date' ].split( '/' )[2]
            msg += '&hdnClasscode=' + classCode
            msg += '&fromStation=' + self.trvl_details[ 'from' ]
            msg += '&toStation=' + self.trvl_details[ 'to' ]
            msg += '&hdnQuota=' + self.trvl_details[ 'quota' ]
            msg += '&service=avail'
        
            att = attempts
            while att > 0:

                print 'Checking availability in', self.trains[ trainNo ][ 'trainName' ], '(' + trainNo + '),', classCode + '...',
                sys.stdout.flush()
                avail = utils.http_post( self.avail_URI + '&ax=' + str( int( time.time() * 1000 ) ),
                                         msg,
                                         'application/x-www-form-urlencoded',
                                         self.planner_form[ '_submit_' ],
                                         True )
                if avail.find( '&' ) == -1:
                    print 'FAILED'
                    att -= 1
                    print avail
                    continue
                
                att    = 0
                status = avail.split('|')[0].split('&')[1].split('<')[0]
                
                print status
                
                if status.find( 'AVAILABLE' ) != -1:
                    return option

            if avail.find( '&' ) == -1:
                print 'Unable to check availability, giving up!'
                sys.exit(0)
            
        print 'None of the options were available, exiting.'
        sys.exit(0)

    ########
    ##### Submit the train/class option and get the booking page
    ########
    def submit_option( self, option ):
        
        trainNo   = option.split('/')[0]
        classCode = option.split('/')[1]
        keys      = [ 'trainNo',
                      'trainName',
                      'trainType',
                      'departure',
                      'arrival',
                      'boardPoint',
                      'destStation',
                      'runsOn',
                      'notStrTrn' ]
        
        book_form  = self.planner_form
        book_form[ 'classCode' ] = classCode
        
        for key in keys:
            book_form[ key ] = self.trains[ trainNo ][ key ]
            
        book_form[ 'submitClicks' ] = '2'
        book_form[ 'screen' ]       = 'bookTicket'
        book_form[ 'counterAvail' ] = '0'

        #book_form += '&userType=0'
        #book_form += '&dayfravail=' + self.trvl_details[ 'date' ].split('/')[0]
        #book_form += '&monthfravail=' + self.trvl_details[ 'date' ].split('/')[1]
        #book_form += '&yearfravail=' + self.trvl_details[ 'date' ].split('/')[2]

        print 'Requesting booking page...',
        sys.stdout.flush()
        booking_page = utils.http_post( self.booking_URI,
                                        utils.urlencode_form( book_form ),
                                        'application/x-www-form-urlencoded',
                                        self.planner_URI )
        print 'OK'
        return booking_page

    ########
    ##### Display the captcha image in the webbrowser and
    ##### get text from stdin ( for now :[ )
    ########
    def get_captcha( self ):
        
        rand = random.random()
        link = self.captcha_URI + str( rand ) + '&' + self.session
        
        print "Downloading captcha image...",
        sys.stdout.flush()
        img  = utils.http_get( link, self.booking_URI )
        print 'OK'

        f    = open( 'captcha.png', 'wb' )
        f.write( img )
        f.close()
        
        webbrowser.open( 'captcha.png' )

        return raw_input( 'Captcha text: ' )

    ########
    ##### Fill and submit the booking form and get the payment page
    ########
    def submit_booking_form( self, booking_page ):
        
        booking_dict = { 'passengers[0].passengerName': self.pass_details[ 'name' ],
                         'passengers[0].passengerAge': self.pass_details[ 'age' ],
                         'passengers[0].passengerSex': self.pass_details[ 'sex' ][0].lower(),
                         'passengers[0].berthPreffer': self.pass_details[ 'berthpreference' ],
                         'passengers[0].foodPreffer': self.pass_details[ 'foodpreference' ],
                         'passengers[0].idCardType' : self.pass_details[ 'idcardtype' ],
                         'passengers[0].idCardNo'   : self.pass_details[ 'idcardno' ],
                         'captchaImage': self.get_captcha(),
                         'submitClicks': '3',
                         'resvUpto': self.trvl_details[ 'to' ],
                         'garibrath': 'false',
}
    
        booking_form = utils.parse_form( booking_page, 'BookTicketForm' )
#        print booking_dict
        for key in booking_dict:
            if key in booking_form:
                booking_form[ key ] = booking_dict[ key ]
            
            
        print 'Sending passenger details...',
        sys.stdout.flush()
        confirm_page = utils.http_post( booking_form[ '_submit_' ],
                                        utils.urlencode_form( booking_form ),
                                        'application/x-www-form-urlencoded',
                                        self.booking_URI )
        print 'OK'

        return confirm_page

    ########
    ##### Confirm booking details
    ########
    def submit_confirm_form( self, confirm_page ):
    
        confirm_dict = { 'submitClicks': '5',
                         'screen'      : 'bankpage' }
                         
        confirm_form = utils.parse_form( confirm_page, 'BookTicketForm' )

        for key in confirm_dict:
            confirm_form[ key ] = confirm_dict[ key ]
        
        print 'Confirming booking details...',
        sys.stdout.flush()
        bank_page     = utils.http_post( confirm_form[ '_submit_' ],
                                        utils.urlencode_form( confirm_form ),
                                        'application/x-www-form-urlencoded',
                                        self.booking_URI )
        print 'OK'
        return bank_page

    ########
    ##### Choose the bank
    ########
    def submit_bank_selection( self, bank_page ):

        CKFARE    = ''
        TatkalOpt = ''
        if self.trvl_details[ 'quota' ] == 'CK':
            CKFARE = 'CKFARE'
            TatkalOpt = 'Y'
        
        bank_dict = { 'paymentMode': '0',
                      'pgType': '1',
                      'gatewayID': '1',
                      'buyTicket': '0',
                      'screen': 'paymnt',
                      'CKFARE': CKFARE,
                      'TatkalOpt': TatkalOpt,
                      'submitClicks': '6',
                      'gatewayIDV': 'on',
                      'Submit': '' }

        bank_form = utils.parse_form( bank_page, 'BookTicketForm' )

        for key in bank_dict:
            bank_form[ key ] = bank_dict[ key ]
        
        print 'Selecting bank...',
        print bank_form
        paymnt_page = utils.http_post( bank_form[ '_submit_' ],
                                       utils.urlencode_form( bank_form ),
                                       'application/x-www-form-urlencoded',
                                       bank_form[ '_submit_' ] )
        print 'OK'
                                     
        return paymnt_page

########
##### main
########
def main():
    MyBooker  = TktBooker()
    
    if len( sys.argv ) > 1:
        MyBooker.load_travel_details( sys.argv[ 1 ] )
    else:
        MyBooker.load_travel_details( )
        
    planner_page = MyBooker.login()
    trains_page  = MyBooker.submit_planner_form( planner_page )
    trains       = MyBooker.extract_trains_info( trains_page )
    option       = MyBooker.check_avail()
    booking_page = MyBooker.submit_option( option )
    confirm_page = MyBooker.submit_booking_form( booking_page )
    bank_page    = MyBooker.submit_confirm_form( confirm_page )
    
    f = open( 'bank_page.html', 'w' )
    f.write( bank_page )
    f.close()
    webbrowser.open( 'bank_page.html' )
        
    #paymnt_page  = MyBooker.submit_bank_selection( bank_page )
    #f = open( 'paymnt_page.html', 'w' )
    #f.write( paymnt_page )
    #f.close()

main()
