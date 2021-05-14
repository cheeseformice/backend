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
				x="-20%" y="-20%" width="140%" height="140%" \
				filterUnits="objectBoundingBox" \
				primitiveUnits="userSpaceOnUse" \
				color-interpolation-filters="sRGB"> \
				\
				<feColorMatrix type="matrix" values="{}" \
					x="0%" y="0%" width="100%" height="100%" \
					in="colormatrix" result="colormatrix1" /> \
			</filter>'.format(_id, get_color_matrix(color))
