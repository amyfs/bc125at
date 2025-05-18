container:
	cp ../bc125at.py ../app.py ../listener.py .
	cp -r ../instance ../templates ../static .
	docker build -t amyfs/bc125at .

clean:
	rm *.py
	rm -r instance templates static

