import os
import asyncio

from shared.pyservice import Service

from shared.roles import to_cfm_roles, to_tfm_roles

from shared.models import roles, player, tribe, member, periods
from aiomysql.sa import create_engine
from sqlalchemy import and_, desc, func
from sqlalchemy.sql import select


class env:
	cfm_ip = os.getenv("DB_IP", "cfmdb")
	cfm_user = os.getenv("DB_USER", "test")
	cfm_pass = os.getenv("DB_PASS", "test")
	cfm_db = os.getenv("DB", "api_data")


service = Service("lookup")


rankable_fields = (
	# (name, db_field)
	("rounds", "round_played"),
	("cheese", "cheese_gathered"),
	("first", "first"),
	("bootcamp", "bootcamp"),
	("stats", "score_stats"),
	("shaman", "score_shaman"),
	("survivor", "score_survivor"),
	("racing", "score_racing"),
	("defilante", "score_defilante"),
	("overall", "score_overall"),
)


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


@service.on_request("player")
async def lookup_player(request):
	offset, limit = request.offset, request.limit
	tribe = request.tribe

	if request.order:
		for name, db_field in rankable_fields:
			if name == request.order:
				break
		else:
			await request.reject(
				"NotImplemented"
				"The field {} is not rankable... yet."
				.format(request.order)
			)
			return

		columns = (player,)
		select_from = player

		if request.period != "overall":
			period = periods["player"][request.period]

			columns = (
				player.c.id,
				player.c.name,
				period
			)
			select_from = select_from.join(period, period.c.id == player.c.id)
		else:
			period = player

		if tribe is not None:
			select_from = select_from.join(
				member, member.c.id_member == player.c.id
			)

		query = (
			select(
				*columns,

				roles.c.cfm.label("cfm_roles"),
				roles.c.tfm.label("tfm_roles"),
			)
			.select_from(
				select_from
				.outerjoin(roles, roles.c.id == player.c.id)
			)
		)
		count_query = select(func.count().label("total"))

		if tribe is not None:
			where = member.c.id_tribe == tribe
			query = query.where(where)

			count_query = count_query.select_from(
				period
				.join(member, member.c.id_member == period.c.id)
			).where(where)
		else:
			count_query = count_query.select_from(period)

		query = query.order_by(desc(getattr(period.c, db_field)))

	elif request.search:
		name = request.search.replace("%", "").replace("_", "\\_") + "%"

		name_query = player.c.name.like(name)
		select_from = player

		if tribe is not None:
			name_query = and_(
				member.c.id_tribe == tribe,
				name_query
			)
			select_from = select_from.join(
				member, member.c.id_member == player.c.id
			)

		query = (
			select(
				player.c.id,
				player.c.name,

				roles.c.cfm.label("cfm_roles"),
				roles.c.tfm.label("tfm_roles"),
			)
			.select_from(
				select_from
				.outerjoin(roles, roles.c.id == player.c.id)
			)
			.where(name_query)
		)
		count_query = (
			select(func.count().label("total"))
			.select_from(select_from)
			.where(name_query)
		)

	elif tribe is not None:
		where = member.c.id_tribe == tribe
		query = (
			select(
				player.c.id,
				player.c.name,

				roles.c.cfm.label("cfm_roles"),
				roles.c.tfm.label("tfm_roles"),
			)
			.select_from(
				player
				.join(member, member.c.id_member == player.c.id)
				.outerjoin(roles, roles.c.id == player.c.id)
			)
			.where(where)
		)
		count_query = (
			select(func.count().label("total"))
			.select_from(member)
			.where(where)
		)

	async with service.db.acquire() as conn:
		result = await conn.execute(count_query)
		total = await result.first()

		result = await conn.execute(query.offset(offset).limit(limit))
		rows = await result.fetchall()

	response = []
	for row in rows:
		row_resp = {
			"id": row.id,
			"name": row.name,
			"cfm_roles": to_cfm_roles(row.cfm_roles or 0),
			"tfm_roles": to_tfm_roles(row.tfm_roles or 0),
		}
		response.append(row_resp)

		if request.order:
			for name, db_field in rankable_fields:
				row_resp[name] = getattr(row, db_field)

	await request.send({
		"total": total.total,
		"page": response,
	})


@service.on_request("tribe")
async def lookup_tribe(request):
	offset, limit = request.offset, request.limit

	if request.order:
		for name, db_field in rankable_fields:
			if name == request.order:
				break
		else:
			await request.reject(
				"NotImplemented"
				"The field {} is not rankable... yet."
				.format(request.order)
			)
			return

		period = periods["tribe"][request.period]
		query = (
			select(
				tribe.c.id,
				tribe.c.name,
				period,
			)
			.select_from(
				tribe
				.join(period, period.c.id == tribe.c.id)
			)
		)

		query = query.order_by(desc(getattr(period.c, db_field)))

		count_query = (
			select(func.count().label("total"))
			.select_from(period)
		)

	elif request.search:
		name = request.search.replace("%", "").replace("_", "\\_") + "%"

		where = tribe.c.name.like(name)

		query = (
			select(tribe.c.id, tribe.c.name)
			.where(where)
		)
		count_query = (
			select(func.count().label("total"))
			.select_from(tribe)
			.where(where)
		)

	async with service.db.acquire() as conn:
		result = await conn.execute(count_query)
		total = await result.first()

		result = await conn.execute(query.offset(offset).limit(limit))
		rows = await result.fetchall()

	response = []
	for row in rows:
		row_resp = {
			"id": row.id,
			"name": row.name,
		}
		response.append(row_resp)

		if request.order:
			for name, db_field in rankable_fields:
				row_resp[name] = getattr(row, db_field)

	await request.send({
		"total": total.total,
		"page": response,
	})


if __name__ == "__main__":
	service.run(workers=int(os.getenv("WORKERS", "2")))
