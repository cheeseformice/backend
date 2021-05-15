"use strict";

const express = require("express");
const { service } = require("./common");

const router = express.Router();

var statusListeners = [];

// Triggered when this service sends a ping request and it gets completed
service.onPing((pings) => {
	let toSend = {};

	// format with structure
	// {
	// 	"service": {
	// 		"0": {
	// 			"success": 0,
	// 			"errors": 0,
	// 			"ping": 2
	// 		},
	// 		"1": {
	// 			"success": 0,
	// 			"errors": 0,
	// 			"ping": 2
	// 		}
	// 	}
	// }

	const services = Object.keys(pings);
	for (var i = 0; i < services.length; i++) {
		const [service, worker] = services[i].split("@", 2);

		if (!toSend[service]) {
			toSend[service] = {
				[worker]: pings[ services[i] ]
			};
		} else {
			toSend[service][worker] = pings[ services[i] ];
		}
	}

	toSend = JSON.stringify(toSend);
	// Notify all the clients listening for this event
	for (i = 0; i < statusListeners.length; i++) {
		statusListeners[i].send(toSend);
	}
});

// A new client wants to listen to service status
router.ws("/status", (ws, req) => {
	statusListeners.push(ws); // Register the client

	ws.on("close", () => {
		// The client disconnected. Remove from list.
		let index = statusListeners.indexOf(ws);
		statusListeners.splice(index, 1);
	});
});

module.exports = router;
