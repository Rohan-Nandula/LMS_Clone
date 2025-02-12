from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from .db import db_connection

ta_endpoints = Blueprint('ta', __name__, template_folder='templates/TA_TEMPLATES')


#TA Login
@ta_endpoints.route('/ta_login', methods=['GET', 'POST'])
def ta_login():
    if request.method == 'POST':
        userId = request.form['userid']
        password = request.form['password']
        conn = db_connection()
        cursor = conn.cursor(dictionary=True)

        # Validate user credentials based on role
        query = "SELECT * FROM user WHERE userid=%s AND password=%s AND role='TA'"
        cursor.execute(query, (userId, password))
        user = cursor.fetchone()
        conn.close()

        if user and user['password'] == password:
            session['userid'] = user['userid']
            session['role'] = 'TA'
            session['name'] = user['firstName'] + ' ' + user['lastName']
            return redirect(url_for('ta.ta_dashboard'))
        else:
            flash('Invalid credentials. Please try again.', 'warning')

    return render_template('login.html', role='TA')


#TA Landing
@ta_endpoints.route('/ta_dashboard', methods=['GET', 'POST'])
def ta_dashboard():
    if 'role' in session and session['role'] == 'TA':
        if request.method == 'GET':
            return render_template('ta_dashboard.html')
    else:
        return redirect(url_for('home'))


#TA Active Course
@ta_endpoints.route('/active_course', methods=['GET', 'POST'])
def goto_active_course():
    if 'role' in session and session['role'] == 'TA':
        if request.method == 'POST':
            course_id = request.form['course_id']
            print(course_id)
            conn = db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM course WHERE id = %s", (course_id,))
            course = cursor.fetchone()
            conn.close()
            if not course:
                flash('Course not found. Please try again.', 'warning')
                return render_template('active_course.html')
            # Store course_id in session or pass it along
            session['course_id'] = course_id
            return redirect(url_for('ta.active_course_menu'))
        return render_template('active_course.html')
    else:
        return redirect(url_for('home'))


#TA Active Course Menu
@ta_endpoints.route('/active_course_menu', methods=['GET', 'POST'])
def active_course_menu():
    if 'userid' in session and 'role' in session and session['role'] == 'TA':
        return render_template('active_course_menu.html', course_id=session['course_id'])
    else:
        return redirect(url_for('home'))


#TA View Students
@ta_endpoints.route('/active_course/view_students', methods=['GET'])
def view_students():
    if 'role' in session and 'course_id' in session and session['role'] == 'TA':
        if request.method == 'GET':
            conn = db_connection()
            cursor = conn.cursor(dictionary=True)

            query = """
            SELECT u.userid, u.firstName, u.lastName, u.email
            FROM user u
            JOIN enrollment e ON u.userid = e.studentID
            WHERE e.courseId = %s AND e.status = 'Approved'
            """
            cursor.execute(query, (session['course_id'],))
            students = cursor.fetchall()
            conn.close()
            print(students)
            return render_template('view_students.html', students=students)
    else:
        return redirect(url_for('ta.active_course_menu'))


#TA add new chapter
@ta_endpoints.route('/active_course/add_chapter', methods=['GET', 'POST'])
def TA_add_chapter():
    if 'role' in session and session['role'] == 'TA':
        if 'course_id' not in session:
            return redirect(url_for('ta.ta_dashboard'))

        conn = db_connection()
        cursor = conn.cursor(dictionary=True)

        # Fetch textbookId associated with the active course
        query = """
            SELECT c.textbookId
            FROM course c
            JOIN teaches t ON c.id = t.course_id
            WHERE t.course_id=%s AND t.user_id = %s AND t.role = 'TA'
            """
        cursor.execute(query, (session['course_id'],session['userid']))
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result and result['textbookId']:
            etextbook_id = result['textbookId']
            return redirect(url_for('add_chapter', textbook_id=etextbook_id))
        else:
            flash('No textbook found for this course.', 'error')
            return redirect(url_for('ta.ta_dashboard'))
    else:
        return redirect(url_for('ta.goto_active_course'))

# Modify chapter
@ta_endpoints.route('/modify_chapter', methods=['GET', 'POST'])
def TA_modify_chapter():
    if 'role' in session and session['role'] == 'TA':
        if 'course_id' not in session:
            return redirect(url_for('ta.ta_dashboard'))

        conn = db_connection()
        cursor = conn.cursor()

        # Fetch textbookId associated with the active course
        query = """
            SELECT c.textbookId
            FROM course c
            JOIN teaches t ON c.id = t.course_id
            WHERE t.course_id=%s AND t.user_id = %s AND t.role = 'TA'
            """
        cursor.execute(query, (session['course_id'], session['userid']))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        print(result[0])
        if result:
            etextbook_id = result[0]
            return redirect(url_for('modify_chapter', textbook_id=etextbook_id))
        else:
            flash('No textbook found for this course.', 'error')
            return redirect(url_for('ta.ta_dashboard'))


#TA View course
@ta_endpoints.route('/view_course', methods=['GET', 'POST'])
def view_course():
    if 'role' in session and session['role'] == 'TA':
        if request.method == 'GET':
            conn = db_connection()
            cursor = conn.cursor(dictionary=True)

            query = """
            SELECT c.title
            FROM course c
            JOIN teaches t ON c.id = t.course_id
            WHERE t.user_id = %s AND t.role = 'TA'
            """
            cursor.execute(query, (session['userid'],))
            courses = cursor.fetchall()
            conn.close()

            return render_template('ta_view_courses.html', courses=courses)

        elif request.method == 'POST':
            choice = request.form.get('choice')
            if choice == '1':
                return redirect(url_for('ta.ta_dashboard'))
    else:
        return redirect(url_for('home'))


#TA Change password
@ta_endpoints.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'role' in session and session['role'] == 'TA':
        if request.method == 'GET':
            return render_template('ta_change_password.html')

        elif request.method == 'POST':
            old_password = request.form['old_password']
            new_password = request.form['new_password']
            confirm_password = request.form['confirm_password']

            if new_password != confirm_password:
                flash('New password and confirm password do not match.', 'info')
                return redirect(url_for('ta.change_password'))

            try:
                conn = db_connection()
                cursor = conn.cursor(dictionary=True)

                query = "SELECT * FROM user WHERE userid=%s AND password=%s"
                cursor.execute(query, (session['userid'], old_password))
                user = cursor.fetchone()

                if user:
                    update_query = "UPDATE user SET password=%s WHERE userid=%s"
                    cursor.execute(update_query, (new_password, session['userid']))
                    conn.commit()
                    flash('Password updated successfully.', 'success')
                    return redirect(url_for('ta.ta_dashboard'))
                else:
                    flash('Invalid old password. Please try again.', 'warning')
                    return redirect(url_for('ta.change_password'))
            except Exception as e:
                flash(f'An error occurred: {str(e)}', 'error')
                return redirect(url_for('ta.change_password'))
            finally:
                conn.close()
    else:
        return redirect(url_for('home'))
