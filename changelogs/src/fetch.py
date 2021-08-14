from shared.models import roles, player, tribe, player_privacy, \
	player_changelog, member_changelog, tribe_changelog
from sqlalchemy import desc
from sqlalchemy.sql import select


async def fetch_player_info(conn, user: int):
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
	return await result.first()


async def fetch_player_logs(conn, user: int, offset: int, limit: int) -> list:
	result = await conn.execute(
		select(player_changelog)
		.where(player_changelog.c.id == user)
		.order_by(desc(player_changelog.c.log_id))
		.offset(offset)
		.limit(limit)
	)
	return await result.fetchall()


async def fetch_member_logs(conn, user: int, offset: int, limit: int) -> list:
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
			.outerjoin(player, player.c.id == member_changelog.c.id_spouse)
			.outerjoin(tribe, tribe.c.id == member_changelog.c.id_tribe)
		)
		.where(member_changelog.c.id_member == user)
		.order_by(desc(member_changelog.c.log_id))
		.offset(offset)
		.limit(limit)
	)
	return await result.fetchall()