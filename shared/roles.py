cfm_roles = (
	"dev",
	"admin",
	"mod",
	"translator",
	"trainee",
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


def from_role_factory(enum):
	def from_roles(roles):
		bits = 0
		for role in roles:
			bits |= 2 ** enum.index(role)
		return bits
	return from_roles


def to_role_factory(enum):
	def to_roles(bits):
		if bits == 0:
			return []

		roles = []
		for idx, role in enumerate(enum):
			if bits & (2 ** idx):
				roles.append(role)

		return roles
	return to_roles


from_cfm_roles = from_role_factory(cfm_roles)
from_tfm_roles = from_role_factory(tfm_roles)
to_cfm_roles = to_role_factory(cfm_roles)
to_tfm_roles = to_role_factory(tfm_roles)
