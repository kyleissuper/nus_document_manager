import json
import os
import datetime
from flask import Flask, render_template, redirect, url_for, request, session, send_from_directory
from gevent.wsgi import WSGIServer
from pymongo import MongoClient
from settings import *

app = Flask(__name__)
app.secret_key = os.urandom(24).encode("hex")

class Document:
    all_documents = []
    def __init__(self, filename, module_code, module_title, timestamp):
        self.filename = filename
        self.module_code = module_code
        self.module_title = module_title
        self.timestamp = timestamp
        self.statuses = {}
        Document.all_documents.append(self)
    def add_status(self, status, username):
        if status not in self.statuses:
            self.statuses[status] = []
        self.statuses[status].append(username)

def add_document(new_doc, username):
    found = False
    for old_doc in Document.all_documents:
        if old_doc.filename == new_doc["filename"]:
            old_doc.add_status(new_doc["status"], username)
            found = True
            break
    if found == False:
        added_doc = Document(
                new_doc["filename"],
                new_doc["code"],
                new_doc["title"],
                new_doc["timestamp_local"]
                )
        added_doc.add_status(new_doc["status"], username)

@app.route("/admin", methods=["GET", "POST"])
def admin():
    error = None
    if "username" not in session:
        return redirect(url_for("login"))
    elif session["admin"] != True:
        return redirect(url_for("home"))
    elif session["admin"] == True:
        if request.method == "POST":
            if request.form["form_id"] == "new_user":
                with MongoClient() as client:
                    if client[DB][COLL].count({
                        "username": request.form["username"]
                        }) > 0:
                        error = "An account already exists with this username."
                    elif client[DB][COLL].count({
                        "username": request.form["admin_id"],
                        "admin": True
                        }) == 0 and request.form["admin_id"] != request.form["username"]:
                        error = "No administrator's account exists with that username."
                    else:
                        if request.form.getlist("admin"):
                            admin = True
                        else:
                            admin = False
                        client[DB][COLL].insert({
                            "username": request.form["username"].lower(),
                            "first_name": request.form["first_name"],
                            "password": request.form["password"],
                            "password_status": request.form["password_status"],
                            "admin": admin,
                            "admin_id": request.form["admin_id"],
                            "files": []
                            })
            elif request.form["form_id"] == "delete_user":
                with MongoClient() as client:
                    if client[DB][COLL].count({
                        "admin_id": request.form["username"]}) > 0:
                        error = "This user is currently administrator to other existing accounts. Cannot delete."
                    else:
                        client[DB][COLL].remove({
                            "username": request.form["username"]})
            elif request.form["form_id"] == "admin_form":
                with MongoClient() as client:
                    for doc in request.form.getlist("selected_docs"):
                        doc = json.loads(doc)
                        client[DB][COLL].update({
                            "files.filename": doc["filename"],
                            "username": doc["user_id"]
                            }, {
                            "$set": {
                                "files.$.status": request.form["change_status"]
                                }
                            },
                            multi = True)
        with MongoClient() as client:
            Document.all_documents = []
            query = client[DB][COLL].find({"admin_id": session["username"]})
            users = {}
            for user in query:
                users[user["username"]] = user
                for f in user["files"]:
                    add_document(f, user["username"])
        return render_template("admin.html", files=sorted(Document.all_documents, key=lambda k: k.timestamp, reverse=True), users=users, error=error)

@app.route("/", methods=["GET", "POST"])
def home():
    if "username" in session:
        if request.method == "POST":
            with MongoClient() as client:
                query = client[DB][COLL].update({
                    "username": session["username"],
                    "files.filename": request.form["filename"]
                    }, {
                    "$set": {
                        "files.$.status": "requested"
                        }
                    })
        with MongoClient() as client:
            query = client[DB][COLL].find({"username": session["username"]})
            user = [q for q in query][0]
            admin = client[DB][COLL].find({"username": user["admin_id"] })
            admin_name = [a for a in admin][0]["first_name"]
        return render_template("home.html", user=user, admin_name=admin_name,
                files=sorted(user["files"], key=lambda k: k["timestamp"], reverse=True))
    else:
        return redirect(url_for("login"))

@app.route("/download/<filename>")
def download(filename):
    #if "username" not in session:
    #    return redirect(url_for("login"))
    with MongoClient() as client:
        #query = client[DB][COLL].find({"username": session["username"]})
        #user = [q for q in query][0]
        #filenames = [f["filename"] for f in user["files"]]
        files = [f for f in client[DB][COLL].find({"files.filename": filename})]
        #if filename in filenames:
        if len(files) > 0:
            return send_from_directory(FILE_DIR, filename)
        else:
            return "File not found"

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    error_message = "Are you sure you got your login right?"
    if "username" in session:
        return redirect(url_for("home"))
    elif request.method == "POST":
        with MongoClient() as client:
            query = client[DB][COLL].find({"username": request.form["username"].lower()})
            users = [q for q in query]
            if len(users) == 0:
                error = error_message
            elif users[0]["password"] != request.form["password"]:
                error = error_message
            else:
                session["username"] = users[0]["username"].lower()
                session["admin"] = users[0]["admin"]
                session.permanent = True
                return redirect(url_for("home"))
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.pop("username", None)
    session.pop("admin", None)
    return redirect(url_for("login"))

@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html")

if ENV == "dev":
    port = 8080
else:
    port = 5000

if __name__ == "__main__":
    #app.run(host="0.0.0.0", debug=False)
    http_server = WSGIServer(("", 5000), app)
    http_server.serve_forever()
