import asyncio
import inspect
from .exceptions import ConnectionLost, InvalidMessage


class RedisProtocol(asyncio.Protocol):
	def __init__(self, conn):
		self.buffer = bytearray()
		self.connection = conn

	def data_received(self, data):
		self.buffer.extend(data)

		while True:
			decoded = self.decode(self.buffer)

			if not decoded:  # No more items to read, stop.
				break

			length, item = decoded
			del self.buffer[:length]  # Free memory
			self.connection.dispatch("message_received", item)

	def connection_made(self, transport):
		self.transport = transport

	def connection_lost(self, exc):
		self.connection.dispatch("connection_lost")

	def encode(self, array):
		parts = [
			"*{}\r\n"
			.format(len(array))
		]

		for string in array:
			parts.append(
				"${}\r\n{}\r\n"
				.format(len(string), string)
			)

		return "".join(parts).encode()

	def decode(self, buff):
		start = buff.find(b"\r\n")
		if start == -1:
			return

		if buff[0] == 43:  # "+" Simple string
			return start + 2, buff[1:start].decode()

		elif buff[0] == 45:  # "-" Error
			return start + 2, {
				"error": buff[1:start].decode()
			}

		elif buff[0] == 58:  # ":" Integer
			return start + 2, int(buff[1:start])

		elif buff[0] == 36:  # "$" Bulk String
			length = int(buff[1:start])
			if length == -1:  # Null Bulk String
				return start + 2, None

			if len(buff) < start + 4 + length:
				return

			return (
				start + 4 + length,
				buff[start + 2:start + 2 + length].decode()
			)

		elif buff[0] == 42:  # "*" Array
			length = int(buff[1:start])
			if length == -1:  # Null Array
				return start + 2, None

			array = []
			end = start + 2
			for i in range(length):
				decoded = self.decode(buff[end:])
				if not decoded:
					return

				end += decoded[0]
				array.append(decoded[1])

			return end, array

		else:
			raise InvalidMessage(
				"Unknown starting byte: {}. buff: {}"
				.format(buff[0], buff)
			)


class Connection:
	"""Represents a connection between the client and the host."""
	PROTOCOL = RedisProtocol

	def __init__(self, client, name, await_responses, *, loop=None):
		self.loop = loop or asyncio.get_event_loop()

		self.client = client
		self.name = name

		self.open = False
		self.send_queue = asyncio.Queue()
		self.response_queue = asyncio.Queue()
		self.await_responses = await_responses

	def _factory(self):
		return Connection.PROTOCOL(self)

	def dispatch(self, evt, *args, **kwargs):
		method_name = "on_{}".format(evt)

		method = getattr(self, method_name, None)
		if method is None:
			# If the event is not registered, do nothing
			return

		coro = method(*args, **kwargs)
		if inspect.isawaitable(coro):
			# The event returned a task, schedule it
			self.loop.create_task(coro)

	def on_connection_lost(self):
		while not self.response_queue.empty():
			fut = self.response_queue.get_nowait()
			fut.set_exception(ConnectionLost())

		self.open = False
		self.client.dispatch("connection_lost", self)

	def on_message_received(self, message):
		if self.await_responses:
			# If we were told to await responses, we grab a future
			# from Q
			fut = self.response_queue.get_nowait()
			fut.set_result(message)

		# And dispatch an event with the response
		self.client.dispatch("message_received", self, message)

	async def connect(self, host, port=6379):
		try:
			self.response_queue = asyncio.Queue()
			self.transport, self.protocol = await asyncio.wait_for(
				self.loop.create_connection(self._factory, host, port), 3
			)
		except asyncio.TimeoutError:
			self.client.dispatch("connection_lost", self)
			return

		self.open = True
		self.client.dispatch("connection_made", self)

		while not self.send_queue.empty():
			request, fut = self.send_queue.get_nowait()
			await self.send(*request, result=False, fut=fut)

	async def send(self, *request, result=True, fut=None):
		"""Send a request to the server, and await for the response"""
		if self.await_responses:
			# If we were told to await responses, we put a future in Q
			if fut is None:
				fut = self.loop.create_future()

			self.response_queue.put_nowait(fut)

		if not self.open:
			# The connection is not open, we wait until it is
			self.send_queue.put_nowait((request, fut))
		else:
			# The connection is open, we send the request
			self.transport.write(self.protocol.encode(request))

		if result and fut is not None:
			# If we were told to return the result, we await the future
			return await fut
