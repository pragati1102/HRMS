import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import User, Attendance, WorkLog, LeaveApplication, Salary

class Command(BaseCommand):
    help = 'Seeds the database with test data'

    def handle(self, *args, **options):
        self.stdout.write('Clearing existing data...')
        Salary.objects.all().delete()
        LeaveApplication.objects.all().delete()
        WorkLog.objects.all().delete()
        Attendance.objects.all().delete()
        User.objects.all().delete()

        self.stdout.write('Creating users...')
        # Create Admin
        admin = User.objects.create_superuser(
            username='admin',
            email='admin@hrms.com',
            first_name='System',
            last_name='Administrator',
            role='admin'
        )
        admin.set_password('admin123')
        admin.save()
        self.stdout.write(f'Created admin: {admin.username} (pw: admin123)')

        # Create Employees
        employees_data = [
            {
                'username': 'johndoe',
                'first_name': 'John',
                'last_name': 'Doe',
                'email': 'john.doe@hrms.com',
                'department': 'Engineering',
                'designation': 'Senior Developer',
                'joining_date': datetime.date(2025, 1, 12),  # Joined on 12th
                'salary_amount': 8500.00,
                'role': 'employee'
            },
            {
                'username': 'janesmith',
                'first_name': 'Jane',
                'last_name': 'Smith',
                'email': 'jane.smith@hrms.com',
                'department': 'HR',
                'designation': 'HR Manager',
                'joining_date': datetime.date(2025, 3, 31),  # Joined on 31st (boundary test)
                'salary_amount': 7200.00,
                'role': 'employee'
            },
            {
                'username': 'bobloader',
                'first_name': 'Bob',
                'last_name': 'Loader',
                'email': 'bob.loader@hrms.com',
                'department': 'Engineering',
                'designation': 'QA Engineer',
                'joining_date': datetime.date(2025, 5, 30),  # Joined on 30th (boundary test)
                'salary_amount': 6000.00,
                'role': 'employee'
            },
            {
                'username': 'alicebrown',
                'first_name': 'Alice',
                'last_name': 'Brown',
                'email': 'alice.brown@hrms.com',
                'department': 'Marketing',
                'designation': 'Designer',
                'joining_date': datetime.date(2025, 8, 15),  # Joined on 15th
                'salary_amount': 5500.00,
                'role': 'employee'
            }
        ]

        employees = []
        for emp_info in employees_data:
            emp = User.objects.create_user(
                username=emp_info['username'],
                email=emp_info['email'],
                first_name=emp_info['first_name'],
                last_name=emp_info['last_name'],
                department=emp_info['department'],
                designation=emp_info['designation'],
                joining_date=emp_info['joining_date'],
                salary_amount=emp_info['salary_amount'],
                role=emp_info['role']
            )
            emp.set_password('employee123')
            emp.save()
            employees.append(emp)
            self.stdout.write(f"Created employee: {emp.username} (pw: employee123)")

        # Create Attendance (today)
        self.stdout.write('Seeding today\'s attendance...')
        today = timezone.localdate()
        Attendance.objects.create(
            employee=employees[0], 
            date=today, 
            status='present',
            check_in=datetime.time(9, 0),
            check_out=datetime.time(17, 0)
        )
        Attendance.objects.create(
            employee=employees[1], 
            date=today, 
            status='absent'
        )
        # Bob loader is on leave
        Attendance.objects.create(
            employee=employees[2], 
            date=today, 
            status='leave'
        )
        # Leave employees[3] with no record for today to test 'No Record' rendering

        # Create Historical Attendance & WorkLogs (Last 5 days)
        self.stdout.write('Seeding historical attendance and work logs...')
        for i in range(1, 6):
            hist_date = today - datetime.timedelta(days=i)
            # Weekend check: skip Saturday (6) and Sunday (7) if desired, but let's just seed all
            for emp in employees:
                # john present, jane present/absent mix, bob half_day/present, alice present
                if emp.username == 'johndoe':
                    status = 'present'
                    hours = 8.00
                elif emp.username == 'janesmith':
                    status = 'present' if i % 2 == 0 else 'absent'
                    hours = 8.00 if status == 'present' else 0.00
                elif emp.username == 'bobloader':
                    status = 'half_day' if i % 3 == 0 else 'present'
                    hours = 4.00 if status == 'half_day' else 8.00
                else:
                    status = 'present'
                    hours = 8.00

                # Define check-in/out times for attendance
                check_in = None
                check_out = None
                if status == 'present':
                    check_in = datetime.time(9, 0)
                    check_out = datetime.time(17, 0)
                elif status == 'half_day':
                    check_in = datetime.time(9, 0)
                    check_out = datetime.time(13, 0)

                Attendance.objects.create(
                    employee=emp, 
                    date=hist_date, 
                    status=status,
                    check_in=check_in,
                    check_out=check_out
                )
                
                if hours > 0:
                    start_time = datetime.time(9, 0)
                    end_time = datetime.time(17, 0) if hours == 8.00 else datetime.time(13, 0)
                    WorkLog.objects.create(
                        employee=emp,
                        date=hist_date,
                        start_time=start_time,
                        end_time=end_time,
                        description=f"Worked on task for day -{i}."
                    )

        # Create Leave Applications
        self.stdout.write('Seeding leave applications...')
        # Bob has a pending leave
        LeaveApplication.objects.create(
            employee=employees[2],
            start_date=today + datetime.timedelta(days=2),
            end_date=today + datetime.timedelta(days=4),
            reason='Family emergency, need to travel.',
            status='pending'
        )
        # John has an approved leave in the past
        LeaveApplication.objects.create(
            employee=employees[0],
            start_date=today - datetime.timedelta(days=12),
            end_date=today - datetime.timedelta(days=10),
            reason='Routine dental checkup and rest.',
            status='approved',
            approved_by=admin
        )
        # Jane has a rejected leave
        LeaveApplication.objects.create(
            employee=employees[1],
            start_date=today + datetime.timedelta(days=10),
            end_date=today + datetime.timedelta(days=12),
            reason='Vacation trip.',
            status='rejected',
            approved_by=admin
        )

        self.stdout.write(self.style.SUCCESS('Successfully seeded database!'))
