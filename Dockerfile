FROM python:alpine
WORKDIR /app
COPY ./app /app
RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
ENTRYPOINT ["python", "main.py"]
