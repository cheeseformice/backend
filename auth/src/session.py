from common import service, ph

from shared.roles import to_cfm_roles, to_tfm_roles
from shared.models import roles, auth, player
from sqlalchemy.sql import select


def verify_password(password, hashed):
	return ph.verify(hashed, password)


@service.on_request("new-session")
async def new_session(request):
	if request.uses == "refresh":
		token = request.refresh

		async with service.db.acquire() as conn:
			result = await conn.execute(
				select(
					auth.c.id,
					auth.c.refresh,

					roles.c.cfm.label("cfm_roles"),
					roles.c.tfm.label("tfm_roles"),
				)
				.select_from(
					auth
					.outerjoin(roles, roles.c.id == auth.c.id)
				)
				.where(auth.c.id == token["user"])
			)
			row = await result.first()

		if row is None or row.refresh != token["refresh"]:
			return await request.reject("ExpiredToken", "Token has expired")

		response = {}
		await request.open_stream()

	elif request.uses == "credentials":
		async with service.db.acquire() as conn:
			result = await conn.execute(
				select(
					player.c.id,
					auth.c.password,
					auth.c.refresh,

					roles.c.cfm.label("cfm_roles"),
					roles.c.tfm.label("tfm_roles"),
				)
				.select_from(
					player
					.join(auth, player.c.id == auth.c.id)
					.outerjoin(roles, roles.c.id == auth.c.id)
				)
				.where(player.c.name == request.user)
			)
			row = await result.first()

		if row is None:  # User isn't registered
			return await request.reject(
				"InvalidCredentials",
				"Invalid username or password."
			)

		# Hashing may take some time, so give a response before timeout
		await request.open_stream()
		is_correct = await service.loop.run_in_executor(
			service.process_pool,
			verify_password, request.password, row.password
		)

		if not is_correct:
			await request.send({
				"success": False,
				"err": "InvalidCredentials",
				"err_msg": "Invalid username or password."
			})
			await request.end()
			return

		# Check if the user wants to stay logged in
		response = {
			"refresh": {
				"user": row.id,
				"refresh": row.refresh,
				"duration": "180d" if request.remind else "1d"
			}
		}

	response["success"] = True
	response["session"] = {
		"user": row.id,
		"cfm_roles": to_cfm_roles(row.cfm_roles),
		"tfm_roles": to_tfm_roles(row.tfm_roles),
	}
	await request.send(response)
	await request.end()
