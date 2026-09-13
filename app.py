from flask import Flask, request, redirect, render_template_string, jsonify, session
import os
import time

app = Flask(__name__)

# ================= SECURITY =================
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret")

USERNAME = os.environ.get("ADMIN_USERNAME", "Jahid")
PASSWORD = os.environ.get("ADMIN_PASSWORD", "Jahid123")

FILE = "keys.txt"
TIMEOUT = 60


# ================= LOAD KEYS =================
def load_keys():
    if not os.path.exists(FILE):
        return []

    with open(FILE, "r", encoding="utf-8") as f:
        return [
            line.strip()
            for line in f.readlines()
            if "|" in line
        ]


def save_keys(keys):
    with open(FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(keys))


# ================= LOGIN =================
@app.route("/login", methods=["GET", "POST"])
def login():

    error = ""

    if request.method == "POST":

        user = request.form.get("username", "")
        pw = request.form.get("password", "")

        if user == USERNAME and pw == PASSWORD:
            session["logged_in"] = True
            return redirect("/dashboard")

        error = "Wrong Login!"

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<title>Login</title>

<style>
body{
    background:#0f172a;
    color:white;
    font-family:Arial;
    display:flex;
    justify-content:center;
    align-items:center;
    height:100vh;
    margin:0;
}

.box{
    background:#1e293b;
    padding:40px;
    border-radius:15px;
    text-align:center;
    width:350px;
    box-shadow:0 0 30px rgba(0,0,0,.5);
}

input{
    width:100%;
    padding:12px;
    margin:10px 0;
    border:none;
    border-radius:8px;
    box-sizing:border-box;
}

button{
    width:100%;
    padding:12px;
    background:#22c55e;
    border:none;
    color:white;
    border-radius:8px;
    cursor:pointer;
}

.error{
    color:#ff4444;
}
</style>
</head>

<body>

<div class="box">

<h2>🔐 Admin Login</h2>

<form method="POST">

<input
type="text"
name="username"
placeholder="Username"
required
>

<input
type="password"
name="password"
placeholder="Password"
required
>

<button type="submit">
Login
</button>

</form>

<p class="error">{{error}}</p>

</div>

</body>
</html>
""", error=error)


# ================= LOGOUT =================
@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# ================= ROOT =================
@app.route("/")
def home():

    return redirect("/dashboard")


# ================= ADD KEY =================
@app.route("/add", methods=["POST"])
def add():

    if not session.get("logged_in"):
        return redirect("/login")

    key = request.form.get("new_key", "").strip().upper()

    if not key:
        return redirect("/dashboard")

    keys = load_keys()

    # Duplicate check
    for line in keys:

        if line.split("|")[0] == key:
            return redirect("/dashboard")

    # KEY FORMAT
    keys.append(f"{key}|active||0")

    save_keys(keys)

    return redirect("/dashboard")


# ================= TOGGLE =================
@app.route("/toggle")
def toggle():

    if not session.get("logged_in"):
        return redirect("/login")

    key = request.args.get("toggle", "")
    set_status = request.args.get("set", "")

    if set_status not in ["active", "inactive"]:
        return redirect("/dashboard")

    keys = load_keys()
    new_keys = []

    for line in keys:

        parts = line.split("|")

        if len(parts) < 2:
            continue

        k = parts[0]
        s = parts[1]

        saved_device = parts[2] if len(parts) >= 3 else ""
        last_time = parts[3] if len(parts) >= 4 else "0"

        if k == key:

            new_keys.append(
                f"{k}|{set_status}|{saved_device}|{last_time}"
            )

        else:

            new_keys.append(line)

    save_keys(new_keys)

    return redirect("/dashboard")


# ================= DELETE =================
@app.route("/delete")
def delete():

    if not session.get("logged_in"):
        return redirect("/login")

    key = request.args.get("delete", "")

    keys = load_keys()

    keys = [
        line
        for line in keys
        if "|" in line and line.split("|")[0] != key
    ]

    save_keys(keys)

    return redirect("/dashboard")


# ================= CHECK API =================
@app.route("/check/<key>")
def check_key(key):

    key = key.strip().upper()

    device = request.args.get("device")

    # Old version protection
    if not device:

        return jsonify({
            "key": key,
            "status": "update_required",
            "valid": False
        })

    keys = load_keys()

    current_time = int(time.time())

    updated_keys = []
    found = False

    for line in keys:

        parts = line.split("|")

        if len(parts) < 2:
            continue

        k = parts[0]
        status = parts[1]

        saved_device = parts[2] if len(parts) >= 3 else ""

        try:
            last_time = int(parts[3])
        except:
            last_time = 0

        if k == key:

            found = True

            # Inactive
            if status != "active":

                return jsonify({
                    "key": k,
                    "status": status,
                    "valid": False
                })

            # First activation
            if saved_device == "":

                updated_keys.append(
                    f"{k}|{status}|{device}|{current_time}"
                )

            # Same device
            elif saved_device == device:

                updated_keys.append(
                    f"{k}|{status}|{device}|{current_time}"
                )

            # Another device currently running
            elif current_time - last_time < TIMEOUT:

                return jsonify({
                    "key": k,
                    "status": "already_running_on_other_device",
                    "valid": False
                })

            # Previous device timed out
            else:

                updated_keys.append(
                    f"{k}|{status}|{device}|{current_time}"
                )

        else:

            updated_keys.append(line)

    if found:

        save_keys(updated_keys)

        return jsonify({
            "key": key,
            "status": "active",
            "valid": True
        })

    return jsonify({
        "key": key,
        "status": "not_found",
        "valid": False
    })


# ================= HEARTBEAT =================
@app.route("/heartbeat")
@app.route("/ping")
def heartbeat():

    device = request.args.get("device")
    key = request.args.get("key", "").strip().upper()

    # Server alive check
    if not device or not key:

        return jsonify({
            "status": "running"
        })

    keys = load_keys()

    new_keys = []

    current_time = int(time.time())

    for line in keys:

        parts = line.split("|")

        if len(parts) < 2:
            continue

        k = parts[0]
        status = parts[1]

        saved_device = parts[2] if len(parts) >= 3 else ""

        if k == key and saved_device == device:

            new_line = (
                f"{k}|{status}|{device}|{current_time}"
            )

            new_keys.append(new_line)

        else:

            new_keys.append(line)

    save_keys(new_keys)

    return jsonify({
        "status": "ok"
    })


# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():

    if not session.get("logged_in"):
        return redirect("/login")

    keys = load_keys()

    active = 0
    inactive = 0

    parsed = []

    for line in keys:

        parts = line.split("|")

        if len(parts) < 2:
            continue

        k = parts[0]
        s = parts[1]

        parsed.append((k, s))

        if s == "active":
            active += 1
        else:
            inactive += 1

    return render_template_string("""
<!DOCTYPE html>
<html>

<head>

<title>License Dashboard</title>

<style>

body{
    background:#0f172a;
    font-family:Arial;
    color:white;
    padding:30px;
}

.top{
    display:flex;
    justify-content:space-between;
    align-items:center;
    margin-bottom:30px;
}

.grid{
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:25px;
}

.box{
    padding:50px;
    border-radius:20px;
    text-align:center;
    font-size:35px;
    font-weight:bold;
}

.red{
    background:#ef4444;
}

.green{
    background:#22c55e;
}

.cyan{
    grid-column:1/3;
    background:linear-gradient(
        90deg,
        #06b6d4,
        #14b8a6
    );
}

.btn-box{
    padding:30px;
    border-radius:15px;
    font-size:22px;
    font-weight:bold;
    cursor:pointer;
    text-align:center;
}

.yellow{
    background:#84cc16;
}

.blue{
    background:#3b82f6;
}

.popup{
    display:none;
    position:fixed;
    top:0;
    left:0;
    width:100%;
    height:100%;
    background:rgba(0,0,0,.7);
}

.popup-content{
    background:#1e293b;
    margin:5% auto;
    padding:20px;
    width:50%;
    border-radius:15px;
}

.scroll-box{
    max-height:400px;
    overflow-y:auto;
}

.key-row{
    background:#0f172a;
    padding:12px;
    margin:10px 0;
    border-radius:10px;
    display:flex;
    justify-content:space-between;
}

.close{
    float:right;
    color:red;
    cursor:pointer;
    font-size:22px;
}

.logout{
    position:absolute;
    top:20px;
    right:30px;
    color:white;
    text-decoration:none;
}

</style>

</head>

<body>

<a href="/logout" class="logout">
Logout
</a>

<div class="top">

<h1>
🔥 License Dashboard
</h1>

</div>


<div class="grid">

<div class="box red">
{{inactive}}
<br>
Inactive
</div>

<div class="box green">
{{active}}
<br>
Active
</div>


<div
class="btn-box yellow"
onclick="openManage()"
>
Manage Key
</div>


<div
class="btn-box blue"
onclick="openAdd()"
>
Generate Key
</div>


<div class="box cyan">

{{total}}
<br>
All Key

</div>

</div>


<!-- MANAGE -->

<div
id="managePopup"
class="popup"
>

<div class="popup-content">

<span
class="close"
onclick="closeManage()"
>
✖
</span>

<h2>
🔑 Manage Key
</h2>

<div class="scroll-box">

{% for k,s in keys %}

<div class="key-row">

<div>

{{k}} →

<span
style="color:{{'lime' if s=='active' else 'red'}};"
>
{{s}}
</span>

</div>


<div>

<a
href="/toggle?toggle={{k}}&set=inactive"
style="
padding:5px 10px;
background:{{'red' if s=='inactive' else '#333'}};
color:white;
border-radius:5px;
text-decoration:none;
"
>
OFF
</a>


<a
href="/toggle?toggle={{k}}&set=active"
style="
padding:5px 10px;
background:{{'red' if s=='active' else '#333'}};
color:white;
border-radius:5px;
text-decoration:none;
"
>
ON
</a>


<a
href="/delete?delete={{k}}"
style="
color:red;
margin-left:10px;
"
>
Delete
</a>

</div>

</div>

{% endfor %}

</div>

</div>

</div>


<!-- ADD -->

<div
id="addPopup"
class="popup"
>

<div
class="popup-content"
style="width:35%;text-align:center;"
>

<span
class="close"
onclick="closeAdd()"
>
✖
</span>

<h2>
🔑 Add Key
</h2>

<form
action="/add"
method="POST"
>

<input
type="text"
name="new_key"
placeholder="Enter Key"
style="
width:80%;
padding:10px;
border-radius:8px;
border:none;
"
required
>

<br><br>

<button
type="submit"
style="
padding:10px 25px;
background:#16a34a;
border:none;
color:white;
border-radius:8px;
"
>
Add
</button>

</form>

</div>

</div>


<script>

function openManage(){

    document.getElementById(
        "managePopup"
    ).style.display="block";

}

function closeManage(){

    document.getElementById(
        "managePopup"
    ).style.display="none";

}

function openAdd(){

    document.getElementById(
        "addPopup"
    ).style.display="block";

}

function closeAdd(){

    document.getElementById(
        "addPopup"
    ).style.display="none";

}

</script>

</body>
</html>
""",
        keys=parsed,
        active=active,
        inactive=inactive,
        total=len(parsed)
    )


# ================= RUN =================
if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )
