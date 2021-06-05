"use strict";

const express = require("express");

const router = express.Router();
const {
	service,
	writeError,
} = require("./common");

const handlers = {};

handlers["cheeseformice/dressroom-assets"] = (req, event, body) => {
	if (event !== "check_run") { return; }

	const { check_run } = body;
	if (check_run["name"] !== "Download and publish dressroom assets") { return; }
	if (check_run["conclussion"] !== "success") { return; }

	// New dressroom assets have been published.
	// Let's notify every dressroom worker!
	const workers = service.otherWorkers["dressroom"];
	if (!workers) {
		console.error("No dressroom workers in network?");
		return;
	}

	for (var i = 0; i < workers.length; i++) {
		service.send("dressroom", "request", {
			request_type: "update-assets",
			request_id: "0",
		}, workers[i]);
	}
};

router.post("/github", (req, res) => {
	const { x_hub_signature_256 } = req.headers;

	if (x_hub_signature_256 === undefined) {
		return writeError(res, 400, "Missing signature.");
	}
	// If the signature is not undefined, it has been verified
	// by the middleware at index.js

	const { repository } = req.body;
	const handler = handlers[repository.full_name];

	if (handler === undefined) {
		return writeError(res, 404, "Unknown repository.");
	}

	const { x_github_event } = req.headers;
	res.status(204).send({});

	if (x_github_event === "ping") { return; }

	handler(req, x_github_event, req.body);
});

module.exports = router;
