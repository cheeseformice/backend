class Request:
	def __init__(self, service, msg):
		self.service = service

		self.source = msg["source"]
		self.worker = msg["worker"]

		self.request = msg["request_id"]
		self.type = msg["request_type"]
		self.msg = msg

		self.streaming = False
		self.alive = True

	def __getattr__(self, attr):
		return self.msg[attr]

	def finish(self):
		self.alive = False
		del self.service
		del self.source, self.worker
		del self.request, self.type, self.streaming

	async def open_stream(self):
		if not self.alive:
			return

		self.streaming = True
		await self.service.send(
			self.source,
			"response",
			worker=self.worker,
			response_type="stream",
			request_id=self.request
		)

	async def error(self):
		if not self.alive:
			return

		await self.service.send(
			self.source,
			"response",
			worker=self.worker,
			response_type="error",
			request_id=self.request
		)
		self.finish()

	async def reject(self, _type, *args, **kwargs):
		if not self.alive:
			return

		await self.service.send(
			self.source,
			"response",
			worker=self.worker,
			response_type="reject",
			request_id=self.request,
			rejection_type=_type,
			args=args,
			kwargs=kwargs
		)
		self.finish()

	async def send(self, content):
		if not self.alive:
			return

		response = "content" if self.streaming else "simple"

		await self.service.send(
			self.source,
			"response",
			worker=self.worker,
			response_type=response,
			request_id=self.request,
			content=content
		)

		if not self.streaming:
			self.finish()

	async def end(self):
		if not self.alive:
			return

		await self.service.send(
			self.source,
			"response",
			worker=self.worker,
			response_type="end",
			request_id=self.request
		)
		self.finish()
