"use strict";

class Request {
	constructor(service, msg) {
		this.service = service;

		this.source = msg.source;
		this.worker = msg.worker;

		this.request = msg.request_id;
		this.type = msg.request_type;
		this.msg = msg;

		this.streaming = false;
		this.alive = true;
	}

	finish() {
		this.alive = false;
		delete this.service;
		delete this.source;
		delete this.worker;
		delete this.request;
		delete this.type;
		delete this.streaming;
	}

	openStream() {
		if (!this.alive) { return; }

		this.streaming = true;
		this.service.send(
			this.source,
			"response",
			{
				response_type: "stream",
				request_id: this.request
			},
			this.worker
		);
	}

	error() {
		if (!this.alive) { return; }

		this.service.send(
			this.source,
			"response",
			{
				response_type: "error",
				request_id: this.request
			},
			this.worker
		);
		this.finish();
	}

	reject(type, args, kwargs) {
		if (!this.alive) { return; }

		this.service.send(
			this.source,
			"response",
			{
				response_type: "reject",
				request_id: this.request,
				rejection_type: type,
				args: args,
				kwargs: kwargs
			},
			this.worker
		);
		this.finish();
	}

	send(content) {
		if (!this.alive) { return; }

		this.service.send(
			this.source,
			"response",
			{
				response_type: this.streaming ? "content" : "simple",
				request_id: this.request,
				content: content
			},
			this.worker
		);

		if (!this.streaming) {
			this.finish();
		}
	}

	end() {
		if (!this.alive) { return; }

		this.service.send(
			this.source,
			"response",
			{
				response_type: "end",
				request_id: this.request
			},
			this.worker
		);
		this.finish();
	}
}


module.exports = Request;
