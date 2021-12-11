"use strict";

const express = require("express");
const {
	service,
	writeError,
	assertAuthorization,
	normalizeName,
	handleServiceError,
	handleBasicServiceResult,
	cfmRoles,
} = require("./common");
const { checkRateLimit } = require("./ratelimits");

const router = express.Router();

router.put("/users/:name/roles", (req, res) => {
	const auth = assertAuthorization(req, res, {
		cfm: ["dev", "admin"]
	});
	if (!auth) { return; }

	let { name } = req.params;
	name = normalizeName(name);

	const isDev = auth.cfm_roles.includes("dev");
	for (var i = 0; i < req.body.roles.length; i++) {
		// Check all roles
		let role = req.body.roles[i];
		if (!cfmRoles.includes(role)) {
			writeError(res, 404, `The role ${role} doesn't exist.`);
			return;
		}

		if (role == "dev") {
			writeError(
				res, 403,
				"New developers have to be appointed through the DB."
			);
			return;
		}

		if (role == "admin" && !isDev) {
			writeError(
				res, 403,
				"New administrators have to be appointed by a developer."
			);
			return;
		}
	}

	// Send the request to the auth service
	service.request(
		"auth", "change-roles",
		{
			user: auth,
			target: name,
			roles: req.body.roles
		}, (result) => {
			if (result.type == "simple") {
				// Everything is ok
				res.status(204).send();
			} else if (!!result.err) {
				// Something went wrong
				if (
					result.err == "rejected" &&
					result.type == "Forbidden"
				) {
					writeError(res, 403, result.args[0]);
					return;
				}
				handleServiceError(res, result);
			}
		}
	);
});

router.all("/users/:id/sanction", (req, res) => {
	const auth = assertAuthorization(req, res, {
		cfm: ["dev", "admin", "mod"]
	});
	if (!auth) { return; }

	let { id } = req.params;
	id = parseInt(id);
	if (isNaN(id)) {
		return writeError(res, 400, "Invalid id");
	}

	let reason;
	if (req.method == "POST") {
		reason = req.query.reason;
		if (!reason) {
			return writeError(res, 400, "Missing reason");
		}
	}

	let procedure;
	switch(req.method) {
		case "GET":
			procedure = "get-sanction";
			break;
		case "POST":
			procedure = "sanction";
			break;
		case "DELETE":
			procedure = "cancel-sanction";
			break;
		default:
			return writeError(res, 400, "Invalid HTTP verb");
	}

	service.request(
		"account", procedure,
		{auth, subject: id, reason},
		(result) => {
			if (result.type == "simple") {
				if (!result.content) {
					res.status(204).send();
				} else {
					res.send(result.content);
				}

			} else if (!!result.err) {
				handleServiceError(res, result);
			}
		}
	);
});

router.post("/@me/password", async (req, res) => {
	if (!await checkRateLimit(req, res, "password")) { return; }

	// Someone wants to change their password
	const auth = assertAuthorization(req, res);
	if (!auth) { return; }

	const { oldPassword, newPassword } = req.body;
	if (!oldPassword || !newPassword) {
		writeError(res, 400, "Missing passwords");
		return;
	}

	service.request(
		"auth", "set-password", { auth, old_password: oldPassword, new_password: newPassword },
		(result) => {
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

				// Everything is ok
				res.status(204).send();
			} else if (!!result.err) {
				// Something went wrong
				handleServiceError(res, result);
			}
		}
	);
})

router.get("/@me", (req, res) => {
	// Someone wants to know their current profile
	const auth = assertAuthorization(req, res);
	if (!auth) { return; }

	// Send the request to the account service,
	// and just send whatever it replies to the user
	service.request(
		"account", "get-me", {auth: auth},
		handleBasicServiceResult(res)
	);
});

router.patch("/@me/privacy", (req, res) => {
	// Someone wants to change their privacy settings
	const auth = assertAuthorization(req, res);
	if (!auth) { return; }

	let fields = Object.keys(req.body);
	for (var i = 0; i < fields.length; i++) {
		// Check every argument
		if (typeof req.body[ fields[i] ] != "boolean") {
			writeError(
				res, 400,
				"Every value must be a boolean"
			);
			return;
		}
	}

	// Send the request to the auth service
	service.request(
		"account", "set-privacy", {
			auth: auth,
			privacy: req.body,
		}, (result) => {
			if (result.type == "simple") {
				// Everything is ok
				res.status(204).send();
			} else if (!!result.err) {
				// Something went wrong
				if (
					result.err == "rejected" &&
					result.type == "UnknownField"
				) {
					writeError(res, 400, result.args[0]);
					return;
				}
				handleServiceError(res, result);
			}
		}
	);
});

module.exports = router;
