from common import service

from shared.roles import to_cfm_roles
from shared.models import disqualified, sanctions, player, roles
from shared.schemas import as_dict
from sqlalchemy.sql import select, delete
from sqlalchemy.dialects.mysql import insert


@service.on_request("get-sanction")
async def get_sanction(request):
	auth = request.auth["cfm_roles"]
	if not auth or not ("mod" in auth or "admin" in auth or "dev" in auth):
		await request.reject("MissingPrivileges")
		return

	async with service.db.acquire() as conn:
		result = await conn.execute(
			select(disqualified.c.tfm, disqualified.c.cfm)
			.select_from(disqualified)
			.where(disqualified.c.id == request.subject)
		)
		disq = await result.first()

		result = await conn.execute(
			select(
				sanctions.c.reason,

				player.c.id.label("mod_id"),
				player.c.name.label("mod_name"),

				roles.c.cfm.label("mod_cfm_roles"),
				roles.c.tfm.label("mod_tfm_roles"),
			)
			.select_from(
				sanctions
				.join(player, player.c.id == sanctions.c.player)
				.outerjoin(roles, roles.c.id == sanctions.c.player)
			)
			.where(sanctions.c.player == request.subject)
		)
		cfm_sanction = await result.first()

	disq_info = None
	if cfm_sanction is not None:
		disq_info = as_dict("CFMDisqualificationInformation", cfm_sanction)
	response = {
		"tfm": disq is not None and disq.tfm > 0,
		"cfm": disq is not None and disq.cfm > 0,
		"disq_info": disq_info,
	}
	await request.send(response)


@service.on_request("sanction")
async def sanction(request):
	auth = request.auth["cfm_roles"]
	if not auth or not ("mod" in auth or "admin" in auth or "dev" in auth):
		await request.reject("MissingPrivileges")
		return

	async with service.db.acquire() as conn:
		result = await conn.execute(
			select(roles.c.cfm)
			.where(roles.c.id == request.subject)
		)
		row = await result.first()
		if row is not None:
			subj = to_cfm_roles(row.cfm)
			if "mod" in subj or "admin" in subj or "dev" in subj:
				# can't sanction a mod, admin or dev
				await request.reject("MissingPrivileges")
				return

		await conn.execute(
			insert(sanctions)
			.values(
				player=request.subject,
				mod=request.auth["user"],
				reason=request.reason,
			)
			.on_duplicate_key_update(
				mod=request.auth["user"],
				reason=request.reason,
			)
		)
		await request.end()


@service.on_request("cancel-sanction")
async def cancel_sanction(request):
	auth = request.auth["cfm_roles"]
	if not auth or not ("mod" in auth or "admin" in auth or "dev" in auth):
		await request.reject("MissingPrivileges")
		return

	async with service.db.acquire() as conn:
		result = await conn.execute(
			select(sanctions.c.player)
			.where(sanctions.c.player == request.subject)
		)
		row = await result.first()
		if row is None:
			await request.reject("NotFound", "The player is not sanctioned.", "notSanctioned")
			return

		await conn.execute(
			delete(sanctions)
			.where(sanctions.c.player == request.subject)
		)
		await request.end()
