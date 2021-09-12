from os.path import abspath, dirname, join
from urllib.request import urlopen
try:
	import ujson as json
except ImportError:
	import json


repo = "cheeseformice/dressroom-assets"
directory = dirname(abspath(__file__))

response = urlopen(f"https://api.github.com/repos/{repo}/releases/latest")
release = json.loads(response.read())

print(f"Using assets from game {release['tag_name']}")

for asset in release["assets"]:
	print(f"Downloading asset {asset['name']}...")

	length = 0
	with open(join(directory, asset["name"]), "wb") as file:
		response = urlopen(asset["browser_download_url"])
		while True:
			chunk = response.read(16 * 1024)
			if not chunk:
				break
			length += len(chunk)
			file.write(chunk)

	print(f"Downloaded {length} bytes.")
