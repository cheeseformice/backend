"use strict";

const zlib = require("zlib");
const { pipeline } = require("stream");
const http = require("http");
const express = require("express");
const {
	writeError,
} = require("./common");

const router = express.Router();

const CACHE_EXPIRES = 60 * 60 * 1000; // 1 hour (ms)
const languages = [
	"ab", "af", "am", "ar", "av", "az", "be", "bh", "bm", "bo", "bs", "ca",
	"ch", "co", "cs", "cv", "da", "dv", "ee", "en", "es", "eu", "ff", "fj",
	"fr", "ga", "gl", "gu", "ha", "hi", "hr", "hu", "hz", "id", "ig", "ik",
	"is", "iu", "jv", "kg", "kj", "kl", "kn", "kr", "ku", "kw", "la", "lg",
	"ln", "lt", "lv", "mh", "mk", "mn", "mr", "mt", "na", "ne", "nl", "nr",
	"ny", "oj", "or", "pa", "pl", "pt", "rc", "rn", "ru", "sa", "sd", "sg",
	"si", "sl", "sn", "sq", "ss", "su", "sw", "te", "th", "tk", "tn", "tr",
	"tt", "ty", "uk", "uz", "vi", "wa", "xh", "yo", "zh",
];

var translations = {};
var fieldList = {}; // key is length, value is array with those fields
var maxLength = 0; // max length in a field

function organizeFields() {
	fetchTranslationFile("en").then((fields) => {
		// Organize fields by length for faster pattern lookup
		fields = Object.keys(fields);
		for (var i = 0; i < fields.length; i++) {
			let field = fields[i];

			if (field.length > maxLength) {
				maxLength = field.length;
			}
			if (!fieldList[field.length]) {
				fieldList[field.length] = [field];
			} else {
				fieldList[field.length].push(field);
			}
		}
	});
}

function matchStarting(pattern) {
	if (pattern.length > maxLength) {
		// Nothing to match lol
		return [];
	}

	let fields = [];
	let list = fieldList[pattern.length];
	if (!!list && list.includes(pattern)) {
		// If the pattern itself is a field, add it
		fields.push(pattern);
	}

	for (var length = pattern.length + 1; length < maxLength; length++) {
		// Start checking from fields that have a chance of matching (longer)
		list = fieldList[length];
		if (!list) { continue; }
		for (var i = 0; i < list.length; i++) {
			if (list[i].startsWith(pattern)) {
				fields.push(list[i]);
			}
		}
	}
	return fields;
}

function fetchTranslationFile(language) {
	return new Promise((resolve, reject) => {
		const options = {
			hostname: "transformice.com",
			port: 80,
			path: `/langues/tfm-${language}.gz`,
			method: "GET",
		};
		let file = translations[language];
		if (!!file && !!file.etag) {
			options.headers = {
				"If-None-Match": file.etag
			};
		}

		const req = http.request(options, (res) => {
			if (res.statusCode == 304) {
				// Resource hasn't been modified
				resolve(file.fields);
				return;
			}
			if (res.statusCode == 404) {
				// Not found
				reject(`Uknown language: ${language}`);
			}

			// Resource has been modified: unpack and update locally
			var fields = {};
			translations[language] = {
				cacheExpires: Date.now() + CACHE_EXPIRES,
				etag: res.headers.etag,
				fields: fields,
			};

			// Decompress in stream
			let unzip = zlib.createUnzip();
			res.pipe(unzip);

			let buffer = [];
			unzip.on("data", (data) => {
				buffer.push(data.toString());
			});

			unzip.on("end", () => {
				if (!buffer) {
					resolve(fields);
					return;
				}

				// The content is now decompressed: parse it
				let content = buffer.join("").split("\n-\n");

				for (var i = 0; i < content.length; i++) {
					let row = content[i];
					let index = row.indexOf("=");
					let field = row.substring(0, index);
					let value = row.substring(index + 1);

					if (!!field) {
						fields[field] = value;
					}
				}
				resolve(fields);
			});

			unzip.on("error", reject);
		});

		req.on("error", reject);
		req.end();
	});
}

function getTranslationFile(language) {
	return new Promise((resolve, reject) => {
		let file = translations[language];
		if (!file || Date.now() >= file.cacheExpires) {
			fetchTranslationFile(language).then(resolve).catch(reject);
		} else {
			resolve(file.fields);
		}
	});
}

function handleTranslationRequest(req, res, fields) {
	let { language } = req.params;
	language = language.toLowerCase();

	if (!languages.includes(language)) {
		writeError(res, 400, "Invalid language.");
		return;
	}

	if (!fields) {
		fields = [];
	} else if (typeof fields == "string") {
		fields = [fields];
	} else if (!(fields instanceof Array)) {
		writeError(res, 400);
		return;
	}

	const { start, all } = req.query;
	if (all == "true") {
		getTranslationFile(language).then((fileFields) => {
			res.send(fileFields);
		});
		return;
	}

	if (!!start) {
		fields.push(...matchStarting(start));
	}

	getTranslationFile(language).then((fileFields) => {
		let result = {};
		for (var i = 0; i < fields.length; i++) {
			result[ fields[i] ] = fileFields[ fields[i] ];
		}

		res.send(result);
	});
}
router.get("/translation/:language", (req, res) => {
	let { field } = req.query;
	return handleTranslationRequest(req, res, field);
});
router.post("/translation/:language", (req, res) => {
	return handleTranslationRequest(req, res, req.body);
});

organizeFields();

module.exports = router;
