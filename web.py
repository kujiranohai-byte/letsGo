from flask import Flask, render_template_string
import sqlite3

app = Flask(__name__)

HTML = """
<h2>Reports</h2>
<table border=1>
<tr><th>ID</th><th>Guild</th><th>User</th><th>Content</th><th>Status</th></tr>
{% for r in rows %}
<tr>
<td>{{r[0]}}</td>
<td>{{r[1]}}</td>
<td>{{r[2]}}</td>
<td>{{r[3]}}</td>
<td>{{r[5]}}</td>
</tr>
{% endfor %}
</table>
"""

@app.route("/")
def index():

    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()

    cur.execute("SELECT * FROM reports")
    rows = cur.fetchall()

    conn.close()

    return render_template_string(HTML, rows=rows)

app.run(port=5000)