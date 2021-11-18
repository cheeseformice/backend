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
	"ad", "ae", "af", "ag", "ai", "al", "am", "an", "ao", "ar", "as", "at",
	"au", "aw", "ax", "az", "ba", "bb", "bd", "be", "bf", "bg", "bh", "bi",
	"bj", "bm", "bn", "bo", "br", "bs", "bt", "bv", "bw", "by", "bz", "ca",
	"cc", "cd", "cf", "cg", "ch", "ci", "ck", "cl", "cm", "cn", "co", "cr",
	"cs", "cu", "cv", "cx", "cy", "cz", "de", "dj", "dk", "dm", "do", "dz",
	"ec", "ee", "eg", "eh", "er", "es", "et", "fi", "fj", "fk", "fm", "fo",
	"fr", "ga", "gb", "gd", "ge", "gf", "gh", "gi", "gl", "gm", "gn", "gp",
	"gq", "gr", "gs", "gt", "gu", "gw", "gy", "hk", "hm", "hn", "hr", "ht",
	"hu", "id", "ie", "il", "in", "io", "iq", "ir", "is", "it", "jm", "jo",
	"jp", "ke", "kg", "kh", "ki", "km", "kn", "kp", "kr", "kw", "ky", "kz",
	"la", "lb", "lc", "li", "lk", "lr", "ls", "lt", "lu", "lv", "ly", "ma",
	"mc", "md", "me", "mg", "mh", "mk", "ml", "mm", "mn", "mo", "mp", "mq",
	"mr", "ms", "mt", "mu", "mv", "mw", "mx", "my", "mz", "na", "nc", "ne",
	"nf", "ng", "ni", "nl", "no", "np", "nr", "nu", "nz", "om", "pa", "pe",
	"pf", "pg", "ph", "pk", "pl", "pm", "pn", "pr", "ps", "pt", "pw", "py",
	"qa", "re", "ro", "rs", "ru", "rw", "sa", "sb", "sc", "sd", "se", "sg",
	"sh", "si", "sj", "sk", "sl", "sm", "sn", "so", "sr", "st", "sv", "sy",
	"sz", "tc", "td", "tf", "tg", "th", "tj", "tk", "tl", "tm", "tn", "to",
	"tr", "tt", "tv", "tw", "tz", "ua", "ug", "um", "us", "uy", "uz", "va",
	"vc", "ve", "vg", "vi", "vk", "vn", "vu", "wf", "ws", "xx", "ye", "yt",
	"za", "zm", "zw",
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
