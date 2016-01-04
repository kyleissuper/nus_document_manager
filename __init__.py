from flask import Flask
app = Flask(__name__)

@app.route("/")
def login():
    return "Hello world"

@app.errorhandler(404)
def page_not_found(error):
    return "Page not found"

if __name__ == "__main__":
    app.run(host="0.0.0.0")
