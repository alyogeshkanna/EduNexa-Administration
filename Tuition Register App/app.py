from flask import Flask, render_template, request, jsonify, flash, redirect, url_for # type: ignore
import mysql.connector # type: ignore
import datetime
import calendar
import traceback # Used for logging detailed errors to the console
import decimal   # Used for precise financial calculations

app = Flask(__name__)
# IMPORTANT: Set a strong secret key for session management (used by flash messages).
# This should be a long, random, and unique string in a production environment.
app.secret_key = 'your_super_secret_key_here_please_change_this_for_production_use'

# Database connection details.
# Ensure these match your MySQL server configuration.
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Babu@02081971", # Replace with your actual MySQL root password
    database="TuitionCentreDB"
)

@app.route('/')
def index():
    """
    Renders the main registration page.
    Fetches available courses and batches from the database to dynamically
    populate dropdowns on the registration form.
    """
    try:
        # Fetch courses: course_id, course_name, and fee. Ordered alphabetically by name.
        cur1 = conn.cursor()
        cur1.execute("SELECT course_id, course_name, fee FROM Courses ORDER BY course_name ASC")
        courses = cur1.fetchall()
        cur1.close()

        # Fetch batches: batch_id and batch_name. Ordered alphabetically by name.
        cur2 = conn.cursor()
        cur2.execute("SELECT batch_id, batch_name FROM Batches ORDER BY batch_name ASC")
        batches = cur2.fetchall()
        cur2.close()

        return render_template('register.html', courses=courses, batches=batches)
    except Exception as e:
        # Log the full traceback for server-side debugging.
        traceback.print_exc()
        # Flash an error message and redirect to the home page.
        flash(f"Error loading registration page: {str(e)}. Please try again later.", "error")
        return redirect('/')


@app.route('/get_fee/<int:course_id>')
def get_fee(course_id):
    """
    API endpoint to fetch the fee for a given course ID.
    This is typically used by frontend JavaScript to auto-populate the
    course fee field when a course is selected in the registration form.
    """
    try:
        cur = conn.cursor()
        cur.execute("SELECT fee FROM Courses WHERE course_id = %s", (course_id,))
        fee = cur.fetchone()
        cur.close()
        # Return the fee as a float, or 0.0 if not found or None, in JSON format.
        return jsonify({'fee': float(fee[0]) if fee and fee[0] is not None else 0.0})
    except Exception as e:
        traceback.print_exc()
        print(f"Error fetching fee for course_id {course_id}: {str(e)}")
        # Return an error message in JSON format with a 500 status code.
        return jsonify({'fee': 0.0, 'error': f"Could not fetch fee: {str(e)}"}), 500


@app.route('/register', methods=['POST'])
def register():
    student_id_from_form = request.form.get('student_id')
    full_name = request.form.get('full_name')
    gender = request.form.get('gender')
    dob = request.form.get('dob')
    email = request.form.get('email')
    phone = request.form.get('phone')
    standard = request.form.get('standard')
    course_id = request.form.get('course_id')
    batch_id = request.form.get('batch_id')

    if not all([full_name, gender, dob, email, phone, standard, course_id, batch_id]):
        flash("All registration fields are required! Please fill in all details.", "error")
        return redirect('/')

    try:
        cur = conn.cursor()
        student_id = None

        if student_id_from_form and str(student_id_from_form).isdigit():
            student_id = int(student_id_from_form)
        else:
            # ✅ FIXED: Tuple needs a trailing comma
            cur.execute("SELECT student_id FROM students WHERE phone = %s", (phone,))
            result = cur.fetchone()
            if result:
                student_id = result[0]

        if student_id:
            # Check if enrollment already exists
            cur.execute("""
                SELECT 1 FROM enrollments
                WHERE student_id = %s AND course_id = %s AND batch_id = %s
            """, (student_id, course_id, batch_id))
            exists = cur.fetchone()

            if exists:
                flash("Student is already enrolled in this course and batch.", "info")
            else:
                cur.execute("""
                    INSERT INTO enrollments (student_id, course_id, batch_id)
                    VALUES (%s, %s, %s)
                """, (student_id, course_id, batch_id))
                flash("Student enrolled in new course/batch successfully.", "success")

            conn.commit()
            cur.close()
            return redirect('/students')

        # ✅ Student not found — proceed with new registration
        cur.execute("""
            INSERT INTO students (full_name, gender, dob, email, phone, standard)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (full_name, gender, dob, email, phone, standard))
        student_id = cur.lastrowid

        # Insert enrollment
        cur.execute("""
            INSERT INTO enrollments (student_id, course_id, batch_id)
            VALUES (%s, %s, %s)
        """, (student_id, course_id, batch_id))

        conn.commit()
        cur.close()
        flash(f"Student '{full_name}' registered and enrolled successfully!", "success")
        return redirect('/students')

    except mysql.connector.IntegrityError as e:
        traceback.print_exc()
        if e.errno == 1062:
            flash("Duplicate entry. Use 'Existing Student?' to re-enroll.", "error")
        else:
            flash(f"Database error: {str(e)}", "error")
        conn.rollback()
        return redirect('/')

    except Exception as e:
        traceback.print_exc()
        flash(f"Unexpected error: {str(e)}", "error")
        conn.rollback()
        return redirect('/')



@app.route('/search_student_by_phone')
def search_student_by_phone():
    phone = request.args.get('phone', '').strip()

    if not phone or not phone.isdigit() or len(phone) != 10:
        return jsonify({'success': False, 'message': 'Invalid phone number'}), 400

    conn = None  # Initialize to prevent UnboundLocalError

    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="Babu@02081971",  # Use your actual MySQL password
            database="TuitionCentreDB"
        )
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT s.student_id, s.full_name, s.dob, s.email, s.phone, s.gender, s.standard
            FROM students s
            WHERE s.phone = %s
            ORDER BY s.student_id DESC
            LIMIT 1
        """, (phone,))
        student = cur.fetchone()

        if not student:
            return jsonify({'success': False, 'message': 'Student not found'}), 404

        return jsonify({'success': True, 'student': student})

    except Exception as e:
        print("Error fetching student by phone:", e)
        return jsonify({'success': False, 'message': 'Server error'}), 500

    finally:
        if conn and conn.is_connected():
            cur.close()
            conn.close()



@app.route('/students')
def students():
    try:
        filters = {
            'name': request.args.get('name', '').strip(),
            'standard': request.args.get('standard', '').strip(),
            'course': request.args.get('course', '').strip(),
            'batch': request.args.get('batch', '').strip()
        }

        base_query = """
            SELECT 
                s.student_id, s.full_name, s.phone, s.email, s.gender, s.standard, s.dob,
                c.course_name, b.batch_name, b.start_time, b.end_time, b.days,
                e.course_id, e.batch_id, e.enrollment_id, c.fee
            FROM students s
            JOIN enrollments e ON s.student_id = e.student_id
            JOIN courses c ON e.course_id = c.course_id
            JOIN batches b ON e.batch_id = b.batch_id
        """

        where_clauses = []
        params = []

        if filters['name']:
            where_clauses.append("s.full_name LIKE %s")
            params.append(f"%{filters['name']}%")
        if filters['standard']:
            where_clauses.append("s.standard = %s")
            params.append(filters['standard'])
        if filters['course']:
            where_clauses.append("c.course_name LIKE %s")
            params.append(f"%{filters['course']}%")
        if filters['batch']:
            where_clauses.append("b.batch_name = %s")
            params.append(filters['batch'])

        if where_clauses:
            base_query += " WHERE " + " AND ".join(where_clauses)

        base_query += " ORDER BY s.student_id ASC"

        cur = conn.cursor()
        #print("QUERY:", base_query)
        #print("PARAMS:", params)
        cur.execute(base_query, tuple(params))
        rows = cur.fetchall()
        cur.close()

        now = datetime.datetime.now()
        current_year = now.year
        current_month = now.month

        cur_batches = conn.cursor()
        cur_batches.execute("SELECT batch_name FROM Batches ORDER BY batch_name ASC")
        all_batches_from_db = [batch[0] for batch in cur_batches.fetchall()]
        cur_batches.close()

        students_data = []

        for row in rows:
            student_id = row[0]
            enrollment_id = row[14]

            # Fetch paid months for this enrollment
            cur2 = conn.cursor()
            cur2.execute("""
                SELECT DISTINCT MONTH(month)
                FROM payments
                WHERE enrollment_id = %s AND YEAR(month) = %s
            """, (enrollment_id, current_year))
            paid_months = [r[0] for r in cur2.fetchall()]
            cur2.close()

            expected_months = list(range(1, current_month + 1))
            missing_months = [m for m in expected_months if m not in paid_months]

            if not missing_months:
                fee_status = "Paid"
            else:
                missing_names = [calendar.month_name[m] for m in missing_months]
                fee_status = f"Not Paid - Missing: {', '.join(missing_names)}"

            students_data.append({
                'student_id': row[0],
                'full_name': row[1],
                'phone': row[2],
                'email': row[3],
                'gender': row[4],
                'standard': row[5],
                'dob': row[6],
                'course': row[7],
                'batch': f"{row[8]} ({row[11]}) {str(row[9])[:-3]} - {str(row[10])[:-3]}",
                'course_id': row[12],
                'batch_id': row[13],
                'enrollment_id': row[14],
                'fee': float(row[15]) if row[15] is not None else 0.0,
                'fee_status': fee_status
            })

        return render_template(
            "students.html",
            students=students_data,
            current_month=now.strftime("%B %Y"),
            filters=filters,
            all_batches=all_batches_from_db
        )

    except Exception as e:
        traceback.print_exc()
        flash(f"Error fetching student list: {str(e)}. Please try again later.", "error")
        return redirect('/')



@app.route('/get_student/<int:student_id>')
def get_student(student_id):
    """
    API endpoint to fetch a single student's details by ID.
    Used by the 'Existing Student?' feature in register.html to pre-fill form fields.
    """
    try:
        cursor = conn.cursor(dictionary=True) # Return results as dictionaries for easy access by key.
        query = "SELECT student_id, full_name, gender, dob, email, phone, standard, course_id, batch_id FROM students WHERE student_id = %s"
        cursor.execute(query, (student_id,))
        student = cursor.fetchone()
        cursor.close()

        if student:
            # Convert date objects (like 'dob') to ISO format strings for JSON serialization.
            if 'dob' in student and isinstance(student['dob'], datetime.date):
                student['dob'] = student['dob'].isoformat()
            return jsonify(success=True, student=student)
        else:
            return jsonify(success=False, message="Student not found with the provided ID.")
    except Exception as e:
        traceback.print_exc()
        print(f"Error in get_student API for ID {student_id}: {str(e)}") # Log error on server.
        return jsonify(success=False, message=f"An error occurred while fetching student details: {str(e)}"), 500

@app.route('/get_student_info/<int:student_id>', methods=['GET'])
def get_student_info(student_id):
    cursor = conn.cursor()
    query = '''
        SELECT c.course_id, c.course_name, c.fee
        FROM courses c
        JOIN student_courses sc ON c.course_id = sc.course_id
        WHERE sc.student_id = %s
    '''
    cursor.execute(query, (student_id,))
    results = cursor.fetchall()
    cursor.close()

    # Return all courses the student is enrolled in
    courses = [{'course_id': cid, 'course_name': cname, 'fee': float(fee)} for cid, cname, fee in results]
    return jsonify({'courses': courses})


@app.route('/search_student_by_details', methods=['GET'])
def search_student_by_details():
    """
    API endpoint to search for a student by student_id, full_name, and dob.
    Returns the full student record if a match is found.
    """
    student_id = request.args.get('student_id')
    full_name = request.args.get('full_name')
    dob = request.args.get('dob')

    query_parts = []
    params = []

    if student_id:
        query_parts.append("student_id = %s")
        params.append(student_id)
    if full_name:
        query_parts.append("full_name = %s")
        params.append(full_name)
    if dob:
        query_parts.append("dob = %s")
        params.append(dob)

    if not query_parts: # Ensure at least one parameter is provided for a valid search
        return jsonify(success=False, message="At least one search parameter (Student ID, Name, or DOB) is required."), 400

    query = "SELECT student_id, full_name, gender, dob, email, phone, standard FROM students WHERE " + " AND ".join(query_parts)

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, tuple(params))
        student = cursor.fetchone() # Fetch the first matching student
        cursor.close()

        if student:
            # Convert date objects (like 'dob') to ISO format strings for JSON serialization.
            if 'dob' in student and isinstance(student['dob'], datetime.date):
                student['dob'] = student['dob'].isoformat()
            return jsonify(success=True, student=student)
        else:
            return jsonify(success=False, message="No matching student found with the provided details."), 404
    except Exception as e:
        traceback.print_exc()
        print(f"Error in search_student_by_details API: {str(e)}")
        return jsonify(success=False, message=f"An error occurred while searching for student: {str(e)}"), 500

@app.route('/fee_payment', methods=['GET', 'POST'])
def fee_payment():
    if request.method == 'POST':
        data = request.form
        enrollment_id = data.get('enrollment_id')
        month_str = data.get('month')  # Format YYYY-MM
        amount_paid = data.get('amount_paid')
        payment_mode = data.get('payment_mode')

        print(f"DEBUG: Form Data Received -> Enrollment ID: {enrollment_id}, Month: {month_str}, Amount Paid: {amount_paid}, Payment Mode: {payment_mode}")

        if not all([enrollment_id, month_str, amount_paid, payment_mode]):
            flash("All payment fields are required! Please fill in all details.", "error")
            print("DEBUG: Missing field in POST data")
            return redirect('/fee_payment')

        try:
            month_date = datetime.datetime.strptime(month_str, "%Y-%m").date().replace(day=1)
            payment_date = datetime.date.today()

            print(f"DEBUG: Parsed Dates -> Payment Date: {payment_date}, Month: {month_date}")

            cur = conn.cursor()

            # ✅ Step 1A: Fetch student_id, course_id, batch_id from enrollments
            cur.execute("SELECT student_id, course_id, batch_id FROM enrollments WHERE enrollment_id = %s", (enrollment_id,))
            result = cur.fetchone()

            if not result:
                flash(f"Enrollment ID {enrollment_id} not found.", "error")
                print(f"DEBUG: No enrollment found for ID {enrollment_id}")
                cur.close()
                return redirect('/fee_payment')

            student_id, course_id, batch_id = result
            print(f"DEBUG: Enrollment Info -> Student ID: {student_id}, Course ID: {course_id}, Batch ID: {batch_id}")

            # ✅ Step 1B: Check for existing payment
            cur.execute("""
                SELECT 1 FROM payments 
                WHERE student_id = %s AND course_id = %s AND batch_id = %s AND month = %s
            """, (student_id, course_id, batch_id, month_date))

            if cur.fetchone():
                flash(f"Payment already exists for {month_date.strftime('%B %Y')} for this enrollment.", "error")
                print("DEBUG: Duplicate payment found.")
                cur.close()
                return redirect('/fee_payment')

            # ✅ Step 1C: Insert payment
            print("DEBUG: Inserting payment into database...")
            cur.execute("""
                INSERT INTO payments (student_id, course_id, batch_id, enrollment_id, amount_paid, payment_date, payment_mode, month)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (student_id, course_id, batch_id, enrollment_id, amount_paid, payment_date, payment_mode, month_date))

            conn.commit()
            cur.close()
            flash("Payment recorded successfully!", "success")
            print("DEBUG: Payment insert success.")
            return redirect('/fee_payment')

        except ValueError:
            flash("Invalid date or amount format.", "error")
            print("DEBUG: ValueError during date parsing or amount conversion")
            conn.rollback()
            return redirect('/fee_payment')
        except Exception as e:
            traceback.print_exc()
            print(f"DEBUG: Unexpected exception: {str(e)}")
            flash(f"An unexpected error occurred: {str(e)}", "error")
            conn.rollback()
            return redirect('/fee_payment')

    else:
        try:
            cur = conn.cursor()

            # ✅ Show available enrollments
            cur.execute("""
                SELECT 
                    e.enrollment_id,     
                    s.student_id,        
                    s.full_name,         
                    c.course_name,       
                    c.course_id,         
                    c.fee,
                    b.batch_name         
                FROM students s
                JOIN enrollments e ON s.student_id = e.student_id
                JOIN courses c ON e.course_id = c.course_id
                JOIN batches b ON e.batch_id = b.batch_id
                ORDER BY s.full_name
            """)

            students_for_dropdown = cur.fetchall()
            cur.close()
            print(f"DEBUG: Loaded {len(students_for_dropdown)} enrollments for dropdown")

            return render_template("fee_payment.html", students=students_for_dropdown)

        except Exception as e:
            traceback.print_exc()
            print(f"DEBUG: Error loading fee_payment page: {str(e)}")
            flash(f"Error loading fee payment page: {str(e)}", "error")
            return redirect('/')





@app.route('/view_payments')
def view_payments():
    """
    Displays all fee payment records. Provides an option to filter records by student ID.
    For a filtered student, it also calculates and displays total paid, total course fee,
    and remaining balance.
    """
    student_id = request.args.get('student_id') # Get student_id from query parameters for filtering.
    base_query = """
        SELECT 
            s.full_name, s.student_id, s.standard, 
            b.batch_name, c.course_name,
            DATE_FORMAT(p.month, '%M %Y') AS month_paid,
            p.amount_paid, p.payment_mode, p.payment_date
        FROM students s
        JOIN enrollments e ON s.student_id = e.student_id
        JOIN payments p ON e.enrollment_id = p.enrollment_id
        JOIN courses c ON e.course_id = c.course_id
        JOIN batches b ON e.batch_id = b.batch_id
    """



    params = []
    if student_id:
        base_query += " WHERE s.student_id = %s"
        params.append(student_id)


    # Order results by payment date (descending) and then by month (descending).
    base_query += " ORDER BY p.payment_date DESC, p.month DESC"

    try:
        cur = conn.cursor()
        cur.execute(base_query, params)
        raw_records = cur.fetchall() # Fetch all payment records.

        records = []
        for row in raw_records:
            # Format date objects into readable strings for display.
            formatted_month = str(row[5])
            formatted_payment_date = row[8].strftime('%Y-%m-%d') if isinstance(row[8], datetime.date) else str(row[8])

            new_row = list(row) # Convert tuple to list to allow modification.
            new_row[5] = formatted_month # Update month field with formatted string.
            new_row[8] = formatted_payment_date # Update payment_date field with formatted string.
            records.append(tuple(new_row)) # Add the modified record as a tuple.

        # Initialize with Decimal('0.00') to ensure all financial calculations are done with Decimal type.
        total_paid = decimal.Decimal('0.00')
        course_fee = decimal.Decimal('0.00')
        balance_remaining = decimal.Decimal('0.00')

        if student_id:
            # Calculate total amount paid by the filtered student.
            cur.execute("""
                SELECT SUM(p.amount_paid)
                FROM payments p
                JOIN enrollments e ON p.enrollment_id = e.enrollment_id
                WHERE e.student_id = %s
            """, (student_id,))
            total_paid_result = cur.fetchone()[0]
            # Convert result to Decimal if not None, otherwise Decimal('0.00').
            total_paid = decimal.Decimal(total_paid_result) if total_paid_result is not None else decimal.Decimal('0.00')

            # Get the total course fee for the filtered student's enrolled course.
            cur.execute("""
                SELECT
                    c.fee, c.duration_in_months
                FROM students s
                JOIN enrollments e ON s.student_id = e.student_id
                JOIN courses c ON e.course_id = c.course_id
                WHERE s.student_id = %s
                LIMIT 1
            """, (student_id,))
            fee_data = cur.fetchone()


            if fee_data:
                # Convert fee_data components to Decimal before multiplication for precision.
                fee_per_month = decimal.Decimal(str(fee_data[0])) if fee_data[0] is not None else decimal.Decimal('0.00')
                duration = decimal.Decimal(str(fee_data[1])) if fee_data[1] is not None else decimal.Decimal('0')
                
                course_fee = fee_per_month * duration
                balance_remaining = course_fee - total_paid
            else:
                # If no course data found for the student, assume course fee is 0.
                course_fee = decimal.Decimal('0.00')
                balance_remaining = -total_paid # Any amount paid is considered overpayment if no fee is defined.

        cur.close()
        return render_template('view_payments.html',
                               records=records,
                               total_paid=total_paid,
                               course_fee=course_fee,
                               balance_remaining=balance_remaining)
    except Exception as e:
        traceback.print_exc()
        flash(f"Error fetching payment records: {str(e)}. Please try again later.", "error")
        return redirect('/') # Redirect to home on error.


@app.route('/attendance', methods=['GET', 'POST'])
def attendance():
    """
    Manages student attendance.
    - Allows marking attendance for a specific date and batch.
    - Displays daily attendance count.
    - Provides student-wise attendance summaries with optional date range filtering.
    """
    try:
        cur = conn.cursor(dictionary=True) # Use dictionary cursor for easier access to column names.

        # Get all batches for the dropdown filter, ordered alphabetically by name.
        cur.execute("SELECT batch_id, batch_name FROM batches ORDER BY batch_name ASC")
        batches = cur.fetchall()

        # Retrieve selected batch and date from form (POST) or URL parameters (GET).
        selected_batch = request.form.get('batch_id', request.args.get('batch_id'))
        selected_date = request.form.get('date', request.args.get('date'))
        from_date = request.form.get('from_date', request.args.get('from_date'))
        to_date = request.form.get('to_date', request.args.get('to_date'))
        action = request.form.get('action') # Distinguish between 'Load Students' and 'submit_attendance'.

        students_for_attendance_table = [] # List to hold students for marking attendance.
        attendance_summary = [] # List for student-wise attendance summary.
        daily_count = None # For total present count on a specific date.

        # --- Attendance Submission Logic (POST request for 'submit_attendance') ---
        if request.method == 'POST' and action == 'submit_attendance' and selected_batch and selected_date:
            try:
                for key in request.form:
                    if key.startswith('status_'):
                        student_id = key.split('_')[1]
                        status = request.form[key]
                        # Use ON DUPLICATE KEY UPDATE to handle re-marking attendance for the same student/date.
                        # This ensures only one entry per student per day, updating status if it changes.
                        cur.execute("""
                            INSERT INTO attendance (student_id, batch_id, date, status)
                            VALUES (%s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE status=%s
                        """, (student_id, selected_batch, selected_date, status, status))
                conn.commit() # Commit all attendance updates for the batch.
                flash("Attendance submitted successfully!", "success")
            except Exception as e:
                traceback.print_exc()
                flash(f"Error submitting attendance: {str(e)}. Please try again.", "error")
                conn.rollback() # Rollback on error.
            # Redirect to the same page with current batch and date to show updated status.
            return redirect(f'/attendance?batch_id={selected_batch}&date={selected_date}')

        # --- Load Students for Attendance Marking Table ---
        # This block runs when 'Load Students' is clicked, or after attendance is submitted,
        # or on initial GET request if batch/date are already in URL parameters.
        if selected_batch and selected_date and (action == 'Load Students' or action == 'submit_attendance' or request.method == 'GET'):
            cur.execute("""
                SELECT s.student_id, s.full_name,
                    COALESCE(a.status, 'Absent') as status
                FROM students s
                JOIN enrollments e ON s.student_id = e.student_id
                LEFT JOIN attendance a ON s.student_id = a.student_id AND a.date = %s AND a.batch_id = %s
                WHERE e.batch_id = %s
                ORDER BY s.full_name
            """, (selected_date, selected_batch, selected_batch))

            students_for_attendance_table = cur.fetchall()

        # --- Daily Present Count for Selected Date ---
        if selected_date and selected_batch:
            cur.execute("""
                SELECT COUNT(*) AS total_present
                FROM attendance
                WHERE batch_id = %s AND date = %s AND status = 'Present'
            """, (selected_batch, selected_date))
            daily_count = cur.fetchone()

        # --- Student-wise Attendance Summary (Total Present Days) ---
        if selected_batch: # Always show summary for the selected batch.
            summary_query = """
                SELECT s.student_id, s.full_name,
                    SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_days
                FROM students s
                JOIN enrollments e ON s.student_id = e.student_id
                LEFT JOIN attendance a ON s.student_id = a.student_id AND a.batch_id = e.batch_id
                WHERE e.batch_id = %s
            """

            summary_params = [selected_batch]

            if from_date and to_date: # Apply date range filter if both dates are provided.
                summary_query += " AND a.date BETWEEN %s AND %s"
                summary_params.extend([from_date, to_date])
            
            summary_query += " GROUP BY s.student_id, s.full_name ORDER BY s.full_name"

            cur.execute(summary_query, tuple(summary_params))
            attendance_summary = cur.fetchall()

        cur.close()
        return render_template(
            'attendance.html',
            batches=batches,
            students=students_for_attendance_table, # Students list for marking attendance.
            selected_batch=selected_batch,
            selected_date=selected_date,
            from_date=from_date,
            to_date=to_date,
            daily_count=daily_count,
            attendance_summary=attendance_summary
        )
    except Exception as e:
        traceback.print_exc()
        flash(f"Error loading attendance page: {str(e)}. Please try again later.", "error")
        return redirect('/') # Redirect to home on error.


@app.route("/courses.html")
def courses_page():
    try:
        cur = conn.cursor()
        cur.execute("SELECT AUTO_INCREMENT FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'TuitionCentreDB' AND TABLE_NAME = 'courses'")
        next_course_id = cur.fetchone()[0]
        return render_template("courses.html", next_course_id=next_course_id)
    except Exception as e:
        print("Error loading courses page:", e)
        flash("Failed to load course page", "error")
    return redirect("/")


@app.route('/api/add-course', methods=['POST'])
def add_course_api():
    """Handles HTML form submission for adding a course."""

    course_name = request.form.get('course_name')
    subject = request.form.get('subject')
    duration_in_months = request.form.get('duration_in_months')
    fee = request.form.get('fee')

    # Validate required fields
    if not all([course_name, subject, duration_in_months, fee]):
        flash('All fields are required!', 'danger')
        return redirect('/courses.html')

    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO Courses (course_name, subject, duration_in_months, fee)
            VALUES (%s, %s, %s, %s)
        """, (course_name, subject, duration_in_months, fee))
        conn.commit()
        cur.close()

        flash('Course added successfully!', 'success')
        return redirect('/courselist.html')
    except mysql.connector.IntegrityError as e:
        traceback.print_exc()
        flash(f'Database integrity error: {str(e)}', 'danger')
        return redirect('/courses.html')
    except Exception as e:
        traceback.print_exc()
        flash(f'Unexpected error: {str(e)}', 'danger')
        return redirect('/courses.html')

@app.route('/courselist.html')
def courselist_page():
    """Renders the 'List Of Courses' page."""
    return render_template('courselist.html')

@app.route('/api/get-courses', methods=['GET'])
def get_courses_api():
    """
    API endpoint to fetch all courses from the database.
    Returns the course data as JSON.
    """
    try:
        cur = conn.cursor(dictionary=True) # Fetch as dictionaries for easier JSON conversion.
        cur.execute("SELECT course_id, course_name, subject, duration_in_months, fee FROM Courses ORDER BY course_id ASC")
        courses = cur.fetchall()
        cur.close()
        return jsonify(courses), 200
    except Exception as e:
        traceback.print_exc()
        print(f"Error fetching courses: {str(e)}") # Log error on server.
        return jsonify({'message': f"Error fetching courses: {str(e)}. Please try again later."}), 500


@app.route('/api/update-course', methods=['POST'])
def update_course():
    """API endpoint to update an existing course's details."""
    data = request.get_json()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE Courses
            SET course_name = %s, subject = %s, duration_in_months = %s, fee = %s
            WHERE course_id = %s
        """, (
            data['course_name'], data['subject'], data['duration_in_months'], data['fee'], data['course_id']
        ))
        conn.commit()
        cur.close()
        return jsonify({'message': 'Course updated successfully!'}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({'message': f"Update failed: {str(e)}. Please check your input."}), 500


@app.route('/api/delete-course/<course_id>', methods=['DELETE'])
def delete_course(course_id):
    """
    API endpoint to delete a course by its ID.
    Includes a check for associated student records to prevent foreign key constraint errors.
    """
    try:
        cur = conn.cursor()
        
        # Check for dependent students before deleting the course.
        cur.execute("SELECT COUNT(*) FROM enrollments WHERE course_id = %s", (course_id,))
        student_count = cur.fetchone()[0]

        if student_count > 0:
            cur.close()
            return jsonify({
                'message': f"Delete failed: Cannot delete Course ID {course_id} because it has {student_count} associated students. Please reassign or delete these students first."
            }), 409 # 409 Conflict status code.

        cur.execute("DELETE FROM Courses WHERE course_id = %s", (course_id,))
        conn.commit()
        cur.close()
        return jsonify({'message': 'Course deleted successfully!'}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({'message': f"Delete failed: {str(e)}. Please try again."}), 500


@app.route("/batches")
def batches_page():
    cursor = conn.cursor()
    cursor.execute("SELECT AUTO_INCREMENT FROM information_schema.TABLES WHERE TABLE_SCHEMA = 'TuitionCentreDB' AND TABLE_NAME = 'batches'")
    result = cursor.fetchone()
    next_batch_id = result[0] if result else None
    cursor.close()
    return render_template("batches.html", next_batch_id=next_batch_id)


@app.route('/api/add-batch', methods=['POST'])
def add_batch_api():
    try:
        batch_name = request.form.get('batch_name') 
        start_time = request.form.get('start_time') + ":00"  # Ensure HH:MM:SS
        end_time = request.form.get('end_time') + ":00"
        days = request.form.get('days') 
        cursor = conn.cursor()
        insert_query = "INSERT INTO batches (batch_name, start_time, end_time, days) VALUES (%s, %s, %s, %s)"
        cursor.execute(insert_query, (batch_name, start_time, end_time, days))
        conn.commit()
        inserted_id = cursor.lastrowid  # 🔥 get the generated ID
        flash(f"Batch added successfully with ID: {inserted_id}", "success")
        return redirect(url_for("batches_page"))
    except Exception as e:
        conn.rollback()
        flash("An error occurred: " + str(e), "error")
    return redirect(url_for("batches_page"))






@app.route('/batchlist.html')
def batchlist_page():
    """Renders the 'List Of Batches' page."""
    return render_template('batchlist.html')

@app.route('/api/get-batches', methods=['GET'])
def get_batches_api():
    """
    API endpoint to fetch all batches from the database.
    Returns the batch data as JSON, handling timedelta objects for time fields.
    """
    try:
        cur = conn.cursor(dictionary=True) # Fetch results as dictionaries.
        cur.execute("SELECT batch_id, batch_name, start_time, end_time, days FROM Batches ORDER BY batch_id ASC")
        batches_raw = cur.fetchall()
        cur.close()

        # Process batches to ensure time fields are string formatted for JSON serialization.
        batches_clean = []
        for batch in batches_raw:
            clean_batch = dict(batch) # Create a mutable copy of the dictionary.

            # Convert datetime.timedelta objects (from MySQL TIME type) to string (HH:MM:SS).
            if isinstance(clean_batch.get('start_time'), datetime.timedelta):
                total_seconds = int(clean_batch['start_time'].total_seconds())
                hours, remainder = divmod(total_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                clean_batch['start_time'] = f"{hours:02}:{minutes:02}:{seconds:02}"
            
            if isinstance(clean_batch.get('end_time'), datetime.timedelta):
                total_seconds = int(clean_batch['end_time'].total_seconds())
                hours, remainder = divmod(total_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                clean_batch['end_time'] = f"{hours:02}:{minutes:02}:{seconds:02}"
            
            batches_clean.append(clean_batch)

        return jsonify(batches_clean), 200
    except Exception as e:
        traceback.print_exc() # Print full traceback to console for debugging.
        print(f"Error fetching batches: {str(e)}")
        return jsonify({'message': f"Error fetching batches: {str(e)}. Please try again later."}), 500


@app.route('/api/update-batch', methods=['POST'])
def update_batch():
    """API endpoint to update an existing batch's details."""
    data = request.get_json()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE Batches
            SET batch_name = %s, start_time = %s, end_time = %s, days = %s
            WHERE batch_id = %s
        """, (
            data['batch_name'], data['start_time'], data['end_time'], data['days'], data['batch_id']
        ))
        conn.commit()
        cur.close()
        return jsonify({'message': 'Batch updated successfully!'}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({'message': f"Update failed: {str(e)}. Please check your input."}), 500


@app.route('/api/delete-batch/<batch_id>', methods=['DELETE'])
def delete_batch(batch_id):
    """
    API endpoint to delete a batch by its ID.
    Includes a check for associated student records to prevent foreign key constraint errors.
    """
    try:
        cur = conn.cursor()

        # Check for dependent students before deleting the batch.
        cur.execute("SELECT COUNT(*) FROM enrollments WHERE batch_id = %s", (batch_id,))

        student_count = cur.fetchone()[0]

        if student_count > 0:
            cur.close()
            return jsonify({
                'message': f"Delete failed: Cannot delete Batch ID {batch_id} because it has {student_count} associated students. Please reassign or delete these students first."
            }), 409 # 409 Conflict status code.

        # If no dependent students, proceed with deletion.
        cur.execute("DELETE FROM Batches WHERE batch_id = %s", (batch_id,))
        conn.commit()
        cur.close()
        return jsonify({'message': 'Batch deleted successfully!'}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({'message': f"Delete failed: An unexpected error occurred: {str(e)}. Please try again."}), 500


if __name__ == '__main__':
    # Run the Flask application in debug mode.
    # debug=True allows for automatic code reloading and provides a debugger in the browser.
    # It should be set to False in a production environment.
    app.run(debug=True)