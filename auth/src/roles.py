from common import service
from datetime import datetime

from shared.roles import from_cfm_roles, to_cfm_roles
from shared.models import roles, player
from sqlalchemy.sql import select
from sqlalchemy.dialects.mysql import insert

from shared.schemas import as_dict_list


role_emojis = {
	"dev": "<:redfeather:929443930032992256>",
	"admin": "<:redfeather:929443930032992256>",
	"mod": "<:yellowfeather:929444076191879188>",
	"translator": "<:purplefeather:929444194345447484>",
	"trainee": "<:lavenderfeather:934812879645982720>",
}


def name_link(name: str) -> str:
	if name is None:
		return "Could not fetch player name"

	link_name = name.replace("#", "-")
	return f"[{name}](https://cheese.formice.com/p/{link_name})"


def add_emoji(role):
	return f"{role_emojis[role]} `{role}`"


def to_embed_roles(roles):
	if not roles:
		return "None"

	return "\n".join(map(add_emoji, roles))


def prepare_role_embed(
	admin_id, admin_name,
	subject_id, subject_name,
	current_roles, new_roles
):
	return {
		"title": "Roles modified",
		"color": 0x4D7489,
		"timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
		"fields": [
			{
				"name": "Subject",
				"value": f"{name_link(subject_name)}: `{subject_id}`",
				"inline": True,
			},
			{
				"name": "Responsible administrator",
				"value": f"{name_link(admin_name)}: `{admin_id}`",
				"inline": True,
			},
			{
				"name": "Old roles",
				"value": f"{to_embed_roles(current_roles)}"
			},
			{
				"name": "New roles",
				"value": f"{to_embed_roles(new_roles)}"
			},
		],
	}


@service.on_request("get-privileged")
async def get_privileged(request):
	async with service.db.acquire() as conn:
		result = await conn.execute(
			select(
				player.c.id,
				player.c.name,
				roles.c.cfm.label("cfm_roles"),
				roles.c.tfm.label("tfm_roles"),
			)
			.select_from(
				player
				.join(roles, roles.c.id == player.c.id)
			)
			.where(roles.c.cfm > 0)
		)
		rows = await result.fetchall()

	await request.send(as_dict_list("BasicPlayer", rows))


@service.on_request("change-roles")
async def change_roles(request):
	async with service.db.acquire() as conn:
		result = await conn.execute(
			select(
				player.c.id,
				player.c.name,
				roles.c.cfm,
			)
			.select_from(
				player
				.outerjoin(roles, roles.c.id == player.c.id)
			)
			.where(player.c.name == request.target)
		)
		row = await result.first()
		if row is None:
			await request.reject(
				"NotFound",
				"The player {} was not found."
				.format(request.target)
			)
			return

		admin = await conn.execute(
			select(player.c.name)
			.select_from(player)
			.where(player.c.id == request.auth["user"])
		)
		admin = await admin.first()
		if admin is None:
			raise Exception("admin not in db?")

		# normalize roles list in case there are unknown roles
		new_roles = to_cfm_roles(from_cfm_roles(request.roles))
		current_roles = []
		if row.cfm is not None:
			# The user had previous roles
			current_roles = to_cfm_roles(row.cfm)

			if "dev" in current_roles \
				and "dev" not in new_roles:
				# Trying to dismiss a dev
				await request.reject(
					"Forbidden",
					"Developers have to be dismissed through the DB."
				)
				return

			source_roles = request.auth["cfm_roles"]
			if "admin" in current_roles \
				and "admin" not in new_roles \
				and "dev" not in source_roles:
				# Trying to dismiss an admin, while not being a dev
				await request.reject(
					"Forbidden",
					"Administrators have to be dismissed by a developer."
				)
				return

		await request.end()

		await service.wh.post(None, [prepare_role_embed(
			request.auth["user"], admin.name,
			row.id, row.name,
			current_roles, new_roles,
		)])

		new_roles = from_cfm_roles(new_roles)
		await service.send_strict("broadcast:roles", "cfm", **{
			str(row.id): new_roles
		})
		insert_stmt = (
			insert(roles)
			.values(
				id=row.id,
				cfm=new_roles,
				tfm=0
			)
		)
		await conn.execute(
			insert_stmt.on_duplicate_key_update(cfm=new_roles)
		)
