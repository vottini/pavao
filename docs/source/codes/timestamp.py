
from datetime import datetime, timezone

def utc_milliseconds():
  now = datetime.now(timezone.utc)
  return now.isoformat(timespec='milliseconds')
