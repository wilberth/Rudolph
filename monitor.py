#!/usr/bin/env python
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
def logistic(x):
	return 1/(1+math.exp(x)) # sigmoid
def core(x, a, b):
	return (x-a)/b
def F(x, a, b):
	return logistic(core(x, a, b))
def f(x, a, b, g=0.04, l=0.04):
	return g + (1 - g - l) * F(x, a, b)
	
	

class Main(QWidget):
	def __init__(self, args):
		super(Main, self).__init__()
		self.args = args
		#print("dir: "+self.args.directory)
		
		# building the ui
		self.setMinimumSize(600, 400)
		self.text = QLabel("Paused")
		plotWidget = pg.PlotWidget(self)
		self.graph = plotWidget.getPlotItem()
		self.graph.addLine(y=0.04)
		self.graph.addLine(y=0.96)
		self.graph.setLabel('bottom', 'stimulus')
		self.graph.setLabel('left', 'response')
		self.graph.showGrid(x=True, y=True)
		
		vbox = QVBoxLayout()
		vbox.addWidget(self.text)
		#vbox.addStretch(1)
		vbox.addWidget(plotWidget)
		self.setLayout(vbox)
		
		self.plot()
		
	def plot(self):
		#self.graph.removeItem(self.data)
		self.graph.clear()
		
		if os.path.isfile(self.args.directory):
			fileName = self.args.directory
		else:
			fileName = lastFile(self.args.directory)
		
		print("Most recent file = {}".format(fileName))
		(x,y) = readFile(fileName)
		"""
		for i in range(len(y)):
			if y[i]:
				y[i]=1.0
			else:
				y[i]=0.0
		"""
		print("x: {}\ny: {}".format(x, y))
		data = zip(x, y, [1]*len(x))
		constraints = ( 'unconstrained', 'unconstrained', 'Uniform(0,0.1)', 'Uniform(0,0.1)')
		B = psi.BootstrapInference ( data, core='ab', sigmoid='gauss', priors=constraints, nafc=1 )
		print("est: {}, dev: {}".format(B.estimate, B.deviance))
		self.fit = self.graph.plot(x, y, pen=None, symbolSize=6, antialias=True)
		
		xx = np.linspace(min(x), max(x), 100)
		yy = []
		for p in xx:
			yy.append(f(p,B.estimate[0], B.estimate[1] ))
		self.data = self.graph.plot(xx, yy)

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
	x = []
	y = []
	with open(fileName, 'r') as f:
		reader = csv.reader(f, delimiter=";", skipinitialspace=True)
		# column headers
		head = [d.lstrip() for d in reader.next()]
		while head[-1] == '':
			del(head[-1])
		nColumn = len(head)
		#print("nColumn: {}".format(nColumn))
		#print("head: {}".format(head))
		# burn experiment file header
		while len(head) and len(head)!=1:
			head = reader.next()
		for row in reader:
			row = [d.lstrip() for d in row]
			x.append(float(row[nColumn-1]))
			y.append(row[nColumn]=='True')
		return tuple([x, y])


if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument("directory", nargs='?', default="")
	args = parser.parse_args()
	
	a = QApplication(sys.argv)
	w = Main(args)
	a.lastWindowClosed.connect(w.quit) # make upper right cross work
	signal.signal(signal.SIGINT, w.quit) # make ctrl-c work
	w.show()
	sys.exit(a.exec_())
	
