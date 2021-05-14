from .exceptions import ServiceError


class SimpleResponse:
	def __init__(self, content):
		self.is_stream = False
		self.content = content


class StreamResponse:
	def __init__(self, service, request, queue):
		self.is_stream = True
		self.service = service
		self.request = request
		self.queue = queue

	def __aiter__(self):
		return self

	async def __anext__(self):
		response = await self.queue.get()

		if response["response_type"] == "end":
			self.service.unregister_waiter(self.request)
			del self.service, self.request, self.queue

			raise StopAsyncIteration

		elif response["response_type"] == "content":
			return response["content"]

		elif response["response_type"] == "error":
			raise ServiceError()
