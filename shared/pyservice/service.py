import os
import json
import time
import uuid
import signal
import asyncio
import inspect
import logging
import traceback
import multiprocessing as mp

from shared.miniredis import Client

from .exceptions import ServiceUnavailable, ServiceError, \
	UnknownRejection, InvalidEventName
from .request import Request
from .response import SimpleResponse, StreamResponse


logger = logging.getLogger("service")


class config:
	ping_delay = float(os.getenv("INFRA_PING_DELAY", "30"))
	ping_timeout = float(os.getenv("INFRA_PING_TIMEOUT", "2"))

	host = os.getenv("INFRA_ADDR", "redis:6379")
	reconnect = float(os.getenv("INFRA_RECONNECT", "10"))


def worker_start(
	worker, workers,
	name,
	events, request_handlers, rejections,
):
	service = Service(name)

	for method_name, handler in events:
		setattr(service, method_name, handler)
	service.request_handlers = request_handlers
	service.rejections = rejections

	return service.run(worker, workers)


class Service:
	def __init__(self, name, loop=None):
		self.loop = loop or asyncio.get_event_loop()
		self.name = name

		self.running = False
		self.open_requests = 0

		# By default, set to worker 0
		self.worker = 0
		self.my_channel = "service:{}@{}".format(name, 0)

		self._events = []
		self.other_workers = {}
		self.used_workers = {}
		self.waiters = {}
		self.rejections = {}
		self.request_handlers = {}

		# Ping data
		self.pings = {}
		self.next_ping_at = 0
		self.ping_valid_until = 0

		# Request data
		self.success = 0
		self.errors = 0

		if ":" in config.host:
			address = config.host.split(":")
			address[1] = int(address[1])
		else:
			address = config.host

		self.redis = Client(
			address,
			reconnect=config.reconnect,
			loop=self.loop
		)
		self.redis.event(self.on_channel_message)  # Setup event

	def set_worker_id(self, worker):
		self.worker = worker
		self.my_channel = "service:{}@{}".format(self.name, worker)

	def register_waiter(self, request_id):
		"""Registers a waiter (queue) for a request response."""
		self.waiters[request_id] = queue = asyncio.Queue()
		return queue

	def unregister_waiter(self, request_id):
		"""Unregisters a waiter for a request response."""
		del self.waiters[request_id]

	def rejection(self, _type, exception):
		"""Registers a rejection exception that will be raised instead
		of UnknownRejection when a request gets rejected.
		"""
		self.rejections[_type] = exception

	def on_request(self, request_type):
		"""Decorator that registers a handler for the given request
		type
		"""
		def decorator(handler):
			self.request_handlers[request_type] = handler
			return handler
		return decorator

	def event(self, handler):
		method_name = handler.__name__
		if method_name.startswith("on_"):
			self._events.append((method_name, handler))
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
			return self.loop.create_task(coro)

	def select_worker(self, target):
		"""Uses round robin to select a worker of the given target."""
		workers = self.other_workers.get(target)
		if workers is None:
			# Target isn't connected (or not yet discovered)
			return 0

		if target not in self.used_workers:
			index = self.used_workers[target]
		else:
			index = -1

		length = len(workers)
		ping_valid = time.time() < self.ping_valid_until
		for attempt in range(length):
			index = (index + 1) % length
			worker = workers[index]

			if ping_valid and f"{target}@{worker}" not in self.pings:
				# If the worker is dead, ignore it!
				continue

			# The worker is alive, return already!
			break

		# If no worker has been found, just do nothing and return a
		# dead worker.

		self.used_workers[target] = index
		return worker

	def send(self, target, msg, worker=None, **data):
		"""Sends a message to the given service worker."""
		if worker is None:
			worker = self.select_worker(target)

		return self.send_strict(
			"service:{}@{}".format(target, worker),
			msg,
			**data
		)

	def send_strict(self, target, msg, **data):
		"""Sends a message to the given listener."""
		data.update({
			"source": self.name,
			"worker": self.worker,
			"type": msg,
		})

		return self.redis.send(
			"publish", target, json.dumps(data),
			result=False
		)

	async def handle_request(self, handler, request):
		"""Execute a request handler, and if it throws an error, send a
		proper error response.
		"""
		try:
			# Execute handler
			await handler(request)

		except Exception:
			# Exception thrown
			self.errors += 1
			traceback.print_exc()
			await request.error()

		else:
			# Request successfully ended
			self.success += 1
			if request.alive:
				await request.end()

		finally:
			if request.alive:
				await request.finish()

	async def request(
		self,
		target, request,
		worker=None, timeout=1.0, **data
	):
		"""Sends a request to a service and waits for a response."""
		if worker is None:
			worker = self.select_worker(target)

		listener = f"{target}@{worker}"
		if time.time() < self.ping_valid_until and listener not in self.pings:
			# None of the workers are alive
			raise ServiceUnavailable("The target is dead.")

		# Generate request ID
		request_id = uuid.uuid4().hex
		queue = self.register_waiter(request_id)  # and register waiter

		# Send request
		data.update({
			"request_type": request,
			"request_id": request_id,
		})
		await self.send(target, "request", worker=worker, **data)

		# Wait for a response
		resp = await asyncio.wait_for(queue.get(), timeout)

		if resp["response_type"] == "stream":
			# Stream start
			return StreamResponse(self, request_id, queue)

		# We don't expect more message if this isn't a stream.
		self.unregister_waiter(request_id)

		if resp["response_type"] == "reject":  # Rejected request
			exception = self.rejections.get(
				resp["rejection_type"],
				UnknownRejection
			)
			raise exception(*resp["args"], **resp["kwargs"])

		elif resp["response_type"] == "simple":
			# Simple response (sent in a single packet)
			return SimpleResponse(resp["content"])

		elif resp["response_type"] == "end":
			# Empty response
			return SimpleResponse(None)

		elif resp["response_type"] == "error":
			# Service error
			raise ServiceError()

	def on_channel_message(self, channel, msg):
		msg = json.loads(msg)

		if channel == self.my_channel:
			if msg["type"] == "request":  # Received a request
				request = Request(self, msg)

				if not self.running:
					# Service doesn't accept requests right now.
					print("Request when not running")
					self.loop.create_task(request.end())
					return

				handler = self.request_handlers.get(msg["request_type"])
				if handler is not None:
					# There is a handler registered
					coro = self.handle_request(handler, request)

				else:
					# No handler
					print("No handler for request", msg["request_type"])
					coro = request.end()

				self.loop.create_task(coro)

			elif msg["type"] == "response":  # Received a response
				queue = self.waiters.get(msg["request_id"])
				if queue is not None:
					# Some code is waiting for this message
					queue.put_nowait(msg)

			else:  # Other message
				self.dispatch("message", msg)

		elif channel == "service:healthcheck":
			if msg["type"] == "ping":
				success, errors = self.success, self.errors
				self.success, self.errors = 0, 0

				self.next_ping_at = time.time() \
					+ config.ping_delay \
					- config.ping_timeout

				self.loop.create_task(self.send(
					msg["source"], "pong",
					worker=msg["worker"], ping_id=msg["ping_id"],
					success=success, errors=errors,
				))

			elif msg["type"] == "ping-result":
				self.pings = msg["pings"]
				self.ping_valid_until = time.time() + config.ping_delay * 2

				for service in self.pings:
					name, worker = service.split("@")
					worker = int(worker)

					if name not in self.other_workers:
						self.other_workers[name] = [worker]
					elif worker not in self.other_workers[name]:
						self.other_workers[name].append(worker)

	async def stop_coro(self):
		self.running = False

		while self.open_requests > 0:
			await asyncio.sleep(.5)

		await self.dispatch("stop")
		self.loop.stop()

	def stop(self):
		self.loop.create_task(self.stop_coro())

	def run(self, worker=None, workers=1):
		if workers > 1:
			if worker is None:
				# Main worker
				worker = 0
				processes = []

				for i in range(1, workers):
					process = mp.Process(
						target=worker_start,
						kwargs={
							"worker": i,
							"workers": workers,

							"name": self.name,

							"events": self._events,
							"request_handlers": self.request_handlers,
							"rejections": self.rejections,
						}
					)
					process.daemon = True
					process.start()
					processes.append(process)

			self.set_worker_id(worker)

		signal.signal(signal.SIGINT, lambda s, f: self.stop())
		signal.signal(signal.SIGTERM, lambda s, f: self.stop())

		self.loop.create_task(self.start())
		self.loop.run_forever()

		self.loop.close()
		if workers > 1 and worker == 0:
			# More workers and this is the main one
			for process in processes:
				process.terminate()

	async def start(self):
		await self.redis.start()
		await self.redis.subscribe(self.my_channel)
		await self.redis.subscribe("service:healthcheck")

		await self.dispatch("boot", self)
		self.running = True
