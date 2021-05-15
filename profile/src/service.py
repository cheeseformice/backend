import os
import re
import json
import aiohttp
import asyncio

from shared.pyservice import Service

from datetime import datetime, timedelta
from shared.models import roles, player, player_changelog, player_privacy, \
	stats, tribe, member, tribe_stats, tribe_changelog
from shared.schemas import as_dict

from aiomysql.sa import create_engine
from sqlalchemy import or_, and_, desc, func
from sqlalchemy.sql import select, delete
from sqlalchemy.dialects.mysql import insert


class env:
	cfm_ip = os.getenv("DB_IP", "cfmdb")
	cfm_user = os.getenv("DB_USER", "test")
	cfm_pass = os.getenv("DB_PASS", "test")
	cfm_db = os.getenv("DB", "api_data")
	name_webhook = os.getenv("NAME_WEBHOOK")


assert env.name_webhook is not None, "NAME_WEBHOOK doesn't have any link"


TEAM_API = "http://discorddb.000webhostapp.com/get?k=&e=json&f=teamList&i=1"
A801_API = "https://atelier801.com/staff-ajax?role={}"
A801_REGEX = (
	r'([^ <]+)<span class="font-s couleur-hashtag-pseudo"> (#\d{4})</span>'
)
tfm_roles = (
	# role, api
	# api: int -> from atelier801.com
	# api: str -> from discorddb
	("admin", 128),
	("mod", 1),
	("sentinel", 4),
	("mapcrew", 16),
	("module", "mt"),
	("funcorp", "fc"),
	("fashion", "fs"),
)

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
	service.loop.create_task(update_roles())


async def ping_db():
	while True:
		async with service.db.acquire() as conn:
			await conn.connection.ping()

		await asyncio.sleep(60.0)


async def update_roles():
	while True:
		teams = {}
		a801 = {}
		a801_members = set()
		check_names = set()  # Check name changes
		user_ids = {}

		async with aiohttp.ClientSession() as sess:
			# Download team API members
			async with sess.get(TEAM_API) as resp:
				result = await resp.json()

				for team, members in result.items():
					# Add these names to check_names
					members = list(map(str.lower, members.keys()))
					check_names = check_names.union(members)

					# Check if we need to store this role
					for role, api in tfm_roles:
						if api == team:
							break
					else:
						continue

					teams[role] = list(members)

			# Download all needed A801 teams
			for role, api in tfm_roles:
				if not isinstance(api, int):
					continue

				async with sess.get(A801_API.format(api)) as resp:
					a801[role] = members = []

					content = await resp.read()
					for name, tag in re.findall(A801_REGEX, content.decode()):
						name = f"{name.lower()}{tag}"
						members.append(name)
						a801_members.add(name)

		# Check all the name changes
		async with service.db.acquire() as conn:
			name_in = [player.c.id == 0]  # in_() doesn't work lol
			for name in check_names.union(a801_members):
				name_in.append(player.c.name == name)

			result = await conn.execute(
				select(
					player.c.id,
					player.c.name,
				)
				.where(or_(*name_in))
			)
			for row in await result.fetchall():
				name = row.name.lower()

				if name in check_names:
					check_names.remove(name)

				user_ids[name] = row.id

			# Now all names in check_names are invalid!
			# Let's check logs.
			name_in = [player.c.id == 0]  # in_() doesn't work lol
			for name in check_names:
				name_in.append(player_changelog.c.name == name)

			result = await conn.execute(
				select(
					player_changelog.c.id,
					player_changelog.c.name,
					player.c.name.label("new_name"),
				)
				.select_from(
					player_changelog
					.join(player, player.c.id == player_changelog.c.id)
				)
				.where(or_(*name_in))
				.group_by(player_changelog.c.name)
			)
			# Write changes
			changes = {}
			for row in await result.fetchall():
				name = row.name.lower()

				if name in check_names:
					check_names.remove(name)

				user_ids[name] = row.id
				changes[name] = row.new_name

			for name in check_names:
				changes[name] = None

		# Send the notification
		if len(changes) > 0:
			async with aiohttp.ClientSession() as sess:
				await sess.post(env.name_webhook, json={
					"content": json.dumps(changes)
				}, headers={
					"Content-Type": "application/json"
				})

		async with service.db.acquire() as conn:
			values = {}

			for idx, (role, api) in enumerate(tfm_roles):
				if isinstance(api, int):
					container = a801
				else:
					container = teams

				for name in container[role]:
					if name in user_ids:
						_id = user_ids[name]
						values[_id] = values.get(_id, 0) | (2 ** idx)

			result = await conn.execute(
				select(roles)
				.where(roles.c.tfm > 0)
			)
			for row in await result.fetchall():
				if row.id not in values:
					values[row.id] = 0

			query = []
			for _id, bits in values.items():
				query.append({
					"id": _id,
					"cfm": 0,
					"tfm": bits
				})

			insert_stmt = insert(roles).values(query)
			await conn.execute(
				insert_stmt.on_duplicate_key_update(
					tfm=insert_stmt.inserted.tfm
				)
			)

			await conn.execute(
				delete(roles)
				.where(and_(roles.c.tfm == 0, roles.c.cfm == 0))
			)

		await asyncio.sleep(60 * 30)  # 30 min


async def fetch_period(conn, request, table, row):
	period = None
	if row is not None and (request.period_start or request.period_end):
		start, end = None, None

		if request.period_start is not None:
			year, month, day = map(int, request.period_start.split("-"))
			start = datetime(year=year, month=month, day=day) \
				+ timedelta(days=1)

			result = await conn.execute(
				select(table)
				.order_by(desc(table.c.log_id))
				.where(and_(
					table.c.id == row.id,
					table.c.log_date <= start
				))
				.limit(1)
			)
			start = await result.first()

		if request.period_end is not None:
			year, month, day = map(int, request.period_end.split("-"))
			end = datetime(year=year, month=month, day=day) \
				+ timedelta(days=1)

			result = await conn.execute(
				select(table)
				.order_by(desc(table.c.log_id))
				.where(and_(
					table.c.id == row.id,
					table.c.log_date <= end
				))
				.limit(1)
			)
			end = await result.first()

		if end is None:
			if request.period_end is None:
				# No period end requested, assume current data
				end = row
			else:
				# Period end requested, no data found.
				end = {}

		is_tribe = table == tribe_changelog
		if start is not None:
			check = stats
			if is_tribe:
				check += (
					"members",
					"active",
				)
				check = check[1:]  # ignore experience

			profile_stats = {}
			for stat in check:
				profile_stats[stat] = (end[stat] or 0) - (start[stat] or 0)

		else:
			# No period start, no need to calculate differences
			profile_stats = end

		today = datetime.utcnow().strftime("%Y-%m-%d")
		period = {
			"start": request.period_start or "2010-05-01",
			"end": request.period_end or today,
		}

		shaman_schema = ("Tribe" if is_tribe else "") + "ShamanStats"
		for name, schema, prefix in (
			("shaman", shaman_schema, None),
			("normal", "NormalStats", None),
			("survivor", "SurvivorStats", "survivor_"),
			("racing", "RacingStats", "racing_"),
			("defilante", "DefilanteStats", "defilante_"),
		):
			if is_tribe:
				is_public = True
			else:
				is_public = row[name] is None or row[name]
			period[name] = store = {
				"public": is_public
			}

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

		result = await conn.execute(
			select(func.count().label("position"))
			.select_from(player)
			.where(
				player.c.score_overall.is_not(None)
				if row.score_overall is None else
				player.c.score_overall >= row.score_overall
			)
		)
		position = await result.first()

		period = await fetch_period(conn, request, player_changelog, row)

	profile = as_dict("PlayerProfile", row)
	profile["position"] = position.position
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
