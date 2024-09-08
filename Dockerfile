FROM ubuntu:latest

RUN apt-get update

RUN apt-get install -y gdal-bin libgdal-dev
RUN apt-get install -y python3 python3-pip python3-gdal python3-boto3 python3-flask 
RUN apt-get install -y python3-flask-cors
RUN export CPLUS_INCLUDE_PATH=/usr/include/gdal
RUN export C_INCLUDE_PATH=/usr/include/gdal

RUN apt-get install -y curl

RUN apt-get install -y unzip


RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && \
    ./aws/install && \
    rm -rf awscliv2.zip

COPY aws-config /root/.aws

WORKDIR /app

COPY . /app

EXPOSE 5000

CMD ["python3", "main.py"]



