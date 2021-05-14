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
		INFRA_HOST: process.env.INFRA_HOST,
		INFRA_PORT: process.env.INFRA_PORT,
		INFRA_DEAD: process.env.INFRA_DEAD,
		INFRA_HEARTBEAT: process.env.INFRA_HEARTBEAT,
		INFRA_PING_DELAY: process.env.INFRA_PING_DELAY,
		INFRA_PING_TIMEOUT: process.env.INFRA_PING_TIMEOUT,
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


const helmet = require("helmet");
const cors = require("cors");
const expressWs = require("express-ws");
const { writeError } = require("./src/common");

const app = express();

// Middleware
expressWs(app);
app.use(helmet());
app.use(cors());
app.use(express.json());
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
	[false, "login"],
	[false, "lookup"],
	[false, "profile"],
	[false, "session"],
	[false, "tfm"],
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
