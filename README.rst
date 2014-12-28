About pybrscan
===============

This is a simple, python-based reimplementation of the daemon provided by
Brother for their DCP and MFC devices.

I bought a Brother DCP-L2520DW due to its good Linux driver support and because
there were few alternatives available at the time that fulfilled my requirements
(b/w laser, duplex print, scanner, wlan). Everything worked fine but to enable
scan to pc and even scan to email (the DCP-L2520DW somehow does not support
direct sending of scanned documents) you have to run a separate application.
This application registers the computer at the scanner and waits for incoming
connections when the scan button is pressed.

Motivation for the Reimplementation
-----------------------------------

- The provided application was not FOSS
- There was very little documentation
- I don't like running some semi-supported, closed source software with root
  privileges on my computer
- Curiosity how the communication between the computer and scanner works and how
  this may be reimplemented in Python

No reverse engineering has been done. Just the (cleartext) communication over
the network has been analysed.

Features
========

- Can be run as daemon with start, stop, status, restart functionality (thanks
  to the `daemonocle <https://github.com/jnrbsn/daemonocle>`_ module)
- Registers the computer via SNMP at the scanner
- Waits for incoming connections and triggers a scan
- Can be configured in a simple ini file

Usage
=====

Installation
------------

.. code:: bash

   $ ./setup.py install

Running the daemon
------------------

.. code:: bash

   $ pybrscan start --ini conf/pybrscan
   Starting pybrscan ... OK
   $ pybrscan status --ini conf/pybrscan
   pybrscan -- pid: 5206, status: sleeping, uptime: 0m, %cpu: 0.0, %mem: 0.5
   $ pybrscan stop --ini conf/pybrscan
   Stopping pybrscan ... OK

Example ini File
----------------

.. code::

    [General]
    iface=wlan0
    port=54925
    printer_addr=printer
    printer_port=161
    pid=/tmp/pybrscan.pid
    log=/tmp/pybrscan.log
    verbose=True
    register=30
    duration=300

    resolution=300
    mode=True Gray
    dst_dir=/tmp/pybrscan

    [IMAGE]
    mode=24bit Color
    resolution=600
    format=png

    [EMAIL]
    email_mta=sendmail
    email_addr=
    email_port=25
    email_user=
    email_password=

    [OCR]

    [FILE]
    resolution=300
    format=pdf

The ``General`` section contains base configuration but may also define defaults
for keys that may be missing in the function specific sections. They are
normally used for the following tasks

:IMAGE:
    Scan to image, e.g., a ``png`` file. Hence normally a higher resolution,
    color scan

:FILE:
    Usually a scan to a ``pdf`` file, e.g., a letter or invoice you received.
    A average resolution scan in b/w

:OCR:
    Scan and run optical character recognition (OCR). Not fully implemented yet
    (see next section)

:EMAIL:
    Scan and send file via email. Not fully implemented yet
    (see next section)

List of parameters:

:iface:
    Interface to listen for incoming connections. Its IP address is send to the
    scanner for registration.

:port:
    Port to listen on

:printer_addr:
    Address or resolvable hostname of the scanner (its also a printer hence the
    name)

:printer_port:
    Port where the printer is listening for connections

:pid:
    File to write the process ID of the daemon

:log:
    Log file

:verbose:
    Set to True to get more logging output

:register:
    Register at the scanner every x-seconds

:duration:
    Register for this many seconds

:resolution:
    Resolution in DPI for the scan

:mode:
    Scan mode, i.e., the color. For example: "True Gray", "24bit Color". The
    valid values depend on your scanner (check via the ``sane`` module)

:dst_dir:
    Destination directory for the scans.

:format:
    Format of the scan when writing to disk. Must be supported by the ``sane``
    module.


Current State
=============

This is a prototype implementation that works for me but many additional
features are yet to be implemented. Please don't expect timely updates and bug
fixes. Some remarks:

- Currently only support scan to file/image. Selecting OCR or EMAIL on the
  scanner will just result in a scan
- Manual duplex scanning or automatic document feeder (ADF) are not yet
  supported
- I still don't know what all the parameters in the SNMP registration message or
  the message sent to trigger a scan mean
- I don't know if this will work with other models
- Stopping the daemon takes a long time as the threads must first wake up to
  detect the stop command
- The `Python sane module <http://svn.effbot.org/public/pil/Sane/sanedoc.txt>`_
  seems to have been deprecated?!?

License
============

Published under the GPLv3 or later

