# Evaluation-Tool-User-Service
A centralized identity provider service that handles authentication and user management for all applications in the ecosystem.

# How to run service (Development)
1. Setup env file like .example.env
2. Install VSCODE extension Dev Containers, Docker
3. Run docker compose to build the application
```bash
docker compose up
```
4. If you run code in VScode, you can enter **Containers** -> **Choose container** (user_management_service) -> **Attach Visual Studio Code** to open docker container in VSCode
5. Inside docker container, navigate to project folder
6. Open terminal, run migrate database using command 
```bash
python manage.py migrate
```
7. You can run the service without debug using
```bash
python manage.py runserver 0.0.0.0:8000
```
Or you can select **Run and Debug** section -> **Python: Django Debug Application** to run in debug mode

# How to run unit test
Begin after step 6, you can run all unit test using command:
```bash
python manage.py test <unit test path>
```
Or you can modify unit test path in file .vscode/launch.json and run **Python: Django Debug Single Test** in debug section for debugging
