"use strict";

const express = require("express");
const {
	service,
	writeError,
	handleBasicServiceResult,
} = require("./common");

const router = express.Router();

router.get("/fur/:id", (req, res) => {
	// Someone wants to get a fur SVG
	var { id } = req.params;
	var { color } = req.query;

	// Check the request
	id = parseInt(id);
	color = parseInt(color, 16);

	if (isNaN(id)) {
		return writeError(res, 400, "The given fur is invalid.");
	}
	if (isNaN(color)) { color = null; }

	// Send the request to the dressroom service and return whatever it says
	service.request("dressroom", "fur", {
		fur: id,
		color: color
	}, handleBasicServiceResult(res, "image/svg+xml"));
});

router.get("/costume/:section/:id", (req, res) => {
	// Someone wants to get a costume SVG
	var { section, costume } = req.params;
	var { colors } = req.query;

	// Check the request
	costume = parseInt(costume);
	if (isNaN(costume) || costume < 1) {
		return writeError(res, 400, "The given costume is invalid.");
	}

	// Colors parameter is supposed to be an array. If it is sent many times,
	// then express gives us an array. Otherwise, a string.
	if (!colors) {
		colors = [];
	} else if (typeof colors === "string") {
		colors = [colors];
	}

	for (var i = 0; i < colors.length; i++) {
		// Check every color is valid
		let color = parseInt(colors[i], 16);

		if (isNaN(color)) {
			return writeError(
				res, 400,
				`${colors[i]} doesn't look like a valid color`
			);
		}

		colors[i] = color;
	}

	// Send the request to the dressroom service and return whatever it says
	service.request("dressroom", "costume", {
		section: section,
		costume: costume,
		colors: colors
	}, handleBasicServiceResult(res, "image/svg+xml"));
});

router.get("/mouse/:look", (req, res) => {
	// Someone wants to draw a full mouse
	const { look } = req.params;

	// Parse the look and check the request
	var [ fur, costumes, fur_color ] = look.split(";", 3);

	if (!fur || !costumes) {
		return writeError(res, 400, "The provided look is invalid.");
	}

	fur = parseInt(fur);
	if (isNaN(fur)) {
		return writeError(res, 400, "The given fur is invalid.");
	}

	if (!!fur_color) {
		// The user wants to use a custom fur color
		let parse = parseInt(fur_color, 16);
		if (isNaN(parse)) {
			return writeError(
				res, 400,
				`${fur_color} doesn't look like a valid color.`
			);
		}

		fur_color = parse;
	} else {
		// Use default fur color
		fur_color = null;
	}

	// Check every costume is valid
	costumes = costumes.split(",", 11);
	for (var i = 0; i < costumes.length; i++) {
		var [ costume, colors ] = costumes[i].split("_", 2);

		costume = parseInt(costume);

		if (isNaN(costume) || costume < 0) {
			// The costume isn't a valid ID
			return writeError(
				res, 400,
				`${costume} doesn't look like a valid costume.`
			);
		}

		if (costume == 0) {
			// ID 0 means nothing in this section, so just ignore
			costumes[i] = [0, []];
			continue;
		}

		if (!!colors) {
			// This costume has custom colors
			colors = colors.split("+", 30); // up to 30 colors lol

			for (var j = 0; j < colors.length; j++) {
				// Check every color is valid
				let color = parseInt(colors[j], 16);

				if (isNaN(color)) {
					return writeError(
						res, 400,
						`${colors[j]} doesn't look like a valid color`
					);
				}

				colors[j] = color;
			}
		} else {
			// No colors.
			colors = [];
		}

		costumes[i] = [costume, colors];
	}

	// Send the request to the dressroom service and return whatever it says
	service.request("dressroom", "mouse", {
		fur: fur,
		fur_color: fur_color,
		costumes: costumes
	}, handleBasicServiceResult(res, "image/svg+xml"));
});

module.exports = router;
