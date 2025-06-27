from flask import Flask, request, render_template, redirect, session, url_for, jsonify
from flask_mysqldb import MySQL
import MySQLdb.cursors
import re


app = Flask(__name__)
app.secret_key = 'your_secret_key'

# MySQL configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'vinayagam'
app.config['MYSQL_DB'] = 'acad'

mysql = MySQL(app)

@app.route('/initdb')
def init_db():
    cur = mysql.connection.cursor()

    # Degree
    cur.execute("""
    CREATE TABLE IF NOT EXISTS degree (
        id CHAR(1) PRIMARY KEY,
        name VARCHAR(100) NOT NULL
    )
    """)

    # Batch
    cur.execute("""
    CREATE TABLE IF NOT EXISTS batch (
        id CHAR(2) PRIMARY KEY,
        duration_start INT,
        duration_end INT
    )
    """)

    # Department
    cur.execute("""
    CREATE TABLE IF NOT EXISTS department (
        id CHAR(1) PRIMARY KEY,
        name VARCHAR(100)
    )
    """)

    # Class
    cur.execute("""
    CREATE TABLE IF NOT EXISTS class (
        id VARCHAR(5) PRIMARY KEY,
        degree_id CHAR(1),
        batch_id CHAR(2),
        department_id CHAR(1),
        FOREIGN KEY (degree_id) REFERENCES degree(id),
        FOREIGN KEY (batch_id) REFERENCES batch(id),
        FOREIGN KEY (department_id) REFERENCES department(id)
    )
    """)

    # Students
    cur.execute("""
    CREATE TABLE IF NOT EXISTS students (
        roll_no VARCHAR(20) PRIMARY KEY,
        name VARCHAR(100),
        password VARCHAR(100),
        class_id VARCHAR(5),
        FOREIGN KEY (class_id) REFERENCES class(id)
    )
    """)

    # Teachers
    cur.execute("""
    CREATE TABLE IF NOT EXISTS teachers (
        id VARCHAR(10) PRIMARY KEY,
        name VARCHAR(100),
        password VARCHAR(100),
        department_id CHAR(1),
        FOREIGN KEY (department_id) REFERENCES department(id)
    )
    """)

    # Courses
    cur.execute("""
    CREATE TABLE IF NOT EXISTS courses (
        code VARCHAR(10) PRIMARY KEY,
        title VARCHAR(100),
        department_id CHAR(1),
        degree_id CHAR(1),
        batch_id CHAR(2),
        semester INT,
        FOREIGN KEY (department_id) REFERENCES department(id),
        FOREIGN KEY (degree_id) REFERENCES degree(id),
        FOREIGN KEY (batch_id) REFERENCES batch(id)
    )
    """)

    # Course Offerings
    cur.execute("""
    CREATE TABLE IF NOT EXISTS course_offerings (
        id INT AUTO_INCREMENT PRIMARY KEY,
        course_code VARCHAR(10),
        class_id VARCHAR(5),
        teacher_id VARCHAR(10),
        FOREIGN KEY (course_code) REFERENCES courses(code),
        FOREIGN KEY (class_id) REFERENCES class(id),
        FOREIGN KEY (teacher_id) REFERENCES teachers(id)
    )
    """)

    # Marks
    cur.execute("""
    CREATE TABLE IF NOT EXISTS marks (
        id INT AUTO_INCREMENT PRIMARY KEY,
        student_id VARCHAR(20),
        offering_id INT,
        `ca1` float DEFAULT NULL,
  	`ca2` float DEFAULT NULL,
  	`final` float DEFAULT NULL,
        total FLOAT GENERATED ALWAYS AS ((final / 2) + (ca1 / 2 + ca2 / 2)) STORED,
	UNIQUE KEY `unique_student_offering` (`student_id`,`offering_id`),
        FOREIGN KEY (student_id) REFERENCES students(roll_no),
        FOREIGN KEY (offering_id) REFERENCES course_offerings(id)
    )
    """)
    
    cur.execute("""
                CREATE TABLE IF NOT EXISTS admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL
);

                """)

    mysql.connection.commit()
    cur.close()
    return 'Database Initialized!'

# ------------------------------
# Student Registration/Login
# ------------------------------
@app.route('/student/register', methods=['GET', 'POST'])
def student_register():
    cur = mysql.connection.cursor()

    # Fetch all available classes
    cur.execute("SELECT id FROM class")
    classes = cur.fetchall()

    if request.method == 'POST':
        roll_no = request.form['roll_no']
        name = request.form['name']
        password = request.form['password']
        class_id = request.form['class_id']

        # Insert student
        cur.execute("INSERT INTO students (roll_no, name, password, class_id) VALUES (%s, %s, %s, %s)",
                    (roll_no, name, password, class_id))

        # Get all course offerings for the selected class
        cur.execute("SELECT id FROM course_offerings WHERE class_id = %s", (class_id,))
        offerings = cur.fetchall()

        # Insert default marks with NULLs
        for offering in offerings:
            cur.execute("""
                INSERT INTO marks (student_id, offering_id, ca1, ca2, final)
                VALUES (%s, %s, %s, %s, %s)
            """, (roll_no, offering[0], None, None, None))

        mysql.connection.commit()
        cur.close()

        return redirect('/student/login')

    cur.close()
    return render_template('student_register.html', classes=classes)




@app.route('/student/login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        roll_no = request.form['roll_no']
        password = request.form['password']
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT * FROM students WHERE roll_no = %s AND password = %s",
                    (roll_no, password))
        student = cur.fetchone()
        cur.close()
        if student:
            session['student'] = student['roll_no']
            
            return redirect('/student/dashboard')
        return 'Invalid login'
    return render_template('student_login.html')

@app.route('/student/dashboard')
def student_dashboard():
    if 'student' not in session:
        return redirect('/student/login')

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        SELECT m.*, c.code, c.title, c.semester 
        FROM marks m
        JOIN course_offerings co ON m.offering_id = co.id
        JOIN courses c ON co.course_code = c.code
        WHERE m.student_id = %s
        ORDER BY c.semester, c.code
    """, (session['student'],))
    rows = cur.fetchall()
    cur.close()

    # Group marks by semester
    from collections import defaultdict
    marks_by_semester = defaultdict(list)
    for row in rows:
        marks_by_semester[row['semester']].append(row)

    return render_template('student_dashboard.html', marks_by_semester=marks_by_semester)


# ------------------------------
# Teacher Login + Dashboard
# ------------------------------
@app.route('/teacher/login', methods=['GET', 'POST'])
def teacher_login():
    if request.method == 'POST':
        id = request.form['id']
        password = request.form['password']
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT * FROM teachers WHERE id = %s AND password = %s", (id, password))
        teacher = cur.fetchone()
        cur.close()
        if teacher:
            session['teacher'] = teacher['id']
            return redirect('/teacher/dashboard')
        return 'Invalid login'
    return render_template('teacher_login.html')

@app.route('/teacher/performance_dashboard')
def teacher_performance_dashboard():
    teacher_id = session.get('teacher')
    if not teacher_id:
        return redirect(url_for('login'))  # Redirect if no teacher_id found

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Step 1: Fetch all course offerings for the teacher
    cur.execute("""
        SELECT co.id, c.title, c.code, cl.id AS class_id
        FROM course_offerings co
        JOIN courses c ON co.course_code = c.code
        JOIN class cl ON co.class_id = cl.id
        WHERE co.teacher_id = %s
    """, (teacher_id,))
    course_offerings = cur.fetchall()

    performance_data = []
    
    # Step 2: For each course offering, fetch student marks and calculate class averages
    for offering in course_offerings:
        cur.execute("""
            SELECT s.name AS student_name, m.ca1, m.ca2, m.final, m.total
            FROM marks m
            JOIN students s ON m.student_id = s.roll_no
            WHERE m.offering_id = %s
        """, (offering['id'],))
        student_marks = cur.fetchall()

        # Step 3: Calculate averages for the class
        total_ca1 = total_ca2 = total_final = total_marks = 0
        num_students = len(student_marks)

        for student in student_marks:
            total_ca1 += student['ca1'] or 0
            total_ca2 += student['ca2'] or 0
            total_final += student['final'] or 0
            total_marks += student['total'] or 0

        avg_ca1 = total_ca1 / num_students if num_students else 0
        avg_ca2 = total_ca2 / num_students if num_students else 0
        avg_final = total_final / num_students if num_students else 0
        avg_total = total_marks / num_students if num_students else 0

        # Step 4: Add the performance data for this course
        performance_data.append({
            'course_title': offering['title'],
            'course_code': offering['code'],
            'class_id': offering['class_id'],
            'avg_ca1': avg_ca1,
            'avg_ca2': avg_ca2,
            'avg_final': avg_final,
            'avg_total': avg_total,
            'student_marks': student_marks
        })

    # Close cursor
    cur.close()

    # Step 5: Render the performance dashboard with calculated performance data
    return render_template('teacher_performance_dashboard.html', performance_data=performance_data)


@app.route('/teacher/dashboard')
def teacher_dashboard():
    if 'teacher' not in session:
        return redirect('/teacher/login')
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        SELECT co.id AS offering_id, c.title, cl.id AS class_id FROM course_offerings co
        JOIN courses c ON co.course_code = c.code
        JOIN class cl ON co.class_id = cl.id
        WHERE co.teacher_id = %s
    """, (session['teacher'],))
    offerings = cur.fetchall()
    cur.close()
    return render_template('teacher_dashboard.html', offerings=offerings)

@app.route('/teacher/marks/<int:offering_id>', methods=['GET', 'POST'])
def update_marks(offering_id):
    if 'teacher' not in session:
        return redirect('/teacher/login')

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if request.method == 'POST':
        student_id = request.form['student_id']

        # Read raw values
        ca1_raw = request.form.get('ca1', '').strip()
        ca2_raw = request.form.get('ca2', '').strip()
        final_raw = request.form.get('final', '').strip()

        # Convert to float or None
        ca1   = float(ca1_raw) if ca1_raw else None
        ca2   = float(ca2_raw) if ca2_raw else None
        final = float(final_raw) if final_raw else None

        # Insert or update, preserving NULLs
        cur.execute("""
            INSERT INTO marks (student_id, offering_id, ca1, ca2, final)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY 
            UPDATE 
              ca1   = VALUES(ca1),
              ca2   = VALUES(ca2),
              final = VALUES(final)
        """, (student_id, offering_id, ca1, ca2, final))

        mysql.connection.commit()

    # Fetch students (and optionally their existing marks)
    cur.execute("""
        SELECT s.roll_no, s.name,
               m.ca1, m.ca2, m.final
        FROM students s
        JOIN class c ON s.class_id = c.id
        JOIN course_offerings co ON c.id = co.class_id
        LEFT JOIN marks m ON m.student_id = s.roll_no AND m.offering_id = co.id
        WHERE co.id = %s
    """, (offering_id,))
    students = cur.fetchall()
    cur.close()

    return render_template('teacher_marks.html',
                           students=students,
                           offering_id=offering_id)


# ------------------------------
# Logout
# ------------------------------
@app.route('/logout')
def logout():
    print(session)
    if 'student' in session:
        session.clear()
        return redirect('/student/login')
    elif 'teacher' in session:
        session.clear()
        return redirect('/teacher/login')
    else:
        session.clear()
        return redirect('/student/login')
    
    
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Check if admin exists in the database
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT * FROM admins WHERE username = %s AND password = %s", (username, password))
        admin = cur.fetchone()
        cur.close()

        if admin:
            session['admin'] = admin['id']
            return redirect('/admin/dashboard')  # Redirect to admin dashboard
        else:
            return "Invalid credentials", 401  # Unauthorized error
    
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin' not in session:
        return redirect('/admin/login')

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Students with class name (degree + batch + department)
    cur.execute("""
        SELECT s.roll_no, s.name, 
               CONCAT(c.id, ' (', d.name, ' ', dg.name, ' ', b.duration_start, '-', b.duration_end, ')') AS class_name
        FROM students s
        JOIN class c ON s.class_id = c.id
        JOIN department d ON c.department_id = d.id
        JOIN degree dg ON c.degree_id = dg.id
        JOIN batch b ON c.batch_id = b.id
    """)
    students = cur.fetchall()

    # Teachers with department name
    cur.execute("""
        SELECT t.id, t.name, d.name AS department_name
        FROM teachers t
        JOIN department d ON t.department_id = d.id
    """)
    teachers = cur.fetchall()

    # Courses with department, degree, and batch names
    cur.execute("""
        SELECT c.code, c.title, d.name AS department_name,
               dg.name AS degree_name,
               CONCAT(b.duration_start, '-', b.duration_end) AS batch_name,
               c.semester
        FROM courses c
        JOIN department d ON c.department_id = d.id
        JOIN degree dg ON c.degree_id = dg.id
        JOIN batch b ON c.batch_id = b.id
    """)
    courses = cur.fetchall()

    # Course offerings with course title, class name, teacher name
    cur.execute("""
        SELECT co.id, co.course_code, cs.title AS course_title,
               cl.id AS class_id,
               CONCAT(cl.id, ' (', d.name, ' ', dg.name, ' ', b.duration_start, '-', b.duration_end, ')') AS class_name,
               t.name AS teacher_name,
               cs.semester
        FROM course_offerings co
        JOIN courses cs ON co.course_code = cs.code
        JOIN class cl ON co.class_id = cl.id
        JOIN department d ON cl.department_id = d.id
        JOIN degree dg ON cl.degree_id = dg.id
        JOIN batch b ON cl.batch_id = b.id
        JOIN teachers t ON co.teacher_id = t.id
    """)
    course_offerings = cur.fetchall()

    # Marks with student name and course title
    cur.execute("""
        SELECT m.student_id, s.name AS student_name,
               m.offering_id, cs.code AS course_code, cs.title AS course_title,
               m.ca1, m.ca2, m.final, m.total
        FROM marks m
        JOIN students s ON m.student_id = s.roll_no
        JOIN course_offerings co ON m.offering_id = co.id
        JOIN courses cs ON co.course_code = cs.code
    """)
    marks = cur.fetchall()

    # Degrees
    cur.execute("SELECT id, name FROM degree")
    degrees = cur.fetchall()

    # Departments
    cur.execute("SELECT id, name FROM department")
    departments = cur.fetchall()

    # Batches
    cur.execute("SELECT id, duration_start, duration_end FROM batch")
    batches = cur.fetchall()

    # Classes with full reference info
    cur.execute("""
        SELECT c.id, d.name AS department, dg.name AS degree,
               b.duration_start, b.duration_end
        FROM class c
        JOIN department d ON c.department_id = d.id
        JOIN degree dg ON c.degree_id = dg.id
        JOIN batch b ON c.batch_id = b.id
    """)
    classes = cur.fetchall()

    cur.close()

    return render_template('admin_dashboard.html',
                           students=students,
                           teachers=teachers,
                           courses=courses,
                           course_offerings=course_offerings,
                           marks=marks,
                           degrees=degrees,
                           departments=departments,
                           batches=batches,
                           classes=classes)



@app.route('/admin/student/create', methods=['GET', 'POST'])
def create_student():
    if 'admin' not in session:
        return redirect('/admin/login')

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch all classes for the dropdown
    cur.execute("SELECT id, degree_id, batch_id, department_id FROM class")
    classes = cur.fetchall()

    if request.method == 'POST':
        roll_no = request.form['roll_no']
        name = request.form['name']
        password = request.form['password']
        class_id = request.form['class_id']

        cur.execute("INSERT INTO students (roll_no, name, password, class_id) VALUES (%s, %s, %s, %s)",
                    (roll_no, name, password, class_id))
        mysql.connection.commit()
        cur.close()

        return redirect('/admin/dashboard')

    return render_template('create_student.html', classes=classes)



@app.route('/admin/teacher/create', methods=['GET', 'POST'])
def create_teacher():
    if 'admin' not in session:
        return redirect('/admin/login')

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch all departments for the dropdown
    cur.execute("SELECT id, name FROM department")
    departments = cur.fetchall()

    if request.method == 'POST':
        teacher_id = request.form['teacher_id']
        name = request.form['name']
        department = request.form['department']

        cur.execute("INSERT INTO teachers (id, name, department_id) VALUES (%s, %s, %s)",
                    (teacher_id, name, department))
        mysql.connection.commit()
        cur.close()

        return redirect('/admin/dashboard')

    return render_template('create_teacher.html', departments=departments)

@app.route('/admin/degrees/<department_id>')
def get_degrees_by_department(department_id):
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT id, name FROM degree WHERE id IN (SELECT DISTINCT degree_id FROM class WHERE department_id = %s)", (department_id,))
    degrees = cur.fetchall()
    cur.close()
    return jsonify(degrees)

@app.route('/admin/batches/<degree_id>')
def get_batches_by_degree(degree_id):
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT DISTINCT b.id, b.duration_start, b.duration_end FROM batch b JOIN class c ON b.id = c.batch_id WHERE c.degree_id = %s", (degree_id,))
    batches = cur.fetchall()
    cur.close()
    return jsonify(batches)

@app.route('/admin/generate_course_code', methods=['POST'])
def generate_course_code():
    data = request.get_json()
    batch_id = data['batch_id']
    department_id = data['department_id']
    semester = data['semester']

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Get batch start year
    cur.execute("SELECT duration_start FROM batch WHERE id = %s", (batch_id,))
    batch = cur.fetchone()
    if not batch:
        return jsonify({'error': 'Invalid batch ID'}), 400

    batch_prefix = str(batch['duration_start'])[-2:]

    # Count existing courses for the same combo
    cur.execute("""
        SELECT COUNT(*) AS count FROM courses
        WHERE batch_id = %s AND department_id = %s AND semester = %s
    """, (batch_id, department_id, semester))
    count = cur.fetchone()['count'] + 1

    # Generate code: e.g., 23C201 for 1st course in 2023 batch, C dept, sem 2
    code = f"{batch_prefix}{department_id}{semester}{count:02d}"

    cur.close()
    return jsonify({'course_code': code})




@app.route('/admin/course/create', methods=['GET', 'POST'])
def create_course():
    if 'admin' not in session:
        return redirect('/admin/login')

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if request.method == 'POST':
        code = request.form['code']
        title = request.form['title']
        department_id = request.form['department_id']
        degree_id = request.form['degree_id']
        batch_id = request.form['batch_id']
        semester = request.form['semester']

        cur.execute("""
            INSERT INTO courses (code, title, department_id, degree_id, batch_id, semester)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (code, title, department_id, degree_id, batch_id, semester))
        mysql.connection.commit()
        cur.close()
        return redirect('/admin/dashboard')

    cur.execute("SELECT id, name FROM department")
    departments = cur.fetchall()
    cur.close()

    return render_template('create_course.html', departments=departments)




@app.route('/admin/course_offering/create', methods=['GET', 'POST'])
def create_course_offering():
    if 'admin' not in session:
        return redirect('/admin/login')
    
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Fetch all courses, classes, and teachers for the dropdowns
    cur.execute("SELECT code, title FROM courses")
    courses = cur.fetchall()

    cur.execute("SELECT id FROM class")
    classes = cur.fetchall()

    cur.execute("SELECT id, name FROM teachers")
    teachers = cur.fetchall()

    # If the form is submitted, insert the course offering into the database
    if request.method == 'POST':
        course_code = request.form['course_code']
        class_id = request.form['class_id']
        teacher_id = request.form['teacher_id']
        semester = request.form['semester']
        
        cur.execute("""INSERT INTO course_offerings (course_code, class_id, teacher_id, semester) 
                       VALUES (%s, %s, %s, %s)""",
                    (course_code, class_id, teacher_id, semester))
        mysql.connection.commit()
        cur.close()
        
        return redirect('/admin/dashboard')

    return render_template('create_course_offering.html', courses=courses, classes=classes, teachers=teachers)

@app.route('/admin/get_class_and_teachers', methods=['GET'])
def get_class_and_teachers():
    course_code = request.args.get('course_code')

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch course details to get department ID, degree ID, and batch ID
    cur.execute("""
        SELECT department_id, degree_id, batch_id 
        FROM courses 
        WHERE code = %s
    """, (course_code,))
    course = cur.fetchone()

    if not course:
        return jsonify({'classes': [], 'teachers': []})

    department_id = course['department_id']
    degree_id = course['degree_id']
    batch_id = course['batch_id']

    # Fetch classes that match department, degree, and batch
    cur.execute("""
        SELECT id 
        FROM class 
        WHERE department_id = %s AND degree_id = %s AND batch_id = %s
    """, (department_id, degree_id, batch_id))
    classes = cur.fetchall()

    # Fetch teachers in the same department
    cur.execute("""
        SELECT id, name 
        FROM teachers 
        WHERE department_id = %s
    """, (department_id,))
    teachers = cur.fetchall()

    return jsonify({'classes': classes, 'teachers': teachers})

@app.route('/admin/degree/create', methods=['GET', 'POST'])
def create_degree():
    if 'admin' not in session:
        return redirect('/admin/login')

    if request.method == 'POST':
        id = request.form['id']
        name = request.form['name']

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO degree (id, name) VALUES (%s, %s)", (id, name))
        mysql.connection.commit()
        cur.close()

        return redirect('/admin/dashboard')

    return render_template('create_degree.html')

@app.route('/admin/department/create', methods=['GET', 'POST'])
def create_department():
    if 'admin' not in session:
        return redirect('/admin/login')

    if request.method == 'POST':
        id = request.form['id']
        name = request.form['name']

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO department (id, name) VALUES (%s, %s)", (id, name))
        mysql.connection.commit()
        cur.close()

        return redirect('/admin/dashboard')

    return render_template('create_department.html')

@app.route('/admin/batch/create', methods=['GET', 'POST'])
def create_batch():
    if 'admin' not in session:
        return redirect('/admin/login')

    if request.method == 'POST':
        id = request.form['id']
        start = request.form['start']
        end = request.form['end']

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO batch (id, duration_start, duration_end) VALUES (%s, %s, %s)",
                    (id, start, end))
        mysql.connection.commit()
        cur.close()

        return redirect('/admin/dashboard')

    return render_template('create_batch.html')

@app.route('/admin/class/create', methods=['GET', 'POST'])
def create_class():
    if 'admin' not in session:
        return redirect('/admin/login')

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT id FROM degree")
    degrees = cur.fetchall()

    cur.execute("SELECT id FROM department")
    departments = cur.fetchall()

    cur.execute("SELECT id FROM batch")
    batches = cur.fetchall()

    if request.method == 'POST':
        id = request.form['id']
        degree_id = request.form['degree_id']
        batch_id = request.form['batch_id']
        department_id = request.form['department_id']

        cur.execute("INSERT INTO class (id, degree_id, batch_id, department_id) VALUES (%s, %s, %s, %s)",
                    (id, degree_id, batch_id, department_id))
        mysql.connection.commit()
        cur.close()

        return redirect('/admin/dashboard')

    return render_template('create_class.html', degrees=degrees, departments=departments, batches=batches)


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect('/admin/login')

@app.route('/') 
def index():
    return render_template('index.html')
    

if __name__ == '__main__':
    app.run(debug=True)
