# warehouse/utils.py
from .models import LabelVersion
import hashlib

def verify_label(label_id, scanned_fnsku, scanned_upc):
    
    try:
        label = LabelVersion.objects.get(id=label_id)
    except LabelVersion.DoesNotExist:
        return False,

    
    scanned_raw = f"{scanned_fnsku}|{scanned_upc}"
    scanned_checksum = hashlib.sha256(scanned_raw.encode('utf-8')).hexdigest()

    if scanned_checksum == label.checksum:
        return True,
    else:
        return False, 