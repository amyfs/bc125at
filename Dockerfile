FROM alpine:latest
WORKDIR /root
RUN apk add --no-cache python3 py3-pip py3-pyserial py3-requests 
RUN apk add --no-cache py3-tqdm py3-flask py3-flask-sqlalchemy
RUN apk add --no-cache py3-pyaudio py3-speechrecognition 
RUN apk add --no-cache ffmpeg alsa-utils alsaconf
RUN pip install --break-system-packages pydub
COPY bc125at.py .
COPY listener.py .
COPY app.py .
COPY runner_t.sh .
COPY listener.pid .
COPY ../instance/ instance
COPY ../templates/ templates
COPY ../static/ static
#ENTRYPOINT exec top -b
ENTRYPOINT exec python app.py
