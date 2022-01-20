cfm_roles = (
	"dev",
	"admin",
	"mod",
	"translator",
)
tfm_roles = (
	"admin",
	"mod",
	"sentinel",
	"mapcrew",
	"module",
	"funcorp",
	"fashion",
	"flash",
	"event",
	"discorderator",
)


def from_cfm_roles(roles):
	bits = 0
	for role in roles:
		bits |= 2 ** cfm_roles.index(role)
	return bits


def to_role_factory(*enum):
	def to_roles(bits):
		if bits == 0:
			return []

		roles = []
		for idx, role in enumerate(enum):
			if bits & (2 ** idx):
				roles.append(role)

		return roles

	return to_roles


to_cfm_roles = to_role_factory(*cfm_roles)
to_tfm_roles = to_role_factory(*tfm_roles)
