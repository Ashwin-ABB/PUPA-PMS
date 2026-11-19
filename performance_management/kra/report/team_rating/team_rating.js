const MONTH_NAMES = [
	"January", "February", "March", "April", "May", "June",
	"July", "August", "September", "October", "November", "December",
];

frappe.query_reports["Team Rating"] = {
	filters: [
		{
			fieldname: "month",
			label: __("Month"),
			fieldtype: "Select",
			options: MONTH_NAMES.join("\n"),
			default: MONTH_NAMES[new Date().getMonth()],
			reqd: 1,
		},
		{
			fieldname: "year",
			label: __("Year"),
			fieldtype: "Int",
			default: new Date().getFullYear(),
			reqd: 1,
		},
		{
			fieldname: "employee",
			label: __("Employee Name"),
			fieldtype: "Link",
			options: "Employee",
		},
	],
};
