class ConnectionLost(Exception):
	"""Raised when you're waiting for a redis response and the
	connection with the server is lost
	"""


class InvalidMessage(Exception):
	"""Raised when you're trying to decode an invalid message"""


class InvalidEventName(Exception):
	"""Raised when you try to register an event with an invalid name"""
