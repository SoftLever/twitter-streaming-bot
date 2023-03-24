FROM python:3.11.2-slim-buster

ENV HOME /root
ENV APP_HOME /application/
ENV C_FORCE_ROOT=true
ENV PYTHONUNBUFFERED 1

RUN mkdir -p $APP_HOME
WORKDIR $APP_HOME

# Install pip packages
ADD ./requirements.txt .

RUN pip install gunicorn
RUN pip install -r requirements.txt

RUN rm requirements.txt

# Copy code into Image
ADD ./thebot/ $APP_HOME
