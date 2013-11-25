#!/usr/bin/env python
# -*- coding: utf8 -*- 
import os, sys, pypsignifit as psi, csv, signal, argparse, math
from PyQt4.QtCore import *
from PyQt4.QtGui import *
import pyqtgraph as pg, numpy as np, numpy.random


def fit(x, y):
	pass
	## cores (of sigmoid)
	#ab(x, a, b) = (x-a)/b
	## sigmoids
	# logistic(x) = 1/(1+exp(-x))
	## 
	# F(x, a, b) = logistic(core(x, a, b))
	## psi (psychometric curve)
	# psi(x, a, b, gamma, lambda) = gamma + (1 - gamma - lambda) * F(x, a, b)
	#
	# where F = 1/(1+exp(x))
	# a = thresshold rate
	# b = slope
	# gamma = guessing rate, or the lower asymptote
	# lambda = lapsing rate, or the upper asymptote
	
	
# we only use this one f function
def sigmoid(x):
	#return 1/(1+math.exp(-2x)) # logistic, d/dx(0) = .5
	#return .5*(1+math.tanh(x)) # logistic
	return .5*(1+math.erf(x*math.sqrt(math.pi)/2)) # sharper than normal cdf, d/dx(0) = .5
def core(x, a, b):
	return (x-a)/b
def f(x, a, b, g=0.04, l=0.04):
	return g + (1 - g - l) * sigmoid(core(x, a, b))
	
	

class Main(QWidget):
	def __init__(self, args):
		super(Main, self).__init__()
		self.args = args
		#print("dir: "+self.args.directory)
		
		# building the ui
		self.setMinimumSize(600, 400)
		plotWidget = pg.PlotWidget(self)
		self.graph = plotWidget.getPlotItem()
		self.graph.setLabel('bottom', 'stimulus')
		self.graph.setLabel('left', 'response')
		self.graph.showGrid(x=True, y=True)
		self.graph.addLegend()
		#self.text = QLabel("")
		
		vbox = QVBoxLayout()
		#vbox.addStretch(1)
		vbox.addWidget(plotWidget)
		#vbox.addWidget(self.text)
		self.setLayout(vbox)
		self.mtime = 0 # modification time of data file
		self.fileSize = -1 # size of data file
		self.plotList = []
		self.startTimer(1000)
		
	def plot(self, fileName):
		self.graph.clear()
		self.graph.legend.items = []
		self.graph.addLine(y=0.04)
		self.graph.addLine(y=0.96)
		(xDict, yDict, conditions) = readFile(fileName)
		colors=['F00', '0F0', '00F', 'AA0', '0AA', 'A0A']
		for i in range(len(conditions)):
			condition = conditions[i] 
			x = xDict[condition]
			y = yDict[condition]
			#print("c: {}\nx: {}\ny: {}\n".format(condition, x, y))
			data = zip(x, y, [1]*len(x))
			constraints = ( 'unconstrained', 'unconstrained', 'Uniform(0.0399,0.0401)', 'Uniform(0.0399,0.0401)')
			B = psi.BootstrapInference ( data, core='ab', sigmoid='gauss', priors=constraints, nafc=1 )
			print("est: {}, dev: {}".format(B.estimate, B.deviance))
			self.graph.plot(x, y, pen=None, symbolPen={'color': colors[i%6]}, symbolSize=6, antialias=True)
			
			xx = np.linspace(min(x), max(x), 100)
			yy = []
			for p in xx:
				yy.append(f(p,B.estimate[0], B.estimate[1]))
			self.graph.plot(xx, yy, pen={'color': colors[i%6], 'width': 2}, 
				name="{}: {:.3f} +/- {:.3f}".format(condition, B.estimate[0], B.estimate[1]))
		
	
	def timerEvent(self, e):
		"""replot if file has changed """
		if os.path.isfile(self.args.directory):
			fileName = self.args.directory
		else:
			fileName = lastFile(self.args.directory)
		
		mtime = os.path.getmtime(fileName)
		fileSize = os.path.getsize(fileName)
		#print("Most recent file = {}, {}, {}".format(fileName, mtime, fileSize))
		if mtime <= self.mtime and fileSize==self.fileSize:
			return
		#print("File was touched")
		self.mtime = mtime
		self.fileSize = fileSize
		self.plot(fileName)
		
		#self.text.setText("boe")

	def quit(self, signum=None, frame=None):
		print("quitting")
		qApp.quit()

def lastFile(directory=''):
	if directory == '':
		if os.path.isdir('data'):
			directory = 'data'
		else:
			directory = '.'

	dataFiles = sorted([ f for f in os.listdir(directory) if f.endswith('dat')])
	fileName = "{}/{}".format(directory, dataFiles[-1])
	return fileName

def readFile(fileName):
	x = {}
	y = {}
	conditions = []
	with open(fileName, 'r') as f:
		reader = csv.reader(f, delimiter=";", skipinitialspace=True)
		# column headers
		head = [d.lstrip(' \t#') for d in reader.next()]
		while head[-1] == '':
			del(head[-1])
		nColumn = len(head)
		
		# determine column that contains iCconditions
		conditionColumn = -1
		for i in range(len(head)):
			if head[i] == 'iCondition':
				conditionColumn = i
				break
		if conditionColumn==-1:
			print("ERROR: no iCondition column")

		# determine column that contains x (stimulus value)
		xColumn = nColumn-4
		
		# determine column that contains y (response value)
		yColumn = -2
		
		#print("nColumn: {}".format(nColumn))
		#print("head: {}".format(head))
		# burn experiment file header
		while len(head) and len(head)!=1:
			head = reader.next()
		for row in reader:
			row = [d.lstrip() for d in row]
			condition = row[conditionColumn]
			if not x.get(condition):
				x[condition] = []
				y[condition] = []
				conditions.append(condition)
			x[condition].append(float(row[xColumn]))
			y[condition].append(row[yColumn]=='True')
		return tuple([x, y, conditions])


if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument("directory", nargs='?', default="")
	args = parser.parse_args()
	
	a = QApplication(sys.argv)
	w = Main(args)
	a.lastWindowClosed.connect(w.quit) # make upper right cross work
	signal.signal(signal.SIGINT, w.quit) # make ctrl-c work (still requires events to happen)
	w.show()
	sys.exit(a.exec_())
	
