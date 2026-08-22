"""
Run this to verify the Podio duplicate-check actually works before
trusting it in a real search:

    python check_podio.py "Some Real Company Already In Podio"
    python check_podio.py "Some Made Up Company That Does Not Exist Xyz123"

The first should print FOUND, the second NOT FOUND. If either is wrong,
send me everything this prints (including the raw JSON) and I'll fix the
parsing logic in podio_check.py to match what Podio actually returns.
"""
import sys
import json

from podio_check import raw_podio_response, exists_in_podio

if len(sys.argv) < 2:
    print('Usage: python check_podio.py "Company Name"')
    raise SystemExit

name = " ".join(sys.argv[1:])
print(f"Querying Podio for: {name!r}\n")

raw = raw_podio_response(name)
if raw is None:
    print("FAILED: got no usable response from Podio at all (network error,")
    print("non-200 status, or non-JSON response). This means Podio checks will")
    print("silently default to 'not found' in real searches right now.")
    raise SystemExit

print("Raw JSON response:")
print(json.dumps(raw, indent=2)[:3000])
print()

found = exists_in_podio(name)
print(f"PARSED RESULT: {'FOUND' if found else 'NOT FOUND'}")
