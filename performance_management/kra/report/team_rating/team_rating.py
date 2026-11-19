import frappe
from frappe import _
from frappe.utils import cint, flt

from performance_management.kra.rating_utils import MONTHS, team_rating_details


def execute(filters=None):
	filters = frappe._dict(filters or {})
	month = filters.month
	year = cint(filters.year)
	if month not in MONTHS or not year:
		frappe.throw(_("Please select a Month and a Year."))

	details = team_rating_details(month, year, filters.employee)
	names = {
		r.name: r.employee_name
		for r in frappe.get_all("Employee", filters={"name": ["in", list(details) or [""]]}, fields=["name", "employee_name"])
	}

	data = []
	for employee, parts in details.items():
		(m_total, m_count), (t_total, t_count) = parts["manager"], parts["team"]
		count = m_count + t_count
		if not count:
			continue
		data.append(
			{
				"employee": employee,
				"employee_name": names.get(employee, ""),
				"from_manager": round(m_total / m_count, 2) if m_count else None,
				"manager_ratings": m_count,
				"from_team": round(t_total / t_count, 2) if t_count else None,
				"team_ratings": t_count,
				"team_rating": round(min((m_total + t_total) / count, 10), 2),
			}
		)
	data.sort(key=lambda r: (r["employee_name"] or "").lower())
	return get_columns(), data


def get_columns():
	def col(fieldname, label, fieldtype="Float", width=130, **kw):
		return {"fieldname": fieldname, "label": label, "fieldtype": fieldtype, "width": width, **kw}

	return [
		col("employee", _("Emp Code"), "Link", 110, options="Employee"),
		col("employee_name", _("Employee Name"), "Data", 200),
		col("from_manager", _("Manager's Rating (out of 10)"), precision=2, width=170),
		col("manager_ratings", _("Manager Ratings"), "Int", 120),
		col("from_team", _("Team's Rating (out of 10)"), precision=2, width=160),
		col("team_ratings", _("Team Ratings"), "Int", 110),
		col("team_rating", _("Team Rating (10)"), precision=2, width=140),
	]
