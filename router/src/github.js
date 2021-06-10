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
	if (check_run.name !== "Download and publish dressroom assets") { return; }
	if (check_run.conclusion !== "success") { return; }

	// New dressroom assets have been published.
	// Let's notify every dressroom worker!
	const workers = service.otherWorkers.dressroom;
	if (!workers) {
		console.error("No dressroom workers in network?");
		return;
	}

	// Signal the container to download and prepare the new assets
	service.request("dressroom", "prepare-assets", {}, (result) => {
		if (result.type == "content") {
			// The service opens a stream first so the request doesn't die
			// Once it is done downloading and preparing, it returns "done"
			if (result.content === "done") {
				// Notify all the dressroom workers to update their cache

				for (var i = 0; i < workers.length; i++) {
					service.send("dressroom", "request", {
						request_type: "update-assets",
						request_id: "0",
					}, workers[i]);
				}
			}

		} else if (!!result.err) {
			console.error(
				"Something went wrong while updating dressroom assets"
			);
		}
	});
};

router.post("/github", (req, res) => {
	const received = req.headers["x-hub-signature-256"];

	if (received === undefined) {
		return writeError(res, 400, "Missing signature.");
	}
	if (!req.validSignature) { return; }
	// If the signature is not undefined, it has been verified
	// by the middleware at index.js

	const repository = req.body.repository;
	const handler = handlers[repository.full_name];

	if (handler === undefined) {
		return writeError(res, 404, "Unknown repository.");
	}

	const event = req.headers["x-github-event"];
	res.status(204).send({});

	if (event === "ping") { return; }

	handler(req, event, req.body);
});

module.exports = router;
