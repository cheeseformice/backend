from collections import namedtuple
from shared.roles import to_cfm_roles, to_tfm_roles


SchemaField = namedtuple(
	"SchemaField",
	["field", "default", "process"],
	defaults=(None,) * 3
)
Field = namedtuple(
	"Field",
	["field", "default"],
	defaults=(None,) * 2
)
Process = namedtuple(
	"Process",
	["field", "process"],
	defaults=(None,) * 2
)
Require = namedtuple(
	"Require",
	["schema", "prefix"],
	defaults=(None,) * 2
)


def as_list(obj):
	if obj == "":
		return []
	return obj.split(",")


def from_hex(string):
	if not string:
		return 0
	return int(string, base=16)


def outfits(dress_list):
	if dress_list == "":
		return []
	return dress_list.split("/")


compiled_schemas = {}
schemas = {
	"BasicPlayer": {
		"id": Field("id"),
		"name": Field("name", ""),
		"cfm_roles": Process(Field("cfm_roles", 0), to_cfm_roles),
		"tfm_roles": Process(Field("tfm_roles", 0), to_tfm_roles),
	},
	"BasicTribe": {
		"id": Field("id"),
		"name": Field("name"),
	},

	"Shop": {
		"look": Field("look", "1;0"),
		"outfits": Process(Field("dress_list", ""), outfits),
		"mouse_color": Process(Field("color1", ""), from_hex),
		"shaman_color": Process(Field("color2", ""), from_hex),
	},

	"TribeShamanStats": {
		"cheese": Field("shaman_cheese", 0),
		"saves_normal": Field("saved_mice", 0),
		"saves_hard": Field("saved_mice_hard", 0),
		"saves_divine": Field("saved_mice_divine", 0),
	},
	"ShamanStats": {
		"__inherit": "TribeShamanStats",

		"experience": Field("experience", 0),
	},
	"MouseStats": {
		"rounds": Field("round_played", 0),
		"cheese": Field("cheese_gathered", 0),
		"first": Field("first", 0),
		"bootcamp": Field("bootcamp", 0),
	},
	"SurvivorStats": {
		"rounds": Field("round_played", 0),
		"killed": Field("mouse_killed", 0),
		"shaman": Field("shaman_count", 0),
		"survivor": Field("survivor_count", 0),
	},
	"RacingStats": {
		"rounds": Field("round_played", 0),
		"finished": Field("finished_map", 0),
		"first": Field("first", 0),
		"podium": Field("podium", 0),
	},
	"DefilanteStats": {
		"rounds": Field("round_played", 0),
		"finished": Field("finished_map", 0),
		"points": Field("points", 0),
	},
	"ScoreStats": {
		"stats": Field("stats", 0),
		"shaman": Field("shaman", 0),
		"survivor": Field("survivor", 0),
		"racing": Field("racing", 0),
		"defilante": Field("defilante", 0),
		"overall": Field("overall", 0),
	},

	"AllStats": {
		"shaman": Require("ShamanStats"),
		"mouse": Require("MouseStats"),
		"survivor": Require("SurvivorStats", "survivor_"),
		"racing": Require("RacingStats", "racing_"),
		"defilante": Require("DefilanteStats", "defilante_"),
		"score": Require("ScoreStats", "score_"),
	},

	"PlayerProfile": {
		"__inherit": "BasicPlayer",

		"title": Field("title", 0),
		"titles": Process(Field("unlocked_titles", "0"), as_list),
		"badges": Process(Field("badges", ""), as_list),

		"tribe": Require("BasicTribe", "tribe_"),
		"soulmate": Require("BasicPlayer", "sm_"),

		"shop": Require("Shop"),
		"stats": Require("AllStats"),
	},

	"TribeMemberCount": {
		"total": Field("members", 0),
		"active": Field("active", 0),
	},

	"TribeProfile": {
		"__inherit": "BasicTribe",

		"members": Require("TribeMemberCount"),
		"stats": Require("AllStats"),
	},

	"Privacy": {
		"titles": Field("titles", True),
		"shaman": Field("shaman", True),
		"mouse": Field("mouse", True),
		"survivor": Field("survivor", True),
		"racing": Field("racing", True),
		"defilante": Field("defilante", True),
	},

	"AccountInformation": {
		"player": Require("BasicPlayer"),
		"privacy": Require("Privacy"),
	},
}


def _recursive_prefix(compiled, prefix):
	new = {}

	for key, field in compiled.copy().items():
		if key == "__inner_schemas":
			new[key] = {}
			for _key, _field in field.copy().items():
				new[key][_key] = _recursive_prefix(_field, prefix)
			continue

		new[prefix + key] = field

	return new


for name, data in schemas.copy().items():
	if "__inherit" in data:
		inherit = data["__inherit"]
		del data["__inherit"]

		inherit = schemas[inherit].copy()
		inherit.update(data)

		schemas[name] = data = inherit

	inner_schemas = {}
	compiled_schemas[name] = compiled = {"__inner_schemas": inner_schemas}
	for key, action in data.items():
		# Outout: {"db_row": SchemaField("result_row", default, process)}
		if isinstance(action, Field):
			# Just cast normally
			compiled[action.field] = SchemaField(key, action.default)

		elif isinstance(action, Process):
			# Add process function, and process default
			field = action.field

			compiled[field.field] = SchemaField(
				key,
				action.process(field.default),
				action.process
			)

		elif isinstance(action, Require):
			# For a require, we have to add it in inner_schemas
			require = compiled_schemas[action.schema].copy()

			if action.prefix is not None:
				# And we have to add the prefixes to the db_row keys,
				# if any.
				require = _recursive_prefix(require, action.prefix)

			inner_schemas[key] = require


def _as_dict(schema, row, prefix=None):
	if prefix is not None:
		prefix_length = len(prefix)

	result = {}
	for key in row:
		if prefix is not None:
			if not key.startswith(prefix):
				continue

			schema_key = key[prefix_length:]
		else:
			schema_key = key

		if schema_key not in schema:
			continue

		action = schema[schema_key]

		# Convert to result
		if row[key] is None:
			value = action.default  # No need to process
		elif action.process is not None:
			value = action.process(row[key])
		else:
			value = row[key]

		result[action.field] = value

	# Process every inner schema too, recursively
	for name, inner in schema["__inner_schemas"].items():
		result[name] = _as_dict(inner, row, prefix)

	return result


def as_dict(schema_name, row, prefix=None):
	return _as_dict(compiled_schemas[schema_name], row, prefix)


def as_dict_list(schema_name, rows, prefix=None):
	schema = compiled_schemas[schema_name]
	return [_as_dict(schema, row, prefix) for row in rows]
