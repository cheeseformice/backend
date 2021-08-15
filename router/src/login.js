"use strict";

const jwt = require("jsonwebtoken");
const express = require("express");
const {
	service,
	SESSION_KEY,
	REFRESH_KEY,
	assertUnauthorized,
	writeError,
	handleServiceError,
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

	} else if (typeof req.body.ticket == "string") {
		// Coming from transformice's ingame verification system
		request.uses = "ticket";
		request.ticket = req.body.ticket;

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

			if (typeof req.body.ticket == "string") {
				response.hasPassword = result.content.has_password;
			}

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

module.exports = router;
