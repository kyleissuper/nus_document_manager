import schedule
import time
import os
import sys

def job():
    #os.system("source /home/kyle/print_app/venv/bin/activate")
    sys.stdout.flush()
    print "Start!"
    os.system("python scraper.py")
    print "Job done at", time.time()

schedule.every(15).minutes.do(job)

while True:
    schedule.run_pending()
    time.sleep(1)
