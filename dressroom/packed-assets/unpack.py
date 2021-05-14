import os
import shutil
import zipfile
import tempfile


src = os.path.abspath(os.path.join(__file__, ".."))
target = os.path.join(src, "..", "assets")
poses_dir = os.path.join(target, "poses")
furs_dir = os.path.join(target, "furs")
costumes_dir = os.path.join(target, "costumes")

sections = [
	"head",
	"eyes",
	"ears",
	"mouth",
	"neck",
	"hair",
	"tail",
	"contact",
	"hands",
	"magic-wand",
	"button-shield",
]


for path in (target, poses_dir, furs_dir, costumes_dir):
	if not os.path.isdir(path):
		os.mkdir(path)

for section in sections:
	path = os.path.join(costumes_dir, section)
	if not os.path.isdir(path):
		os.mkdir(path)


def remove_first_line(path):
	with open(path, "r+b") as file:
		file.readline()  # Ignore first line

		content = file.read()
		file.truncate(0)
		file.seek(0)

		file.write(content)


def preprocess_poses(path):
	renames = []

	for directory in os.listdir(path):
		if "Anim" not in directory:
			continue

		_, name = directory.split("Anim", 1)

		tmp = os.path.join(path, directory, "1.svg")
		remove_first_line(tmp)

		renames.append((
			tmp,
			os.path.join(poses_dir, "{}.svg".format(name.lower()))
		))

	return renames


def preprocess_furs(path):
	furs = set()
	renames = []

	for directory in os.listdir(path):
		if "__" not in directory:
			continue

		tmpdir = os.path.join(path, directory)

		_, _, _, part, pose, fur, _type = directory.split("_")
		if pose != "1" or _type != "1":
			continue

		target_dir = os.path.join(furs_dir, fur)

		if fur not in furs:
			if not os.path.isdir(target_dir):
				os.mkdir(target_dir)

			furs.add(fur)

		tmpfile = os.path.join(tmpdir, "1.svg")
		remove_first_line(tmpfile)

		renames.append((
			tmpfile,
			os.path.join(target_dir, "{}.svg".format(part))
		))

	return renames


def preprocess_costumes(path):
	renames = []

	for directory in os.listdir(path):
		if "$" not in directory:
			continue

		if directory.endswith("$P6"):
			continue

		_, _, _, section, _id = directory.split("_")
		section_name = sections[int(section)]

		tmp = os.path.join(path, directory, "1.svg")
		remove_first_line(tmp)

		renames.append((
			tmp,
			os.path.join(costumes_dir, section_name, "{}.svg".format(_id))
		))

	return renames


def apply_renames(renames):
	for source, dest in renames:
		if os.path.exists(dest):
			if os.path.isdir(dest):
				shutil.rmtree(dest)
			else:
				os.remove(dest)

		os.rename(source, dest)


for file in os.listdir(src):
	if not file.endswith(".zip"):
		continue

	with tempfile.TemporaryDirectory() as tmp:
		with zipfile.ZipFile(os.path.join(src, file)) as zip_ref:
			zip_ref.extractall(tmp)

		for directory in os.listdir(tmp):
			path = os.path.join(tmp, directory)

			if directory == "poses":
				renames = preprocess_poses(path)

			elif directory == "furs":
				renames = preprocess_furs(path)

			elif directory == "costumes":
				renames = preprocess_costumes(path)

			else:
				continue

			apply_renames(renames)

	print("extracted", file)
