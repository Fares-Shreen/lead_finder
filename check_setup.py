"""
Run this before `streamlit run app.py` to check whether your SerpApi key
is actually visible in THIS terminal session:

    python check_setup.py

If it says "NOT SET", that's why Google and LinkedIn always return 0 —
the app never even makes a request, it just gives up instantly.
Environment variables set with `set VAR=value` on Windows only apply to
the exact terminal window you typed it into, for as long as that window
stays open. Closing the terminal, opening a new one, or restarting your
PC clears it.
"""
from config import SERPAPI_KEY

def _status(name, value):
    if value:
        masked = value[:4] + "..." + value[-4:] if len(value) > 8 else "set"
        print(f"  {name}: SET  ({masked})")
    else:
        print(f"  {name}: NOT SET  <-- this is why Google/LinkedIn return 0")

print("Checking SerpApi credentials in this terminal session...")
_status("SERPAPI_KEY", SERPAPI_KEY)

if SERPAPI_KEY:
    print("\nSet. If Google/LinkedIn still return 0, run:")
    print("  python -c \"from sources.serpapi_search import search_google_companies as s; print(s('software','Alexandria, Egypt', 5))\"")
    print("...to see the raw response/error.")
else:
    print("\nFix: get a free key at https://serpapi.com/users/sign_up")
    print("Then, in THIS SAME terminal window, before running streamlit, run:")
    print('  set SERPAPI_KEY=paste-your-key-here')
    print('  python -m streamlit run app.py')
