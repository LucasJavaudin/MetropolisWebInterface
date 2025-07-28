FROM python:3.10-alpine
ENV PYTHONUNBUFFERED=1
RUN mkdir /metroweb
WORKDIR /metroweb
ADD . /metroweb/
RUN pip install -r requirements.txt
