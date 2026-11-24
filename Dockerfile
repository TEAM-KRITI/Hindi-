FROM nikolaik/python-nodejs:python3.11-nodejs19

RUN rm -f /etc/apt/sources.list.d/yarn.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg aria2 git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app/
COPY . /app/

RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir --upgrade -r requirements.txt && \
    pip3 install --no-cache-dir six

CMD ["bash", "start"]
