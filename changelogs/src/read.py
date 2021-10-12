from shared.schemas import as_dict
from shared.logs import LogInfo
from typing import Dict


special_cases = {}


def special_case(name):
	def decorator(fnc):
		special_cases[name] = fnc
		return fnc
	return decorator


@special_case("soulmate")
@special_case("tribe")
def schema_log(info: Dict[str, LogInfo], rows: list):
	if info.name == "soulmate":
		prefix = "sm_"
		schema = "BasicPlayer"
	else:
		prefix = "tribe_"
		schema = "BasicTribe"
	id_field = f"{prefix}id"

	used_dates = set()
	store = []
	last = None
	for idx in range(len(rows) - 1, -1, -1):
		row = rows[idx]
		_id = row[id_field]

		if _id == last:
			continue

		last = _id
		value = None
		if _id is not None:
			value = as_dict(schema, row, prefix)

		used_dates.add(row.log_date)
		store.append([row.log_date, value])

	store.reverse()
	return store, used_dates


@special_case("badges")
@special_case("titles")
def list_log(info: Dict[str, LogInfo], rows: list):
	field = (
		"badges" if info.name == "badges"
		else "unlocked_titles"
	)

	used_dates = set()
	obtained = set()
	store = []
	for idx in range(len(rows) - 1, -1, -1):
		row = rows[idx]
		_list = row[field]

		if _list == "":
			# Empty list
			continue

		additions = []
		for item in _list.split(","):
			if item not in obtained:
				additions.append(item)
				obtained.add(item)

		if len(additions) > 0:
			used_dates.add(row.log_date)
			store.append([row.log_date, additions])

	store.reverse()
	return store, used_dates


def read_history(logs_info: Dict[str, LogInfo], rows: list):
	used_dates = set()
	log_stores = []  # Used to replace dates with indices

	logs = {}
	rows_len = len(rows)
	for name, info in logs_info.items():
		if info.fields.special:
			store, dates = special_cases[name](info, rows)

			logs[name] = store
			used_dates = used_dates.union(dates)
			log_stores.append(store)
			continue

		conversions = info.fields.conversions
		log_result = logs[name] = {}
		for _from, to in conversions:
			store = log_result[to] = []
			last = None

			log_stores.append(store)

			# Iterate over rows backwards
			for idx in range(rows_len - 1, -1, -1):
				row = rows[idx]
				value = row[_from]

				if value == last:
					# Remove duplicates, last appearance is kept
					continue

				last = value
				used_dates.add(row.log_date)  # Mark date as used
				store.append([row.log_date, value])

			# The store is reversed after appending items, as this is
			# way faster than doing store.insert(0, item) instead.
			store.reverse()

		if len(conversions) == 1:
			# If this container just holds a single field, just return that
			logs[name] = store

	return logs, used_dates, log_stores
