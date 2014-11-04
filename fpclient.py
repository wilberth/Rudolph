#!/usr/bin/python
from __future__ import print_function
import socket, sys, binascii, struct, time, threading, warnings, math, logging,  numpy as np, copy, weakref
from collections import deque

def exitHandler():
	print("exit")

class FpClient(object):
	"Client for NDI First Principles"
	## package and component types
	pTypes = ['Error', 'Command', 'XML', 'Data', 'Nodata', 'C3D']
	cTypes = ['', '3D', 'Analog', 'Force', '6D', 'Event']
	
	def __init__(self, verbose=0, nBuffer=3):
		# 1 verbose, 2: very verbose
		self.verbose = verbose 
		# number of buffered marker coordinate set 
		if nBuffer >= 3:
			self.nBuffer = nBuffer
		else:
			logging.waring("illegal number for nBuffer: {}, using nBuffer=3".format(nBuffer))
		self.sock = 0
		self.stoppingStream = False;
		self.win32TimerOffset = time.time()
		time.clock() # start time.clock 
	
	def __del__(self):
		self.close()
	
	# low level communication functions
	def connect(self, host="localhost", port=3020):
		self.host = host
		self.port = port
		# Create a socket (SOCK_STREAM means a TCP socket)
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		# socket without nagling
		self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
		# Connect to server and send data
		self.sock.settimeout(3)
		try:
			self.sock.connect((host, port))
		except Exception as e:
			logging.error("ERROR connecting to FP Server: "+str(e))
			raise

	def send(self, body, pType):
		#type  0: error, 1: command, 2: xml, 3: data, 4 nodata, 5: c3d
		# pack length and type as 32 bit big endian.
		head = struct.pack(">I", len(body)+8) + struct.pack(">I", pType)
		if self.verbose:
			print("Sent: Body ({}): #{}#".format(len(body), body))
			#print "Sent: Body ({}): #{}#".format(len(body), binascii.hexlify(body))
		try:
			self.sock.sendall(head+body)
		except Exception as e:
			logging.error("ERROR sending to FP server", e)
			raise

	def sendHandshake(self):
		head = struct.pack(">I", 0) + struct.pack("BBBB", 1,3,3,6)
			
	def sendCommand(self, body):
		self.send(body, 1)
		
	def sendXml(self, body):
		self.send(body, 2)

	def receive(self):
		# set pSize, pType and pContent
		try:
			# Receive data from the server and shut down
			# the size given is the buffer size, which is the maximum package size
			self.pSize = struct.unpack(">I", self.sock.recv(4))[0] # package size in bytes
			self.pType = struct.unpack(">I", self.sock.recv(4))[0]
			if self.verbose>1:
				print ("Received ({}, {}): ".format(self.pSize, self.pTypes[self.pType]))
			if self.pSize>8:
				self.pContent = self.sock.recv(self.pSize-8)
			else:
				self.pContent = buffer("", 0)
			return self.pType
		except Exception as e:
			logging.error("ERROR receiving from FP server: ", e)
			raise
			
	def show(self):
		"Show last received package. uses: pType and pContent"
		print("Received: {} ({})".format(self.pTypes[self.pType], self.pType))
		if self.pType in [0,1]: # error or command
			print("  Command: #{}#".format(self.pContent))
			#print "  Received: #{}#".format(binascii.hexlify(self.pContent))
		elif self.pType in [3]: # data
			cCount = struct.unpack(">I", buffer(self.pContent,0,4))[0]
			pointer = 4
			print("  {} data components".format(cCount))
			for i in range(cCount):
				[cSize, cType, cFrame, cTime] = struct.unpack(">IIIQ", buffer(self.pContent, pointer, 20))
				pointer += 20
				print("  component size: {}\n  component type: {} ({})\n  component frame: {}\n  component time: {}".format(cSize, self.cTypes[cType], cType, cFrame, cTime/1E6))
				if cType == 1: # 3D
					[mCount] = struct.unpack(">I", buffer(self.pContent, pointer, 4))
					pointer+=4
					for j in range(mCount):
						[x, y, z, delta] = struct.unpack(">ffff", buffer(self.pContent, pointer, 16))
						pointer+=16
						print("  marker[{}]: ({}, {}, {}) +/- {} m".format(j, x/1E3, y/1E3, z/1E3, delta/1E3))
				elif cType == 2: # analog
					[cCount] = struct.unpack(">I", buffer(self.pContent, pointer, 4))
					pointer+=4
					for j in range(cCount):
						[v] = struct.unpack(">f", buffer(self.pContent, pointer, 4))
						pointer += 4
						print("channel[{}]: {} V".format(j, v))
				elif cType == 4: # 6D
					[tCount] = struct.unpack(">I", buffer(self.pContent, pointer, 4))
					pointer+=4
					for j in range(tCount):
						[q0, qx, qy, qzx, y, z, delta] = struct.unpack(">fffffff", buffer(self.pContent, pointer, 28))
						pointer+=28
						print("  tool[{}]: ({}, {}, {}, {})({}, {}, {}) +/- {} m".format(j, x/1E3, y/1E3, z/1E3, delta/1E3))
			print("  Received data: #{}#".format(binascii.hexlify(self.pContent)))
		else:
			print("  Other {}".format(self.pContent))
			print("  Received: #{}#".format(binascii.hexlify(self.pContent)))
			
	def close(self):
		print("Closing fpClient") # cannot use logging lib logging object may not exist anymore
		self.stopStream()
		self.thread.join() #wait for other thread to die
		self.sock.close()
		
	def parse3D(self):
		"Parse 3D data components in the last received package, "
		"return them as n x 3 array and an "
		if self.pType == 3: # data
			cCount = struct.unpack(">I", buffer(self.pContent,0,4))[0]
			pointer = 4
			markerList = []
			for i in range(cCount):
				[cSize, cType, cFrame, cTime] = struct.unpack(">IIIQ", buffer(self.pContent, pointer, 20))
				pointer += 20
				if cType == 1: # 3D
					# number of markers
					[mCount] = struct.unpack(">I", buffer(self.pContent, pointer, 4))
					pointer+=4
					for j in range(mCount):
						[x, y, z, delta] = struct.unpack(">ffff", buffer(self.pContent, pointer, 16))
						pointer+=16
						markerList.append([x, y, z])
			return (np.matrix(markerList)*1e-3, cTime*1e-6)
		else:
			logging.error("expected 3d data but got packageType: {}".format(self.pType))
			if self.pType==1:
				logging.info("  package: ", self.pContent)
			return np.matrix([])
			
	def time(self):
		if sys.platform == "win32":
			# on Windows, the highest resolution timer is time.clock()
			# time.time() only has the resolution of the interrupt timer (1-15.6 ms)
			# Note that time.clock does not provide time of day information. 
			# EXPECT DRIFT if you do not have ntp better than the MS version
			return self.win32TimerOffset + time.clock()
		else:
			# on most other platforms, the best timer is time.time()
			return time.time()

	# background thead functions
	def startThread(self):
		"""The response time ot the StreamFrames command is used to establish the network delay."""
		# I dont care about warnings that my markers are not moving
		warnings.simplefilter('ignore', np.RankWarning)
		logging.info("starting client thread")
		self.p = deque() # positions
		self.t = deque() # time
		self.ta = deque() # arrival time
		
		self.sendCommand("SetByteOrder BigEndian")
		self.receive()
		
		# start frames and measure network delay and clock difference
		if self.verbose:
			self.show()
		t0 = self.time()
		self.sendCommand("StreamFrames FrequencyDivisor:1")
		self.receive()
		delay = self.time() - t0
		tDifference = []
		nPackage = 0
		for i in range(6):
			retval = self.receive()
			if retval != 3: # not data
				continue
			nPackage += 1
			tClient = self.time()
			(pp, tServer) = self.parse3D() # position of markers and fp server time
			tDifference.append(tClient-tServer)
			
		logging.info("Timing error estimate: delay: {:f}, variation: {:f} (from {} packages)".format(delay, np.std(tDifference), nPackage))
		self.tDifference = np.mean(tDifference)+delay # add this to server time to get client time

		# main data retrieval loop
		tSync = 0
		nSync = 0
		while not self.stoppingStream:
			retval = self.receive()
			if retval != 3: # not data
				logging.info("not data: {}".format(retval))
				continue
			(pp, tServer) = self.parse3D() # position of markers and fp server time
			self.t.append(tServer + self.tDifference) # push
			self.p.append(pp) # push
			self.ta.append(self.time()) # arrival time
			if len(self.p) > self.nBuffer:
				self.p.popleft()
				self.t.popleft()
				
			# print syncing frequency
			#tNew = self.time()
			#nSync += 1
			#if math.floor(tNew) != tSync:
				#tSync = math.floor(tNew)
				#logging.info("syncing at {} Hz".format(nSync))
				#nSync=0
		
		self.sendCommand("Bye")
		logging.info("stopped")
		self.stoppingStream = False;
		
	def startStream(self):
		"Start the background thread that synchronizes with the fp server"
		self.thread = threading.Thread(target = self.startThread)
		self.thread.start()
		
	def stopStream(self):
		"Stop the background thread that synchronizes with the fp server"
		if(self.thread.isAlive()):
			self.stoppingStream = True
			
	# query functions
	def getPosition(self, t = None, dt = None):
		"Extrapolate from the current value of self.p at times self.t to the values at time t."
		if len(self.p)<3:
			logging.error("FpClient was not yet initialized when getPosition request was received")
			return np.matrix([0,0,0])
		if t==None and dt==None:
			# simply return last value
			return self.p[-1]
			
		if t==None:
			# relative time
			t = self.time() + dt
			
		p = np.vstack([self.p[-3].ravel(), self.p[-2].ravel(), self.p[-1].ravel()]) # the last three positions
		#poly = np.polyfit([self.t[-3], self.t[-2], self.t[-1]], p, 2) # fit a quadratic function to the last three positions
		# like the one above but use arrival times at, rather than times t. 
		# This prevents errors if server and client clock drift. """
		poly = np.polyfit([self.ta[-3], self.ta[-2], self.ta[-1]], p, 2)
		p =  np.reshape(np.polyval(poly, t), np.shape(self.p[0]))
		return p
		
	def getPosition2(self, t=None, dt=None):
		"""Like getPosition, but return the extrapolation time as second argument """
		if len(self.p)<3:
			logging.error("FpClient was not yet initialized when getPosition request was received")
			return np.matrix([0,0,0])
		if t==None and dt==None:
			# simply return last value
			return self.p[-1]
			
		if t==None:
			# relative time
			t = self.time() + dt
			
		p = np.vstack([self.p[-3].ravel(), self.p[-2].ravel(), self.p[-1].ravel()])
		poly = np.polyfit([self.ta[-3], self.ta[-2], self.ta[-1]], p, 2)
		p =  np.reshape(np.polyval(poly, t), np.shape(self.p[0]))
		#print ("extrapolation time: {:.3f}".format(t - self.t[-1]))
		return [p, t - self.ta[-1]]


	def getBuffer(self):
		"Return the buffered values."
		return (copy.deepcopy(self.p), copy.deepcopy(self.t))

if __name__ == '__main__':
	logging.basicConfig(level=logging.DEBUG)
	if len(sys.argv) > 1:
		server = sys.argv[1]
	else:
		server = "localhost"
	print ("fp server: ", server)
	positionClient = FpClient()                          # make a new NDI First Principles client
	positionClient.connect(server)                       # connect the client to the First Principles server
	positionClient.startStream()                         # start the synchronization stream. 
	time.sleep(2)
	t = time.time()
	p = positionClient.getPosition()                     # get marker positions
	print ("time elapsed to get pos", time.time() - t)
	print ("position: ", p)                              # do something with the position
	time.sleep(2)
	positionClient.stopStream()
