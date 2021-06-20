from common import service, env

import aiohttp


link = "https://cheese.formice.com"


def profile_link(is_player, name, _id):
	return f"[{name}]({link}/{'p' is_player else 't'}/{_id}): `{_id}`"


async def sanction_notification(sanction):
	subject_type = "Player" if sanction.player else "Tribe"
	subject = profile_link(
		sanction.player, sanction.subject_name, sanction.subject
	)
	fields = [
		{
			"name": "Subject",
			"value": f"{subject_type}\n{subject}",
			"inline": True
		},
		{
			"name": "Sanction type",
			"value": sanction.type.capitalize(),
			"inline": True
		},
		{
			"name": "Responsible moderator",
			"value": profile_link(True, sanction.mod_name, sanction.mod),
			"inline": True
		},
		{
			"name": "Sanction date",
			"value": sanction.date.strftime("%Y-%m-%d %H:%M:%S UTC"),
			"inline": True
		},
		{
			"name": "Sanction reason",
			"value": sanction.reason
		}
	]

	if sanction.canceller is None:
		title = f"New sanction #{sanction.id}"
		color = 0xC10015
	else:
		title = f"Sanction #{sanction.id} cancelled"
		color = 0xF2C037
		fields.extend([
			{
				"name": "Canceller",
				"value": profile_link(
					True, sanction.canceller_name, sanction.canceller
				),
				"inline": True
			},
			{
				"name": "Cancellation date",
				"value": sanction.cancel_date.strftime(
					"%Y-%m-%d %H:%M:%S UTC"
				),
				"inline": True
			},
			{
				"name": "Cancellation reason",
				"value": sanction.cancel_reason
			},
		])

	info = f"{link}/sanction/{sanction.id}"
	history = f"{link}/p/{sanction.subject}/sanctions"
	fields.append({
		"name": "Useful links",
		"value": (
			f"[Sanction information]({info}) - "
			f"[Subject sanction history]({history})"
		)
	})

	async with aiohttp.ClientSession() as session:
		await sess.post(env.sanction_webhook, json={
			"embed": {
				"title": title,
				"color": color,
				"fields": fields,
			}
		}, headers={
			"Content-Type": "application/json"
		})

@service.on_request("get-sanctions")
async def get_sanctions(request):
	# by player or latest sanctions
	pass
	"""[
		{
			"id": 1,
			"subject": {
				"type": "player",
				"id": 51058033,
				"name": "Tocutoeltuco#0000",
				"cfm_roles": ["dev"],
				"tfm_roles": ["module"]
			},
			"sanction": {
				"mod": null OR {
					"id": 51058033,
					"name": "Tocutoeltuco#0000",
					"cfm_roles": ["dev"],
					"tfm_roles": ["module"]
				},
				"type": "hacking",
				"reason": "loser",
				"date": "2021-06-14T16:35:22Z"
			},
			"cancellation": null OR {
				"mod": null OR {
					"id": 51058033,
					"name": "Tocutoeltuco#0000",
					"cfm_roles": ["dev"],
					"tfm_roles": ["module"]
				},
				"reason": "not a loser anymore",
				"date": "2021-06-14T16:36:15Z"
			},
			"appeal": {
				"status": "available",
				"messages": 0
			}
		}
	]"""


@service.on_request("get-sanction")
async def get_sanction(request):
	pass
	"""{
		"id": 1,
		"subject": {
			"type": "player",
			"id": 51058033,
			"name": "Tocutoeltuco#0000",
			"cfm_roles": ["dev"],
			"tfm_roles": ["module"]
		},
		"sanction": {
			"mod": null OR {
				"id": 51058033,
				"name": "Tocutoeltuco#0000",
				"cfm_roles": ["dev"],
				"tfm_roles": ["module"]
			},
			"type": "hacking",
			"reason": "loser",
			"date": "2021-06-14T16:35:22Z"
		},
		"cancellation": null OR {
			"mod": null OR {
				"id": 51058033,
				"name": "Tocutoeltuco#0000",
				"cfm_roles": ["dev"],
				"tfm_roles": ["module"]
			},
			"reason": "not a loser anymore",
			"date": "2021-06-14T16:36:15Z"
		},
		"appeal": {
			"status": "closed"
			"messages": [
				{
					"type": "text",
					"author": {
						"id": 51058033,
						"name": "Tocutoeltuco#0000",
						"cfm_roles": ["dev"],
						"tfm_roles": ["module"]
					},
					"message": "haha lol",
					"date": "2021-06-14T16:35:41Z"
				},
				{
					"type": "system",
					"author": null OR {
						"id": 51058033,
						"name": "Tocutoeltuco#0000",
						"cfm_roles": ["dev"],
						"tfm_roles": ["module"]
					},
					"message": "sanction-cancelled",
					"date": "2021-06-14T16:36:15Z"
				}
			]
		}
	}"""


@service.on_request("sanction")
async def sanction(request):
	pass


@service.on_request("cancel-sanction")
async def cancel_sanction(request):
	pass


@service.on_request("post-appeal-msg")
async def post_appeal_msg(request):
	pass


@service.on_request("change-appeal-state")
async def change_appeal_state(request):
	pass
