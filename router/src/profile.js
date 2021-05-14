"use strict";

const express = require("express");
const {
	service,
	getPagination,
	writeError,
	checkAuthorization,
	handleServiceError,
	handleBasicServiceResult,
	normalizeName,
} = require("./common");

const router = express.Router();

function changelogs(what) {
	return (req, res) => {
		// Someone wants to request a changelog
		const { offset, limit } = getPagination(req);
		let { id, logs } = req.params;

		id = parseInt(id);
		logs = parseInt(logs);

		if (isNaN(id) || isNaN(logs)) {
			// Both ID and logs have to be numbers
			return writeError(res, 400);
		}

		const auth = checkAuthorization(req, res);
		if (auth === undefined) { return; } // error written

		// Get the session (if any) and send it to the changelogs service
		// Then return whatever it replies to the user
		service.request("changelogs", what, {
			id: id,
			logs: logs,
			offset: offset,
			limit: limit,
			auth: auth,
		}, handleBasicServiceResult(res));
	};
}
router.get("/players/:id/changelogs/:logs", changelogs("player"));
router.get("/tribes/:id/changelogs/:logs", changelogs("tribe"));

function checkPeriod(req, res) {
	const unsuccessful = {
		success: false,
		start: null,
		end: null,
	};

	const { start, end } = req.query;
	const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
	const dates = [
		start,
		end,
	];
	for (var i = 0; i < dates.length; i++) {
		let date = dates[i];

		if (!!date) {
			if (!date.match(dateRegex) || isNaN(Date.parse(date))) {
				writeError(
					res, 400,
					`Invalid date: ${date} (expected YYYY-MM-DD)`
				);
				return unsuccessful;
			}
		}
	}

	if (!!start && !!end && Date.parse(start) >= Date.parse(end)) {
		writeError(
			res, 400,
			"End date must not be a date before the start date."
		);
		return unsuccessful;
	}

	return {
		success: true,
		start: start,
		end: end,
	};
}

function pushProfile(type, content) {
	const id = content.id.toString();
	content.requested_at = new Date().toISOString();

	service.redis.lrem(`last:id:${type}`, -1, id);
	service.redis.hset(`last:obj:${type}`, id, JSON.stringify(content));
	service.redis.lpush(`last:id:${type}`, id, (err, items) => {
		if (!!err) {
			console.error(err);
			return;
		}

		const maxSize = 100;
		if (items > maxSize) {
			service.redis.rpop(
				`last:id:${type}`,
				items - maxSize,
				(err, pop) => {
					if (!!err) {
						console.error(err);
						return;
					}
					service.redis.hdel(`last:obj:${type}`, pop);
				}
			);
		}
	});
}

router.get("/players/:idOrName", (req, res) => {
	// Someone wants a player profile
	const { idOrName } = req.params;

	// Prepare what we're gonna send to the service
	const request = {
		id: null,
		name: null,
		period_start: null,
		period_end: null,
	};
	const id = parseInt(idOrName);

	if (isNaN(id)) {
		// They're requesting by name, not by ID
		const name = normalizeName(idOrName);
		if (!name) {
			return writeError(res, 400, "Invalid username");
		}
		request.name = name;
	} else {
		// They're requesting by ID
		request.id = id;
	}

	let { success, start, end } = checkPeriod(req, res);
	if (!success) { return; }
	if (!!start) { request.period_start = start; }
	if (!!end) { request.period_end = end; }

	// Send the request to the profile service
	// Then return whatever it replies to the user
	service.request("profile", "player", request, (result) => {
		if (result.type == "simple") {
			if (!!result.content.id) {
				pushProfile("player", {
					id: result.content.id,
					name: result.content.name,
					cfm_roles: result.content.cfm_roles,
					tfm_roles: result.content.tfm_roles,
				});
			}
			res.send(result.content);

		} else if (!!result.err) {
			handleServiceError(res, result);
		}
	});
});

router.get("/tribes/:idOrName", (req, res) => {
	// Someone wants a tribe profile
	const { idOrName } = req.params;

	const request = {
		id: null,
		name: null,
		period_start: null,
		period_end: null,
	};

	if (isNaN(idOrName)) {
		// If the string is not a number, it is a name
		request.name = idOrName.replace("%20", " ");
	} else {
		// Otherwise, an ID
		request.id = parseInt(idOrName);
	}

	let { success, start, end } = checkPeriod(req, res);
	if (!success) { return; }
	if (!!start) { request.period_start = start; }
	if (!!end) { request.period_end = end; }

	// Send the request to the profile service
	// Then return whatever it replies to the user
	service.request("profile", "tribe", request, (result) => {
		if (result.type == "simple") {
			if (!!result.content.id) {
				pushProfile("tribe", {
					id: result.content.id,
					name: result.content.name,
				});
			}
			res.send(result.content);

		} else if (!!result.err) {
			handleServiceError(res, result);
		}
	});
});

module.exports = router;
