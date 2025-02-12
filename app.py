from flask import flash, render_template, request, redirect, url_for, session, jsonify, Flask
import mysql.connector
from datetime import datetime
import re
from .ta_routes import ta_endpoints

from .db import db_connection

app = Flask(__name__)
app.config.from_pyfile('config.py')
app.register_blueprint(ta_endpoints, url_prefix='/ta')


# Home Page
@app.route('/')
def home():
    return render_template('home.html')


# Exit App
@app.route('/exit_app')
def exit_app():
    session.clear()  # Clear the session for the user
    return render_template('home.html')  # Show the exit page


# Admin Login
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        userid = request.form['userid']
        password = request.form['password']
        conn = db_connection()
        cursor = conn.cursor(dictionary=True)

        # Validate user credentials based on role
        query = "SELECT * FROM user WHERE userid=%s AND password=%s AND role='Admin'"
        cursor.execute(query, (userid, password))
        user = cursor.fetchone()
        conn.close()

        if user and user['password'] == password:
            session['userid'] = user['userid']
            session['role'] = 'Admin'
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials. Please try again.', 'danger')

    return render_template('login.html', role='Admin')


# Faculty Login
@app.route('/faculty_login', methods=['GET', 'POST'])
def faculty_login():
    if request.method == 'POST':
        userid = request.form['userid']
        password = request.form['password']
        conn = db_connection()
        cursor = conn.cursor(dictionary=True)

        # Validate user credentials based on role
        query = "SELECT * FROM user WHERE userid=%s AND password=%s AND role='Faculty'"
        cursor.execute(query, (userid, password))
        user = cursor.fetchone()
        conn.close()

        if user and user['password'] == password:
            session['userid'] = user['userid']
            session['role'] = 'Faculty'
            return redirect(url_for('faculty_dashboard'))
        else:
            flash('Invalid credentials. Please try again.', 'danger')

    return render_template('login.html', role='Faculty')

#Student - First Page
@app.route('/student_options')
def student_options():
    return render_template('student_options.html')
#Student - Enroll in a course
@app.route('/enroll_course',methods=['GET', 'POST'])
def enroll_course():
    if request.method == 'POST':
        first_name = request.form['firstName']
        last_name = request.form['lastName']
        email = request.form['email']
        course_token = request.form['courseToken']
        
        conn = db_connection()
        cursor = conn.cursor()
        #check if entered courseToken is valid
        cursor.execute("SELECT * FROM course WHERE courseToken = %s AND type = 'Active' ", (course_token,))
        course = cursor.fetchone()
        
        if course:
            print("COURSE EXISTS")
            course_id = course[0]
            course_capacity = course[6]
            #count number of students enrolled in that course
            cursor.execute("SELECT count(*) FROM enrollment WHERE courseId = %s AND status = 'Approved' ",(course_id,))
            course_enrollment_size = cursor.fetchone()[0]
            #check if course has available seats so that student can be enrolled
            if course_enrollment_size < course_capacity:
                print("COURSE HAS SEATS")
                #check if student exists
                cursor.execute("SELECT * FROM user WHERE email = %s",(email,))
                student = cursor.fetchone()
                
                if student is None:
                    print("CREATING NEW STUDENT")
                    print("creating new student")
                    add_new_student(first_name, last_name, email,cursor,conn)
                    print("Student account created before starting enrollment")
                    cursor.execute("SELECT * FROM user WHERE email = %s",(email,))
                    student = cursor.fetchone()
                check_and_create_enrollment(student[0],course_id,cursor,conn)
            else:
                print("Course capacity full. Enrollment Failed.")
                flash("Course capacity full. Enrollment Failed.", "error")
                return render_template('student_options.html')
        else:
            print("Course does not exist. The course token is invalid.")
            flash("Course does not exist. The course token is invalid.", "error")
            return render_template('student_options.html')
        conn.close()
        print("enroll function end-----")
        return render_template('student_options.html')
    return render_template('enroll_course.html')

#Student Login
@app.route('/student_login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        userid = request.form['userid']
        password = request.form['password']
        conn = db_connection()
        cursor = conn.cursor(dictionary=True)

        # Validate user credentials based on role
        query = "SELECT * FROM user WHERE userid=%s AND password=%s AND role='Student'"
        cursor.execute(query, (userid, password))
        user = cursor.fetchone()
        conn.close()

        if user and user['password'] == password:
            session['userid'] = user['userid']
            session['role'] = 'Student'
            return redirect(url_for('student_landing'))
        else:
            flash('Invalid credentials. Please try again.', 'danger')
            return render_template('login.html', role='Student')
    
    return render_template('login.html', role='Student')

def add_new_student(first_name, last_name, email,cursor,conn):
    student_id = generate_userid(first_name,last_name)
    try:
        query = "INSERT INTO user (userid, firstName, lastName, email, role) VALUES (%s, %s, %s, %s, 'Student')"
        cursor.execute(query, (student_id, first_name, last_name, email))
        conn.commit()
    except mysql.connector.IntegrityError as e:
                    conn.rollback()
                    if 'email' in str(e):
                        flash('Error: A student account with this email already exists.', 'danger')
                    elif 'PRIMARY' in str(e):
                        flash('Error: A student account with this user ID already exists.', 'danger')
                    else:
                        flash('Error: Could not create student account. Please try again.', 'danger')
                    conn.close()

def check_and_create_enrollment(student_id, course_id, cursor, conn):
    try:
        # Check if enrollment exists
        query = "SELECT * FROM enrollment WHERE studentID = %s AND courseId = %s"
        cursor.execute(query, (student_id, course_id))
        result = cursor.fetchone()
        
        if result is None:
            print(" Enrollment does not exist, create it")
            create_enrollment(student_id, course_id, cursor, conn)
            print("Enrollment successful in pending state. Waiting for Faculty approval")
            flash("Enrollment successful in pending state. Waiting for Faculty approval", "info")
        else:
            print("You are already enrolled in this course")
            flash("Enrollment failed, you are already enrolled in this course ", "info")
    except mysql.connector.Error as e:
        flash('Error: Could not check enrollment. Please try again.', 'danger')
        conn.rollback()
        conn.close()

def create_enrollment(student_id,course_id,cursor,conn):
    try:
        CURRENT_DATE = datetime.now().date()
        query = "INSERT INTO enrollment (studentID, courseId, requestDate, status) VALUES (%s, %s, CURRENT_DATE, 'Pending')"
        cursor.execute(query, (student_id, course_id))
        conn.commit()
    except mysql.connector.IntegrityError as e:
                    # Handle duplicate entry for email or userid
                    conn.rollback()
                    if 'PRIMARY' in str(e):
                        flash('Error: An enrollment for this student and course already exists.', 'danger')
                    else:
                        flash('Error: Could not create enrollment. Please try again.', 'danger')
                    conn.close()

#Student Landing Page
@app.route('/student_landing', methods=['GET'])
def student_landing():
    if 'userid' not in session or session.get('role') != 'Student':
        print("No Access")
        flash("Access denied. Please log in as a student to view this page.", "warning")
        return redirect(url_for('login.html'))

    user_id = session['userid']
    enrolled_courses_data = []

    try:
        conn = db_connection()
        cursor = conn.cursor(dictionary=True)

        # Get enrolled courses
        cursor.execute("SELECT * FROM course INNER JOIN enrollment ON course.id = enrollment.courseId WHERE enrollment.studentID = %s AND enrollment.status = 'Approved'", (user_id,))
        enrolled_courses = cursor.fetchall()
        
        
        for course in enrolled_courses:
            textbook_id = course['textbookId'] 
            cursor.execute("SELECT title FROM textbook WHERE id = %s AND hidden='No' ", (textbook_id,))
            ebook = cursor.fetchone()

            if ebook:
                course_data = {
                    "course_title": course['title'],
                    "textbook_title": ebook['title'],
                    "chapters": []
                }


                # Get chapters for the textbook
                cursor.execute("SELECT * FROM chapter WHERE textbook_id = %s AND hidden = 'No'", (textbook_id,))
                chapters = cursor.fetchall()

                for chapter in chapters:
                    chapter_data = {
                        "chapter_title": chapter['title'],
                        "sections": []
                    }

                    # Get sections for each chapter
                    cursor.execute("SELECT * FROM section WHERE chapterNumber = %s AND textbook_id = %s AND hidden = 'No'", (chapter['chapterNumber'], textbook_id))
                    sections = cursor.fetchall()

                    for section in sections:
                        section_data = {
                            "section_title": section['title'],
                            "content_blocks": []
                        }

                        # Get content blocks for each section
                        cursor.execute("""
                            SELECT * FROM content_block 
                            WHERE sectionNumber = %s AND chapterNumber = %s AND textbook_id = %s AND hidden = 'No'
                        """, (section['sectionNumber'], chapter['chapterNumber'], textbook_id))
                        content_blocks = cursor.fetchall()

                        for content_block in content_blocks:
                            cursor.execute("""
                                SELECT activityId FROM activity 
                            WHERE sectionNumber = %s AND chapterNumber = %s AND textbook_id = %s AND content_block_id= %s
                            """, (section['sectionNumber'], section['chapterNumber'], section['textbook_id'],content_block['id'],))
                            activity = cursor.fetchone()

                            if activity is not None:
                                content_block['content']=activity['activityId']
                            section_data["content_blocks"].append(content_block)


                        chapter_data["sections"].append(section_data)

                    course_data["chapters"].append(chapter_data)

                enrolled_courses_data.append(course_data)

        conn.close()
    except Exception as e:
        flash("An error occurred while retrieving data.", "danger")
        print(e)

    return render_template('student_landing.html', enrolled_courses=enrolled_courses_data)

#View Section
@app.route('/section', methods=['GET'])
def section():
    if 'userid' not in session or session.get('role') != 'Student':
        print("No Access")
        flash("Access denied. Please log in as a student to view this page.", "warning")
        return render_template('login.html', role='Student')
    return render_template('view_section.html')

@app.route('/view_block',methods=['GET','POST'])
def view_block():
    if 'userid' not in session or session.get('role') != 'Student':
        print("No Access")
        flash("Access denied. Please log in as a student to view this page.", "warning")
        return render_template('login.html', role='Student')
    if request.method == 'POST':
        courseId = request.form['courseId']
        chapterId = request.form['chapterId']
        sectionId = request.form['sectionId']
        user_id = session['userid']

        try:
            conn = db_connection()
            cursor = conn.cursor(dictionary=True)
            session['courseId']=courseId

            # get the enrolled course by the student
            cursor.execute("select * from enrollment where courseId=%s and studentID=%s and status = 'Approved'", (courseId,user_id,))
            enrolled_course = cursor.fetchone()
            course_selected = None
            section_selected = None
            #get the textbook corresponding to the course
            cursor.execute("select textbookId from course where id=%s", (courseId,))
            course_textbook = cursor.fetchone()

            if enrolled_course:
                textbook_id = course_textbook['textbookId']
                cursor.execute("SELECT * FROM chapter WHERE chapterNumber = %s AND textbook_id = %s", (chapterId,textbook_id,))
                chapter = cursor.fetchone()
                
                if chapter is not None and chapter.get('hidden') == 'No':
                    cursor.execute("SELECT * FROM section WHERE sectionNumber = %s AND chapterNumber = %s AND textbook_id = %s", (sectionId,chapterId,textbook_id,))
                    section = cursor.fetchone()

                    if section is not None and section.get('hidden') == 'No':
                        course_selected = enrolled_course
                        section_selected = section
                        
            else:
                print("Not enrolled in this course or Course not found")
                flash("Not enrolled in this course or Course not found", "danger")
                conn.close()
                return render_template('view_section.html')
                        

            if course_selected is not None and section_selected is not None:
                print("------VIEW BLOCK--------")
                try:
                    content_to_display = None
                    cursor.execute("""
                        SELECT * FROM content_block 
                        WHERE sectionNumber = %s AND chapterNumber = %s AND textbook_id = %s ORDER BY id
                    """, (section_selected['sectionNumber'], section_selected['chapterNumber'], section_selected['textbook_id'],))
                    content_blocks = cursor.fetchall()

                    # Initialize current_block_index from the session
                    session['current_block_index']=0
                    while session['current_block_index'] < len(content_blocks):
                        if session['current_block_index'] >= len(content_blocks):
                            print("You have reached the end of this section,going to landing page")
                            return redirect(url_for('student_landing'))

                        current_block = content_blocks[session['current_block_index']]

                        # Skip hidden content blocks
                        if current_block.get('hidden') == 'Yes':
                            print("skipping hidden block")
                            session['current_block_index'] += 1
                            print("session:increment: ",session['current_block_index'])
                            continue

                        # using section get the activity
                        cursor.execute("""
                            SELECT * FROM activity 
                            WHERE sectionNumber = %s AND chapterNumber = %s AND textbook_id = %s AND content_block_id= %s
                        """, (section_selected['sectionNumber'], section_selected['chapterNumber'], section_selected['textbook_id'],current_block['id'],))
                        activity = cursor.fetchone()

                        session['section_selected'] = section_selected
                        
                        if activity is None:
                            # Append content block data
                            content_to_display = {
                                'type': current_block['type'],
                                'content': current_block['content']
                            }
                            
                            # Increment index for next access
                            session['current_block_index'] += 1
                            print("session:increment: ",session['current_block_index'])
                            session['content_to_display'] = content_to_display
                            
                            return render_template('view_block.html', content_to_display=content_to_display)
                        else:
                            activity_content_block = activity
                            session['current_block_index'] += 1
                            
                            print("Working on Activity")
                            cursor.execute("""
                            select * from question where content_block_id=%s and textbook_id=%s and chapterNumber=%s and sectionNumber=%s and activityId=%s;
                            """, (activity['content_block_id'],activity['textbook_id'],activity['chapterNumber'],activity['sectionNumber'],activity['activityId'],))
                            questions = cursor.fetchall()

                            session['questions'] = questions
                            session['current_question_index'] = 0
                            session['activity_score'] = 0
                            session['activityId'] = activity['activityId']

                            #call to display all question and answer respt.
                            return redirect(url_for('activity_view'))

                    if session['current_block_index'] >= len(content_blocks):
                        print("You have reached the end of this section,No more content blocks")
                        flash("You have reached the end of this section,No more content blocks", "danger")
                        return redirect(url_for('student_landing'))
                except Exception as e:
                    flash("An error while viewing block.", "danger")
                    print(e)
            else:
                print("Section not accessible or section not present")
                flash("Section not accessible or section not present", "danger")
            conn.close()
        except Exception as e:
            flash("An error occurred while retrieving data.", "danger")
            print(e)
    print("done done done")
    return render_template('view_section.html')


@app.route('/activity_view', methods=['GET','POST'])
def activity_view():
    try:
        print("Entering activity view")
        questions = session['questions']
        course_id = session['courseId']


        if not questions:
            print("No questions in activity")
            return redirect(url_for('view_next_block'))
    
        current_index = session['current_question_index']
        conn = db_connection()
        cursor = conn.cursor(dictionary=True)

        if current_index < len(questions):
            question = questions[current_index]
            
            cursor.execute("""
                        SELECT * FROM answer_set where content_block_id=%s and textbook_id=%s and chapterNumber=%s 
                        and sectionNumber=%s and activityId=%s and questionId=%s 
                        """, (question['content_block_id'],question['textbook_id'],question['chapterNumber'],question['sectionNumber'],question['activityId'],question['questionId'],))
            answer_options = cursor.fetchall()

            for option in answer_options:
                if option['isCorrect'] == 1:
                    correct_answer_id = option['answerId']
                    break

            if request.method == 'POST':
                score = 0
                # Store the user's answer choice
                selected_answer = request.form.get('answer')

                cursor.execute("""
                        SELECT * FROM answer_set where content_block_id=%s and textbook_id=%s and chapterNumber=%s 
                        and sectionNumber=%s and activityId=%s and questionId=%s and answerId=%s
                        """, (question['content_block_id'],question['textbook_id'],question['chapterNumber'],question['sectionNumber'],question['activityId'],question['questionId'], selected_answer))
                selected_option = cursor.fetchone()

                if int(selected_answer) == correct_answer_id:
                    print("Correct answer")
                    flash(option['explanation'],"success")
                    flash("Received 3 points for correct answer","success")
                    score = 3
                else:
                    print("Incorrect answerrrr")
                    #TODO Need to display the correct explanation here
                    flash(selected_option['explanation'],"danger")
                    flash("Received 1 points for attempt","danger")
                    score = 1

                cursor.execute("""
                               SELECT * FROM student_progress WHERE studentID=%s AND activityId=%s AND questionId=%s AND course_id=%s
                               """,(session['userid'],question['activityId'],question['questionId'],course_id,))
                student_progress = cursor.fetchone()


                if student_progress:
                    if student_progress['completion_status']=='Yes':
                        print("Reattempting activity")
                        update_query = """
                                UPDATE student_progress 
                                SET point = %s, completion_status = 'No' 
                                WHERE studentID = %s AND activityId = %s AND questionId=%s AND course_id=%s
                            """
                        cursor.execute(update_query, (0, session['userid'], question['activityId'],question['questionId'],course_id))
                        conn.commit()

                    
                    #getting the updated record
                    cursor.execute("""
                               SELECT * FROM student_progress WHERE studentID=%s AND activityId=%s AND questionId=%s AND course_id=%s
                               """,(session['userid'],question['activityId'],question['questionId'],course_id,))
                    student_progress = cursor.fetchone()

                    update_query = """
                                UPDATE student_progress 
                                SET point = %s, completion_status = 'Yes', timestamp = CURRENT_TIMESTAMP
                                WHERE studentID = %s AND activityId = %s AND questionId=%s AND course_id=%s
                            """
                    cursor.execute(update_query, (score, session['userid'], question['activityId'], question['questionId'],course_id,))
                    conn.commit()
                else:
                    query = "INSERT INTO student_progress (studentID, course_id, questionId, activityId, content_block_id, sectionNumber, chapterNumber, textbook_id, point, completion_status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,%s)"
                    cursor.execute(query, (session['userid'], course_id, question['questionId'], question['activityId'], question['content_block_id'], question['sectionNumber'], question['chapterNumber'],question['textbook_id'],score,'Yes'))
                    conn.commit()
                # Move to the next question
                session['current_question_index'] = current_index + 1
                return redirect(url_for('activity_view'))
            conn.close()
            return render_template('view_activity.html', question=question, answer_options=answer_options)
        else:
            # All questions have been answered, redirect to next block
            #should have marked the all questions in activity of student_progress as completed
            flash("You have completed the activity.", "success")
            conn.close()
            

            return redirect(url_for('view_next_block'))
    except Exception as e:
            flash("An error occurred while retrieving data in activity view.", "danger")
            print(e)
            return redirect(url_for('student_landing'))


@app.route('/view_next_block', methods=['GET', 'POST'])
def view_next_block():
    try:
        print("Enter VIEW_NEXT_BLOCK")
        conn = db_connection()
        cursor = conn.cursor(dictionary=True)
        section_selected = session['section_selected']
        cursor.execute("""
                        SELECT * FROM content_block 
                        WHERE sectionNumber = %s AND chapterNumber = %s AND textbook_id = %s ORDER BY id
                    """, (section_selected['sectionNumber'], section_selected['chapterNumber'], section_selected['textbook_id']))
        content_blocks = cursor.fetchall()
        while session['current_block_index'] < len(content_blocks):
                if session['current_block_index'] >= len(content_blocks):
                    print("You have reached the end of this section,going to landing page")
                    return redirect(url_for('student_landing'))

                current_block = content_blocks[session['current_block_index']]

                # Skip hidden content blocks
                if current_block.get('hidden') == 'Yes':
                    print("skipping hidden block")
                    session['current_block_index'] += 1
                    print("session:increment: ",session['current_block_index'])
                    continue

                # using section get the activities
                cursor.execute("""
                            SELECT * FROM activity 
                            WHERE sectionNumber = %s AND chapterNumber = %s AND textbook_id = %s AND content_block_id= %s
                        """, (section_selected['sectionNumber'], section_selected['chapterNumber'], section_selected['textbook_id'],current_block['id'],))
                activity = cursor.fetchone()
                        
                if activity is None:
                    # Append content block data
                    content_to_display = {
                            'type': current_block['type'],
                            'content': current_block['content']
                    }
                    # Increment index for next access
                    session['current_block_index'] += 1
                    print("session:increment: ",session['current_block_index'])
                    return render_template('view_block.html', content_to_display=content_to_display)
                else:
                    activity_content_block = activity
                    session['current_block_index'] += 1
                    print("session:increment: ",session['current_block_index'])
                            
                    print("Working on Activity")
                    cursor.execute("""
                            select * from question where content_block_id=%s and textbook_id=%s and chapterNumber=%s and sectionNumber=%s and activityId=%s;
                            """, (activity['content_block_id'],activity['textbook_id'],activity['chapterNumber'],activity['sectionNumber'],activity['activityId'],))
                    questions = cursor.fetchall()

                    print("caller - questions")
                    print(questions)
                    session['questions'] = questions
                    session['current_question_index'] = 0
                    session['activity_score'] = 0
                    session['activityId'] = activity['activityId']

                    #call to display all question and answer respt.
                    return redirect(url_for('activity_view'))
                
        print("printing session to check current_block_index")
        print(session)
                
        if session['current_block_index'] >= len(content_blocks):
                    print("You have reached the end of this section,going to landing page")
                    flash("Reached End of Section","info")
                    return redirect(url_for('student_landing'))
    except Exception as e:
            print("An error occurred view next block.")
            flash("An error occurred view next block.", "danger")
            print(e)
    return render_template('view_section.html')


@app.route('/participation_point', methods=['GET'])
def participation_point():
    if 'userid' not in session or session.get('role') != 'Student':
        print("No Access")
        flash("Access denied. Please log in as a student to view this page.", "warning")
        return render_template('login.html', role='Student')
    try:
        conn = db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
                        SELECT sp.studentID, sp.course_id AS course_id, SUM(sp.point) AS total_points_earned,
                            COUNT(*) * 3 AS total_points,
                            COUNT(DISTINCT CASE WHEN sp.completion_status = 'Yes' THEN sp.activityId END) 
                            AS num_of_finished_activities
                        FROM 
                            student_progress sp
                        WHERE 
                            sp.studentID = %s
                        GROUP BY 
                            sp.studentID, sp.course_id
                       """,(session['userid'],))
        result = cursor.fetchall()
        conn.close()
        return render_template('view_participation_points.html', result = result)
    except Exception as e:
        print("An error occurred in participation_point.")
        flash("An error occurred in participation_point.", "danger")
        print(e)
        return redirect(url_for('student_landing'))

    

@app.route('/view_notification', methods=['GET', 'POST'])
def view_notification():
    print("Enter NOTIFICATION")
    user_id = session['userid']  

    try:
        print()
        conn = db_connection()
        cursor = conn.cursor(dictionary=True)
    
        if request.method == 'POST':
            # Get selected notification ID from form submission
            notification_id = request.form['notification_id']

            # Update isRead status to 1 for the selected notification
            cursor.execute("""
            UPDATE notification SET isRead = 1 WHERE id = %s AND userId = %s
                           """,(notification_id, user_id))
            conn.commit()

            cursor.execute("""
            DELETE FROM notification WHERE isRead = 1 AND id = %s AND userId = %s
                           """, (notification_id, user_id))
            conn.commit()

            conn.close()
        
            return redirect(url_for('view_notification'))

        # Fetch notifications for the user where isRead = 0 (unread)
        cursor.execute("""
        SELECT * FROM notification WHERE userId = %s AND isRead = 0
        """,(user_id,))
        notifications = cursor.fetchall()
        conn.close()
    
        # Render the template with the list of unread notifications
        return render_template('view_notification.html', notifications=notifications)
    except Exception as e:
        print("An error occurred in fetching notifications.")
        flash("An error occurred in fetching notifications.", "danger")
        print(e)
        return redirect(url_for('student_landing'))

#Admin Landing
@app.route('/admin_dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if 'role' in session and session['role'] == 'Admin':
        if request.method == 'POST':
            choice = request.form.get('choice')

            # Redirect to the appropriate page based on the choice
            if choice == '1':
                return redirect(url_for('create_faculty_account'))
            elif choice == '2':
                return redirect(url_for('create_etextbook'))
            elif choice == '3':
                return redirect(url_for('modify_etextbooks'))
            elif choice == '4':
                return redirect(url_for('create_active_course'))
            elif choice == '5':
                return redirect(url_for('create_evaluation_course'))
            elif choice == '6':
                return redirect(url_for('exit_app'))

        return render_template('admin_dashboard.html')
    else:
        return redirect(url_for('home'))


# Generate Userid
def generate_userid(first_name, last_name):
    # Get first two letters of first name and last name
    first_part = first_name[:2].capitalize()
    last_part = last_name[:2].capitalize()

    # Get the current date (for the account creation date)
    now = datetime.now()
    month = now.strftime("%m")  # Two-digit month
    year = now.strftime("%y")  # Two-digit year

    # Form the unique user ID
    userid = f"{first_part}{last_part}{month}{year}"

    return userid


# Create Faculty Account
@app.route('/create_faculty_account', methods=['GET', 'POST'])
def create_faculty_account():
    if 'role' in session and session['role'] == 'Admin':
        if request.method == 'POST':
            # Getting user inputs from form
            first_name = request.form['first_name']
            last_name = request.form['last_name']
            email = request.form['email']
            password = request.form['password']
            choice = request.form.get('choice')

            if choice == '1':  # If the user selects 'Add User'
                conn = db_connection()
                cursor = conn.cursor()

                # Generate a unique user ID based on the provided first and last name
                userid = generate_userid(first_name, last_name)

                try:
                    # Inserting the new faculty user into the database
                    query = "INSERT INTO user (userid, firstName, lastName, email, password, role) VALUES (%s, %s, %s, %s, %s, 'Faculty')"
                    cursor.execute(query, (userid, first_name, last_name, email, password))
                    conn.commit()
                    conn.close()

                    flash('Faculty account created successfully!', 'success')
                    return redirect(url_for('admin_dashboard'))  # Go back to admin landing page
                except mysql.connector.IntegrityError as e:
                    # Handle duplicate entry for email or userid
                    conn.rollback()
                    if 'email' in str(e):
                        flash('Error: A faculty account with this email already exists.', 'danger')
                    elif 'PRIMARY' in str(e):
                        flash('Error: A faculty account with this user ID already exists.', 'danger')
                    else:
                        flash('Error: Could not create faculty account. Please try again.', 'danger')
                    conn.close()

        return render_template('create_faculty_account.html')
    else:
        return redirect(url_for('home'))


# Create E-Textbook
@app.route('/create_etextbook', methods=['GET', 'POST'])
def create_etextbook():
    if 'role' in session and session['role'] == 'Admin':
        if request.method == 'POST':
            title = request.form['title']
            etextbook_id = request.form['etextbook_id']
            choice = request.form.get('choice')

            if choice == '1':  # Add new chapter
                # Save the new e-textbook to the database
                conn = db_connection()
                cursor = conn.cursor()
                try:
                    query = "INSERT INTO textbook (id, title) VALUES (%s, %s)"
                    cursor.execute(query, (etextbook_id, title))
                    conn.commit()
                    conn.close()

                    flash('E-textbook created successfully! Now add chapters.', 'success')
                    return redirect(url_for('add_chapter', textbook_id=etextbook_id))
                except mysql.connector.IntegrityError as e:
                    conn.rollback()
                    if 'PRIMARY' in str(e):
                        flash('Error: An e-textbook with this ID already exists.', 'danger')
                    else:
                        flash('Error: Could not create e-textbook. Please try again.', 'danger')
                    conn.close()


        return render_template('create_etextbook.html')
    else:
        return redirect(url_for('home'))


# ------------------------------------------------- ADD NEW CHAPTER FLOW -------------------------------------------------
# Add New Chapter
@app.route('/<int:textbook_id>/add_chapter', methods=['GET', 'POST'])
def add_chapter(textbook_id):
    if 'role' in session and session['role'] in ('Admin', 'Faculty', 'TA'):
        if request.method == 'POST':
            chapter_number = request.form['chapter_number']
            chapter_title = request.form['chapter_title']
            choice = request.form.get('choice')

            if not re.match(r'^chap\d{2}$', chapter_number):
                flash('Error: Chapter number must start with "chap" followed by two digits (e.g., "chap01").', 'danger')
                return render_template('add_chapter.html', textbook_id=textbook_id, role=session['role'])

            if choice == '1':  # Add new section
                # Save the new chapter to the database
                conn = db_connection()
                cursor = conn.cursor()

                try:
                    query = "INSERT INTO chapter (chapterNumber, title, textbook_id, createdBy) VALUES (%s, %s, %s, %s)"
                    cursor.execute(query, (chapter_number, chapter_title, textbook_id, session['userid']))
                    conn.commit()
                    conn.close()
                    flash('Chapter added successfully! Now add sections.', 'success')
                    return redirect(url_for('add_section', chapter_number=chapter_number, textbook_id=textbook_id,
                                            role=session['role']))
                except mysql.connector.IntegrityError as e:
                    conn.rollback()
                    if 'PRIMARY' in str(e):
                        flash('Error: A chapter with this number already exists in this textbook.', 'danger')
                    else:
                        flash('Error: Could not add chapter. Please try again.', 'danger')
                    conn.close()

        return render_template('add_chapter.html', textbook_id=textbook_id, role=session['role'])
    else:
        return redirect(url_for('home'))


# Admin - 3 - Modify Textbook
@app.route('/modify_etextbooks', methods=['GET', 'POST'])
def modify_etextbooks():
    if 'role' in session and session['role'] == 'Admin':
        if request.method == 'POST':
            etextbook_id = request.form['etextbook_id']
            choice = request.form.get('choice')

            # Ensure that the e-textbook exists
            conn = db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM textbook WHERE id = %s", (etextbook_id,))
            etextbook = cursor.fetchone()
            conn.close()

            if not etextbook:
                flash("Error: E-textbook not found. Please enter a valid ID.", 'danger')
                return render_template('modify_etextbook.html')

            if choice == '1':  # Add new chapter
                return redirect(url_for('add_chapter', textbook_id=etextbook_id))
            elif choice == '2':  # Modify existing chapter
                return redirect(url_for('modify_chapter_admin', textbook_id=etextbook_id))

        return render_template('modify_etextbook.html')
    else:
        return redirect(url_for('home'))


# Admin - 3 - Add Section
@app.route('/<int:textbook_id>/<string:chapter_number>/add_section', methods=['GET', 'POST'])
def add_section(textbook_id, chapter_number):
    if 'role' in session and session['role'] in ('Admin', 'Faculty', 'TA'):
        if request.method == 'POST':
            section_number = request.form['section_number']
            section_title = request.form['section_title']
            choice = request.form.get('choice')

            if choice == '1':  # Add new content block
                conn = db_connection()
                cursor = conn.cursor()

                # Insert the new section into the database
                try:
                    query = "INSERT INTO section (sectionNumber, title, chapterNumber, textbook_id, createdBy) VALUES (%s, %s, %s, %s, %s)"
                    cursor.execute(query,
                                   (section_number, section_title, chapter_number, textbook_id, session['userid']))
                    conn.commit()
                    conn.close()

                    flash('Section added successfully! Now add content blocks.', 'success')
                    return redirect(
                        url_for('add_content_block', chapter_number=chapter_number, section_number=section_number,
                                textbook_id=textbook_id))
                except mysql.connector.IntegrityError as e:
                    conn.rollback()
                    if e.errno == 1062:  # MySQL duplicate entry error code
                        flash('Error: A section with this number already exists.', 'danger')
                    else:
                        flash('Error: Could not add section. Please try again.', 'danger')
                finally:
                    conn.close()
        return render_template('add_section.html', textbook_id=textbook_id, chapter_number=chapter_number,
                               role=session['role'])
    else:
        return redirect(url_for('home'))


# New Content Block
@app.route('/<textbook_id>/<chapter_number>/<section_number>/add_content_block', methods=['GET', 'POST'])
def add_content_block(chapter_number, section_number, textbook_id):
    if 'role' in session and session['role'] in ('Admin', 'Faculty', 'TA'):
        if request.method == 'POST':
            content_block_id = request.form['content_block_id']
            option = request.form['option']

            conn = db_connection()
            cursor = conn.cursor()

            # Check if the content block ID already exists
            query = "SELECT id FROM content_block WHERE id = %s AND sectionNumber = %s AND chapterNumber = %s AND textbook_id = %s"
            cursor.execute(query, (content_block_id, section_number, chapter_number, textbook_id))
            existing_block = cursor.fetchone()

            if existing_block:
                # Content block exists: allow associating it with an activity directly
                if option == '3':  # Add Activity
                    flash(f"Content block with ID {content_block_id} exists, proceeding to add activity.", "info")
                    return redirect(url_for('add_activity', content_block_id=content_block_id, section_number=section_number, chapter_number=chapter_number, textbook_id=textbook_id))
                elif option == '1':  # Add Text
                    flash(f"Content block with ID {content_block_id} exists, proceeding to modify text.", "info")
                    return redirect(url_for('add_text', content_block_id=content_block_id, section_number=section_number, chapter_number=chapter_number, textbook_id=textbook_id))
                elif option == '2':  # Add Picture
                    flash(f"Content block with ID {content_block_id} exists, proceeding to modify picture.", "info")
                    return redirect(url_for('add_picture', content_block_id=content_block_id, section_number=section_number, chapter_number=chapter_number, textbook_id=textbook_id))

            # If not exists, allow adding a new content block (Text or Image)
            if option == '1':  # Add Text
                return redirect(url_for('add_text', content_block_id=content_block_id, section_number=section_number, chapter_number=chapter_number, textbook_id=textbook_id))
            elif option == '2':  # Add Picture
                return redirect(url_for('add_picture', content_block_id=content_block_id, section_number=section_number, chapter_number=chapter_number, textbook_id=textbook_id))
            elif option == '3':
                flash('Error: Please create a content_block with text/picture', 'danger')
                return redirect(url_for('add_content_block', textbook_id=textbook_id, chapter_number=chapter_number, section_number=section_number))

        return render_template('add_content_block.html', textbook_id=textbook_id, chapter_number=chapter_number, section_number=section_number)
    else:
        return redirect(url_for('home'))


@app.route('/<int:textbook_id>/<string:chapter_number>/<string:section_number>/<content_block_id>/add_text',
           methods=['GET', 'POST'])
def add_text(textbook_id, chapter_number, section_number, content_block_id):
    if 'role' in session and session['role'] in ('Admin', 'Faculty', 'TA'):
        conn = db_connection()
        cursor = conn.cursor(dictionary=True)

        # Check if the content block already exists
        query = "SELECT * FROM content_block WHERE id = %s AND sectionNumber = %s AND chapterNumber = %s AND textbook_id = %s"
        cursor.execute(query, (content_block_id, section_number, chapter_number, textbook_id))
        content_block = cursor.fetchone()

        if request.method == 'POST':
            content_text = request.form['content_text']
            choice = request.form.get('choice')
            created_by = session.get('userid', 'JoDo1024')  # Defaulting to 'JoDo1024' if no user ID is in session

            if content_block:  # Content block exists, proceed to modify
                if choice == '1':  # Modify the existing content
                    try:
                        update_query = """
                        UPDATE content_block 
                        SET content = %s, type = 'Text'
                        WHERE id = %s AND sectionNumber = %s AND chapterNumber = %s AND textbook_id = %s
                        """
                        cursor.execute(update_query, (content_text, content_block_id, section_number, chapter_number, textbook_id))
                        conn.commit()
                        flash('Text content modified successfully!', 'success')
                    except mysql.connector.IntegrityError:
                        flash('Error: Could not modify text content.', 'danger')
                else:
                    flash('Modification cancelled.', 'info')

            else:  # Content block doesn't exist, proceed to add
                if choice == '1':  # Add new content
                    try:
                        insert_query = """
                        INSERT INTO content_block (id, content, type, sectionNumber, chapterNumber, textbook_id, createdBy)
                        VALUES (%s, %s, 'Text', %s, %s, %s, %s)
                        """
                        cursor.execute(insert_query, (content_block_id, content_text, section_number, chapter_number, textbook_id, created_by))
                        conn.commit()
                        flash('Text content added successfully!', 'success')
                    except mysql.connector.IntegrityError:
                        flash('Error: Could not add text content.', 'danger')

            conn.close()
            return redirect(url_for('add_content_block', section_number=section_number, chapter_number=chapter_number, textbook_id=textbook_id))

        return render_template('add_text.html', content_block=content_block, content_block_id=content_block_id, section_number=section_number, chapter_number=chapter_number, textbook_id=textbook_id)
    else:
        return redirect(url_for('home'))


@app.route('/<int:textbook_id>/<string:chapter_number>/<string:section_number>/<content_block_id>/add_picture',
           methods=['GET', 'POST'])
def add_picture(textbook_id, chapter_number, section_number, content_block_id):
    if 'role' in session and session['role'] in ('Admin', 'Faculty', 'TA'):
        conn = db_connection()
        cursor = conn.cursor(dictionary=True)

        # Check if the content block already exists
        query = "SELECT * FROM content_block WHERE id = %s AND sectionNumber = %s AND chapterNumber = %s AND textbook_id = %s"
        cursor.execute(query, (content_block_id, section_number, chapter_number, textbook_id))
        content_block = cursor.fetchone()

        if request.method == 'POST':
            picture_url = request.form['picture_url']
            choice = request.form.get('choice')
            created_by = session.get('userid', 'JoDo1024')  # Defaulting to 'JoDo1024' if no user ID is in session

            if content_block:  # Content block exists, proceed to modify
                if choice == '1':  # Modify the existing content
                    try:
                        update_query = """
                        UPDATE content_block 
                        SET content = %s, type = 'Image'
                        WHERE id = %s AND sectionNumber = %s AND chapterNumber = %s AND textbook_id = %s
                        """
                        cursor.execute(update_query, (picture_url, content_block_id, section_number, chapter_number, textbook_id))
                        conn.commit()
                        flash('Picture modified successfully!', 'success')
                    except mysql.connector.IntegrityError:
                        flash('Error: Could not modify picture.', 'danger')
                else:
                    flash('Modification cancelled.', 'info')

            else:  # Content block doesn't exist, proceed to add
                if choice == '1':  # Add new picture
                    try:
                        insert_query = """
                        INSERT INTO content_block (id, content, type, sectionNumber, chapterNumber, textbook_id, createdBy)
                        VALUES (%s, %s, 'Image', %s, %s, %s, %s)
                        """
                        cursor.execute(insert_query, (content_block_id, picture_url, section_number, chapter_number, textbook_id, created_by))
                        conn.commit()
                        flash('Picture added successfully!', 'success')
                    except mysql.connector.IntegrityError:
                        flash('Error: Could not add picture.', 'danger')

            conn.close()
            return redirect(url_for('add_content_block', section_number=section_number, chapter_number=chapter_number, textbook_id=textbook_id))

        return render_template('add_picture.html', content_block=content_block, content_block_id=content_block_id, section_number=section_number, chapter_number=chapter_number, textbook_id=textbook_id)
    else:
        return redirect(url_for('home'))


@app.route('/<int:textbook_id>/<string:chapter_number>/<string:section_number>/<content_block_id>/add_activity',
           methods=['GET', 'POST'])
def add_activity(textbook_id, chapter_number, section_number, content_block_id):
    if 'role' in session and session['role'] in ('Admin', 'Faculty', 'TA'):
        conn = db_connection()
        cursor = conn.cursor(dictionary=True)

        if request.method == 'POST':
            try:
            # Check if the content block already exists
                query = "SELECT * FROM content_block WHERE id = %s AND sectionNumber = %s AND chapterNumber = %s AND textbook_id = %s"
                cursor.execute(query, (content_block_id, section_number, chapter_number, textbook_id))
                content_block = cursor.fetchone()

                # Check if the content block already has an activity, get the all the activity ids
                print(textbook_id, chapter_number, section_number, content_block_id)
                activity_query = "SELECT activityId FROM activity WHERE content_block_id = %s AND sectionNumber = %s AND chapterNumber = %s and textbook_id = %s"
                cursor.execute(activity_query, (content_block_id, section_number, chapter_number, textbook_id))
                existing_activity = cursor.fetchone()
                print(existing_activity)
            except:
                content_block = None
                existing_activity = None
        
            activity_id = request.form['activity_id']
            choice = request.form.get('choice')
            created_by = session.get('userid', 'JoDo1024')  # Defaulting to 'JoDo1024' if no user ID is in session
            
            if content_block:  # Content block exists, check if any activity exists, if so get the latest activity id
                if choice == '1' and existing_activity == None:
                    flash('No activity exists for this content block. Adding a new activity for this content_block.', 'info')
                    try:
                        insert_query = """
                        INSERT INTO activity (activityId, sectionNumber, chapterNumber, textbook_id, content_block_id, createdBy) 
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """
                        cursor.execute(insert_query, (activity_id, section_number, chapter_number, textbook_id, content_block_id, created_by))
                        conn.commit()
                        flash('Activity created successfully! Now add a question.', 'success')
                        return redirect(url_for('add_question', textbook_id=textbook_id, chapter_number=chapter_number, section_number=section_number, content_block_id=content_block_id, activity_id=activity_id))
                    except mysql.connector.IntegrityError as e:
                        conn.rollback()
                        flash('Error: Could not create activity. Please try again.', 'danger')
                        conn.close()
                elif choice=="1" and activity_id == existing_activity['activityId']:
                    flash(f'This activity already exists for this content block. Please add a new question to this activity.', 'success')
                    return redirect(url_for('add_question', textbook_id=textbook_id, chapter_number=chapter_number, section_number=section_number, content_block_id=content_block_id, activity_id=activity_id))
                elif choice == '1' and activity_id != existing_activity['activityId']:
                    flash(f'Another activity already exists for this content block. Please add a new content_block to add this new activity.', 'danger')
                    return redirect(url_for('add_content_block', section_number=section_number, chapter_number=chapter_number, textbook_id=textbook_id))
            else:  # Content block doesn't exist, proceed to add
                flash('Error: Content block does not exist. Please add a content block first.', 'danger')
                return redirect(url_for('add_content_block', section_number=section_number, chapter_number=chapter_number, textbook_id=textbook_id))

        return render_template('add_activity.html', content_block_id=content_block_id, section_number=section_number, chapter_number=chapter_number, textbook_id=textbook_id)
    else:
        return redirect(url_for('home'))

@app.route(
    '/<int:textbook_id>/<string:chapter_number>/<string:section_number>/<content_block_id>/<activity_id>/add_question',
    methods=['GET', 'POST'])
def add_question(textbook_id, chapter_number, section_number, content_block_id, activity_id):
    if 'role' in session and session['role'] in ('Admin', 'Faculty', 'TA'):
        conn = db_connection()
        cursor = conn.cursor(dictionary=True)

        if request.method == 'POST':
            # Retrieve question and options details from the form
            question_text = request.form['question_text']
            question_id = request.form['question_id']

            options = [
                {
                    "text": request.form['option1_text'],
                    "explanation": request.form['option1_explanation'],
                    "is_correct": request.form['option1_label'] == 'Correct'
                },
                {
                    "text": request.form['option2_text'],
                    "explanation": request.form['option2_explanation'],
                    "is_correct": request.form['option2_label'] == 'Correct'
                },
                {
                    "text": request.form['option3_text'],
                    "explanation": request.form['option3_explanation'],
                    "is_correct": request.form['option3_label'] == 'Correct'
                },
                {
                    "text": request.form['option4_text'],
                    "explanation": request.form['option4_explanation'],
                    "is_correct": request.form['option4_label'] == 'Correct'
                }
            ]

            choice = request.form.get('choice')

            if choice == '1':  # Save the question and options
                try:
                    # Insert the question into the question table
                    question_query = """
                        INSERT INTO question (questionId, question, activityId, content_block_id, sectionNumber, chapterNumber, textbook_id, createdBy) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    created_by = session.get('userid', 'JoDo1024')
                    cursor.execute(question_query, (question_id, question_text, activity_id, content_block_id, section_number, chapter_number, textbook_id, created_by))
                    
                    # Insert each option into the answer_set table
                    option_query = """
                        INSERT INTO answer_set (answer, explanation, activityId, content_block_id, sectionNumber, chapterNumber, textbook_id, questionId, isCorrect, createdBy) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    for option in options:
                        cursor.execute(option_query, (
                            option["text"], option["explanation"], activity_id, content_block_id, 
                            section_number, chapter_number, textbook_id, question_id, option["is_correct"], created_by
                        ))

                    # Commit the transaction
                    conn.commit()
                    flash('Question and options saved successfully!', 'success')
                    return redirect(url_for('add_activity', section_number=section_number, chapter_number=chapter_number, textbook_id=textbook_id, content_block_id=content_block_id))
                
                except mysql.connector.IntegrityError as e:
                    conn.rollback()
                    flash(f'Error: Could not add question due to database integrity error: {e}', 'danger')
                
                finally:
                    cursor.close()
                    conn.close()

        return render_template('add_question.html', activity_id=activity_id, section_number=section_number, chapter_number=chapter_number, textbook_id=textbook_id, content_block_id=content_block_id)
    else:
        return redirect(url_for('home'))

# ------------------------------------------------- ADD NEW CHAPTER FLOW ENDS -------------------------------------------------
# ------------------------------------------------- MODIFY FLOW FOR ADMIN -------------------------------------------------
# Admin - 3 - Modify Chapter Admin
@app.route('/<int:textbook_id>/modify_chapter_admin', methods=['GET', 'POST'])
def modify_chapter_admin(textbook_id):
    if 'role' in session and session['role'] == 'Admin':
        if request.method == 'POST':
            chapter_number = request.form['chapter_number']
            choice = request.form.get('choice')

            # Ensure that the chapter exists in the textbook
            conn = db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM chapter WHERE chapterNumber = %s AND textbook_id = %s", (chapter_number, textbook_id))
            chapter = cursor.fetchone()
            conn.close()

            if not chapter:
                flash("Error: Chapter not found. Please enter a valid Chapter ID.", 'danger')
                return render_template('modify_chapter_admin.html', textbook_id=textbook_id)

            # Handle the different options
            if choice == '1':  # Add New Section
                return redirect(url_for('add_section', chapter_number=chapter_number, textbook_id=textbook_id))
            elif choice == '2':  # Modify Section
                return redirect(url_for('modify_section_admin', chapter_number=chapter_number, textbook_id=textbook_id))

        return render_template('modify_chapter_admin.html', textbook_id=textbook_id)
    else:
        return redirect(url_for('home'))
    
# Admin - 3 - Modify Section Admin
@app.route('/<int:textbook_id>/<string:chapter_number>/modify_section_admin', methods=['GET', 'POST'])
def modify_section_admin(textbook_id, chapter_number):
    if 'role' in session and session['role'] == 'Admin':
        if request.method == 'POST':
            section_number = request.form['section_number']
            choice = request.form.get('choice')

            conn = db_connection()
            cursor = conn.cursor()

            # Ensure section exists in the given e-textbook and chapter
            query = """
            SELECT * FROM section WHERE sectionNumber = %s AND chapterNumber = %s AND textbook_id = %s
            """
            cursor.execute(query, (section_number, chapter_number, textbook_id))
            section = cursor.fetchone()

            if not section:
                flash("Error: Section not found. Please enter valid details.", 'danger')
                return render_template('modify_section_admin.html', textbook_id=textbook_id, chapter_number=chapter_number)

            if choice == '1':  # Add new content block
                return redirect(url_for('add_content_block', section_number=section_number, chapter_number=chapter_number, textbook_id=textbook_id))
            elif choice == '2':  # Modify existing content block
                return redirect(url_for('modify_content_block_admin', section_number=section_number, chapter_number=chapter_number, textbook_id=textbook_id))

        return render_template('modify_section_admin.html', textbook_id=textbook_id, chapter_number=chapter_number)
    else:
        return redirect(url_for('home'))

# Admin - 3 - Modify Content Block Admin
@app.route('/<int:textbook_id>/<string:chapter_number>/<string:section_number>/modify_content_block_admin', methods=['GET', 'POST'])
def modify_content_block_admin(textbook_id, chapter_number, section_number):
    if 'role' in session and session['role'] == 'Admin':
        if request.method == 'POST':
            content_block_id = request.form['content_block_id']
            choice = request.form.get('choice')

            conn = db_connection()
            cursor = conn.cursor()

            # Ensure content block exists
            query = """
            SELECT * FROM content_block WHERE id = %s AND sectionNumber = %s AND chapterNumber = %s AND textbook_id = %s
            """
            cursor.execute(query, (content_block_id, section_number, chapter_number, textbook_id))
            content_block = cursor.fetchone()

            if not content_block:
                flash("Error: Content block not found. Please enter a valid ID.", 'danger')
                return render_template('modify_content_block_admin.html', textbook_id=textbook_id, chapter_number=chapter_number, section_number=section_number)

            if choice == '1':  # Add text to content block
                return redirect(url_for('add_text', content_block_id=content_block_id, section_number=section_number, chapter_number=chapter_number, textbook_id=textbook_id))
            elif choice == '2':  # Add picture to content block
                return redirect(url_for('add_picture', content_block_id=content_block_id, section_number=section_number, chapter_number=chapter_number, textbook_id=textbook_id))
            elif choice == '3':  # Add new activity to content block
                return redirect(url_for('add_activity', content_block_id=content_block_id, section_number=section_number, chapter_number=chapter_number, textbook_id=textbook_id))
            

        return render_template('modify_content_block_admin.html', textbook_id=textbook_id, chapter_number=chapter_number, section_number=section_number)
    else:
        return redirect(url_for('home'))

# ------------------------------------------------- MODIFY FLOW FOR ADMIN ENDS -------------------------------------------------
# ------------------------------------------------- Admin create active/evaluation course -------------------------------------------------
# Admin - 4 - Create New Active Course
@app.route('/create_active_course', methods=['GET', 'POST'])
def create_active_course():
    if 'role' in session and session['role'] == 'Admin':
        if request.method == 'POST':
            # Get user input from the form
            course_id = request.form['course_id']
            course_name = request.form['course_name']
            etextbook_id = request.form['etextbook_id']
            faculty_id = request.form['faculty_id']
            start_date = request.form['start_date']
            end_date = request.form['end_date']
            course_token = request.form['course_token']
            course_capacity = request.form['course_capacity']
            choice = request.form.get('choice')

            # If the user chooses to save (choice 1)
            if choice == '1':
                conn = db_connection()
                cursor = conn.cursor()

                try:
                    # Insert the new course into the database
                    query = """
                    INSERT INTO course (id, title, type, startDate, endDate, courseToken, courseCapacity, facultyId, textbookId)
                    VALUES (%s, %s, 'Active', %s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(query, (course_id, course_name, start_date, end_date, course_token, course_capacity, faculty_id, etextbook_id))
                    conn.commit()
                    conn.close()

                    flash('Active course created successfully!', 'success')
                    return redirect(url_for('admin_dashboard'))
                except mysql.connector.IntegrityError as e:
                    conn.rollback()
                    if 'PRIMARY' in str(e):
                        flash('Error: A course with this ID already exists.', 'danger')
                    else:
                        flash('Error: Could not create course. Please try again.', 'danger')
                    conn.close()

        return render_template('create_active_course.html')
    else:
        return redirect(url_for('home'))

# Admin - 5 - Create New Evaluation Course
# Admin - Create New Evaluation Course
@app.route('/create_evaluation_course', methods=['GET', 'POST'])
def create_evaluation_course():
    if 'role' in session and session['role'] == 'Admin':
        if request.method == 'POST':
            # Get user input from the form
            course_id = request.form['course_id']
            course_name = request.form['course_name']
            etextbook_id = request.form['etextbook_id']
            faculty_id = request.form['faculty_id']
            start_date = request.form['start_date']
            end_date = request.form['end_date']
            choice = request.form.get('choice')

            # If the user chooses to save (choice 1)
            if choice == '1':
                conn = db_connection()
                cursor = conn.cursor()

                try:
                    # Insert the new evaluation course into the database
                    query = """
                    INSERT INTO course (id, title, type, startDate, endDate, facultyId, textbookId)
                    VALUES (%s, %s, 'Evaluation', %s, %s, %s, %s)
                    """
                    cursor.execute(query, (course_id, course_name, start_date, end_date, faculty_id, etextbook_id))
                    conn.commit()
                    conn.close()

                    flash('Evaluation course created successfully!', 'success')
                    return redirect(url_for('admin_dashboard'))
                except mysql.connector.IntegrityError as e:
                    conn.rollback()
                    if 'PRIMARY' in str(e):
                        flash('Error: A course with this ID already exists.', 'danger')
                    else:
                        flash('Error: Could not create course. Please try again.', 'danger')
                    conn.close()

        return render_template('create_evaluation_course.html')
    else:
        return redirect(url_for('home'))


# ------------------------------------------------ MODIFY CHAPTER FACULTY TA FLOW------------------------------------------------------
# Modify Chapter
@app.route('/<int:textbook_id>/modify_chapter', methods=['GET', 'POST'])
def modify_chapter(textbook_id):
    if 'role' in session and session['role'] in ('Faculty', 'TA'):
        if request.method == 'POST':
            chapter_number = request.form['chapter_number']
            choice = request.form.get('choice')
            if choice == '5':
                if session['role'] == 'Faculty':
                    return redirect(url_for('faculty_dashboard'))
                elif session['role'] == 'TA':
                    return redirect(url_for('ta.ta_dashboard'))
            if not chapter_number:
                flash('Error: Please enter a Chapter ID.', 'error')
                return render_template('modify_chapter.html', textbook_id=textbook_id)
            

            # check if the chapter exists
            conn = db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM chapter WHERE chapterNumber = %s AND textbook_id = %s", (chapter_number, textbook_id))
            chapter = cursor.fetchone()
            conn.close()
            if not chapter:
                flash("Error: Chapter not found. Please enter a valid Chapter ID.", 'danger')
                return render_template('modify_chapter.html', textbook_id=textbook_id)
            
            if choice == '1':
                return redirect(url_for('hide_chapter', textbook_id=textbook_id, chapter_number=chapter_number))
            elif choice == '2':
                return redirect(url_for('delete_chapter', textbook_id=textbook_id, chapter_number=chapter_number))
            elif choice == '3':
                return redirect(url_for('add_section', textbook_id=textbook_id, chapter_number=chapter_number))
            elif choice == '4':
                return redirect(url_for('modify_section', textbook_id=textbook_id, chapter_number=chapter_number))
            

        return render_template('modify_chapter.html', textbook_id=textbook_id)
    else:
        return redirect(url_for('home'))


# Hide Chapter
@app.route('/<int:textbook_id>/<string:chapter_number>/hide_chapter', methods=['GET', 'POST'])
def hide_chapter(textbook_id, chapter_number):
    if request.method == 'POST':
        if 'save' in request.form:
            try:
                conn = db_connection()
                cursor = conn.cursor()

                # Update the chapter status to hidden
                query = "UPDATE chapter SET hidden = 'Yes' WHERE chapterNumber = %s AND textbook_id = %s"
                cursor.execute(query, (chapter_number, textbook_id))
                conn.commit()

                flash('Chapter hidden successfully!', 'success')
            except Exception as e:
                flash(f'Error: {str(e)}', 'error')
            finally:
                cursor.close()
                conn.close()

            return redirect(url_for('modify_chapter', textbook_id=textbook_id))

        elif 'cancel' in request.form:
            flash('Action canceled. No changes made.', 'info')
            return redirect(url_for('modify_chapter', textbook_id=textbook_id))

    return render_template('hide_chapter.html', textbook_id=textbook_id, chapter_number=chapter_number)


# Delete Chapter
@app.route('/<int:textbook_id>/<string:chapter_number>/delete_chapter', methods=['GET', 'POST'])
def delete_chapter(textbook_id, chapter_number):
    if 'userid' in session and session['role'] in ('Faculty', 'TA'):
        if request.method == 'POST':
            if 'save' in request.form:
                try:
                    conn = db_connection()
                    cursor = conn.cursor()
                    
                    roleCheckQuery = "SELECT u.role as role, u.userid as userid FROM chapter c JOIN user u on c.createdBy = u.userid WHERE c.chapterNumber = %s AND c.textbook_id = %s"
                    cursor.execute(roleCheckQuery, (chapter_number, textbook_id,))
                    data = cursor.fetchone()
                    if data[0] == 'Admin':
                        flash('Error: You are not allowed to delete this chapter. (admin created)', 'error')
                        return redirect(url_for('modify_chapter', textbook_id=textbook_id))
                    if data[0] == 'Faculty':
                        if session['role'] == 'TA':
                            flash('Error: You are not allowed to delete this chapter. (faculty created)', 'error')
                            return redirect(url_for('modify_chapter', textbook_id=textbook_id))
                        if session['role'] == 'Faculty' and data[1] != session['userid']:
                            flash('Error: You are not allowed to delete this chapter. (created by different faculty)', 'error')
                            return redirect(url_for('modify_chapter', textbook_id=textbook_id))
                    if data[0] == 'TA' and data[1] != session['userid']:
                        flash('Error: You are not allowed to delete this chapter. (created by different TA)', 'error')
                        return redirect(url_for('modify_chapter', textbook_id=textbook_id))
                    
                    # Delete the chapter from the database
                    query = "DELETE FROM chapter WHERE chapterNumber = %s AND textbook_id = %s"
                    cursor.execute(query, (chapter_number, textbook_id))
                    conn.commit()

                    flash('Chapter deleted successfully!', 'success')
                except Exception as e:
                    flash(f'Error: {str(e)}', 'error')
                finally:
                    cursor.close()
                    conn.close()

                return redirect(url_for('modify_chapter', textbook_id=textbook_id))

            elif 'cancel' in request.form:
                flash('Action canceled. No changes made.', 'info')
                return redirect(url_for('modify_chapter', textbook_id=textbook_id))

        return render_template('delete_chapter.html', textbook_id=textbook_id, chapter_number=chapter_number)


# Modify Section
@app.route('/<int:textbook_id>/<string:chapter_number>/modify_section', methods=['GET', 'POST'])
def modify_section(textbook_id, chapter_number):
    if request.method == 'POST':
        section_number = request.form['section_number']
        option = request.form['option']

        if option == '5':
            return redirect(url_for('modify_chapter', textbook_id=textbook_id))

        if not section_number:
            flash('Error: Please enter a Section ID.', 'error')
            return render_template('modify_section.html', textbook_id=textbook_id, chapter_number=chapter_number)
        
        # Check if the section exists
        conn = db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM section WHERE sectionNumber = %s AND chapterNumber = %s AND textbook_id = %s", (section_number, chapter_number, textbook_id))
        section = cursor.fetchone()
        conn.close()

        if not section:
            flash("Error: Section not found. Please enter a valid Section ID.", 'error')
            return render_template('modify_section.html', textbook_id=textbook_id, chapter_number=chapter_number)

        # Redirect based on the selected option
        if option == '1':
            return redirect(url_for('hide_section', textbook_id=textbook_id, chapter_number=chapter_number,
                                    section_number=section_number))
        elif option == '2':
            return redirect(url_for('delete_section', textbook_id=textbook_id, chapter_number=chapter_number,
                                    section_number=section_number))
        elif option == '3':
            return redirect(url_for('add_content_block', textbook_id=textbook_id, chapter_number=chapter_number,
                                    section_number=section_number))
        elif option == '4':
            return redirect(url_for('modify_content_block', textbook_id=textbook_id, chapter_id=chapter_number,
                                    section_number=section_number))
        

    return render_template('modify_section.html', textbook_id=textbook_id, chapter_number=chapter_number)


# Hide Section
@app.route('/<int:textbook_id>/<string:chapter_number>/<string:section_number>/hide_section',
           methods=['GET', 'POST'])
def hide_section(textbook_id, chapter_number, section_number):
    if request.method == 'POST':
        if 'save' in request.form:
            try:
                conn = db_connection()
                cursor = conn.cursor()

                # Update section to be hidden
                query = """
                    UPDATE section
                    SET hidden = 'Yes'
                    WHERE sectionNumber = %s AND chapterNumber = %s AND textbook_id = %s
                """
                cursor.execute(query, (section_number, chapter_number, textbook_id))
                conn.commit()

                flash('Section hidden successfully!', 'success')
            except Exception as e:
                flash(f'Error: {str(e)}', 'error')
            finally:
                cursor.close()
                conn.close()

            return redirect(url_for('modify_section', textbook_id=textbook_id, chapter_number=chapter_number))

        elif 'cancel' in request.form:
            flash('Action canceled. No changes made.', 'info')
            return redirect(url_for('modify_section', textbook_id=textbook_id, chapter_number=chapter_number))

    return render_template('hide_section.html', textbook_id=textbook_id, chapter_number=chapter_number,
                           section_number=section_number)


# Delete Section
@app.route('/<int:textbook_id>/<string:chapter_number>/<string:section_number>/delete_section',
           methods=['GET', 'POST'])
def delete_section(textbook_id, chapter_number, section_number):
    if request.method == 'POST':
        if 'save' in request.form:
            try:
                conn = db_connection()
                cursor = conn.cursor()

                roleCheckQuery = "SELECT u.role as role, u.userid as userid FROM section s JOIN user u on s.createdBy = u.userid WHERE s.sectionNumber = %s AND s.chapterNumber = %s AND s.textbook_id = %s"
                cursor.execute(roleCheckQuery, (section_number, chapter_number, textbook_id,))
                data = cursor.fetchone()
                print(data)
                if data[0] == 'Admin':
                    flash('Error: You are not allowed to delete this section. (admin created)', 'error')
                    return redirect(url_for('modify_section', textbook_id=textbook_id, chapter_number=chapter_number))
                if data[0] == 'Faculty':
                    if session['role'] == 'TA':
                        flash('Error: You are not allowed to delete this section. (faculty created)', 'error')
                        return redirect(url_for('modify_section', textbook_id=textbook_id, chapter_number=chapter_number))
                    if session['role'] == 'Faculty' and data[1] != session['userid']:
                        flash('Error: You are not allowed to delete this chapter. (created by different faculty)', 'error')
                        return redirect(url_for('modify_section', textbook_id=textbook_id, chapter_number=chapter_number))
                if data[0] == 'TA' and data[1] != session['userid']:
                    flash('Error: You are not allowed to delete this chapter. (created by different TA)', 'error')
                    return redirect(url_for('modify_section', textbook_id=textbook_id, chapter_number=chapter_number))

                # Delete the section from the database
                query = """
                    DELETE FROM section
                    WHERE sectionNumber = %s AND chapterNumber = %s AND textbook_id = %s
                """
                cursor.execute(query, (section_number, chapter_number, textbook_id))
                conn.commit()

                flash('Section deleted successfully!', 'success')
            except Exception as e:
                flash(f'Error: {str(e)}', 'error')
            finally:
                cursor.close()
                conn.close()

            return redirect(url_for('modify_section', textbook_id=textbook_id, chapter_number=chapter_number))

        elif 'cancel' in request.form:
            flash('Action canceled. No changes made.', 'info')
            return redirect(url_for('modify_section', textbook_id=textbook_id, chapter_number=chapter_number))

    return render_template('delete_section.html', textbook_id=textbook_id, chapter_number=chapter_number,
                           section_number=section_number)


@app.route('/<textbook_id>/<chapter_id>/<section_number>/modify_content_block', methods=['GET', 'POST'])
def modify_content_block(textbook_id, chapter_id, section_number):
    if request.method == 'POST':
        content_block_id = request.form['content_block_id']
        option = request.form['option']

        # check if the user wants to go back
        if option == '8':
            return redirect(url_for('modify_section', textbook_id=textbook_id, chapter_number=chapter_id))
        # check if the content block id is entered
        if not content_block_id:
            flash('Error: Please enter a Content Block ID.', 'error')
            return render_template('modify_content_block.html', textbook_id=textbook_id, chapter_id=chapter_id,
                                   section_number=section_number)
        # check if the content block exists
        conn = db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM content_block WHERE id = %s AND sectionNumber = %s AND chapterNumber = %s AND textbook_id = %s", (content_block_id, section_number, chapter_id, textbook_id))
        content_block = cursor.fetchone()
        conn.close()

        if not content_block:
            flash("Error: Content block not found. Please enter a valid Content Block ID.", 'error')
            return render_template('modify_content_block.html', textbook_id=textbook_id, chapter_id=chapter_id,
                                   section_number=section_number)
        # redirect based on the selected option
        if option == '1':
            return redirect(url_for('hide_content_block', textbook_id=textbook_id, chapter_number=chapter_id,
                                    section_number=section_number, content_block_id=content_block_id))
        elif option == '2':
            return redirect(url_for('delete_content_block', textbook_id=textbook_id, chapter_number=chapter_id,
                                    section_number=section_number, content_block_id=content_block_id))
        elif option == '3':
            return redirect(
                url_for('add_text', textbook_id=textbook_id, chapter_number=chapter_id, section_number=section_number,
                        content_block_id=content_block_id))
        elif option == '4':
            return redirect(url_for('add_picture', textbook_id=textbook_id, chapter_number=chapter_id,
                                    section_number=section_number, content_block_id=content_block_id))
        elif option == '5':
            return redirect(url_for('hide_activity', textbook_id=textbook_id, chapter_number=chapter_id,
                                    section_number=section_number, content_block_id=content_block_id))
        elif option == '6':
            return redirect(url_for('delete_activity', textbook_id=textbook_id, chapter_number=chapter_id,
                                    section_number=section_number, content_block_id=content_block_id))
        elif option == '7':
            return redirect(url_for('add_activity', textbook_id=textbook_id, chapter_number=chapter_id,
                                    section_number=section_number, content_block_id=content_block_id))
    else:
        return render_template('modify_content_block.html', textbook_id=textbook_id, chapter_id=chapter_id,
                               section_number=section_number)


@app.route(
    '/<int:textbook_id>/<string:chapter_number>/<string:section_number>/<content_block_id>/hide_content_block',
    methods=['GET', 'POST'])
def hide_content_block(textbook_id, chapter_number, section_number, content_block_id):
    if request.method == 'POST':
        if 'save' in request.form:
            try:
                conn = db_connection()
                cursor = conn.cursor()

                query = """
                    UPDATE content_block
                    SET hidden = 'Yes'
                    WHERE id = %s AND sectionNumber = %s AND chapterNumber = %s AND textbook_id = %s
                """
                cursor.execute(query, (content_block_id, section_number, chapter_number, textbook_id))
                conn.commit()

                flash('Content block hidden successfully!', 'success')
            except Exception as e:
                conn.rollback()
                flash(f'Error: {str(e)}', 'error')
            finally:
                cursor.close()
                conn.close()
            return redirect(url_for('modify_content_block', textbook_id=textbook_id, chapter_id=chapter_number,
                                    section_number=section_number))
        elif 'cancel' in request.form:
            flash('Action canceled. No changes made.', 'info')
            return redirect(url_for('modify_content_block', textbook_id=textbook_id, chapter_id=chapter_number,
                                    section_number=section_number))
    else:
        return render_template('hide_content_block.html', content_block_id=content_block_id)


@app.route(
    '/<int:textbook_id>/<string:chapter_number>/<string:section_number>/<content_block_id>/delete_content_block',
    methods=['GET', 'POST'])
def delete_content_block(textbook_id, chapter_number, section_number, content_block_id):
    if request.method == 'POST':
        if 'save' in request.form:
            try:
                conn = db_connection()
                cursor = conn.cursor()

                roleCheckQuery = "SELECT u.role as role, u.userid as userid FROM content_block c JOIN user u on c.createdBy = u.userid WHERE c.id = %s AND c.sectionNumber = %s AND c.chapterNumber = %s AND c.textbook_id = %s"
                cursor.execute(roleCheckQuery, (content_block_id, section_number, chapter_number, textbook_id,))
                data = cursor.fetchone()
                print(data)
                if data[0] == 'Admin':
                    flash('Error: You are not allowed to delete this content block. (admin created)', 'error')
                    return redirect(url_for('modify_content_block', textbook_id=textbook_id, chapter_id=chapter_number,
                                    section_number=section_number))
                if data[0] == 'Faculty':
                    if session['role'] == 'TA':
                        flash('Error: You are not allowed to delete this content block. (faculty created)', 'error')
                        return redirect(url_for('modify_content_block', textbook_id=textbook_id, chapter_id=chapter_number,
                                    section_number=section_number))
                    if session['role'] == 'Faculty' and data[1] != session['userid']:
                        flash('Error: You are not allowed to delete this content block. (created by different faculty)', 'error')
                        return redirect(url_for('modify_content_block', textbook_id=textbook_id, chapter_id=chapter_number,
                                    section_number=section_number))
                if data[0] == 'TA' and data[1] != session['userid']:
                    flash('Error: You are not allowed to delete this content block. (created by different TA)', 'error')
                    return redirect(url_for('modify_content_block', textbook_id=textbook_id, chapter_id=chapter_number,
                                    section_number=section_number))

                query = """
                    DELETE FROM content_block
                    WHERE id = %s AND sectionNumber = %s AND chapterNumber = %s AND textbook_id = %s
                """
                cursor.execute(query, (content_block_id, section_number, chapter_number, textbook_id))
                conn.commit()

                flash('Content block deleted successfully!', 'success')
            except Exception as e:
                conn.rollback()
                flash(f'Error: {str(e)}', 'error')
            finally:
                cursor.close()
                conn.close()
            return redirect(url_for('modify_content_block', textbook_id=textbook_id, chapter_id=chapter_number,
                                    section_number=section_number))
        elif 'cancel' in request.form:
            flash('Action canceled. No changes made.', 'info')
            return redirect(url_for('modify_content_block', textbook_id=textbook_id, chapter_id=chapter_number,
                                    section_number=section_number))
    else:
        return render_template('delete_content_block.html', content_block_id=content_block_id)


@app.route(
    '/<int:textbook_id>/<string:chapter_number>/<string:section_number>/<content_block_id>/hide_activity',
    methods=['GET', 'POST'])
def hide_activity(textbook_id, chapter_number, section_number, content_block_id):
    if request.method == 'POST':
        activity_id = request.form['activity_id']
        if 'save' in request.form:
            try:
                conn = db_connection()
                cursor = conn.cursor()

                query = """
                    UPDATE activity
                    SET hidden = 'Yes'
                    WHERE activityId = %s AND content_block_id = %s AND sectionNumber = %s AND chapterNumber = %s AND textbook_id = %s
                """
                cursor.execute(query, (activity_id, content_block_id, section_number, chapter_number, textbook_id))
                conn.commit()

                flash('Activity hidden successfully!', 'success')
            except Exception as e:
                conn.rollback()
                flash(f'Error: {str(e)}', 'error')
            finally:
                cursor.close()
                conn.close()
            return redirect(url_for('modify_content_block', textbook_id=textbook_id, chapter_id=chapter_number,
                                    section_number=section_number))
        elif 'cancel' in request.form:
            return redirect(url_for('modify_content_block', textbook_id=textbook_id, chapter_id=chapter_number,
                                    section_number=section_number))
    else:
        return render_template('hide_activity.html', content_block_id=content_block_id)


@app.route(
    '/<int:textbook_id>/<string:chapter_number>/<string:section_number>/<content_block_id>/delete_activity',
    methods=['GET', 'POST'])
def delete_activity(textbook_id, chapter_number, section_number, content_block_id):
    if request.method == 'POST':
        activity_id = request.form['activity_id']
        if 'save' in request.form:
            try:
                conn = db_connection()
                cursor = conn.cursor()

                roleCheckQuery = "SELECT u.role as role, u.userid as userid FROM activity a JOIN user u on a.createdBy = u.userid WHERE a.activityId = %s AND a.content_block_id = %s AND a.sectionNumber = %s AND a.chapterNumber = %s AND a.textbook_id = %s"
                cursor.execute(roleCheckQuery, (activity_id, content_block_id, section_number, chapter_number, textbook_id,))
                data = cursor.fetchone()
                print(data)
                if data[0] == 'Admin':
                    flash('Error: You are not allowed to delete this activity. (admin created)', 'error')
                    return redirect(url_for('modify_content_block', textbook_id=textbook_id, chapter_id=chapter_number,
                                    section_number=section_number))
                if data[0] == 'Faculty':
                    if session['role'] == 'TA':
                        flash('Error: You are not allowed to delete this activity. (faculty created)', 'error')
                        return  redirect(url_for('modify_content_block', textbook_id=textbook_id, chapter_id=chapter_number,
                                    section_number=section_number))
                    if session['role'] == 'Faculty' and data[1] != session['userid']:
                        flash('Error: You are not allowed to delete this activity. (created by different faculty)', 'error')
                        return  redirect(url_for('modify_content_block', textbook_id=textbook_id, chapter_id=chapter_number,
                                    section_number=section_number))
                if data[0] == 'TA' and data[1] != session['userid']:
                    flash('Error: You are not allowed to delete this activity. (created by different TA)', 'error')
                    return redirect(url_for('modify_content_block', textbook_id=textbook_id, chapter_id=chapter_number,
                                    section_number=section_number))
                
                query = """
                    DELETE FROM activity
                    WHERE activityId = %s AND content_block_id = %s AND sectionNumber = %s AND chapterNumber = %s AND textbook_id = %s
                """
                cursor.execute(query, (activity_id, content_block_id, section_number, chapter_number, textbook_id))
                conn.commit()

                flash('Activity deleted successfully!', 'success')
            except Exception as e:
                conn.rollback()
                flash(f'Error: {str(e)}', 'error')
            finally:
                cursor.close()
                conn.close()
            return redirect(url_for('modify_content_block', textbook_id=textbook_id, chapter_id=chapter_number,
                                    section_number=section_number))
        elif 'cancel' in request.form:
            return redirect(url_for('modify_content_block', textbook_id=textbook_id, chapter_id=chapter_number,
                                    section_number=section_number))
    else:
        return render_template('delete_activity.html', content_block_id=content_block_id)


# ------------------------------------------------- MODIFY CHAPTER FLOW ENDS -------------------------------------------------
# Faculty Landing
@app.route('/faculty/dashboard')
def faculty_dashboard():
    if 'role' in session and session['role'] == 'Faculty':
        return render_template('faculty_dashboard.html')
    else:
        return redirect(url_for('home'))


# active courses of that faculty
@app.route('/faculty/active_course', methods=['GET', 'POST'])
def active_course():
    if 'userid' in session:
        if request.method == 'POST':
            course_id = request.form['course_id']
            # Store course_id in session or pass it along
            session['course_id'] = course_id
            return redirect(url_for('active_course_menu'))
        return render_template('active_course.html')
    else:
        return redirect(url_for('login'))


@app.route('/faculty/evaluation_course', methods=['GET', 'POST'])
def evaluation_course():
    if 'userid' in session:
        if request.method == 'POST':
            course_id = request.form['course_id']
            # Store course_id in session or pass it along
            session['course_id'] = course_id
            return redirect(url_for('evaluation_course_menu'))
        return render_template('evaluation_course.html')
    else:
        return redirect(url_for('login'))


@app.route('/faculty/active_course/menu')
def active_course_menu():
    if 'userid' in session and 'course_id' in session:

        conn = db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM textbook WHERE id = %s", (session['course_id'],))
        etextbook_id = cursor.fetchone()
        conn.close()

        return render_template('active_course_menu.html')
    else:
        return redirect(url_for('active_course'))


@app.route('/faculty/evaluation_course/menu')
def evaluation_course_menu():
    if 'userid' in session and 'course_id' in session:

        conn = db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM textbook WHERE id = %s", (session['course_id'],))
        etextbook_id = cursor.fetchone()
        conn.close()

        return render_template('evaluation_course_menu.html')
    else:
        return redirect(url_for('evaluation_course'))


@app.route('/faculty/view_courses', methods=['GET', 'POST'])
def view_courses():
    if 'userid' in session:
        conn = db_connection()
        cursor = conn.cursor()
        query = """
            SELECT c.id, c.title, c.type
            FROM course c
            WHERE c.facultyId = %s
        """
        cursor.execute(query, (session['userid'],))
        courses = cursor.fetchall()
        cursor.close()
        conn.close()

        return render_template('view_courses.html', courses=courses)
    else:
        return redirect(url_for('login'))


@app.route('/faculty/change_password', methods=['GET', 'POST'])
def change_password():
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        if new_password != confirm_password:
            flash('New password and confirm password do not match', 'error')
            return render_template('change_password.html')

        # Check if the current password is correct
        conn = db_connection()
        cursor = conn.cursor()
        query = "SELECT password FROM user WHERE userid = %s"
        cursor.execute(query, (session['userid'],))
        stored_password = cursor.fetchone()[0]

        if current_password != stored_password:
            flash('Current password is incorrect', 'error')
        else:
            update_query = "UPDATE user SET password = %s WHERE userid = %s"
            cursor.execute(update_query, (new_password, session['userid']))
            conn.commit()
            flash('Password updated successfully', 'success')

        cursor.close()
        conn.close()

        return redirect(url_for('faculty_dashboard'))

    return render_template('change_password.html')


@app.route('/faculty/active_course/view_worklist')
def view_worklist():
    if 'userid' in session and 'course_id' in session:
        # Fetch worklist data based on course_id
        conn = db_connection()
        cursor = conn.cursor()
        query = """
            SELECT u.userid, u.firstName, u.lastName, c.id, c.title
            FROM user u
            JOIN enrollment e ON u.userid = e.studentID
            JOIN course c ON c.id = e.courseId
            WHERE e.status = 'Pending' AND c.facultyId = %s
        """
        cursor.execute(query, (session['userid'],))
        worklist = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('worklist.html', worklist=worklist)
    else:
        return redirect(url_for('active_course'))


@app.route('/faculty/active_course/approve_enrollment', methods=['GET', 'POST'])
def approve_enrollment():
    if request.method == 'POST':
        student_id = request.form['student_id']
        faculty_id = session['userid']
        course_id = session['course_id']

        if 'save' in request.form:
            try:
                conn = db_connection()
                cursor = conn.cursor()

                # Update the enrollment status from 'Pending' to 'Approved'
                cursor.callproc('approve_enrollment_proc', [student_id, faculty_id, course_id])
                # query = """
                #     UPDATE enrollment
                #     SET status = 'Approved'
                #     WHERE studentID = %s AND status = 'Pending'
                #     and courseId in (select id from course where facultyId=%s)
                # """
                # cursor.execute(query, (student_id, session['userid']))

                # Fetch the result message from the stored procedure
                for result in cursor.stored_results():
                    result_message = result.fetchone()[0]

                flash(result_message,
                      'Enrollment approved successfully!' if 'approved' in result_message.lower() else 'Error')

                conn.commit()

                # Check if any row was affected (indicating success)
                if cursor.rowcount > 0:
                    flash('Enrollment approved successfully!', 'success')

            except Exception as e:
                flash(f'Error: {str(e)}', 'error')

            finally:
                cursor.close()
                conn.close()

            return redirect(url_for('active_course_menu'))  # Go back to the course menu

        elif 'cancel' in request.form:
            flash('Action canceled. No changes made.', 'info')
            return redirect(url_for('active_course_menu'))  # Go back to the course menu

    return render_template('approve_enrollment.html')


@app.route('/faculty/active_course/view_students', methods=['GET'])
def view_students():
    if 'course_id' in session:
        try:
            # Establish database connection
            conn = db_connection()
            cursor = conn.cursor(dictionary=True)

            # Fetch students enrolled in the active course
            query = """
                SELECT u.userid, u.firstName, u.lastName, u.email
                FROM user u
                JOIN enrollment e ON u.userid = e.studentID
                WHERE e.courseId = %s
            """
            cursor.execute(query, (session['course_id'],))
            students = cursor.fetchall()
            conn.close()
            print(students)
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
            students = []

        finally:
            cursor.close()
            conn.close()

        return render_template('view_students.html', students=students)
    else:
        flash('No active course selected.', 'error')
        return redirect(url_for('active_course_menu'))


@app.route('/faculty/add_ta', methods=['GET', 'POST'])
def add_ta():
    if 'role' in session and 'course_id' in session and session['role'] == 'Faculty':
        if request.method == 'POST':
            first_name = request.form['first_name']
            last_name = request.form['last_name']
            email = request.form['email']
            password = request.form['password']

            if 'save' in request.form:
                conn = db_connection()
                cursor = conn.cursor()

                # Generate a unique user ID based on the provided first and last name
                userid = generate_userid(first_name, last_name)

                try:
                    # Inserting the new TA user into the database
                    query = "INSERT INTO user (userid, firstName, lastName, email, password, role) VALUES (%s, %s, %s, %s, %s, 'TA')"

                    cursor.execute(query, (userid, first_name, last_name, email, password))
                    teaches_query = "INSERT INTO teaches (course_id, user_id, role) VALUES (%s, %s, 'TA')"
                    cursor.execute(teaches_query, (session['course_id'], userid))
                    conn.commit()
                    flash('TA account created successfully!', 'success')
                except mysql.connector.IntegrityError as e:
                    conn.rollback()
                    if 'email' in str(e):
                        flash('Error: A TA account with this email already exists.', 'danger')
                    elif 'PRIMARY' in str(e):
                        flash('Error: A TA account with this user ID already exists.', 'danger')
                    else:
                        flash('Error: Could not create TA account. Please try again.', 'danger')
                finally:
                    cursor.close()
                    conn.close()

                return redirect(url_for('faculty_dashboard'))

            elif 'cancel' in request.form:
                flash('Action canceled. No changes made.', 'info')
                return redirect(url_for('faculty_dashboard'))

        return render_template('add_ta.html')
    else:
        return redirect(url_for('active_course'))


@app.route('/faculty/add_chapter', methods=['GET', 'POST'])
def fac_TA_add_chapter():
    if 'role' in session and session['role'] == 'Faculty':
        if 'course_id' not in session:
            return redirect(url_for('faculty_dashboard'))

        conn = db_connection()
        cursor = conn.cursor()

        # Fetch textbookId associated with the active course
        query = """
            SELECT textbookId
            FROM course
            WHERE id = %s AND facultyId = %s
        """
        cursor.execute(query, (session['course_id'], session['userid']))
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result:
            etextbook_id = result[0]
            return redirect(url_for('add_chapter', textbook_id=etextbook_id))
        else:
            flash('No textbook found for this course.', 'error')
            return redirect(url_for('faculty_dashboard'))
    else:
        return redirect(url_for('active_course'))


@app.route('/faculty/modify_chapter', methods=['GET', 'POST'])
def fac_TA_modify_chapter():
    if 'role' in session and session['role'] == 'Faculty':
        if 'course_id' not in session:
            return redirect(url_for('faculty_dashboard'))

        conn = db_connection()
        cursor = conn.cursor()

        # Fetch textbookId associated with the active course
        query = """
                SELECT textbookId
                FROM course
                WHERE id = %s AND facultyId = %s
            """
        cursor.execute(query, (session['course_id'], session['userid']))
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result:
            etextbook_id = result[0]
            return redirect(url_for('modify_chapter', textbook_id=etextbook_id))
        else:
            flash('No textbook found for this course.', 'error')
            return redirect(url_for('faculty_dashboard'))


# Student Landing
@app.route('/student_dashboard')
def student_dashboard():
    if 'role' in session and session['role'] == 'Student':
        return render_template('student_dashboard.html')
    else:
        return redirect(url_for('home'))


@app.route('/query_screen', methods=['GET', 'POST'])
def query_screen():
    if request.method == 'POST':
        query_number = request.form.get('query_number')

        # Execute corresponding query based on user selection
        query_result = None
        try:
            conn = db_connection()
            cursor = conn.cursor(dictionary=True)

            if query_number == '1':
                cursor.execute("""
                    SELECT textbook_id "Textbook id",count(1) "Number of Sections in first chapter"
                    FROM section WHERE chapterNumber='chap01'
                    GROUP BY textbook_id
                """)
                query_result = cursor.fetchall()

            elif query_number == '2':
                cursor.execute("""
                    SELECT u.firstName "First Name", u.lastName "Last Name", u.role "Role", c.title "Course Title" FROM course c, user u
                    WHERE c.facultyId=u.userid
                    UNION
                    SELECT u.firstName "First Name", u.lastName "Last Name", u.role "Role", c.title "Course Title" FROM course c, user u, teaches t
                    WHERE t.user_id=u.userid AND u.role='TA' AND t.course_id=c.id
                """)
                query_result = cursor.fetchall()

            elif query_number == '3':
                cursor.execute("""
                    SELECT c.id AS "Course ID", u.firstName "First Name", u.lastName "Last Name", COUNT(e.studentID) AS "Total Students" 
                    FROM course c 
                    INNER JOIN enrollment e ON c.id = e.courseId 
                    INNER JOIN user u ON u.userid = c.facultyId 
                    WHERE c.type = 'Active' 
                    GROUP BY c.id
                """)
                query_result = cursor.fetchall()

            elif query_number == '4':
                cursor.execute("""
                    SELECT e.courseId "Course ID", COUNT(e.studentID) AS Waiting_List_Count 
                    FROM enrollment e 
                    WHERE e.status = 'Pending' 
                    GROUP BY e.courseId 
                    ORDER BY Waiting_List_Count DESC
                    LIMIT 1
                """)
                query_result = cursor.fetchone()

            elif query_number == '5':
                cursor.execute("""
                    SELECT content "Content"
                    FROM content_block 
                    WHERE chapterNumber = 'chap02' AND textbook_id = 101 
                    ORDER BY sectionNumber,id
                """)
                query_result = cursor.fetchall()

            elif query_number == '6':
                cursor.execute("""
                    SELECT answer "Incorrect Answer", explanation "Explanation of Incorrect Answer"
                    FROM answer_set 
                    WHERE activityId = 'ACT0' AND questionId = '2' AND isCorrect = 0
                    order by answerid
                """)
                query_result = cursor.fetchall()

            elif query_number == '7':
                cursor.execute("""
                    SELECT t.title "Textbook Title"
                    FROM course c1 -- active course textbook
                    JOIN course c2 -- eval course textbook
                    ON c1.textbookId = c2.textbookId 
                    JOIN textbook t ON c1.textbookId = t.id 
                    WHERE c1.type = 'Active' 
                    AND c2.type = 'Evaluation' 
                    AND c1.facultyId != c2.facultyId
                """)
                query_result = cursor.fetchall()

            cursor.close()
            conn.close()

        except mysql.connector.Error as e:
            flash(f"Database error: {e}", "danger")
        except Exception as e:
            flash(f"Unexpected error: {e}", "danger")

        return render_template('query_screen.html', query_result=query_result)

    return render_template('query_screen.html', query_result=None)


if __name__ == '__main__':
    app.run(debug=True)
