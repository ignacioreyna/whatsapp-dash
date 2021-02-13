import os
from datetime import datetime, timedelta
from apscheduler.schedulers.blocking import BlockingScheduler


sched = BlockingScheduler()


def is_old(age):
    TWO_HOURS = 60 * 60 * 2
    return age > TWO_HOURS


@sched.scheduled_job('interval', hours=1)
def delete_cached_files():
    '''
    This will run just in case dash-component-unload 
    misses to catch some beforeUnload events.
    '''
    CURR_DIR = os.path.dirname(os.path.realpath(__file__))
    CACHE_DIR = os.path.join(CURR_DIR, 'cache')
    
    for _, _, files in os.walk(CACHE_DIR):
        for f in files:
            full_dir = os.path.join(CACHE_DIR, f)
            last_modification = datetime.fromtimestamp(os.path.getmtime(full_dir))
            file_age = (datetime.now() - last_modification).total_seconds()
            if is_old(file_age):
                os.remove(full_dir)


sched.start()
