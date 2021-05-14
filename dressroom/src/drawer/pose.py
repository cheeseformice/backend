import os

from .asset_loader import AssetLoader


assets = os.path.abspath(
	os.path.join(
		__file__,
		"..", "..", "..",
		"assets", "poses"
	)
)
layers = {
	# G = Gauche (left)
	# D = Droite (right)

	# capitalized parts are fur stuff, otherwise costumes
	# section: layer
	"OreilleG": "OreilleG",  # Left ear
	"PiedG": "PiedG",  # Left foot
	"CuisseG": "CuisseG",  # Left thigh

	"PatteG": "PatteG",  # Left paw
	"magic-wand": "PatteG",

	"PiedD": "PiedD",  # Right foot
	"Corps": "Corps",  # Body

	"Queue": "Queue",  # Tail
	# "Boule": "Boule",  # Tail items
	"tail": "Boule",

	"CuisseD": "CuisseD",  # Right thigh

	"Tete": "Tete",  # Head
	"neck": "Tete",
	"hair": "Tete",
	"head": "Tete",
	"mouth": "Tete",

	"PatteD": "PatteD",  # Right paw
	"hands": "PatteD",
	"button-shield": "PatteD",

	"Oeil": "Oeil",  # Eye
	"contact": "Oeil",
	"eyes": "Oeil",

	"OreilleD": "OreilleD",  # Right ear
	"ears": "OreilleD",
}


class Pose(AssetLoader):
	def __init__(self, name):
		self.name = name
		self.matrices = {}

		self.load_asset(os.path.join(assets, "{}.svg".format(name)))

	def preprocess(self):
		g = self.doc.getElementsByTagName("g")[0]
		self.matrices["main"] = g.getAttribute("transform")

		for use in self.doc.getElementsByTagName("use"):
			layer = use.getAttribute("id").split("_", 1)[0]

			self.matrices[layer] = use.getAttribute("transform")

		self.post_costumes = [
			'<g transform="{}">'
			.format(self.matrices["main"])
		]

		for section, layer in layers.items():
			self.post_costumes.append(
				'<use transform="{}" href="#{}" />'
				.format(self.matrices[layer], section)
			)

		self.post_costumes.append("</g>")
		self.post_costumes = "".join(self.post_costumes)

	def generate(self, costumes):
		self._preprocess()

		if not costumes:
			return self.post_costumes

		defs = ["<defs>"]
		to_render = set()
		for costume, _ in costumes:
			to_render.add(costume.section)
			defs.append(costume.mouse_use)
		defs.append("</defs>")
		defs.append(self.post_costumes)

		return "".join(defs)
