import schedule
import time
import datetime
import os
import sys

def job():
    sys.stdout.flush()
    print "Start!"
    os.system("python scraper.py")
    print "Job done at", datetime.datetime.now()

schedule.every(15).minutes.do(job)

while True:
    schedule.run_pending()
    time.sleep(1)
