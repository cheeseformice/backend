import os

from .asset_loader import AssetLoader
from .utils import get_color_filter


assets = os.path.abspath(
	os.path.join(
		__file__,
		"..", "..", "..",
		"assets", "costumes"
	)
)

sections = dict(enumerate([
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
]))


class Costume(AssetLoader):
	def __init__(self, section, _id):
		self.section = section
		self.colors = []
		self.id = _id

		self.id_format = "costume_{}_{}_{{}}".format(section, _id).format
		self.load_asset(os.path.join(assets, section, "{}.svg".format(_id)))

	def preprocess(self):
		self.colors = colors = {}

		# Add color filters to the costume
		for use in self.doc.getElementsByTagName("use"):
			_id = use.getAttribute("id")

			if "Couleur" in _id:
				name, hexa = _id.split("_")

				color_id = int(name[7:])
				color = int(hexa, 16)
				colors[color_id] = color

				use.setAttribute(
					"filter",
					"url(#color_{})".format(self.id_format(color_id))
				)

		super().preprocess()

		g = self.doc.getElementsByTagName("g")[0]
		g.setAttribute("id", self.section)

		self._render = g.toxml()

		has_attribute = g.hasAttribute("transform")
		if has_attribute:
			transform = g.getAttribute("transform")
			g.removeAttribute("transform")

		self._mouse_use = g.toxml()

		if has_attribute:
			g.setAttribute("transform", transform)

	def generate_color(self, colors):
		self._preprocess()

		amount = len(colors)

		filters = []
		for idx, color in self.colors.items():
			if amount > idx:
				color = colors[idx]

			filters.append(get_color_filter(self.id_format(idx), color))

		return filters

	@property
	def render(self):
		self._preprocess()
		return self._render

	@property
	def mouse_use(self):
		self._preprocess()
		return self._mouse_use
