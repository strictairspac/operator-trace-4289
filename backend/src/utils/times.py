from datetime import datetime
def canonical(ts):
 try:return datetime.fromisoformat(str(ts).strip()).isoformat()
 except (ValueError,TypeError):return None
def ts_key(ts):
 c=canonical(ts)
 return c if c is not None else str(ts)
