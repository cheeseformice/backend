import os

from .asset_loader import AssetLoader
from .utils import get_color_filter


assets = os.path.abspath(
	os.path.join(
		__file__,
		"..", "..", "..",
		"assets", "furs"
	)
)


class Fur(AssetLoader):
	def __init__(self, _id):
		self.id = _id

		self.id_format = "fur_{}_{{}}_{{{{}}}}".format(_id).format
		self.load_asset(os.path.join(assets, "{}".format(_id)))

	def preprocess(self):
		for section, doc in self.docs:
			for use in doc.getElementsByTagName("use"):
				_id = use.getAttribute("id")

				if _id == "c1" \
					or section == "Corps" \
					and "shape2" in use.getAttribute("xlink:href"):
					# This is a shaman-specific part, just remove it
					parent = use.parentNode
					parent.removeChild(use)

				elif _id == "c0":
					# This is a part to color
					use.setAttribute("filter", "url(#color_fur)")

		super().preprocess()

		self._pose_asset = ["<defs>"]

		for section, doc in self.docs:
			g = doc.getElementsByTagName("g")[0]
			# Make this part available to be referenced from a Pose
			g.setAttribute("id", section)
			# and remove the transform for it
			g.removeAttribute("transform")

			self._pose_asset.append(g.toxml())

		self._pose_asset.append("</defs>")

		self._pose_asset = "".join(self._pose_asset)

	@property
	def pose_asset(self):
		self._preprocess()
		return self._pose_asset

	def generate_color(self, color):
		if color is None:
			color = 0x78583A

		return get_color_filter("fur", color)
