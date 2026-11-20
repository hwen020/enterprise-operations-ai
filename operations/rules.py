"""Local rule agents; no model API and no outbound transport."""
import hashlib
import json
from decimal import Decimal,InvalidOperation,ROUND_HALF_UP
SEGMENTS = {"Workspace":"Business","Industrial":"Industrial","Outdoor":"Retail"}
class Problem(ValueError):
    def __init__(self,message,status=422):
        super().__init__(message)
        self.status=status
def text(value,label,limit=120):
    if not isinstance(value,str) or not value.strip() or len(value.strip())>limit:
        raise Problem(label+" is required (max "+str(limit)+" characters)")
    return value.strip()
def decimal(value,label,positive=False):
    if isinstance(value,(float,bool)): raise Problem(label+" must be a decimal string")
    try:
        n=Decimal(str(value))
        if not n.is_finite() or n<0 or n>Decimal("1000000") or (positive and n<=0) or n.as_tuple().exponent < -4: raise InvalidOperation()
        return n
    except (InvalidOperation,ValueError,TypeError): raise Problem(label+" must be nonnegative, up to four decimal places")
def amount(n): return format(n.quantize(Decimal("0.01"),rounding=ROUND_HALF_UP),".2f")
def calculate(quantity,unit_price):
    q,p=decimal(quantity,"Quantity",True),decimal(unit_price,"Unit price")
    if q*p>Decimal("1000000000"): raise Problem("Quotation exceeds demo limits")
    net=Decimal(amount(q*p));tax=Decimal(amount(net*Decimal("0.08")))
    return dict(quantity=format(q,"f"),unit_price=format(p,"f"),subtotal=amount(net),tax=amount(tax),total=amount(net+tax))
def digest(value): return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def message(names,segment):
    return ("A fresh selection for "+segment.lower(),
        "Hello,\n\nExplore our fictional selection: "+", ".join(names[:4])+
        ". This draft was composed by a local rule agent, without model inference.\n\nWould a product overview be useful?\n\n"+
        "Enterprise Operations AI demo team\nSIMULATION ONLY. No email will be sent. Demo opt-out: reply STOP (simulated).")
def outcome(email):
    n=int(hashlib.sha256(email.encode()).hexdigest()[:8],16)
    opened=int(n%5!=0)
    return (1,opened,int(bool(opened) and n%3==0))
