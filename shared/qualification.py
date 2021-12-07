import configparser

from shared.models import player
from sqlalchemy import and_


qualification = configparser.ConfigParser()
qualification.read("/src/shared/qualification.cfg")
qualification = qualification["req"]

qualification_query = []
for key, minimum in qualification.items():
	attr = getattr(player.c, key)
	if attr is None:
		raise Exception("Malformed qualification config")

	qualification_query.append(attr >= int(minimum))
qualification_query = and_(*qualification_query)


def can_qualify(row) -> bool:
	for key, minimum in qualification.items():
		if getattr(row, key, 0) < int(minimum):
			return False
	return True