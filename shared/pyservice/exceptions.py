class ServiceUnavailable(Exception):
	"""Raised when you try to send a request to a service that is
	unavailable.
	"""


class ServiceError(Exception):
	"""Raised when a service failed to fulfill your request."""


class UnknownRejection(Exception):
	"""Raised when a service rejects your request, and you haven't
	registered an exception for this rejection type
	"""
	def __init__(self, *args, **kwargs):
		self.args = args
		self.kwargs = kwargs


class InvalidEventName(Exception):
	"""Raised when you try to register an event with an invalid name"""
