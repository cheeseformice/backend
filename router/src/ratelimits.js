const { writeError, service } = require("./common");

const buckets = {
  session: {
    paramType: "ip",
    maxUses: 2,
    expires: 5 * 60,
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
      const { x_real_ip } = req.headers;
      param = x_real_ip;
    }

		service.redis.get(`rate:${bucket.paramType}:${bucketName}:${param}`, (err, uses) => {
			if (!!err) {
        console.error(err);
        writeError(res, 500);
        reject(err);
				return;
			}

			if (!!uses && uses >= bucket.maxUses) {
        writeError(res, 429, `Max requests for bucket '${bucketName}' exceeded`);
				resolve(false);
				return;
			}

			if (!uses) {
				service.redis.set(bucketName, 1);
				service.redis.expire(bucketName, bucket.expires);
			} else {
				service.redis.incr(bucketName);
			}

			resolve(true);
		});
	});
}

module.exports = {
  buckets: buckets,
  checkRateLimit: checkRateLimit
}