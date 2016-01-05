import os
import time
import datetime
import random
import subprocess
import re
import pytz
from pymongo import MongoClient
import requests
from bs4 import BeautifulSoup
from settings import *

with MongoClient() as client:
    local_tz = pytz.timezone("Asia/Singapore")
    coll = client[DB][COLL]
    for user in coll.find():
        s = requests.Session()
        r = s.post("https://ivle.nus.edu.sg/", {
            "ctl00$ctl00$ContentPlaceHolder1$userid": user["username"],
            "ctl00$ctl00$ContentPlaceHolder1$password": user["password"],
            "__VIEWSTATEGENERATOR": "CA0B0334",
            "__SCROLLPOSITIONX": random.randint(0,5),
            "__SCROLLPOSITIONY": random.randint(340, 350),
            "__EVENTTARGET": "ctl00$ctl00$ContentPlaceHolder1$btnSignIn"
            })
        soup = BeautifulSoup(r.text, "html.parser")
        links = soup.find_all(href=re.compile("\?CourseID="))
        course_ids = set()
        for link in links:
            course_ids.add(link["href"].split("CourseID=")[1])
        for course_id in course_ids:
            r = s.get("https://ivle.nus.edu.sg/v1/File/Student/download_all.aspx?CourseID="+course_id)
            soup = BeautifulSoup(r.text, "html.parser")
            if len(soup.find_all(text="No folder found for this Module.")) == 1:
                continue # Not module found
            module_code = soup.title.string.split(" > ")[1]
            module_name = soup.find("a", class_="accordion-toggle").string
            tree = soup.find("div", class_="TreeView")
            links = tree.find_all(href=re.compile("/workbin/file_download"))
            for link in links:
                url = link["href"]
                filename = link.string
                datestamp = "".join(link.parent.find("font", class_="iItem-txt").string.split(",")[2][1:-1].split()[0].split("'"))
                new_name = " - ".join([module_code, filename.split(".")[0], datestamp + "."+filename.split(".")[1]])
                # Does it exist on this machine yet?
                if coll.count({"files.filename": new_name}) == 0:
                    #os.system("wget -O '{0}/{1}' '{2}{3}'".format(
                    #    "files",
                    #    new_name,
                    #    "https://ivle.nus.edu.sg",
                    #    url
                    #    ))
                    with open("{}/{}".format("files", new_name), "wb") as handle:
                        r = s.get("{}{}".format("https://ivle.nus.edu.sg", url), stream=True)
                        if not r.ok:
                            print "Oh larddd"
                        for block in r.iter_content(1024):
                            handle.write(block)
                # Does this user have this yet?
                # timestamp = float(subprocess.check_output("stat -c %Y '{}/{}'".format("files", new_name), shell=True))
                timestamp = os.path.getmtime("{}/{}".format("files", new_name))
                ts = pytz.utc.localize(datetime.datetime.fromtimestamp(timestamp),
                    is_dst=None).astimezone(local_tz)
                if coll.count({ "username": user["username"],
                    "files.filename": new_name }) == 0:
                    coll.update({
                        "username": user["username"]
                        }, {
                        "$push": {"files":{
                            "timestamp": ts,
                            "timestamp_local": ts.strftime("%Y-%m-%d %H:%M"),
                            "filename": new_name,
                            "code": module_code,
                            "title": module_name,
                            "status": "new"
                            }} 
                        })
