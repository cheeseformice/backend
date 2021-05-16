"use strict";

const jwt = require("jsonwebtoken");
const express = require("express");
const {
	service,
	SESSION_KEY,
	REFRESH_KEY,
	VALIDATE_KEY,
	assertUnauthorized,
	writeError,
	handleServiceError,
	normalizeName,
	checkRateLimit,
} = require("./common");

const router = express.Router();
const users = express.Router();

router.post("/session", (req, res) => {
	// Someone wants to create a new session
	const success = assertUnauthorized(req, res);
	if (!success) { return; }

	let request = {};
	if (typeof req.body.refresh == "string") {
		// They want to use a refresh token
		let refresh;
		try {
			// Verify it is valid first
			refresh = jwt.verify(req.body.refresh, REFRESH_KEY);
		} catch(err) {
			// Looks like it isn't!
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

		request.uses = "refresh";
		request.refresh = refresh;

	} else if (
		typeof req.body.user == "string" &&
		typeof req.body.password == "string"
	) {
		// They want to use user and password
		let remind = false;
		if (typeof req.body.remind == "boolean") {
			remind = !!req.body.remind;
		}

		request.uses = "credentials";
		request.user = req.body.user;
		request.password = req.body.password;
		request.remind = remind;

	} else {
		// tf are they trying to use lol
		return writeError(res, 400);
	}

	// Send the data to the auth service
	service.request("auth", "new-session", request, (result) => {
		if (result.type == "content") {
			// The service takes some time to fulfill a response
			// (due to hashing); so it opens a stream first
			if (!result.content.success) {
				// Something went wrong
				if (result.content.err == "InvalidCredentials") {
					writeError(res, 401, result.content.err_msg);
				}
				return;
			}

			// Everything is OK
			let response = {};

			let refresh = result.content.refresh;
			let session = result.content.session;
			if (!!refresh) {
				// The service wants us to sign a new refresh token
				let duration = refresh.duration;
				delete refresh.duration;

				response.refresh = jwt.sign(refresh, REFRESH_KEY, {
					expiresIn: duration
				});
			}
			// Sign a new session
			response.session = jwt.sign(session, SESSION_KEY, {
				expiresIn: "30m"
			});

			res.send(response);

		} else if (!!result.err) {
			// The request is invalid!!
			if (result.err == "rejected") {
				if (result.type == "ExpiredToken" ||
					result.type == "InvalidCredentials") {
					writeError(res, 401, result.args[0]);
					return;
				}
			}
			handleServiceError(res, result);
		}
	});
});

function verificationRateLimits(req, res) {
	return new Promise((resolve, reject) => {
		const { x_real_ip } = req.headers;

		let { name } = req.params;
		name = normalizeName(name);

		// 2 requests every 10 minutes per IP
		checkRateLimit(`rate:verif:ip:${x_real_ip}`, 2, 60 * 10)
			.then((success) => {
				if (!success) {
					writeError(
						res, 429,
						"You can't request more than two verification " +
						"messages in 10 minutes."
					);
					reject();
					return;
				}

				checkRateLimit(`rate:verif:name:${name}`, 1, 60 * 5)
					.then((success) => {
						if (!success) {
							writeError(
								res, 429,
								"That user already received a message in " +
								"the past 5 minutes."
							);
							reject();
							return;
						}
						resolve(name);
					})
					.catch((err) => {
						console.error(err);
						writeError(res, 500);
						reject();
					});
			})
			.catch((err) => {
				console.error(err);
				writeError(res, 500);
				reject();
			});
	});
}

function updatePassword(method) {
	// Someone wants to update a password (recover my password or register)
	return (req, res) => {
		verificationRateLimits(req, res).then((name) => {
			const success = assertUnauthorized(req, res);
			if (!success) { return; }

			// Send the request to the auth service
			service.request("auth", "new-validation", {
				user: name,
				method: method
			}, (result) => {
				if (result.type == "simple") {
					// Everything is ok
					// Sign a new validation token
					const token = jwt.sign({
						name: name.toLowerCase(),
						user: result.content.user,
						refresh: result.content.refresh
					}, VALIDATE_KEY, {
						expiresIn: "5m"
					});

					var title
					if (method == "register") {
						title = "Account validation";
					} else {
						title = "Password recovery";
					}

					// Tell the validation bot to send a forum PM
					service.redis.publish("bots:validation", JSON.stringify({
						target: name,
						title: title,
						content: token,
					}));

					// Return an empty response to signal everything is ok
					res.send({});

				} else if (!!result.err) {
					if (
						result.err == "rejected" &&
						result.type == "WrongMethod"
					) {
						// Trying to register an already registered player
						// or recovering a password of an unregistered one
						writeError(
							res, 400,
							"Can not perform this action in this user."
						);
						return;
					}
					handleServiceError(res, result);
				}
			});
		}).catch(() => {});
	};
}
users.post("/:name", updatePassword("register"));
users.post("/:name/password", updatePassword("password"));

function checkToken(req, res, token, password) {
	// Check if a validation token is... valid!
	try {
		// Verify the signature
		token = jwt.verify(token, VALIDATE_KEY);
	} catch(err) {
		// Looks like it is incorrect!
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

	let { name } = req.params;
	name = normalizeName(name);

	if (name.toLowerCase() != token.name) {
		// The token is not for this user
		writeError(res, 401, "Invalid token");
		return;
	}

	service.request(
		"auth",
		// If we need to also change the password, we do that
		!!password ? "use-validity" : "is-valid",
		!!password ? {password: password, token: token} : token,
		(result) => {
			if (result.type == "simple") {
				// The action was ok
				// (either checking validity or using it)
				res.send({});

			} else if (!!result.err) {
				// Something went wrong...
				if (
					result.err == "rejected" &&
					result.type == "ExpiredToken"
				) {
					writeError(res, 401, "Token has expired");
					return;
				}
				handleServiceError(res, result);
			}
		}
	);
}

users.get("/:name/validation", (req, res) => {
	// Someone wants to check if a validation token is still valid
	const success = assertUnauthorized(req, res);
	if (!success) { return; }

	checkToken(req, res, req.query.token, null);
});

users.post("/:name/validation", (req, res) => {
	// Someone wants to use a validation token
	const success = assertUnauthorized(req, res);
	if (!success) { return; }

	checkToken(req, res, req.body.token, req.body.password);
});

router.use("/users", users);

module.exports = router;
