import requests
from apscheduler.schedulers.blocking import BlockingScheduler


sched = BlockingScheduler()


@sched.scheduled_job('interval', minutes=5)
def keep_alive():
    requests.get('https://whatstat.herokuapp.com/')



sched.start()