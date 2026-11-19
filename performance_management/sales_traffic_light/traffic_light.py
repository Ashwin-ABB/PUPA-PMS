import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

from performance_management.kra.rating_utils import team_rating_scores

MONTHS = [
	"January", "February", "March", "April", "May", "June",
	"July", "August", "September", "October", "November", "December",
]

# Designations that belong to each sheet (matched case-insensitively)
DESIGNATIONS = {
	"BDE Traffic Light": [
		"SENIOR BUSINESS DEVELOPNMENT EXECUTIVE",
		"SENIOR BUSINESS DEVELOPMENT EXECUTIVE",
		"BUSINESS DEVELOPMENT EXECUTIVE",
	],
	"ASM Traffic Light": ["AREA SALES MANAGER"],
	"Home Care Traffic Light": ["EXECUTIVE BUSINESS DEVELOPMENT"],
	"Inshop Traffic Light": ["EXECUTIVE BUSINESS DEVELOPMENT"],
	"Gallery Traffic Light": ["SALES EXECUTIVE -GALLERY", "GALLERY INCHARGE"],
}

# Score columns of each sheet: (fieldname, label, maximum). Every sheet adds up to 100.
SHEET_FIELDS = {
	"BDE Traffic Light": [
		("feedback_internal", "Team Rating", 5),
		("feedback_external", "Feedback External", 10),
		("meeting", "Meeting", 20),
		("promoter_visit", "Promoter Visit", 10),
		("promoter_conversion", "Promoter Conversion", 15),
		("testimonial", "Testimonial", 5),
		("sales_collection", "Sales & Collection", 35),
	],
	"ASM Traffic Light": [
		("feedback_internal", "Team Rating", 5),
		("feedback_external", "Feedback External", 10),
		("meeting", "Meeting", 20),
		("promoter_visit", "Promoter Visit", 10),
		("promoter_conversion", "Promoter Conversion", 15),
		("testimonial", "Testimonial", 5),
		("sales_collection", "Sales & Collection", 35),
	],
	"Home Care Traffic Light": [
		("internal_feedback", "Team Rating", 10),
		("external_feedback", "External Feedback", 10),
		("sales_collection", "Sales & Collection", 45),
		("road_show", "Road Show", 20),
		("demo_video", "Demo Video", 15),
	],
	"Inshop Traffic Light": [
		("internal_feedback", "Team Rating", 10),
		("external_feedback", "External Feedback", 10),
		("sales_collection", "Sales & Collection", 25),
		("project_conversion", "Project Conversion / Secondary Sales - Inshop", 20),
		("project_visit", "Project Visit / New Product Billing", 5),
		("tea_shop_road_show", "Tea Shop / Road Show", 15),
		("testimonial", "Testimonial", 5),
		("dressing_code", "Dressing Code", 5),
		("display_cleaning", "Display Cleaning", 5),
	],
	"Gallery Traffic Light": [
		("feedback_internal", "Team Rating", 10),
		("feedback_external", "Feedback External", 10),
		("sales", "Sales", 40),
		("promoters_meeting", "Promoters Meeting", 20),
		("google_review", "Google Review", 10),
		("makkal_kural_360", "Makkal Kural, 360 Degree", 10),
	],
}

# Starting colour limits for the BDE / ASM columns, fitted to the colours in the Sep'26 BDE sheet.
# fieldname -> (green from, yellow from). Editable later in "Traffic Light Rules".
BDE_DEFAULTS = {
	"feedback_internal": (4, 3),
	"feedback_external": (8, 6),
	"meeting": (15, 10),
	"promoter_visit": (8, 5),
	"promoter_conversion": (11, 8),
	"testimonial": (5, 3),
	"sales_collection": (30, 20),
}
DEFAULTS_BY_SHEET = {"BDE Traffic Light": BDE_DEFAULTS, "ASM Traffic Light": BDE_DEFAULTS}


# The column on each sheet that is filled automatically from the ratings (Manager Rating Employee and
# Employee Rating Manager): the person's average rating out of 10, scaled to the column's maximum.
TEAM_RATING = {
	"BDE Traffic Light": "feedback_internal",
	"ASM Traffic Light": "feedback_internal",
	"Home Care Traffic Light": "internal_feedback",
	"Inshop Traffic Light": "internal_feedback",
	"Gallery Traffic Light": "feedback_internal",
}


def team_rating_values(doctype, month, year, employees):
	"""employee -> Team Rating value for the sheet's month, scaled to the column's maximum (0 when unrated)."""
	field = TEAM_RATING.get(doctype)
	if not field:
		return {}
	maximum = next(mx for fn, _label, mx in SHEET_FIELDS[doctype] if fn == field)
	scores = team_rating_scores(month, year)
	return {e: round(min(flt(scores.get(e, 0)), 10) * maximum / 10, 2) for e in employees}


@frappe.whitelist()
def get_team_ratings(doctype, date, employees):
	"""Team Rating value of each employee, for the month of the sheet's date."""
	if doctype not in SHEET_FIELDS:
		frappe.throw(_("Unknown sheet type."))
	frappe.has_permission(doctype, "create", throw=True)
	d = getdate(date)
	return team_rating_values(doctype, MONTHS[d.month - 1], d.year, _as_list(employees))


def get_designations(sheet):
	"""Designations chosen in Traffic Light Rules, otherwise the built-in defaults."""
	chosen = frappe.get_all(
		"Traffic Light Designation",
		filters={"parent": sheet, "parenttype": "Traffic Light Rules"},
		pluck="designation",
		order_by="idx asc",
	)
	return [d for d in chosen if d] or DESIGNATIONS[sheet]


def default_rules(sheet):
	"""key -> {green, yellow, red}. A value >= green is Green, >= yellow Yellow, >= red Red, lower Grey."""
	rules = {"total": {"green": 70, "yellow": 50, "red": 40}}
	for fieldname, _label, maximum in SHEET_FIELDS[sheet]:
		green, yellow = DEFAULTS_BY_SHEET.get(sheet, {}).get(
			fieldname, (round(maximum * 0.8, 2), round(maximum * 0.6, 2))
		)
		rules[fieldname] = {"green": green, "yellow": yellow, "red": 0}
	return rules


def rating_for(value, rule):
	value = flt(value)
	if value >= rule["green"]:
		return "Green"
	if value >= rule["yellow"]:
		return "Yellow"
	if value >= rule["red"]:
		return "Red"
	return "Grey"


@frappe.whitelist()
def get_rules(doctype):
	"""Colour limits for a sheet: Traffic Light Rules if present, otherwise the defaults."""
	if doctype not in SHEET_FIELDS:
		frappe.throw(_("Unknown sheet type."))
	rules = default_rules(doctype)
	if frappe.db.exists("Traffic Light Rules", doctype):
		for row in frappe.get_doc("Traffic Light Rules", doctype).rules:
			rules[row.column_key] = {
				"green": flt(row.green_from),
				"yellow": flt(row.yellow_from),
				"red": flt(row.red_from),
			}
	return rules


def ensure_rule_sets():
	"""Create the five rule sets (and add rows for any new column). Runs after install and migrate."""
	for sheet in SHEET_FIELDS:
		defaults = default_rules(sheet)
		if frappe.db.exists("Traffic Light Rules", sheet):
			doc = frappe.get_doc("Traffic Light Rules", sheet)
		else:
			doc = frappe.new_doc("Traffic Light Rules")
			doc.sheet = sheet
		existing = {r.column_key for r in doc.get("rules", [])}
		entries = [("total", "Total", 100)] + [(fn, label, mx) for fn, label, mx in SHEET_FIELDS[sheet]]
		changed = doc.is_new()
		labels = {key: label for key, label, _maximum in entries}
		for row in doc.get("rules", []):
			if row.column_key in labels and row.column_label != labels[row.column_key]:
				row.column_label = labels[row.column_key]
				changed = True
		for key, label, maximum in entries:
			if key not in existing:
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
		# first time only: pre-select the designations that exist in your Designation master
		if not doc.get("designations"):
			for name in DESIGNATIONS[sheet]:
				actual = frappe.db.get_value("Designation", name, "name")
				if actual and actual not in {d.designation for d in doc.get("designations", [])}:
					doc.append("designations", {"designation": actual})
					changed = True
		if changed:
			doc.flags.ignore_permissions = True
			doc.save()
	frappe.db.commit()


def _as_list(value):
	value = frappe.parse_json(value) if value else []
	return [v for v in value if v]


def _filter_designations(doctype, chosen):
	"""The designations a sheet may list: the ones picked on the form (each must belong to the sheet) or all of them."""
	allowed = get_designations(doctype)
	chosen = _as_list(chosen)
	if not chosen:
		return allowed
	ok = {x.casefold() for x in allowed}
	for name in chosen:
		if name.casefold() not in ok:
			frappe.throw(_("{0} is not one of the designations for this sheet.").format(name))
	return chosen


@frappe.whitelist()
def get_filter_options(doctype, designations=None, branches=None):
	"""Options for the form's filters: the sheet's designations, and the departments that actually
	exist among the matching active employees (so Department follows the other selections)."""
	if doctype not in DESIGNATIONS:
		frappe.throw(_("Unknown sheet type."))
	frappe.has_permission(doctype, "create", throw=True)

	filters = {"designation": ["in", _filter_designations(doctype, designations)], "status": "Active"}
	if _as_list(branches):
		filters["branch"] = ["in", _as_list(branches)]
	departments = {d for d in frappe.get_all("Employee", filters=filters, pluck="department") if d}
	return {"designations": get_designations(doctype), "departments": sorted(departments)}


@frappe.whitelist()
def load_employees(doctype, designations=None, departments=None, branches=None):
	"""Active employees for the sheet, narrowed by the designations / departments / branches picked on the form."""
	if doctype not in DESIGNATIONS:
		frappe.throw(_("Unknown sheet type."))
	frappe.has_permission(doctype, "create", throw=True)

	filters = {"designation": ["in", _filter_designations(doctype, designations)], "status": "Active"}
	if _as_list(departments):
		filters["department"] = ["in", _as_list(departments)]
	if _as_list(branches):
		filters["branch"] = ["in", _as_list(branches)]
	return frappe.get_all(
		"Employee",
		filters=filters,
		fields=["name as employee", "employee_name", "branch"],
		order_by="employee_name asc",
	)

RATING_COLOURS = {
	"Green": ("#bbf7d0", "#166534"),
	"Yellow": ("#fef08a", "#854d0e"),
	"Red": ("#fecaca", "#991b1b"),
	"Grey": ("#e5e7eb", "#374151"),
}


def get_print_data(doc):
	"""Rows with a colour for every score and total, for the coloured print format.
	Submitted sheets use the colours stored when they were submitted; drafts use the current limits."""
	rules = get_rules(doc.doctype)

	def paint(key, value, stored):
		rating = (stored.get(key) if doc.docstatus == 1 else None) or rating_for(value, rules[key])
		bg, fg = RATING_COLOURS[rating]
		return {"value": "%g" % round(flt(value), 2), "bg": bg, "fg": fg}

	rows = []
	for row in doc.items:
		try:
			stored = json.loads(row.ratings or "{}")
		except ValueError:
			stored = {}
		rows.append(
			{
				"employee": row.employee,
				"employee_name": row.employee_name,
				"branch": row.branch or frappe.db.get_value("Employee", row.employee, "branch") or "",
				"cells": [paint(fn, row.get(fn), stored) for fn, _label, _max in SHEET_FIELDS[doc.doctype]],
				"total": paint("total", row.total, stored),
			}
		)

	t = rules["total"]
	legend = [
		{"label": "Green", "range": "%g and above" % t["green"]},
		{"label": "Yellow", "range": "%g to below %g" % (t["yellow"], t["green"])},
		{"label": "Red", "range": "%g to below %g" % (t["red"], t["yellow"])},
		{"label": "Grey", "range": "below %g" % t["red"]},
	]
	for item in legend:
		item["bg"], item["fg"] = RATING_COLOURS[item["label"]]
	return {
		"columns": [{"label": label, "max": maximum} for _fn, label, maximum in SHEET_FIELDS[doc.doctype]],
		"rows": rows,
		"legend": legend,
	}

class TrafficLightDocument(Document):
	def validate(self):
		d = getdate(self.date)
		self.month = MONTHS[d.month - 1]
		self.year = d.year
		self.validate_rows()
		self.check_other_sheets()

	def validate_rows(self):
		if not self.items:
			frappe.throw(_("The sheet has no employees."))
		allowed = {x.casefold() for x in get_designations(self.doctype)}
		rules = get_rules(self.doctype)
		auto_field = TEAM_RATING.get(self.doctype)
		auto_values = (
			team_rating_values(self.doctype, self.month, self.year, [r.employee for r in self.items])
			if auto_field
			else {}
		)
		seen = set()
		for row in self.items:
			if row.employee in seen:
				frappe.throw(_("Row {0}: {1} is listed more than once.").format(row.idx, row.employee))
			seen.add(row.employee)

			designation = frappe.db.get_value("Employee", row.employee, "designation") or ""
			if designation.casefold() not in allowed:
				frappe.throw(
					_("Row {0}: {1} has designation '{2}', which does not belong to this sheet.").format(
						row.idx, row.employee, designation
					)
				)

			total = 0
			ratings = {}
			for fieldname, label, maximum in SHEET_FIELDS[self.doctype]:
				if fieldname == auto_field:
					# filled from the ratings, never typed in
					row.set(fieldname, auto_values.get(row.employee, 0))
				value = flt(row.get(fieldname))
				if value < 0 or value > maximum:
					frappe.throw(
						_("Row {0} ({1}): {2} must be between 0 and {3}.").format(
							row.idx, row.employee_name or row.employee, label, maximum
						)
					)
				total += value
				ratings[fieldname] = rating_for(value, rules[fieldname])
			row.total = round(total, 2)
			row.rating = rating_for(row.total, rules["total"])
			ratings["total"] = row.rating
			row.ratings = json.dumps(ratings)

	def check_other_sheets(self):
		"""An employee can be scored only once per month on a given sheet type."""
		child_doctype = self.meta.get_field("items").options
		employees = tuple(r.employee for r in self.items)
		rows = frappe.db.sql(
			f"""
			select c.employee, p.name
			from `tab{child_doctype}` c
			inner join `tab{self.doctype}` p on p.name = c.parent
			where p.month = %s and p.year = %s and p.docstatus < 2
				and p.name != %s and c.employee in %s
			""",
			(self.month, self.year, self.name or "", employees),
		)
		if rows:
			frappe.throw(
				_("{0} is already scored for {1} {2} in {3}.").format(
					rows[0][0], self.month, self.year, rows[0][1]
				)
			)
