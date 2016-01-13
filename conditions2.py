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
import sys, math, csv, re, os, time, numpy as np, logging
import root

class Conditions():
	"""
	This class contains all the conditions used in an entire experiment. Conditions
	can be translated into trials. A trial is a dictionary where a number of keys
	have a value, that can either be an integer number, a real number or a set of 
	three numbers reprecenting a color. If a repsonse is given, the current trial
	gets an extra dictionary entry, called response, containing this reponse. 
	Subsequently the next condition is expanded into a new trial.
	
	All conditions in an experiment have the same keys. In additions to the user 
	chosen keys there are a few special keys:
	nTrial: number times that this conditons is translated into a trial
	response: 1 for true/indeed larger than/down, 0 for false/ not larger than/ down
	function: functor instance 
	functionKey: key of the value which is to be gotten from 'function'
	"""
	def __init__(self, fileName=None, dataKeys=[]):
		#default trial variables
		self.trial = None
		self.iTrial = 0       # index of current trial, must not be larger than self.nTrial
		self.nTrial = 0       # total number of trials (in all blocks)
		self.nBlock = 1       # number of blocks
		self.pauseBlocks = [] # blocks that start with a pause
		self.saveFile = None  # file to save data to
		self.dataKeys = dataKeys
		self.trial = {}
		
		if fileName:
			self.load(fileName)
		
	def __del__(self):
		# this is not a reliable method, but the alternatives are worse
		if self.saveFile:
			self.saveFile.close()

	def __repr__(self):
		s = ""
		iCondition = 0
		for condition in self.conditions:
			s += "condition {:d}: \n".format(iCondition)
			for key in condition.keys():
				s += "  {:16s}: {}\n".format(key, condition[key])
			iCondition += 1
		return s
		
	def printTrial(self):
		for key in self.trial.keys():
			print ("self.trial keys: {:16s}: {}".format(key, self.trial[key]))
			
	def saveTrial(self, data):
		s = ""
		# the trial itself
		for key in self.keys:
			s += str(self.trial[key])+";\t"
		# the data
		for key in self.dataKeys:
			s += str(self.trial[key])+";\t"
		s += str(data)
		
		self.saveFile.write("{};\t{:14.3f}\n".format(s, time.time()))
		self.saveFile.flush()
		logging.info("#" + ";\t".join(self.keys))
		logging.info(s)
		
	def load(self, fileName, saveFileName = None):
		"""Load new list of conditions. Indicate in dataKeys what data will be added to the trials"""
		
		# open file to save data
		if saveFileName == None:
			if os.path.isdir('data'):
				directory = 'data/'
			saveFileNamefileName="{}{}.dat".format(directory, time.strftime('%Y-%m-%dT%H:%M:%S')) # ISO compliant
			altSaveFileName="{}{}.dat".format(directory, time.strftime('%Y-%m-%dT%H.%M.%S')) #for MS Windows
			try:
				self.saveFile = open(saveFileName, 'wb')
				name = saveFileName
			except Exception as e:
				self.saveFile = open(altSaveFileName, 'wb')
				name = altSaveFileName
		else:
			self.saveFile = open(saveFileName, 'wb')
			name = saveFileName
		logging.info("data file: {}".format(name))

		self.conditions = []
		with open(fileName, 'rb') as csvfile:
			reader = csv.reader(csvfile, delimiter=';', quotechar='"', skipinitialspace=True)
			# read first line
			self.keys = reader.next()
			self.keys[0] = self.keys[0].lstrip('#')
			# write header of data file (continaining the experiment file)
			self.saveFile.write("#" + ";\t".join(self.keys+self.dataKeys) + ";\n")
			logging.debug("keys: "+str(self.keys))
			# read subsequent lines as conditions

			for row in reader:
				# write header of data file (containing the experiment file)
				self.saveFile.write(";\t".join(row)+ "\n")

				# parse row into condition
				condition = {}
				condition['iBlock'] = self.nBlock - 1
				
				if len(row)==1 and row[0] == 'pause': # pause line, new block
					self.pauseBlocks.append(self.nBlock)
					self.nBlock += 1
					continue
				
				if len(row)==0: # empty line, new block
					self.nBlock += 1
					continue
				
				for i in range(len(row)):
					#print ("i: {}".format(i))
					value = row[i]
					
					# parse the various types of values: integer, real, color, function
					#logging.debug("value: {}".format(value))
					if re.match('^[\d\-\+]+$', value): # integer
						#logging.debug("{}: int".format(i))
						condition[self.keys[i]] = int(value)
						#self.parent().log.print("int {}: {}".format(self.keys[i], self.trial[self.keys[i]]))
					elif re.match('^[\d\-\+\.Ee]+$', value): # real
						#logging.debug("{}: float".format(i))
						condition[self.keys[i]] = float(value)
						#self.parent().log.print("float {}: {}".format(self.keys[i], self.trial[self.keys[i]]))
					elif re.match('^\#[0-9A-Fa-f]{6}$', value): # color
						#logging.debug("{}: color".format(i))
						condition[self.keys[i]] = np.array(map(ord, value[1:].decode('hex')), np.float32)/255
						#self.parent().log.print("color {}: {}".format(self.keys[i], self.trial[self.keys[i]]))
					elif 'functionKey' not in condition and re.match('\w+\([\d\-\+\.Ee]+\,\s*[\d\-\+\.Ee]+\)', value): # root finding class
						logging.debug("Old style functor: {}".format(value))
						# set condition.function and condition.functionKey
						m = re.match('(\w+)\(([\d\-\+\.Ee]+)\,\s*([\d\-\+\.Ee]+)\)', value)
						functionString = m.group(1)
						condition['functionKey'] = self.keys[i]
						min = float(m.group(2))
						max = float(m.group(3))
						try:
							condition['function'] = getattr(root, functionString)(min, max)
						except Exception as e:
							logging.error("No root finder named: {}".format(functionString))
							raise e
					elif 'functionKey' not in condition and re.match('[\.\w+]+\(.+\)', value): # root finding class
						logging.debug("New style functor: {}".format(value))
						condition['functionKey'] = self.keys[i]
						condition['function'] = eval("root."+value)
					elif 'iteratorKey' not in condition and re.match('\[.+\]', value): # iterable
						logging.debug("Iterator: {}".format(value))
						condition['iteratorKey'] = self.keys[i]
						condition['iterator'] = eval(value).__iter__()
					elif re.match('^[a-zA-Z0-9]+$', value): # string
						#logging.debug("string: {}".format(value))
						condition[self.keys[i]] = value
					else:
						logging.error("ERROR: could not parse value '{}' in row {}, column {}".format(value, reader.line_num, i))
			
				if 'nTrial' not in condition:
					condition['nTrial'] = 1
				self.nTrial += condition['nTrial']
				condition['iTrial'] = 0 # index of current trial, must not be larger than or equal to condition['nTrial']
				self.conditions.append(condition)
			
		logging.info("load file {} with {} conditions".format(fileName, len(self.conditions)))
		
		self.saveFile.write("## START OF TRIALDATA\n")
			
		self.iCondition = 0
		self.makeTrial()
		

	def addData(self, value, save=True):
		""" testee gives input, process it."""
		if save:
			self.saveTrial(value)
		condition = self.conditions[self.iCondition]
		# if the condition contains a functor which must be updated
		if 'function' in condition:
			condition['function'].addData(value)
	
	def __iter__(self):
		"""iterable with self contained iterator"""
		return self
	def next(self):
		"""return current trial en proceed to next. Implementation of iterator/iterable"""
		if self.iTrial==self.nTrial-1:
			self.iTrial += 1 # allow check while iTrial<nTrial
			raise StopIteration
		elif not hasattr(self, '_notFirstTime'):
			# first trial was expanded in initialization, do not do that again
			self._notFirstTime = True
			return self.trial
		else:
			self.nextTrial()
			return self.trial
		
	def nextTrial(self, data=None):
		"""increment the condition pointer and expand it into a trial. """
		pauseRequest = False
		if data!=None:
			self.addData(data)
			
		if self.iTrial < self.nTrial:
			self.iTrial += 1
		if self.iTrial == self.nTrial:
			print("####################HALT######################")
			return
		self.conditions[self.iCondition]['iTrial'] += 1
		
		# go to next condition if iTrial/nTrial for this condition is larger than average
		#while self.conditions[self.iCondition]['iTrial'] > self.conditions[self.iCondition]['nTrial'] * self.iTrial/self.nTrial:
			#self.iCondition = (self.iCondition + 1) % len(self.conditions)
			
		# go to next block if the number of trials in the block has been reached
		iBlock = self.conditions[self.iCondition]['iBlock']
		while True:
			iTrialBlock = 0 # number of trials finished in current block
			nTrialBlock = 0 # total number of trials in current block
			for c in self.conditions:
				if c['iBlock'] == iBlock:
					iTrialBlock += c['iTrial']
					nTrialBlock += c['nTrial']
			if iTrialBlock == nTrialBlock:
				iBlock += 1
				if iBlock in self.pauseBlocks:
					pauseRequest = True
			else:
				break

		logging.debug("current block: {}, i/n Condition: {}/{}, i/n Block: {}/{}, i/n Total: {}/{}".
			format(iBlock, self.conditions[self.iCondition]['iTrial'], self.conditions[self.iCondition]['nTrial'], iTrialBlock, nTrialBlock, self.iTrial, self.nTrial))
		# go to next condition in block if iTrial/nTrial for this condition is larger than average in block
		while self.conditions[self.iCondition]['iTrial'] > self.conditions[self.iCondition]['nTrial'] * iTrialBlock/nTrialBlock:
			while True: # increase to next condition in same block (may loop)
				self.iCondition = (self.iCondition + 1) % len(self.conditions)
				if self.conditions[self.iCondition]['iBlock'] == iBlock: 
					break

		self.makeTrial() # expand this condition into a trial
		return pauseRequest
		
	def makeTrial(self):
		"""expand current condition into a trial """
		self.trial = self.conditions[self.iCondition]
		extra = ""
		if 'functionKey' in self.trial:
			self.trial[self.trial['functionKey']] = self.trial['function']()
			logging.debug("expanding {}: {}".format(self.trial['functionKey'], self.trial[self.trial['functionKey']]))
			extra = ": {} = {}".format(self.trial['functionKey'], self.trial[self.trial['functionKey']])

		if 'iteratorKey' in self.trial:
			self.trial[self.trial['iteratorKey']] = self.trial['iterator'].next()
			logging.debug("expanding {}: {}".format(self.trial['iteratorKey'], self.trial[self.trial['iteratorKey']]))
			extra = ": {} = {}".format(self.trial['iteratorKey'], self.trial[self.trial['iteratorKey']])
		
		logging.info("expanded condition {}/{} into trial (this condition) {}/{}, trial (total) {}/{}{}".format(
			self.iCondition, len(self.conditions), 
			self.trial['iTrial'], self.trial['nTrial'],  
			self.iTrial, self.nTrial,
			extra))
		#self.printTrial()
		
	def setTrial(self, i):
		self.setCondition(i)
	def setCondition(self, i):
		"""use a condition without incrementing the trial counters"""
		self.iCondition = i
		self.makeTrial()
		
	def getNumber(self, key):
		"get a number from the current trial, defaults to 0"
		try:
			return self.trial[key]
		except:
			logging.error("getNumber could not read key: "+key)
			return 0
			
	def getColor(self, key):
		"get a color from the current trial, defaults to [1,1,1]"
		try:
			return self.trial[key]
		except:
			logging.error("getColor could not read key: "+key)
			return np.array([1.0,1.0,1.0], "f")

	def getString(self, key):
		"get a string from the current trial, defaults to ''"
		try:
			return self.trial[key]
		except:
			logging.error("getString could not read key: "+key)
			return ''
		
def test(x):
	return x*x-2

if __name__ == '__main__':
	logging.basicConfig(level=logging.DEBUG)
	conditions = Conditions()
	if len(sys.argv) > 1:
		conditions.load(sys.argv[1])
	else:
		conditions.load("experiment/two.csv")
		
	print ("######conditions after load: \n{}".format(conditions))
	print ("######run")

	while conditions.iTrial < conditions.nTrial:
		print("{}/{}".format(conditions.iTrial, conditions.nTrial))
		x = conditions.trial['x']
		if x < 1.0:
			print("x: {} ↑".format(x))
		else:
			print("x: {} ↓".format(x))
		conditions.nextTrial(x > 1.0)
		time.sleep(1)
