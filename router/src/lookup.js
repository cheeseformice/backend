"use strict";

const express = require("express");
const {
	service,
	getPagination,
	writeError,
	rankableFields,
	handleServiceError,
	handleBasicServiceResult,
} = require("./common");

const router = express.Router();

const validPeriods = [
	"overall",
	"daily",
	"weekly",
	"monthly",
];

function showLastRequested(type, last, res) {
	service.redis.lrange(`last:id:${type}`, 0, last - 1, (err, ids) => {
		if (!!err) {
			console.error(err);
			writeError(res, 500);
			return;
		}

		if (ids.length == 0) {
			res.send([]);
			return;
		}

		for (var i = 0; i < ids.length; i++) {
			ids[i] = ids[i].toString();
		}

		service.redis.hmget(`last:obj:${type}`, ids, (err, items) => {
			if (!!err) {
				console.error(err);
				writeError(res, 500);
				return;
			}

			const response = [];

			for (var i = 0; i < items.length; i++) {
				response.push(JSON.parse(items[i]));
			}

			res.send(response);
		});
	});
}

function lookup(what) {
	// Lookup several players or tribes
	return (req, res) => {
		const { offset, limit } = getPagination(req);
		const { search, order } = req.query;
		var { last } = req.query;

		if (!!last && !isNaN(last)) {
			last = parseInt(last);

			if (last < 1 || last > 100) {
				return writeError(
					res, 400,
					"'last' parameter not in range [1-100]"
				);
			}

			return showLastRequested(what, last, res);
		}

		const hasSearch = !!search;
		const hasOrder = !!order;
		if (hasSearch === hasOrder) {
			// If none of the queries is in the request, or both are...
			return writeError(
				res, 400,
				"This endpoint requires either search or order query parameters (not both!)"
			);
		}

		let period;
		if (hasOrder) {
			period = req.query.period || "overall";

			if (!rankableFields.includes(order)) {
				return writeError(res, 400, "The given field is not rankable.");
			} else if (!validPeriods.includes(period)) {
				return writeError(
					res, 400,
					"Invalid leaderboard period"
				);
			}
		}

		// Send the request to the lookup service and send whatever it replies
		// to the user
		service.request("lookup", what, {
			search: search || null,
			offset: offset,
			order: order || null,
			limit: limit,
			tribe: null,
			period: period,
		}, handleBasicServiceResult(res));
	};
}
router.get("/players", lookup("player"));
router.get("/tribes", lookup("tribe"));

router.get("/position/:field", (req, res) => {
	let { field } = req.params;
	let { value } = req.query;

	value = parseInt(value);
	if (isNaN(value)) {
		return writeError(res, 400, "Invalid stat value");
	}

	if (!rankableFields.includes(field)) {
		return writeError(res, 400, "The given field is not rankable.");
	}

	service.request("lookup", "player-position", {
		field, value
	}, (result) => {
		if (result.type == "simple") {
			res.send(result.content);

		} else if (!!result.err) {
			if (result.err == "rejected" && result.type == "Unavailable") {
				writeError(res, 503, "This operation can't be performed right now.");
				return;
			}

			handleServiceError(res, result);
		}
	});
});

router.get("/tribes/:id/members", (req, res) => {
	// Someone wants the list of members of a tribe
	var { id } = req.params;

	id = parseInt(id);
	if (isNaN(id)) {
		return writeError(res, 400, "Invalid tribe ID");
	}

	const { offset, limit } = getPagination(req);
	const { search, order } = req.query;

	if (!!search && !!order) {
		// You may have one of them or none, but not both
		return writeError(
			res, 400,
			"This endpoint may have either search or order query parameters (not both!)"
		);
	}

	let period;
	if (!!order) {
		period = req.query.period || "overall";

		if (!rankableFields.includes(order)) {
			return writeError(res, 400, "The given field is not rankable.");
		} else if (!validPeriods.includes(period)) {
				return writeError(
					res, 400,
					"Invalid leaderboard period"
				);
			}
	}

	// Send the request to the lookup service and send whatever it replies
	// to the user
	service.request("lookup", "player", {
		search: search || null,
		offset: offset,
		order: order || null,
		limit: limit,
		tribe: id,
		period: period,
	}, handleBasicServiceResult(res));
});

module.exports = router;
