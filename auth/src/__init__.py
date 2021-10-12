import os

from common import service

# Initialize modules
import roles  # noqa
import session  # noqa


if __name__ == "__main__":
	service.run(workers=int(os.getenv("WORKERS", "2")))
