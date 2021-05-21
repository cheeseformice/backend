"use strict";

const express = require("express");
const {
	service,
	writeError,
} = require("./common");

const router = express.Router();

var statusListeners = [];
var services = [];
const reportsPerGroup = 10; // 5 minutes (1 report = 30 seconds)
const historySize = 288; // 24 hours
var nextGroup = [];

service.redis.smembers("status:services", (err, result) => {
	if (!!err) {
		console.error(err);
		return;
	}

	services = result;
});

function mergeReports(reports) {
	const merged = {};

	for (let name of services) {
		let count = 0,
			ping = 0,
			success = 0,
			errors = 0;

		for (var i = 0; i < reports.length; i++) {
			let serviceReport = reports[i][service];
			if (!serviceReport) { continue; }

			count += 1;
			ping += serviceReport.ping;
			success += serviceReport.success;
			errors += serviceReport.errors;
		}

		merged[name] = {
			success,
			errors,
			ping: Math.ceil(ping / count),
		};
	}

	return merged;
}

function compressReports(reports) {
	const compressed = [];

	for (var i = 0; i < reports.length; i++) {
		let report = reports[i];
		let compressedReport = [];

		for (let name of services) {
			let serviceReport = report[name];

			if (!serviceReport) {
				compressedReport.push(null);
				continue;
			}

			compressedReport.push([
				serviceReport.ping,
				serviceReport.success,
				serviceReport.errors,
			]);
		}

		compressed.push(compressedReport);
	}

	return compressed;
}

function parsePings(pings) {
	let report = {};

	// format with structure
	// {
	// 	"service": {
	// 		"success": 0,
	// 		"errors": 0,
	// 		"ping": average
	// 	}
	// }

	const workers = Object.keys(pings);
	for (let i = 0; i < workers.length; i++) {
		const [service, worker] = workers[i].split("@", 2);
		let ping = pings[ workers[i] ];

		if (!report[service]) {
			report[service] = {
				count: 1,
				...ping,
			};
		} else {
			report[service].count += 1;
			report[service].ping += ping.ping;
			report[service].success += ping.success;
			report[service].errors += ping.errors;
		}
	}

	let unknownServices = [];
	const serviceKeys = Object.keys(report);
	for (let i = 0; i < serviceKeys.length; i++) {
		const service = serviceKeys[i];

		if (!services.includes(service)) {
			unknownServices.push(service);
		}

		report[service].ping = report[service].ping / report[service].count;
		delete report[service].count;
	}

	return [ report, unknownServices ];
}

// Triggered when this service sends a ping request and it gets completed
service.onPing((responsible, pings) => {
	const [ report, unknownServices ] = parsePings(pings);

	if (unknownServices.length > 0) {
		for (let i = 0; i < unknownServices.length; i++) {
			services.push(unknownServices[i]);
		}

		if (responsible) {
			service.redis.sadd("status:services", unknownServices, (err) => {
				if (!!err) {
					console.log(err);
				}
			});
		}
	}

	nextGroup.push(report);
	if (nextGroup.length >= reportsPerGroup) {
		if (responsible) {
			const group = mergeReports(nextGroup);
			service.redis.rpush(
				"status:reports",
				JSON.stringify(group),
				(err, items) => {
					if (!!err) {
						console.error(err);
						return;
					}

					if (items > historySize) {
						service.redis.lpop(
							"status:reports",
							items - historySize,
							(err) => {
								if (!!err) {
									console.error(err);
									return;
								}
							}
						);
					}
				}
			);
		}
		nextGroup = [];
	}

	let toSend = JSON.stringify({
		services,
		data: compressReports([report])[0],
	});
	// Notify all the clients listening for this event
	for (let i = 0; i < statusListeners.length; i++) {
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

router.get("/status/past", (req, res) => {
	let { interval } = req.query;
	interval = parseInt(interval) || 2;

	if (interval > 12) {
		writeError(res, 400, "Requested interval is too big.");
		return;
	}

	service.redis.lrange("status:reports", 0, -1, (err, result) => {
		if (!!err) {
			console.error(err);
			writeError(res, 500);
			return;
		}

		let reports = [];
		let forInterval = [];
		if (interval > 1) {
			// Some intervals are skipped, so let's merge them
			for (let i = 0; i < result.length; i++) {
				forInterval.push(JSON.parse(result[i]));

				if (i > 0 && (i + 1) % interval) {
					reports.push(mergeReports(forInterval));
					forInterval = [];
				}
			}

			forInterval = compressReports(forInterval);
		} else {
			for (let i = 0; i < result.length; i++) {
				reports.push(JSON.parse(result[i]));
			}
		}

		res.send({
			interval,
			services,
			forInterval,
			data: compressReports(reports)
		});
	});
});

module.exports = router;
