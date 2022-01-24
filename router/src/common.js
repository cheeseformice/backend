"use strict";

const jwt = require("jsonwebtoken");
const Service = require("./shared/jsservice/service");
const service = new Service(
	"router", true,
	parseInt(process.env.SERVICE_WORKER_ID || "0")
);

const SESSION_KEY = process.env.SESSION_KEY || "some long ass string lol";
const REFRESH_KEY = process.env.REFRESH_KEY || "another long ass string lol";
const BOT_KEY = process.env.BOT_KEY || "yet another long ass string lol";

if (!process.env.SESSION_KEY ||
	!process.env.REFRESH_KEY ||
	!process.env.BOT_KEY) {
	console.warn(
		"One or many of the required JWT aren't defined. Using default."
	);
}

const statusReasons = {
	400: "Bad request",
	401: "Unauthorized",
	403: "Forbidden",
	404: "Not found",
	429: "Too many requests",
	500: "Internal server error",
	503: "Service unavailable",
};

function writeError(res, status, message, translationKey) {
	const reason = statusReasons[status] || "";
	const result = { status: status, success: false };

	if (!!reason) { result.error = reason; }
	if (!!message) { result.message = message; }
	if (!!translationKey) { result.translation_key = `errors.${translationKey}`; }

	res.status(status).send(result);
}

function handleServiceError(res, result) {
	switch (result.err) {
		case "unavailable":
		case "timeout":
			writeError(res, 503, "The service is unavailable");
			break;

		case "rejected":
			if (result.type == "BadRequest") {
				writeError(res, 400, result.args[0]);
			}	else if (result.type == "MissingPrivileges") {
				writeError(res, 401, result.args[0]);
			}	else if (result.type == "NotFound") {
				writeError(res, 404, result.args[0]);
			} else if (result.type == "NotImplemented") {
				writeError(res, 500, result.args[0]);
			} else {
				writeError(res, 500, result.args[0], result.kwargs.translation_key);
			}
			break;

		case "internal":
		default:
			writeError(res, 500, null, "internal");
			break;
	}
}

function handleBasicServiceResult(res, contentType) {
	return (result) => {
		if (result.type == "simple") {
			if (!!contentType) { res.type(contentType); }
			res.send(result.content);

		} else if (!!result.err) {
			handleServiceError(res, result);
		}
	};
}

function getPagination(req) {
	var { page, limit } = req.query;

	page = parseInt(page);
	limit = parseInt(limit);

	page = Math.max(1, isNaN(page) ? 1 : page); // [1,inf)
	limit = Math.min(100, Math.max(1, isNaN(limit) ? 50 : limit)); // [1,100]

	return {
		offset: (page - 1) * limit,
		limit: limit
	};
}

function checkAuthorization(req, res, bot) {
	if (req.cfmAuthorization) {
		return req.cfmAuthorization;
	}

	const { authorization } = req.headers;
	if (!authorization) { return null; }

	if (!authorization.toLowerCase().startsWith(bot ? "bot " : "bearer ")) {
		writeError(res, 401, `Invalid ${bot ? 'bot' : 'user'} token`);
		return;
	}

	const [type, token] = authorization.split(" ", 2);

	try {
		req.cfmAuthorization = jwt.verify(token, bot ? BOT_KEY : SESSION_KEY);
		return req.cfmAuthorization;
	} catch(err) {
		switch (err.name) {
			case "TokenExpiredError":
				writeError(res, 401, "Token has expired");
				break;

			case "JsonWebTokenError":
			default:
				writeError(res, 401, "Invalid token");
				break;
		}
		return;
	}
}

function assertAuthorization(req, res, roles) {
	const auth = checkAuthorization(req, res, roles && roles.bot);

	// error already written
	if (auth === undefined) { return; }

	if (!auth) {
		writeError(
			res, 401,
			"You need a session to use this endpoint."
		);
		return;
	}

	if (auth.cfm_roles.includes("dev") ||
		auth.cfm_roles.includes("admin")) {
		// All privileges
		return auth;
	}

	if (!!roles) {
		var i;
		if (!!roles.cfm) {
			// Requires CFM authorization
			for (i = 0; i < roles.cfm.length; i++) {
				if (auth.cfm_roles.includes(roles.cfm[i])) {
					return auth;
				}
			}
		}

		if (!!roles.tfm) {
			// Requires TFM authorization
			roles.tfm.push("admin"); // if the user has admin role, grant all

			for (i = 0; i < roles.tfm.length; i++) {
				if (auth.tfm_roles.includes(roles.tfm[i])) {
					return auth;
				}
			}
		}
	}

	return auth;
}

function assertUnauthorized(req, res) {
	const auth = checkAuthorization(req, res);

	// error already written
	if (auth === undefined) { return false; }

	if (!!auth) {
		writeError(
			res, 403,
			"You can't use a session in this endpoint."
		);
		return false;
	}

	return true;
}

function normalizeName(name) {
	name = name.replace("-", "#", 1).replace("%23", "#", 1);
	return name.includes("#") ? name : `${name}#0000`;
}

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

module.exports = {
	service: service,

	rankableFields: [
		"rounds",
		"cheese",
		"first",
		"bootcamp",
		"stats",
		"shaman",
		"survivor",
		"racing",
		"defilante",
		"overall",
	],
	cfmRoles: [
		"dev",
		"admin",
		"mod",
		"translator",
		"trainee",
	],

	SESSION_KEY: SESSION_KEY,
	REFRESH_KEY: REFRESH_KEY,
	BOT_KEY: BOT_KEY,
	writeError: writeError,
	handleServiceError: handleServiceError,
	handleBasicServiceResult: handleBasicServiceResult,
	getPagination: getPagination,
	checkAuthorization: checkAuthorization,
	assertAuthorization: assertAuthorization,
	assertUnauthorized: assertUnauthorized,
	normalizeName: normalizeName,
	checkPeriod: checkPeriod,
};
