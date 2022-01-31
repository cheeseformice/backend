def get_color_matrix(color):
	r = (color >> 16 & 255) / 255
	g = (color >> 8 & 255) / 255
	b = (color & 255) / 255

	return "1 0 0 0 {} \
			0 1 0 0 {} \
			0 0 1 0 {} \
			0 0 0 1 0".format(r - 0.5, g - 0.5, b - 0.5)


def get_color_filter(_id, color):
	return '<filter id="color_{}" \
				x="-100%" y="-100%" width="300%" height="300%" \
				filterUnits="objectBoundingBox" \
				primitiveUnits="userSpaceOnUse" \
				color-interpolation-filters="sRGB"> \
				\
				<feColorMatrix type="matrix" values="{}" \
					x="-100%" y="-100%" width="300%" height="300%" \
					in="colormatrix" result="colormatrix1" /> \
			</filter>'.format(_id, get_color_matrix(color))
