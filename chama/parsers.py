"""
SMS parsing utilities for M-Pesa and Cytonn confirmation messages.

Supported formats:

M-Pesa send confirmation:
  QGH3K2P1R5 Confirmed. Ksh5,000.00 sent to CYTONN MONEY MARKET FUND on 1/8/25 at 3:45 PM.
  QGH3K2P1R5 Confirmed.Ksh5,000.00 sent to CYTONN MONEY MARKET FUND on 1/8/2025 at 3:45 PM.

M-Pesa App payment (no date/time in message):
  TLH8017IP1 Confirmed. 5,000.00 KSH paid to Cytonn Fund, 775093 for account number 108109011 via M-PESA App.

Cytonn deposit confirmation:
  Your deposit of KES 5,000.00 in Cytonn Money Market Fund was successful.
  Transaction ID: CYTXYZ123. Date: 01-Aug-2025
"""

import re
from datetime import datetime, date
from decimal import Decimal


class ParseError(Exception):
    pass


# ── Regex patterns ───────────────────────────────────────────────────────────

# M-Pesa: "QGH3K2P1R5 Confirmed. Ksh5,000.00 sent to CYTONN ... on 1/8/25 at 3:45 PM."
_MPESA_PATTERN = re.compile(
    r'^([A-Z0-9]{10,12})\s+Confirmed\.?\s*'
    r'Ksh([\d,]+(?:\.\d{1,2})?)\s+sent\s+to\s+CYTONN.*?'
    r'on\s+(\d{1,2}/\d{1,2}/\d{2,4})\s+at\s+(\d{1,2}:\d{2}\s*[AP]M)',
    re.IGNORECASE | re.DOTALL,
)

# Cytonn: "Your deposit of KES 5,000.00 ... Transaction ID: XYZ123. Date: 01-Aug-2025"
_CYTONN_PATTERN = re.compile(
    r'deposit\s+of\s+(?:KES|Ksh)\s*([\d,]+(?:\.\d{1,2})?)'
    r'.*?(?:Transaction\s+ID|Ref(?:erence)?(?:\s+No\.?)?)\s*[:\-]\s*([A-Z0-9]+)'
    r'.*?Date\s*[:\-]\s*(\d{1,2}[-/]\w{3}[-/]\d{2,4})',
    re.IGNORECASE | re.DOTALL,
)

# M-Pesa App: "TLH8017IP1 Confirmed. 5,000.00 KSH paid to Cytonn Fund, 775093 for account number ... via M-PESA App."
# No date/time is present in this message format; we fall back to today at midnight.
_MPESA_APP_PATTERN = re.compile(
    r'^([A-Z0-9]{8,12})\s+Confirmed\.?\s*'
    r'([\d,]+(?:\.\d{1,2})?)\s+KSH\s+paid\s+to\s+Cytonn',
    re.IGNORECASE,
)

# Alternative Cytonn format where date comes before code
_CYTONN_ALT_PATTERN = re.compile(
    r'deposit\s+of\s+(?:KES|Ksh)\s*([\d,]+(?:\.\d{1,2})?)'
    r'.*?Date\s*[:\-]\s*(\d{1,2}[-/]\w{3}[-/]\d{2,4})'
    r'.*?(?:Transaction\s+ID|Ref(?:erence)?(?:\s+No\.?)?)\s*[:\-]\s*([A-Z0-9]+)',
    re.IGNORECASE | re.DOTALL,
)


def _parse_amount(raw: str) -> Decimal:
    """Convert '5,000.00' → Decimal('5000.00')."""
    return Decimal(raw.replace(',', ''))


def _prev_month(txn_dt: datetime) -> date:
    """
    Return the first day of the month BEFORE the transaction date.
    e.g. transaction on 3 Feb 2026 → contribution month is Jan 2026.
    """
    if txn_dt.month == 1:
        return date(txn_dt.year - 1, 12, 1)
    return date(txn_dt.year, txn_dt.month - 1, 1)


def _parse_mpesa_date(date_str: str, time_str: str) -> datetime:
    """
    Parse M-Pesa date like '1/8/25 at 3:45 PM' or '1/8/2025 at 3:45 PM'.
    Returns naive datetime (local time implied).
    """
    date_str = date_str.strip()
    time_str = time_str.strip().replace(' ', '')
    parts = date_str.split('/')
    if len(parts) != 3:
        raise ParseError(f'Cannot parse M-Pesa date: {date_str!r}')
    day, month, year = parts
    year = int(year)
    if year < 100:
        year += 2000
    fmt = '%I:%M%p'
    try:
        t = datetime.strptime(time_str, fmt)
    except ValueError:
        raise ParseError(f'Cannot parse M-Pesa time: {time_str!r}')
    return datetime(year, int(month), int(day), t.hour, t.minute)


def _parse_cytonn_date(date_str: str) -> datetime:
    """
    Parse Cytonn date like '01-Aug-2025' or '01/Aug/2025'.
    Returns datetime at midnight.
    """
    date_str = date_str.strip().replace('/', '-')
    for fmt in ('%d-%b-%Y', '%d-%b-%y'):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ParseError(f'Cannot parse Cytonn date: {date_str!r}')


def parse_sms_text(sms: str) -> dict:
    """
    Parse an M-Pesa or Cytonn SMS string.

    Returns:
        {
            'code': str,
            'amount': str (decimal string),
            'transaction_date': str (ISO datetime),
            'contribution_month': str (YYYY-MM-01),
            'source': 'mpesa' | 'cytonn',
        }

    Raises ParseError if no pattern matches.
    """
    sms = sms.strip()

    # Try M-Pesa first
    m = _MPESA_PATTERN.search(sms)
    if m:
        code, raw_amount, date_str, time_str = m.groups()
        amount = _parse_amount(raw_amount)
        txn_dt = _parse_mpesa_date(date_str, time_str)
        month_start = _prev_month(txn_dt)
        return {
            'code': code.upper(),
            'amount': str(amount),
            'transaction_date': txn_dt.isoformat(),
            'contribution_month': month_start.isoformat(),
            'source': 'mpesa',
        }

    # Try M-Pesa App format (no date in message – use today)
    m = _MPESA_APP_PATTERN.search(sms)
    if m:
        code, raw_amount = m.groups()
        amount = _parse_amount(raw_amount)
        txn_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = _prev_month(txn_dt)
        return {
            'code': code.upper(),
            'amount': str(amount),
            'transaction_date': txn_dt.isoformat(),
            'contribution_month': month_start.isoformat(),
            'source': 'mpesa',
        }

    # Try Cytonn standard pattern
    m = _CYTONN_PATTERN.search(sms)
    if m:
        raw_amount, code, date_str = m.groups()
        amount = _parse_amount(raw_amount)
        txn_dt = _parse_cytonn_date(date_str)
        month_start = _prev_month(txn_dt)
        return {
            'code': code.upper(),
            'amount': str(amount),
            'transaction_date': txn_dt.isoformat(),
            'contribution_month': month_start.isoformat(),
            'source': 'cytonn',
        }

    # Try Cytonn alt pattern
    m = _CYTONN_ALT_PATTERN.search(sms)
    if m:
        raw_amount, date_str, code = m.groups()
        amount = _parse_amount(raw_amount)
        txn_dt = _parse_cytonn_date(date_str)
        month_start = _prev_month(txn_dt)
        return {
            'code': code.upper(),
            'amount': str(amount),
            'transaction_date': txn_dt.isoformat(),
            'contribution_month': month_start.isoformat(),
            'source': 'cytonn',
        }

    raise ParseError(
        'Could not parse SMS. Expected an M-Pesa send confirmation or '
        'Cytonn deposit confirmation message.'
    )
