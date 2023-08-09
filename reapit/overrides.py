# Copyright (c) 2022, Wahni Green Technologies and contributors
# For license information, please see license.txt

from erpnext.stock.doctype.serial_no.serial_no import get_serial_nos
from erpnext.stock.stock_ledger import get_stock_ledger_entries
from erpnext.stock.doctype.serial_no.serial_no import SerialNo
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry
from erpnext.stock.utils import get_incoming_rate
from frappe.utils import flt
import copy, frappe
from frappe.utils import cint

class CustomStockEntry(StockEntry):
	def validate(self):
		super().validate()
		rf_cost = 0
		if self.purpose == 'Repack':
			for row in self.items:
				if (row.item_code not in ['2003', '2001'] and not row.t_warehouse):
					rf_cost += row.basic_amount
			self.refurbishment_cost = rf_cost

	def set_rate_for_outgoing_items(self, reset_outgoing_rate=True, raise_error_if_no_rate=True):
		outgoing_items_cost = 0.0
		for d in self.get("items"):
			if d.s_warehouse:
				if not d.set_basic_rate_manually and reset_outgoing_rate:
					args = self.get_args_for_incoming_rate(d)
					rate = get_incoming_rate(args, raise_error_if_no_rate)
					if rate > 0:
						d.basic_rate = rate

				d.basic_amount = flt(flt(d.transfer_qty) * flt(d.basic_rate), d.precision("basic_amount"))
				if not d.t_warehouse:
					outgoing_items_cost += flt(d.basic_amount)

		return outgoing_items_cost

class CustomSerialNo(SerialNo):
	def get_stock_ledger_entries(self, serial_no=None):
		sle_dict = {}
		if not serial_no:
			serial_no = self.name
		queryy = frappe.db.sql(
			"""
			SELECT voucher_type, voucher_no,
				posting_date, posting_time, incoming_rate, actual_qty, serial_no
			FROM
				`tabStock Ledger Entry`
			WHERE
				item_code=%s AND company = %s
				AND is_cancelled = 0
				AND (serial_no = %s
					OR serial_no like %s
					OR serial_no like %s
					OR serial_no like %s
				)
				AND warehouse=%s
			ORDER BY
				posting_date desc, posting_time desc, creation desc""",
			(
				self.item_code,
				self.company,
				serial_no,
				serial_no + "\n%",
				"%\n" + serial_no,
				"%\n" + serial_no + "\n%",
				self.warehouse
			),
			as_dict=1,
		)
		for sle in queryy:
			if serial_no.upper() in get_serial_nos(sle.serial_no):
				if cint(sle.actual_qty) > 0:
					sle_dict.setdefault("incoming", []).append(sle)
				else:
					sle_dict.setdefault("outgoing", []).append(sle)

		return sle_dict


def validate_serial_no(sle):
	print('Validate Overided')
	for sn in get_serial_nos(sle.serial_no):
		args = copy.deepcopy(sle)
		args.serial_no = sn
		args.warehouse = sle.warehouse
		queryy = get_stock_ledger_entries(args, ">")
		vouchers = []
		for row in queryy:
			voucher_type = frappe.bold(row.voucher_type)
			voucher_no = frappe.bold(get_link_to_form(row.voucher_type, row.voucher_no))
			vouchers.append(f"{voucher_type} {voucher_no}")

		if vouchers:
			serial_no = frappe.bold(sn)
			msg = (
				f"""The serial no {serial_no} has been used in the future transactions so you need to cancel them first.
				The list of the transactions are as below."""
				+ "<br><br><ul><li>"
			)

			msg += "</li><li>".join(vouchers)
			msg += "</li></ul>"

			title = "Cannot Submit" if not sle.get("is_cancelled") else "Cannot Cancel"
			frappe.throw(_(msg), title=_(title), exc=SerialNoExistsInFutureTransaction)

