CREATE DATABASE class_manager;
USE class_manager;

CREATE TABLE class(
	class_id  INTEGER PRIMARY KEY AUTO_INCREMENT,
    course_number VARCHAR(200) NOT NULL,
    term VARCHAR(200) NOT NULL,
    section_number INTEGER NOT NULL,
    class_description TEXT,
    credits INT NOT NULL
);

CREATE TABLE category (
	category_id INTEGER PRIMARY KEY AUTO_INCREMENT,
    category_name VARCHAR(200) NOT NULL,
    weight DECIMAL NOT NULL,
    class_id INTEGER NOT NULL REFERENCES class,
    CHECK(weight > 0 and weight <= 100),
    
    FOREIGN KEY (class_id) REFERENCES class(class_id),
    INDEX (class_id)
);

CREATE TABLE assignment (
	assignment_id INTEGER PRIMARY KEY AUTO_INCREMENT,
    assignment_name VARCHAR(200),
    assignment_description TEXT,
    assignment_point_value DECIMAL,
    category_id INTEGER NOT NULL REFERENCES category,
    class_id INTEGER NOT NULL REFERENCES class,
    UNIQUE (assignment_name, class_id),
    
    FOREIGN KEY (category_id) REFERENCES category (category_id),
    FOREIGN KEY (class_id) REFERENCES class (class_id),
    INDEX (category_id),
    INDEX (class_id)
);

CREATE TABLE student(
	student_id INTEGER PRIMARY KEY,
    student_name VARCHAR(200),
    student_username VARCHAR(200) UNIQUE,
    student_email VARCHAR(200) UNIQUE
);

CREATE TABLE enroll(
	class_id INT NOT NULL,
    student_id INT NOT NULL,
    
    PRIMARY KEY(class_id, student_id),
    FOREIGN KEY(class_id) REFERENCES class (class_id),
    FOREIGN KEY(student_id) REFERENCES student (student_id),
    
    INDEX (class_id),
    INDEX (student_id)
);

CREATE TABLE grade(
	student_id INT NOT NULL,
    assignment_id INT NOT NULL,
    score DECIMAL NOT NULL,
    
    PRIMARY KEY (student_id, assignment_id),
    FOREIGN KEY (student_id) REFERENCES student (student_id),
    FOREIGN KEY (assignment_id) REFERENCES assignment (assignment_id),
    
    INDEX (student_id),
    INDEX (assignment_id)
);
