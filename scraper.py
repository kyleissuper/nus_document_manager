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

def clean_name(name):
    name = name.replace("/", "-")
    return name

with MongoClient() as client:
    local_tz = pytz.timezone("Asia/Singapore")
    coll = client[DB][COLL]
    for user in coll.find():
        module_codes = set()
        s = requests.Session()
        # Get course files
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
        if len(links) == 0:
            coll.update({ "username": user["username"] }, { "$set": {
                "password_status": "bad"
                }})
            continue
        elif user["password_status"] != "ok":
            coll.update({ "username": user["username"] }, { "$set": {
                "password_status": "ok"
                }})
        for link in links:
            course_ids.add(link["href"].split("CourseID=")[1])
            module_codes.add(link.string)
        for course_id in course_ids:
            r = s.get("https://ivle.nus.edu.sg/v1/File/Student/download_all.aspx?CourseID="+course_id)
            soup = BeautifulSoup(r.text, "html.parser")
            if len(soup.find_all(text="No folder found for this Module.")) == 1:
                continue # No module found
            module_code = soup.title.string.split(" > ")[1]
            module_name = soup.find("a", class_="accordion-toggle").string
            tree = soup.find("div", class_="TreeView")
            links = tree.find_all(href=re.compile("/workbin/file_download"))
            for link in links:
                url = link["href"]
                filename = link.string
                datestamp = "".join(link.parent.find("font", class_="iItem-txt").string.split(",")[2][1:-1].split()[0].split("'"))
                new_name = " - ".join([module_code, clean_name(filename.split(".")[0]), datestamp + "."+filename.split(".")[1]])
                # Does it exist on this machine yet?
                if coll.count({"files.filename": new_name}) == 0:
                    with open("{}/{}".format("files", new_name), "wb") as handle:
                        r = s.get("{}{}".format("https://ivle.nus.edu.sg", url), stream=True)
                        if not r.ok:
                            print "Oh larddd"
                        for block in r.iter_content(1024):
                            handle.write(block)
                # Does this user have this yet?
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
        # Get exam files
        EXAM_DOMAIN = "https://libbrs.nus.edu.sg"
        for module_code in module_codes:
            if (module_code is None) or ("/" in module_code):
                continue
            r = s.post(EXAM_DOMAIN + "/infogate/loginAction.do?execution=login", {
                "userid": user["username"],
                "password": user["password"],
                "domain": "NUSSTU",
                "key": "blankid+RESULT+EXAM+" + module_code
                })
            if "Loading page... please wait" not in r.text:
                continue
            r = s.post(EXAM_DOMAIN + "/infogate/searchAction.do?execution=ResultList", {
                "database": "EXAM",
                "searchstring": module_code,
                "d": ""
                })
            soup = BeautifulSoup(r.text, "html.parser")
            data = []
            form = soup.find(attrs={"name": "SearchForm"})
            maxNo = None
            for el in form.find_all("input"):
                attrs = el.attrs
                if "value" not in attrs:
                    value = ""
                else:
                    value = attrs["value"]
                if "name" in attrs:
                    if attrs["name"] == "maxNo":
                        maxNo = int(value)
                    elif attrs["name"] == "preSelectedId" or \
                            attrs["name"] == "exportids":
                        continue
                    data.append((attrs["name"], value))
            if maxNo == 0 or maxNo is None:
                continue
            data.append(("preSelectedId", ",".join([str(i) for i in range(1, maxNo + 1)])))
            for i in range(1, maxNo+1):
                data.append(("exportids", str(i)))
            r = s.post(EXAM_DOMAIN + "/infogate/searchAction.do?execution=ViewSelectedResultListLong", data)
            soup = BeautifulSoup(r.text, "html.parser")
            links = soup.find_all("a", string=re.compile("View attached"))
            for link in links:
                url = link["href"]
                filename = clean_name(link.attrs["title"][14:])
                new_name = " - ".join([module_code, "EXAM", filename])
                # Does it exist on this machine yet?
                if coll.count({"files.filename": new_name}) == 0:
                    with open("{}/{}".format("files", new_name), "wb") as handle:
                        r = s.get(EXAM_DOMAIN + "/infogate/" + url, stream=True)
                        if not r.ok:
                            print "Oh larddd"
                        for block in r.iter_content(1024):
                            handle.write(block)
                # Does this user have this yet?
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
                            "title": "EXAM",
                            "status": "new"
                            }} 
                        })
