"use strict";

const express = require("express");
const os = require("os");
const cluster = require("cluster");

const workersAmount = parseInt(process.env.WORKERS || "1");

function getChildENV(i) {
	return {
		SERVICE_WORKER_ID: i,
		SESSION_KEY: process.env.SESSION_KEY,
		REFRESH_KEY: process.env.REFRESH_KEY,
		VALIDATE_KEY: process.env.VALIDATE_KEY,
		INFRA_ADDR: process.env.INFRA_ADDR,
		INFRA_PING_DELAY: process.env.INFRA_PING_DELAY,
		INFRA_PING_TIMEOUT: process.env.INFRA_PING_TIMEOUT,
		GITHUB_SECRET: process.env.GITHUB_SECRET,
	};
}

process.on("SIGTERM", shutDown);
process.on("SIGINT", shutDown);

if (workersAmount > 1 && cluster.isMaster) {
	const workers = {};

	for (var i = 0; i < workersAmount; i++) {
		const worker = cluster.fork(getChildENV(i));
		workers[worker.process.pid] = i;
	}

	cluster.on("fork", (worker) => {
		const id = workers[worker.process.pid];
		console.log(`spawned worker ${id}`);
	});

	cluster.on("exit", (worker, code, signal) => {
		const id = workers[worker.process.pid];
		workers[worker.process.pid] = undefined;

		console.log(`worker ${id} died (${signal || code})`);

		worker = cluster.fork(getChildENV(id));
		workers[worker.process.pid] = id;
	});

	function shutDown() {
		const pids = Object.keys(workers);

		for (var i = 0; i < pids.length; i++) {
			const worker = workers[ pids[i] ];
			worker.kill("SIGTERM");
		}
	}
	return;
}


const crypto = require("crypto");
const helmet = require("helmet");
const cors = require("cors");
const expressWs = require("express-ws");
const { writeError } = require("./src/common");

const app = express();

// Verify GitHub requests
const secret = process.env.GITHUB_SECRET || "test123";

function getSignature(buf) {
	const hmac = crypto.createHmac("sha256", secret);
	hmac.update(buf, "utf-8");
	return `sha256=${hmac.digest("hex")}`;
}

function verify(req, res, buf, encoding) {
	const received = req.headers["x-hub-signature-256"];

	if (received === undefined) {
		return; // No signature; nothing to validate.
	}

	const expected = getSignature(buf);
	if (expected !== received) {
		req.validSignature = false;
		writeError(res, 400, "Invalid signature.");
		throw new Error("Invalid signature.");
	}
	req.validSignature = true;
}

// Middleware
expressWs(app);
app.use(helmet());
app.use(cors());
app.use(express.json({ verify }));
app.use((err, req, res, next) => {
	if (err instanceof SyntaxError) {
		writeError(res, 400, "invalid json body");
	} else {
		next();
	}
});

// Import all modules
let modules = [
	// [hasPrefix, moduleName],
	[true, "dressroom"],
	[false, "healthcheck"],
	// [false, "login"],
	[false, "lookup"],
	[false, "profile"],
	[false, "session"],
	[false, "tfm"],
	[false, "github"],
];

const api = express.Router();
for (var i = 0; i < modules.length; i++) {
	let [ hasPrefix, moduleName ] = modules[i];
	let router = require(`./src/${moduleName}`);
	api.use(`/${hasPrefix ? moduleName : ""}`, router);
}

app.use("/api", api);

const server = app.listen(80);

function shutDown() {
	server.close();
}
