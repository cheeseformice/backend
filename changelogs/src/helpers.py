from typing import Dict, Tuple
from logs import LogInfo

member_logs = {"soulmate", "tribe"}


def first_item(item):
	return item[0]


def filter_private(logs: Dict[str, LogInfo], settings) -> Dict[str, LogInfo]:
	return {
		name: log_info
		for name, log_info in logs.items()
		if getattr(settings, name, log_info.public)
	}


def check_needs(logs: Dict[str, LogInfo]) -> Tuple[bool]:
	member, total = 0, len(logs)
	for name in logs.keys():
		if name in member_logs:
			member += 1

	needs_player = member < total
	needs_member = member > 0
	return needs_player, needs_member


def fix_dates(used_dates: set, stores: list) -> list:
	date_index = {}
	used_dates = list(used_dates)
	for idx, date in enumerate(used_dates):
		# faster than doing used_dates.index() for every item
		date_index[date] = idx

	for store in stores:
		for entry in store:
			entry[0] = date_index[entry[0]]

	return used_dates
