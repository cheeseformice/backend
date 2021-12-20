import json

from common import service, env

from argon2 import PasswordHasher, exceptions

from shared.roles import to_cfm_roles, to_tfm_roles
from shared.models import roles, auth, player, bots
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
		if "bot" not in token:
			token["bot"] = False

		async with service.db.acquire() as conn:
			if not token["bot"]:
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
			else:
				result = await conn.execute(
					select(
						bots.c.id,
						bots.c.refresh,

						bots.c.owner.label("owner_id"),
						roles.c.cfm.label("cfm_roles"),
						roles.c.tfm.label("tfm_roles"),
					)
					.select_from(
						bots
						.outerjoin(roles, roles.c.id == bots.c.owner)
					)
					.where(bots.c.id == token["client_id"])
				)
			row = await result.first()

		if row is None or row.refresh != token["refresh"]:
			return await request.reject("ExpiredToken", "Token has expired")

		response = {}
		if token["bot"]:
			response["bot"] = True
			response["session"] = {
				"bot": row.id,
				"owner": row.owner_id,
				"cfm_roles": to_cfm_roles(row.cfm_roles or 0),
				"tfm_roles": to_tfm_roles(row.tfm_roles or 0),
			}
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
				"Invalid username or password.",
				translation_key="wrongCredentials"
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
				"err_msg": "Invalid username or password.",
				"translationKey": "wrongCredentials",
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
					.outerjoin(auth, player.c.id == auth.c.id)
					.outerjoin(roles, roles.c.id == player.c.id)
				)
				.where(player.c.id == user["playerId"])
			)
			row = await result.first()

			if row is None:
				return await request.reject(
					"InvalidCredentials",
					"Account has been created less than 24 hours ago.",
					translation_key="accountNotInDb"
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

	elif request.uses == "bot-token":
		async with service.db.acquire() as conn:
			result = await conn.execute(
				select(
					bots.c.id,
					bots.c.token,
					bots.c.refresh,

					bots.c.owner.label("owner_id"),
					roles.c.cfm.label("cfm_roles"),
					roles.c.tfm.label("tfm_roles"),
				)
				.select_from(
					bots
					.outerjoin(roles, roles.c.id == bots.c.owner)
				)
				.where(bots.c.id == request.client_id)
			)
			row = await result.first()

		if row is None or row.token != request.token:
			# bot doesn't exist or token doesn't match
			return await request.reject(
				"InvalidCredentials",
				"Invalid client id or token.",
				translation_key="wrongCredentials"
			)

		response = {
			"bot": True,
			"refresh": {
				"bot": True,
				"client_id": row.id,
				"refresh": row.refresh,
				"duration": request.duration,
			},
			"session": {
				"bot": row.id,
				"owner": row.owner_id,
				"cfm_roles": to_cfm_roles(row.cfm_roles or 0),
				"tfm_roles": to_tfm_roles(row.tfm_roles or 0),
			},
		}

		await request.open_stream()

	response["success"] = True
	if "session" not in response:
		response["session"] = {
			"user": row.id,
			"cfm_roles": to_cfm_roles(row.cfm_roles or 0),
			"tfm_roles": to_tfm_roles(row.tfm_roles or 0),
		}
	await request.send(response)
	await request.end()


@service.on_request("set-password")
async def set_password(request):
	await request.open_stream()

	async with service.db.acquire() as conn:
		result = await conn.execute(
			select(auth.c.password)
			.select_from(auth)
			.where(auth.c.id == request.auth["user"])
		)
		row = await result.first()

	if row is None:
		raise Exception("authenticated user not in db?")

	if row.password != "":
		# User has a password
		is_correct = await service.loop.run_in_executor(
			service.process_pool,
			verify_password, request.old_password, row.password
		)

		if not is_correct:
			await request.send({
				"success": False,
				"err": "InvalidCredentials",
				"err_msg": "Wrong password.",
				"translation_key": "wrongPassword",
			})
			await request.end()
			return

	new_password = await service.loop.run_in_executor(
		service.process_pool,
		hash_password, request.new_password
	)

	async with service.db.acquire() as conn:
		await conn.execute(
			auth.update()
			.where(auth.c.id == request.auth["user"])
			.values(
				password=new_password,
				refresh=auth.c.refresh + 1
			)
		)

	await request.send({"success": True})
	await request.end()
