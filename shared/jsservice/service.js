"use strict";

const redis = require("redis");
const { v4: uuidv4 } = require("uuid");
const Request = require("./request");


const ping_delay = (process.env.INFRA_PING_DELAY || 30) * 1000;
const ping_timeout = (process.env.INFRA_PING_TIMEOUT || 2) * 1000;
const redis_address = process.env.INFRA_ADDR || "redis:6379";


class Service {
	constructor(name, doPings=false, worker=0) {
		this.name = name;

		this.worker = worker;
		this.myChannel = `service:${name}@${worker}`;

		this.otherWorkers = {};
		this.usedWorkers = {};
		this.waiters = {};
		this.requestHandlers = {};

		this.pings = {};
		this.nextPingAt = 0;
		this.pingValidUntil = 0;

		this.success = 0;
		this.errors = 0;

		this.messageCallback = null;

		let connectOptions;
		if (redis_address.includes(":")) {
			const [host, port] = redis_address.split(":", 2);

			connectOptions = {
				host: host,
				port: parseInt(port),
			};
		} else {
			connectOptions = {
				path: redis_address,
			};
		}

		this.redisSubscriber = redis.createClient(connectOptions);
		this.redis = redis.createClient(connectOptions);

		this.redisSubscriber.on("message", this.onMessage.bind(this));
		this.redisSubscriber.subscribe(this.myChannel);
		this.redisSubscriber.subscribe("service:healthcheck");

		if (doPings) {
			this.pingId = null;
			this.pingStart = 0;
			this.nextPings = {};
			this.missingResponses = [];
			this.pingTimeout = null;
			this.pingCallback = null;

			// Add some offset to the ping loop, depending on the worker
			// This way, two workers will never send the ping packet at the
			// same time.
			setTimeout(() => {
				setInterval(this.pingLoop.bind(this), ping_delay);
			}, worker * ping_timeout);
		}
	}

	setMessageCallback(handler) {
		this.messageCallback = handler;
	}

	onRequest(request, handler) {
		this.requestHandlers[request] = handler;
	}

	onPing(handler) {
		this.pingCallback = handler;
	}

	selectWorker(target) {
		const workers = this.otherWorkers[target];
		if (!workers) { return 0; }

		let index = this.usedWorkers[target];
		if (index === undefined) {
			index = -1;
		}

		let worker;
		const pingValid = Date.now() < this.pingValidUntil;
		for (var attempt = 0; attempt < workers.length; attempt++) {
			index = (index + 1) % workers.length;
			worker = workers[index];

			if (pingValid && !this.pings[`${target}@${worker}`]) {
				continue;
			}
			break;
		}

		this.usedWorkers[target] = index;
		return worker;
	}

	send(target, msg, data, worker) {
		if (typeof worker == "undefined") {
			worker = this.selectWorker(target);
		}

		return this.sendStrict(`service:${target}@${worker}`, msg, data);
	}

	sendStrict(target, msg, data) {
		data.source = this.name;
		data.worker = this.worker;
		data.type = msg;

		this.redis.publish(target, JSON.stringify(data));
	}

	handleRequest(handler, request) {
		let success = true;
		try {
			handler(request);
		} catch (e) {
			success = false;

			this.errors += 1;
			console.error(e);

			request.error();
		}

		if (success) {
			this.success += 1;
			if (request.alive) {
				request.end();
			}
		}
	}

	request(target, request, data, callback, timeout=1000, worker=undefined) {
		if (typeof worker == "undefined") {
			worker = this.selectWorker(target);
		}

		const listener = `${target}@${worker}`;
		if (Date.now() < this.pingValidUntil && !this.pings[listener]) {
			// None of the workers are alive
			return callback({
				err: "unavailable",
			});
		}

		var requestId = uuidv4();
		var timeoutId;
		var receivedOnce = false;

		let onResponse = (response) => {
			// Called when the other service responds
			if (!receivedOnce) {
				clearTimeout(timeoutId);
			}

			if (response.response_type == "reject") {
				// Rejected request
				return callback({
					err: "rejected",
					type: response.rejection_type,
					args: response.args,
					kwargs: response.kwargs
				});
			} else if (response.response_type == "error") {
				// Oops!
				return callback({ err: "internal" });
			}

			if (!receivedOnce) {
				receivedOnce = true;

				if (response.response_type == "stream") {
					// Just signal that we're starting a stream
					return callback({ type: "stream" });
				}

				// If there is no stream, no need to keep the waiter in memory
				delete this.waiters[requestId];

				if (response.response_type == "simple") {
					// Simple response
					callback({ type: "simple", content: response.content });
				} else if (response.response_type == "end") {
					// Simple response, but no content
					callback({ type: "simple", content: null });
				}
			} else {
				if (response.response_type == "content") {
					// Stream content
					callback({ type: "content", content: response.content });
				} else {
					// Stream ended
					delete this.waiters[requestId];
					callback({ type: "end" });
				}
			}
		};
		this.waiters[requestId] = onResponse;

		data.request_type = request;
		data.request_id = requestId;
		this.send(target, "request", data, worker);

		timeoutId = setTimeout(() => {
			if (receivedOnce) { return; }
			receivedOnce = true;

			delete this.waiters[requestId];
			callback({ err: "timeout" });
		}, timeout);
	}

	onMessage(channel, msg) {
		msg = JSON.parse(msg);

		if (channel == this.myChannel) {
			if (msg.type == "request") {
				let request = new Request(this, msg);

				let handler = this.requestHandlers[msg.request_type];
				if (!!handler) {
					this.handleRequest(handler, request);
				} else {
					request.end();
				}

			} else if (msg.type == "response") {
				let waiter = this.waiters[msg.request_id];
				if (!!waiter) {
					// Some code is waiting for this message
					waiter(msg);
				}

			} else if (msg.type == "pong") {
				if (msg.ping_id != this.pingId) { return; }

				const name = `${msg.source}@${msg.worker}`;
				this.nextPings[name] = {
					ping: Date.now() - this.pingStart,
					success: msg.success,
					errors: msg.errors,
				};

				let index = this.missingResponses.indexOf(name);
				if (index != -1) {
					this.missingResponses.splice(index, 1);

					if (this.missingResponses.length == 0) {
						clearTimeout(this.pingTimeout);
						this.pingDone();
					}
				}

			} else if (!!this.messageCallback) {
				this.messageCallback(msg);
			}

		} else if (channel == "service:healthcheck") {
			if (msg.type == "ping") {
				let success = this.success;
				let errors = this.errors;
				this.success = 0;
				this.errors = 0;

				this.nextPingAt = Date.now() + ping_delay - ping_timeout;
				this.send(msg.source, "pong", {
					ping_id: msg.ping_id,
					success: success,
					errors: errors,
				}, msg.worker);

			} else if (msg.type == "ping-result") {
				this.pingValidUntil = Date.now() + ping_delay * 2;

				if (msg.source === this.name && msg.worker == this.worker) {
					// Ignore echo
					return;
				}

				this.pingDone(msg.pings);
			}
		}
	}

	pingDone(pings) {
		this.pings = pings || this.nextPings;
		this.pingId = null;

		if (!!this.pingCallback) {
			this.pingCallback(this.pings);
		}

		if (!pings) {
			// Result from this worker. Need to broadcast results!
			this.sendStrict("service:healthcheck", "ping-result", {
				pings: this.pings
			});
		}

		const services = Object.keys(this.pings);
		for (var i = 0; i < services.length; i++) {
			let [ name, worker ] = services[i].split("@", 2);
			worker = parseInt(worker);

			if (!this.otherWorkers[name]) {
				this.otherWorkers[name] = [worker];
			} else if (!this.otherWorkers[name].includes(worker)) {
				this.otherWorkers[name].push(worker);
			}
		}
	}

	pingLoop() {
		if (Date.now() < this.nextPingAt) {
			// Ping made recently (most likely by another worker)
			return;
		}

		this.pingId = uuidv4();
		this.pingStart = Date.now();
		this.nextPings = {};

		this.missingResponses = [];
		let services = Object.keys(this.pings);
		for (var i = 0; i < services.length; i++) {
			this.missingResponses.push(services[i]);
		}

		this.sendStrict("service:healthcheck", "ping", {
			ping_id: this.pingId
		});

		this.pingTimeout = setTimeout(() => {
			this.pingDone();
		}, ping_timeout);
	}
}


module.exports = Service;
