from common import service
from datetime import datetime

from shared.roles import to_cfm_roles
from shared.models import disqualified, sanctions, player, roles
from shared.schemas import as_dict
from sqlalchemy import or_
from sqlalchemy.sql import select, delete
from sqlalchemy.dialects.mysql import insert


def name_link(name: str) -> str:
	if name is None:
		return "Could not fetch player name"

	link_name = name.replace("#", "-")
	return f"[{name}](https://cheese.formice.com/p/{link_name})"


def prepare_sanction_embed(
	reason: str,
	subject_id: int, subject_name: str,
	mod_id: int, mod_name: str,
):
	return {
		"title": "New sanction",
		"color": 0xD0021B,
		"timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
		"fields": [
			{
				"name": "Subject",
				"value": f"{name_link(subject_name)}: `{subject_id}`",
				"inline": True,
			},
			{
				"name": "Responsible moderator",
				"value": f"{name_link(mod_name)}: `{mod_id}`",
				"inline": True,
			},
			{
				"name": "Sanction reason",
				"value": f"{reason}"
			},
		],
	}


def prepare_cancel_embed(
	subject_id: int, subject_name: str,
	mod_id: int, mod_name: str,
):
	return {
		"title": "Sanction cancelled",
		"color": 0xF5A623,
		"timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
		"fields": [
			{
				"name": "Subject",
				"value": f"{name_link(subject_name)}: `{subject_id}`",
				"inline": True,
			},
			{
				"name": "Responsible moderator",
				"value": f"{name_link(mod_name)}: `{mod_id}`",
				"inline": True,
			},
		],
	}


@service.on_request("get-sanction")
async def get_sanction(request):
	auth = request.auth["cfm_roles"]
	roles = (
		"trainee" in auth or "mod" in auth or "admin" in auth or "dev" in auth
	)
	if not auth or not roles:
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
				.join(player, player.c.id == sanctions.c.mod)
				.outerjoin(roles, roles.c.id == sanctions.c.mod)
			)
			.where(sanctions.c.player == request.subject)
		)
		cfm_sanction = await result.first()

	disq_info = None
	if cfm_sanction is not None:
		disq_info = as_dict("CFMDisqualificationInformation", cfm_sanction)
	response = {
		"tfm": disq is not None and disq.tfm > 0,
		"cfm": cfm_sanction is not None,
		"disq_info": disq_info,
	}
	await request.send(response)


@service.on_request("sanction")
async def sanction(request):
	auth = request.auth["cfm_roles"]
	roles = (
		"trainee" in auth or "mod" in auth or "admin" in auth or "dev" in auth
	)
	if not auth or not roles:
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
			if ("trainee" in subj or
				"mod" in subj or
				"admin" in subj or
				"dev" in subj):
				# can't sanction a trainee, mod, admin or dev
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

		result = await conn.execute(
			select(player.c.id, player.c.name)
			.where(or_(
				player.c.id == request.subject,
				player.c.id == request.auth["user"]
			))
		)
		rows = await result.fetchall()
		subject_name, mod_name = None, None
		for row in rows:
			if row.id == request.subject:
				subject_name = row.name
			else:
				mod_name = row.name

		await service.wh.post(None, [prepare_sanction_embed(
			request.reason,
			request.subject, subject_name,
			request.auth["user"], mod_name,
		)])


@service.on_request("cancel-sanction")
async def cancel_sanction(request):
	auth = request.auth["cfm_roles"]
	roles = (
		"trainee" in auth or "mod" in auth or "admin" in auth or "dev" in auth
	)
	if not auth or not roles:
		await request.reject("MissingPrivileges")
		return

	async with service.db.acquire() as conn:
		result = await conn.execute(
			select(sanctions.c.player)
			.where(sanctions.c.player == request.subject)
		)
		row = await result.first()
		if row is None:
			await request.reject(
				"NotFound",
				"The player is not sanctioned.",
				"notSanctioned"
			)
			return

		await conn.execute(
			delete(sanctions)
			.where(sanctions.c.player == request.subject)
		)
		await request.end()

		result = await conn.execute(
			select(player.c.id, player.c.name)
			.where(or_(
				player.c.id == request.subject,
				player.c.id == request.auth["user"]
			))
		)
		rows = await result.fetchall()
		subject_name, mod_name = None, None
		for row in rows:
			if row.id == request.subject:
				subject_name = row.name
			else:
				mod_name = row.name

		await service.wh.post(None, [prepare_cancel_embed(
			request.subject, subject_name,
			request.auth["user"], mod_name,
		)])
