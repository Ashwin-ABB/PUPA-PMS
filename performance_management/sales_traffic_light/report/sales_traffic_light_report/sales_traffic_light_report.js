const MONTH_NAMES = [
	"January", "February", "March", "April", "May", "June",
	"July", "August", "September", "October", "November", "December",
];
const CELL_COLOURS = {
	Green: ["#bbf7d0", "#166534"],
	Yellow: ["#fef08a", "#854d0e"],
	Red: ["#fecaca", "#991b1b"],
	Grey: ["#e5e7eb", "#374151"],
};

frappe.query_reports["Sales Traffic Light Report"] = {
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

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) {
			return value;
		}
		if (data.row_type === "title") {
			return '<div style="background:#1f3a5f;color:#fff;font-weight:700;padding:2px 4px;white-space:nowrap">' + value + "</div>";
		}
		if (data.row_type === "labels") {
			return '<div style="background:#e5e7eb;font-weight:700;text-align:center;white-space:normal;line-height:1.2">' + value + "</div>";
		}
		const rating = data[column.fieldname + "_rating"];
		if (rating && CELL_COLOURS[rating]) {
			const c = CELL_COLOURS[rating];
			return '<div style="text-align:center;font-weight:600;background:' + c[0] + ";color:" + c[1] + ';">' + value + "</div>";
		}
		return value;
	},
};
