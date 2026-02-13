

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import os
import uuid

from datetime import datetime
from functools import wraps
app = Flask(__name__)
app.secret_key = "plastic-shop-secret-key-2026"

from itsdangerous import URLSafeTimedSerializer
serializer = URLSafeTimedSerializer(app.secret_key)
import smtplib
from email.mime.text import MIMEText

#email
EMAIL_ADDRESS = "garviborad12@gmail.com"
EMAIL_APP_PASSWORD = "grcp xowe bexc rawq"

def send_register_email(to_email, name):
    msg = MIMEText(f"Hello {name},\n\nYour account is successfully registered.")
    msg["Subject"] = "Welcome to Plastic Shop"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
    server.send_message(msg)
    server.quit()
# -------------------- ADD THIS --------------------
from functools import wraps



# ---------------- DATABASE CONNECTION ----------------
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",   # 👈 example (apna password dalo)
    database="plastic_shop"
)


cursor = db.cursor(dictionary=True)


def get_db():
    global db
    if db.is_connected():
        return db
    else:
        db = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="plastic_shop"
        )
        return db


# ===== DELIVERY BOY LOGIN REQUIRED =====
def deliveryboy_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("deliveryboy_id"):
            return redirect(url_for("deliveryboy_login"))
        return f(*args, **kwargs)
    return decorated_function


def admin_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("admin_login"))

        if not session.get("admin_dashboard_access"):
            session.clear()
            return redirect(url_for("admin_login"))

        return f(*args, **kwargs)
    return decorated_function

# ===== CUSTOMER LOGIN REQUIRED =====

def customer_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Login required to access Profile", "danger")
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function



@app.route("/profile_icon_click")
def profile_icon_click():
    """
    Handles profile icon click:
    - If logged in → go to profile
    - If not logged in → go to login, after login redirect to home
    """
    if session.get("user_id"):
        # Already logged in → go to profile
        return redirect(url_for("profile"))
    else:
        # Not logged in → go to login, after login redirect to home
        return redirect(url_for("login", next=url_for("home")))


# ===== CUSTOMER LOGIN REQUIRED FOR PROFILE =====
@app.route("/force_login_profile")
def force_login_profile():
    """
    Handles clicks on the profile icon.
    """
    # If user is already logged in, go directly to profile
    if session.get("user_id"):
        return redirect(url_for("profile"))
    
    # Not logged in → redirect to login with next=/profile
    return redirect(url_for("login", next=url_for("profile")))



# ---------- PROFILE ROUTE ----------
@app.route("/profile")
@customer_login_required
def profile():
    user_id = session.get("user_id")

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, name, email, mobile, address FROM customer WHERE id=%s",
        (user_id,)
    )
    user = cursor.fetchone()
    cursor.close()
    db.close()

    if not user:
        flash("User not found", "danger")
        return redirect(url_for("login"))

    cart_count = sum(session.get("cart", {}).values())
    return render_template(
        "customer/profile.html",
        user=user,
        cart_count=cart_count,
        current_year=datetime.now().year
    )




# --- Edit profile route ---

# ---------- EDIT PROFILE ROUTE (UPDATED) ----------
@app.route("/edit_profile", methods=["POST"])
@customer_login_required
def edit_profile():
    user_id = session["user_id"]
    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Fetch current user
    cursor.execute("SELECT id, name, email, mobile, address, password FROM customer WHERE id=%s", (user_id,))
    user = cursor.fetchone()
    if not user:
        flash("User not found!", "danger")
        cursor.close()
        db.close()
        return redirect(url_for("profile"))

    # Get form data
    name = request.form.get("name", "").strip()
    mobile = request.form.get("mobile", "").strip()
    address = request.form.get("address", "").strip()
    new_password = request.form.get("password", "").strip()
    confirm_password = request.form.get("confirm_password", "").strip()

    # Validate required fields
    if not name or not mobile or not address:
        flash("All fields are required.", "danger")
        cursor.close()
        db.close()
        return redirect(url_for("profile"))

    # Handle password change
    if new_password:
        if new_password != confirm_password:
            flash("Passwords do not match!", "danger")
            cursor.close()
            db.close()
            return redirect(url_for("profile"))
        hashed_password = generate_password_hash(new_password)
    else:
        hashed_password = user["password"]

    # Perform update
    try:
        cursor.execute("""
            UPDATE customer
            SET name=%s, mobile=%s, address=%s, password=%s
            WHERE id=%s
        """, (name, mobile, address, hashed_password, user_id))
        db.commit()
    except Exception as e:
        flash(f"Database error: {str(e)}", "danger")
        db.rollback()
        cursor.close()
        db.close()
        return redirect(url_for("profile"))

    # Update session data
    session["user_name"] = name

    flash("Profile updated successfully!", "success")
    cursor.close()
    db.close()
    return redirect(url_for("profile"))



# ================= REGISTER =================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        confirm = request.form["confirm_password"]
        address = request.form["address"]
        mobile = request.form["mobile"]

        if password != confirm:
            flash("Password and Confirm Password do not match", "danger")
            return redirect(url_for("register"))

        db = get_db()
        cur = db.cursor(dictionary=True)

        # Check if email already exists
        cur.execute("SELECT id FROM customer WHERE email=%s", (email,))
        if cur.fetchone():
            flash("Email already registered. Please login.", "danger")
            return redirect(url_for("login"))

        hashed_password = generate_password_hash(password)

        cur.execute(
            "INSERT INTO customer (name, email, password, address, mobile) VALUES (%s, %s, %s, %s, %s)",
            (name, email, hashed_password, address, mobile)
        )
        db.commit()

        # Optional email
        send_register_email(email, name)

        flash("Registration successful. Please login.", "success")
        return redirect(url_for("login"))

    return render_template("customer/register.html")

#login customer
# ---------- LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    next_page = request.args.get("next")  # Page to redirect after login

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM customer WHERE email=%s", (email,))
        user = cursor.fetchone()
        cursor.close()
        db.close()

        if user and check_password_hash(user["password"], password):
            # Set session
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_email"] = user["email"]

            flash("Login successful ✅", "success")

            # Redirect to the intended page (next) OR homepage
            if next_page:
                return redirect(next_page)
            else:
                return redirect(url_for("home"))

        flash("Invalid email or password ❌", "danger")

    # Pass next_page to login form
    return render_template("customer/login.html", next=next_page)



# ================= LOGOUT =================
# ---------- LOGOUT ROUTE (RECOMMENDED) ----------
@app.route("/logout")
def logout():
    """Clear all session data on logout"""
    session.clear()
    flash("You have been logged out successfully", "success")
    return redirect(url_for("home"))



# ---------------- HOME ----------------
@app.route("/")
def home():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            p.id,
            p.name,
            p.price,
            p.image,
            p.folder,
            o.offer_percent
        FROM products p
        LEFT JOIN offers o 
            ON o.product_id = p.id
    """)

    products = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("customer/index.html", products=products)






    
# ================= USER LOGIN =================








@app.route("/services")
def services():
    return render_template("customer/services.html")
    
@app.route("/about")
def about():
    return render_template("customer/about.html")




        # ===== visitor feedback =====
@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    db = get_db()

    if request.method == "POST":
        cursor = db.cursor(dictionary=True)

        name = request.form.get("name")
        email = request.form.get("email")
        rating = request.form.get("rating")
        message = request.form.get("message")

        cursor.execute(
            "SELECT id FROM feedback WHERE email=%s AND user_id IS NULL",
            (email,)
        )
        existing = cursor.fetchone()
        cursor.fetchall()  # 🔥 CLEAR RESULT

        if existing:
            cursor.execute(
                "UPDATE feedback SET rating=%s, message=%s WHERE id=%s",
                (rating, message, existing["id"])
            )
        else:
            cursor.execute(
                "INSERT INTO feedback (name, email, rating, message) VALUES (%s,%s,%s,%s)",
                (name, email, rating, message)
            )

        db.commit()
        cursor.close()

        flash("Thank you for your feedback!", "success")
        return redirect(url_for("feedback"))

    # ---------- GET ----------
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM feedback WHERE user_id IS NULL ORDER BY id DESC")
    feedbacks = cursor.fetchall()
    cursor.close()

    return render_template("customer/feedback.html", feedbacks=feedbacks)








# ADMIN FEEDBACK PAGE
# ADMIN FEEDBACK PAGE
@app.route("/admin/feedback")
@admin_login_required
def admin_feedback():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM feedback ORDER BY id DESC")
    feedbacks = cursor.fetchall()
    cursor.close()

    return render_template("admin/feedback.html", feedbacks=feedbacks)



#reply feedback

# REPLY (UPDATE)
@app.route("/admin/feedback/reply/<int:id>", methods=["POST"])
@admin_login_required
def admin_feedback_reply(id):
    reply = request.form.get("reply")

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "UPDATE feedback SET admin_reply=%s WHERE id=%s",
        (reply, id)
    )
    db.commit()
    cursor.close()

    return redirect(url_for("admin_feedback"))




# DELETE REPLY
# DELETE REPLY ONLY
@app.route("/admin/feedback/reply/delete/<int:id>", methods=["POST"])
@admin_login_required
def delete_reply(id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "UPDATE feedback SET admin_reply=NULL WHERE id=%s",
        (id,)
    )
    db.commit()
    cursor.close()

    flash("Reply deleted successfully!", "success")
    return redirect(url_for("admin_feedback"))




# category page (customer)

@app.route("/category")
def category_page():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    # table name = category, no status column
    cursor.execute("SELECT * FROM category")
    categories = cursor.fetchall()

    cursor.close()
    return render_template(
        "customer/category.html",
        categories=categories
    )




# ===== customer SUBCATEGORY =====

@app.route("/subcategory/<int:category_id>")
def customer_subcategory(category_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    # 🔹 dropdown se aane wala subcategory id
    selected_sub_id = request.args.get("sub_id")

    # 🔹 dropdown list (same category)
    cursor.execute(
        "SELECT id, name FROM subcategory WHERE category_id=%s",
        (category_id,)
    )
    subcategory_list = cursor.fetchall()

    # 🔹 FILTER LOGIC (IMPORTANT)
    if selected_sub_id:
        cursor.execute(
            "SELECT * FROM subcategory WHERE id=%s AND category_id=%s",
            (selected_sub_id, category_id)
        )
    else:
        cursor.execute(
            "SELECT * FROM subcategory WHERE category_id=%s",
            (category_id,)
        )

    products = cursor.fetchall()

    # 🔹 image path
    for p in products:
        folder = p.get("folder") or ""
        image = p.get("image") or "default.png"
        p["img_path"] = (
            f"/static/images/{folder}/{image}"
            if folder else "/static/images/default.png"
        )

    # 🔹 category name
    cursor.execute("SELECT name FROM category WHERE id=%s", (category_id,))
    category = cursor.fetchone()
    category_name = category["name"] if category else "Subcategory Products"

    cursor.close()

    return render_template(
        "customer/subcategory.html",
        products=products,
        category_name=category_name,
        subcategory_list=subcategory_list,
        category_id=category_id,
        selected_sub_id=selected_sub_id
    )



# =================================================
# ========== DELIVERY BOY DASHBOARD ===================
# =================================================

# ================= DELIVERY BOY LOGIN =================

@app.route("/deliveryboy/login", methods=["GET", "POST"])
def deliveryboy_login():
    if request.method == "POST":
        email = request.form.get("email").strip()
        password = request.form.get("password")

        db_conn = get_db()  # ✅ ensure live connection
        cursor = db_conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM delivery_boys WHERE email=%s", (email,))
        delivery = cursor.fetchone()
        cursor.close()

        if delivery and check_password_hash(delivery["password"], password):
            session["deliveryboy_id"] = delivery["id"]
            session["deliveryboy_name"] = delivery["name"]
            session["deliveryboy_dashboard_access"] = True

            return redirect(url_for("deliveryboy_dashboard"))

        flash("Invalid delivery boy credentials", "danger")
        return redirect(url_for("deliveryboy_login"))

    return render_template("deliveryboy/login.html")




@app.route("/deliveryboy/dashboard")
@deliveryboy_login_required
def deliveryboy_dashboard():
    return render_template(
        "deliveryboy/dashboard.html",
        name=session.get("deliveryboy_name")
    )




@app.route("/deliveryboy/logout")
def deliveryboy_logout():
    session.pop("deliveryboy_id", None)
    session.pop("deliveryboy_name", None)
    session.pop("deliveryboy_dashboard_access", None)
    flash("Delivery Boy logged out successfully", "success")
    # Redirect to delivery boy login page instead of home
    return redirect(url_for("deliveryboy_login"))





# =================================================
# ========== ADMIN DASHBOARD ==========================
# ================================================
@app.route("/admin/dashboard")
@admin_login_required
def admin_dashboard():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Total Orders
    cursor.execute("SELECT COUNT(*) AS total_orders FROM orders")
    total_orders = cursor.fetchone()["total_orders"]

    # Pending Orders
    cursor.execute("SELECT COUNT(*) AS pending_orders FROM orders WHERE order_status='pending'")
    pending_orders = cursor.fetchone()["pending_orders"]

    # Total Products
    cursor.execute("SELECT COUNT(*) AS total_products FROM products")
    total_products = cursor.fetchone()["total_products"]

    # Total Customers
    cursor.execute("SELECT COUNT(*) AS total_customers FROM customer")
    total_customers = cursor.fetchone()["total_customers"]

    cursor.close()
    db.close()

    return render_template(
        "admin/dashboard.html",
        total_orders=total_orders,
        pending_orders=pending_orders,
        total_products=total_products,
        total_customers=total_customers
    )






@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_id", None)
    session.pop("admin_email", None)
    session.pop("admin_dashboard_access", None)
    flash("Admin logged out successfully", "success")
    # Redirect to admin login page instead of home
    return redirect(url_for("admin_login"))






# ================= admin ( login) =================


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    # If admin already logged in, redirect to dashboard
    if "admin_id" in session and session.get("admin_dashboard_access"):
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        email = request.form.get("email").strip()
        password = request.form.get("password")

        db = get_db()  # ✅ get a fresh connection
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT * FROM admin WHERE email=%s", (email,))
        admin = cursor.fetchone()

        cursor.close()
        db.close()  # ✅ close the connection

        if admin and check_password_hash(admin["password"], password):
            session["admin_id"] = admin["id"]
            session["admin_email"] = admin["email"]
            session["admin_dashboard_access"] = True
            return redirect(url_for("admin_dashboard"))

        flash("Invalid admin credentials", "danger")
        return redirect(url_for("admin_login"))

    return render_template("admin/login.html")








@app.route('/admin/delivery_boy')
def delivery_boy():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="plastic_shop"
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM delivery_boys")
    delivery_boys = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template(
        "admin/deliveryboy.html",
        delivery_boys=delivery_boys
    )









@app.route("/add_delivery_boy", methods=["POST"])
def add_delivery_boy():
    name = request.form.get("name")
    email = request.form.get("email")
    phone = request.form.get("phone")
    password = request.form.get("password")

    if not password:
        flash("Please enter password for delivery boy", "danger")
        return redirect(url_for("delivery_boy"))

    hashed_password = generate_password_hash(password)

    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO delivery_boys (name, email, phone, password) VALUES (%s,%s,%s,%s)",
        (name, email, phone, hashed_password)
    )
    db.commit()
    cursor.close()

    flash("Delivery boy added successfully", "success")
    return redirect(url_for("delivery_boy"))





@app.route("/delete_delivery_boy/<int:id>", methods=["POST"])
def delete_delivery_boy(id):
    cursor = db.cursor()
    cursor.execute("DELETE FROM delivery_boys WHERE id=%s", (id,))
    db.commit()
    cursor.close()

    flash("Delivery boy deleted successfully", "success")
    return redirect(url_for("delivery_boy"))





@app.route("/edit_delivery_boy/<int:id>")
def edit_delivery_boy(id):
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="plastic_shop"
    )
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM delivery_boys")
    delivery_boys = cursor.fetchall()

    cursor.execute("SELECT * FROM delivery_boys WHERE id=%s", (id,))
    edit_delivery = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template(
        "admin/deliveryboy.html",
        delivery_boys=delivery_boys,
        edit_delivery=edit_delivery
    )




@app.route("/update_delivery_boy/<int:id>", methods=["POST"])
def update_delivery_boy(id):
    name = request.form["name"]
    email = request.form["email"]
    phone = request.form["phone"]

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="plastic_shop"
    )
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE delivery_boys
        SET name=%s, email=%s, phone=%s
        WHERE id=%s
    """, (name, email, phone, id))

    conn.commit()
    cursor.close()
    conn.close()

    flash("Delivery boy updated successfully", "success")
    return redirect(url_for("delivery_boy"))



# ================= CONTACT US (customer + ) =================
@app.route("/contact", methods=["GET", "POST"])
def contact():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        message = request.form.get("message", "").strip()

        if not name or not email or not message:
            flash("All fields are required", "danger")
            cursor.close()
            db.close()
            return redirect(url_for("contact"))

        # Step 1: Default user_id from session
        user_id = session.get("user_id")

        # Step 2: If session empty, try to get user_id from email
        if not user_id:
            cursor.execute("SELECT id FROM customer WHERE email=%s", (email,))
            user = cursor.fetchone()
            if user:
                user_id = user["id"]

        # Step 3: Insert into contact_messages
        try:
            cursor.execute(
                """
                INSERT INTO contact_messages (name, email, message, user_id, created_at)
                VALUES (%s, %s, %s, %s, NOW())
                """,
                (name, email, message, user_id)
            )
            db.commit()
            flash("Message sent successfully ✅", "success")
        except Exception as e:
            db.rollback()
            flash(f"Error sending message: {str(e)}", "danger")
        finally:
            cursor.close()
            db.close()

        return redirect(url_for("contact"))

    return render_template("customer/contact.html")




# ================= ADMIN CONTACT MESSAGES =================
@app.route("/admin/contact")
@admin_login_required
def admin_contact():
    db = get_db()                # ✅ GET LIVE DB CONNECTION
    cursor = db.cursor(dictionary=True)  # ✅ NEW CURSOR

    cursor.execute("SELECT * FROM contact_messages ORDER BY id DESC")
    messages = cursor.fetchall()
    cursor.close()

    return render_template("admin/contact.html", messages=messages)




#forgot password customer


@app.route('/forgot_password', methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")

        db = get_db()  # ✅ get a fresh connection
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT * FROM customer WHERE email=%s", (email,))
        user = cursor.fetchone()

        if not user:
            flash("Email not found", "danger")
            return redirect(url_for("forgot_password"))

        token = "123456"  # demo token

        cursor.execute("UPDATE customer SET reset_token=%s WHERE email=%s", (token, email))
        db.commit()
        cursor.close()
        db.close()

        flash("Reset link sent to your email (demo token: 123456)", "success")
        return redirect(url_for("reset_password", token=token))

    return render_template('customer/forgot_password.html')


@app.route('/reset_password/<token>', methods=["GET", "POST"])
def reset_password(token):
    if request.method == "POST":
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        if new_password != confirm_password:
            flash("Password not matched", "danger")
            return redirect(url_for("reset_password", token=token))

        db = get_db()  # ✅ fresh connection
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT * FROM customer WHERE reset_token=%s", (token,))
        user = cursor.fetchone()

        if not user:
            flash("Invalid token", "danger")
            cursor.close()
            db.close()
            return redirect(url_for("forgot_password"))

        hashed_password = generate_password_hash(new_password)
        cursor.execute("UPDATE customer SET password=%s, reset_token=NULL WHERE id=%s",
                       (hashed_password, user["id"]))
        db.commit()
        cursor.close()
        db.close()

        flash("Password changed successfully", "success")
        return redirect(url_for("login"))

    return render_template('customer/reset_password.html', token=token)


#admin forgot password

@app.route("/admin/forgot-password", methods=["GET", "POST"])
def admin_forgot_password():
    if request.method == "POST":
        email = request.form["email"]

        db = get_db()  # ✅ fresh connection
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT * FROM admin WHERE email=%s", (email,))
        admin = cursor.fetchone()

        if not admin:
            flash("Admin email not found", "danger")
            cursor.close()
            db.close()
            return redirect(url_for("admin_forgot_password"))

        token = "ADMIN123"  # demo token

        cursor.execute("UPDATE admin SET reset_token=%s WHERE id=%s", (token, admin["id"]))
        db.commit()
        cursor.close()
        db.close()

        flash("Reset link sent to admin email (demo token: ADMIN123)", "success")
        return redirect(url_for("admin_reset_password", token=token))

    return render_template("admin/forgot_password.html")


@app.route("/admin/reset-password/<token>", methods=["GET", "POST"])
def admin_reset_password(token):
    db = get_db()  # ✅ fresh connection
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM admin WHERE reset_token=%s", (token,))
    admin = cursor.fetchone()

    if not admin:
        flash("Invalid reset link", "danger")
        cursor.close()
        db.close()
        return redirect(url_for("admin_forgot_password"))

    if request.method == "POST":
        password = request.form["password"]
        confirm = request.form["confirm_password"]

        if password != confirm:
            flash("Password not matched", "danger")
            cursor.close()
            db.close()
            return redirect(url_for("admin_reset_password", token=token))

        hashed = generate_password_hash(password)

        cursor.execute(
            "UPDATE admin SET password=%s, reset_token=NULL WHERE id=%s",
            (hashed, admin["id"])
        )
        db.commit()
        cursor.close()
        db.close()

        flash("Password reset successfully", "success")
        return redirect(url_for("admin_login"))

    cursor.close()
    db.close()
    return render_template("admin/reset_password.html", token=token)






#deliveryboy


# ================= DELIVERY BOY FORGOT PASSWORD =================
@app.route("/deliveryboy/forgot-password", methods=["GET", "POST"])
def deliveryboy_forgot_password():
    if request.method == "POST":
        email = request.form.get("email")

        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM delivery_boys WHERE email=%s", (email,))
        user = cursor.fetchone()
        cursor.close()

        if not user:
            flash("Email not found", "danger")
            return redirect(url_for("deliveryboy_forgot_password"))

        token = serializer.dumps(email, salt="delivery-reset")

        # 🔥 DIRECT RESET PAGE
        return redirect(
            url_for("deliveryboy_reset_password", token=token)
        )

    return render_template("deliveryboy/forgot_password.html")


# ================= DELIVERY BOY RESET PASSWORD =================
@app.route("/deliveryboy/reset-password/<token>", methods=["GET", "POST"])
def deliveryboy_reset_password(token):
    try:
        email = serializer.loads(
            token,
            salt="delivery-reset",
            max_age=3600
        )
    except:
        flash("Reset link expired or invalid", "danger")
        return redirect(url_for("deliveryboy_forgot_password"))

    if request.method == "POST":
        password = request.form.get("password")
        confirm = request.form.get("confirm_password")

        if password != confirm:
            flash("Passwords do not match", "danger")
            return redirect(request.url)

        hashed = generate_password_hash(password)

        cursor = db.cursor()
        cursor.execute(
            "UPDATE delivery_boys SET password=%s WHERE email=%s",
            (hashed, email)
        )
        db.commit()
        cursor.close()

        # ✅ MESSAGE ONLY HERE
        flash("Password reset successful. Please login.", "success")

        # 🔥 LOGIN OPEN but NO MESSAGE THERE
        return redirect(url_for("deliveryboy_login"))

    return render_template(
        "deliveryboy/reset_password.html",
        token=token
    )


 

# ================= ADMIN ADD PRODUCT hompage=================
@app.route("/admin/product", methods=["GET", "POST"])
@admin_login_required
def admin_product():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":
        product_id = request.form.get("product_id")
        name = request.form["name"].strip()
        price = request.form["price"]
        qty = request.form.get("qty", 1)
        image = request.form["image"].strip()
        folder = request.form["folder"].strip()
        rating = request.form.get("rating", 4)

        if not name or not folder or not image:
            flash("Product name, folder and image are required", "danger")
            return redirect(url_for("admin_product"))

        if product_id:
            cursor.execute("""
                UPDATE products
                SET name=%s, price=%s, qty=%s, image=%s, folder=%s, rating=%s
                WHERE id=%s
            """, (name, price, qty, image, folder, rating, product_id))
            db.commit()
            flash(f"Product '{name}' updated successfully!", "success")
        else:
            cursor.execute("""
                INSERT INTO products (name, price, qty, image, rating, folder)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (name, price, qty, image, rating, folder))
            db.commit()
            flash(f"Product '{name}' added successfully!", "success")

        return redirect(url_for("admin_product"))

    # ============ PAGINATION ============
    per_page = 6
    page = int(request.args.get("page", 1))
    offset = (page - 1) * per_page

    cursor.execute("SELECT COUNT(*) AS total FROM products")
    total_products = cursor.fetchone()["total"]
    total_pages = (total_products + per_page - 1) // per_page

    cursor.execute("SELECT * FROM products ORDER BY id DESC LIMIT %s OFFSET %s", (per_page, offset))
    products = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("admin/product.html",
                           products=products,
                           page=page,
                           total_pages=total_pages)



#updated productt
@app.route("/admin/product/update", methods=["POST"])
@admin_login_required
def admin_product_update():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    # 🔹 Form data
    product_id = request.form.get("product_id")
    name   = request.form.get("name").strip()
    price  = request.form.get("price")
    qty    = request.form.get("qty")
    image  = request.form.get("image").strip()
    folder = request.form.get("folder").strip()
    rating = request.form.get("rating", 4)

    # 🔴 Validation
    if not product_id:
        flash("Product ID missing", "danger")
        return redirect(url_for("admin_product"))

    if not name or not image or not folder:
        flash("All fields are required", "danger")
        return redirect(url_for("admin_product"))

    # 🔹 Update query
    cursor.execute("""
        UPDATE products
        SET name=%s,
            price=%s,
            
            image=%s,
            
            folder=%s
            
        WHERE id=%s
    """, (name, price,  image, folder, product_id))

    db.commit()

    flash("Product updated successfully!", "success")
    return redirect(url_for("admin_product"))


#admin delete product hompage 

@app.route("/admin/product/delete/<int:id>")
@admin_login_required
def delete_product(id):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("DELETE FROM products WHERE id=%s", (id,))
    db.commit()

    if cursor.rowcount == 0:
        flash("Product not found ❌", "danger")
    else:
        flash("Product deleted successfully ✅", "success")

    cursor.close()
    db.close()

    return redirect(url_for("admin_product"))


#admin category
# ===== ADMIN CATEGORY PAGE =====
@app.route("/admin/category", methods=["GET"])
@admin_login_required
def admin_category():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    page = int(request.args.get("page", 1))
    per_page = 2
    offset = (page - 1) * per_page

    # total count
    cursor.execute("SELECT COUNT(*) AS total FROM category")
    total = cursor.fetchone()["total"]
    total_pages = (total + per_page - 1) // per_page

    # paginated categories
    cursor.execute(
        "SELECT * FROM category LIMIT %s OFFSET %s",
        (per_page, offset)
    )
    categories = cursor.fetchall()
    cursor.close()

    return render_template(
        "admin/category.html",
        categories=categories,
        page=page,
        total_pages=total_pages
    )


# ===== ADD CATEGORY =====
# ===== ADD CATEGORY =====
@app.route("/admin/category/add", methods=["POST"])
@admin_login_required
def add_category():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    name = request.form.get("name", "").strip()
    image = request.form.get("image", "").strip()

    # Keep only filename if user typed path
    image = image.split("/")[-1]

    if not name or not image:
        flash("Please fill all fields!", "danger")
        return redirect(url_for("admin_category"))

    # Check for duplicate category name or image
    cursor.execute("SELECT * FROM category WHERE name=%s OR image=%s", (name, image))
    existing = cursor.fetchone()
    if existing:
        flash("Category with this name or image already exists!", "danger")
        cursor.close()
        return redirect(url_for("admin_category"))

    cursor.execute("INSERT INTO category (name, image) VALUES (%s, %s)", (name, image))
    db.commit()
    cursor.close()

    flash("Category added successfully ✅", "success")
    return redirect(url_for("admin_category"))


# ===== UPDATE CATEGORY =====
@app.route("/admin/category/update", methods=["POST"])
@admin_login_required
def update_category():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    category_id = request.form.get("category_id")
    name = request.form.get("name", "").strip()
    image = request.form.get("image", "").strip()
    old_image = request.form.get("old_image", "").strip()

    if not category_id or not name:
        flash("Category name is required!", "danger")
        cursor.close()
        return redirect(url_for("admin_category"))

    # Use old image if admin didn't type new one
    if image:
        image = image.split("/")[-1]
    else:
        image = old_image

    # Check for duplicates
    check_cursor = db.cursor(dictionary=True)
    check_cursor.execute(
        "SELECT * FROM category WHERE (name=%s OR image=%s) AND id != %s",
        (name, image, category_id)
    )
    existing = check_cursor.fetchall()
    check_cursor.close()

    if existing:
        flash("Another category with this name or image already exists!", "danger")
        cursor.close()
        return redirect(url_for("admin_category"))

    # Update category
    cursor.execute(
        "UPDATE category SET name=%s, image=%s WHERE id=%s",
        (name, image, category_id)
    )
    db.commit()
    cursor.close()

    flash("Category updated successfully ✅", "success")
    return redirect(url_for("admin_category"))


#delete category admin 
@app.route("/admin/category/delete/<int:category_id>", methods=["POST"])
@admin_login_required
def delete_category(category_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM category WHERE id=%s", (category_id,))
    db.commit()
    cursor.close()
    flash("Category deleted successfully ✅", "success")
    return redirect(url_for("admin_category"))


# ===== SUBCATEGORY PAGE =====
# ===== VIEW SUBCATEGORY PAGE =====
# Admin subcategory
# ===========================
# Admin Subcategory Routes
# ===========================
@app.route("/admin/subcategory", methods=["GET"])
@admin_login_required
def admin_subcategory():
    db = get_db()
    cursor = db.cursor(dictionary=True, buffered=True)

    # Categories
    cursor.execute("SELECT * FROM category")
    categories = cursor.fetchall()

    category_id = request.args.get("category_id")

    if category_id:
        cursor.execute(
            "SELECT * FROM subcategory WHERE category_id=%s",
            (category_id,)
        )
    else:
        cursor.execute("SELECT * FROM subcategory")

    subcategories = cursor.fetchall()

    # Image path
    for sub in subcategories:
        folder = sub.get("folder") or ""
        image = sub.get("image") or "default.png"
        sub["img_path"] = (
            f"/static/images/{folder}/{image}"
            if folder else "/static/images/default.png"
        )

    cursor.close()

    return render_template(
        "admin/subcategory.html",
        categories=categories,
        subcategories=subcategories,
        selected_category=category_id
    )


@app.route("/admin/subcategory/add", methods=["POST"])
@admin_login_required
def add_subcategory():
    db = get_db()
    cursor = db.cursor(dictionary=True, buffered=True)

    category_id = request.form.get("category_id")
    folder = request.form.get("folder", "").strip()
    name = request.form.get("name", "").strip()
    image = request.form.get("image", "").strip() or "default.png"

    if not category_id or not name or not folder:
        cursor.close()
        flash("Please fill all fields!", "danger")
        return redirect(url_for("admin_subcategory", category_id=category_id))

    # Duplicate check
    cursor.execute(
        "SELECT id FROM subcategory WHERE name=%s AND category_id=%s",
        (name, category_id)
    )
    existing = cursor.fetchone()

    if existing:
        cursor.close()
        flash("Subcategory already exists!", "danger")
        return redirect(url_for("admin_subcategory", category_id=category_id))

    cursor.execute("""
        INSERT INTO subcategory
        (category_id, folder, name, image)
        VALUES (%s,%s,%s,%s)
    """, (category_id, folder, name, image))

    db.commit()
    cursor.close()

    flash("Subcategory added successfully ✅", "success")
    return redirect(url_for("admin_subcategory", category_id=category_id))


@app.route("/admin/subcategory/update", methods=["POST"])
@admin_login_required
def update_subcategory():
    db = get_db()
    cursor = db.cursor(buffered=True)

    sub_id = request.form["sub_id"]
    category_id = request.form["category_id"]
    folder = request.form["folder"]
    image = request.form["image"]
    name = request.form["name"]

    cursor.execute("""
        UPDATE subcategory SET
        category_id=%s,
        folder=%s,
        image=%s,
        name=%s
        WHERE id=%s
    """, (category_id, folder, image, name, sub_id))

    db.commit()
    cursor.close()

    flash("Subcategory updated successfully!", "success")
    return redirect(url_for("admin_subcategory"))

#delete  subcategory
@app.route("/admin/subcategory/delete", methods=["POST"])
def delete_subcategory():
    sub_id = request.form.get("sub_id")
    if not sub_id:
        return jsonify({"success": False, "message": "No subcategory ID provided"})
    try:
        cursor.execute("DELETE FROM subcategory WHERE id=%s", (sub_id,))
        db.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})



#pdetails

# ----------------- Product Details Page -----------------
@app.route("/admin/pdetails", methods=["GET"])
def admin_pdetails():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Fetch categories
    cursor.execute("SELECT * FROM category")
    categories = cursor.fetchall()

    # Fetch subcategories
    cursor.execute("SELECT * FROM subcategory")
    subcategories = cursor.fetchall()

    # Fetch all products
    cursor.execute("SELECT * FROM pdetails")
    products = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "admin/pdetails.html",
        categories=categories,
        subcategories=subcategories,
        products=products,
        selected_category="",
        selected_subcategory="",
        folder="",
        image="",
        name=""
    )

# ----------------- Get subcategories by category -----------------
@app.route("/admin/get_subcategories/<int:category_id>")
def get_subcategories(category_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM subcategory WHERE category_id=%s", (category_id,))
    subcategories = cursor.fetchall()
    cursor.close()
    db.close()
    return jsonify(subcategories)



@app.route("/admin/pdetails/add", methods=["POST"])
@admin_login_required
def add_pdetails():
    category_id = request.form.get("category_id")
    subcategory_id = request.form.get("subcategory_id")
    folder = request.form.get("folder").strip()
    name = request.form.get("name").strip()
    image = request.form.get("image").strip()
    price = request.form.get("price")  # ✅ get price from form

    if not all([category_id, subcategory_id, folder, name, image, price]):
        flash("All fields are required!", "danger")
        return redirect(url_for("admin_pdetails"))

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        """
        INSERT INTO pdetails (category_id, subcategory_id, folder, name, image, price) 
        VALUES (%s,%s,%s,%s,%s,%s)
        """,
        (category_id, subcategory_id, folder, name, image, price)
    )
    db.commit()
    cursor.close()
    db.close()

    flash("Product added successfully!", "success")
    return redirect(url_for("admin_pdetails"))



#update admin pdetails 


# ----------------- Update Product admin pdetails -----------------
@app.route("/admin/pdetails/update", methods=["POST"])
@admin_login_required
def update_pdetails():
    product_id = request.form.get("product_id")
    category_id = request.form.get("category_id")
    subcategory_id = request.form.get("subcategory_id")
    folder = request.form.get("folder").strip()
    name = request.form.get("name").strip()
    image = request.form.get("image").strip()
    price = request.form.get("price")  # ✅ get price from form

    if not all([product_id, category_id, subcategory_id, folder, name, image, price]):
        flash("All fields are required!", "danger")
        return redirect(url_for("admin_pdetails"))

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        """
        UPDATE pdetails 
        SET category_id=%s, subcategory_id=%s, folder=%s, name=%s, image=%s, price=%s 
        WHERE id=%s
        """,
        (category_id, subcategory_id, folder, name, image, price, product_id)
    )
    db.commit()
    cursor.close()
    db.close()

    flash("Product updated successfully!", "success")
    return redirect(url_for("admin_pdetails"))


# ----------------- Delete Product  pdetails admin-----------------
@app.route("/admin/pdetails/delete", methods=["POST"])
@admin_login_required
def delete_pdetails():
    product_id = request.form.get("product_id")
    if not product_id:
        flash("Product ID missing!", "danger")
        return redirect(url_for("admin_pdetails"))

    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM pdetails WHERE id=%s", (product_id,))
    db.commit()
    cursor.close()
    db.close()

    flash("Product deleted successfully!", "success")
    return redirect(url_for("admin_pdetails"))


#customer pdetails
@app.route("/pdetails")
def pdetails():
    category_id = request.args.get("category_id")
    subcategory_id = request.args.get("subcategory_id")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    # ================== Fetch categories for dropdown ==================
    cursor.execute("SELECT * FROM category")
    categories = cursor.fetchall()

    # ================== Fetch subcategories for dropdown ==================
    if category_id:
        cursor.execute("SELECT * FROM subcategory WHERE category_id=%s", (category_id,))
        subcategories = cursor.fetchall()
    else:
        cursor.execute("SELECT * FROM subcategory")
        subcategories = cursor.fetchall()

    # ================== Fetch selected subcategory for heading ==================
    subcategory = None
    if subcategory_id:
        cursor.execute("SELECT * FROM subcategory WHERE id=%s", (subcategory_id,))
        subcategory = cursor.fetchone()

    # ================== Fetch pdetails products with offers ==================
    query = """
        SELECT 
            pd.id,
            pd.name,
            pd.price,
            pd.folder,
            pd.image,
            pd.category_id,
            pd.subcategory_id,
            o.offer_percent
        FROM pdetails pd
        LEFT JOIN offers o ON o.pdetails_id = pd.id
        WHERE 1=1
    """
    params = []

    if category_id:
        query += " AND pd.category_id = %s"
        params.append(category_id)
    if subcategory_id:
        query += " AND pd.subcategory_id = %s"
        params.append(subcategory_id)

    cursor.execute(query, params)
    products = cursor.fetchall()

    cursor.close()

    return render_template(
        "customer/pdetails.html",
        categories=categories,
        subcategories=subcategories,
        products=products,
        selected_category=category_id,
        selected_subcategory=subcategory_id,
        subcategory=subcategory
    )




# Admin Orders Page
# Admin Orders Page
# ---------- Admin Orders Page ----------
# ---------- Admin Orders Page ----------
@app.route("/admin/orders")
def admin_orders():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    db = get_db()
    cur = db.cursor(dictionary=True)

    # Orders fetch karna customer name aur subcategory name ke saath
    cur.execute("""
        SELECT 
            o.id AS order_id,
            c.name AS customer_name,
            s.name AS subcategory_name,
            s.folder AS subcategory_folder,
            s.image AS subcategory_image,
            o.quantity,
            o.total_price,
            o.payment_status,
            o.order_date,
            o.delivery_date
        FROM orders o
        JOIN customers c ON o.user_id = c.id
        JOIN subcategory s ON o.subcategory_id = s.id
        ORDER BY o.id DESC
    """)
    orders = cur.fetchall()

    cur.close()
    db.close()

    return render_template("admin/orders.html", orders=orders)



# ---------- Update Delivery Date ----------
@app.route("/admin/orders/<int:order_id>/update_delivery", methods=["POST"])
def update_delivery_date(order_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    delivery_date = request.form.get("delivery_date")
    
    if not delivery_date:
        flash("Please enter a delivery date!", "danger")
        return redirect(url_for("admin_orders"))

    db = get_db()
    cur = db.cursor()
    cur.execute("UPDATE orders SET delivery_date=%s WHERE id=%s", (delivery_date, order_id))
    db.commit()
    cur.close()
    db.close()

    flash("Delivery date updated successfully!", "success")
    return redirect(url_for("admin_orders"))


#customer order

@app.route('/customer/orders')
def customer_orders():
    if "user_id" not in session:
        return redirect(url_for('login'))

    user_id = session["user_id"]
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            o.id AS order_id,
            sc.name AS subcategory_name,
            sc.image AS subcategory_image,
            sc.folder AS subcategory_folder,
            o.quantity,
            o.total_price,
            o.payment_status,
            o.order_date,
            o.delivery_date,
            o.order_status   -- ✅ Make sure this is selected

        FROM orders o
        JOIN subcategory sc ON o.subcategory_id = sc.id
        WHERE o.user_id = %s
        ORDER BY o.order_date DESC
    """, (user_id,))

    orders = cursor.fetchall()
    return render_template('customer/orders.html', orders=orders)

#admin order status
@app.route('/admin/order/status/<int:order_id>', methods=['POST'])
def update_order_status(order_id):
    status = request.form.get('order_status')

    db = get_db()
    cur = db.cursor()
    cur.execute(
        "UPDATE orders SET order_status=%s WHERE id=%s",
        (status, order_id)
    )
    db.commit()

    flash("Order status updated successfully", "success")
    return redirect(url_for('admin_orders'))


#payment admin










#product details hompage
@app.route("/product/<int:product_id>")
def product_details(product_id):
    db = get_db()
    cur = db.cursor(dictionary=True)

    # 🔹 Product basic info
    cur.execute("""
        SELECT id, name, price, image, folder
        FROM products
        WHERE id = %s
    """, (product_id,))
    product = cur.fetchone()

    if not product:
        return "Product not found", 404

    # 🔹 Product description (use product_id directly)
    cur.execute("""
        SELECT description
        FROM product_details
        WHERE product_id=%s
    """, (product_id,))
    detail = cur.fetchone()
    description = detail["description"] if detail else "No description available"

    # 🔹 Feedback (subcategory_id = product_id)
    cur.execute("""
        SELECT name, rating, message, admin_reply, created_at
        FROM feedback
        WHERE subcategory_id=%s
        ORDER BY created_at DESC
    """, (product_id,))
    feedbacks = cur.fetchall()

    # 🔹 Image path
    image_path = f"/static/images/{product['folder']}/{product['image']}"

    cur.close()
    return render_template(
        "customer/product_details.html",
        product=product,
        description=description,
        feedbacks=feedbacks,
        image_path=image_path
    )




@app.route("/add_feedback/<int:product_id>", methods=["POST"])
@customer_login_required
def add_feedback(product_id):
    db = get_db()
    cur = db.cursor()

    # 🔹 Treat product_id as subcategory_id only for feedback
    subcategory_id = product_id

    # 🔹 Get form data
    rating = request.form.get("rating")
    message = request.form.get("message")
    name = session.get("user_name")  # logged-in user
    email = session.get("user_email")

    # 🔹 Insert feedback
    cur.execute("""
        INSERT INTO feedback (subcategory_id, user_id, name, email, rating, message)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (subcategory_id, session['user_id'], name, email, rating, message))
    db.commit()
    cur.close()

    flash("Feedback added successfully ✅", "success")
    return redirect(url_for("product_details", product_id=product_id))



#admin product_dteails(description)

@app.route("/admin/product_details", methods=["GET", "POST"])
def admin_product_details():
    db = get_db()
    cur = db.cursor(dictionary=True)

    # ----- Fetch homepage products -----
    cur.execute("SELECT id, name FROM products")
    homepage_products = cur.fetchall() or []

    # ----- Fetch Product List products -----
    cur.execute("SELECT id, name, subcategory_id, category_id FROM pdetails")
    productlist_products = cur.fetchall() or []

    # ----- Fetch categories and subcategories -----
    cur.execute("SELECT id, name FROM category")
    categories = cur.fetchall() or []

    cur.execute("SELECT id, name, category_id FROM subcategory")
    subcategories = cur.fetchall() or []

    selected_homepage_desc = None
    selected_productlist_desc = None

    # ===================== ADD / UPDATE =====================
    if request.method == "POST":

        homepage_id = request.form.get("homepage_product_id")
        productlist_id = request.form.get("product_id")
        description = request.form.get("description")

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # -------- HOMEPAGE PRODUCT --------
        if homepage_id:
            cur.execute("SELECT id FROM product_details WHERE product_id=%s", (homepage_id,))
            exists = cur.fetchone()

            if exists:
                cur.execute(
                    "UPDATE product_details SET description=%s, created_at=%s WHERE product_id=%s",
                    (description, now, homepage_id)
                )
            else:
                cur.execute(
                    "INSERT INTO product_details (product_id, description, created_at) VALUES (%s,%s,%s)",
                    (homepage_id, description, now)
                )

        # -------- PRODUCT LIST PRODUCT --------
        elif productlist_id:
            cur.execute("SELECT id FROM product_details WHERE pdetails_id=%s", (productlist_id,))
            exists = cur.fetchone()

            if exists:
                cur.execute(
                    "UPDATE product_details SET description=%s, created_at=%s WHERE pdetails_id=%s",
                    (description, now, productlist_id)
                )
            else:
                cur.execute(
                    "INSERT INTO product_details (pdetails_id, description, created_at) VALUES (%s,%s,%s)",
                    (productlist_id, description, now)
                )

        db.commit()
        flash("Description saved successfully!", "success")
        return redirect(url_for("admin_product_details"))

    # ===================== HANDLE UPDATE CLICK (GET) =====================

    homepage_id = request.args.get("homepage_product_id")
    productlist_id = request.args.get("productlist_product_id")

    # Homepage update load
    if homepage_id:
        cur.execute("SELECT description FROM product_details WHERE product_id=%s", (homepage_id,))
        data = cur.fetchone()

        selected_homepage_desc = {
            "product_id": homepage_id,
            "description": data["description"] if data else ""
        }

    # ProductList update load
    if productlist_id:
        cur.execute("SELECT description FROM product_details WHERE pdetails_id=%s", (productlist_id,))
        data = cur.fetchone()

        selected_productlist_desc = {
            "product_id": productlist_id,
            "description": data["description"] if data else ""
        }

    # ===================== VIEW ALL DESCRIPTIONS =====================

    cur.execute("""
        SELECT pd.id, pd.description, p.name AS product_name,
               'homepage' AS type, pd.product_id
        FROM product_details pd
        JOIN products p ON pd.product_id = p.id
        WHERE pd.product_id IS NOT NULL
    """)
    all_homepage_descriptions = cur.fetchall() or []

    cur.execute("""
        SELECT pd.id, pd.description, p.name AS product_name,
               'productlist' AS type, pd.pdetails_id AS product_id
        FROM product_details pd
        JOIN pdetails p ON pd.pdetails_id = p.id
        WHERE pd.pdetails_id IS NOT NULL
    """)
    all_productlist_descriptions = cur.fetchall() or []

    all_descriptions = all_homepage_descriptions + all_productlist_descriptions

    cur.close()
    db.close()

    return render_template(
        "admin/product_details.html",
        homepage_products=homepage_products,
        productlist_products=productlist_products,
        categories=categories,
        subcategories=subcategories,
        all_descriptions=all_descriptions,
        selected_homepage_desc=selected_homepage_desc,
        selected_productlist_desc=selected_productlist_desc
    )


# ===================== DELETE =====================

@app.route("/admin/delete_product_description/<int:desc_id>", methods=["POST"])
def delete_product_description(desc_id):
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM product_details WHERE id=%s", (desc_id,))
    db.commit()
    cur.close()
    db.close()

    flash("Description deleted successfully!", "success")
    return redirect(url_for("admin_product_details"))


    

#productlist 
@app.route("/productlist")
def productlist():
    pid = request.args.get("pid")

    if not pid:
        return redirect(url_for("category_page"))

    try:
        pid = int(pid)
    except ValueError:
        return redirect(url_for("category_page"))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    # ✅ FIXED QUERY
    cursor.execute("""
        SELECT 
            p.id, 
            p.name, 
            p.price, 
            p.folder, 
            p.image,
            o.offer_percent,
            pd.description
        FROM pdetails p
        LEFT JOIN offers o
            ON o.pdetails_id = p.id
        LEFT JOIN product_details pd
            ON pd.pdetails_id = p.id   -- 🔥 FIXED HERE
        WHERE p.id = %s
        ORDER BY o.created_at DESC
        LIMIT 1
    """, (pid,))

    product = cursor.fetchone()

    if not product:
        return redirect(url_for("category_page"))

    # IMAGE PATH
    folder = product.get("folder") or ""
    image = product.get("image") or "default.png"

    if folder:
        product["img_path"] = f"/static/images/{folder}/{image}"
    else:
        product["img_path"] = f"/static/images/{image}"

    # PRICE CALCULATION
    price = float(product["price"])
    offer_percent = float(product.get("offer_percent") or 0)
    product["discounted_price"] = round(price * (1 - offer_percent / 100), 2)

    cursor.close()

    return render_template(
        "customer/productlist.html",
        products=[product]
    )



#cart customer






# ---------- ADD TO CART ----------
# ---------- ADD TO CART ----------
@app.route("/add_to_cart/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    customer_id = session.get("user_id")
    session_id = session.get("cart_session_id")

    import uuid
    if not customer_id and not session_id:
        session_id = str(uuid.uuid4())
        session["cart_session_id"] = session_id

    # Check if product is already in cart
    if customer_id:
        cursor.execute(
            "SELECT id, quantity FROM cart WHERE customer_id=%s AND pdetails_id=%s",
            (customer_id, product_id)
        )
    else:
        cursor.execute(
            "SELECT id, quantity FROM cart WHERE session_id=%s AND pdetails_id=%s",
            (session_id, product_id)
        )

    existing = cursor.fetchone()

    if existing:
        cursor.execute(
            "UPDATE cart SET quantity=%s WHERE id=%s",
            (existing["quantity"] + 1, existing["id"])
        )
    else:
        if customer_id:
            cursor.execute(
                "INSERT INTO cart (customer_id, pdetails_id, quantity, added_on) VALUES (%s, %s, %s, NOW())",
                (customer_id, product_id, 1)
            )
        else:
            cursor.execute(
                "INSERT INTO cart (session_id, pdetails_id, quantity, added_on) VALUES (%s, %s, %s, NOW())",
                (session_id, product_id, 1)
            )

    db.commit()
    cursor.close()
    db.close()
    flash("Product added to cart ✅", "success")
    return redirect(request.referrer or url_for("productlist"))



@app.route("/view_cart")
def view_cart():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    customer_id = session.get("user_id")
    session_id = session.get("cart_session_id")

    import uuid
    # If guest and no session_id yet, create one
    if not customer_id and not session_id:
        session_id = str(uuid.uuid4())
        session["cart_session_id"] = session_id

    # Fetch cart items
    if customer_id:
        cursor.execute("""
            SELECT 
                c.quantity,
                pd.id,
                pd.name,
                pd.price,
                pd.folder,
                pd.image
            FROM cart c
            JOIN pdetails pd ON c.pdetails_id = pd.id
            WHERE c.customer_id = %s
        """, (customer_id,))
    else:
        cursor.execute("""
            SELECT 
                c.quantity,
                pd.id,
                pd.name,
                pd.price,
                pd.folder,
                pd.image
            FROM cart c
            JOIN pdetails pd ON c.pdetails_id = pd.id
            WHERE c.session_id = %s
        """, (session_id,))

    products = cursor.fetchall()

    # Add image path
    for p in products:
        folder = p.get("folder") or ""
        image = p.get("image") or "default.png"
        p["img_path"] = f"/static/images/{folder}/{image}"

    cursor.close()
    db.close()

    return render_template("customer/cart.html", products=products)



@app.route("/remove_from_cart/<int:pid>", methods=["POST"])
def remove_from_cart(pid):
    db = get_db()
    cursor = db.cursor()

    customer_id = session.get("user_id")
    session_id = session.get("cart_session_id")

    import uuid
    # If guest and no session_id yet, create one
    if not customer_id and not session_id:
        session_id = str(uuid.uuid4())
        session["cart_session_id"] = session_id

    # Delete the product from cart based on user type
    if customer_id:
        cursor.execute(
            "DELETE FROM cart WHERE customer_id=%s AND pdetails_id=%s",
            (customer_id, pid)
        )
    else:
        cursor.execute(
            "DELETE FROM cart WHERE session_id=%s AND pdetails_id=%s",
            (session_id, pid)
        )

    db.commit()
    cursor.close()
    db.close()

    flash("Product removed from cart ❌", "success")
    return redirect(url_for("view_cart"))


@app.route("/update_cart", methods=["POST"])
def update_cart():
    db = get_db()
    cursor = db.cursor()

    customer_id = session.get("user_id")
    session_id = session.get("cart_session_id")

    import uuid
    # If guest and no session_id yet, create one
    if not customer_id and not session_id:
        session_id = str(uuid.uuid4())
        session["cart_session_id"] = session_id

    # Loop through form fields like qty_1, qty_2, etc.
    for key, value in request.form.items():
        if key.startswith("qty_"):
            try:
                product_id = int(key.split("_")[1])
                quantity = int(value)
                if quantity < 1:
                    quantity = 1  # minimum 1

                if customer_id:
                    cursor.execute(
                        "UPDATE cart SET quantity=%s WHERE customer_id=%s AND pdetails_id=%s",
                        (quantity, customer_id, product_id)
                    )
                else:
                    cursor.execute(
                        "UPDATE cart SET quantity=%s WHERE session_id=%s AND pdetails_id=%s",
                        (quantity, session_id, product_id)
                    )
            except ValueError:
                continue  # skip invalid inputs

    db.commit()
    cursor.close()
    db.close()

    flash("Cart quantities updated successfully ✅", "success")
    return redirect(url_for("view_cart"))



#buy now
@app.route('/buy-now/<int:pid>')
def buy_now(pid):
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Fetch product
    cursor.execute("SELECT * FROM pdetails WHERE id=%s", (pid,))
    product = cursor.fetchone()

    if not product:
        cursor.close()
        db.close()
        abort(404)

    # Fetch customer address
    cursor.execute("SELECT address FROM customer WHERE id=%s", (session["user_id"],))
    customer = cursor.fetchone()

    address = customer["address"] if customer else ""

    cursor.close()
    db.close()

    # Image path fix
    folder = product.get("folder") or ""
    image = product.get("image") or "default.png"

    if folder:
        product["img_path"] = f"/static/images/{folder}/{image}"
    else:
        product["img_path"] = "/static/images/default.png"

    return render_template(
        "customer/checkout.html",
        product=product,
        address=address
    )


@app.route("/update-address", methods=["POST"])
def update_address():
    if "user_id" not in session:
        return jsonify({"status": "error", "message": "Login required"}), 401

    new_address = request.form.get("address", "").strip()

    if not new_address:
        return jsonify({"status": "error", "message": "Address cannot be empty"}), 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE customer SET address=%s WHERE id=%s", (new_address, session["user_id"]))
    db.commit()
    cursor.close()
    db.close()

    return jsonify({"status": "success", "message": "Address updated"})




#admin payment
@app.route("/admin/payment")
def admin_payments():
    return render_template("admin/payment.html")


@app.route('/payment')
def payment():
    # ✅ Get parameters safely
    product_id = request.args.get("product_id", type=int)
    qty = request.args.get("qty", default=1, type=int)

    # ❌ If product_id missing
    if not product_id:
        return "No product selected", 400

    # ✅ Qty validation
    if qty < 1:
        qty = 1

    db = get_db()
    cursor = db.cursor(dictionary=True)

    # ✅ Fetch product
    cursor.execute("SELECT id, name, price, image, folder FROM pdetails WHERE id=%s", (product_id,))
    product = cursor.fetchone()

    cursor.close()
    db.close()

    if not product:
        return "Product not found", 404

    # ✅ Always calculate total in backend
    total_price = product["price"] * qty

    # ✅ Send separate variables (better practice)
    return render_template(
        "customer/payment.html",
        product=product,
        qty=qty,
        total_price=total_price
    )



@app.route('/place_order', methods=['POST'])
def place_order():
    payment_method = request.form.get('payment_method')
    online_method = request.form.get('online_method')
    
    # For now, just print or store data
    print("Payment Method:", payment_method)
    print("Online Method:", online_method)
    
    # Redirect to a success page or order summary
    return "Order Placed Successfully!"


#admin offer

# ===================== ADMIN OFFERS PAGE =====================
@app.route("/admin/offers")
@admin_login_required
def admin_offers():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            p.id, p.name, p.price, p.folder, p.image,
            o.offer_percent
        FROM products p
        LEFT JOIN offers o ON o.product_id = p.id
    """)
    products = cursor.fetchall()

    cursor.execute("""
        SELECT 
            pd.id, pd.name, pd.price, pd.folder, pd.image,
            pd.subcategory_id,
            o.offer_percent
        FROM pdetails pd
        LEFT JOIN offers o ON o.pdetails_id = pd.id
    """)
    pdetails_products = cursor.fetchall()

    # ================= Categories =================
    cursor.execute("SELECT id, name FROM category")
    categories = cursor.fetchall()

    # ================= Product offers list (for display) =================
    cursor.execute("""
        SELECT o.id AS offer_id, o.offer_percent,
               p.id AS product_id, p.name, p.image, p.folder
        FROM offers o
        JOIN products p ON o.product_id = p.id
        WHERE o.product_id IS NOT NULL
    """)
    product_offers = cursor.fetchall()

    # ================= PDetails offers list =================
    cursor.execute("""
        SELECT o.id AS offer_id, o.offer_percent,
               pd.id AS pdetails_id, pd.name, pd.image, pd.folder,
               pd.subcategory_id
        FROM offers o
        JOIN pdetails pd ON o.pdetails_id = pd.id
        WHERE o.pdetails_id IS NOT NULL
    """)
    pdetails_offers = cursor.fetchall()

    cursor.close()
    return render_template(
        "admin/offers.html",
        products=products,
        pdetails_products=pdetails_products,
        categories=categories,
        product_offers=product_offers,
        pdetails_offers=pdetails_offers
    )

# ===================== GET SUBCATEGORIES =====================
@app.route("/admin/get_subcategories/<int:category_id>")
@admin_login_required
def admin_get_subcategories(category_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, name FROM subcategory WHERE category_id=%s",
        (category_id,)
    )
    subcategories = cursor.fetchall()
    cursor.close()
    return jsonify(subcategories)

# ===================== GET SUBCATEGORIES (FOR OFFERS AJAX) =====================
@app.route("/get_subcategories/<int:category_id>")
def offers_get_subcategories(category_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, name FROM subcategory WHERE category_id=%s",
        (category_id,)
    )
    data = cursor.fetchall()
    cursor.close()
    return jsonify(data)

# ===================== GET PDETAILS BY SUBCATEGORY =====================
@app.route("/get_pdetails/<int:subcategory_id>")
def get_pdetails(subcategory_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, name FROM pdetails WHERE subcategory_id=%s",
        (subcategory_id,)
    )
    data = cursor.fetchall()
    cursor.close()
    return jsonify(data)

# ===================== ADD OFFER =====================
@app.route("/admin/offers/add", methods=["POST"])
@admin_login_required
def add_offer():
    db = get_db()
    cursor = db.cursor()

    # Get form values
    product_id = request.form.get("product_id")
    pdetails_id = request.form.get("pdetails_id")
    offer_percent = request.form.get("offer_percent")

    if not offer_percent:
        flash("Offer percentage is required!", "danger")
        return redirect(url_for("admin_offers"))

    # Ensure only one of product_id or pdetails_id is provided
    if product_id and pdetails_id:
        flash("Select either a product or a pdetails, not both!", "danger")
        return redirect(url_for("admin_offers"))

    # Insert offer
    cursor.execute("""
        INSERT INTO offers (product_id, pdetails_id, offer_percent)
        VALUES (%s, %s, %s)
    """, (product_id or None, pdetails_id or None, offer_percent))

    db.commit()
    cursor.close()

    flash("Offer added successfully ✅", "success")
    return redirect(url_for("admin_offers"))


# ===================== DELETE OFFER =====================
@app.route("/admin/offers/delete/<int:offer_id>", methods=["POST"])
@admin_login_required
def delete_offer(offer_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM offers WHERE id=%s", (offer_id,))
    db.commit()
    cursor.close()
    flash("Offer deleted successfully ✅", "success")
    return redirect(url_for("admin_offers"))

# ===================== UPDATE OFFER =====================
@app.route("/admin/offers/update/<int:offer_id>", methods=["POST"])
@admin_login_required
def update_offer(offer_id):
    offer_percent = request.form.get("offer_percent")
    if not offer_percent:
        flash("Offer percentage is required!", "danger")
        return redirect(url_for("admin_offers"))

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "UPDATE offers SET offer_percent=%s WHERE id=%s",
        (offer_percent, offer_id)
    )
    db.commit()
    cursor.close()
    flash("Offer updated successfully ✅", "success")
    return redirect(url_for("admin_offers"))

#admin profile

@app.route("/admin/profile", methods=["GET", "POST"])
def admin_profile():
    # Ensure admin is logged in
    if "admin_id" not in session or not session.get("admin_dashboard_access"):
        return redirect(url_for("admin_login"))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Fetch admin email only
    cursor.execute("SELECT id, email FROM admin WHERE id=%s", (session["admin_id"],))
    user = cursor.fetchone()  # user['email'] will be used in template

    if request.method == "POST":
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if password != confirm_password:
            flash("Passwords do not match", "danger")
        elif password.strip() == "":
            flash("Password cannot be empty", "danger")
        else:
            hashed_pw = generate_password_hash(password)
            cursor.execute(
                "UPDATE admin SET password=%s WHERE id=%s",
                (hashed_pw, session["admin_id"])
            )
            db.commit()
            flash("Password updated successfully", "success")

    cursor.close()
    db.close()

    return render_template("admin/profile.html", user=user)


#admin payment
@app.route("/admin/customer")
def admin_customer():
    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("""
        SELECT id, name, email, mobile, address, created_at 
        FROM customer
        ORDER BY id DESC
    """)

    customers = cur.fetchall()
    return render_template("admin/customer.html", customers=customers)




# ================== RUN ==================
if __name__ == "__main__":
    app.run(debug=True)









