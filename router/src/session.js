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

router.get("/@me/privacy", (req, res) => {
	// Someone wants to know their current privacy settings
	const auth = assertAuthorization(req, res);
	if (!auth) { return; }

	// Send the request to the auth service,
	// and just send whatever it replies to the user
	service.request(
		"auth", "get-privacy", {auth: auth},
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
		"auth", "set-privacy", {
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
