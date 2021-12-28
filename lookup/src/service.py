import os
import asyncio

from dataclasses import dataclass
from typing import Tuple

from shared.pyservice import Service
from shared.roles import to_cfm_roles, to_tfm_roles
from shared.models import roles, player, tribe, tribe_stats, member, periods, \
	disqualified
from shared.qualification import player_qualification_query, \
	tribe_qualification_query

from aiomysql.sa import create_engine
from sqlalchemy import and_, desc, func
from sqlalchemy.sql import select


class env:
	cfm_ip = os.getenv("DB_IP", "cfmdb")
	cfm_user = os.getenv("DB_USER", "test")
	cfm_pass = os.getenv("DB_PASS", "test")
	cfm_db = os.getenv("DB", "api_data")


service = Service("lookup")


@dataclass
class Relation:
	keys: Tuple[str]
	relations: Tuple[str]


relations = (
	# db fields that are related to each other
	Relation(("score_overall",), ()),
	Relation(("bootcamp",), ()),
	Relation(
		("round_played", "cheese_gathered", "first", "score_stats"),
		("saved_mice",)
	),
	Relation(
		("score_shaman",),
		(
			"shaman_cheese", "saved_mice", "saved_mice_hard",
			"saved_mice_divine", "round_played",
		)
	),
	Relation(
		("score_survivor",),
		(
			"survivor_survivor_count", "survivor_mouse_killed",
			"survivor_shaman_count", "survivor_round_played",
		)
	),
	Relation(
		("score_racing",),
		(
			"racing_first", "racing_podium", "racing_round_played",
			"racing_finished_map",
		)
	),
	Relation(
		("score_defilante",),
		("defilante_points", "defilante_round_played", "defilante_finished_map")
	),
)
rankable_fields = {
	"rounds": "round_played",
	"cheese": "cheese_gathered",
	"first": "first",
	"bootcamp": "bootcamp",
	"stats": "score_stats",
	"shaman": "score_shaman",
	"survivor": "score_survivor",
	"racing": "score_racing",
	"defilante": "score_defilante",
	"overall": "score_overall",
}
aliases = {
	# all scores show up as "score"
	# all aliases that don't appear here use the db name
	"round_played": "rounds",
	"cheese_gathered": "cheese",

	"shaman_cheese": "cheese",
	"saved_mice": "saves_normal",
	"saved_mice_hard": "saves_hard",
	"saved_mice_divine": "saves_divine",

	"survivor_survivor_count": "survivor",
	"survivor_mouse_killed": "killed",
	"survivor_shaman_count": "shaman",
	"survivor_round_played": "rounds",

	"racing_first": "first",
	"racing_podium": "podium",
	"racing_round_played": "rounds",
	"racing_finished_map": "finished",

	"defilante_points": "points",
	"defilante_round_played": "rounds",
	"defilante_finished_map": "finished",
}


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
		if request.order not in rankable_fields:
			await request.reject(
				"NotImplemented"
				"The field {} is not rankable... yet."
				.format(request.order)
			)
			return

		db_field = rankable_fields[request.order]

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
				.outerjoin(disqualified, disqualified.c.id == player.c.id)
			)
		)
		count_query = select(func.count().label("total"))

		field = getattr(period.c, db_field)
		if tribe is not None:
			where = member.c.id_tribe == tribe
			query = query.where(and_(
				where,
				disqualified.c.id.is_(None),
				player_qualification_query,
			))

			count_query = count_query.select_from(
				period
				.join(member, member.c.id_member == period.c.id)
			).where(where)
		else:
			if request.period == "overall":
				without_seek = False
				response = await service.redis.send(
					"ranking.getpage",
					"player",
					db_field,
					offset
				)
				if isinstance(response, list):
					if response[2] and offset < 100:
						# outdated indices and offset is small
						without_seek = True
					else:
						offset -= response[0]
						query = query.where(and_(
							field <= response[1],
							disqualified.c.id.is_(None),
							player_qualification_query,
						))

				else:
					if offset > 10000:
						await request.reject(
							"BadRequest",
							"The page is too far."
						)
						return
					without_seek = True

				if without_seek:
					query = query.where(and_(
						disqualified.c.id.is_(None),
						player_qualification_query,
					))
			count_query = count_query.select_from(period)

		query = query.order_by(desc(field))

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

	if request.order:
		for relation in relations:
			if db_field in relation.keys:
				break
		else:
			raise ValueError(f"missing relation for {db_field}")

		relation = relation.keys + relation.relations

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
			for db_field in relation:
				value = getattr(row, db_field)
				if db_field.startswith("score_"):
					key = "score"
				else:
					key = aliases.get(db_field, db_field)

				row_resp[key] = value

	await request.send({
		"total": total.total,
		"page": response,
	})


@service.on_request("tribe")
async def lookup_tribe(request):
	offset, limit = request.offset, request.limit

	if request.order:
		if request.order not in rankable_fields:
			await request.reject(
				"NotImplemented"
				"The field {} is not rankable... yet."
				.format(request.order)
			)
			return

		db_field = rankable_fields[request.order]

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

		field = getattr(period.c, db_field)
		if request.period == "overall":
			without_seek = False
			response = await service.redis.send(
				"ranking.getpage",
				"tribe_stats",
				db_field,
				offset
			)
			if isinstance(response, list):
				if response[2] and offset < 100:
					# outdated indices and offset is small
					without_seek = True
				else:
					offset -= response[0]
					query = query.where(and_(
						field <= response[1],
						tribe_qualification_query,
					))

			else:
				if offset > 10000:
					await request.reject(
						"BadRequest",
						"The page is too far."
					)
					return
				without_seek = True

			if without_seek:
				query = query.where(tribe_qualification_query)
		query = query.order_by(desc(field))

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

	if request.order:
		for relation in relations:
			if db_field in relation.keys:
				break
		else:
			raise ValueError(f"missing relation for {db_field}")

		relation = relation.keys + relation.relations

	response = []
	for row in rows:
		row_resp = {
			"id": row.id,
			"name": row.name,
		}
		response.append(row_resp)

		if request.order:
			for db_field in relation:
				value = getattr(row, db_field)
				if db_field.startswith("score_"):
					key = "score"
				else:
					key = aliases.get(db_field, db_field)

				row_resp[key] = value

	await request.send({
		"total": total.total,
		"page": response,
	})


@service.on_request("position")
async def get_position(request):
	for_player = request.for_player
	field, value = request.field, request.value

	if field not in rankable_fields:
		await request.reject(
			"NotImplemented"
			"The field {} is not rankable... yet."
			.format(field)
		)
		return

	db_field = rankable_fields[field]

	response = await service.redis.send(
		"ranking.getpos",
		"player" if for_player else "tribe_stats",
		db_field,
		value
	)
	if not isinstance(response, list):
		await request.reject("Unavailable")
		return

	tbl = player if for_player else tribe_stats
	outdated, approximate, boundary = response
	field = getattr(tbl.c, db_field)
	async with service.db.acquire() as conn:
		if approximate <= 10000:
			condition = and_(field <= boundary, field >= value)
		else:
			condition = and_(field < boundary, field > value)

		if for_player:
			tbl = tbl.outerjoin(disqualified, disqualified.c.id == player.c.id)
			condition = and_(
				condition,
				disqualified.c.id.is_(None),
				player_qualification_query
			)
		else:
			condition = and_(condition, tribe_qualification_query)

		result = await conn.execute(
			select(func.count().label("count"))
			.select_from(tbl)
			.where(condition)
		)
		count = await result.first()

	await request.send({
		"position": max(1, count.count + approximate),
		"accurate": approximate <= 10000,
		"outdated": outdated == 1,
	})


if __name__ == "__main__":
	service.run(workers=int(os.getenv("WORKERS", "2")))
