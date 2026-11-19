import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

# Maximum of each column. Internal Feedback is out of 20, KPI is stored out of 100 and shown out of 60,
# PTS is shown out of 10, and Team Rating (the average rating out of 10) is used as it is.
TEAM_RATING_MAX = 10
INTERNAL_FEEDBACK_MAX = 20
KPI_MAX = 60
PTS_MAX = 10
TOTAL_MAX = 100

# key (report fieldname), label, maximum
COLUMNS = [
	("team_rating", "Team Rating", TEAM_RATING_MAX),
	("internal_feedback", "Internal Feedback", INTERNAL_FEEDBACK_MAX),
	("kpi_score", "KPI Score", KPI_MAX),
	("pts_score", "PTS", PTS_MAX),
	("total_score", "Total Score", TOTAL_MAX),
]


def default_rules():
	"""key -> {green, yellow, red}. Total starts at 70 / 50 / 40; the others at 80% / 60% of their maximum."""
	rules = {}
	for key, _label, maximum in COLUMNS:
		if key == "total_score":
			rules[key] = {"green": 70, "yellow": 50, "red": 40}
		else:
			rules[key] = {"green": round(maximum * 0.8, 2), "yellow": round(maximum * 0.6, 2), "red": 0}
	return rules


def get_rules():
	"""Colour limits from HO Traffic Light Settings, falling back to the defaults."""
	rules = default_rules()
	rows = frappe.get_all(
		"HO Traffic Light Rule",
		filters={"parent": "HO Traffic Light Settings", "parenttype": "HO Traffic Light Settings"},
		fields=["column_key", "green_from", "yellow_from", "red_from"],
	)
	for row in rows:
		if row.column_key in rules:
			rules[row.column_key] = {
				"green": flt(row.green_from),
				"yellow": flt(row.yellow_from),
				"red": flt(row.red_from),
			}
	return rules


def rating_for(value, rule):
	if value is None:
		return None
	value = flt(value)
	if value >= rule["green"]:
		return "Green"
	if value >= rule["yellow"]:
		return "Yellow"
	if value >= rule["red"]:
		return "Red"
	return "Grey"


def ensure_defaults():
	"""Fill the rule rows, and bring older rows in line (new maximums, renamed or removed columns).
	Runs after install and migrate."""
	doc = frappe.get_single("HO Traffic Light Settings")
	defaults = default_rules()
	keys = {key for key, _label, _maximum in COLUMNS}
	changed = False

	# drop rows of columns that no longer exist (for example the old Feedback Rating)
	keep = [r for r in doc.get("rules", []) if r.column_key in keys]
	if len(keep) != len(doc.get("rules", [])):
		doc.set("rules", keep)
		changed = True

	existing = {r.column_key: r for r in doc.get("rules", [])}
	for key, label, maximum in COLUMNS:
		row = existing.get(key)
		if row is None:
			d = defaults[key]
			doc.append(
				"rules",
				{
					"column_key": key,
					"column_label": label,
					"maximum": maximum,
					"green_from": d["green"],
					"yellow_from": d["yellow"],
					"red_from": d["red"],
				},
			)
			changed = True
			continue
		old_max = flt(row.maximum)
		if old_max and abs(old_max - maximum) > 1e-9:
			# keep the same percentages when a column's maximum changes
			ratio = maximum / old_max
			row.green_from = round(flt(row.green_from) * ratio, 2)
			row.yellow_from = round(flt(row.yellow_from) * ratio, 2)
			row.red_from = round(flt(row.red_from) * ratio, 2)
			row.maximum = maximum
			changed = True
		if row.column_label != label:
			row.column_label = label
			changed = True

	if changed:
		doc.flags.ignore_permissions = True
		doc.save()
		frappe.db.commit()


class HOTrafficLightSettings(Document):
	def validate(self):
		for row in self.rules:
			green, yellow, red = flt(row.green_from), flt(row.yellow_from), flt(row.red_from)
			maximum = flt(row.maximum) or 100
			if not (0 <= red < yellow < green <= maximum):
				frappe.throw(
					_("Row {0} ({1}): limits must satisfy 0 <= Red < Yellow < Green <= {2}.").format(
						row.idx, row.column_label, maximum
					)
				)
