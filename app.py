from flask import Flask, render_template, request, jsonify
import json

app = Flask(__name__)

@app.route("/")
def home():
  return ("JHC IBM Test Page workflows")

if __name__ == "__main__":
  app.run(host="0.0.0.0", port=8080)
