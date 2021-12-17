const { writeError, service, checkAuthorization } = require("./common");

const buckets = {
  session: {
    paramType: "ip",
    maxUses: 5,
    expires: 5 * 60,
  },

  login: {
    paramType: "ip",
    maxUses: 5,
    expires: 1 * 60,
  },

  password: {
    paramType: "user",
    maxUses: 3,
    expires: 10 * 60,
  }
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