# -*- coding: utf-8 -*-
from __future__ import unicode_literals

__version__ = '0.0.1'

import erpnext.stock.stock_ledger as _standard
import reapit.overrides as _custom

_standard.validate_serial_no = _custom.validate_serial_no