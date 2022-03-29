import os
import asyncio

from shared.pyservice import Service

from datetime import datetime, timedelta
from shared.roles import to_cfm_roles
from shared.models import roles, player, player_changelog, player_privacy, \
	stats, tribe, member, tribe_stats, tribe_changelog, disqualified, auth
from shared.schemas import as_dict
from shared.qualification import can_qualify

from aiomysql.sa import create_engine
from sqlalchemy import and_, desc, asc
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

	profile_stats = {}
	for stat in check:
		end_stat = getattr(end, stat, 0) or 0
		start_stat = getattr(start, stat, 0) or 0
		profile_stats[stat] = end_stat - start_stat
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


async def fetch_period(conn, request, table, row, force_public=False):
	period = None
	if row is not None and (request.period_start or request.period_end):
		changelogs = service.is_alive("changelogs")

		period_start = None
		start, end = None, None

		if request.period_start is not None and changelogs:
			date = parse_date(request.period_start)
			start = await fetch_boundary_log(
				row.id, conn, table, table.c.log_date <= date
			)

		if request.period_end is not None and changelogs:
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
		if not changelogs:
			profile_stats = null_stats(is_tribe)

		elif start is not None:
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
			if is_tribe or force_public:
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


@service.on_request("progress")
async def account_progress(request):
	async with service.db.acquire() as conn:
		result = await conn.execute(
			select(player)
			.select_from(player)
			.where(player.c.id == request.auth["user"])
		)
		row = await result.first()
		period = await fetch_period(conn, request, player_changelog, row, True)

	await request.send(period)


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

				auth.c.login,
				member.c.id_gender,

				roles.c.cfm.label("cfm_roles"),
				roles.c.tfm.label("tfm_roles"),

				soulmate.c.id.label("sm_id"),
				soulmate.c.name.label("sm_name"),

				sm_roles.c.cfm.label("sm_cfm_roles"),
				sm_roles.c.tfm.label("sm_tfm_roles"),

				tribe.c.id.label("tribe_id"),
				tribe.c.name.label("tribe_name"),

				disqualified.c.cfm.label("disq_cfm"),
				disqualified.c.tfm.label("disq_tfm"),
			)
			.select_from(
				player
				.outerjoin(auth, auth.c.id == player.c.id)
				.outerjoin(player_privacy, player_privacy.c.id == player.c.id)
				.outerjoin(roles, roles.c.id == player.c.id)
				.outerjoin(member, member.c.id_member == player.c.id)
				.outerjoin(soulmate, soulmate.c.id == member.c.id_spouse)
				.outerjoin(sm_roles, sm_roles.c.id == soulmate.c.id)
				.outerjoin(tribe, tribe.c.id == member.c.id_tribe)
				.outerjoin(disqualified, disqualified.c.id == player.c.id)
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

		last_login = None
		if request.auth is not None:
			me = request.auth["cfm_roles"]
			subj = to_cfm_roles(row.cfm_roles or 0)

			if "admin" in me or "dev" in me:
				if "mod" in subj or "trainee" in subj or "translator" in subj:
					last_login = row.login or datetime(2010, 5, 14)

		period = await fetch_period(conn, request, player_changelog, row)

	profile = as_dict("PlayerProfile", row)
	if row.sm_id is None:
		profile["soulmate"] = None
	if row.tribe_id is None:
		profile["tribe"] = None

	disq_tfm = row.disq_tfm
	if (row.tfm_roles is not None and row.tfm_roles > 0) \
		or row.name.endswith("#0095"):
		disq_tfm = 0

	profile["disqualified"] = (row.disq_cfm or 0) + (disq_tfm or 0) > 0
	profile["can_qualify"] = can_qualify(row)

	if period is not None:
		profile["period"] = period

	if row.outfits is False:  # Ignore None
		profile["shop"]["outfits"] = []

	if last_login is not None:
		profile["last_login"] = last_login.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

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

		period = await fetch_period(conn, request, tribe_changelog, row)

	profile = as_dict("TribeProfile", row)
	if period is not None:
		profile["period"] = period

	await request.send(profile)


if __name__ == "__main__":
	service.run(workers=int(os.getenv("WORKERS", "2")))
