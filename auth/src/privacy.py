from common import service

from shared.models import player_privacy
from sqlalchemy.sql import select
from sqlalchemy.dialects.mysql import insert


privacy_fields = (
	# (name, default)
	("names", False),
	("soulmate", False),
	("tribe", False),
	("look", False),
	("activity", False),
	("badges", True),
	("titles", True),
	("shaman", True),
	("normal", True),
	("survivor", True),
	("racing", True),
	("defilante", True),
)
privacy_keys = set()
for field, _ in privacy_fields:
	privacy_keys.add(field)


@service.on_request("get-privacy")
async def get_privacy(request):
	async with service.db.acquire() as conn:
		result = await conn.execute(
			select(player_privacy)
			.where(player_privacy.c.id == request.auth["user"])
		)
		row = await result.first()

	if row is None:
		await request.send(dict(privacy_fields))

	else:
		response = {}
		for field, _ in privacy_fields:
			response[field] = getattr(row, field)

		await request.send(response)


@service.on_request("set-privacy")
async def set_privacy(request):
	for field in request.privacy:
		if field not in privacy_keys:
			await request.reject("UnknownField", f"Uknown field: {field}")
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
