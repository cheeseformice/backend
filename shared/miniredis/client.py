import asyncio
import inspect
from .connection import Connection
from .exceptions import InvalidEventName


class Client:
	def __init__(self, host, port=6379, reconnect=0, loop=None):
		self.loop = loop or asyncio.get_event_loop()

		self.host = host
		self.port = port
		self.reconnect = reconnect

		self.subscribed = set()
		self.channels = Connection(self, "channels", False, loop=self.loop)
		self.main = Connection(self, "main", True, loop=self.loop)

	def event(self, handler):
		method_name = handler.__name__
		if method_name.startswith("on_"):
			setattr(self, method_name, handler)

		else:
			raise InvalidEventName(
				"{} is not a valid event name"
				.format(method_name)
			)

		return handler

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

	async def start(self):
		await self.channels.connect(self.host, self.port)
		await self.main.connect(self.host, self.port)

	async def on_connection_lost(self, client):
		if self.reconnect > 0:
			await asyncio.sleep(self.reconnect)

			await client.connect(self.host, self.port)

	async def on_connection_made(self, client):
		if client.name == "channels":
			for channel in self.subscribed:
				await client.send("subscribe", channel)

	def on_message_received(self, client, message):
		if isinstance(message, list) and message[0] == "message":
			self.dispatch("channel_message", message[1], message[2])

	async def subscribe(self, channel):
		if channel not in self.subscribed:
			self.subscribed.add(channel)

			if self.channels.open:
				await self.channels.send("subscribe", channel)

	async def unsubscribe(self, channel):
		if channel in self.subscribed:
			self.subscribed.remove(channel)

			if self.channels.open:
				await self.channels.send("unsubscribe", channel)

	def send(self, *args, **kwargs):
		return self.main.send(*args, **kwargs)
