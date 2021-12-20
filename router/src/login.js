"use strict";

const ms = require("ms");
const jwt = require("jsonwebtoken");
const express = require("express");
const {
	service,
	SESSION_KEY,
	REFRESH_KEY,
	BOT_KEY,
	assertUnauthorized,
	writeError,
	handleServiceError,
	normalizeName,
} = require("./common");
const { checkRateLimit } = require("./ratelimits");

const router = express.Router();

router.post("/session", async (req, res) => {
	// Someone wants to create a new session
	const success = assertUnauthorized(req, res);
	if (!success) { return; }

	let request = {};
	let bucket = "session";
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
		bucket = "login";
		// They want to use user and password
		let remind = false;
		if (typeof req.body.remind == "boolean") {
			remind = !!req.body.remind;
		}

		request.uses = "credentials";
		request.user = normalizeName(req.body.user);
		request.password = req.body.password;
		request.remind = remind;

	} else if (typeof req.body.ticket == "string") {
		// Coming from transformice's ingame verification system
		request.uses = "ticket";
		request.ticket = req.body.ticket;

	} else if (
		typeof req.body.client_id == "number" &&
		typeof req.body.token == "string"
	) {
		request.uses = "bot-token";
		request.client_id = req.body.client_id;
		request.token = req.body.token;

		let duration;
		if (typeof req.body.duration == "number") {
			duration = req.body.duration * 1000;
		} else if (typeof req.body.duration == "string") {
			duration = ms(req.body.duration);
		} else {
			duration = ms("4h");
		}

		if (duration < ms("1m")) {
			duration = ms("1m");
		} else if (duration > ms("1d")) {
			duration = ms("1d");
		}

		request.duration = ms(duration);

	} else {
		// tf are they trying to use lol
		return writeError(res, 400);
	}

	const result = await checkRateLimit(req, res, bucket);
	if (!result) { return; }

	// Send the data to the auth service
	service.request("auth", "new-session", request, (result) => {
		if (result.type == "content") {
			// The service takes some time to fulfill a response
			// (due to hashing); so it opens a stream first
			if (!result.content.success) {
				// Something went wrong
				if (result.content.err == "InvalidCredentials") {
					writeError(
						res,
						401,
						result.content.err_msg,
						result.content.translation_key
					);
				}
				return;
			}

			// Everything is OK
			let response = {
				success: true,
			};

			if (typeof req.body.ticket == "string") {
				response.has_password = result.content.has_password;
			}

			const bot = result.content.bot;
			let refresh = result.content.refresh;
			let session = result.content.session;
			if (!!refresh) {
				// The service wants us to sign a new refresh token
				let duration = refresh.duration;
				delete refresh.duration;

				if (bot) {
					response.duration = Math.floor(ms(duration) / 1000);
				}

				response.refresh = jwt.sign(refresh, REFRESH_KEY, {
					expiresIn: duration
				});
			}
			// Sign a new session
			response.session = jwt.sign(session, bot ? BOT_KEY : SESSION_KEY, {
				expiresIn: "30m"
			});

			res.send(response);

		} else if (!!result.err) {
			// The request is invalid!!
			if (result.err == "rejected") {
				if (result.type == "ExpiredToken" ||
					result.type == "InvalidCredentials") {
					writeError(
						res,
						401,
						result.args[0],
						result.kwargs.translation_key
					);
					return;
				}
			}
			handleServiceError(res, result);
		}
	});
});

module.exports = router;
