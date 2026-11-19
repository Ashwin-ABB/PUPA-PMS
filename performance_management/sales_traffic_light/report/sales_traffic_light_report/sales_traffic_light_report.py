import json

import frappe
from frappe import _
from frappe.utils import cint, flt

from performance_management.kra.rating_utils import MONTHS
from performance_management.sales_traffic_light.traffic_light import SHEET_FIELDS

SCORE_COLUMNS = 9  # the widest sheet (Inshop) has nine score columns


def execute(filters=None):
	filters = frappe._dict(filters or {})
	month = filters.month
	year = cint(filters.year)
	if month not in MONTHS or not year:
		frappe.throw(_("Please select a Month and a Year."))

	data = []
	for sheet, fields in SHEET_FIELDS.items():
		score_columns = ", ".join("c.`%s`" % fieldname for fieldname, _label, _maximum in fields)
		conditions = "p.month = %s and p.year = %s and p.docstatus < 2"
		params = [month, year]
		if filters.employee:
			conditions += " and c.employee = %s"
			params.append(filters.employee)
		rows = frappe.db.sql(
			"""
			select c.employee, c.employee_name, c.branch, c.total, c.ratings, p.docstatus, {columns}
			from `tab{child}` c
			inner join `tab{parent}` p on p.name = c.parent
			where {conditions}
			order by c.employee_name
			""".format(columns=score_columns, child=sheet + " Item", parent=sheet, conditions=conditions),
			params,
			as_dict=True,
		)
		if not rows:
			continue

		# each sheet is a block: a title row, a row naming its columns, then one row per employee
		data.append({"row_type": "title", "employee_name": "%s - %s %s" % (sheet.upper(), month.upper(), year)})
		labels = {"row_type": "labels", "employee": "Emp Code", "employee_name": "Name", "branch": "Branch", "status": "Status"}
		for i, (_fieldname, label, maximum) in enumerate(fields, 1):
			labels["c%d" % i] = "%s (%d)" % (label, maximum)
		labels["total"] = "Total (100)"
		data.append(labels)

		for r in rows:
			try:
				ratings = json.loads(r.ratings or "{}")
			except ValueError:
				ratings = {}
			row = {
				"row_type": "row",
				"employee": r.employee,
				"employee_name": r.employee_name,
				"branch": r.branch,
				"status": _("Submitted") if r.docstatus == 1 else _("Draft"),
				"total": "%g" % round(flt(r.total), 2),
				"total_rating": ratings.get("total"),
			}
			for i, (fieldname, _label, _maximum) in enumerate(fields, 1):
				row["c%d" % i] = "%g" % round(flt(r.get(fieldname)), 2)
				row["c%d_rating" % i] = ratings.get(fieldname)
			data.append(row)

	return get_columns(), data


def get_columns():
	def col(fieldname, label, width=110, **kw):
		return {"fieldname": fieldname, "label": label, "fieldtype": "Data", "width": width, **kw}

	columns = [
		col("employee", _("Emp Code"), 100),
		col("employee_name", _("Name"), 190),
		col("branch", _("Branch"), 90),
		col("status", _("Status"), 90),
	]
	columns += [col("c%d" % i, _("Score {0}").format(i), 120) for i in range(1, SCORE_COLUMNS + 1)]
	columns.append(col("total", _("Total"), 90))
	# ratings travel with each row so the report can colour the cells
	columns += [col("c%d_rating" % i, "", 0, hidden=1) for i in range(1, SCORE_COLUMNS + 1)]
	columns.append(col("total_rating", "", 0, hidden=1))
	return columns
