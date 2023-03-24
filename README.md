## Running the app for the first time

1. ssh into the server.

2. Clone the project; https://github.com/SoftLever/twitter-streaming-bot.git

3. `cd twitter-streaming-bot`

4. `cp .env.sample .env && nano .env` then edit environment variables

5. `sudo docker-compose up --build -d`

6. `sudo docker-compose exec web python manage.py migrate`

8. `sudo docker-compose exec web python manage.py run_stream --user=username > /home/ubuntu/logs.log 2>&1 &`


## Changing filter stream

This has to be done every time you want to change the users and/or keywords to follow.

1. ssh into the server

2. If a stream is already running, disconnect by killing the process running it. You can find the process id by running `ps aux | grep run_stream`. Then `sudo kill -9 <pid>`

3. Finally, run 8 above

