import configparser

from shared.models import player, tribe_stats
from sqlalchemy import and_


qualification = configparser.ConfigParser()
qualification.read("/src/shared/qualification.cfg")
qualification = qualification["req"]


def generate_qualification_query(tbl):
	qualification_query = []
	for key, minimum in qualification.items():
		attr = getattr(tbl.c, key)
		if attr is None:
			raise Exception("Malformed qualification config")

		qualification_query.append(attr >= int(minimum))
	qualification_query = and_(*qualification_query)


player_qualification_query = generate_qualification_query(player)
tribe_qualification_query = generate_qualification_query(tribe_stats)


def can_qualify(row) -> bool:
	for key, minimum in qualification.items():
		if (getattr(row, key) or 0) < int(minimum):
			return False
	return True
