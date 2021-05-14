"use strict";

const jwt = require("jsonwebtoken");
const Service = require("./shared/jsservice/service");
const service = new Service(
	"router", true,
	parseInt(process.env.SERVICE_WORKER_ID || "0")
);

const SESSION_KEY = process.env.SESSION_KEY || "some long ass string lol";
const REFRESH_KEY = process.env.REFRESH_KEY || "another long ass string lol";
const VALIDATE_KEY = process.env.VALIDATE_KEY || "one more long ass string lol";

if (!process.env.SESSION_KEY ||
	!process.env.REFRESH_KEY ||
	!process.env.VALIDATE_KEY) {
	console.warn(
		"One or many of the required JWT aren't defined. Using default."
	);
}

const statusReasons = {
	400: "Bad request",
	401: "Unauthorized",
	404: "Not found",
	429: "Too many requests",
	500: "Internal server error",
	503: "Service unavailable",
};

function writeError(res, status, message) {
	const reason = statusReasons[status] || "";
	const result = { status: status };

	if (!!reason) { result.error = reason; }
	if (!!message) { result.message = message; }

	res.status(status).send(result);
}

function handleServiceError(res, result) {
	switch (result.err) {
		case "unavailable":
		case "timeout":
			writeError(res, 503, "The service is unavailable");
			break;

		case "rejected":
			if (result.type == "NotFound") {
				writeError(res, 404, result.args[0]);
			} else if (result.type == "NotImplemented") {
				writeError(res, 500, result.args[0]);
			} else {
				writeError(res, 500);
			}
			break;

		case "internal":
		default:
			writeError(res, 500);
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

function checkAuthorization(req, res) {
	const { authorization } = req.headers;

	if (!authorization) { return null; }

	if (!authorization.toLowerCase().startsWith("bearer ")) {
		writeError(res, 401, "Invalid token");
		return;
	}

	const [bearer, token] = authorization.split(" ", 2);

	try {
		return jwt.verify(token, SESSION_KEY);
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
	const auth = checkAuthorization(req, res);

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

	return;
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

function checkRateLimit(bucket, maxUses, expiration) {
	return new Promise((resolve, reject) => {
		service.redis.get(bucket, (err, uses) => {
			if (!!err) {
				reject(err);
				return;
			}

			if (!!uses && uses >= maxUses) {
				resolve(false);
				return;
			}

			if (!uses) {
				service.redis.set(bucket, 1);
				service.redis.expire(bucket, expiration);
			} else {
				service.redis.incr(bucket);
			}

			resolve(true);
		});
	});
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
	],

	SESSION_KEY: SESSION_KEY,
	REFRESH_KEY: REFRESH_KEY,
	VALIDATE_KEY: VALIDATE_KEY,
	writeError: writeError,
	handleServiceError: handleServiceError,
	handleBasicServiceResult: handleBasicServiceResult,
	getPagination: getPagination,
	checkAuthorization: checkAuthorization,
	assertAuthorization: assertAuthorization,
	assertUnauthorized: assertUnauthorized,
	normalizeName: normalizeName,
	checkRateLimit: checkRateLimit,
};
