

# Learning Management System Clone (Full Stack Flask App with Database Design)

## Run Locally

### Prerequisites
1. Install Python
Follow the steps from the below reference document based on your Operating System. Reference: https://docs.python-guide.org/starting/installation/

### Steps

Clone the project or download the zip

```bash
  git clone https://link-to-project
```

Genegrate a virtual environment
```bash
  pip install venv
  python -m venv env
```

Activate the virtual env
```bash
  .\env\Scripts\activate
```

Install dependencies

```bash
  pip install -r requirements.txt
```

Create a config.py file and add your secret key

```python
  SECRET_KEY = "your_secret_key"
```

Create a db.py file and add the following code with your DB instance creds.

```python
  import mysql.connector
  def db_connection():
      conn = mysql.connector.connect(
          host="<hostName>",
          user="<userName>",
          password="<password>",
          database="<databaseName>",
          port="<portNumber>"
      )
      return conn
```

Start the server by running the command on root of the folder in terminal

```bash
  flask run
  flask run --debug  # if you want to automatically reload on changes in code
```
## Tools Used

mysql - https://pypi.org/project/mysql-connector-python/

flask - https://pypi.org/project/Flask/
