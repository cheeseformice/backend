from common import service

from shared.roles import from_cfm_roles, to_cfm_roles
from shared.models import roles, player
from sqlalchemy.sql import select
from sqlalchemy.dialects.mysql import insert


@service.on_request("change-roles")
async def change_roles(request):
	async with service.db.acquire() as conn:
		result = await conn.execute(
			select(
				player.c.id,
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

		new_roles = request.roles
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

			source_roles = request.user["cfm_roles"]
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
