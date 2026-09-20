To run the program on your local machine : 
use Bash commands : 
Navigate to backend files i.e. the apps/api folder 
	now run this commands :
	 	cd api
	 	python -m venv .venv && source .venv/bin/activate
		pip install -r requirements.txt
		uvicorn app.main:app --reload


Use another terminal to run the web part that is frontend part of the project 

Navigate to web directory of the project ie. apps/web
Run this commands : 
	npm install
	npm run dev