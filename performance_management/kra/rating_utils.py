import frappe
from frappe import _
from frappe.utils import cint, flt

MONTHS = [
	"January", "February", "March", "April", "May", "June",
	"July", "August", "September", "October", "November", "December",
]
PRIVILEGED_ROLES = {"System Manager", "HR Manager"}

# The 1 to 10 scale shown in the rating dropdowns. The score for each is kept in Rating Score Master.
RATING_OPTIONS = [
	"1 - Unacceptable",
	"2 - Poor Performance",
	"3 - Weak",
	"4 - Not Satisfied",
	"5 - Average",
	"6 - Above Average",
	"7 - Good",
	"8 - Very Good",
	"9 - Excellent",
	"10 - Outstanding",
]


def own_employee():
	return frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"}, "name")


def require_own(employee, message):
	"""HR / System Manager can act for anyone; everyone else only as themselves."""
	if PRIVILEGED_ROLES & set(frappe.get_roles()):
		return
	if own_employee() != employee:
		frappe.throw(message)


def check_reports_to(manager, employee):
	if manager == employee:
		frappe.throw(_("The manager and the employee cannot be the same person."))
	if frappe.db.get_value("Employee", employee, "reports_to") != manager:
		frappe.throw(_("{0} does not report to {1}.").format(employee, manager))


def rating_score(label):
	"""(rating number, score) for a rating such as '8 - Very Good'; the score comes from Rating Score Master."""
	if not label:
		return 0, 0
	number = cint(label.split(" - ")[0])
	score = frappe.db.get_value("Rating Score Master", label, "score")
	return number, flt(score) if score is not None else flt(number)


def previous_month(d):
	"""Month name and year of the month before date d."""
	year, month = d.year, d.month - 1
	if month == 0:
		month, year = 12, year - 1
	return MONTHS[month - 1], year


@frappe.whitelist()
def get_managers():
	"""Active employees that at least one active employee reports to."""
	rows = frappe.get_all("Employee", filters={"status": "Active", "reports_to": ["is", "set"]}, pluck="reports_to")
	return sorted(set(rows))


def team_rating_details(month, year, employee=None):
	"""Ratings each person received in a month, from both directions:
	- their manager's rating of them (Manager Rating Employee, the Employee Name is the person rated), and
	- their team's rating of them as a manager (Employee Rating Manager, the Manager Name is the person rated).
	Returns {employee: {"manager": [total, count], "team": [total, count]}}."""
	out = {}

	def collect(query, params, key):
		for employee_id, total, count in frappe.db.sql(query, params):
			entry = out.setdefault(employee_id, {"manager": [0, 0], "team": [0, 0]})
			entry[key] = [flt(total), cint(count)]

	extra = " and {0} = %s" if employee else ""
	collect(
		"select employee, sum(score), count(*) from `tabManager Rating Employee` "
		"where rated_month = %s and rated_year = %s and docstatus < 2" + extra.format("employee") + " group by employee",
		(month, year) + ((employee,) if employee else ()),
		"manager",
	)
	collect(
		"select manager, sum(score), count(*) from `tabEmployee Rating Manager` "
		"where rating_month_name = %s and rating_year = %s and docstatus < 2" + extra.format("manager") + " group by manager",
		(month, year) + ((employee,) if employee else ()),
		"team",
	)
	return out


def team_rating_scores(month, year):
	"""{employee: Team Rating out of 10}: the average of every rating the person received in the month,
	from their manager and from their team together."""
	scores = {}
	for employee, parts in team_rating_details(month, year).items():
		total = parts["manager"][0] + parts["team"][0]
		count = parts["manager"][1] + parts["team"][1]
		if count:
			scores[employee] = round(min(total / count, 10), 2)
	return scores
