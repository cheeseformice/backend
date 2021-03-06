import os

from .pose import Pose
from .fur import Fur
from .costume import sections, Costume
from .shaman import Shaman


assets = os.path.abspath(
	os.path.join(
		__file__,
		"..", "..", "..", "assets"
	)
)

get_section_name = sections.get

pose_list, fur_list, costume_list, shaman_list = [], [], {}, []
poses_cache, furs_cache, costumes_cache, shamans_cache = {}, {}, {}, {}


def read_assets():
	global pose_list, fur_list, costume_list, shaman_list
	global poses_cache, furs_cache, costumes_cache, shamans_cache

	pose_list, fur_list, costume_list, shaman_list = [], [], {}, []
	poses_cache, furs_cache, costumes_cache, shamans_cache = {}, {}, {}, {}

	for pose in os.listdir(
		os.path.join(assets, "poses")
	):
		name, ext = pose.rsplit(".", 1)
		if ext != "svg":
			continue

		pose_list.append(name)

	for fur in os.listdir(
		os.path.join(assets, "furs")
	):
		if not fur.isdigit():
			continue

		fur_list.append(int(fur))

	for section in sections.values():
		costumes = []
		costume_list[section] = costumes

		for costume in os.listdir(
			os.path.join(assets, "costumes", section)
		):
			name, ext = costume.rsplit(".", 1)
			if ext != "svg" or not name.isdigit():
				continue

			costumes.append(int(name))

	for section in sections.values():
		costumes_cache[section] = {}

	for item in os.listdir(
		os.path.join(assets, "shaman")
	):
		_id, ext = item.rsplit(".", 1)
		if ext != "svg":
			continue
		if not _id.isdigit():
			continue

		shaman_list.append(int(_id))


def get_pose(pose, head: bool):
	if pose not in pose_list:
		return

	if pose not in poses_cache:
		poses_cache[pose] = {
			True: Pose(pose, True),
			False: Pose(pose, False),
		}

	return poses_cache[pose][head]


def get_fur(fur):
	if fur not in fur_list:
		return

	if fur not in furs_cache:
		furs_cache[fur] = Fur(fur)

	return furs_cache[fur]


def get_costume(section_name, costume):
	if section_name not in costume_list:
		return

	section = costume_list[section_name]
	if costume not in section:
		return

	cache = costumes_cache[section_name]
	if costume not in cache:
		cache[costume] = Costume(section_name, costume)

	return cache[costume]


def get_shaman_item(item):
	if item not in shaman_list:
		return

	if item not in shamans_cache:
		shamans_cache[item] = Shaman(item)

	return shamans_cache[item]


read_assets()
