import os
import asyncio

from collections import namedtuple

from shared.pyservice import Service

from shared.models import roles, player, tribe, player_privacy, \
	player_changelog, member_changelog, tribe_changelog
from shared.schemas import as_dict

from aiomysql.sa import create_engine
from sqlalchemy import desc
from sqlalchemy.sql import select


class env:
	cfm_ip = os.getenv("DB_IP", "cfmdb")
	cfm_user = os.getenv("DB_USER", "test")
	cfm_pass = os.getenv("DB_PASS", "test")
	cfm_db = os.getenv("DB", "api_data")


service = Service("changelogs")


def first_item(item):
	return item[0]


@service.event
async def on_boot(new):
	global service
	service = new

	service.db = await create_engine(
		host=env.cfm_ip, port=3306,
		user=env.cfm_user, password=env.cfm_pass,
		db=env.cfm_db, loop=service.loop,
		autocommit=True
	)

	service.loop.create_task(ping_db())


async def ping_db():
	while True:
		async with service.db.acquire() as conn:
			await conn.connection.ping()

		await asyncio.sleep(60.0)


LogInfo = namedtuple("LogInfo", "name public in_member fields force_hide")
player_logs_info = {
	# Fields set to None means that it is a special case
	# Fields set to a tuple of length one means it is a single value
	# Fields set to a tuple of tuples means it is an Object
	"names": LogInfo(
		name="names", public=False, in_member=False, fields=("name",),
		force_hide=True
	),
	"soulmate": LogInfo(
		name="soulmate", public=False, in_member=True, fields=None,
		force_hide=False
	),
	"tribe": LogInfo(
		name="tribe", public=False, in_member=True, fields=None,
		force_hide=False
	),
	"look": LogInfo(
		name="look", public=False, in_member=False, fields=("look",),
		force_hide=True
	),
	"badges": LogInfo(
		name="badges", public=True, in_member=False, fields=None,
		force_hide=True
	),
	"titles": LogInfo(
		name="titles", public=True, in_member=False, fields=None,
		force_hide=False
	),
	"shaman": LogInfo(
		name="shaman", public=True, in_member=False, fields=(
			("experience", "experience"),
			("shaman_cheese", "cheese"),
			("saved_mice", "saves_normal"),
			("saved_mice_hard", "saves_hard"),
			("saved_mice_divine", "saves_divine"),
			("score_shaman", "score"),
		),
		force_hide=False
	),
	"normal": LogInfo(
		name="normal", public=True, in_member=False, fields=(
			("round_played", "rounds"),
			("cheese_gathered", "cheese"),
			("first", "first"),
			("bootcamp", "bootcamp"),
			("score_stats", "score"),
			("score_overall", "overall_score"),
		),
		force_hide=False
	),
	"survivor": LogInfo(
		name="survivor", public=True, in_member=False, fields=(
			("survivor_round_played", "rounds"),
			("survivor_mouse_killed", "killed"),
			("survivor_shaman_count", "shaman"),
			("survivor_survivor_count", "survivor"),
			("score_survivor", "score"),
		),
		force_hide=False
	),
	"racing": LogInfo(
		name="racing", public=True, in_member=False, fields=(
			("racing_round_played", "rounds"),
			("racing_finished_map", "finished"),
			("racing_first", "first"),
			("racing_podium", "podium"),
			("score_racing", "score"),
		),
		force_hide=False
	),
	"defilante": LogInfo(
		name="defilante", public=True, in_member=False, fields=(
			("defilante_round_played", "rounds"),
			("defilante_finished_map", "finished"),
			("defilante_points", "points"),
			("score_defilante", "score"),
		),
		force_hide=False
	),
}
tribe_logs_info = {
	"members": LogInfo(
		name="members", public=True, in_member=False, fields=("members",),
		force_hide=False
	),
	"active": LogInfo(
		name="active", public=True, in_member=False, fields=("active",),
		force_hide=False
	),
	"shaman": LogInfo(
		name="shaman", public=True, in_member=False, fields=(
			("shaman_cheese", "cheese"),
			("saved_mice", "saves_normal"),
			("saved_mice_hard", "saves_hard"),
			("saved_mice_divine", "saves_divine"),
			("score_shaman", "score"),
		),
		force_hide=False
	),
	"normal": player_logs_info["normal"],
	"survivor": player_logs_info["survivor"],
	"racing": player_logs_info["racing"],
	"defilante": player_logs_info["defilante"],
}


def interpret_logs(logs_req, enum):
	logs = {}

	for idx, log in enumerate(enum.values()):
		if logs_req & (2 ** idx):
			logs[log.name] = {
				"public": log.public and not log.force_hide
			}

	return logs


def read_history(
	logs, result, to_read,
	unused_dates, to_fix,
	special_case=None
):
	result_len = len(result)
	for log in to_read:
		if log.fields is None:
			if special_case is not None:
				special_case(
					log, logs, result, result_len,
					unused_dates, to_fix
				)
			continue

		is_single = len(log.fields) == 1
		if is_single:
			to_check = log.fields
		else:
			to_check = map(first_item, log.fields)

		# Check all fields
		data = {}
		for field in to_check:
			store = data[field] = []
			last = None
			for idx in range(result_len - 1, -1, -1):
				row = result[idx]
				value = getattr(row, field)

				if value == last:
					# Same value as the last one. Ignore.
					continue

				if row.log_date in unused_dates:
					unused_dates.remove(row.log_date)

				last = value

				entry = [row.log_date, value]
				store.append(entry)
				to_fix.append(entry)

			store.reverse()

		if is_single:
			logs[log.name]["logs"] = data[log.fields[0]]
		else:
			for field, rename in log.fields:
				logs[log.name][rename] = data[field]


def player_history_special_case(
	log, logs, result, result_len,
	unused_dates, to_fix
):
	if log.name in ("badges", "titles"):
		# No need to repeat the full list all the time.
		# Every entry means items obtained that day, except in
		# the last entry, that means all the items the player
		# had that day.
		obtained = set()
		field = (
			"badges" if log.name == "badges"
			else "unlocked_titles"
		)
		store = logs[log.name]["logs"] = []

		for idx in range(result_len - 1, -1, -1):
			row = result[idx]
			value = getattr(row, field)
			if value == "":
				continue

			value_store = []
			for item in value.split(","):
				if item not in obtained:
					value_store.append(item)
					obtained.add(item)

			if value_store:
				if row.log_date in unused_dates:
					unused_dates.remove(row.log_date)

				entry = [row.log_date, value_store]
				store.append(entry)
				to_fix.append(entry)

		store.reverse()


def fix_dates(unused_dates, all_dates, to_fix):
	if unused_dates:
		for idx in range(len(all_dates) - 1, -1, -1):
			date = all_dates[idx]
			if date in unused_dates:
				del all_dates[idx]

	for entry in to_fix:
		entry[0] = all_dates.index(entry[0])

	for idx in range(len(all_dates)):
		all_dates[idx] = all_dates[idx].strftime("%Y-%m-%dT%H:%M:%SZ")


@service.on_request("player")
async def player_logs(request):
	user, logs_req = request.id, request.logs
	offset, limit = request.offset, request.limit
	auth = request.auth

	logs = interpret_logs(logs_req, player_logs_info)
	async with service.db.acquire() as conn:
		# Fetch player ID, name and privacy settings
		result = await conn.execute(
			select(
				player,
				player_privacy,

				roles.c.cfm.label("cfm_roles"),
				roles.c.tfm.label("tfm_roles"),
			)
			.select_from(
				player
				.outerjoin(player_privacy, player_privacy.c.id == player.c.id)
				.outerjoin(roles, roles.c.id == player.c.id)
			)
			.where(player.c.id == user)
		)
		row = await result.first()

		if row is None:
			return await request.reject("NotFound", "Player not found")

		response = as_dict("BasicPlayer", row)

		# Check which logs this user has permission to read and which
		# tables we need to fetch
		read_player, read_member = [], []
		privileged = auth is not None and auth["user"] == user

		for name, data in logs.items():
			public = getattr(row, name)
			if public is None:
				public = data["public"]
			else:
				data["public"] = public

			log = player_logs_info[name]
			if (privileged or public) and not log.force_hide:
				if not log.in_member:
					read_player.append(log)
				else:
					read_member.append(log)

		results = []
		# Fetch log information
		if read_player:
			result = await conn.execute(
				select(player_changelog)
				.where(player_changelog.c.id == user)
				.order_by(desc(player_changelog.c.log_id))
				.offset(offset)
				.limit(limit)
			)
			player_data = await result.fetchall()
			results.append(player_data)

		if read_member:
			result = await conn.execute(
				select(
					member_changelog,

					player.c.id.label("sm_id"),
					player.c.name.label("sm_name"),

					tribe.c.id.label("tribe_id"),
					tribe.c.name.label("tribe_name"),
				)
				.select_from(
					member_changelog
					.outerjoin(
						player,
						player.c.id == member_changelog.c.id_spouse
					)
					.outerjoin(
						tribe,
						tribe.c.id == member_changelog.c.id_tribe
					)
				)
				.where(member_changelog.c.id_member == user)
				.order_by(desc(member_changelog.c.log_id))
				.offset(offset)
				.limit(limit)
			)
			member_data = await result.fetchall()
			results.append(member_data)

	# Store unused dates and dates to fix
	to_fix = []
	all_dates = []
	unused_dates = set()
	for rows in results:
		for row in rows:
			all_dates.append(row.log_date)
			unused_dates.add(row.log_date)

	# Now parse all the data
	if read_player:
		read_history(
			logs, player_data, read_player,
			unused_dates, to_fix,
			player_history_special_case
		)

	if read_member:
		member_data_len = len(member_data)
	for log in read_member:
		store = logs[log.name]["logs"] = []
		is_soulmate = log.name == "soulmate"

		last = None
		for idx in range(member_data_len - 1, -1, -1):
			row = player_data[idx]
			_id = row.sm_id if is_soulmate else row.tribe_id

			if _id == last:
				# Same value as the last one. Ignore.
				continue

			if row.log_date in unused_dates:
				unused_dates.remove(row.log_date)

			last, value = _id, None
			if _id is not None:
				if is_soulmate:
					value = as_dict("BasicPlayer", row, "sm_")
				else:
					value = as_dict("BasicTribe", row, "tribe_")

			entry = [row.log_date, value]
			store.append(entry)
			to_fix.append(entry)

		store.reverse()

	fix_dates(unused_dates, all_dates, to_fix)
	response["dates"] = all_dates
	response.update(logs)
	await request.send(response)


@service.on_request("tribe")
async def tribe_logs(request):
	tribe_id, logs_req = request.id, request.logs
	offset, limit = request.offset, request.limit

	logs = interpret_logs(logs_req, tribe_logs_info)
	async with service.db.acquire() as conn:
		result = await conn.execute(
			select(tribe)
			.where(tribe.c.id == tribe_id)
		)
		row = await result.first()

		if row is None:
			return await request.reject("NotFound", "Tribe not found")

		response = as_dict("BasicTribe", row)
		if not logs:
			response["dates"] = []
			return await request.send(response)

		# Check which logs this user has permission
		to_read = []
		for name, data in logs.items():
			if data["public"]:
				to_read.append(tribe_logs_info[name])

		result = await conn.execute(
			select(tribe_changelog)
			.where(tribe_changelog.c.id == tribe_id)
			.order_by(desc(tribe_changelog.c.log_id))
			.offset(offset)
			.limit(limit)
		)
		result = await result.fetchall()

	to_fix = []
	all_dates = []
	unused_dates = set()
	for row in result:
		all_dates.append(row.log_date)
		unused_dates.add(row.log_date)

	read_history(
		logs, result, to_read,
		unused_dates, to_fix,
		None
	)

	fix_dates(unused_dates, all_dates, to_fix)
	response["dates"] = all_dates
	response.update(logs)
	await request.send(response)


if __name__ == "__main__":
	service.run(workers=int(os.getenv("WORKERS", "2")))
