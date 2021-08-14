from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass(init=False)
class Fields:
	special: bool
	conversions: Optional[Tuple[Tuple[str]]]

	def __init__(self, *conversions, special: bool=False) -> None:
		self.special = special

		if not special and conversions:
			if len(conversions) == 1 and isinstance(conversions[0], str):
				self.conversions = ((conversions[0], conversions[0]))
			else:
				self.conversions = conversions
		else:
			self.conversions = None


@dataclass
class LogInfo:
	public: bool
	fields: Fields
	invisible: bool = False
	name: str = ""  # defined after init


@dataclass(init=False)
class LogContainer:
	names: Tuple[str]
	logs: Dict[str, LogInfo]

	def __init__(self, **logs) -> None:
		self.names = tuple(logs.keys())
		self.logs = logs

		for name, log_info in logs.items():
			log_info.name = name

	def filter(self, mask: int) -> Dict[str, LogInfo]:
		logs: Dict[str, LogInfo] = {}

		for idx, name in enumerate(self.names):
			if not mask & (2 ** idx):
				# not in mask
				continue

			log_info = self.logs[name]
			if log_info.invisible:
				# not meant to be shown to anyone
				continue

			logs[name] = log_info

		return logs


PlayerLogs = LogContainer(
	names=LogInfo(public=False, fields=Fields("name"), invisible=True),
	soulmate=LogInfo(public=False, fields=Fields(special=True)),
	tribe=LogInfo(public=False, fields=Fields(special=True)),
	look=LogInfo(public=False, fields=Fields("look"), invisible=True),
	badges=LogInfo(public=True, fields=Fields(special=True), invisible=True),
	titles=LogInfo(public=True, fields=Fields(special=True)),
	shaman=LogInfo(public=True, fields=Fields(
		("experience", "experience"),
		("shaman_cheese", "cheese"),
		("saved_mice", "saves_normal"),
		("saved_mice_hard", "saves_hard"),
		("saved_mice_divine", "saves_divine"),
		("score_shaman", "score"),
	)),
	mouse=LogInfo(public=True, fields=Fields(
		("round_played", "rounds"),
		("cheese_gathered", "cheese"),
		("first", "first"),
		("bootcamp", "bootcamp"),
		("score_stats", "score"),
		("score_overall", "overall_score"),
	)),
	survivor=LogInfo(public=True, fields=Fields(
		("survivor_round_played", "rounds"),
		("survivor_mouse_killed", "killed"),
		("survivor_shaman_count", "shaman"),
		("survivor_survivor_count", "survivor"),
		("score_survivor", "score"),
	)),
	racing=LogInfo(public=True, fields=Fields(
		("racing_round_played", "rounds"),
		("racing_finished_map", "finished"),
		("racing_first", "first"),
		("racing_podium", "podium"),
		("score_racing", "score"),
	)),
	defilante=LogInfo(public=True, fields=Fields(
		("defilante_round_played", "rounds"),
		("defilante_finished_map", "finished"),
		("defilante_points", "points"),
		("score_defilante", "score"),
	)),
)
TribeLogs = LogContainer(
	members=LogInfo(public=True, fields=Fields("members")),
	active=LogInfo(public=True, fields=Fields("active")),
	shaman=LogInfo(public=True, fields=Fields(  # everything but experience
		("shaman_cheese", "cheese"),
		("saved_mice", "saves_normal"),
		("saved_mice_hard", "saves_hard"),
		("saved_mice_divine", "saves_divine"),
		("score_shaman", "score"),
	)),
	mouse=PlayerLogs.logs["mouse"],
	survivor=PlayerLogs.logs["survivor"],
	racing=PlayerLogs.logs["racing"],
	defilante=PlayerLogs.logs["defilante"],
)