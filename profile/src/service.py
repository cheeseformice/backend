import os
import asyncio

from shared.pyservice import Service

from datetime import datetime, timedelta
from shared.models import roles, player, player_changelog, player_privacy, \
	stats, tribe, member, tribe_stats, tribe_changelog
from shared.schemas import as_dict

from aiomysql.sa import create_engine
from sqlalchemy import and_, desc, asc, func
from sqlalchemy.sql import select


class env:
	cfm_ip = os.getenv("DB_IP", "cfmdb")
	cfm_user = os.getenv("DB_USER", "test")
	cfm_pass = os.getenv("DB_PASS", "test")
	cfm_db = os.getenv("DB", "api_data")


service = Service("profile")


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


def parse_date(date):
	year, month, day = map(int, date.split("-"))
	return datetime(year=year, month=month, day=day) \
		+ timedelta(days=1)


async def fetch_boundary_log(_id, conn, table, condition, _desc=True):
	result = await conn.execute(
		select(table)
		.order_by(
			desc(table.c.log_id) if _desc else asc(table.c.log_id)
		)
		.where(and_(
			table.c.id == _id,
			condition
		))
		.limit(1)
	)
	return await result.first()


def calculate_difference(is_tribe, end, start):
	check = stats  # comes from shared.models
	if is_tribe:
		check += (
			"members",
			"active",
		)
		check = check[1:]  # ignore experience

	profile_stats = {}
	for stat in check:
		profile_stats[stat] = (end[stat] or 0) - (start[stat] or 0)
	return profile_stats


def null_stats(is_tribe):
	check = stats  # comes from shared.models
	if is_tribe:
		check += (
			"members",
			"active",
		)
		check = check[1:]  # ignore experience

	profile_stats = {}
	for stat in check:
		profile_stats[stat] = 0
	return profile_stats


async def fetch_period(conn, request, table, row):
	period = None
	if row is not None and (request.period_start or request.period_end):
		period_start = None
		start, end = None, None

		if request.period_start is not None:
			date = parse_date(request.period_start)
			start = await fetch_boundary_log(
				row.id, conn, table, table.c.log_date <= date
			)

		if request.period_end is not None:
			date = parse_date(request.period_end)
			end = await fetch_boundary_log(
				row.id, conn, table, table.c.log_date <= date
			)

		if end is None:
			if request.period_end is None:
				# No period end requested, assume current data
				end = row
			else:
				# Period end requested, no data found.
				end = {}

		is_tribe = table == tribe_changelog
		if start is not None:
			profile_stats = calculate_difference(is_tribe, end, start)

		elif request.period_start is None or not request.use_recent:
			# No period start requested, so return stats up to the end point
			profile_stats = end

		else:
			# Period start requested, but not found. Use newer data.
			date = parse_date(request.period_start)
			start = await fetch_boundary_log(
				row.id, conn, table, table.c.log_date > date, _desc=False
			)
			if start is None:
				profile_stats = null_stats(is_tribe)
			else:
				period_start = start.log_date.strftime("%Y-%m-%d")
				profile_stats = calculate_difference(is_tribe, end, start)

		today = datetime.utcnow().strftime("%Y-%m-%d")
		period = {
			"start": period_start or request.period_start or "2010-05-01",
			"end": request.period_end or today,
		}

		shaman_schema = ("Tribe" if is_tribe else "") + "ShamanStats"
		for name, schema, prefix in (
			("shaman", shaman_schema, None),
			("mouse", "MouseStats", None),
			("survivor", "SurvivorStats", "survivor_"),
			("racing", "RacingStats", "racing_"),
			("defilante", "DefilanteStats", "defilante_"),
		):
			if is_tribe:
				is_public = True
			else:
				is_public = row[name] is None or row[name]
			period[name] = store = {}

			if is_public:
				store.update(as_dict(schema, profile_stats, prefix=prefix))

		if is_tribe:
			period.update({
				"members": profile_stats["members"],
				"active": profile_stats["active"],
			})

	return period


@service.on_request("player")
async def profile_player(request):
	if request.id is not None:
		query = player.c.id == request.id
	else:
		query = player.c.name == request.name

	async with service.db.acquire() as conn:
		soulmate = player.alias()
		sm_roles = roles.alias()

		result = await conn.execute(
			select(
				player,
				player_privacy,

				roles.c.cfm.label("cfm_roles"),
				roles.c.tfm.label("tfm_roles"),

				soulmate.c.id.label("sm_id"),
				soulmate.c.name.label("sm_name"),

				sm_roles.c.cfm.label("sm_cfm_roles"),
				sm_roles.c.tfm.label("sm_tfm_roles"),

				tribe.c.id.label("tribe_id"),
				tribe.c.name.label("tribe_name"),
			)
			.select_from(
				player
				.outerjoin(player_privacy, player_privacy.c.id == player.c.id)
				.outerjoin(roles, roles.c.id == player.c.id)
				.outerjoin(member, member.c.id_member == player.c.id)
				.outerjoin(soulmate, soulmate.c.id == member.c.id_spouse)
				.outerjoin(sm_roles, sm_roles.c.id == soulmate.c.id)
				.outerjoin(tribe, tribe.c.id == member.c.id_tribe)
			)
			.where(query)
		)
		row = await result.first()

		if row is None:
			await request.reject(
				"NotFound",
				"The player {} was not found."
				.format(request.name or request.id)
			)
			return

		# result = await conn.execute(
		# 	select(func.count().label("position"))
		# 	.select_from(player)
		# 	.where(
		# 		player.c.score_overall.is_not(None)
		# 		if row.score_overall is None else
		# 		player.c.score_overall >= row.score_overall
		# 	)
		# )
		# position = await result.first()

		period = await fetch_period(conn, request, player_changelog, row)

	profile = as_dict("PlayerProfile", row)
	profile["position"] = None  # position.position
	if row.sm_id is None:
		profile["soulmate"] = None
	if row.tribe_id is None:
		profile["tribe"] = None

	if period is not None:
		profile["period"] = period

	await request.send(profile)


@service.on_request("tribe")
async def profile_tribe(request):
	if request.id is not None:
		query = tribe.c.id == request.id
	else:
		query = tribe.c.name == request.name

	async with service.db.acquire() as conn:
		result = await conn.execute(
			select(
				tribe,
				tribe_stats,
			)
			.select_from(
				tribe
				.outerjoin(tribe_stats, tribe_stats.c.id == tribe.c.id)
			)
			.where(query)
		)
		row = await result.first()

		if row is None or row.id is None:
			await request.reject(
				"NotFound",
				"The tribe {} was not found."
				.format(request.name or request.id)
			)
			return

		result = await conn.execute(
			select(func.count().label("position"))
			.select_from(tribe_stats)
			.where(
				tribe_stats.c.score_overall.is_not(None)
				if row.score_overall is None else
				tribe_stats.c.score_overall >= row.score_overall
			)
		)
		position = await result.first()

		period = await fetch_period(conn, request, tribe_changelog, row)

	profile = as_dict("TribeProfile", row)
	profile["position"] = position.position
	if period is not None:
		profile["period"] = period

	await request.send(profile)


if __name__ == "__main__":
	service.run(workers=int(os.getenv("WORKERS", "2")))
