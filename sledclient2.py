import rtc3dclient

class SledClient2(rtc3dclient.Rtc3dClient):
	def __init__(self):
		"""just call the superclass constructor with default arguments"""
		#super(SledClient, self).__init__()
		rtc3dclient.Rtc3dClient(self).__init__()
	def connect(self, host="localhost", port=3375):
	#def connect(self, host="localhost", port=3020):
		"""same as in superclass, but with a default port"""
		#super(SledClient, self).connect(host, port)
		rtc3dclient.Rtc3dClient(self).connect(host, port)
	def goto(self, dx):
		"""Oder the sled to a certain position and return the time it will take in seconds"""
		self.sledClient.sendCommand("Profile 40 Set Table 2 Abs 0.1 {}".format(dx))
		self.sledClient.sendCommand("Profile 40 Execute")
		return 2.0
