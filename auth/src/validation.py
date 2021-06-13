from common import service, ph

from shared.models import auth, player
from sqlalchemy.sql import select


def hash_password(password):
	return ph.hash(password)


@service.on_request("new-validation")
async def new_validation(request):
	async with service.db.acquire() as conn:
		result = await conn.execute(
			select(
				player.c.id,
				auth.c.refresh
			)
			.select_from(
				player
				.outerjoin(auth, auth.c.id == player.c.id)
			)
			.where(player.c.name == request.user)
		)
		row = await result.first()

	if row is None:
		return await request.reject(
			"NotFound",
			"The given player has not been found in Transformice."
		)

	if request.method == "register" and row.refresh is not None:
		return await request.reject("WrongMethod")
	elif request.method == "password" and row.refresh is None:
		return await request.reject("WrongMethod")

	await request.send({
		"user": row.id,
		"refresh": row.refresh
	})


@service.on_request("is-valid")
@service.on_request("use-validity")
async def validation(request):
	if request.type == "is-valid":
		token = {
			"user": request.user,
			"refresh": request.refresh,
		}
	else:
		token = request.token

	async with service.db.acquire() as conn:
		result = await conn.execute(
			select(
				player.c.id,
				auth.c.refresh
			)
			.select_from(
				player
				.outerjoin(auth, auth.c.id == player.c.id)
			)
			.where(player.c.id == token["user"])
		)
		row = await result.first()

		if row is None:
			# The account has been deleted?
			return await request.reject(
				"NotFound",
				"The given player has not been found in Transformice."
			)

		if token["refresh"] != row.refresh:
			return await request.reject("ExpiredToken")

		if request.type == "is-valid":
			return await request.end()

		# Hashing may take some time, so give a response before timeout
		await request.end()

		password = await service.loop.run_in_executor(
			service.process_pool,
			hash_password, request.password
		)

		if token["refresh"] is None:
			query = (
				auth.insert()
				.values(
					id=token["user"],
					password=password,
					discord=None
				)
			)
		else:
			query = (
				auth.update()
				.where(auth.c.id == token["user"])
				.values(
					password=password,
					refresh=auth.c.refresh + 1
				)
			)

		await conn.execute(query)
