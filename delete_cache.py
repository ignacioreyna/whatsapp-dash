import sys
import os
from datetime import datetime, timedelta


CURR_DIR = '/'.join(sys.argv[0].split('/')[:-1])
CACHE_DIR = os.path.join(CURR_DIR, 'cache')

def is_old(age):
    TWO_HOURS = 60 * 60 * 2
    print(TWO_HOURS)
    return age > TWO_HOURS


for _, _, files in os.walk(CACHE_DIR):
    for f in files:
        full_dir = os.path.join(CACHE_DIR, f)
        last_modification = datetime.fromtimestamp(os.path.getmtime(full_dir))
        file_age = (datetime.now() - last_modification).total_seconds()
        if is_old(file_age):
            os.remove(full_dir)
