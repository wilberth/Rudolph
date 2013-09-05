#!/usr/bin/python
import logging

if __name__ == '__main__':
	logger = logging.getLogger(__name__)
	print(logger)
	logging.basicConfig(level=logging.DEBUG)
	logging.info("boe")
	logging.warning("boe")
