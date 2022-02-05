const { writeError, service, checkAuthorization } = require("./common");

const buckets = {
  session: {
    paramType: "ip",
    maxUses: 15,
    expires: 1 * 60,
  },

  login: {
    paramType: "ip",
    maxUses: 15,
    expires: 1 * 60,
  },

  password: {
    paramType: "user",
    maxUses: 3,
    expires: 10 * 60,
  },

  dressroomPNG: {
    paramType: "bot",
    maxUses: 1,
    expires: 3,
    botOwner: false,
  },
}

const checkRateLimit = (req, res, bucketName, param) => {
	return new Promise((resolve, reject) => {
    const bucket = buckets[bucketName];

    if (!bucket) {
      reject(`unknown bucket: ${bucketName}`);
      return;
    }

    if (bucket.paramType === "ip") {
      param = req.headers["x-real-ip"];
    } else if (bucket.paramType === "user") {
      const user = checkAuthorization(req, res);
      if (!user) {
        resolve(false);
        return;
      }
      param = user.user; // user id
    } else if (bucket.paramType === "bot") {
      const bot = checkAuthorization(req, res, true);
      if (!bot) {
        resolve(false);
        return;
      }
      param = bucket.botOwner ? bot.owner : bot.bot;
    }

    const key = `rate:${bucket.paramType}:${bucketName}:${param}`;
		service.redis.get(key, (err, uses) => {
			if (!!err) {
        console.error(err);
        writeError(res, 500, null, "internal");
        reject(err);
				return;
			}

			if (!!uses && uses >= bucket.maxUses) {
        writeError(res, 429, `Max requests for bucket '${bucketName}' exceeded`, "calmDown");
				resolve(false);
				return;
			}

			if (!uses) {
				service.redis.set(key, 1);
				service.redis.expire(key, bucket.expires);
			} else {
				service.redis.incr(key);
			}

			resolve(true);
		});
	});
}

module.exports = {
  buckets: buckets,
  checkRateLimit: checkRateLimit
}