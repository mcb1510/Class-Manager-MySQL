import mysql.connector

class ClassManagerShell:
    def __init__(self):
        self.active_class_id = None  #Stores the currently active selected class

        #connect to DB when program starts
        self.conn = mysql.connector.connect(
            host= "127.0.0.1",         #  local sandbox
            port= 58659,               #  sandbox port
            user= "msandbox",          
            password= "liverpool",      
            database= "class_manager"    
        )
        self.cursor = self.conn.cursor()

    ##################################################################################################################
    ######################################## Grade Reporting ######################################################### 
    ##################################################################################################################

    ############################################################################################
    ## Gradebook – show the current class’s gradebook: students (username, student ID, and name), 
    ## along with their total grades in the class. 
    def gradebook(self):
        if self.active_class_id is None:
            print("Select a class first to see the gradebook.")
            return

        # Get the total weight from active categories (those with at least one assignment)
        self.cursor.execute(
            """
            SELECT SUM(weight)
            FROM category
            WHERE class_id = %s
            AND category.category_id IN (
                SELECT DISTINCT assignment.category_id
                FROM assignment
                WHERE class_id = %s
            )
            """,
            (self.active_class_id, self.active_class_id)
        )
        total_weight_result = self.cursor.fetchone()
        total_weight = total_weight_result[0]

        if total_weight is None or total_weight == 0:
            print("No categories with assignments found for this class.")
            return

        self.cursor.execute(
             """
            SELECT
            student.student_username,
            student.student_id,
            student.student_name,

            -- Total Grade:
            ROUND(SUM(
                CASE
                WHEN total.total_points > 0 THEN total.scored_points / total.total_points * total.weight
                ELSE 0
                END
            ) * 100 / %s, 2) AS total_grade,

            -- Attempted Grade:
            ROUND(SUM(
                CASE
                WHEN total.attempted_points > 0 THEN total.scored_points / total.attempted_points * total.weight
                ELSE 0
                END
            ) * 100 /
            NULLIF(SUM(
                CASE
                WHEN total.attempted_points > 0 THEN total.weight
                ELSE 0
                END
            ), 0), 2) AS attempted_grade

            FROM student
            JOIN enroll ON student.student_id = enroll.student_id

            LEFT JOIN (
            SELECT
                enroll.student_id,
                category.category_id,
                category.weight,

                SUM(assignment.assignment_point_value) AS total_points,
                SUM(CASE WHEN grade.score IS NOT NULL THEN grade.score ELSE 0 END) AS scored_points,
                SUM(CASE WHEN grade.score IS NOT NULL THEN assignment.assignment_point_value ELSE 0 END) AS attempted_points

            FROM enroll
            JOIN assignment ON enroll.class_id = assignment.class_id
            JOIN category ON assignment.category_id = category.category_id
            LEFT JOIN grade ON grade.assignment_id = assignment.assignment_id
                AND grade.student_id = enroll.student_id

            WHERE assignment.class_id = %s
            GROUP BY enroll.student_id, category.category_id
            ) AS total ON student.student_id = total.student_id

            WHERE enroll.class_id = %s
            GROUP BY student.student_id
            ORDER BY student.student_username;

        """,
            (total_weight, self.active_class_id, self.active_class_id)
        )

        results = self.cursor.fetchall()

        if not results:
            print("No students or grades found.")
            return

        print("\nGradebook:")
        print(f"{'Username':<15} {'ID':<6} {'Name':<25} {'Total Grade':<15} {'Attempted Grade':<17}")
        print("-" * 80)
        for username, student_id, name, total, attempted in results:
            total = total if total is not None else 0.0
            attempted = attempted if attempted is not None else 0.0
            print(f"{username:<15} {student_id:<6} {name:<25} {total:<15.2f} {attempted:<17.2f}")




    #############################################################################################
    # Show student’s current grade: all assignments, visually 
    # grouped by category, with the student’s grade (if they have one). Show subtotals for each 
    # category, along with the overall grade in the class.
    def show_grades(self, args):
        if self.active_class_id is not None:
            if len(args) != 1:
                print("Please enter a valid format to see current grades.")
                print("[student-grades] [username]")
                return
            
            username = args[0]

            # We get the id of the student
            self.cursor.execute(
                """
                SELECT student_id
                FROM student
                WHERE student_username = %s 
                """,(username,)
            )

            result_id = self.cursor.fetchone()
            if not result_id:
                print("Error. Student does not exist.")
                return
            
            student_id = result_id[0]

            # We get all the assignments
            self.cursor.execute(
                """
                SELECT
                    category.category_name,
                    category.weight,
                    assignment.assignment_name,
                    assignment.assignment_point_value,
                    grade.score
                FROM assignment
                JOIN category ON assignment.category_id = category.category_id
                LEFT JOIN grade ON assignment.assignment_id = grade.assignment_id AND grade.student_id = %s
                WHERE assignment.class_id = %s
                ORDER BY category.category_name, assignment.assignment_name 
                """,(student_id, self.active_class_id)
            )

            result = self.cursor.fetchall()
            if not result:
                print("No assignments or categories found for this class")
                return
            
            # Display Scores
            current_category = None
            points_scored = 0
            points_possible = 0

            for row in result:
                category, weight, assignment, point_value, score = row
                point_value = float(point_value)

                if score is not None:
                    score_display = float(score)
                else:
                    score_display = "-"

                if category != current_category and current_category is not None and points_possible > 0:
                    percent = (points_scored / points_possible) * 100
                    print(f"Subtotal: {points_scored}/{points_possible} - Grade:{round(percent, 2)}%")
                    points_scored = 0
                    points_possible = 0

                if category != current_category:
                    print(f"\n{category} ({weight}%)")
                    current_category = category

                points_possible += point_value
                if score is not None:
                    points_scored += float(score)

                print(f"    - {assignment} : {score_display}/{point_value}")
            
            # Final category subtotal (last group)
            if current_category and points_possible > 0:
                percent = (points_scored / points_possible) * 100
                print(f"Subtotal: {points_scored}/{points_possible} - Grade:{round(percent, 2)}%")

            # Total and Attempted Grade Calculation with rescaled weights
            self.cursor.execute("""
            SELECT 
                category.category_name,
                category.weight,
                SUM(assignment.assignment_point_value) AS total_points,
                SUM(CASE WHEN grade.score IS NOT NULL THEN grade.score ELSE 0 END) AS scored_points,
                SUM(CASE WHEN grade.score IS NOT NULL THEN assignment.assignment_point_value ELSE 0 END) AS attempted_points
            FROM category
            JOIN assignment ON category.category_id = assignment.category_id
            LEFT JOIN grade ON grade.assignment_id = assignment.assignment_id AND grade.student_id = %s
            WHERE assignment.class_id = %s
            GROUP BY category.category_id
            """, (student_id, self.active_class_id))

            rows = self.cursor.fetchall()

            total_grade = 0.0
            attempted_grade = 0.0
            total_weight = 0.0
            attempted_weight = 0.0

            for category, weight, total_points, scored_points, attempted_points in rows:
                weight = float(weight)
                total_points = float(total_points)
                scored_points = float(scored_points)
                attempted_points = float(attempted_points)

                if total_points > 0:
                    total_grade += (scored_points / total_points) * weight
                    total_weight += weight

                if attempted_points > 0:
                    attempted_grade += (scored_points / attempted_points) * weight
                    attempted_weight += weight

            if total_weight > 0:
                print(f"\n Total Grade: {round(total_grade * (100 / total_weight), 2)}%")
            else:
                print("\n Total Grade: N/A")

            if attempted_weight > 0:
                print(f"Attempted Grade: {round(attempted_grade * (100 / attempted_weight), 2)}%")
            else:
                print("Attempted Grade: N/A")

        else:
            print("Select a class first")


    
    ##################################################################################################################
    ################################## Student Management ############################################################
    ##################################################################################################################
    # Assign the grade ‘grade’ for student with user name ‘username’ for assignment ‘assignmentname’. 
    # If the student already has a grade for that assignment, replace it. If the number of points 
    # exceeds the number of points configured for the assignment, print a warning (showing the number
    # of points configured)
    def grade_assignment(self,args):
        if self.active_class_id is not None:
            if len(args) != 3:
                print("Please enter a valid format to assign a grade.")
                print("[grade] [assignmentname] [username] [grade]")
                return
            
            assignment_name = args[0]
            username = args[1]
            grade = args[2]

             # Make sure grade is decimal before we do anything to the DB
            try:
                grade = float(grade)
            except ValueError:
                print("Grade should be a number")
                return

            # We get the id of the student
            self.cursor.execute(
                """
                SELECT student_id
                FROM student
                WHERE student_username = %s 
                """,(username,)
                )

            result_id= self.cursor.fetchone()
            if not result_id:
                print("Error. Student does not exist.")
                return
            
            student_id = result_id[0]

            # We get the id of the assignment
            self.cursor.execute(
                """
                SELECT assignment_id,assignment_point_value
                FROM assignment
                WHERE assignment_name = %s AND assignment.class_id = %s
                """,(assignment_name,self.active_class_id)
                )

            result_assignment = self.cursor.fetchone()
            if not result_assignment:
                print("Error. Assignment does not exist in this class.")
                return
            
            assignment_id = result_assignment[0]
            max_score = result_assignment[1]

            if grade > max_score:
                print(f"Warning: Max number of points for the assignment are: {max_score}")
                #return 

                
            # We add grade if the assignment and student exist
            try:
                self.cursor.execute(
                    """
                    INSERT INTO grade (student_id, assignment_id,score) 
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE score = %s
                    """,(student_id, assignment_id,grade,grade)
                    )
                self.conn.commit()
                print("Grade added/updated succesfully")
            
            except mysql.connector.Error as err:
                print("Error grading assignment:", err) # This catches any MySQL error related
            
        else:
            print("Select a class first")    


    #################################################################################################################
    # Adds a student and enrolls them in the current class. If the student already exists, enroll them in the class; 
    # if the name provided does not match their stored name, update the name but print a warning
    # that the name is being changed.
    def add_student(self,args):
        if self.active_class_id is not None:
            if len(args) !=4:
                print("Please enter a valid format to enroll a student in the class.")
                print("[add-student] [username] [studentid] [Last] [First]")
                return
            
            username = args[0]
            student_id = int(args[1])
            last = args [2]
            first = args[3]
            full_name = f"{first} {last}"
            email = f"{username}@example.com"

            # We check if the student id is already in the system with a different user
            self.cursor.execute(
                """
                SELECT student_username
                FROM student
                WHERE student_id = %s 
                """,(student_id,)
                )
            id_found = self.cursor.fetchone()
            if id_found and id_found[0] != username:
                print("This student ID is already used by another student")
                return


            # We get the id and name of the student
            self.cursor.execute(
                """
                SELECT student_id,student_name
                FROM student
                WHERE student_username = %s 
                """,(username,)
                )

            result = self.cursor.fetchone()
            if not result:
                #we need to add the student
                try:
                    self.cursor.execute(
                    """
                    INSERT INTO student(student_id, student_name, student_username,student_email) 
                    VALUES (%s,%s,%s, %s)
                    """,(student_id,full_name, username, email)
                    )
                    self.conn.commit()
                    print("Student sucessfully created.")

                except mysql.connector.Error as err:
                    print("Error adding student:", err)
                    return
                
                
            else:
                # Student exist
                student_id, current_name = result
                if current_name != full_name:
                    print(f"Warning, name does not match, updating '{current_name}' to '{full_name}'")
                    self.cursor.execute(
                        """
                        UPDATE student
                        SET student_name = %s
                        WHERE student_id = %s
                        """,(full_name, student_id)
                    )
                    self.conn.commit()

            # We enroll student 
            try:
                self.cursor.execute(
                    """
                    INSERT INTO enroll (class_id, student_id) 
                    VALUES (%s, %s)
                    """,(self.active_class_id, student_id)
                    )
                self.conn.commit()
                print("Student sucessfully enrolled in the class.")
            
            except mysql.connector.IntegrityError:
                print("Student is already enrolled in this class.")
            except mysql.connector.Error as err:
                print("Error enrolling student:", err) # This catches any MySQL error related
            
        else:
            print("Select the class you want to enroll the student first")
    
    #####################################################################################################################
    # Enrolls an already-existing student in the current class. if the specified student does not exist, report an error
    def add_existing_student(self,args):
        if self.active_class_id is not None:
            if len(args) != 1:
                print("Please enter a valid format to enroll a student in the class.")
                print("[add-student] [username]")
                return
            
            username = args[0]

            # We get the id of the student
            self.cursor.execute(
                """
                SELECT student_id
                FROM student
                WHERE student_username = %s 
                """,(username,)
                )

            result = self.cursor.fetchone()
            if not result:
                print("Error. Student does not exist.")
                return
            
            student_id = result[0]
                
            # We enroll student if exists
            try:
                self.cursor.execute(
                    """
                    INSERT INTO enroll (class_id, student_id) 
                    VALUES (%s, %s)
                    """,(self.active_class_id, student_id)
                    )
                self.conn.commit()
                print("Student sucessfully enrolled in the class.")
            
            except mysql.connector.IntegrityError:
                print("Student is already enrolled in this class.")
            except mysql.connector.Error as err:
                print("Error enrolling student:", err) # This catches any MySQL error related
            
        else:
            print("Select the class you want to enroll the student first")

    ####################################################################################
    # show all students in the current class
    def show_students_string(self,args):
        if self.active_class_id is None:
            print("Select a class first to see its students.")
            return
        if not args:
            print("Please enter a valid format to create search student.")
            print("[show-students] [string]")
            return
        # We convert the string to lower always
        search_string = args[0].lower()
        sql_format_to_find = f"%{search_string}%"

        self.cursor.execute(
            """
            select student.student_name, student.student_username
            from student 
            JOIN enroll on student.student_id = enroll.student_id
            WHERE enroll.class_id = %s AND
            LOWER(student.student_name) LIKE %s OR
            LOWER(student.student_username) LIKE %s
            """, (self.active_class_id, sql_format_to_find, sql_format_to_find)
        )
        result = self.cursor.fetchall()

        if result:
            print(f"Matching student records for '{search_string}':")
            print("Student Name - Username")
            for name,username in result:
                print(f" - {name} - {username}")
        else:
            print(f"No matching students found for {search_string}.")


    ############################################################################
    # show all students in the current class
    def show_students(self):
        if self.active_class_id is not None:
            self.cursor.execute(
                """
                select student.student_id,student.student_name 
                from student 
                JOIN enroll on student.student_id = enroll.student_id
                WHERE enroll.class_id = %s

                """, (self.active_class_id,)
            )
            result = self.cursor.fetchall()

            if result:
                print("Students enrolled:")
                print(f"{'ID':<10} {'Name':<30}")
                print("-" * 40)
                for student_id, student_name in result:
                    print(f"{student_id:<10} {student_name:<30}")
            else:
                print("No students enrolled in this class.")
        
        else:
            print("Select a class first to see its students.")

    ##################################################################################################################
    ################################## Category and Assignment Managment ############################################# 
    ##################################################################################################################
    #add a new assignment
    def add_assignment(self,args):
        if self.active_class_id is None:
            print("Select a class first to add an assignment to a category.")
            return

        if len(args) < 4:
            print("Please enter a valid format to create an assignment.")
            print("[Assignment Name(Unique)] [Category] [Description] [Points]")
            return
        
        name = args[0]
        category = args[1]
        points = args[-1]
        description = " ".join(args[2:-1])

        # Make sure points is decimal before we do anything to the DB
        try:
            points = float(points)
        except ValueError:
            print("Points must be a number")
            return

        # We check if assigment already exists in the class first
        self.cursor.execute(
            """
            SELECT *
            FROM assignment
            WHERE class_id = %s AND assignment_name = %s
            """,(self.active_class_id, name)
            )

        if self.cursor.fetchone():
            print("Assignment already exists for this class.")
            return
            
        
        # We get category_id
        self.cursor.execute(
            """
            SELECT category_id
            FROM category
            WHERE category_name = %s and category.class_id = %s 
            """,(category, self.active_class_id)
            )
        
        result = self.cursor.fetchone()
        if not result:
            print("Category does not exist in this class.")
            return

        category_id = result[0]    
        
        # We create assignment if everything is okay
        try:  
            self.cursor.execute(
                """
                INSERT INTO assignment (assignment_name, assignment_description, assignment_point_value, category_id, class_id) 
                VALUES (%s, %s, %s, %s ,%s)
                """,(name,description,points, category_id, self.active_class_id)
                )
            self.conn.commit()
            print("Assignment sucessfully created.")
        
        except mysql.connector.Error as err:
            print("Error creating assignment:", err) # This catches any MySQL error related
        
    
    ##############################################################################################
    # list the assignments with their point values, grouped by category
    def show_assignments(self):
        if self.active_class_id is not None:
            self.cursor.execute(
                """
                SELECT 
                    category.category_name,
                    assignment.assignment_name, 
                    assignment.assignment_point_value 
                    
                FROM assignment 
                JOIN category on assignment.category_id = category.category_id
                WHERE assignment.class_id = %s
                ORDER BY category.category_name, assignment_name

                """, (self.active_class_id,)
            )
            result = self.cursor.fetchall()

            if result:
                print("Assignments by Category")
                current_category = None

                #Display assignment group by category
                for category, name, value in result:
                    if category != current_category:
                        print(f"\n{category}")
                        current_category = category
                    print(f"   - {name} ({value} pts)")
            else:
                print("No assignments found.")
        else:
            print("Select a class first to see the assignments for each category.")
    
    ###############################################################################################
    #add a new category
    def add_category(self,args):
        if self.active_class_id is not None:
            if len(args) != 2:
                print("Please enter a valid format to create a category.")
                print("[Category Name] [Weight]")
                return
            
            name = args[0]
            weight = args[1]

            # Make sure weight is decimal before we do anything to the DB
            try:
                weight = float(weight)
            except ValueError:
                print("Weight must be a number")
                return

            # We check if category already exists first
            self.cursor.execute(
                """
                SELECT *
                FROM category
                WHERE class_id = %s AND category_name = %s
                """,(self.active_class_id, name)
                )

            if self.cursor.fetchone():
                print("Category already exists for this class.")
                return
                
            # We create Category if everything is okay
            try:
                self.cursor.execute(
                    """
                    INSERT INTO category (category_name, weight, class_id) 
                    VALUES (%s, %s, %s)
                    """,(name,weight,self.active_class_id)
                    )
                self.conn.commit()
                print("Category sucessfully created.")
            
            except mysql.connector.Error as err:
                print("Error creating category:", err) # This catches any MySQL error related
            
        else:
            print("Select a class first to add a category to it.")

    ##################################################################################3
    # list the categories with their weights
    def show_categories(self):
        if self.active_class_id is not None:
            self.cursor.execute(
                """
                SELECT 
                    category_name,
                    weight
                FROM category
                WHERE category.class_id = %s
                """, (self.active_class_id,)
            )
            result = self.cursor.fetchall()
            if result:
                print(f"{'Category':<25} {'Weight (%)':<10}")
                print("-" * 35)
                for name, weight in result:
                    print(f"{name:<25} {weight:<10.2f}")
            else:
                print("No categories for this class")
        else:
            print("Select a class first to see its categories.")



    ##################################################################################################################
    ######################################### Class Management ####################################################### 
    ##################################################################################################################
    # Create a class:
    def create_class(self,args):
        if len(args) < 5:
            print("Please enter a valid format for class")
            print("[Course_number] [Term] [Section] [Description] [Credits]")
            return
        course_number = args[0]
        term = args[1]
        section = args[2]
        credits = args[-1]
        description = " ".join(args[3:-1]) # this joins everything between section and credits, no proble with white spaces

        try:
            self.cursor.execute(
                """
                INSERT INTO class (course_number, term, section_number, class_description, credits) 
                VALUES (%s, %s, %s, %s, %s)
                """,(course_number, term,section,description,credits)
                )
            self.conn.commit()
            print("Class sucessfully created.")
        
        except mysql.connector.Error as err:
            print("Error creating class:", err) # This catches any MySQL error related
        

    ################################################################################################
    # Shows the currently-active class
    def show_class(self):
        if self.active_class_id is not None:
            self.cursor.execute(
                """
                SELECT 
                    class.class_id,
                    class.course_number,
                    class.term,
                    class.section_number
                FROM class
                WHERE class.class_id = %s
                """, (self.active_class_id,)
            )
            result = self.cursor.fetchall()
            for class_id, course_number, term, section in result:
                print(f"Current active class: ID:{class_id} {course_number} {term} Section {section}")
        else:
            print("No active class selected yet.")

    ################################################################################################3
    # Activate a class
    def select_class(self, args):
        
        # option 1: select-class CS410
        # Selects the only section of CS410 in the most recent term
        # if there is only one such section; if there are multiple sections it fails.
        if len(args) == 1:
            # First, we find the most recent term
            self.cursor.execute(
                """
                SELECT term
                FROM class
                WHERE course_number = %s
                ORDER BY term DESC
                LIMIT 1
                 
                """, (args[0],) # We send the argument (course_number) as tuple
            ) 
            result_query = self.cursor.fetchone()
            
            if result_query:
                most_recent_term = result_query[0]
            
            # now, we find sections in the term selected
            self.cursor.execute(
                """
                SELECT class_id
                FROM class
                WHERE course_number = %s and term = %s
            
                """, (args[0],most_recent_term) # We send the argument (course_number and term) as tuple
            ) 

        # Option2: select-class CS410 Sp20 
        # selects the only section of CS410 in Fall 2018
        # if there are multiple such sections, it fails.
        elif len(args) == 2:
            self.cursor.execute(
                """
                SELECT class_id
                FROM class
                WHERE course_number = %s AND term = %s 
                """, (args[0],args[1]) # We send the argument (course_number) as tuple
            )

        # Option 3:select-class CS410 Sp20 1 selects a specific section
        elif len(args) == 3:
            self.cursor.execute(
                """
                SELECT class_id
                FROM class
                WHERE course_number = %s AND term = %s AND section_number = %s 
                """, (args[0],args[1],args[2]) # We send the argument (course_number) as tuple
        )
            
        # if select command entered is invalid
        else:
            print("Please use the following format: select-class COURSE_NUMBER [TERM] [SECTION]")
            return

        #We make sure to only get one class selected  
        rows = self.cursor.fetchall()

        if len(rows) == 1:
            # We select the first class id (first column) from the first row
            self.active_class_id = rows[0][0]
            print(f"Class selected(ID: {self.active_class_id})")

        elif len(rows) > 1:
            print("Multiple matching class found. Try to be more specific.")
        
        else:
            print("No matching class found.")

    #################################################################################
    # List classes, with the # of students in each:
    def list_classes(self):
        self.cursor.execute(
            """
            SELECT 
                class.class_id,
                class.course_number,
                class.term,
                class.section_number,
                COUNT(enroll.student_id)
            FROM class
            LEFT JOIN enroll
            on class.class_id = enroll.class_id
            GROUP BY class.class_id

            """
        )
        results = self.cursor.fetchall()

        if not results:
            print("No classes found")
        
        else:
            for class_id, course_number, term, section, student_count in results:
                print(f"📚 {course_number} {term} Section {section} - {student_count} students enrolled")
   
    
    
    ##################################################################################################################
    ######################################### Run Program ############################################################ 
    ##################################################################################################################
    def run(self):
        print("Welcome to Class Manager - Enter 'commands' to see the list of available commands")
        while True:
            command = input("> ").strip()

            ######################################### Class Management #######################################################
            if command == "list-classes":
                self.list_classes()

            elif command.startswith("select-class"):
                self.select_class(command.split()[1:]) # we dont pass select-class as argument

            elif command == "show-class":
                self.show_class()

            elif command.startswith("new-class"):
                self.create_class(command.split()[1:]) # we dont pass new-class as argument
            

            ######################################### Category and Assignment Management #####################################
            elif command == "show-categories":
                self.show_categories()

            elif command.startswith("add-category"):
                self.add_category(command.split()[1:]) # we dont pass add-category as argument

            elif command == "show-assignment":
                self.show_assignments()

            elif command.startswith("add-assignment"):
                self.add_assignment(command.split()[1:]) # we dont pass add-assignment as argument


            ######################################### Student Management ####################################################
            elif command.startswith("show-students") and len(command.split()) > 1: # we need this to avoid conflict with normal show-student
                self.show_students_string(command.split()[1:]) # we dont pass show-students as argument
            
            elif command == "show-students":
                self.show_students()

            elif command.startswith("add-student") and len(command.split()) == 2: # we need this to avoid conflict with other add-student
                self.add_existing_student(command.split()[1:]) # we dont pass add-students as argument

            elif command.startswith("add-student") and len(command.split()) == 5:
                self.add_student(command.split()[1:])
            
            elif command.startswith("grade") and len(command.split()) == 4:
                self.grade_assignment(command.split()[1:])

            
            ######################################### Grade Reporting #######################################################
            elif command.startswith("student-grades") and len(command.split()) == 2:
                self.show_grades(command.split()[1:])

            elif command == "gradebook":
                self.gradebook()
            
            elif command == "commands":
                print("Use the following commands: ")
                print("new-class [course_number] [term] [section] [description] [credits]")
                print("list-classes")
                print("select-class [course_number] ([term] [section])")
                print("show-class")
                print("show-categories")
                print("add-category [name] [weight]")
                print("show-assignment")
                print("add-assignment [name] [Category] [Description] [points]")
                print("add-student [username] [studentid] [Last] [Firt]")
                print("add-student [username]")
                print("show-students")
                print("show-students [string]")
                print("grade [assignment_name] [username] [grade]")
                print("student-grades [username]")
                print("gradebook")
                print()

            elif command == "exit":
                print("Goodbye!")
                break
            else:
                print(f"Unknown command '{command}', enter a valid command")

def main():
    shell = ClassManagerShell()
    shell.run()

if __name__ == "__main__":
    main()