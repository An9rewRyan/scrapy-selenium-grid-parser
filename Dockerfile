FROM python:3.9
WORKDIR /app

COPY . /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN pip install pipenv && pipenv install --system

ENV DISPLAY=:99

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]






