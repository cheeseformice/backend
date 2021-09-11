import json

from common import service, env

from argon2 import PasswordHasher, exceptions

from shared.roles import to_cfm_roles, to_tfm_roles
from shared.models import roles, auth, player
from sqlalchemy.sql import select


ph = PasswordHasher()


def verify_password(password, hashed):
	try:
		return ph.verify(hashed, password)
	except exceptions.VerifyMismatchError:
		return False


def hash_password(password):
	return ph.hash(password)


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

		if row is None or row.password == "":
			# User hasn't logged in or didn't set up a password
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

	elif request.uses == "ticket":
		async with service.http.get(
			f"{env.ticket_api}"
			f"?ticket={request.ticket}"
		) as resp:
			if resp.status == 200:
				user = json.loads(await resp.read())

			else:
				return await request.reject(
					"InvalidCredentials",
					"Invalid ticket."
				)

		async with service.db.acquire() as conn:
			result = await conn.execute(
				select(
					player.c.id,
					auth.c.refresh,

					roles.c.cfm.label("cfm_roles"),
					roles.c.tfm.label("tfm_roles"),
				)
				.select_from(
					player
					.join(auth, player.c.id == auth.c.id)
					.outerjoin(roles, roles.c.id == auth.c.id)
				)
				.where(player.c.id == user["playerId"])
			)
			row = await result.first()

			if row is None:
				return await request.reject(
					"InvalidCredentials",
					"Account has been created less than 24 hours ago."
				)

			await request.open_stream()
			if row.refresh is None:
				# First time logging in
				await conn.execute(
					auth.insert()
					.values(
						id=row.id,
						password="",
						discord=None
					)
				)

		refresh = row.refresh or 0
		response = {
			"refresh": {
				"user": row.id,
				"refresh": refresh,
				"duration": "1d"
			},
			"has_password": refresh > 0
		}

	response["success"] = True
	response["session"] = {
		"user": row.id,
		"cfm_roles": to_cfm_roles(row.cfm_roles),
		"tfm_roles": to_tfm_roles(row.tfm_roles),
	}
	await request.send(response)
	await request.end()


@service.on_request("set-password")
async def set_password(request):
	await request.open_stream()

	password = await service.loop.run_in_executor(
		service.process_pool,
		hash_password, request.password
	)

	async with service.db.acquire() as conn:
		await conn.execute(
			auth.update()
			.where(auth.c.id == request.auth["user"])
			.values(
				password=password,
				refresh=auth.c.refresh + 1
			)
		)

	await request.end()
