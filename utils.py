#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Copyright © 2013, W. van Ham, Radboud University Nijmegen
This file is part of Sleelab.

Sleelab is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Sleelab is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Sleelab.  If not, see <http://www.gnu.org/licenses/>.
'''

from __future__ import print_function
import os, time, logging
""" Log output to both stdout and a file. If a directory "log" exists, it is using for the logfiles."""
def openLog(fileName=""):
	if fileName == "":
		directory = ""
		if os.path.isdir('log'):
			directory = 'log/'
		fileName="{}{}.dat".format(directory, time.strftime('%Y-%m-%dT%H.%M.%S')) # MS Windows does not allow '-'
	logger = logging.getLogger()
	logger.setLevel(logging.DEBUG)
	handler = logging.FileHandler(fileName)
	handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
	logger.addHandler(handler)
	logging.info("open logfile: {}".format(fileName))

