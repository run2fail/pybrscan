'''
Provides the PyBrScan class that implements the periodic (re-)registration at
the scanner device and listens for incoming commands that will then trigger
a scan.
'''

from pysnmp.entity.rfc3413.oneliner import cmdgen
from pysnmp.proto import rfc1902
import os
import getpass
import netifaces
import threading
import time
import socket
import re
import sane
import datetime
import configparser
import select
import sys

class PyBrScan(object):
    ''' Implements a multi-threaded daemon to interact with the scanner device '''

    def __init__(self, ini, logger):
        ''' Initialize the PyBrScan instance

        :param ini: ini file with the configuration
        :param logger: logging instance
        '''
        self.ini = ini
        self.config = None
        self.logger = logger
        self.parse_ini()
        self.stop = False
        self.register_thead = threading.Thread(target=self.register)
        self.listen_thread = threading.Thread(target=self.listen)

    def shutdown(self, message, code):
        ''' Stop the daemon and its threads '''
        self.logger.info('Daemon is stopping: %s', code)
        self.stop = True
        self.logger.debug(message)

    def run(self):
        ''' Start the daemon and its threads '''
        self.logger.info('Starting daemon')
        self.register_thead.start()
        self.listen_thread.start()
        while True:
            self.logger.debug('Main thread still running')
            time.sleep(5)

    def register(self):
        ''' Periodically register this host at the scanner '''
        printer_addr = self.config['General']['printer_addr']
        printer_port = self.config['General'].get('printer_port', '61')
        port = self.config['General'].get('port', '54925')
        user = self.config['General'].get('user', getpass.getuser())
        iface = self.config['General'].get('iface', 'wlan0')
        host = netifaces.ifaddresses(iface)[netifaces.AF_INET][0]['addr']
        duration = int(self.config['General'].get('duration', 300))
        sleep = int(self.config['General'].get('register', 30))

        def register_loop():
            ''' Takes care of the registration at the scanner device '''
            oid = '1.3.6.1.4.1.2435.2.3.9.2.11.1.1.0'
            msg_format = 'TYPE=BR;BUTTON=SCAN;USER="{user}";FUNC={func};HOST={host}:{port};APPNUM={appnum};DURATION={duration};BRID={brid};'

            values = list()
            for func, num in [('IMAGE', 1), ('EMAIL', 2), ('OCR', 3), ('FILE', 5)]:
                val_ascii = msg_format.format(
                    user=user, func=func, host=host, port=port,
                    appnum=num, duration=duration, brid='')
                self.logger.debug('Registration string: %s', val_ascii)
                val_octet = rfc1902.OctetString(val_ascii)
                values.append((oid, val_octet))

            cmd_gen = cmdgen.CommandGenerator()
            self.logger.debug('Registering via SNMP')
            error_indication, error_status, error_index, var_binds = cmd_gen.setCmd(
                cmdgen.CommunityData('internal'),
                cmdgen.UdpTransportTarget((printer_addr, printer_port)),
                *values
            )

            if error_indication:
                self.logger.error('SNMP registration problem: %s', error_indication)
            elif error_status:
                self.logger.error('%s at %s', error_status.prettyPrint(), error_index and var_binds[int(error_index)-1] or '?')

        self.logger.info('Starting register loop')
        while not self.stop:
            self.logger.debug('Register thread still running')
            register_loop()
            time.sleep(sleep)
        self.logger.info('Stopped register loop')

    def listen(self):
        ''' Listen on a socket for packets from the scanner '''
        port = int(self.get_conf_val('General', 'port', '54925'))
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('', port))
        sock.setblocking(0)
        seq = -1

        regex_user = r'"(?P<user>[\w\d])+"'
        regex_func = r'(?P<func>\w+)'
        regex_host = r'(?P<host_ip>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(?P<host_port>\d{4,5})'
        regex_seq = r'(?P<seq>\d+)'
        regex_appnum = r'(?P<appnum>\d)'
        regex_regid = r'(?P<regid>\d+)'
        regex = re.compile(r'^.*TYPE=BR;BUTTON=SCAN;USER=' + regex_user + r';FUNC=' + regex_func + r';HOST=' + regex_host + r';APPNUM=' + regex_appnum + r';P1=\d;P2=\d;P3=\d;P4=\d;REGID=' + regex_regid +';SEQ=' + regex_seq + r';$')

        def listen_loop():
            ''' Listen for incoming connections until timeout '''
            ready = select.select([sock], [], [], 10)
            if not ready[0]:
                return
            data, addr = sock.recvfrom(1024)
            printer_addr = socket.gethostbyname(self.get_conf_val('General', 'printer_addr', ''))
            if addr[0] != printer_addr:
                self.logger.warn('Received command from %s but printer address is %s', addr[0], printer_addr)
                return
            if not regex.match(data):
                self.logger.error('Received invalid command: %s' % data)
                return
            self.logger.debug('Received valid command from %s', printer_addr)
            group_dict = match.groupdict()
            self.logger.debug('Parsed message: %s', group_dict)
            msg_seq = int(group_dict['seq'])
            if seq == -1 or msg_seq > seq:
                seq = msg_seq
            else:
                self.logger.warn('received duplicate scanning request, seq=%s', msg_seq)
                return
            msg_func = int(group_dict['func'])
            if msg_func in ['OCR', 'EMAIL']:
                self.logger.warn('OCR and EMAIL is not yet supported, only a scan will be executed')
            self.scan(msg_func)

        self.logger.info('Starting listen loop')
        while not self.stop:
            self.logger.debug('Listen thread still running')
            listen_loop()
        self.logger.info('Stopped listen loop')

    def parse_ini(self):
        ''' Open specified ini file and create ConfigParser instance

        Exits if the ini file does not exist or cannot be read. This shoud not
        happen as the ini file is already parsed in the pybrscan "binary".

        '''
        try:
            with open(self.ini, 'r') as inifile_fd:
                config = configparser.ConfigParser()
                config.readfp(inifile_fd)
        except FileNotFoundError as exception:
            self.logger.error('Could not read ini file: %s\n' % exception)
            sys.exit(1)
        except PermissionError as exception:
            self.logger.error('Could not read ini file: %s\n' % exception)
            sys.exit(1)
        self.config = config

    def get_conf_val(self, func, key, default):
        ''' Get value based on key from the ini file

        Get a value from the ini file based on the key. If the key is not found
        in the specified "func" section, the key is searched in the "General"
        section. If this fails again, the default value is returned.

        :param func: The scanner function [IMAGE, EMAIL, OCR, FILE]
        :param key: The key to get the value
        :param default: Default value
        :returns: Value for the key or default value if not found
        '''
        if func in self.config and key in self.config[func]:
            return self.config[func][key]
        elif key in self.config['General']:
            return self.config['General'][key]
        else:
            self.logger.info('"%s" missing for func=%s, using default: %s', key, func, default)
            return default

    def scan(self, func):
        ''' Start scan process

        Starts a scan proces with the parameters defined for "func" in the ini
        file. In general this function can handle all functions but does not
        run OCR or send any email.

        :param func: The function received from the scanner [IMAGE, EMAIL, OCR, FILE]
        '''
        sane.init()
        # TODO Check if there are actually scanners and get the right one
        scanner = sane.open(sane.get_devices()[0][0])
        scanner.mode = self.get_conf_val(func, 'mode', 'True Gray')
        scanner.resolution = int(self.get_conf_val(func, 'resolution', '300'))
        dst_dir = self.get_conf_val(func, 'dst_dir', '/tmp')
        if not os.path.isdir(dst_dir):
            try:
                os.mkdir(dst_dir, mode=0o750)
            except OSError as exception:
                self.logger.error('Could not create destination directory: %s' % exception)
                return
        fformat = self.get_conf_val(func, 'format', 'pdf')

        self.logger.info('Scanning:\n\tfunc=%s, mode=%s, resolution=%d, dst_dir=%s, format=%s', func, scanner.mode, scanner.resolution, dst_dir, fformat)
        scanned = scanner.scan()
        scanned.save('%s/scan-%s.%s' % (dst_dir, datetime.datetime.today().strftime('%Y-%m-%d_%H:%M:%S'), fformat))
        scanner.close()
