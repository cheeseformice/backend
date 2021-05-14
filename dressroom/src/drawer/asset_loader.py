import os

from typing import Callable
from xml.dom import minidom


class AssetLoader:
	id_format: Callable[[str], str]
	preprocessed: bool

	def load_asset(self, path):
		self.preprocessed = False

		if os.path.isdir(path):
			self.multi = True
			self.docs = []
			for file in os.listdir(path):
				self.docs.append((
					file.rsplit(".", 1)[0],
					minidom.parse(os.path.join(path, file))
				))

		else:
			self.multi = False
			self.doc = minidom.parse(path)

	def replace_id(self, node, id_format):
		if node.nodeType == minidom.Node.ELEMENT_NODE:
			if node.hasAttribute("id"):
				node.setAttribute(
					"id",
					id_format(node.getAttribute("id"))
				)

			if node.hasAttribute("xlink:href"):
				ref = node.getAttribute("xlink:href")[1:]
				node.removeAttribute("xlink:href")  # Deprecated
				node.setAttribute(
					"href",
					"#{}".format(id_format(ref))
				)

			if node.hasAttribute("fill"):
				fill = node.getAttribute("fill")
				if fill.startswith("url(#"):
					node.setAttribute(
						"fill",
						"url(#{})".format(id_format(fill[5:-1]))
					)

		for child in node.childNodes:
			self.replace_id(child, id_format)

	def get_definitions(self, doc):
		defs = doc.getElementsByTagName("defs")
		if defs:
			return defs[0].toxml()
		return ""

	def preprocess(self):
		if self.multi:
			definitions = []

			for section, doc in self.docs:
				id_format = self.id_format(section).format

				self.replace_id(doc, id_format)
				definitions.append(self.get_definitions(doc))

			self.definitions = "".join(definitions)

		else:
			self.replace_id(self.doc, self.id_format)
			self.definitions = self.get_definitions(self.doc)

	def _preprocess(self):
		if not self.preprocessed:
			self.preprocess()
			self.preprocessed = True

	@property
	def asset(self):
		self._preprocess()
		return self.definitions
