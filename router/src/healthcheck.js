"use strict";

const express = require("express");
const { service } = require("./common");

const router = express.Router();

var statuses = {};
var statusListeners = [];

// Triggered when a service sends a heartbeat packet
service.onHeartbeat((serv, success, errors) => {
	if (!statuses[serv]) {
		// The service isn't registered in our statuses
		statuses[serv] = {
			success: success,
			errors: errors,
		};
	} else {
		// The server is registered, just sum the data
		statuses[serv].success += success;
		statuses[serv].errors += errors;
	}
});

// Triggered when this service sends a ping request and it gets completed
service.onPing((pings) => {
	let data = statuses;
	statuses = {}; // reset so other heartbeats don't get affected/lost

	// Get all the services that replied (or not) to this ping
	let services = Object.keys(pings);
	for (var i = 0; i < services.length; i++) {
		let service = services[i];

		if (!data[service]) {
			// The service isn't in the heartbeat list.
			// It just connected to the network.
			data[service] = {
				success: 0,
				errors: 0,
				ping: pings[service],
			};
		} else {
			// The service was in the heartbeat list. Register its ping.
			data[service].ping = pings[service];
		}
	}

	// Check if any service sent heartbeat data, but not ping (died)
	services = Object.keys(data);
	for (i = 0; i < services.length; i++) {
		let service = data[ services[i] ];

		if (typeof service.ping == "undefined") {
			// The service died! Set ping to null.
			service.ping = null;
		}
	}

	setImmediate(() => {
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

		for (var i = 0; i < services.length; i++) {
			const [service, worker] = services[i].split("@");

			if (!toSend[service]) {
				toSend[service] = {
					[worker]: data[ services[i] ]
				};
			} else {
				toSend[service][worker] = data[ services[i] ];
			}
		}

		toSend = JSON.stringify(toSend);
		// Notify all the clients listening for this event
		for (i = 0; i < statusListeners.length; i++) {
			statusListeners[i].send(toSend);
		}
	});
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
