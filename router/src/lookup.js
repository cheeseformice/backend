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
		var { last, tfm, cfm, operator } = req.query;

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
		const hasRoles = !!tfm || !!cfm;
		if (hasRoles && what === "tribe") {
			return writeError(
				res, 400,
				"This endpoint does not allow to filter by roles."
			);
		}

		if (hasSearch + hasOrder + hasRoles !== 1) {
			// for some reason javascript allows us to sum booleans
			// and we exclusively only need one filter
			return writeError(
				res, 400,
				"This endpoint requires only one filter (search, order, tfm/cfm)"
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

		let requestName;
		let request;
		if (!hasRoles) {
			requestName = what;
			request = {
				search: search || null,
				offset: offset,
				order: order || null,
				limit: limit,
				tribe: null,
				period: period,
			};
		} else {
			if (typeof tfm === "string" && tfm !== "all") {
				tfm = [tfm];
			}
			if (typeof cfm === "string" && cfm !== "all") {
				cfm = [cfm];
			}

			let op = operator;
			if (!operator) {
				op = "or";
			} else if (!["or", "and"].includes(operator)) {
				return writeError(res, 400, "Invalid operator");
			}

			requestName = "roles";
			request = {
				tfm: tfm || [],
				cfm: cfm || [],
				op,
				offset,
				limit,
			};
		}

		// Send the request to the lookup service and send whatever it replies
		// to the user
		service.request("lookup", requestName, request, handleBasicServiceResult(res));
	};
}
router.get("/players", lookup("player"));
router.get("/tribes", lookup("tribe"));

router.get("/position/:field", (req, res) => {
	let { field } = req.params;
	let { entity, value } = req.query;

	if (!entity) {
		entity = "player";
	} else if (entity !== "player" && entity !== "tribe") {
		return writeError(res, 400, "Invalid entity (must be either `player` or `tribe`)")
	}

	value = parseInt(value);
	if (isNaN(value)) {
		return writeError(res, 400, "Invalid stat value");
	}

	if (!rankableFields.includes(field)) {
		return writeError(res, 400, "The given field is not rankable.");
	}

	service.request("lookup", "position", {
		field, value, for_player: entity === "player"
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
