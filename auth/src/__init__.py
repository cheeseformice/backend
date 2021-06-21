import os

from common import service

# Initialize modules
import privacy  # noqa
import roles  # noqa
import sanction  # noqa
import session  # noqa
import validation  # noqa


if __name__ == "__main__":
	service.run(workers=int(os.getenv("WORKERS", "2")))
