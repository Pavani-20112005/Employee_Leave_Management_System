# Employee Leave Management System

A beginner-friendly enterprise-style web application built with **Python, Flask and SQL (SQLite)**.

## Features
- Employee CRUD operations
- Employee search by name, department and role
- Leave request creation
- Leave approval/rejection workflow
- Dashboard with employee and leave statistics
- SQL JOIN queries for employee/leave reports
- Form validation for leave dates

## Tech Stack
- Python
- Flask
- SQL / SQLite
- HTML
- CSS

## Run the project

1. Install Python 3.10+.
2. Open a terminal in this project folder.
3. Create a virtual environment:
   `python -m venv venv`
4. Activate it:
   - Windows: `venv\Scripts\activate`
5. Install dependencies:
   `pip install -r requirements.txt`
6. Run:
   `python app.py`
7. Open:
   `http://127.0.0.1:5000`

The SQLite database `employee_leave.db` is created automatically.

## Interview explanation

Problem:
Organizations need a simple system to manage employee records and leave approvals.

Solution:
I developed a Flask-based application with SQL tables for employees and leave requests. The application performs CRUD operations, uses parameterized SQL queries, JOINs employee and leave data, and provides an approval/rejection workflow.

Future improvements:
- Login and role-based access
- MySQL/Oracle database
- REST API
- Email notifications
- Leave balance calculation
- Deployment on a cloud platform
