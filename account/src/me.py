from common import service

from shared.logs import PlayerLogs
from shared.models import player, player_privacy, roles, disqualified
from shared.schemas import as_dict
from shared.qualification import can_qualify

from sqlalchemy.sql import select
from sqlalchemy.dialects.mysql import insert


visible_logs = [
	log
	for log in PlayerLogs.logs.values()
	if not log.invisible
]
privacy_columns = [
	getattr(player_privacy.c, log.name)
	for log in visible_logs
	if hasattr(player_privacy.c, log.name)
]


@service.on_request("get-me")
async def get_me(request):
	myself = request.auth["user"]
	async with service.db.acquire() as conn:
		result = await conn.execute(
			select(
				player,

				roles.c.cfm.label("cfm_roles"),
				roles.c.tfm.label("tfm_roles"),

				disqualified.c.cfm.label("disq_cfm"),
				disqualified.c.tfm.label("disq_tfm"),

				*privacy_columns,
			)
			.select_from(
				player
				.outerjoin(roles, roles.c.id == player.c.id)
				.outerjoin(player_privacy, player_privacy.c.id == player.c.id)
				.outerjoin(disqualified, disqualified.c.id == player.c.id)
			)
			.where(player.c.id == myself)
		)
		row = await result.first()
		if row is None:
			raise Exception("Could not find authenticated user")

	result = as_dict("AccountInformation", row)
	result["disqualified"] = (row.disq_cfm or 0) + (row.disq_tfm or 0) > 0
	result["can_qualify"] = can_qualify(row)
	await request.send(result)


@service.on_request("set-privacy")
async def set_privacy(request):
	for field, value in request.privacy.items():
		log = PlayerLogs.logs.get(field, None)
		if log is None or log.invisible:
			await request.reject("UnknownField", f"Uknown field: {field}")
			return

		if not isinstance(value, bool):
			await request.reject(
				"BadRequest",
				f"Invalid value for {field} (not a boolean)"
			)
			return

	if not request.privacy:
		await request.end()
		return

	async with service.db.acquire() as conn:
		insert_stmt = (
			insert(player_privacy)
			.values(id=request.auth["user"], **request.privacy)
		)
		await conn.execute(
			insert_stmt.on_duplicate_key_update(**request.privacy)
		)

	await request.end()
