const TL = {
 "child": "Worker Traffic Light Item",
 "fields": [
  {
   "fn": "attendance",
   "label": "வருகை",
   "max": 10
  },
  {
   "fn": "punctuality",
   "label": "நேரம் தவறாமை",
   "max": 10
  },
  {
   "fn": "behaviour_with_colleagues",
   "label": "சக ஊழியர்களிடம் பழகும் விதம்",
   "max": 15
  },
  {
   "fn": "work_speed",
   "label": "வேலையின் வேகம்",
   "max": 20
  },
  {
   "fn": "five_s_surroundings",
   "label": "5 S & சுற்றுப்புற பராமரிப்பு",
   "max": 20
  },
  {
   "fn": "dedication_responsibility",
   "label": "வேலை அர்ப்பணிப்பு மற்றும் பொறுப்பு",
   "max": 25
  }
 ]
};

const RATING_STYLE = {
	Green: ["#bbf7d0", "#166534"],
	Yellow: ["#fef08a", "#854d0e"],
	Red: ["#fecaca", "#991b1b"],
	Grey: ["#e5e7eb", "#374151"],
};
let RULES = {};

frappe.ui.form.on("Worker Traffic Light", {
	setup(frm) {
		set_filter_queries(frm);
	},
	onload(frm) {
		if (frm.is_new() && !(frm.doc.items || []).length) {
			refresh_filter_options(frm).then(() => fill_rows(frm));
		}
	},
	refresh(frm) {
		if (!frm.is_new()) {
			refresh_filter_options(frm);
		}
		load_rules(frm).then(() => render_sheet(frm));
	},
	filter_designations(frm) {
		refresh_filter_options(frm).then(() => fill_rows(frm));
	},
	filter_branches(frm) {
		refresh_filter_options(frm).then(() => fill_rows(frm));
	},
	filter_departments(frm) {
		fill_rows(frm);
	},
	load_employees(frm) {
		fill_rows(frm);
	},
});

// The filters are multi-select. Designation lists only the sheet's designations; Department lists only
// departments that exist among the employees matching the other filters.
let FILTER_OPTIONS = { designations: [], departments: [] };

function picked(frm, field, key) {
	return (frm.doc[field] || []).map((r) => r[key]).filter(Boolean);
}

function set_filter_queries(frm) {
	const only = (names) => ({ filters: { name: ["in", names.length ? names : ["-"]] } });
	const designations = () => only(FILTER_OPTIONS.designations);
	const departments = () => only(FILTER_OPTIONS.departments);
	// never let a failure here stop the form from drawing
	try {
		frm.set_query("filter_designations", designations);
		frm.set_query("filter_departments", departments);
	} catch (e) {
		console.error(e);
	}
}

function refresh_filter_options(frm) {
	if (frm.doc.docstatus !== 0) {
		return Promise.resolve();
	}
	return frappe
		.xcall("performance_management.worker_driver_security_tl.traffic_light.get_filter_options", {
			doctype: frm.doctype,
			designations: picked(frm, "filter_designations", "designation"),
			branches: picked(frm, "filter_branches", "branch"),
		})
		.then((o) => {
			FILTER_OPTIONS = o;
			// drop chosen departments that no longer match the other filters
			const current = frm.doc.filter_departments || [];
			const keep = current.filter((r) => (o.departments || []).includes(r.department));
			if (keep.length !== current.length) {
				frm.clear_table("filter_departments");
				keep.forEach((r) => frm.add_child("filter_departments", { department: r.department }));
				frm.refresh_field("filter_departments");
			}
		})
		.catch(() => {});
}

function load_rules(frm) {
	return frappe
		.xcall("performance_management.worker_driver_security_tl.traffic_light.get_rules", { doctype: frm.doctype })
		.then((r) => (RULES = r))
		.catch(() => RULES);
}

function rating_of(key, value) {
	const rule = RULES[key];
	if (!rule) {
		return null;
	}
	const v = flt(value);
	if (v >= rule.green) return "Green";
	if (v >= rule.yellow) return "Yellow";
	if (v >= rule.red) return "Red";
	return "Grey";
}

function colours(rating) {
	return RATING_STYLE[rating] || ["", ""];
}

function fill_rows(frm) {
	if (frm.doc.docstatus !== 0) {
		return;
	}
	frappe.call({
		method: "performance_management.worker_driver_security_tl.traffic_light.load_employees",
		args: {
			doctype: frm.doctype,
			designations: picked(frm, "filter_designations", "designation"),
			departments: picked(frm, "filter_departments", "department"),
			branches: picked(frm, "filter_branches", "branch"),
		},
		freeze: true,
		callback(r) {
			const old = {};
			(frm.doc.items || []).forEach((row) => (old[row.employee] = row));
			frm.clear_table("items");
			(r.message || []).forEach((emp) => {
				const row = frm.add_child("items", emp);
				const prev = old[emp.employee];
				if (prev) {
					TL.fields.forEach((f) => (row[f.fn] = prev[f.fn]));
					row.total = prev.total;
				}
			});
			frm.refresh_field("items");
			load_rules(frm).then(() => render_sheet(frm));
			if (!(r.message || []).length) {
				frappe.show_alert({
					message: __("No active employees found. Choose the designations in WDS TL Rules."),
					indicator: "orange",
				});
			}
		},
	});
}

function render_sheet(frm) {
	const $w = frm.fields_dict.score_sheet.$wrapper;
	const editable = frm.doc.docstatus === 0;
	const esc = frappe.utils.escape_html;

	let html = '<div style="overflow-x:auto"><table class="table table-bordered" style="min-width:900px"><thead><tr>';
	html += "<th>S.No</th><th>Emp Code</th><th>Emp Name</th><th>Department</th>";
	TL.fields.forEach((f) => {
		html += '<th style="text-align:center">' + esc(f.label) + " (" + f.max + ")</th>";
	});
	html += '<th style="text-align:center">Total Value (100)</th></tr></thead><tbody>';

	(frm.doc.items || []).forEach((row, i) => {
		let stored = {};
		try {
			stored = JSON.parse(row.ratings || "{}");
		} catch (e) {}
		const pick = (key, value, blank) =>
			blank ? null : editable ? rating_of(key, value) : stored[key] || rating_of(key, value);

		html += '<tr data-name="' + row.name + '"><td>' + (i + 1) + "</td>";
		html += "<td>" + esc(row.employee || "") + "</td>";
		html += "<td>" + esc(row.employee_name || "") + "</td>";
		html += "<td>" + esc(row.department || "") + "</td>";
		TL.fields.forEach((f) => {
			const blank = row[f.fn] == null || row[f.fn] === "";
			const val = blank ? "" : row[f.fn];
			const c = colours(pick(f.fn, val, blank));
			const style = c[0] ? "background:" + c[0] + ";color:" + c[1] + ";" : "";
			if (editable) {
				html +=
					'<td><input type="number" class="form-control input-sm tl-input" style="min-width:70px;font-weight:600;' +
					style + '" data-field="' + f.fn + '" min="0" max="' + f.max + '" step="any" value="' + val + '"></td>';
			} else {
				html += '<td style="text-align:center;font-weight:600;' + style + '">' + val + "</td>";
			}
		});
		const tot = flt(row.total, 2);
		const tc = colours(pick("total", tot, false));
		html +=
			'<td class="tl-total-cell" style="text-align:center;font-weight:700;background:' +
			tc[0] + ";color:" + tc[1] + '">' + tot + "</td></tr>";
	});
	html += "</tbody></table></div>";
	$w.html(html);

	$w.find(".tl-input").on("change", function () {
		const $i = $(this);
		const $tr = $i.closest("tr");
		const f = TL.fields.find((x) => x.fn === $i.data("field"));
		let v = flt($i.val());
		if (v < 0 || v > f.max) {
			frappe.show_alert({
				message: __("{0} must be between 0 and {1}", [f.label, f.max]),
				indicator: "red",
			});
			v = Math.min(Math.max(v, 0), f.max);
			$i.val(v);
		}
		if ($i.val() !== "") {
			const c = colours(rating_of(f.fn, v));
			$i.css({ background: c[0], color: c[1] });
		} else {
			$i.css({ background: "", color: "" });
		}
		const cdn = $tr.data("name");
		frappe.model.set_value(TL.child, cdn, f.fn, v);
		let total = 0;
		$tr.find(".tl-input").each(function () {
			total += flt($(this).val());
		});
		total = flt(total, 2);
		frappe.model.set_value(TL.child, cdn, "total", total);
		const tc = colours(rating_of("total", total));
		$tr.find(".tl-total-cell").text(total).css({ background: tc[0], color: tc[1] });
	});
}
