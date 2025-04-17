# This is a note for a temporary project

This is a temporary django project in order to test first docker + database init.

Running docker compose: 
```bash
docker compose up
```

Inside container, you can:
- Load data: 
```bash
python manage.py migrate
python manage.py loaddata fixture.json
```

- Run the project: 
```bash
python manage.py runserver 0.0.0.0:8000
```

- Run unit test:
```bash
python manage.py test
```
You can also debug unit test by create .vscode/launch.json inside container:
```bash
{
    "configurations": [
        {
            "name": "Python: Django Debug Single Test",
            "type": "debugpy",
            "request": "launch",
            "program": "${workspaceFolder}/manage.py",
            "args": [
                "test",
                "tests.temps.views.test_student_views.StudentViewsTestCase"
            ],
            "django": true
        },  
    ]
}
```

You can import Postman collection to test the API